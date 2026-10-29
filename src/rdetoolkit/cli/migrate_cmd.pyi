from pathlib import Path
from dataclasses import dataclass

import typer

app: typer.Typer

@dataclass(frozen=True, slots=True)
class Finding:
    line: int
    category: str

def check(path: Path = ...) -> None: ...
def apply(path: Path = ..., out: Path | None = ..., dry_run: bool = ...) -> None: ...
