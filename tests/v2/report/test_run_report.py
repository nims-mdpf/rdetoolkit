"""Tests for the canonical v2 RunReport schema.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``to_legacy_statuses`` | non-integer index | preserve explicit value | TC-EP-HR2-A-002 |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| ``to_legacy_statuses`` | missing index | empty run_id fallback | TC-BV-HR2-A-002 |
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any

import pytest

from rdetoolkit.report.run_report import RunReport


def _make_report(**overrides: Any) -> RunReport:
    """Build a minimal canonical RunReport for tests."""
    defaults: dict[str, Any] = {
        "run_id": "run-1",
        "status": "success",
        "flow_id": "pkg.mod:pipeline",
        "mode": "invoice",
        "started_at": "2026-01-01T00:00:00Z",
        "duration_ms": 12.3,
        "config_digest": "sha256:abcdef",
        "iterations": [],
        "warnings": [],
    }
    defaults.update(overrides)
    return RunReport(**defaults)


class TestRunReport:
    """Tests for the RunReport dataclass."""

    def test_construction__tc_ep_001(self) -> None:
        """TC-EP-001: RunReport can be constructed with all canonical fields."""
        # Given: valid canonical fields
        iterations = [{"index": 0, "status": "success"}]
        warnings = [{"code": 1001, "message": "mode overridden"}]
        # When: constructing a RunReport
        report = _make_report(iterations=iterations, warnings=warnings)
        # Then: all fields are accessible
        assert report.schema_version == "2"
        assert report.run_id == "run-1"
        assert report.status == "success"
        assert report.flow_id == "pkg.mod:pipeline"
        assert report.mode == "invoice"
        assert report.duration_ms == 12.3
        assert report.config_digest == "sha256:abcdef"
        assert report.iterations == iterations
        assert report.warnings == warnings
        assert report.error is None

    def test_to_json__tc_ep_002(self) -> None:
        """TC-EP-002: RunReport serializes to valid canonical JSON."""
        # Given: a RunReport
        report = _make_report()
        # When: serializing to JSON
        json_str = report.to_json()
        # Then: it is valid JSON with schema_version first
        data = json.loads(json_str)
        assert next(iter(data)) == "schema_version"
        assert data["schema_version"] == "2"
        assert data["run_id"] == "run-1"
        assert data["iterations"] == []

    def test_round_trip__tc_ep_003(self) -> None:
        """TC-EP-003: JSON round-trip preserves canonical content."""
        # Given: a RunReport with warning and error details
        original = _make_report(
            status="failed",
            iterations=[{"index": 0, "status": "failed"}],
            warnings=[{"code": 1001, "message": "warn"}],
            error={"code": 3001, "message": "failed"},
        )
        # When: round-tripping through JSON
        restored = RunReport.from_json(original.to_json())
        # Then: content is identical
        assert restored == original

    @pytest.mark.parametrize(
        "status",
        ["success", "partial", "failed"],
        ids=["success", "partial", "failed"],
    )
    def test_status_accepts_canonical_values__tc_ep_004(self, status: str) -> None:
        """TC-EP-004: status can represent success, partial, and failed outcomes."""
        # Given/When: a report with a canonical status
        report = _make_report(status=status)
        # Then: status is preserved
        assert report.status == status

    def test_empty_iterations__tc_bv_001(self) -> None:
        """TC-BV-001: RunReport accepts an empty iterations list."""
        # Given/When: a report with no iterations
        report = _make_report(iterations=[])
        # Then: the list is preserved
        assert report.iterations == []

    def test_error_none_for_success__tc_bv_002(self) -> None:
        """TC-BV-002: Successful reports may omit an error."""
        # Given/When: a successful report
        report = _make_report(status="success")
        # Then: error is None
        assert report.error is None

    def test_failed_report_accepts_error_dict__tc_bv_003(self) -> None:
        """TC-BV-003: Failed reports can carry an error dict."""
        # Given/When: a failed report
        report = _make_report(status="failed", error={"code": 3001, "message": "boom"})
        # Then: error details are preserved
        assert report.error == {"code": 3001, "message": "boom"}

    @pytest.mark.parametrize(
        ("iteration", "expected"),
        [
            pytest.param({"status": "completed"}, "", id="missing"),
            pytest.param({"index": "tile-x", "status": "completed"}, "tile-x", id="non-integer"),
        ],
    )
    def test_legacy_run_id_has_total_fallback__tc_ep_bv_hr2_a_002(
        self,
        iteration: dict[str, Any],
        expected: str,
    ) -> None:
        """TC-EP/BV-HR2-A-002: malformed iteration indexes have explicit fallbacks."""
        # Given: a report with an iteration index outside the canonical integer shape
        report = _make_report(iterations=[iteration])

        # When: converting through the total legacy compatibility helper
        status = json.loads(report.to_legacy_statuses())["statuses"][0]

        # Then: missing is empty and an explicit non-integer value remains inspectable
        assert status["run_id"] == expected

    def test_no_events_field(self) -> None:
        """RunReport does not carry EventSink output in A2."""
        # Given: RunReport dataclass fields
        field_names = {field.name for field in dataclasses.fields(RunReport)}
        # Then: events is absent because aggregation is Phase D scope
        assert "events" not in field_names
