from collections.abc import Callable
from pathlib import Path
from typing import Any

from rdetoolkit.report.failure import FailureDiagnostic
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.types import RdeConfig

PASSTHROUGH_ERROR_NAME: str

def structured_error_record(exc: BaseException | None) -> dict[str, Any] | None: ...
def processing_error_record(exc: BaseException | None) -> dict[str, Any] | None: ...

class RunFinalizer:
    def __init__(self, *, data_root: Path | Callable[[], Path]) -> None: ...
    def finalize(self, report: RunReport, config: RdeConfig) -> None: ...

def finalize(report: RunReport, config: RdeConfig, *, data_root: Path) -> None: ...
def write_run_report(report: RunReport, *, data_root: Path) -> None: ...
def write_failure_diagnostics(
    diagnostics: list[FailureDiagnostic],
    *,
    run_id: str,
    run_status: str,
    data_root: Path,
    truncated: bool = False,
) -> Path: ...
def atomic_write_text(path: Path, text: str) -> None: ...
