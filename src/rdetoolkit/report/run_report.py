"""V2 RunReport — execution result summary with serialization.

Captures the outcome of a workflow execution including per-node results,
timing, and the event stream for later analysis or persistence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from rdetoolkit.report.events import Event


@dataclass(frozen=True, slots=True)
class NodeResult:
    """Result of executing a single node.

    Attributes:
        node_id: ID of the executed node.
        status: "success", "failed", or "skipped".
        duration: Execution duration in seconds.
        error: Error message if status is "failed", else None.
    """

    node_id: str
    status: str
    duration: float
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict.

        Returns:
            Dict with all fields.
        """
        d: dict[str, Any] = {
            "node_id": self.node_id,
            "status": self.status,
            "duration": self.duration,
        }
        if self.error is not None:
            d["error"] = self.error
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NodeResult:
        """Deserialize from a plain dict.

        Args:
            data: Dict with node result fields.

        Returns:
            A NodeResult instance.
        """
        return cls(
            node_id=data["node_id"],
            status=data["status"],
            duration=data["duration"],
            error=data.get("error"),
        )


@dataclass(frozen=True, slots=True)
class RunReport:
    """Summary of a workflow execution run.

    Attributes:
        phase: Execution phase name (e.g. "execute").
        node_results: Per-node execution results.
        duration: Total execution duration in seconds.
        events: Event stream captured during execution.
    """

    phase: str
    node_results: list[NodeResult]
    duration: float
    events: list[Event] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        """Count of nodes that completed successfully.

        Returns:
            Number of node results with status "success".
        """
        return sum(1 for nr in self.node_results if nr.status == "success")

    @property
    def failure_count(self) -> int:
        """Count of nodes that failed.

        Returns:
            Number of node results with status "failed".
        """
        return sum(1 for nr in self.node_results if nr.status == "failed")

    @property
    def skip_count(self) -> int:
        """Count of nodes that were skipped.

        Returns:
            Number of node results with status "skipped".
        """
        return sum(1 for nr in self.node_results if nr.status == "skipped")

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialize the report to a JSON string.

        Args:
            indent: JSON indentation level (None for compact).

        Returns:
            JSON string representation.
        """
        data: dict[str, Any] = {
            "phase": self.phase,
            "node_results": [nr.to_dict() for nr in self.node_results],
            "duration": self.duration,
            "events": [e.to_dict() for e in self.events],
        }
        return json.dumps(data, ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> RunReport:
        """Deserialize a RunReport from a JSON string.

        Args:
            json_str: JSON string produced by ``to_json()``.

        Returns:
            A RunReport instance.
        """
        data = json.loads(json_str)
        node_results = [NodeResult.from_dict(nr) for nr in data["node_results"]]
        events = [
            Event(
                node_id=e["node_id"],
                kind=e["kind"],
                timestamp=e["timestamp"],
                payload=e.get("payload", {}),
            )
            for e in data.get("events", [])
        ]
        return cls(
            phase=data["phase"],
            node_results=node_results,
            duration=data["duration"],
            events=events,
        )
