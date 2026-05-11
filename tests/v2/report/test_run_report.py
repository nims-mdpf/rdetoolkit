"""Tests for Phase 2.1: RunReport structure and serialization.

EP Table:
| API                       | Partition               | Rationale           | Expected                       | Test ID    |
|---------------------------|-------------------------|---------------------|--------------------------------|------------|
| RunReport()               | valid fields            | normal construction | all fields accessible          | TC-EP-001  |
| RunReport.to_json         | serialize               | JSON output         | valid JSON string              | TC-EP-002  |
| RunReport.from_json       | deserialize             | round-trip          | same content as original       | TC-EP-003  |
| RunReport.success_count   | mixed results           | aggregation         | counts only successes          | TC-EP-004  |
| RunReport.failure_count   | mixed results           | aggregation         | counts only failures           | TC-EP-005  |
| RunReport.to_json         | with events             | event serialization | events included in JSON        | TC-EP-006  |

BV Table:
| API                       | Boundary                | Rationale           | Expected                       | Test ID    |
|---------------------------|-------------------------|---------------------|--------------------------------|------------|
| RunReport()               | no node results         | empty run           | counts are 0                   | TC-BV-001  |
| RunReport()               | all successes           | no failures         | failure_count == 0             | TC-BV-002  |
| RunReport()               | all failures            | no successes        | success_count == 0             | TC-BV-003  |
"""

from __future__ import annotations

import json

import pytest

from rdetoolkit.report.events import Event
from rdetoolkit.report.run_report import NodeResult, RunReport


