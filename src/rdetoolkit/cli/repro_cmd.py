"""Export and import reproducible run inputs.

The export argument is a run-report path so the command can locate both the
recorded calls and the run's sibling input directories.

A full export is a local reproduction: it holds the run's raw inputs, invoice,
report and effective config. ``--manifest-only`` writes structural metadata,
digests and the ``report diagnose`` envelope instead, and cannot be replayed.
Import treats an archive as untrusted: every member is checked before anything
is extracted, extraction goes to a staging directory next to the target, and
the target appears only after the config digests agree (#671).

Manifest ``schema_version`` ``"3"`` (#699) adds export-time provenance to both
archive kinds and, for a full archive, every member's size and SHA-256 so
import refuses a modified member before the target appears. ``"1"`` archives
remain importable and are reported as "provenance unavailable". ``repro
inspect`` reports what an archive does and does not record, without
extracting it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import unicodedata
import zipfile
import zlib
from collections.abc import Callable, Iterator
from functools import partial
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, cast

import typer
import yaml

from rdetoolkit.cli import _repro_pytest
from rdetoolkit.cli._help import EXIT_CLICK_USAGE, EXIT_OK, CommandHelp
from rdetoolkit.cli._repro_provenance import _file_digest, capture_provenance, read_provenance
from rdetoolkit.cli.run_cmd import load_config_overrides
from rdetoolkit.config.normalize import ConfigNormalizer
from rdetoolkit.domain.mode_selection import normalize_mode_name
from rdetoolkit.report.diagnostics import diagnostic, envelope
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.config_loader import compute_config_digest, config_for_replay, load_config
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
        "rdetoolkit repro inspect repro.zip",
        "rdetoolkit repro import repro.zip ./replay",
    ),
    exit_codes=(
        EXIT_OK,
        EXIT_CLICK_USAGE,
        (3, "unreadable report or archive, missing or unsafe inputs, a checksum mismatch, or an unreproducible config"),
    ),
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
        "`--manifest-only`: write metadata only (`archive_kind` `\"manifest-only\"`); `--config` is not needed.",
    ),
    outputs=(
        (
            "Writes the zip given by `-o/--output` (parent directories are created). An existing file is never replaced. "
            "A full zip holds `data/{inputdata,invoice,tasksupport}`, `data/logs/<report>`, `rdeconfig.yaml`, and "
            "`repro_manifest.json` (`schema_version` `\"3\"`) listing every member's size and SHA-256."
        ),
        (
            "Both kinds record export-time provenance: rdetoolkit, Python and platform versions, the git commit and "
            "whether tracked files changed (when the project is a git checkout), and a supported lockfile's digest. "
            "Source code is never archived."
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
        "which becomes the target only after every member matches the manifest's SHA-256 and the archived config "
        "reloads to the manifest's and the report's `config_digest`. Matching digests show consistency, not who made "
        "the archive: review imported data and config before running your flow on them. A `schema_version` `\"1\"` "
        "archive is still imported, with a notice that its provenance and per-file checksums are unavailable."
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
        (3, (
            "the target is not empty, the zip is unreadable, a member differs from the manifest, or a member, the "
            "manifest, or the config digest is not acceptable"
        )),
    ),
    see_also=("rdetoolkit repro inspect", "rdetoolkit repro export", "rdetoolkit run"),
)

INSPECT_HELP = CommandHelp(
    summary="Show what a `repro export` zip records for reproduction and what it does not, without extracting it.",
    details=(
        "Checks the archive members like `repro import`, then compares every full-archive member with the SHA-256 in "
        "`repro_manifest.json` (reading it, never writing it to disk), and lists the export-time provenance as known "
        "or unavailable. The provenance describes the environment that ran `repro export`, which may differ from the "
        "one that ran the flow. Matching digests are not proof that a rerun reproduces the original result."
    ),
    inputs=(
        "`ARCHIVE`: a zip written by `rdetoolkit repro export`, full or `--manifest-only`, of any manifest version.",
        "`--format`: `text` (default) or `json` (the versioned diagnostics envelope).",
    ),
    outputs=("Prints the report on stdout. Writes no file.",),
    examples=(
        "rdetoolkit repro inspect repro.zip",
        "rdetoolkit repro inspect repro.zip --format json",
    ),
    exit_codes=(
        EXIT_OK,
        EXIT_CLICK_USAGE,
        (3, "the zip is unreadable or unsafe, the manifest is unsupported, a member differs from it, or `--format` is unknown"),
    ),
    see_also=("rdetoolkit repro import", "rdetoolkit repro export"),
)

TO_PYTEST_HELP = CommandHelp(
    summary="Write an editable pytest regression test (an `rde_case`) for the run in a full `repro export` zip.",
    details=(
        "The flow is never inferred from the archive: `--ref` names it, and it is imported (which runs the module's "
        "top-level code) but never called. The archive is checked like `repro inspect`, and a member that differs "
        "from the manifest is refused. The test expects `success`, the behaviour after the fix, unless "
        "`--expect-status` says otherwise; the archived failure is never taken as the expected result. Review the "
        "generated file before committing it."
    ),
    inputs=(
        "`ARCHIVE`: a full zip written by `rdetoolkit repro export` (a `--manifest-only` zip is refused).",
        "`--ref`: the flow `pkg.mod:callable` the test runs, importable from the working directory.",
        (
            "`--project DIR`: an existing project for the case, such as one made by `repro import`. Its inputs and "
            "effective config must match the archive's digests (needs a `schema_version` `\"3\"` archive)."
        ),
        (
            "`--stage-inputs DIR`: extract the archive into the new or empty `DIR` (as `repro import` does) and use it "
            "as the project. This copies the raw research inputs there: only use it when they may be stored with the tests."
        ),
        "`--expect-status`: `success`, `partial` or `failed`, when you have confirmed the expected outcome.",
    ),
    outputs=(
        (
            "Writes `-o/--output` (a `.py` file) with a test function that requests `rde_run`, the project path relative "
            "to that file, and the archive's provenance as comments. An existing file is replaced only with `--force`."
        ),
        "Prints the file path on stdout and the review steps (and any environment difference) on stderr.",
    ),
    examples=(
        "rdetoolkit repro to-pytest repro.zip --ref modules.processing:main \\",
        "    -o tests/test_regression.py --project ./replay",
        "rdetoolkit repro to-pytest repro.zip --ref pkg.flows:main \\",
        "    -o tests/test_case.py --stage-inputs tests/cases/case1",
    ),
    exit_codes=(
        EXIT_OK,
        (2, "invalid command line, including neither or both of --project and --stage-inputs"),
        (3, (
            "an unreadable, unsafe, metadata-only or modified archive, an invalid or unimportable --ref, a project "
            "that differs from the archive, a non-empty --stage-inputs directory, or an output that exists or is not a file"
        )),
    ),
    see_also=("rdetoolkit repro inspect", "rdetoolkit repro import", "rdetoolkit doctor"),
)

app =typer.Typer(help=REPRO_HELP.render(), short_help=REPRO_HELP.summary, no_args_is_help=True)
_INPUT_DIRS = ("inputdata", "invoice", "tasksupport")
_MANIFEST = "repro_manifest.json"
_CONFIG = "rdeconfig.yaml"

# Archive limits, checked on import and (so an export always imports) before an export is kept.
_MAX_MEMBERS = 100_000
_MAX_TOTAL_BYTES = 16 * 1024**3
#: Deflate cannot expand data more than about 1032:1, so a larger whole-archive
#: ratio means overlapping or forged entries (a zip bomb).
_MAX_COMPRESSION_RATIO = 1100
#: Large enough for a full manifest listing _MAX_MEMBERS typical paths.
_MAX_MANIFEST_BYTES = 64 * 1024**2
_MAX_PATH_LENGTH = 1024
_MAX_PATH_DEPTH = 64
#: Names that only Windows reads as drives, streams or devices; refused only there,
#: where they would escape the staging directory or open a device.
_WINDOWS = os.name == "nt"
_WINDOWS_DEVICES = frozenset({"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))})
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_REMEDIATION_ARCHIVE = "Remediation: import only a full archive written by 'rdetoolkit repro export', unmodified."
_REMEDIATION_EXPORT = "Remediation: rename or reduce the inputs so that 'rdetoolkit repro import' can accept them, then export again."
_SCHEMA_VERSION = "3"
_LEGACY_SCHEMA_VERSION = "1"
_MANIFEST_FORMAT = "rdetoolkit.repro-manifest"
_CHUNK = 1024 * 1024
_REPLAY_NOTE = (
    "Note: matching digests show that the archive is intact and consistent; they are not proof that a rerun "
    "reproduces the original result (interpreter, dependencies and source code may differ)."
)


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
    is skipped. The caller reports one usage
    error if no candidate reproduces the digest.
    """
    for root in _project_roots(data_root):
        builders: list[Callable[[], RdeConfig]] = [partial(load_config, root, overrides, data_root=data_root)]
        if overrides is None:
            builders.append(partial(_v1_entry_config, root, data_root))
        for build in builders:
            try:
                config = build()
                yield config
                mode = normalize_mode_name(config.system.extended_mode).value
                if config.system.extended_mode != mode:
                    canonical = config.model_copy(deep=True)
                    canonical.system.extended_mode = mode
                    yield canonical
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

    Defaults are omitted except policy-significant flags. If the compact form
    fails to reload to the same digest, the full replay-safe dump is used
    instead; the digest is the contract, not the form.

    Keys are sorted: ``config_digest`` is computed over key-sorted JSON, so key
    order never affects whether the archived form replays.
    """
    dumps: tuple[Callable[[], dict[str, Any]], ...] = (
        lambda: config_for_replay(config, compact=True),
        lambda: config_for_replay(config),
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
        manifest_bytes = _manifest_bytes(manifest)
        _export_archive(output, lambda archive: archive.writestr(_MANIFEST, manifest_bytes))
    else:
        report = _validate_report(report_path)
        entries = _source_entries(data_root)
        # Resolved before the archive is opened, so a refusal leaves no file behind.
        config_text = _config_yaml(_effective_config(report, data_root, config), report.config_digest)
        _preview_export(entries, report_path, config_text)
        manifest = {
            "schema_version": _SCHEMA_VERSION,
            "format": _MANIFEST_FORMAT,
            "archive_kind": "full",
            "replayable": True,
            "config_included": True,
            "config_digest": report.config_digest,
            "provenance": capture_provenance(_project_root(data_root)),
        }
        _export_archive(output, partial(_write_full_archive, entries=entries, report_path=report_path, config_text=config_text, manifest=manifest))
    typer.echo(str(output))


def _project_root(data_root: Path) -> Path:
    """The directory that holds the project's lockfile and is queried for git."""
    roots = _project_roots(data_root)
    return roots[0] if roots else data_root.parent


