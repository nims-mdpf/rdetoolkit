from pathlib import Path
from typing import Any

from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.execute import ExecutionResult

class RunAggregator:
    run_id: str
    flow_id: str
    mode: str
    config_digest: str
    logs_dir: Path
    iterations: list[dict[str, Any]]

    def __init__(
        self,
        *,
        run_id: str,
        flow_id: str,
        mode: str,
        config_digest: str,
        logs_dir: Path,
    ) -> None: ...
    def record(self, result: ExecutionResult) -> None: ...
    def build_report(
        self,
        *,
        status: str,
        started_at: str,
        duration_ms: float,
        warnings: list[dict[str, Any]] | None = ...,
        error: dict[str, Any] | None = ...,
    ) -> RunReport: ...
