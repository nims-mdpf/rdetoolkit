from collections.abc import Iterable
from pathlib import Path
from typing import Any

from rdetoolkit.modes.protocol import PlanningContext, RawCopyStrategy
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.planner import ExecutionPlan, TilePlan

class SmartTableModeHandler:
    kind: ModeKind
    def create_tiles(self, context: PlanningContext) -> Iterable[TilePlan]: ...
    def raw_copy_strategy(self, plan: ExecutionPlan) -> RawCopyStrategy | None: ...
    def artifact_stage_order(self, plan: ExecutionPlan) -> tuple[str, ...] | None: ...

class SmartTableInvoiceBuilder:
    def __init__(self) -> None: ...
    def reset(self) -> None: ...
    def build(
        self,
        *,
        rowfile: Path,
        invoice_org: Path,
        invoice_schema_path: Path,
        dist_path: Path,
        metadata_def_path: Path,
        metadata_path: Path,
    ) -> dict[str, Any] | None: ...
