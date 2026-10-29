"""Tests for the canonical v2 event schema and sinks."""

from __future__ import annotations

import json
from pathlib import Path

from rdetoolkit.report.events import Event, EventSink, FileEventSink, MemoryEventSink


class TestEvent:
    """Tests for the Event dataclass."""

    def test_event_construction_and_field_access__tc_ep_001(self) -> None:
        """TC-EP-001: Event can be constructed with canonical fields."""
        # Given: valid canonical event fields
        # When: constructing an Event
        event = Event(
            schema_version="1",
            run_id="run-1",
            name="node.started",
            node_id="my_node",
            timestamp=1234567890.0,
            payload={"call_id": "my_node#1"},
        )
        # Then: all canonical fields are accessible
        assert event.schema_version == "1"
        assert event.run_id == "run-1"
        assert event.name == "node.started"
        assert event.node_id == "my_node"
        assert event.timestamp == 1234567890.0
        assert event.payload == {"call_id": "my_node#1"}

    def test_event_empty_payload__tc_bv_001(self) -> None:
        """TC-BV-001: Event with empty payload is valid."""
        # Given/When: a run-scoped event with no payload
        event = Event(run_id="run-1", name="run.started", timestamp=0.0)
        # Then: node_id is optional and payload defaults to an empty dict
        assert event.node_id is None
        assert event.payload == {}

    def test_event_node_started_factory__tc_ep_002(self) -> None:
        """TC-EP-002: node_started factory creates a canonical event."""
        # Given: node and call identifiers
        # When: using the factory method
        event = Event.node_started(run_id="run-1", node_id="my_node", call_id="my_node#1")
        # Then: name is dot-separated and call_id is in payload
        assert event.name == "node.started"
        assert event.run_id == "run-1"
        assert event.node_id == "my_node"
        assert event.payload["call_id"] == "my_node#1"

    def test_event_node_completed_factory__tc_ep_003(self) -> None:
        """TC-EP-003: node_completed factory carries duration_ms."""
        # Given: node completion data
        # When: using the factory method
        event = Event.node_completed(
            run_id="run-1",
            node_id="my_node",
            call_id="my_node#1",
            duration_ms=1.5,
        )
        # Then: duration_ms is in payload
        assert event.name == "node.completed"
        assert event.payload["duration_ms"] == 1.5

    def test_event_node_failed_factory__tc_ep_004(self) -> None:
        """TC-EP-004: node_failed factory carries error info."""
        # Given: node failure details
        # When: using the factory method
        event = Event.node_failed(
            run_id="run-1",
            node_id="my_node",
            call_id="my_node#1",
            error_type="ValueError",
            error_msg="something went wrong",
        )
        # Then: error details are in payload
        assert event.name == "node.failed"
        assert event.payload["error_type"] == "ValueError"
        assert event.payload["error_msg"] == "something went wrong"

    def test_event_node_failed_empty_message__tc_bv_003(self) -> None:
        """TC-BV-003: node_failed accepts an empty error message."""
        # Given/When: an empty error message
        event = Event.node_failed(
            run_id="run-1",
            node_id="n",
            call_id="n#1",
            error_type="RuntimeError",
            error_msg="",
        )
        # Then: error_msg is preserved
        assert event.payload["error_msg"] == ""

    def test_event_iteration_started_has_no_node_id(self) -> None:
        """Iteration events are representable without node_id."""
        # Given/When: an iteration event
        event = Event.iteration_started(run_id="run-1", index=0)
        # Then: it has no node_id and carries the iteration index
        assert event.name == "iteration.started"
        assert event.node_id is None
        assert event.payload["iteration_index"] == 0

    def test_event_to_dict(self) -> None:
        """Event can be serialized to a dict."""
        # Given: an event
        event = Event(run_id="run-1", name="run.started", timestamp=1.0)
        # When: converting to dict
        data = event.to_dict()
        # Then: schema_version is first and canonical fields are present
        assert next(iter(data)) == "schema_version"
        assert data["run_id"] == "run-1"
        assert data["name"] == "run.started"