def _manifest_bytes(manifest: dict[str, Any]) -> bytes:
    """Serialize a manifest, refusing one that import would refuse for its size."""
    content = json.dumps(manifest, indent=2).encode("utf-8")
    if len(content) > _MAX_MANIFEST_BYTES:
        _usage_error(f"{_MANIFEST} would exceed {_MAX_MANIFEST_BYTES} bytes.\n{_REMEDIATION_EXPORT}")
    return content


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
        "schema_version": _SCHEMA_VERSION,
        "format": _MANIFEST_FORMAT,
        "archive_kind": "manifest-only",
        "replayable": False,
        "config_included": False,
        "config_digest": config_digest if isinstance(config_digest, str) and _DIGEST.match(config_digest) else None,
        "directories": directories,
        "files": files,
        "provenance": capture_provenance(_project_root(report_path.parent.parent)),
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
    """Write the members, then the manifest listing the digest of each member's archived bytes."""
    files: list[dict[str, Any]] = []
    for path, name in entries:
        if path.is_dir():
            _write_directory(archive, name)
        else:
            files.append(_write_file(archive, path, name))
    files.append(_write_file(archive, report_path, _report_archive_name(report_path)))
    config_bytes = config_text.encode("utf-8")
    archive.writestr(_CONFIG, config_bytes)
    files.append({"path": _CONFIG, "byte_count": len(config_bytes), "sha256": "sha256:" + hashlib.sha256(config_bytes).hexdigest()})
    archive.writestr(_MANIFEST, _manifest_bytes({**manifest, "files": sorted(files, key=lambda item: item["path"])}))
    # Refuse now rather than hand over an archive that import would refuse.
    _validate_members(archive.infolist(), remediation=_REMEDIATION_EXPORT)


