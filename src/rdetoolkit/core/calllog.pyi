from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

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

def get_active_recorder() -> CallLogRecorder | None: ...
def type_name_of(target: type) -> str: ...

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
    ) -> None: ...
    @property
    def records(self) -> tuple[NodeCallRecord, ...]: ...
    def __enter__(self) -> CallLogRecorder: ...
    def __exit__(self, exc_type: object, exc: object, tb: object) -> None: ...
    def call_node(self, spec: Any, fn: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any: ...