class TestMemoryEventSink:
    """Tests for the MemoryEventSink implementation."""

    def test_memory_sink_emit__tc_ep_005(self) -> None:
        """TC-EP-005: MemoryEventSink stores emitted events."""
        # Given: an opened MemoryEventSink
        sink = MemoryEventSink()
        sink.open("run-1")
        event = Event.run_started(run_id="run-1")
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


class TestFileEventSink:
    """Tests for the FileEventSink implementation."""

    def test_file_sink_emit__tc_ep_007(self, tmp_path: Path) -> None:
        """TC-EP-007: FileEventSink writes JSONL after open()."""
        # Given: an opened FileEventSink
        logs_dir = tmp_path / "logs"
        sink = FileEventSink(logs_dir)
        sink.open("run-1")
        event = Event.node_started(run_id="run-1", node_id="a", call_id="a#1")
        # When: emitting an event
        sink.emit(event)
        sink.close()
        # Then: file contains header plus the event JSON line
        lines = (logs_dir / "events_run-1.jsonl").read_text().strip().split("\n")
        assert len(lines) == 2
        header = json.loads(lines[0])
        data = json.loads(lines[1])
        assert header["run_id"] == "run-1"
        assert data["node_id"] == "a"
        assert data["name"] == "node.started"

    def test_file_sink_isinstance_event_sink__tc_ep_008(self, tmp_path: Path) -> None:
        """TC-EP-008: FileEventSink satisfies EventSink protocol."""
        # Given/When: a FileEventSink instance
        sink = FileEventSink(tmp_path / "logs")
        # Then: it is an instance of EventSink
        assert isinstance(sink, EventSink)

    def test_file_sink_multiple_events(self, tmp_path: Path) -> None:
        """FileEventSink writes multiple events as separate lines."""
        # Given: an opened FileEventSink
        logs_dir = tmp_path / "logs"
        sink = FileEventSink(logs_dir)
        sink.open("run-1")
        events = [
            Event.run_started(run_id="run-1"),
            Event.run_completed(run_id="run-1", status="success"),
        ]
        # When: emitting two events
        for event in events:
            sink.emit(event)
        sink.close()
        # Then: file has one header plus two event lines
        lines = (logs_dir / "events_run-1.jsonl").read_text().strip().split("\n")
        assert len(lines) == 3
        assert json.loads(lines[1])["name"] == "run.started"
        assert json.loads(lines[2])["payload"]["status"] == "success"

    def test_file_sink_flushes_after_each_emit__tc_ep_flush_001(self, tmp_path: Path) -> None:
        """TC-EP-flush-001 (Session D2, decisions_pre_D2.md Ruling 2 mini-task 2):
        immediately after emit(), a line written by this emit must be
        readable through a SEPARATE, independently-opened file handle --
        proving the write was flushed to the OS rather than buffered inside
        this process only.

        Implementation note (session_d2.md Current-State Survey): as of this
        session's survey, FileEventSink._write_line already calls
        self._file.flush() after every write (events.py:343) -- this test is
        expected to be an ANCHOR (already GREEN) rather than a genuine Red
        failure. It exists because the contract itself was previously
        untested, not because the behavior is new.
        """
        logs_dir = tmp_path / "logs"
        sink = FileEventSink(logs_dir)
        sink.open("run-flush")

        sink.emit(Event.node_started(run_id="run-flush", node_id="a", call_id="a#1"))

        # A second, independent file handle must already see the line --
        # the original sink object is never used to read back.
        with (logs_dir / "events_run-flush.jsonl").open(encoding="utf-8") as separate_handle:
            lines = separate_handle.read().strip().split("\n")

        sink.close()

        assert len(lines) == 2, "header line plus the just-emitted event line must both be visible"
        emitted = json.loads(lines[1])
        assert emitted["name"] == "node.started"
        assert emitted["node_id"] == "a"
