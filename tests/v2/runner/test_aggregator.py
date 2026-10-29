"""Tests for rdetoolkit v2 RunAggregator (Session D2, TC-AGG-001..005).

Written before implementation (TDD Red phase).
Target: make all tests pass in codex-worker Green phase.

Design authority: local/develop/v2/Design.md v2.1 §7.4 (aggregation --
superseded in part by decisions_pre_D.md, see session_d2.md Conflict #1),
§8.2 (EventSink/RunReport separation).
Session authority: local/develop/v2/tasks/session_d2.md ("runner/aggregator.py",
D2.3/D2.4/D2.5).

Pinned API surface (established by this test file -- Design.md leaves the
concrete class shape to this session):

    class RunAggregator:
        def __init__(
            self, *, run_id: str, flow_id: str, mode: str,
            config_digest: str, logs_dir: Path,
        ) -> None: ...

        def record(self, result: ExecutionResult) -> None:
            '''Record one completed/failed tile. Streams the full detail to
            logs_dir/"iterations"/f"iteration_{result.iteration_index}.json"
            immediately; only a lightweight summary dict is kept in
            .iterations (D2.5).'''

        iterations: list[dict[str, Any]]  # summaries only, in record() order

        def build_report(
            self, *, status: str, started_at: str, duration_ms: float,
            warnings: list[dict[str, Any]] | None = None,
            error: dict[str, Any] | None = None,
        ) -> RunReport: ...

Streaming contract (D2.5): record() writes
logs_dir/"iterations"/f"iteration_{n}.json" before returning -- never
batched until build_report() is called, and never waiting for later tiles.

EventSink independence (D2.3, Design §8.2): RunAggregator's constructor and
methods never take an EventSink; a RunReport built from a given
ExecutionResult sequence is a pure function of that sequence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rdetoolkit.core.calllog import NodeCallRecord, TypeSummary
from rdetoolkit.runner.execute import ExecutionResult

# Target import — fails until implementation exists (expected in Red phase):
# from rdetoolkit.runner.aggregator import RunAggregator


def _completed_result(index: int, *, output_count: int = 1) -> ExecutionResult:
    return ExecutionResult(
        iteration_index=index,
        status="completed",
        call_records=(),
        outputs=tuple(TypeSummary(type_name="NoneType", repr_head=None) for _ in range(output_count)),
        error=None,
        datatile_id=f"tile_{index}",
    )


def _dummy_call_record(seq: int) -> NodeCallRecord:
    return NodeCallRecord(
        call_id=f"node#{seq}",
        node_id="node",
        parent_flow="flow",
        seq=seq,
        iteration_index=0,
        started_at="2026-07-10T00:00:00",
        duration_ms=0.1,
        status="completed",
        inputs={},
        outputs=(),
        error=None,
    )


class TestRunAggregatorBuildsReport:
    """TC-AGG-001: RunAggregator builds RunReport from a sequence of ExecutionResult."""

    def test_build_report_from_execution_results__tc_agg_001(self, tmp_path: Path) -> None:
        from rdetoolkit.runner.aggregator import RunAggregator  # noqa: PLC0415

        aggregator = RunAggregator(
            run_id="run-agg-1",
            flow_id="mymod.myflow",
            mode="multidatatile",
            config_digest="sha256:deadbeef",
            logs_dir=tmp_path / "data" / "logs",
        )
        aggregator.record(_completed_result(0))
        aggregator.record(_completed_result(1))

        report = aggregator.build_report(status="success", started_at="2026-07-10T00:00:00", duration_ms=12.5)

        assert report.run_id == "run-agg-1"
        assert report.flow_id == "mymod.myflow"
        assert report.mode == "multidatatile"
        assert report.status == "success"
        assert report.config_digest == "sha256:deadbeef"
        assert len(report.iterations) == 2
        assert {entry["index"] for entry in report.iterations} == {0, 1}
        assert {entry["datatile_id"] for entry in report.iterations} == {"tile_0", "tile_1"}
        assert all(
            set(entry)
            == {
                "index",
                "datatile_id",
                "status",
                "node_calls",
                "error",
                "title",
                "target",
                "stacktrace",
            }
            for entry in report.iterations
        )


class TestRunAggregatorEventSinkIndependence:
    """TC-AGG-002: RunReport construction never depends on EventSink (Design §8.2)."""

    def test_constructor_has_no_event_sink_parameter__tc_agg_002a(self) -> None:
        """RunAggregator must not accept an event_sink; it is built purely
        from ExecutionResult objects (Design §8.2 separation).
        """
        import inspect  # noqa: PLC0415

        from rdetoolkit.runner.aggregator import RunAggregator  # noqa: PLC0415

        params = inspect.signature(RunAggregator.__init__).parameters
        assert "event_sink" not in params, "RunAggregator must be independent of EventSink (Design §8.2)"

    def test_report_is_pure_function_of_execution_results__tc_agg_002b(self, tmp_path: Path) -> None:
        """Two RunAggregator instances fed the identical ExecutionResult
        sequence -- with no EventSink involved anywhere -- must produce
        identical RunReport.iterations: the aggregator's only input is the
        ExecutionResult sequence (Design §8.2 separation from EventSink).
        """
        from rdetoolkit.runner.aggregator import RunAggregator  # noqa: PLC0415

        results = [_completed_result(0), _completed_result(1, output_count=2)]

        def _run(tag: str) -> Any:
            aggregator = RunAggregator(
                run_id="run-x",
                flow_id="f",
                mode="invoice",
                config_digest="sha256:aaa",
                logs_dir=tmp_path / tag / "data" / "logs",
            )
            for result in results:
                aggregator.record(result)
            return aggregator.build_report(status="success", started_at="t", duration_ms=1.0)

        report_1 = _run("first")
        report_2 = _run("second")

        assert report_1.iterations == report_2.iterations


class TestRunAggregatorStreaming:
    """TC-AGG-003: per-tile results stream to logs/iterations/iteration_{n}.json
    as each tile completes (D2.5), not batched at build_report() time.
    """

    def test_iteration_file_exists_immediately_after_record__tc_agg_003(self, tmp_path: Path) -> None:
        from rdetoolkit.runner.aggregator import RunAggregator  # noqa: PLC0415

        logs_dir = tmp_path / "data" / "logs"
        aggregator = RunAggregator(
            run_id="run-stream",
            flow_id="f",
            mode="multidatatile",
            config_digest="sha256:aaa",
            logs_dir=logs_dir,
        )

        for index in range(5):
            aggregator.record(_completed_result(index))
            iteration_file = logs_dir / "iterations" / f"iteration_{index}.json"
            assert iteration_file.exists(), f"iteration_{index}.json must exist immediately after record(), before build_report() and before later tiles are processed"
            payload = json.loads(iteration_file.read_text(encoding="utf-8"))
            assert payload["iteration_index"] == index
            for future_index in range(index + 1, 5):
                future_file = logs_dir / "iterations" / f"iteration_{future_index}.json"
                assert not future_file.exists(), "not-yet-recorded tiles must not have a file yet"


class TestRunAggregatorMemorySummaryOnly:
    """TC-AGG-004: in-memory iterations hold only lightweight summaries, not
    full call_records/outputs detail (proxy metric per session_d2.md).
    """

    def test_in_memory_summary_excludes_call_records_detail__tc_agg_004(self, tmp_path: Path) -> None:
        from rdetoolkit.runner.aggregator import RunAggregator  # noqa: PLC0415

        logs_dir = tmp_path / "data" / "logs"
        aggregator = RunAggregator(
            run_id="run-mem",
            flow_id="f",
            mode="multidatatile",
            config_digest="sha256:aaa",
            logs_dir=logs_dir,
        )

        heavy_result = ExecutionResult(
            iteration_index=0,
            status="completed",
            call_records=tuple(_dummy_call_record(i) for i in range(500)),
            outputs=tuple(TypeSummary(type_name="int", repr_head=str(i)) for i in range(500)),
            error=None,
            datatile_id="heavy",
        )
        aggregator.record(heavy_result)

        summary = aggregator.iterations[0]
        assert "call_records" not in summary, "full call_records must not be retained in the in-memory summary"
        assert "outputs" not in summary, "full outputs detail must not be retained in the in-memory summary"
        assert len(summary["node_calls"]) == 500
        assert all(set(call) == {"call_id", "node_id", "seq", "status", "duration_ms"} for call in summary["node_calls"])


class TestRunAggregatorOutputsPassthrough:
    """TC-AGG-005: ExecutionResult.outputs (flow-return TypeSummary) flows
    into RunReport.iterations[*] unchanged -- no terminal-node inference is
    implemented (regression guard against reintroducing lineage/edges,
    session_d2.md Conflict #1 / ADR-022).
    """

    def test_outputs_count_matches_execution_result_exactly__tc_agg_005(self, tmp_path: Path) -> None:
        from rdetoolkit.runner.aggregator import RunAggregator  # noqa: PLC0415

        aggregator = RunAggregator(
            run_id="run-out",
            flow_id="f",
            mode="invoice",
            config_digest="sha256:aaa",
            logs_dir=tmp_path / "data" / "logs",
        )
        result = _completed_result(0, output_count=3)
        aggregator.record(result)

        payload = json.loads((tmp_path / "data" / "logs" / "iterations" / "iteration_0.json").read_text(encoding="utf-8"))
        assert len(payload["outputs"]) == 3, "the streamed primary result must preserve ExecutionResult.outputs without terminal-node inference (Conflict #1, ADR-022)"
