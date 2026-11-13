from pathlib import Path

import typer

app: typer.Typer

def show(run_report: Path) -> None: ...
def trace(run_report: Path, format_: str = ...) -> None: ...
