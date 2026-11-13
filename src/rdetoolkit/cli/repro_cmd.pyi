from pathlib import Path

import typer

app: typer.Typer

def export_run(run_report: Path, output: Path, config: Path | None = None, manifest_only: bool = False) -> None: ...
def import_run(archive_path: Path, target: Path) -> None: ...
