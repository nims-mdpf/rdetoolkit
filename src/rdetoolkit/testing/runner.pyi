import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from rdetoolkit.report.run_report import RunReport
from rdetoolkit.templates.base import ProcessingTemplate
from rdetoolkit.types import RdeConfig

@dataclass(frozen=True)
class RdeIterationSummary:
    index: int
    datatile_id: str
    status: str
    error_code: int | None = None
    error_name: str | None = None
    error_message: str | None = None

@dataclass(frozen=True)
class RdeTestResult:
    report: RunReport
    project_root: Path
    data_root: Path
    report_path: Path | None
    events_path: Path | None
    diagnostics_path: Path | None
    job_failed_path: Path | None
    @property
    def status(self) -> str: ...
    @property
    def iterations(self) -> tuple[RdeIterationSummary, ...]: ...
    def artifact_path(self, name: str | os.PathLike[str]) -> Path: ...
    def assert_success(self) -> None: ...
    def failure_summary(self, *, expected_status: str) -> str: ...

class RdeTestRunner:
    base_dir: Path
    def __init__(self, base_dir: Path) -> None: ...
    def run(
        self,
        *,
        flow: Callable[..., Any] | type[ProcessingTemplate],
        project: str | os.PathLike[str],
        config: RdeConfig | Mapping[str, Any] | None = None,
    ) -> RdeTestResult: ...

def relative_artifact(name: str | os.PathLike[str]) -> PurePosixPath: ...
def _collect_result(report: RunReport, *, project_root: Path, data_root: Path) -> RdeTestResult: ...
