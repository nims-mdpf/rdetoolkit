from pathlib import Path

import typer

app: typer.Typer

def export_run(run_report: Path, output: Path, config: Path | None = None) -> None: ...
def import_run(archive_path: Path, target: Path) -> None: ...