def _write_file(archive: zipfile.ZipFile, path: Path, name: str) -> dict[str, Any]:
    """Stream one file into the archive, hashing the bytes as they are written.

    Hashing the stream (not the file beforehand) makes the manifest describe
    exactly what the archive holds even if the file changes meanwhile.
    """
    info = zipfile.ZipInfo.from_file(path, name)
    info.compress_type = archive.compression
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source, archive.open(info, "w") as target:
        for chunk in iter(partial(source.read, _CHUNK), b""):
            digest.update(chunk)
            target.write(chunk)
            size += len(chunk)
    return {"path": name, "byte_count": size, "sha256": "sha256:" + digest.hexdigest()}


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
    _report_verification(_import_archive(archive_path, target))
    typer.echo(str(target))


def _import_archive(archive_path: Path, target: Path) -> dict[str, tuple[int, str]] | None:
    """Publish a full archive at ``target`` after every check; return the verified listing (None for "1")."""
    _validate_target(target)
    try:
        archive_size = archive_path.stat().st_size
        with zipfile.ZipFile(archive_path) as archive:
            _validate_members(archive.infolist(), archive_size=archive_size)
            manifest = _read_manifest(archive)
            files = _manifest_files(manifest)
            if files is not None:
                problems = _listing_problems(archive.infolist(), files)
                if problems:
                    _usage_error(f"Archive members do not match {_MANIFEST}: {problems[0][1]}\n{_REMEDIATION_ARCHIVE}")
            target.parent.mkdir(parents=True, exist_ok=True)
            # Same parent, so publishing is one rename; removed on every exit path.
            with tempfile.TemporaryDirectory(prefix=".rdetoolkit-import-", dir=target.parent) as scratch:
                stage = Path(scratch) / "project"
                stage.mkdir()
                _extract_members(archive, stage, files)
                _validate_replay(stage, manifest)
                _publish(stage, target)
    # Not RuntimeError: typer.Exit is one, and the refusals above must keep their own message.
    except (OSError, EOFError, ValueError, zlib.error, zipfile.BadZipFile, NotImplementedError) as exc:
        _usage_error(f"Unable to import archive {archive_path}: {exc}\n{_REMEDIATION_ARCHIVE}")
    return files


