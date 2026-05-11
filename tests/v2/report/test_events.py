"""Tests for Phase 2.1: Event, EventSink Protocol, and sink implementations.

EP Table:
| API                    | Partition               | Rationale           | Expected                   | Test ID    |
|------------------------|-------------------------|---------------------|----------------------------|------------|
| Event()                | valid fields            | normal construction | all fields accessible      | TC-EP-001  |
| Event.node_started     | factory with node_id    | convenience method  | kind="node_started"        | TC-EP-002  |
| Event.node_finished    | factory with payload    | convenience method  | kind="node_finished"       | TC-EP-003  |
| Event.node_failed      | factory with error      | convenience method  | kind="node_failed"         | TC-EP-004  |
| MemoryEventSink.emit   | emit event              | protocol conformance| stored in .events          | TC-EP-005  |
| MemoryEventSink        | isinstance EventSink    | protocol check      | True                       | TC-EP-006  |
| FileEventSink.emit     | emit event              | JSONL output        | line written               | TC-EP-007  |
| FileEventSink          | isinstance EventSink    | protocol check      | True                       | TC-EP-008  |

BV Table:
| API                    | Boundary                | Rationale           | Expected                   | Test ID    |
|------------------------|-------------------------|---------------------|----------------------------|------------|
| Event()                | empty payload           | minimal event       | payload={}                 | TC-BV-001  |
| MemoryEventSink        | zero events emitted     | empty state         | events == []               | TC-BV-002  |
| Event.node_failed      | no error message        | edge case           | payload has empty error_msg| TC-BV-003  |
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rdetoolkit.report.events import (
    Event,
    EventSink,
    FileEventSink,
    MemoryEventSink,
)


class TestEvent:
    """Tests for the Event dataclass."""

    def test_event_construction_and_field_access__tc_ep_001(self) -> None:
        """TC-EP-001: Event can be constructed and fields are accessible."""
        # Given: valid event fields
        # When: constructing an Event
        event = Event(
            node_id="my_node",
            kind="node_started",
            timestamp=1234567890.0,
            payload={"key": "value"},
        )
        # Then: all fields are accessible
        assert event.node_id == "my_node"
        assert event.kind == "node_started"
        assert event.timestamp == 1234567890.0
        assert event.payload == {"key": "value"}

    def test_event_empty_payload__tc_bv_001(self) -> None:
        """TC-BV-001: Event with empty payload is valid."""
        # Given/When: event with no payload
        event = Event(
            node_id="n", kind="custom", timestamp=0.0, payload={},
        )
        # Then: payload is empty dict
        assert event.payload == {}

    def test_event_node_started_factory__tc_ep_002(self) -> None:
        """TC-EP-002: node_started factory creates correct event."""
        # Given: a node_id
        # When: using the factory method
        event = Event.node_started("my_node")
        # Then: kind is "node_started" and node_id matches
        assert event.kind == "node_started"
        assert event.node_id == "my_node"
        assert isinstance(event.timestamp, float)
        assert event.timestamp > 0

    def test_event_node_finished_factory__tc_ep_003(self) -> None:
        """TC-EP-003: node_finished factory creates correct event with duration."""
        # Given: a node_id and duration
        # When: using the factory method
        event = Event.node_finished("my_node", duration=1.5)
        # Then: kind is "node_finished" and duration is in payload
        assert event.kind == "node_finished"
        assert event.node_id == "my_node"
        assert event.payload["duration"] == 1.5

    def test_event_node_failed_factory__tc_ep_004(self) -> None:
        """TC-EP-004: node_failed factory creates correct event with error info."""
        # Given: a node_id and error
        err = ValueError("something went wrong")
        # When: using the factory method
        event = Event.node_failed("my_node", error=err)
        # Then: kind is "node_failed" and error info is in payload
        assert event.kind == "node_failed"
        assert event.node_id == "my_node"
        assert event.payload["error_type"] == "ValueError"
        assert event.payload["error_msg"] == "something went wrong"

    def test_event_node_failed_empty_message__tc_bv_003(self) -> None:
        """TC-BV-003: node_failed with empty error message."""
        # Given: error with empty message
        err = RuntimeError("")
        # When: using the factory method
        event = Event.node_failed("n", error=err)
        # Then: error_msg is empty string
        assert event.payload["error_msg"] == ""

    def test_event_node_skipped_factory__new(self) -> None:
        """NEW: node_skipped factory creates correct event with reason."""
        # Given: a node_id and skip reason
        # When: using the factory method
        event = Event.node_skipped("my_node", reason="upstream 'src' failed")
        # Then: kind is "node_skipped" and reason is in payload
        assert event.kind == "node_skipped"
        assert event.node_id == "my_node"
        assert event.payload["reason"] == "upstream 'src' failed"
        assert isinstance(event.timestamp, float)

    def test_event_to_dict(self) -> None:
        """Event can be serialized to a dict."""
        # Given: an event
        event = Event(
            node_id="a", kind="node_started", timestamp=1.0, payload={"x": 1},
        )
        # When: converting to dict
        d = event.to_dict()
        # Then: dict has all fields
        assert d == {
            "node_id": "a",
            "kind": "node_started",
            "timestamp": 1.0,
            "payload": {"x": 1},
        }


class TestMemoryEventSink:
    """Tests for the MemoryEventSink implementation."""

    def test_memory_sink_emit__tc_ep_005(self) -> None:
        """TC-EP-005: MemoryEventSink stores emitted events."""
        # Given: a MemoryEventSink
        sink = MemoryEventSink()
        event = Event(node_id="a", kind="test", timestamp=1.0, payload={})
        # When: emitting an event
        sink.emit(event)
        # Then: event is stored
        assert len(sink.events) == 1
        assert sink.events[0] is event

    def test_memory_sink_isinstance_event_sink__tc_ep_006(self) -> None:
        """TC-EP-006: MemoryEventSink satisfies EventSink protocol."""
        # Given/When: a MemoryEventSink instance
        sink = MemoryEventSink()
        # Then: it is an instance of EventSink
        assert isinstance(sink, EventSink)

    def test_memory_sink_empty__tc_bv_002(self) -> None:
        """TC-BV-002: Fresh MemoryEventSink has no events."""
        # Given/When: a new sink
        sink = MemoryEventSink()
        # Then: events list is empty
        assert sink.events == []

    def test_memory_sink_multiple_events(self) -> None:
        """MemoryEventSink accumulates multiple events in order."""
        # Given: a sink
        sink = MemoryEventSink()
        e1 = Event(node_id="a", kind="start", timestamp=1.0, payload={})
        e2 = Event(node_id="b", kind="end", timestamp=2.0, payload={})
        # When: emitting multiple events
        sink.emit(e1)
        sink.emit(e2)
        # Then: both are stored in order
        assert len(sink.events) == 2
        assert sink.events[0] is e1
        assert sink.events[1] is e2


class TestFileEventSink:
    """Tests for the FileEventSink implementation."""

    def test_file_sink_emit__tc_ep_007(self, tmp_path: Path) -> None:
        """TC-EP-007: FileEventSink writes JSONL to file."""
        # Given: a FileEventSink with a temp file
        filepath = tmp_path / "events.jsonl"
        sink = FileEventSink(filepath)
        event = Event(
            node_id="a", kind="node_started", timestamp=1.0, payload={"x": 1},
        )
        # When: emitting an event
        sink.emit(event)
        # Then: file contains one JSON line
        lines = filepath.read_text().strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["node_id"] == "a"
        assert data["kind"] == "node_started"
        assert data["timestamp"] == 1.0
        assert data["payload"] == {"x": 1}

    def test_file_sink_isinstance_event_sink__tc_ep_008(self, tmp_path: Path) -> None:
        """TC-EP-008: FileEventSink satisfies EventSink protocol."""
        # Given/When: a FileEventSink instance
        sink = FileEventSink(tmp_path / "events.jsonl")
        # Then: it is an instance of EventSink
        assert isinstance(sink, EventSink)

    def test_file_sink_multiple_events(self, tmp_path: Path) -> None:
        """FileEventSink writes multiple events as separate lines."""
        # Given: a FileEventSink
        filepath = tmp_path / "events.jsonl"
        sink = FileEventSink(filepath)
        e1 = Event(node_id="a", kind="start", timestamp=1.0, payload={})
        e2 = Event(node_id="b", kind="end", timestamp=2.0, payload={"dur": 0.5})
        # When: emitting two events
        sink.emit(e1)
        sink.emit(e2)
        # Then: file has two lines
        lines = filepath.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["node_id"] == "a"
        assert json.loads(lines[1])["node_id"] == "b"
