"""Export and import reproducible run inputs.

The export argument is a run-report path so the command can locate both the
recorded calls and the run's sibling input directories.

A full export is a local reproduction: it holds the run's raw inputs, invoice,
report and effective config. ``--manifest-only`` writes structural metadata,
digests and the ``report diagnose`` envelope instead, and cannot be replayed.
Import treats an archive as untrusted: every member is checked before anything
is extracted, extraction goes to a staging directory next to the target, and
the target appears only after the config digests agree (#671).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import unicodedata
import zipfile
import zlib
from collections.abc import Callable, Iterator
from functools import partial
from pathlib import Path, PurePosixPath
from typing import Annotated, Any

import typer
import yaml

from rdetoolkit.cli._help import EXIT_CLICK_USAGE, EXIT_OK, CommandHelp
from rdetoolkit.cli.run_cmd import load_config_overrides
from rdetoolkit.config.normalize import ConfigNormalizer
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.config_loader import compute_config_digest, load_config
from rdetoolkit.runner.paths import resolve_data_root
from rdetoolkit.types import RdeConfig

if sys.version_info >= (3, 11):
    from typing import Never
else:
    from typing_extensions import Never


REPRO_HELP = CommandHelp(
    summary="Export a finished run's inputs and effective config to a zip, and import such a zip to rerun it.",
    details=(
        "A full export contains the run's raw inputs, invoice, report and config, which may be confidential: "
        "keep it local unless you have reviewed it. `--manifest-only` writes digests and diagnostics without data."
    ),
    examples=(
        "rdetoolkit repro export data/logs/run_report_<id>.json -o repro.zip",
        "rdetoolkit repro import repro.zip ./replay",
    ),
    exit_codes=(EXIT_OK, EXIT_CLICK_USAGE, (3, "unreadable report or archive, missing or unsafe inputs, or an unreproducible config")),
    see_also=("rdetoolkit run", "rdetoolkit report diagnose"),
)

EXPORT_HELP = CommandHelp(
    summary="Archive a run report, the run's input directories, and its effective rdeconfig.yaml into one zip.",
    details=(
        "The full archive is for local reproduction. It contains every file under the three input directories, "
        "which may hold unpublished data or credentials; it is never uploaded. `--manifest-only` writes "
        "`repro_manifest.json` alone: file sizes and SHA-256 digests by directory, no file names or contents, "
        "and the `report diagnose` envelope. That archive cannot be imported or replayed."
    ),
    inputs=(
        (
            "`RUN_REPORT`: `data/logs/run_report_<run_id>.json`; `data/inputdata`, `data/invoice`, and "
            "`data/tasksupport` next to it must still exist and contain no symbolic links or special files."
        ),
        (
            "`--config`: the YAML overrides the run used (`rdetoolkit run --config`). Required when the run used "
            "overrides, because the config is only archived if it reproduces the report's `config_digest`."
        ),
        "`--manifest-only`: write metadata only (manifest `schema_version` `\"2\"`); `--config` is not needed.",
    ),
    outputs=(
        (
            "Writes the zip given by `-o/--output` (parent directories are created). An existing file is never replaced. "
            "A full zip holds `data/{inputdata,invoice,tasksupport}`, `data/logs/<report>`, `rdeconfig.yaml`, and "
            "`repro_manifest.json` (`schema_version` `\"1\"`)."
        ),
        (
            "Before writing a full zip, prints to stderr what it will contain (files and bytes per directory) and a "
            "confidentiality warning. Prints the archive path on stdout."
        ),
    ),
    examples=(
        "rdetoolkit repro export data/logs/run_report_<id>.json -o repro.zip",
        "rdetoolkit repro export data/logs/run_report_<id>.json -o r.zip \\",
        "    --config overrides.yaml",
        "rdetoolkit repro export run_report_<id>.json -o m.zip --manifest-only",
    ),
    exit_codes=(
        EXIT_OK,
        EXIT_CLICK_USAGE,
        (3, (
            "unreadable report, a missing input directory, a link or special file among the inputs, an existing "
            "output, inputs over the archive limits, or a config that does not reproduce the digest"
        )),
    ),
    see_also=("rdetoolkit repro import", "rdetoolkit report diagnose", "rdetoolkit run"),
)

IMPORT_HELP = CommandHelp(
    summary="Unpack a full `repro export` zip into an empty directory, ready for `rdetoolkit run`.",
    details=(
        "The zip is checked before anything is extracted: only the `repro export` layout is accepted, and absolute "
        "or `..` paths, backslashes, control characters, links and special files, duplicate names (ignoring case), "
        "and archives over the size limits are refused. It is extracted to a staging directory next to the target, "
        "which becomes the target only after the archived config reloads to the manifest's and the report's "
        "`config_digest`. A matching digest shows consistency, not who made the archive: review imported data and "
        "config before running your flow on them."
    ),
    inputs=(
        "`ARCHIVE`: a full zip written by `rdetoolkit repro export` (a `--manifest-only` zip is refused).",
        "`TARGET_DIR`: a new or empty directory, not a symbolic link.",
    ),
    outputs=(
        (
            "Creates `TARGET_DIR` with the archived project and prints its path. Never overwrites: a non-empty target "
            "is refused, and a failed import leaves the target as it was."
        ),
    ),
    examples=(
        "rdetoolkit repro import repro.zip ./replay",
        "rdetoolkit repro import downloads/repro.zip ../replays/run_0001",
    ),
    exit_codes=(
        EXIT_OK,
        EXIT_CLICK_USAGE,
        (3, "the target is not empty, the zip is unreadable, or a member, the manifest, or the config digest is not acceptable"),
    ),
    see_also=("rdetoolkit repro export", "rdetoolkit run"),
)

app = typer.Typer(help=REPRO_HELP.render(), short_help=REPRO_HELP.summary, no_args_is_help=True)
_INPUT_DIRS = ("inputdata", "invoice", "tasksupport")
_MANIFEST = "repro_manifest.json"
_CONFIG = "rdeconfig.yaml"

# Archive limits, checked on import and (so an export always imports) before an export is kept.
_MAX_MEMBERS = 100_000
_MAX_TOTAL_BYTES = 16 * 1024**3
#: Deflate cannot expand data more than about 1032:1, so a larger whole-archive
#: ratio means overlapping or forged entries (a zip bomb).
_MAX_COMPRESSION_RATIO = 1100
_MAX_MANIFEST_BYTES = 1024 * 1024
_MAX_PATH_LENGTH = 1024
_MAX_PATH_DEPTH = 64
#: Names that only Windows reads as drives, streams or devices; refused only there,
#: where they would escape the staging directory or open a device.
_WINDOWS = os.name == "nt"
_WINDOWS_DEVICES = frozenset({"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))})
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_REMEDIATION_ARCHIVE = "Remediation: import only a full archive written by 'rdetoolkit repro export', unmodified."
_REMEDIATION_EXPORT = "Remediation: rename or reduce the inputs so that 'rdetoolkit repro import' can accept them, then export again."


def _usage_error(message: str) -> Never:
    typer.echo(message, err=True)
    raise typer.Exit(code=3)


def _validate_report(path: Path) -> RunReport:
    try:
        return RunReport.from_json(path.read_text(encoding="utf-8"))
    except (OSError, KeyError, TypeError, ValueError) as exc:
        _usage_error(
            f"Unable to read run report {path}: {exc}\n"
            "Remediation: pass the run_report_<run_id>.json file that 'rdetoolkit run' wrote under data/logs/.",
        )


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
       (``rdetoolkit run pkg.mod:flow`` and the v2 Python API);
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
        if compute_config_digest(config) == report.config_digest:
            return config
    if config_option is not None:
        _usage_error(
            f"The configuration discovered for {data_root} merged with --config {config_option} does not "
            f"reproduce the run's config_digest {report.config_digest}.\nRemediation: pass the override YAML the run used.",
        )
    _usage_error(
        f"The run's config_digest {report.config_digest} does not match the configuration discovered for "
        f"{data_root}: the run used overrides (run --config or the Python API) that cannot be recovered "
        "from files.\nRemediation: pass the same override YAML with 'rdetoolkit repro export --config <yaml>'.",
    )


def _replays_to(text: str, digest: str) -> bool:
    """Whether ``text`` as an archive-root rdeconfig.yaml reloads to ``digest``."""
    with tempfile.TemporaryDirectory(prefix="rdetoolkit-repro-") as scratch:
        root = Path(scratch)
        (root / "rdeconfig.yaml").write_text(text, encoding="utf-8")
        return compute_config_digest(load_config(root, data_root=root / "data")) == digest


def _config_yaml(config: RdeConfig, digest: str) -> str:
    """Serialize the effective config as v2-form YAML that replays to ``digest``.

    Only non-default values are written so a replay does not see defaults as
    explicitly set. If that form ever fails to reload to the same digest, the
    full dump is used instead; the digest is the contract, not the form.

    Keys are sorted: ``config_digest`` is computed over key-sorted JSON, so key
    order never affects whether the archived form replays.
    """
    dumps: tuple[Callable[[], dict[str, Any]], ...] = (
        lambda: config.model_dump(mode="json", exclude_defaults=True),
        lambda: config.model_dump(mode="json"),
    )
    for dump in dumps:
        text = yaml.safe_dump(dump(), sort_keys=True, allow_unicode=True)
        if _replays_to(text, digest):
            return text
    _usage_error(f"The effective configuration cannot be written in a form that reproduces config_digest {digest}.")


@app.command("export", help=EXPORT_HELP.render(), short_help=EXPORT_HELP.summary)
def export_run(
    run_report: Annotated[Path, typer.Argument(metavar="RUN_REPORT", help="Path to run_report_<run_id>.json.")],
    output: Annotated[Path, typer.Option("-o", "--output", help="Destination zip archive; must not exist.")],
    config: Annotated[
        Path | None,
        typer.Option("--config", help="The YAML overrides the run used (same form as 'run --config')."),
    ] = None,
    manifest_only: Annotated[
        bool,
        typer.Option("--manifest-only", help="Write digests and diagnostics only: no input data; cannot be imported."),
    ] = False,
) -> None:
    """Archive a report, its inputs, and the run's effective config, or only their metadata."""
    if output.exists() or output.is_symlink():
        _usage_error(f"Export destination already exists: {output}\nRemediation: pass an -o path that does not exist yet.")
    report_path = run_report.resolve()
    data_root = report_path.parent.parent
    if manifest_only:
        manifest = _metadata_manifest(report_path, _source_entries(data_root))
        _export_archive(output, lambda archive: archive.writestr(_MANIFEST, json.dumps(manifest, indent=2)))
    else:
        report = _validate_report(report_path)
        entries = _source_entries(data_root)
        # Resolved before the archive is opened, so a refusal leaves no file behind.
        config_text = _config_yaml(_effective_config(report, data_root, config), report.config_digest)
        _preview_export(entries, report_path, config_text)
        manifest = {"schema_version": "1", "config_included": True, "config_digest": report.config_digest}
        _export_archive(output, partial(_write_full_archive, entries=entries, report_path=report_path, config_text=config_text, manifest=manifest))
    typer.echo(str(output))