def _report_verification(files: dict[str, tuple[int, str]] | None) -> None:
    if files is None:
        typer.echo(
            f"Provenance unavailable: this archive's {_MANIFEST} (schema_version \"{_LEGACY_SCHEMA_VERSION}\") predates "
            "provenance and per-file checksums; its members were checked only against the zip CRCs.",
            err=True,
        )
    else:
        typer.echo(f"Verified {len(files)} archived files against the SHA-256 digests in {_MANIFEST}.", err=True)


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


def _load_manifest(archive: zipfile.ZipFile) -> object:
    """Return the parsed manifest JSON (None if it does not parse), refusing a missing or oversized one."""
    try:
        member = archive.getinfo(_MANIFEST)
    except KeyError:
        _usage_error(f"Archive has no {_MANIFEST}.\n{_REMEDIATION_ARCHIVE}")
    if member.file_size > _MAX_MANIFEST_BYTES:
        _usage_error(f"{_MANIFEST} exceeds {_MAX_MANIFEST_BYTES} bytes.\n{_REMEDIATION_ARCHIVE}")
    try:
        return json.loads(archive.read(member))
    except (ValueError, RecursionError):
        return None


def _has_config(manifest: dict[str, Any]) -> bool:
    digest = manifest.get("config_digest")
    return manifest.get("config_included") is True and isinstance(digest, str) and _DIGEST.match(digest) is not None


def _is_full_legacy(manifest: object) -> bool:
    """A schema_version "1" full manifest, written before #699."""
    return isinstance(manifest, dict) and manifest.get("schema_version") == _LEGACY_SCHEMA_VERSION and _has_config(manifest)


def _is_full_current(manifest: object) -> bool:
    """A schema_version "3" full manifest with a well-formed file list."""
    return (
        isinstance(manifest, dict)
        and manifest.get("schema_version") == _SCHEMA_VERSION
        and manifest.get("format") == _MANIFEST_FORMAT
        and manifest.get("archive_kind") == "full"
        and manifest.get("replayable") is True
        and _has_config(manifest)
        and _parse_files(manifest.get("files")) is not None
    )


def _read_manifest(archive: zipfile.ZipFile) -> dict[str, Any]:
    """Return a full archive's manifest, refusing a metadata-only or unsupported one."""
    manifest = _load_manifest(archive)
    if isinstance(manifest, dict) and manifest.get("archive_kind") == "manifest-only":
        _usage_error(
            "This is a --manifest-only archive: it holds metadata, not the run's inputs, and cannot be imported.\n"
            "Remediation: ask for a full archive (written without --manifest-only) to reproduce the run.",
        )
    if not isinstance(manifest, dict) or not (_is_full_legacy(manifest) or _is_full_current(manifest)):
        _usage_error(
            f"Unsupported {_MANIFEST}: expected a full archive's schema_version \"{_SCHEMA_VERSION}\" (or "
            f"\"{_LEGACY_SCHEMA_VERSION}\") with the config included and, for \"{_SCHEMA_VERSION}\", a well-formed "
            f"file list.\n{_REMEDIATION_ARCHIVE}",
        )
    return manifest


def _manifest_files(manifest: dict[str, Any]) -> dict[str, tuple[int, str]] | None:
    """The listed ``path -> (size, digest)`` of an accepted manifest; None for a legacy one."""
    return _parse_files(manifest.get("files")) if manifest.get("schema_version") == _SCHEMA_VERSION else None


def _file_entry(item: object) -> tuple[str, int, str] | None:
    """Validate one ``files`` entry; the path must be a name the export layout allows."""
    if not isinstance(item, dict):
        return None
    path, size, digest = item.get("path"), item.get("byte_count"), item.get("sha256")
    if not (isinstance(path, str) and isinstance(size, int) and not isinstance(size, bool) and size >= 0):
        return None
    if not (isinstance(digest, str) and _DIGEST.match(digest)) or path == _MANIFEST:
        return None
    if _unsafe_name(zipfile.ZipInfo(path)) or not _allowed_member(PurePosixPath(path).parts, is_dir=False):
        return None
    return path, size, digest


