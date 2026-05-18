"""V2 Event system — events, sinks, and observability primitives.

Provides an ``Event`` dataclass with factory methods for common lifecycle
events, an ``EventSink`` Protocol for pluggable event handling, and two
concrete sink implementations: ``MemoryEventSink`` (testing) and
``FileEventSink`` (JSONL output).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Event:
    """An observable event emitted during workflow execution.

    Attributes:
        node_id: ID of the node that produced the event.
        kind: Event kind string (e.g. "node_started", "node_finished", "node_failed").
        timestamp: Unix timestamp (seconds since epoch).
        payload: Additional event-specific data.
    """

    node_id: str
    kind: str
    timestamp: float
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def node_started(cls, node_id: str) -> Event:
        """Create a node_started event.

        Args:
            node_id: ID of the node that started.

        Returns:
            An Event with kind="node_started".
        """
        return cls(
            node_id=node_id,
            kind="node_started",
            timestamp=time.time(),
        )

    @classmethod
    def node_finished(cls, node_id: str, *, duration: float) -> Event:
        """Create a node_finished event.

        Args:
            node_id: ID of the node that finished.
            duration: Execution duration in seconds.

        Returns:
            An Event with kind="node_finished" and duration in payload.
        """
        return cls(
            node_id=node_id,
            kind="node_finished",
            timestamp=time.time(),
            payload={"duration": duration},
        )

    @classmethod
    def node_failed(cls, node_id: str, *, error: Exception) -> Event:
        """Create a node_failed event.

        Args:
            node_id: ID of the node that failed.
            error: The exception that caused the failure.

        Returns:
            An Event with kind="node_failed" and error info in payload.
        """
        return cls(
            node_id=node_id,
            kind="node_failed",
            timestamp=time.time(),
            payload={
                "error_type": type(error).__name__,
                "error_msg": str(error),
            },
        )

    @classmethod
    def node_skipped(cls, node_id: str, *, reason: str) -> Event:
        """Create a node_skipped event.

        Args:
            node_id: ID of the node that was skipped.
            reason: Reason for skipping (e.g., "upstream 'src' failed").

        Returns:
            An Event with kind="node_skipped" and reason in payload.
        """
        return cls(
            node_id=node_id,
            kind="node_skipped",
            timestamp=time.time(),
            payload={"reason": reason},
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to a plain dict.

        Returns:
            Dict with all event fields.
        """
        return {
            "node_id": self.node_id,
            "kind": self.kind,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }


@runtime_checkable
class EventSink(Protocol):
    """Protocol for event sinks that receive workflow events."""

    def emit(self, event: Event) -> None:
        """Emit an event to this sink.

        Args:
            event: The event to emit.
        """
        ...


class MemoryEventSink:
    """In-memory event sink that accumulates events in a list.

    Useful for testing and inspection.

    Attributes:
        events: List of emitted events.
    """

    def __init__(self) -> None:
        self.events: list[Event] = []

    def emit(self, event: Event) -> None:
        """Store an event in the internal list.

        Args:
            event: The event to store.
        """
        self.events.append(event)


class FileEventSink:
    """Event sink that writes events as JSONL (one JSON object per line).

    The parent directory of ``path`` is created on construction (idempotent)
    so callers do not need to ensure the directory exists ahead of time.

    Args:
        path: Path to the output JSONL file.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        # Ensure parent directory exists to avoid FileNotFoundError on emit().
        parent = self._path.parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: Event) -> None:
        """Append an event as a JSON line to the file.

        Args:
            event: The event to write.
        """
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
