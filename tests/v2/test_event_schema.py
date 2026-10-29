"""Canonical acceptance tests for rdetoolkit v2 Event / EventSink / RunReport — Session A2.

Written before implementation (TDD Red phase).
Target: make all tests pass in the codex-worker Green phase.

TC-EVENT-001..023 as inventoried in local/develop/v2/tasks/session_a2.md.
Authority: local/develop/v2/Design.md §8 (Events, EventSink, RunReport schemas).

No compat anchors expected for this file — all tests target the new canonical API
which diverges substantially from the archive-restored pre-A2 implementation.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Helper — constructs a minimal valid RunReport for round-trip tests.
# Defined at module level so it can be shared across test classes.
# ---------------------------------------------------------------------------


def _make_run_report(**overrides: Any):  # type: ignore[return]
    """Return a minimal valid RunReport constructed with Design §8.3 fields."""
    from rdetoolkit.report.run_report import RunReport  # noqa: PLC0415

    defaults: dict[str, Any] = {
        "schema_version": "2",
        "run_id": "test-run-id",
        "status": "success",
        "flow_id": "pkg.mod:pipeline",
        "mode": "invoice",
        "started_at": "2026-01-01T00:00:00Z",
        "duration_ms": 123.4,
        "config_digest": "sha256:abcdef",
        "iterations": [],
        "warnings": [],
    }
    defaults.update(overrides)
    return RunReport(**defaults)


# ===========================================================================
# Event schema — TC-EVENT-001..012
# ===========================================================================


class TestEventSchemaVersion:
    """TC-EVENT-001: Event.schema_version must default to '1'."""

    def test_event_schema_version_defaults_to_one__tc_event_001(self) -> None:
        """TC-EVENT-001: Event has schema_version='1' (str) by default."""
        import dataclasses as dc  # noqa: PLC0415

        from rdetoolkit.report.events import Event  # noqa: PLC0415

        field_names = {f.name for f in dc.fields(Event)}
        assert "schema_version" in field_names, (
            "Event must have a schema_version field per Design §8.1"
        )
        # Use the run_started factory to obtain a concrete instance
        e = Event.run_started(run_id="check-version")
        assert e.schema_version == "1", (
            f"Event.schema_version must default to '1', got {e.schema_version!r}"
        )
        assert isinstance(e.schema_version, str), (
            "schema_version must be a str, not an int"
        )


class TestEventRequiredFields:
    """TC-EVENT-002..004: run_id required, name dot-separated, node_id optional."""

    def test_event_run_id_is_required_field__tc_event_002(self) -> None:
        """TC-EVENT-002: Event.run_id is a required str field; omitting it raises TypeError."""
        import dataclasses as dc  # noqa: PLC0415

        from rdetoolkit.report.events import Event  # noqa: PLC0415

        field_names = {f.name for f in dc.fields(Event)}
        assert "run_id" in field_names, (
            "Event must have a run_id field — all events carry run_id per Design §8.1"
        )
        # Trying to build Event without run_id (using new canonical fields) must fail
        with pytest.raises(TypeError):
            Event(schema_version="1", name="run.started")  # type: ignore[call-arg]

    def test_event_name_field_is_dot_separated__tc_event_003(self) -> None:
        """TC-EVENT-003: Event.name field exists and uses dot-separated format."""
        import dataclasses as dc  # noqa: PLC0415

        from rdetoolkit.report.events import Event  # noqa: PLC0415

        field_names = {f.name for f in dc.fields(Event)}
        assert "name" in field_names, (
            "Event must have a 'name' field (not 'kind'). "
            "The old 'kind' field is replaced by dot-separated 'name' per Design §8.1."
        )
        e = Event.run_started(run_id="name-test")
        assert "." in e.name, (
            f"Event.name must be dot-separated (e.g. 'run.started'), got {e.name!r}"
        )

    def test_event_node_id_is_optional_none_accepted__tc_event_004(self) -> None:
        """TC-EVENT-004: Event.node_id is Optional — iteration events need no node_id."""
        from rdetoolkit.report.events import Event  # noqa: PLC0415

        # iteration.started is an event without a node — node_id must be None-able
        e = Event.iteration_started(run_id="iter-test", index=0)
        assert e.node_id is None, (
            f"iteration.started event must have node_id=None, got {e.node_id!r}. "
            "Design §8.1: 'node_id を必須にしない (iteration イベントを表現できなかった旧スキーマ欠陥の解消)'"
        )


# ---------------------------------------------------------------------------
# TC-EVENT-005..012: Factory methods for each canonical event name
# ---------------------------------------------------------------------------


class TestEventFactories:
    """Event classmethod factories for the 8 canonical event names (Design §8.1)."""

    def test_run_started_factory__tc_event_005(self) -> None:
        """TC-EVENT-005: Event.run_started(run_id) sets name='run.started'."""
        from rdetoolkit.report.events import Event  # noqa: PLC0415

        e = Event.run_started(run_id="run-abc")
        assert e.name == "run.started"
        assert e.run_id == "run-abc"

    def test_run_completed_factory__tc_event_006(self) -> None:
        """TC-EVENT-006: Event.run_completed(run_id) sets name='run.completed'."""
        from rdetoolkit.report.events import Event  # noqa: PLC0415

        e = Event.run_completed(run_id="run-abc")
        assert e.name == "run.completed"
        assert e.run_id == "run-abc"

    def test_iteration_started_factory_with_index_in_payload__tc_event_007(self) -> None:
        """TC-EVENT-007: Event.iteration_started(run_id, index) carries index in payload."""
        from rdetoolkit.report.events import Event  # noqa: PLC0415

        e = Event.iteration_started(run_id="run-1", index=3)
        assert e.name == "iteration.started"
        assert e.run_id == "run-1"
        # iteration_index must be in the payload (Design §8.1)
        assert e.payload.get("iteration_index") == 3, (
            f"iteration.started payload must contain iteration_index=3, got {e.payload}"
        )

    def test_iteration_completed_factory__tc_event_008(self) -> None:
        """TC-EVENT-008: Event.iteration_completed(run_id, index) sets name='iteration.completed'."""
        from rdetoolkit.report.events import Event  # noqa: PLC0415

        e = Event.iteration_completed(run_id="run-1", index=3)
        assert e.name == "iteration.completed"
        assert e.payload.get("iteration_index") == 3

    def test_node_started_factory_with_call_id_in_payload__tc_event_009(self) -> None:
        """TC-EVENT-009: Event.node_started(run_id, node_id, call_id) carries call_id."""
        from rdetoolkit.report.events import Event  # noqa: PLC0415

        e = Event.node_started(
            run_id="run-1", node_id="pkg.mod.read_xrd", call_id="pkg.mod.read_xrd#1"
        )
        assert e.name == "node.started"
        assert e.run_id == "run-1"
        assert e.node_id == "pkg.mod.read_xrd"
        assert e.payload.get("call_id") == "pkg.mod.read_xrd#1", (
            f"node.started payload must contain call_id, got {e.payload}"
        )

    def test_node_completed_factory_with_duration_in_payload__tc_event_010(self) -> None:
        """TC-EVENT-010: Event.node_completed carries call_id and duration_ms in payload."""
        from rdetoolkit.report.events import Event  # noqa: PLC0415

        e = Event.node_completed(
            run_id="run-1",
            node_id="pkg.mod.normalize",
            call_id="pkg.mod.normalize#1",
            duration_ms=42.5,
        )
        assert e.name == "node.completed"
        assert e.payload.get("call_id") == "pkg.mod.normalize#1"
        assert e.payload.get("duration_ms") == pytest.approx(42.5)

    def test_node_failed_factory_with_error_info_in_payload__tc_event_011(self) -> None:
        """TC-EVENT-011: Event.node_failed carries error_type and error_msg in payload."""
        from rdetoolkit.report.events import Event  # noqa: PLC0415

        e = Event.node_failed(
            run_id="run-1",
            node_id="pkg.mod.save_csv",
            call_id="pkg.mod.save_csv#1",
            error_type="ValueError",
            error_msg="bad value",
        )
        assert e.name == "node.failed"
        assert e.payload.get("error_type") == "ValueError"
        assert e.payload.get("error_msg") == "bad value"
        assert e.payload.get("call_id") == "pkg.mod.save_csv#1"

    def test_warning_factory_with_code_in_payload__tc_event_012(self) -> None:
        """TC-EVENT-012: Event.warning(run_id, code, message) sets name='warning'."""
        from rdetoolkit.report.events import Event  # noqa: PLC0415

        e = Event.warning(run_id="run-1", code=1001, message="Mode overridden by file")
        assert e.name == "warning"
        assert e.run_id == "run-1"
        assert e.payload.get("code") == 1001
        assert "Mode overridden" in e.payload.get("message", "")


# ===========================================================================
# EventSink Protocol — TC-EVENT-013..014
# ===========================================================================


class TestEventSinkProtocol:
    """EventSink Protocol must declare open(), emit(), and close() (Design §8.2)."""

    def test_event_sink_protocol_has_open_method__tc_event_013(self) -> None:
        """TC-EVENT-013: EventSink Protocol declares open(run_id: str) -> None."""
        from rdetoolkit.report.events import EventSink  # noqa: PLC0415

        assert hasattr(EventSink, "open"), (
            "EventSink Protocol must declare an 'open(run_id: str)' method per Design §8.2"
        )

    def test_event_sink_protocol_has_close_method__tc_event_014(self) -> None:
        """TC-EVENT-014: EventSink Protocol declares close() -> None."""
        from rdetoolkit.report.events import EventSink  # noqa: PLC0415

        assert hasattr(EventSink, "close"), (
            "EventSink Protocol must declare a 'close()' method per Design §8.2"
        )


# ===========================================================================
# FileEventSink — TC-EVENT-015..016
# ===========================================================================


class TestFileEventSink:
    """FileEventSink writes to logs/events_{run_id}.jsonl with a run-meta header."""

    def test_file_event_sink_filename_contains_run_id__tc_event_015(
        self, tmp_path: Path
    ) -> None:
        """TC-EVENT-015: FileEventSink creates events_{run_id}.jsonl in the logs dir."""
        from rdetoolkit.report.events import FileEventSink  # noqa: PLC0415

        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        run_id = "abc-123"
        sink = FileEventSink(logs_dir)
        sink.open(run_id)
        sink.close()

        expected_file = logs_dir / f"events_{run_id}.jsonl"
        assert expected_file.exists(), (
            f"FileEventSink must create {expected_file.name} in the logs directory, "
            f"not a fixed path. Files found: {list(logs_dir.iterdir())}"
        )

    def test_file_event_sink_open_writes_run_meta_header_line__tc_event_016(
        self, tmp_path: Path
    ) -> None:
        """TC-EVENT-016: FileEventSink.open() writes run-meta JSONL header as line 1."""
        from rdetoolkit.report.events import FileEventSink  # noqa: PLC0415

        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        run_id = "header-test"
        sink = FileEventSink(logs_dir)
        sink.open(run_id)
        sink.close()

        log_file = logs_dir / f"events_{run_id}.jsonl"
        assert log_file.exists(), "Log file must be created by open()"
        lines = [ln for ln in log_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) >= 1, "At least one line (run-meta header) must be written by open()"
        header = json.loads(lines[0])
        assert "run_id" in header, (
            f"First line must be a JSON run-meta object containing 'run_id'. Got: {lines[0]}"
        )
        assert header["run_id"] == run_id


# ===========================================================================
# RunReport schema — TC-EVENT-017..023
# ===========================================================================


class TestRunReportSchema:
    """RunReport must follow Design §8.3 schema: versioned, iteration-based, no events."""

    def test_run_report_has_schema_version_field__tc_event_017(self) -> None:
        """TC-EVENT-017: RunReport.schema_version field exists."""
        from rdetoolkit.report.run_report import RunReport  # noqa: PLC0415

        field_names = {f.name for f in dataclasses.fields(RunReport)}
        assert "schema_version" in field_names, (
            "RunReport must have schema_version per Design §8.1 (破壊変更時にインクリメント)"
        )

    def test_run_report_has_run_id_field__tc_event_018(self) -> None:
        """TC-EVENT-018: RunReport.run_id is a required str field."""
        from rdetoolkit.report.run_report import RunReport  # noqa: PLC0415

        field_names = {f.name for f in dataclasses.fields(RunReport)}
        assert "run_id" in field_names, (
            "RunReport must have run_id — all reports carry the run UUID"
        )
        # Constructing without run_id must fail
        with pytest.raises(TypeError):
            RunReport(schema_version="1", status="success")  # type: ignore[call-arg]

    def test_run_report_has_iterations_field_accepting_empty_list__tc_event_019(
        self,
    ) -> None:
        """TC-EVENT-019: RunReport.iterations exists and accepts an empty list."""
        from rdetoolkit.report.run_report import RunReport  # noqa: PLC0415

        field_names = {f.name for f in dataclasses.fields(RunReport)}
        assert "iterations" in field_names, (
            "RunReport must have iterations: list[...] per Design §8.3"
        )
        r = _make_run_report(iterations=[])
        assert r.iterations == [], "iterations must accept an empty list"

    def test_run_report_has_config_digest_field__tc_event_020(self) -> None:
        """TC-EVENT-020: RunReport.config_digest field exists (str)."""
        from rdetoolkit.report.run_report import RunReport  # noqa: PLC0415

        field_names = {f.name for f in dataclasses.fields(RunReport)}
        assert "config_digest" in field_names, (
            "RunReport must have config_digest: str per Design §8.3"
        )
        r = _make_run_report(config_digest="sha256:abcdef1234")
        assert r.config_digest == "sha256:abcdef1234"

    @pytest.mark.parametrize(
        "status",
        ["success", "partial", "failed"],
        ids=["success", "partial", "failed"],
    )
    def test_run_report_status_field_accepts_canonical_values__tc_event_021(
        self, status: str
    ) -> None:
        """TC-EVENT-021: RunReport.status accepts 'success', 'partial', 'failed'."""
        from rdetoolkit.report.run_report import RunReport  # noqa: PLC0415

        field_names = {f.name for f in dataclasses.fields(RunReport)}
        assert "status" in field_names, "RunReport must have a status field"
        r = _make_run_report(status=status)
        assert r.status == status

    def test_run_report_to_json_includes_schema_version_as_first_key__tc_event_022(
        self,
    ) -> None:
        """TC-EVENT-022: to_json() output contains schema_version (ideally first key)."""
        r = _make_run_report()
        d = json.loads(r.to_json())
        assert "schema_version" in d, (
            f"to_json() output must include 'schema_version'. Keys found: {list(d.keys())}"
        )
        assert d["schema_version"] == "2"
        # schema_version should be the first key in the JSON dict
        first_key = next(iter(d))
        assert first_key == "schema_version", (
            f"schema_version must be the first JSON key (machine-readable version guard). "
            f"First key found: {first_key!r}"
        )

    def test_run_report_does_not_have_events_field__tc_event_023(self) -> None:
        """TC-EVENT-023: RunReport must NOT have an events field — that is Phase D scope.

        Design §8.2: 'RunReport は EventSink から作らない。RunAggregator は Phase D。
        sink は純粋な観測出力であり、File/Memory どちらを選んでもレポートに影響しない。'
        """
        from rdetoolkit.report.run_report import RunReport  # noqa: PLC0415

        field_names = {f.name for f in dataclasses.fields(RunReport)}
        assert "events" not in field_names, (
            f"RunReport must NOT have an 'events: list[Event]' field. "
            f"RunAggregator (Phase D) owns the event collection. "
            f"Current fields: {sorted(field_names)}"
        )
