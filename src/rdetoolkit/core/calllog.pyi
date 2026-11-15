from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

@dataclass(frozen=True, slots=True)
class TypeSummary:
    type_name: str
    repr_head: str | None

@dataclass(frozen=True, slots=True)
class NodeCallRecord:
    call_id: str
    node_id: str
    parent_flow: str | None
    seq: int
    iteration_index: int
    started_at: str
    duration_ms: float
    status: Literal["completed", "failed"]
    inputs: dict[str, TypeSummary]
    outputs: tuple[TypeSummary, ...]
    error: dict[str, Any] | None

class CallSequence:
    def __init__(self) -> None: ...
    def next(self) -> int: ...
    def next_invocation(self) -> int: ...

@dataclass(frozen=True, slots=True)
class NodeInvocation:
    invocation_id: str
    node_id: str
    iteration_index: int
    parent_invocation_id: str | None

class InvocationListener(Protocol):
    def invocation_started(self, invocation: NodeInvocation) -> None: ...
    def invocation_finished(self, invocation: NodeInvocation, record: NodeCallRecord) -> None: ...

def get_active_recorder() -> CallLogRecorder | None: ...
def type_name_of(target: type) -> str: ...

# Internal: the single summary implementation, shared with runner/execute.py
# (#641). Declared here so the Runner's import type-checks; not public API.
def _summarize_outputs(value: Any, *, repr_head: str, repr_head_len: int) -> tuple[TypeSummary, ...]: ...

class CallLogRecorder:
    repr_head: Literal["on", "off"]
    repr_head_len: int
    type_check: Literal["off", "warn", "strict"]
    iteration_index: int
    def __init__(
        self,
        *,
        repr_head: Literal["on", "off"] = "off",
        repr_head_len: int = 80,
        type_check: Literal["off", "warn", "strict"] = "off",
        iteration_index: int = 0,
        sequence: CallSequence | None = None,
        invocation_listener: InvocationListener | None = None,
    ) -> None: ...
    @property
    def records(self) -> tuple[NodeCallRecord, ...]: ...
    def __enter__(self) -> CallLogRecorder: ...
    def __exit__(self, exc_type: object, exc: object, tb: object) -> None: ...
    def call_node(self, spec: Any, fn: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any: ...
