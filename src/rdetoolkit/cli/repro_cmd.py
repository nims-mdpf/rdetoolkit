"""Export and import reproducible run inputs.

The export argument is a run-report path so the command can locate both the
recorded calls and the run's sibling input directories.
"""

from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from collections.abc import Callable, Iterator
from functools import partial
from pathlib import Path, PurePosixPath
from typing import Annotated, Any

import typer
import yaml

from rdetoolkit.cli.run_cmd import load_config_overrides
from rdetoolkit.config.normalize import ConfigNormalizer
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.config_loader import load_config

# The digest is the one ``RunReport.config_digest`` carries; importing the
# Runner's private function keeps "same config" defined in exactly one place.
from rdetoolkit.runner.lifecycle import _config_digest
from rdetoolkit.runner.paths import resolve_data_root
from rdetoolkit.types import RdeConfig

if sys.version_info >= (3, 11):
    from typing import Never
else:
    from typing_extensions import Never


app = typer.Typer(help="Export and import reproducible run inputs.")
_INPUT_DIRS = ("inputdata", "invoice", "tasksupport")


def _usage_error(message: str) -> Never:
    typer.echo(message, err=True)
    raise typer.Exit(code=3)


def _validate_report(path: Path) -> RunReport:
    try:
        return RunReport.from_json(path.read_text(encoding="utf-8"))
    except (OSError, KeyError, TypeError, ValueError) as exc:
        _usage_error(f"Unable to read run report {path}: {exc}")


def _project_roots(data_root: Path) -> list[Path]:
    """Return the project roots whose Runner data root is ``data_root``.

    A nested layout is run from ``data_root.parent``; an alias-flat project is
    run from ``data_root`` itself. Both are checked (a nested ``data`` root
    matches both spellings), parent first.
    """
    return [candidate for candidate in (data_root.parent, data_root) if resolve_data_root(candidate) == data_root]


def _v1_entry_config(root: Path, data_root: Path) -> RdeConfig:
    """Rebuild the config ``workflows.run(custom_dataset_function=...)`` resolves.

    The v1 callback entry does not use v2 discovery: it reads
    ``data/tasksupport`` with the v1 loader and normalizes the result with
    ``origin="v1"`` (v1 defaults are fail-fast). Without this candidate every
    v1 callback run without a config file would look like an unrecoverable
    override.
    """
    from rdetoolkit.config import load_config as load_v1_config  # noqa: PLC0415 -- v1 model layer, only for v1 runs

    return ConfigNormalizer().normalize(
        load_v1_config(str(data_root / "tasksupport"), config=None),
        root=root,
        origin="v1",
    )


def _config_candidates(data_root: Path, overrides: dict[str, Any] | None) -> Iterator[RdeConfig]:
    """Yield every effective config the Runner could have used for this data root.

    The order is fixed: for each project root from :func:`_project_roots`
    (``data_root.parent`` first, then ``data_root``),

    1. the v2 Runner discovery, ``load_config(root, overrides, data_root=...)``
       (``rdetoolkit run --flow`` and the v2 Python API);
    2. only when no ``--config`` overrides were given, the v1 callback entry
       config from :func:`_v1_entry_config` (``workflows.run`` with
       ``config=None``), because that entry never merges overrides.

    The caller accepts the first candidate whose digest equals the report's,
    so the order only decides which of several digest-identical configs is
    archived, never whether a mismatching one is. A source that no longer loads
    is skipped rather than raised: it cannot reproduce the digest, and the
    caller reports that as one usage error.
    """
    for root in _project_roots(data_root):
        builders: list[Callable[[], RdeConfig]] = [partial(load_config, root, overrides, data_root=data_root)]
        if overrides is None:
            builders.append(partial(_v1_entry_config, root, data_root))
        for build in builders:
            try:
                yield build()
            except Exception:  # noqa: BLE001,S112 -- any loader failure means "not this source"
                continue


def _effective_config(report: RunReport, data_root: Path, config_option: Path | None) -> RdeConfig:
    """Return the discovered config whose digest equals the report's, or exit 3."""
    overrides = load_config_overrides(config_option)
    for config in _config_candidates(data_root, overrides):
        if _config_digest(config) == report.config_digest:
            return config
    if config_option is not None:
        _usage_error(
            f"The configuration discovered for {data_root} merged with --config {config_option} does not "
            f"reproduce the run's config_digest {report.config_digest}. Pass the override YAML the run used.",
        )
    _usage_error(
        f"The run's config_digest {report.config_digest} does not match the configuration discovered for "
        f"{data_root}: the run used overrides (run --config or the Python API) that cannot be recovered "
        "from files. Pass the same override YAML with 'rdetoolkit repro export --config <yaml>'.",
    )


