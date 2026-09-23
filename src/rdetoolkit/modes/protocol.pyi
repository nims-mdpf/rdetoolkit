from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from rdetoolkit.domain.invoice_service import InvoiceService
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.planner import ExecutionPlan, TilePlan
from rdetoolkit.types import RdeConfig

@dataclass(frozen=True, slots=True)
class PlanningContext:
    root: Path
    inputdata_path: Path
    unpacked_dir_path: Path
    invoice_service: InvoiceService
    data_root: Path
    config: RdeConfig | None = ...

class RawCopyStrategy(Protocol):
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

class ModeHandler(Protocol):
    kind: ModeKind
    def create_tiles(self, context: PlanningContext) -> Iterable[TilePlan]: ...

class RawCopyStrategyProvider(Protocol):
    def raw_copy_strategy(self, plan: ExecutionPlan) -> RawCopyStrategy | None: ...

class ArtifactStageProvider(Protocol):
    def artifact_stage_order(self, plan: ExecutionPlan) -> tuple[str, ...] | None: ...