def _parse_files(value: object) -> dict[str, tuple[int, str]] | None:
    """Parse a v3 ``files`` list, or None if any entry is malformed or repeated."""
    if not isinstance(value, list):
        return None
    files: dict[str, tuple[int, str]] = {}
    for item in value:
        entry = _file_entry(item)
        if entry is None or entry[0] in files:
            return None
        files[entry[0]] = (entry[1], entry[2])
    return files


def _listing_problems(members: list[zipfile.ZipInfo], files: dict[str, tuple[int, str]]) -> list[tuple[str, str]]:
    """Compare the archive's file members with the manifest listing, by name and declared size.

    Returns:
        Sorted ``(member, description)`` pairs; empty when they agree.
    """
    actual = {member.filename: member.file_size for member in members if not member.is_dir() and member.filename != _MANIFEST}
    problems: list[tuple[str, str]] = []
    for name in sorted(actual.keys() | files.keys()):
        if name not in files:
            problems.append((name, f"{name!r} is not listed in the manifest"))
        elif name not in actual:
            problems.append((name, f"{name!r} is listed in the manifest but missing from the archive"))
        elif actual[name] != files[name][0]:
            problems.append((name, f"{name!r} holds {actual[name]} bytes, the manifest lists {files[name][0]}"))
    return problems


def _stream(source: Any, sink: Any = None) -> str:
    """Read ``source`` to the end, copying to ``sink`` if given; return its ``sha256:`` digest."""
    digest = hashlib.sha256()
    for chunk in iter(partial(source.read, _CHUNK), b""):
        digest.update(chunk)
        if sink is not None:
            sink.write(chunk)
    return "sha256:" + digest.hexdigest()


def _extract_members(archive: zipfile.ZipFile, stage: Path, files: dict[str, tuple[int, str]] | None) -> None:
    """Extract every member into ``stage``, refusing one whose bytes differ from the manifest digest."""
    for member in archive.infolist():
        destination = stage.joinpath(*PurePosixPath(member.filename).parts)
        if member.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        # zipfile stops at the declared size and checks the CRC, so the total
        # written never exceeds what _validate_members accepted.
        with archive.open(member) as source, destination.open("xb") as output:
            digest = _stream(source, output)
        if files is not None and member.filename in files and files[member.filename][1] != digest:
            _usage_error(
                f"Archive member checksum mismatch: {member.filename!r} differs from its SHA-256 in {_MANIFEST}.\n"
                f"{_REMEDIATION_ARCHIVE}",
            )


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


@app.command("inspect", help=INSPECT_HELP.render(), short_help=INSPECT_HELP.summary)
def inspect_archive(
    archive_path: Annotated[Path, typer.Argument(metavar="ARCHIVE", help="Zip written by 'rdetoolkit repro export'.")],
    output_format: Annotated[str, typer.Option("--format", help="Output format: text or json.")] = "text",
) -> None:
    """Report an archive's integrity and recorded provenance without extracting it."""
    if output_format not in {"text", "json"}:
        _usage_error(f"Unsupported --format {output_format!r}.\nRemediation: pass --format text or --format json.")
    try:
        archive_size = archive_path.stat().st_size
        with zipfile.ZipFile(archive_path) as archive:
            _validate_members(archive.infolist(), archive_size=archive_size)
            manifest = _inspectable_manifest(_load_manifest(archive))
            inputs = _inspect_inputs(archive, manifest)
    except (OSError, EOFError, ValueError, zlib.error, zipfile.BadZipFile, NotImplementedError) as exc:
        _usage_error(f"Unable to inspect archive {archive_path}: {exc}\nRemediation: pass a zip written by 'rdetoolkit repro export'.")
    payload = _inspect_payload(manifest, inputs)
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False) if output_format == "json" else _inspect_text(payload))
    if inputs["status"] == "mismatch":
        raise typer.Exit(code=3)


def _is_metadata_only(manifest: dict[str, Any]) -> bool:
    return (
        manifest.get("archive_kind") == "manifest-only"
        and manifest.get("schema_version") in ("2", _SCHEMA_VERSION)  # a tuple: the value may be unhashable
        and manifest.get("format") == _MANIFEST_FORMAT
        and manifest.get("replayable") is False
    )


def _inspectable_manifest(manifest: object) -> dict[str, Any]:
    """Accept a full (v1 or v3) or metadata-only (v2 or v3) manifest, else exit 3."""
    if isinstance(manifest, dict):
        if manifest.get("archive_kind") == "manifest-only":
            if _is_metadata_only(manifest):
                return manifest
        elif _is_full_current(manifest) or _is_full_legacy(manifest):
            return manifest
    _usage_error(f"Unsupported {_MANIFEST}: not a manifest that 'rdetoolkit repro export' writes.\n{_REMEDIATION_ARCHIVE}")