def _replays_to(text: str, digest: str) -> bool:
    """Whether ``text`` as an archive-root rdeconfig.yaml reloads to ``digest``."""
    with tempfile.TemporaryDirectory(prefix="rdetoolkit-repro-") as scratch:
        root = Path(scratch)
        (root / "rdeconfig.yaml").write_text(text, encoding="utf-8")
        return _config_digest(load_config(root, data_root=root / "data")) == digest


def _config_yaml(config: RdeConfig, digest: str) -> str:
    """Serialize the effective config as v2-form YAML that replays to ``digest``.

    Only non-default values are written so a replay does not see defaults as
    explicitly set. If that form ever fails to reload to the same digest, the
    full dump is used instead; the digest is the contract, not the form.

    Keys keep their insertion order (``sort_keys=False``): ``config_digest``
    hashes the dump as-is, so sorting a free-form mapping such as ``custom``
    would make a valid config unreproducible.
    """
    dumps: tuple[Callable[[], dict[str, Any]], ...] = (
        lambda: config.model_dump(mode="json", exclude_defaults=True),
        lambda: config.model_dump(mode="json"),
    )
    for dump in dumps:
        text = yaml.safe_dump(dump(), sort_keys=False, allow_unicode=True)
        if _replays_to(text, digest):
            return text
    _usage_error(f"The effective configuration cannot be written in a form that reproduces config_digest {digest}.")


@app.command("export")
def export_run(
    run_report: Annotated[Path, typer.Argument(metavar="<run_report.json>")],
    output: Annotated[Path, typer.Option("--output", help="Destination zip archive.")],
    config: Annotated[
        Path | None,
        typer.Option("--config", help="The YAML overrides the run used (same form as 'run --config')."),
    ] = None,
) -> None:
    """Archive a report, its inputs, and the run's effective config."""
    report_path = run_report.resolve()
    report = _validate_report(report_path)
    data_root = report_path.parent.parent
    for dirname in _INPUT_DIRS:
        source = data_root / dirname
        if not source.is_dir():
            _usage_error(f"Missing source directory: {source}")

    # Resolved before the archive is opened, so a refusal leaves no file behind.
    config_text = _config_yaml(_effective_config(report, data_root, config), report.config_digest)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for dirname in _INPUT_DIRS:
                _write_tree(archive, data_root / dirname, Path("data") / dirname)
            archive.write(report_path, Path("data") / "logs" / report_path.name)
            archive.writestr("rdeconfig.yaml", config_text)
            manifest = {"schema_version": "1", "config_included": True, "config_digest": report.config_digest}
            archive.writestr("repro_manifest.json", json.dumps(manifest, indent=2))
    except OSError as exc:
        _usage_error(f"Unable to write archive {output}: {exc}")
    typer.echo(str(output))


def _write_tree(archive: zipfile.ZipFile, source: Path, destination: Path) -> None:
    _write_directory(archive, destination)
    for path in sorted(source.rglob("*")):
        if path.is_file():
            archive.write(path, destination / path.relative_to(source))
        elif path.is_dir() and not any(path.iterdir()):
            _write_directory(archive, destination / path.relative_to(source))


def _write_directory(archive: zipfile.ZipFile, destination: Path) -> None:
    name = destination.as_posix().rstrip("/") + "/"
    info = zipfile.ZipInfo(name)
    info.external_attr = (0o40775 << 16) | 0x10
    archive.writestr(info, b"")


@app.command("import")
def import_run(
    archive_path: Annotated[Path, typer.Argument(metavar="<archive>")],
    target: Annotated[Path, typer.Argument(metavar="<target_dir>")],
) -> None:
    """Reconstruct archived run inputs beneath a fresh target directory."""
    if target.exists() and not target.is_dir():
        _usage_error(f"Import target is not a directory: {target}")
    if target.exists() and any(target.iterdir()):
        _usage_error(f"Import target is not empty: {target}")
    try:
        with zipfile.ZipFile(archive_path) as archive:
            _validate_members(archive.infolist())
            target.mkdir(parents=True, exist_ok=True)
            archive.extractall(target)
    except (OSError, zipfile.BadZipFile) as exc:
        _usage_error(f"Unable to import archive {archive_path}: {exc}")
    typer.echo(str(target))


def _validate_members(members: list[zipfile.ZipInfo]) -> None:
    for member in members:
        path = PurePosixPath(member.filename)
        if path.is_absolute() or ".." in path.parts:
            _usage_error(f"Unsafe archive member: {member.filename}")
