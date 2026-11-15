import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from rdetoolkit.testing.runner import RdeTestResult

IGNORED_PLACEHOLDER: str
UPDATE_OPTION: str

class SnapshotError(AssertionError): ...

@dataclass(frozen=True)
class SnapshotUpdate:
    path: Path
    action: str

def ci_is_active(environ: Mapping[str, str] | None = None) -> bool: ...
def set_update_mode(enabled: bool) -> None: ...
def update_mode() -> bool: ...
def recorded_updates() -> tuple[SnapshotUpdate, ...]: ...
def update_summary_lines() -> list[str]: ...
def ci_refusal_message() -> str: ...
def reset() -> None: ...
def assert_snapshot(
    result: RdeTestResult,
    artifact: str | os.PathLike[str],
    golden: str | os.PathLike[str],
    *,
    ignore_fields: Iterable[str] = (),
    ignore_columns: Iterable[str] = (),
    ignore_files: Iterable[str] = (),
    max_bytes: int = ...,
    allow_raw: bool = False,
    update: bool | None = None,
) -> None: ...
