"""Export and import reproducible run inputs.

The export argument is a run-report path so the command can locate both the
recorded calls and the run's sibling input directories.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Annotated

import typer

from rdetoolkit.report.run_report import RunReport

if sys.version_info >= (3, 11):
    from typing import Never
else:
    from typing_extensions import Never


app = typer.Typer(help="Export and import reproducible run inputs.")
_INPUT_DIRS = ("inputdata", "invoice", "tasksupport")


def _usage_error(message: str) -> Never:
    typer.echo(message, err=True)
    raise typer.Exit(code=3)


def _validate_report(path: Path) -> None:
    try:
        RunReport.from_json(path.read_text(encoding="utf-8"))
    except (OSError, KeyError, TypeError, ValueError) as exc:
        _usage_error(f"Unable to read run report {path}: {exc}")


@app.command("export")
def export_run(
    run_report: Annotated[Path, typer.Argument(metavar="<run_report.json>")],
    output: Annotated[Path, typer.Option("--output", help="Destination zip archive.")],
) -> None:
    """Archive a report, its inputs, and the discoverable run config."""
    report_path = run_report.resolve()
    _validate_report(report_path)
    data_root = report_path.parent.parent
    for dirname in _INPUT_DIRS:
        source = data_root / dirname
        if not source.is_dir():
            _usage_error(f"Missing source directory: {source}")

    config_path = data_root.parent / "rdeconfig.yaml"
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for dirname in _INPUT_DIRS:
                _write_tree(archive, data_root / dirname, Path("data") / dirname)
            archive.write(report_path, Path("data") / "logs" / report_path.name)
            if config_path.is_file():
                archive.write(config_path, "rdeconfig.yaml")
            manifest = {"schema_version": "1", "config_included": config_path.is_file()}
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
