from contextlib import AbstractContextManager
from contextvars import ContextVar
from typing import Protocol

from rdetoolkit.api.request import ExecutionTarget
from rdetoolkit.core.context import RunContext
from rdetoolkit.report.events import EventSink
from rdetoolkit.runner.execute import ExecutionResult
from rdetoolkit.runner.planner import TileMaterial
from rdetoolkit.types import RdeConfig

_TARGET_FAILURES: ContextVar[list[Exception] | None]

def capture_target_failures() -> AbstractContextManager[list[Exception]]: ...
def capture_run_failures() -> AbstractContextManager[list[Exception]]: ...
def record_run_failure(exc: Exception) -> None: ...

class TargetInvoker(Protocol):
    def invoke(
        self,
        target: ExecutionTarget,
        context: RunContext,
        *,
        event_sink: EventSink,
        run_id: str,
        config: RdeConfig,
        material: TileMaterial,
    ) -> ExecutionResult: ...

class FlowInvoker:
    def invoke(
        self,
        target: ExecutionTarget,
        context: RunContext,
        *,
        event_sink: EventSink,
        run_id: str,
        config: RdeConfig,
        material: TileMaterial,
    ) -> ExecutionResult: ...

class InvokerRegistry:
    def __init__(
        self,
        *,
        flow_invoker: TargetInvoker | None = ...,
        legacy_invoker: TargetInvoker | None = ...,
    ) -> None: ...
    def for_target(self, target: ExecutionTarget) -> TargetInvoker: ...
    def invoke(
        self,
        target: ExecutionTarget,
        context: RunContext,
        *,
        event_sink: EventSink,
        run_id: str,
        config: RdeConfig,
        material: TileMaterial,
    ) -> ExecutionResult: ...