def _inspect_inputs(archive: zipfile.ZipFile, manifest: dict[str, Any]) -> dict[str, Any]:
    """Compare every file member with the manifest digest; nothing is written to disk."""
    if manifest.get("archive_kind") == "manifest-only":
        listed = manifest.get("files")
        return {"status": "not_included", "file_count": len(listed) if isinstance(listed, list) else 0, "verified_count": 0, "mismatched": []}
    members = [member for member in archive.infolist() if not member.is_dir() and member.filename != _MANIFEST]
    files = _manifest_files(manifest)
    if files is None:
        return {"status": "unverifiable", "file_count": len(members), "verified_count": 0, "mismatched": []}
    mismatched = {name for name, _ in _listing_problems(archive.infolist(), files)}
    for member in members:
        if member.filename not in mismatched:
            with archive.open(member) as source:
                if _stream(source) != files[member.filename][1]:
                    mismatched.add(member.filename)
    return {
        "status": "mismatch" if mismatched else "verified",
        "file_count": len(files),
        "verified_count": sum(1 for name in files if name not in mismatched),
        "mismatched": sorted(mismatched),
    }


def _inspect_findings(inputs: dict[str, Any], unavailable: dict[str, str]) -> list[dict[str, Any]]:
    """Symbolic findings (``code`` None) for what the archive cannot vouch for."""
    remediation = "Export the run again with this rdetoolkit version and compare before relying on the archive."
    findings = [
        diagnostic(
            code=None, severity="error", name="ReproChecksumMismatch", subject=name, remediation=remediation,
            message=f"The member is missing, unlisted, or its size or SHA-256 differs from {_MANIFEST}.",
        )
        for name in inputs["mismatched"]
    ]
    if inputs["status"] == "unverifiable":
        findings.append(diagnostic(
            code=None, severity="warning", name="ReproInputsUnverifiable", subject="inputs", remediation=remediation,
            message="The manifest predates per-file checksums; members can only be checked against zip CRCs.",
        ))
    if inputs["status"] == "not_included":
        findings.append(diagnostic(
            code=None, severity="info", name="ReproInputsNotIncluded", subject="inputs",
            message="A metadata-only archive describes the inputs by digest and does not contain them.",
            remediation="Ask for a full archive to reproduce the run.",
        ))
    for name in unavailable:
        if name == "source_code":
            findings.append(diagnostic(
                code=None, severity="info", name="ReproSourceNotIncluded", subject=name,
                message="Repro archives never contain the flow's source code.",
                remediation="Check out the flow's source separately, at the recorded git commit when one is known.",
            ))
        else:
            findings.append(diagnostic(
                code=None, severity="warning", name="ReproProvenanceUnavailable", subject=name,
                message="The archive does not record this reproducibility attribute in a readable form.",
                remediation="Record it by hand when you reproduce the run, or export again with a current rdetoolkit.",
            ))
    return findings


