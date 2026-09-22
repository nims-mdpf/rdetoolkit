from collections.abc import Iterable
from pathlib import Path

from rdetoolkit.modes.protocol import PlanningContext, RawCopyStrategy
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.planner import ExecutionPlan, TilePlan
from rdetoolkit.types import RdeConfig

class RdeFormatRawCopyStrategy:
    def copy(
        self,
        source_files: tuple[Path, ...],
        *,
        raw_dir: Path,
        nonshared_raw_dir: Path,
        config: RdeConfig,
        smarttable: bool = ...,
        data_root: Path,
    ) -> None: ...

class RdeFormatModeHandler:
    kind: ModeKind
    def create_tiles(self, context: PlanningContext) -> Iterable[TilePlan]: ...
    def raw_copy_strategy(self, plan: ExecutionPlan) -> RawCopyStrategy | None: ...
    def artifact_stage_order(self, plan: ExecutionPlan) -> tuple[str, ...] | None: ...
