from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

@dataclass(frozen=True, slots=True)
class CompletedProgram:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    duration: float

def to_wine_path(path: str | Path) -> str: ...
def run_program(args: Sequence[str | Path], *, cwd: Path | None = None, timeout: float | None = None, env: Mapping[str, str] | None = None, wine: bool | Literal['auto'] = False, error_code: int | None = None, error_message: str | None = None) -> CompletedProgram: ...
