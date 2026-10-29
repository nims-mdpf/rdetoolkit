from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from rdetoolkit.core.calllog import CallSequence, NodeCallRecord, TypeSummary
from rdetoolkit.core.context import RunContext
from rdetoolkit.errors import RdeExecutionError
from rdetoolkit.report.events import EventSink
from rdetoolkit.types import RdeConfig

@dataclass(frozen=True, slots=True)
class ExecutionResult:
    iteration_index: int
    status: Literal["completed", "failed"]
    call_records: tuple[NodeCallRecord, ...]
    outputs: tuple[TypeSummary, ...]
    error: dict[str, Any] | None = ...
    datatile_id: str = ...
    title: str = ...
    target: str | None = ...
    stacktrace: str | None = ...

class TileExecutionError(RdeExecutionError):
    result: ExecutionResult
    def __init__(self, result: ExecutionResult, cause: Exception) -> None: ...

def run_tile(
    flow_fn: Callable[..., Any],
    run_context: RunContext,
    *,
    event_sink: EventSink,
    run_id: str,
    config: RdeConfig,
    emit_iteration_events: bool = ...,
    sequence: CallSequence | None = ...,
) -> ExecutionResult: ...
