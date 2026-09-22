from collections.abc import Callable
from pathlib import Path
from typing import Any

from rdetoolkit.api.request import ExecutionTarget, RunRequest
from rdetoolkit.domain.invoice_service import InvoiceService
from rdetoolkit.report.events import EventSink
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.executor import TileExecutor
from rdetoolkit.runner.finalize import RunFinalizer
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.planner import RunPlanner
from rdetoolkit.types import RdeConfig

class Runner:
    root: Path
    inputdata_path: Path
    unpacked_dir_path: Path
    event_sink: EventSink
    run_id: str
    @property
    def data_root(self) -> Path: ...
    def __init__(
        self,
        *,
        root: Path | None = None,
        inputdata_path: Path | None = None,
        unpacked_dir_path: Path | None = None,
        event_sink: EventSink | None = None,
        run_id_factory: Callable[[], str] | None = None,
        planner: RunPlanner | None = None,
        executor: TileExecutor | None = None,
        finalizer: RunFinalizer | None = None,
        invoice_service: InvoiceService | None = None,
    ) -> None: ...
    def run(self, request: RunRequest | Callable[..., Any], **overrides: Any) -> RunReport: ...
    def load_config(self, source: object | None = None) -> RdeConfig: ...
    def resolve_mode(self, config: RdeConfig) -> ModeKind: ...
    def pre_validate(self, config: RdeConfig) -> None: ...
    def iterate(
        self,
        target: ExecutionTarget | Callable[..., Any],
        mode: ModeKind,
        config: RdeConfig,
    ) -> RunReport: ...
    def post_validate(self, config: RdeConfig, report: RunReport) -> None: ...
    def finalize(self, report: RunReport, config: RdeConfig) -> None: ...
