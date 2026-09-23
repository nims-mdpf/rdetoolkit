from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from rdetoolkit.api.request import ExecutionTarget, RunRequest
from rdetoolkit.domain.invoice_service import InvoiceService
from rdetoolkit.modes.protocol import PlanningContext
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import InputPaths, InvoiceData, IterationInfo, OutputContext, RdeConfig

@dataclass(frozen=True, slots=True)
class TilePreparation:
    invoice: InvoiceData | None = ...
    smarttable_row_data: Mapping[str, Any] | None = ...

@dataclass(frozen=True, slots=True)
class TilePlan:
    iteration: IterationInfo
    paths: InputPaths
    out: OutputContext
    invoice: InvoiceData | None
    prepare_invoice: Callable[[], TilePreparation] | None = ...
    precompleted: bool = ...

@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    run_id: str
    target: ExecutionTarget
    mode: ModeKind
    config: RdeConfig
    root: Path
    error_policy: Literal["continue", "fail_fast"]
    tiles: Iterable[TilePlan]
    data_root: Path
    invoice_source: Path

@dataclass(frozen=True, slots=True)
class TileMaterial:
    invoice_source: Path
    smarttable_row_data: Mapping[str, Any] | None = ...

PathProvider = Path | Callable[[], Path]

class RunPlanner:
    def __init__(
        self,
        *,
        inputdata_path: PathProvider,
        unpacked_dir_path: PathProvider,
        run_id_factory: Callable[[], str],
        invoice_service: InvoiceService | None = ...,
    ) -> None: ...
    def create(
        self,
        request: RunRequest,
        *,
        config: RdeConfig,
        mode: ModeKind,
        data_root: Path,
    ) -> ExecutionPlan: ...

def create_common_tiles(mode: ModeKind, context: PlanningContext) -> Iterator[TilePlan]: ...
