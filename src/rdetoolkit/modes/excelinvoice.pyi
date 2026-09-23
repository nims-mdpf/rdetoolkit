from collections.abc import Iterable

from rdetoolkit.modes.protocol import PlanningContext, RawCopyStrategy
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.planner import ExecutionPlan, TilePlan

class ExcelInvoiceModeHandler:
    kind: ModeKind
    def create_tiles(self, context: PlanningContext) -> Iterable[TilePlan]: ...
    def raw_copy_strategy(self, plan: ExecutionPlan) -> RawCopyStrategy | None: ...
    def artifact_stage_order(self, plan: ExecutionPlan) -> tuple[str, ...] | None: ...
