"""Tests for ``rdetoolkit.report.graph_render`` (Session E2, TC-GRAPH-UNIT-*).

Written before implementation (TDD Red phase). Target: make all tests pass
in codex-worker Green phase. Authority: local/develop/v2/tasks/session_e2.md
(Current-State Survey's ``node_calls`` shape, Conflicts #1/#2, Known Traps
1/6/7), local/develop/v2/Design.md v2.1 §10 (R2), ADR-022.

Binding API-shape pin (precision standard): ``rdetoolkit.report.graph_render
.render_call_sequence(report: RunReport, format: str = "json") -> str`` is a
pure function -- no filesystem access, no ``rdetoolkit._core`` import. It
renders a **Call Sequence** (call order only, via ``seq``) from
``RunReport.iterations[*].node_calls``. Mermaid uses labeled sequence links
between consecutive calls solely to preserve that recorded order (ADR-022). Supported ``format``
values: ``"json"``, ``"mermaid"``, ``"html"``; any other value raises
``ValueError``.

Pinned ``format="json"`` output shape (this file's contract, since Design.md
only mandates content, not exact JSON keys)::

    {
        "title": "Call Sequence",
        "run_id": <str>,
        "iterations": [
            {
                "index": <int>, "datatile_id": <str>, "status": <str>,
                "node_calls": [
                    {"call_id": ..., "node_id": ..., "seq": ..., "status": ...,
                     "duration_ms": ...},
                    ...
                ],
            },
            ...
        ],
    }

Every fixture ``RunReport`` in this file is hand-built (not produced by a
real run) -- acceptable per session_e2.md's TDD-ENFORCER TEST MANIFEST note:
"hand-built RunReport(...) construction ... is fine for graph/report show
unit-level formatting tests that don't need a real run."
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from rdetoolkit.report.graph_render import render_call_sequence
from rdetoolkit.report.run_report import RunReport

_BANNED_VOCABULARY = ("dataflow", "dag", "edge_confidence", "identity_key", "producer")


def _assert_no_banned_vocabulary(text: str) -> None:
    lowered = text.lower()
    for banned in _BANNED_VOCABULARY:
        assert banned not in lowered, f"ADR-022 violation: forbidden vocabulary {banned!r} found in rendered output"


def _call(call_id: str, node_id: str, seq: int, *, status: str = "success", duration_ms: float = 1.0) -> dict[str, Any]:
    return {"call_id": call_id, "node_id": node_id, "seq": seq, "status": status, "duration_ms": duration_ms}


def _iteration(index: int, node_calls: list[dict[str, Any]], *, status: str = "success", error: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"index": index, "datatile_id": str(index), "status": status, "node_calls": node_calls, "error": error}


def _make_report(iterations: list[dict[str, Any]], **overrides: Any) -> RunReport:
    defaults: dict[str, Any] = {
        "run_id": "graph-render-run-1",
        "status": "success",
        "flow_id": "pkg.mod:pipeline",
        "mode": "invoice",
        "started_at": "2026-01-01T00:00:00Z",
        "duration_ms": 42.0,
        "config_digest": "sha256:abcdef",
        "iterations": iterations,
        "warnings": [],
    }
    defaults.update(overrides)
    return RunReport(**defaults)


def _two_tile_report() -> RunReport:
    """2 tiles, 3 node calls each, tile 0 has a repeated ``node_id`` (two
    ``call_id``s) and a failed call -- covers TC-GRAPH-UNIT-001/002/003/005
    from a single fixture."""
    tile0 = _iteration(
        0,
        [
            _call("c0-reader-1", "reader", 0, status="success", duration_ms=1.0),
            _call("c0-reader-2", "reader", 1, status="success", duration_ms=2.0),
            _call("c0-writer-1", "writer", 2, status="failed", duration_ms=3.0),
        ],
        status="failed",
    )
    tile1 = _iteration(
        1,
        [
            _call("c1-reader-1", "reader", 0, status="success", duration_ms=1.5),
            _call("c1-transform-1", "transform", 1, status="success", duration_ms=2.5),
            _call("c1-writer-1", "writer", 2, status="success", duration_ms=3.5),
        ],
        status="success",
    )
    return _make_report([tile0, tile1], status="partial")


def _all_call_ids(report: RunReport) -> list[str]:
    return [call["call_id"] for iteration in report.iterations for call in iteration["node_calls"]]


class TestRenderCallSequenceJson:
    """TC-GRAPH-UNIT-001: format="json" produces valid, title-bearing JSON."""

    def test_json_output_has_title_per_tile_grouping_and_call_fields__tc_graph_unit_001(self) -> None:
        report = _two_tile_report()

        rendered = render_call_sequence(report, format="json")

        data = json.loads(rendered)
        assert "Call Sequence" in data["title"]
        assert {entry["index"] for entry in data["iterations"]} == {0, 1}
        for entry in data["iterations"]:
            source_iteration = report.iterations[entry["index"]]
            assert len(entry["node_calls"]) == len(source_iteration["node_calls"])
            for call in entry["node_calls"]:
                for field_name in ("call_id", "node_id", "seq", "status", "duration_ms"):
                    assert field_name in call

    def test_json_negative_guard_no_banned_vocabulary(self) -> None:
        rendered = render_call_sequence(_two_tile_report(), format="json")
        _assert_no_banned_vocabulary(rendered)


class TestRenderCallSequenceMermaid:
    """TC-GRAPH-UNIT-002: format="mermaid" is a valid Mermaid diagram
    declaration whose labeled links preserve each tile's recorded order."""

    def test_mermaid_output_links_only_consecutive_calls_per_tile__tc_graph_unit_002(self) -> None:
        report = _two_tile_report()

        rendered = render_call_sequence(report, format="mermaid")

        stripped = rendered.strip()
        assert stripped.startswith(("flowchart", "sequenceDiagram")), "must be a valid Mermaid diagram declaration"
        assert "Call Sequence" in rendered
        for call_id in _all_call_ids(report):
            assert call_id in rendered
        link_lines = [line.strip() for line in rendered.splitlines() if "-->" in line]
        assert link_lines == [
            "call_0_0 -->|seq| call_0_1",
            "call_0_1 -->|seq| call_0_2",
            "call_1_0 -->|seq| call_1_1",
            "call_1_1 -->|seq| call_1_2",
        ]
        assert all("-->|seq|" in line for line in link_lines)
        _assert_no_banned_vocabulary(rendered)

    def test_mermaid_negative_guard_no_banned_vocabulary(self) -> None:
        rendered = render_call_sequence(_two_tile_report(), format="mermaid")
        _assert_no_banned_vocabulary(rendered)