def _walk_error(error: OSError) -> Never:
    raise error


def _source_entries(data_root: Path) -> list[tuple[Path, str]]:
    """List the three input trees as ``(path, archive name)``, refusing what an archive must not hold.

    An unreadable directory fails instead of being skipped, and a link or special
    file fails instead of being followed: the archive would otherwise silently
    omit inputs or include data from outside the project.
    """
    entries: list[tuple[Path, str]] = []
    for dirname in _INPUT_DIRS:
        source = data_root / dirname
        if source.is_symlink() or not source.is_dir():
            _usage_error(
                f"Missing source directory: {source}\n"
                "Remediation: export from the project whose data/ directory produced the report; "
                "the input directories must still exist (as directories, not links).",
            )
        try:
            for root, directories, filenames in os.walk(source, onerror=_walk_error):
                directories.sort()
                entries.append((Path(root), (Path("data") / Path(root).relative_to(data_root)).as_posix()))
                for name in sorted(filenames):
                    path = Path(root) / name
                    if path.is_symlink() or not path.is_file():
                        _usage_error(
                            f"Input is a symbolic link or special file: {path}\n"
                            "Remediation: copy the file it refers to into the project, or remove it, then export again.",
                        )
                    entries.append((path, (Path("data") / path.relative_to(data_root)).as_posix()))
                # A linked directory is listed by os.walk but never entered.
                for name in directories:
                    if (Path(root) / name).is_symlink():
                        _usage_error(
                            f"Input is a symbolic link: {Path(root) / name}\n"
                            "Remediation: copy the directory it refers to into the project, then export again.",
                        )
        except OSError as exc:
            _usage_error(f"Unable to read input directory {source}: {exc}\nRemediation: make every input readable, then export again.")
        if len(entries) > _MAX_MEMBERS:
            _usage_error(f"The inputs hold more than {_MAX_MEMBERS} files and directories, the archive limit.")
    return entries


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(partial(source.read, 1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _metadata_manifest(report_path: Path, entries: list[tuple[Path, str]]) -> dict[str, Any]:
    """Describe the inputs without their names or contents, plus the ``report diagnose`` envelope."""
    from rdetoolkit.report.diagnosis import diagnose_report

    try:
        diagnostics = diagnose_report(report_path)
    except (OSError, UnicodeError, KeyError, TypeError, ValueError, RecursionError):
        _usage_error(
            "Unable to read a supported run report.\n"
            "Remediation: pass the run_report_<run_id>.json file that 'rdetoolkit run' wrote under data/logs/, unmodified.",
        )
    config_digest = RunReport.from_json(report_path.read_text(encoding="utf-8")).config_digest
    directories = {name: {"file_count": 0, "byte_count": 0} for name in _INPUT_DIRS}
    files: list[dict[str, Any]] = []
    try:
        for path, name in entries:
            if path.is_file():
                category = PurePosixPath(name).parts[1]
                size = path.stat().st_size
                directories[category]["file_count"] += 1
                directories[category]["byte_count"] += size
                files.append({"file_id": len(files) + 1, "category": category, "byte_count": size, "sha256": _file_digest(path)})
    except OSError as exc:
        _usage_error(f"Unable to read input file: {exc}\nRemediation: make every input readable, then export again.")
    return {
        "schema_version": "2",
        "format": "rdetoolkit.repro-manifest",
        "archive_kind": "manifest-only",
        "replayable": False,
        "config_included": False,
        "config_digest": config_digest if isinstance(config_digest, str) and _DIGEST.match(config_digest) else None,
        "directories": directories,
        "files": files,
        "diagnostics": diagnostics,
    }


def _report_archive_name(path: Path) -> str:
    # Import accepts only the Runner's report name; any other name is normalised.
    filename = path.name if path.name.startswith("run_report_") and path.suffix == ".json" else "run_report_export.json"
    return f"data/logs/{filename}"


def _preview_export(entries: list[tuple[Path, str]], report_path: Path, config_text: str) -> None:
    typer.echo(
        "Warning: this archive contains the run's raw input files, invoice, report and effective config. They may "
        "hold unpublished research data, personal data or credentials. Review the archive before sharing it; "
        "nothing is uploaded. Use --manifest-only for metadata without data.",
        err=True,
    )
    for dirname in _INPUT_DIRS:
        sizes = [path.stat().st_size for path, name in entries if name.startswith(f"data/{dirname}/") and path.is_file()]
        typer.echo(f"  data/{dirname}/: {len(sizes)} files, {sum(sizes)} bytes", err=True)
    report_size = report_path.stat().st_size
    config_size = len(config_text.encode("utf-8"))
    typer.echo(f"  {_report_archive_name(report_path)}: {report_size} bytes", err=True)
    typer.echo(f"  {_CONFIG}: {config_size} bytes (effective config)", err=True)
    total = sum(path.stat().st_size for path, _ in entries if path.is_file()) + report_size + config_size
    typer.echo(f"  total before compression: {total} bytes", err=True)


def _write_full_archive(
    archive: zipfile.ZipFile, *, entries: list[tuple[Path, str]], report_path: Path, config_text: str, manifest: dict[str, Any],
) -> None:
    for path, name in entries:
        if path.is_dir():
            _write_directory(archive, name)
        else:
            archive.write(path, name)
    archive.write(report_path, _report_archive_name(report_path))
    archive.writestr(_CONFIG, config_text)
    archive.writestr(_MANIFEST, json.dumps(manifest, indent=2))
    # Refuse now rather than hand over an archive that import would refuse.
    _validate_members(archive.infolist(), remediation=_REMEDIATION_EXPORT)


def _write_directory(archive: zipfile.ZipFile, name: str) -> None:
    info = zipfile.ZipInfo(name.rstrip("/") + "/")
    info.external_attr = (0o40775 << 16) | 0x10
    archive.writestr(info, b"")


def _export_archive(output: Path, write: Callable[[zipfile.ZipFile], None]) -> None:
    """Create ``output`` exclusively and fill it; remove it again if anything fails."""
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        stream = output.open("xb")
    except FileExistsError:
        _usage_error(f"Export destination already exists: {output}\nRemediation: pass an -o path that does not exist yet.")
    except OSError as exc:
        _usage_error(f"Unable to write archive {output}: {exc}\nRemediation: pass an -o path in a writable directory.")
    try:
        with stream, zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            write(archive)
    except BaseException as exc:
        output.unlink(missing_ok=True)
        if isinstance(exc, OSError):
            _usage_error(f"Unable to write archive {output}: {exc}\nRemediation: check that the inputs are readable and the disk has space.")
        raise


@app.command("import", help=IMPORT_HELP.render(), short_help=IMPORT_HELP.summary)
def import_run(
    archive_path: Annotated[Path, typer.Argument(metavar="ARCHIVE", help="Zip written by 'rdetoolkit repro export'.")],
    target: Annotated[Path, typer.Argument(metavar="TARGET_DIR", help="New or empty directory to extract into.")],
) -> None:
    """Check an archive, stage it next to ``target``, and publish it there only if it is consistent."""
    _validate_target(target)
    try:
        archive_size = archive_path.stat().st_size
        with zipfile.ZipFile(archive_path) as archive:
            _validate_members(archive.infolist(), archive_size=archive_size)
            manifest = _read_manifest(archive)
            target.parent.mkdir(parents=True, exist_ok=True)
            # Same parent, so publishing is one rename; removed on every exit path.
            with tempfile.TemporaryDirectory(prefix=".rdetoolkit-import-", dir=target.parent) as scratch:
                stage = Path(scratch) / "project"
                stage.mkdir()
                _extract_members(archive, stage)
                _validate_replay(stage, manifest)
                _publish(stage, target)
    # Not RuntimeError: typer.Exit is one, and the refusals above must keep their own message.
    except (OSError, EOFError, ValueError, zlib.error, zipfile.BadZipFile, NotImplementedError) as exc:
        _usage_error(f"Unable to import archive {archive_path}: {exc}\n{_REMEDIATION_ARCHIVE}")
    typer.echo(str(target))


def _validate_target(target: Path) -> None:
    if target.is_symlink():
        _usage_error(f"Import target is a symbolic link: {target}\nRemediation: pass a new or empty directory.")
    if target.exists() and not target.is_dir():
        _usage_error(f"Import target is not a directory: {target}\nRemediation: pass a new or empty directory.")
    if target.exists() and any(target.iterdir()):
        _usage_error(f"Import target is not empty: {target}\nRemediation: pass a new or empty directory.")


def _unsafe_name(member: zipfile.ZipInfo) -> bool:
    name = member.filename
    parts = name.rstrip("/").split("/")
    return (
        # zipfile cuts a name at NUL (and turns os.sep into "/"); the raw spelling must survive unchanged.
        member.orig_filename != name
        or not 0 < len(name) <= _MAX_PATH_LENGTH
        or len(parts) > _MAX_PATH_DEPTH
        or name.startswith("/")
        or "\\" in name
        or any(ord(char) < 0x20 or ord(char) == 0x7F for char in name)  # noqa: PLR2004 -- ASCII control characters
        or any(part in {"", ".", ".."} for part in parts)
        or (_WINDOWS and any(":" in part or part.endswith((".", " ")) or part.split(".")[0].casefold() in _WINDOWS_DEVICES for part in parts))
    )


def _allowed_member(parts: tuple[str, ...], is_dir: bool) -> bool:
    """Whether a path belongs to the ``repro export`` layout."""
    if len(parts) == 1:
        return parts[0] == "data" if is_dir else parts[0] in {_MANIFEST, _CONFIG}
    if parts[0] != "data":
        return False
    if parts[1] in _INPUT_DIRS:
        return len(parts) > 2 or is_dir  # noqa: PLR2004
    if parts[1] == "logs":
        return len(parts) == 2 if is_dir else len(parts) == 3 and parts[2].startswith("run_report_") and parts[2].endswith(".json")  # noqa: PLR2004
    return False


def _check_member(member: zipfile.ZipInfo, remediation: str) -> None:
    if _unsafe_name(member):
        _usage_error(f"Unsafe archive member name: {member.filename!r}\n{remediation}")
    kind = stat.S_IFMT(member.external_attr >> 16)
    if kind not in {0, stat.S_IFDIR if member.is_dir() else stat.S_IFREG} or member.flag_bits & 0x1:
        _usage_error(f"Archive member is a link, special file, or encrypted: {member.filename!r}\n{remediation}")
    if member.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED} or (member.is_dir() and member.file_size):
        _usage_error(f"Archive member uses an unsupported encoding: {member.filename!r}\n{remediation}")
    if not _allowed_member(PurePosixPath(member.filename).parts, member.is_dir()):
        _usage_error(f"Archive member is not part of a reproduction archive: {member.filename!r}\n{remediation}")


def _validate_members(members: list[zipfile.ZipInfo], *, archive_size: int | None = None, remediation: str = _REMEDIATION_ARCHIVE) -> None:
    """Refuse an archive unless every member is a safe regular file or directory of the export layout.

    Args:
        members: The archive's entries.
        archive_size: Bytes of the archive file; enables the whole-archive ratio check
            (export passes None: it wrote the entries itself).
        remediation: The remediation line printed with a refusal.
    """
    total = sum(member.file_size for member in members)
    if len(members) > _MAX_MEMBERS or total > _MAX_TOTAL_BYTES:
        _usage_error(f"Archive exceeds {_MAX_MEMBERS} entries or {_MAX_TOTAL_BYTES} bytes uncompressed.\n{remediation}")
    if archive_size is not None and total > max(archive_size, 1) * _MAX_COMPRESSION_RATIO:
        _usage_error(f"Archive expands more than {_MAX_COMPRESSION_RATIO}:1, which only overlapping or forged entries do.\n{remediation}")
    seen: dict[str, bool] = {}
    for member in members:
        _check_member(member, remediation)
        # One spelling per file on case-insensitive or normalising file systems (Windows, macOS).
        key = unicodedata.normalize("NFC", member.filename.rstrip("/")).casefold()
        if key in seen:
            _usage_error(f"Archive member is duplicated: {member.filename!r}\n{remediation}")
        seen[key] = member.is_dir()
    for key in seen:
        if any(not seen.get(parent.as_posix(), True) for parent in PurePosixPath(key).parents):
            _usage_error(f"Archive member is inside a file entry: {key!r}\n{remediation}")


def _read_manifest(archive: zipfile.ZipFile) -> dict[str, Any]:
    try:
        member = archive.getinfo(_MANIFEST)
    except KeyError:
        _usage_error(f"Archive has no {_MANIFEST}.\n{_REMEDIATION_ARCHIVE}")
    if member.file_size > _MAX_MANIFEST_BYTES:
        _usage_error(f"{_MANIFEST} exceeds {_MAX_MANIFEST_BYTES} bytes.\n{_REMEDIATION_ARCHIVE}")
    try:
        manifest = json.loads(archive.read(member))
    except (ValueError, RecursionError):
        manifest = None
    if isinstance(manifest, dict) and manifest.get("archive_kind") == "manifest-only":
        _usage_error(
            "This is a --manifest-only archive: it holds metadata, not the run's inputs, and cannot be imported.\n"
            "Remediation: ask for a full archive (written without --manifest-only) to reproduce the run.",
        )
    digest = manifest.get("config_digest") if isinstance(manifest, dict) else None
    if not (
        isinstance(manifest, dict) and manifest.get("schema_version") == "1" and manifest.get("config_included") is True
        and isinstance(digest, str) and _DIGEST.match(digest)
    ):
        _usage_error(f"Unsupported {_MANIFEST}: expected schema_version \"1\" with the config included.\n{_REMEDIATION_ARCHIVE}")
    return manifest


def _extract_members(archive: zipfile.ZipFile, stage: Path) -> None:
    for member in archive.infolist():
        destination = stage.joinpath(*PurePosixPath(member.filename).parts)
        if member.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        # zipfile stops at the declared size and checks the CRC, so the total
        # written never exceeds what _validate_members accepted.
        with archive.open(member) as source, destination.open("xb") as output:
            shutil.copyfileobj(source, output, 1024 * 1024)


def _validate_replay(stage: Path, manifest: dict[str, Any]) -> None:
    """Require the inputs, one report, and a config that reloads to the manifest's and the report's digest."""
    reports = sorted((stage / "data" / "logs").glob("run_report_*.json"))
    if len(reports) != 1 or not (stage / _CONFIG).is_file() or not all((stage / "data" / name).is_dir() for name in _INPUT_DIRS):
        _usage_error(f"Archive lacks the input directories, {_CONFIG}, or exactly one run report.\n{_REMEDIATION_ARCHIVE}")
    try:
        report_digest = RunReport.from_json(reports[0].read_text(encoding="utf-8")).config_digest
    except (KeyError, TypeError, ValueError, RecursionError):
        _usage_error(f"The archived run report is not readable.\n{_REMEDIATION_ARCHIVE}")
    try:
        digest = compute_config_digest(load_config(stage, data_root=stage / "data"))
    except Exception:  # noqa: BLE001 -- an archived config that does not load must never be published
        _usage_error(f"The archived {_CONFIG} does not load.\n{_REMEDIATION_ARCHIVE}")
    if digest != manifest["config_digest"] or digest != report_digest:
        _usage_error(f"The archived config, manifest and report disagree on config_digest.\n{_REMEDIATION_ARCHIVE}")


def _publish(stage: Path, target: Path) -> None:
    """Rename the staged project to ``target`` in one step.

    POSIX ``rename`` replaces an empty directory and fails on a non-empty one,
    so a target filled meanwhile is never overwritten. Windows cannot rename
    onto a directory: there the empty target is removed first and restored on failure.
    """
    removed = _WINDOWS and target.is_dir()
    if removed:
        target.rmdir()
    try:
        stage.rename(target)
    except OSError:
        if removed:
            target.mkdir(exist_ok=True)
        raise
