from pathlib import Path

import typer

app: typer.Typer

def graph(run_report: Path, format_: str = ...) -> None: ...