class TestRenderCallSequenceHtml:
    """TC-GRAPH-UNIT-003: format="html" is self-contained, titled, and
    contains every call_id."""

    def test_html_output_is_self_contained_titled_and_lists_all_calls__tc_graph_unit_003(self) -> None:
        report = _two_tile_report()

        rendered = render_call_sequence(report, format="html")

        assert "Call Sequence" in rendered
        for call_id in _all_call_ids(report):
            assert call_id in rendered
        lowered = rendered.lower()
        assert 'src="http' not in lowered
        assert 'href="http' not in lowered
        assert "src='http" not in lowered
        assert "href='http" not in lowered

    def test_html_negative_guard_no_banned_vocabulary(self) -> None:
        rendered = render_call_sequence(_two_tile_report(), format="html")
        _assert_no_banned_vocabulary(rendered)


class TestRenderCallSequenceEmptyNodeCalls:
    """TC-GRAPH-UNIT-004: a tile with ``node_calls == []`` (matching
    a failed ``ExecutionResult`` summary's real output shape, Known Trap 1)
    renders without raising in all three formats, showing the tile as
    present but empty."""

    @pytest.fixture
    def report_with_empty_tile(self) -> RunReport:
        empty_tile = _iteration(0, [], status="failed", error={"code": 3001, "message": "boom"})
        populated_tile = _iteration(1, [_call("c1-only", "solo", 0)])
        return _make_report([empty_tile, populated_tile], status="partial")

    @pytest.mark.parametrize("fmt", ["json", "mermaid", "html"])
    def test_empty_node_calls_tile_renders_without_raising__tc_graph_unit_004(
        self,
        report_with_empty_tile: RunReport,
        fmt: str,
    ) -> None:
        rendered = render_call_sequence(report_with_empty_tile, format=fmt)

        assert rendered  # must not raise, must produce non-empty output

    def test_empty_tile_present_with_zero_calls_in_json__tc_graph_unit_004_json_detail(
        self,
        report_with_empty_tile: RunReport,
    ) -> None:
        rendered = render_call_sequence(report_with_empty_tile, format="json")

        data = json.loads(rendered)
        empty_entry = next(entry for entry in data["iterations"] if entry["index"] == 0)
        assert empty_entry["node_calls"] == []


class TestRenderCallSequenceRepeatedNodeId:
    """TC-GRAPH-UNIT-005: a node called twice in the same tile (shared
    ``node_id``, distinct ``call_id``s) renders as two distinct entries in
    all three formats -- never merged into one."""

    @pytest.mark.parametrize("fmt", ["json", "mermaid", "html"])
    def test_repeated_node_id_appears_as_two_distinct_call_ids__tc_graph_unit_005(self, fmt: str) -> None:
        report = _two_tile_report()

        rendered = render_call_sequence(report, format=fmt)

        assert "c0-reader-1" in rendered
        assert "c0-reader-2" in rendered
        if fmt == "json":
            data = json.loads(rendered)
            tile0 = next(entry for entry in data["iterations"] if entry["index"] == 0)
            call_ids = [call["call_id"] for call in tile0["node_calls"]]
            assert call_ids.count("c0-reader-1") == 1
            assert call_ids.count("c0-reader-2") == 1


class TestRenderCallSequenceUnknownFormat:
    """Bonus guard (not a numbered TC): an unrecognized format raises
    ValueError so ``graph_cmd.py`` can translate it into exit code 3."""

    def test_unknown_format_raises_value_error(self) -> None:
        report = _two_tile_report()

        with pytest.raises(ValueError, match="format"):
            render_call_sequence(report, format="svg")
