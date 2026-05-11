from dataclasses import dataclass
from typing import Any

from rdetoolkit.report.events import Event

@dataclass(frozen=True, slots=True)
class NodeResult:
    node_id: str
    status: str
    duration: float
    error: str | None = ...
    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NodeResult: ...

@dataclass(frozen=True, slots=True)
class RunReport:
    phase: str
    node_results: list[NodeResult]
    duration: float
    events: list[Event] = ...
    @property
    def success_count(self) -> int: ...
    @property
    def failure_count(self) -> int: ...
    @property
    def skip_count(self) -> int: ...
    def to_json(self, *, indent: int | None = ...) -> str: ...
    @classmethod
    def from_json(cls, json_str: str) -> RunReport: ...