def _inspect_payload(manifest: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    captured_at, known, unavailable = read_provenance(manifest)
    digest = manifest.get("config_digest")
    archive = {
        "schema_version": manifest["schema_version"],
        "archive_kind": "manifest-only" if manifest.get("archive_kind") == "manifest-only" else "full",
        "replayable": manifest.get("archive_kind") != "manifest-only",
        "config_digest": digest if isinstance(digest, str) and _DIGEST.match(digest) else None,
    }
    return envelope(
        _inspect_findings(inputs, unavailable),
        command="repro inspect",
        archive=archive,
        inputs=inputs,
        provenance={"captured_at": captured_at, "known": known, "unavailable": unavailable},
    )


def _inputs_lines(inputs: dict[str, Any], schema_version: str) -> list[str]:
    count = inputs["file_count"]
    if inputs["status"] == "unverifiable":
        return [f"Verified inputs: none; manifest schema_version {schema_version} has no per-file checksums ({count} files)"]
    if inputs["status"] == "not_included":
        return [f"Verified inputs: not included (a metadata-only archive describing {count} files by digest)"]
    lines = [f"Verified inputs: {inputs['verified_count']} of {count} files match the manifest's SHA-256 digests"]
    lines.extend(f"  checksum mismatch: {name}" for name in inputs["mismatched"])
    return lines


def _describe(name: str, fields: dict[str, Any]) -> str:
    if name == "git":
        return f"{fields['commit']} ({'tracked files changed' if fields['dirty'] else 'clean'})"
    return " ".join(str(value) for value in fields.values())


def _provenance_lines(provenance: dict[str, Any]) -> list[str]:
    known: dict[str, dict[str, Any]] = provenance["known"]
    unavailable: dict[str, str] = provenance["unavailable"]
    if known:
        captured = "captured at export" if provenance["captured_at"] else "capture point not recorded"
        lines = [f"Known provenance ({captured}):", *(f"  {name}: {_describe(name, fields)}" for name, fields in known.items())]
    else:
        lines = ["Known provenance: none (provenance unavailable)"]
    return [*lines, "Unknown or unavailable:", *(f"  {name}: {reason}" for name, reason in unavailable.items())]


def _inspect_text(payload: dict[str, Any]) -> str:
    archive = payload["archive"]
    lines = [
        f"Archive: {archive['archive_kind']}, manifest schema_version {archive['schema_version']}, "
        + ("replayable" if archive["replayable"] else "not replayable"),
        f"Config digest: {archive['config_digest'] or 'not recorded'}",
        *_inputs_lines(payload["inputs"], archive["schema_version"]),
        *_provenance_lines(payload["provenance"]),
        _REPLAY_NOTE,
    ]
    return "\n".join(lines)


@app.command("to-pytest", help=TO_PYTEST_HELP.render(), short_help=TO_PYTEST_HELP.summary)
def to_pytest(  # noqa: PLR0913 -- one parameter per CLI option
    archive_path: Annotated[Path, typer.Argument(metavar="ARCHIVE", help="Full zip written by 'rdetoolkit repro export'.")],
    ref: Annotated[str, typer.Option("--ref", metavar="REF", help="The flow pkg.mod:callable the test runs (imported, never called).")],
    output: Annotated[Path, typer.Option("-o", "--output", help="The test file to write (.py).")],
    project: Annotated[Path | None, typer.Option("--project", help="Existing project whose inputs match the archive.")] = None,
    stage_inputs: Annotated[
        Path | None, typer.Option("--stage-inputs", help="Extract the archived raw inputs into this new or empty directory and use it."),
    ] = None,
    expect_status: Annotated[
        str | None, typer.Option("--expect-status", help="Expected run status (success, partial, failed); default success."),
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Replace an existing output file.")] = False,
) -> None:
    """Generate a pytest regression scaffold for the archived run."""
    if (project is None) == (stage_inputs is None):
        _command_line_error("Pass exactly one of --project or --stage-inputs: the case needs a project to run.")
    if expect_status is not None and expect_status not in _repro_pytest.STATUSES:
        _command_line_error(f"--expect-status must be one of {', '.join(_repro_pytest.STATUSES)}.")
    _check_output(output, force=force)
    try:
        module, attributes = _repro_pytest.parse_ref(ref)
    except ValueError as exc:
        _usage_error(f"{exc}\nRemediation: pass the flow as --ref pkg.mod:callable, as for 'rdetoolkit run'.")
    manifest, files, run = _read_case_archive(archive_path)
    _import_flow(ref)
    # Read from the manifest before any input is staged or checked.
    notes, differences = _repro_pytest.provenance_notes(manifest, None if files is None else len(files))
    case_project = _case_project(archive_path, manifest, files, project=project, stage_inputs=stage_inputs)
    expression, absolute = _repro_pytest.project_expression(case_project, output)
    if absolute:
        typer.echo(f"Warning: {case_project} has no path relative to {output.parent}; the test names it absolutely.", err=True)
    for difference in differences:
        typer.echo(f"Warning: {difference}; a rerun may behave differently.", err=True)
    source = _repro_pytest.render_test(module=module, attributes=attributes, project=expression, run=run, expect_status=expect_status, notes=notes)
    _write_test(output, source, force=force)
    typer.echo(
        "Review expect_status and replace the assertion template with independent expectations before committing; "
        f"then run: pytest {output}",
        err=True,
    )
    typer.echo(str(output))


def _case_project(
    archive_path: Path, manifest: dict[str, Any], files: dict[str, tuple[int, str]] | None, *, project: Path | None, stage_inputs: Path | None,
) -> Path:
    """Verify ``--project`` against the archive, or stage the archive at ``--stage-inputs`` (the explicit opt-in)."""
    if project is not None:
        _verify_project(project, manifest, files)
        return project
    target = cast("Path", stage_inputs)  # exactly one of the two is set (checked by the caller)
    _report_verification(_import_archive(archive_path, target))
    typer.echo(
        f"Warning: {target} now holds the archived raw input files, invoice and config. Review them before "
        "committing; keep the directory out of version control if the data must stay local.",
        err=True,
    )
    return target


def _command_line_error(message: str) -> Never:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=EXIT_CLICK_USAGE[0])


def _check_output(output: Path, *, force: bool) -> None:
    if output.suffix != ".py":
        _usage_error(f"Output must be a .py file: {output}\nRemediation: pass -o tests/test_<name>.py.")
    if output.is_symlink() or (output.exists() and not output.is_file()):
        _usage_error(f"Output is a symbolic link or not a regular file: {output}\nRemediation: pass a new file path.")
    if output.exists() and not force:
        _usage_error(f"Output already exists: {output}\nRemediation: pass a new -o path, or --force to replace it.")
    # Checked before anything is staged, so a doomed write leaves no extracted inputs behind.
    existing = next(parent for parent in output.absolute().parents if parent.exists())
    if not existing.is_dir():
        _usage_error(f"Unable to write {output}: {existing} is not a directory.\nRemediation: pass an -o path in a writable directory.")


def _read_case_archive(archive_path: Path) -> tuple[dict[str, Any], dict[str, tuple[int, str]] | None, _repro_pytest.ArchivedRun]:
    """Return a verified full archive's manifest, file listing and archived-run facts, or exit 3."""
    try:
        archive_size = archive_path.stat().st_size
        with zipfile.ZipFile(archive_path) as archive:
            _validate_members(archive.infolist(), archive_size=archive_size)
            manifest = _read_manifest(archive)
            inputs = _inspect_inputs(archive, manifest)
            # Members are validated: a file under data/logs/ is a run_report_*.json.
            reports = [member for member in archive.infolist() if member.filename.startswith("data/logs/") and not member.is_dir()]
            report_text = archive.read(reports[0]).decode("utf-8") if len(reports) == 1 else None
    except (OSError, EOFError, ValueError, zlib.error, zipfile.BadZipFile, NotImplementedError) as exc:
        _usage_error(f"Unable to read archive {archive_path}: {exc}\n{_REMEDIATION_ARCHIVE}")
    if inputs["status"] == "mismatch":
        _usage_error(
            f"Archive members differ from {_MANIFEST}: {', '.join(inputs['mismatched'])}\n"
            f"Remediation: run 'rdetoolkit repro inspect {archive_path}' and export the run again.",
        )
    try:
        run = _repro_pytest.archived_run(report_text) if report_text is not None else None
    except (KeyError, TypeError, ValueError, RecursionError):
        run = None
    if run is None:
        _usage_error(f"The archive does not hold exactly one readable run report.\n{_REMEDIATION_ARCHIVE}")
    return manifest, _manifest_files(manifest), run


def _import_flow(ref: str) -> None:
    """Import ``ref`` as 'rdetoolkit run' would, without calling it or writing bytecode."""
    from rdetoolkit.cli.run_cmd import resolve_flow  # noqa: PLC0415

    previous_path, previous_bytecode = list(sys.path), sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        resolve_flow(ref)
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001 -- the module's top-level code may raise anything
        _usage_error(f"Unable to resolve flow {ref}: {type(exc).__name__}: {exc}\nRemediation: check that the module imports from the working directory.")
    finally:
        sys.path[:] = previous_path
        sys.dont_write_bytecode = previous_bytecode


def _verify_project(project: Path, manifest: dict[str, Any], files: dict[str, tuple[int, str]] | None) -> None:
    if not project.is_dir():
        _usage_error(f"--project is not a directory: {project}\nRemediation: pass the directory 'rdetoolkit repro import' created.")
    if files is None:
        _usage_error(
            f"This archive's {_MANIFEST} (schema_version \"{_LEGACY_SCHEMA_VERSION}\") has no per-file checksums, so "
            f"{project} cannot be checked against it.\nRemediation: pass --stage-inputs DIR to use the archived inputs.",
        )
    problems = _repro_pytest.project_problems(project, files, manifest["config_digest"])
    if problems:
        _usage_error(
            f"--project {project} does not hold the archived inputs and config:\n{_repro_pytest.summarize(problems)}\n"
            "Remediation: pass the directory 'rdetoolkit repro import' created from this archive, or --stage-inputs DIR.",
        )


def _write_test(output: Path, source: str, *, force: bool) -> None:
    """Write ``source`` to ``output``: exclusively, or (``force``) by replacing it in one rename."""
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        if not force:
            with output.open("x", encoding="utf-8") as stream:
                stream.write(source)
            return
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, prefix=".rdetoolkit-", suffix=".tmp", delete=False) as temporary:
            temporary.write(source)
        try:
            os.replace(temporary.name, output)
        finally:
            Path(temporary.name).unlink(missing_ok=True)
    except FileExistsError:
        _usage_error(f"Output already exists: {output}\nRemediation: pass a new -o path, or --force to replace it.")
    except OSError as exc:
        _usage_error(f"Unable to write {output}: {exc}\nRemediation: pass an -o path in a writable directory.")