class TestRunReport:
    """Tests for the RunReport dataclass."""

    def test_construction__tc_ep_001(self) -> None:
        """TC-EP-001: RunReport can be constructed with all fields."""
        # Given: valid fields
        results = [
            NodeResult(node_id="a", status="success", duration=1.0),
            NodeResult(node_id="b", status="failed", duration=0.5, error="oops"),
        ]
        # When: constructing a RunReport
        report = RunReport(
            phase="execute",
            node_results=results,
            duration=1.5,
            events=[],
        )
        # Then: all fields accessible
        assert report.phase == "execute"
        assert len(report.node_results) == 2
        assert report.duration == 1.5
        assert report.events == []

    def test_to_json__tc_ep_002(self) -> None:
        """TC-EP-002: RunReport serializes to valid JSON."""
        # Given: a RunReport
        report = RunReport(
            phase="execute",
            node_results=[
                NodeResult(node_id="a", status="success", duration=1.0),
            ],
            duration=1.0,
            events=[],
        )
        # When: serializing to JSON
        json_str = report.to_json()
        # Then: it is valid JSON with expected fields
        data = json.loads(json_str)
        assert data["phase"] == "execute"
        assert len(data["node_results"]) == 1
        assert data["node_results"][0]["node_id"] == "a"
        assert data["duration"] == 1.0

    def test_round_trip__tc_ep_003(self) -> None:
        """TC-EP-003: JSON round-trip preserves content."""
        # Given: a RunReport
        original = RunReport(
            phase="execute",
            node_results=[
                NodeResult(node_id="a", status="success", duration=1.0),
                NodeResult(node_id="b", status="failed", duration=0.5, error="err"),
            ],
            duration=1.5,
            events=[
                Event(node_id="a", kind="node_started", timestamp=100.0, payload={}),
            ],
        )
        # When: round-tripping through JSON
        json_str = original.to_json()
        restored = RunReport.from_json(json_str)
        # Then: content is identical
        assert restored.phase == original.phase
        assert restored.duration == original.duration
        assert len(restored.node_results) == len(original.node_results)
        for orig_nr, rest_nr in zip(
            original.node_results, restored.node_results, strict=True,
        ):
            assert rest_nr.node_id == orig_nr.node_id
            assert rest_nr.status == orig_nr.status
            assert rest_nr.duration == orig_nr.duration
            assert rest_nr.error == orig_nr.error
        assert len(restored.events) == len(original.events)
        assert restored.events[0].node_id == original.events[0].node_id
        assert restored.events[0].kind == original.events[0].kind

    def test_success_count__tc_ep_004(self) -> None:
        """TC-EP-004: success_count counts only successful nodes."""
        # Given: mixed results
        report = RunReport(
            phase="execute",
            node_results=[
                NodeResult(node_id="a", status="success", duration=1.0),
                NodeResult(node_id="b", status="failed", duration=0.5, error="err"),
                NodeResult(node_id="c", status="success", duration=0.8),
            ],
            duration=2.3,
            events=[],
        )
        # When/Then: counting successes
        assert report.success_count == 2

    def test_failure_count__tc_ep_005(self) -> None:
        """TC-EP-005: failure_count counts only failed nodes."""
        # Given: mixed results
        report = RunReport(
            phase="execute",
            node_results=[
                NodeResult(node_id="a", status="success", duration=1.0),
                NodeResult(node_id="b", status="failed", duration=0.5, error="err"),
                NodeResult(node_id="c", status="failed", duration=0.3, error="err2"),
            ],
            duration=1.8,
            events=[],
        )
        # When/Then: counting failures
        assert report.failure_count == 2

    def test_to_json_includes_events__tc_ep_006(self) -> None:
        """TC-EP-006: Serialized JSON includes events."""
        # Given: report with events
        report = RunReport(
            phase="execute",
            node_results=[],
            duration=0.0,
            events=[
                Event(node_id="a", kind="node_started", timestamp=1.0, payload={}),
                Event(node_id="a", kind="node_finished", timestamp=2.0, payload={"duration": 1.0}),
            ],
        )
        # When: serializing
        data = json.loads(report.to_json())
        # Then: events are present
        assert len(data["events"]) == 2
        assert data["events"][0]["kind"] == "node_started"
        assert data["events"][1]["payload"]["duration"] == 1.0

    def test_empty_results__tc_bv_001(self) -> None:
        """TC-BV-001: RunReport with no node results has zero counts."""
        # Given/When: empty report
        report = RunReport(phase="execute", node_results=[], duration=0.0, events=[])
        # Then: counts are zero
        assert report.success_count == 0
        assert report.failure_count == 0

    def test_all_successes__tc_bv_002(self) -> None:
        """TC-BV-002: All successes means failure_count == 0."""
        # Given: all successful
        report = RunReport(
            phase="execute",
            node_results=[
                NodeResult(node_id="a", status="success", duration=1.0),
                NodeResult(node_id="b", status="success", duration=1.0),
            ],
            duration=2.0,
            events=[],
        )
        # Then:
        assert report.success_count == 2
        assert report.failure_count == 0

    def test_all_failures__tc_bv_003(self) -> None:
        """TC-BV-003: All failures means success_count == 0."""
        # Given: all failed
        report = RunReport(
            phase="execute",
            node_results=[
                NodeResult(node_id="a", status="failed", duration=0.5, error="e1"),
                NodeResult(node_id="b", status="failed", duration=0.3, error="e2"),
            ],
            duration=0.8,
            events=[],
        )
        # Then:
        assert report.success_count == 0
        assert report.failure_count == 2

    def test_skip_count__new(self) -> None:
        """NEW: skip_count counts only skipped nodes."""
        # Given: mixed results including skipped
        report = RunReport(
            phase="execute",
            node_results=[
                NodeResult(node_id="a", status="success", duration=1.0),
                NodeResult(node_id="b", status="failed", duration=0.5, error="err"),
                NodeResult(node_id="c", status="skipped", duration=0.0),
                NodeResult(node_id="d", status="skipped", duration=0.0),
            ],
            duration=1.5,
            events=[],
        )
        # When/Then: counting skipped
        assert report.success_count == 1
        assert report.failure_count == 1
        assert report.skip_count == 2

    def test_mixed_counts_independent__new(self) -> None:
        """NEW: success/failed/skipped counts are independent."""
        # Given: mixed list
        report = RunReport(
            phase="execute",
            node_results=[
                NodeResult(node_id="a", status="success", duration=1.0),
                NodeResult(node_id="b", status="failed", duration=0.5, error="e"),
                NodeResult(node_id="c", status="skipped", duration=0.0),
            ],
            duration=1.5,
            events=[],
        )
        # Then: three counts are independent
        assert report.success_count == 1
        assert report.failure_count == 1
        assert report.skip_count == 1
        assert (
            report.success_count + report.failure_count + report.skip_count
            == len(report.node_results)
        )
