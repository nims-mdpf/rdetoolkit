"""Integration-level tests for per-tile streaming during a real Runner.iterate()
run (Session D2, companion to test_aggregator.py's unit-level TC-AGG-003/004).

Written before implementation (TDD Red phase).
Target: make all tests pass in codex-worker Green phase.

Design authority: local/develop/v2/Design.md v2.1 §7.4 ("sequential write to
disk", "memory holds only summaries").
Session authority: local/develop/v2/tasks/session_d2.md D2.5.

test_aggregator.py proves RunAggregator streams and stays lightweight at the
unit level (calling .record() directly). This file proves the same
observable behavior end-to-end through the real Runner.iterate() loop, i.e.
that lifecycle.py actually wires the aggregator in rather than batching
results itself.
"""

from __future__ import annotations

import json
from pathlib import Path

from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import IterationInfo, RdeConfig


def _build_multidatatile_root(tmp_path: Path, file_count: int) -> Path:
    """Build an alias-flat root: the marker directories sit directly below it.

    ``resolve_data_root`` therefore answers ``root`` itself, and the Runner
    streams to ``root/logs/iterations`` (Session I-REVIEW-A ruling #1); before
    that ruling the invoice side used ``root`` while the outputs used
    ``root/data``, splitting one run across two roots.
    """
    root = tmp_path / "run_root"
    (root / "inputdata").mkdir(parents=True)
    for i in range(file_count):
        (root / "inputdata" / f"file_{i}.txt").write_text(f"data-{i}", encoding="utf-8")
    (root / "unpacked").mkdir()
    (root / "invoice").mkdir()
    (root / "tasksupport").mkdir()
    return root


class TestPerTileStreamingDuringRealRun:
    """TC-STREAM-001: logs/iterations/iteration_{n}.json is written for tile
    N before tile N+1's flow call begins.
    """

    def test_iteration_file_exists_before_next_tile_flow_call__tc_stream_001(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """A 6-tile run must have logs/iterations/iteration_{n-1}.json on
        disk by the time tile n's flow starts (proves per-tile streaming
        inside the real Runner.iterate() loop, not batching at the end).
        """
        tile_count = 6
        root = _build_multidatatile_root(tmp_path, tile_count)
        monkeypatch.chdir(root)

        observed_before_start: dict[int, bool] = {}

        @node
        def _observe(iteration: IterationInfo) -> None:
            if iteration.index > 0:
                previous_file = root / "logs" / "iterations" / f"iteration_{iteration.index - 1}.json"
                observed_before_start[iteration.index] = previous_file.exists()

        @flow
        def _observing_flow(iteration: IterationInfo) -> None:
            _observe(iteration)

        runner = Runner(root=root, inputdata_path=root / "inputdata", unpacked_dir_path=root / "unpacked")
        runner.run_id = "test-stream-001"
        config = RdeConfig(execution={"on_iteration_error": "continue"})

        runner.iterate(_observing_flow, ModeKind.multidatatile, config)

        assert len(observed_before_start) == tile_count - 1
        assert all(observed_before_start.values()), "each tile's predecessor iteration_{n-1}.json must already exist before this tile's flow call starts -- streaming must not batch until the run finishes"


class TestManyTilesMemorySummaryOnly:
    """TC-STREAM-002: a large tile count must not accumulate full call-record
    detail in the RunReport returned by a real Runner.iterate() run.
    """

    def test_large_tile_count_memory_summary_only__tc_stream_002(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Runner.iterate()'s returned RunReport.iterations entries stay
        lightweight (no full call_records/outputs detail) regardless of
        per-tile output volume (session_d2.md TC-AGG-004's proxy metric,
        exercised end-to-end).
        """
        tile_count = 25
        root = _build_multidatatile_root(tmp_path, tile_count)
        monkeypatch.chdir(root)

        @node
        def _wide_output(iteration: IterationInfo) -> tuple[int, ...]:
            return tuple(range(50))

        @flow
        def _wide_flow(iteration: IterationInfo) -> tuple[int, ...]:
            return _wide_output(iteration)

        runner = Runner(root=root, inputdata_path=root / "inputdata", unpacked_dir_path=root / "unpacked")
        runner.run_id = "test-stream-002"
        config = RdeConfig(execution={"on_iteration_error": "continue"})

        report = runner.iterate(_wide_flow, ModeKind.multidatatile, config)

        assert len(report.iterations) == tile_count
        for entry in report.iterations:
            assert "call_records" not in entry
            assert "outputs" not in entry


class TestFailedTileCallLogStreaming:
    """Review-response preservation of recorder primary state (Design §8.2)."""

    def test_failed_node_record_reaches_stream_and_report__tc_d2r_f4(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """TC-D2R-F4: a failed node remains visible in both iteration outputs."""
        # Given: one tile whose decorated node fails after recording begins
        root = _build_multidatatile_root(tmp_path, 1)
        monkeypatch.chdir(root)

        @node(id="tc_d2r_f4_failed_node")
        def _fail() -> None:
            msg = "intentional failure"
            raise ValueError(msg)

        @flow
        def _pipeline() -> None:
            _fail()

        runner = Runner(root=root, inputdata_path=root / "inputdata", unpacked_dir_path=root / "unpacked")
        runner.run_id = "tc-d2r-f4"

        # When: executing with the continue error policy
        report = runner.iterate(_pipeline, ModeKind.multidatatile, RdeConfig())

        # Then: recorder snapshots, not EventSink reconstruction, supply both views
        streamed = json.loads((root / "logs" / "iterations" / "iteration_0.json").read_text(encoding="utf-8"))
        assert streamed["call_records"][0]["node_id"] == "tc_d2r_f4_failed_node"
        assert streamed["call_records"][0]["status"] == "failed"
        assert report.iterations[0]["node_calls"][0]["node_id"] == "tc_d2r_f4_failed_node"
        assert report.iterations[0]["node_calls"][0]["status"] == "failed"


class TestCanonicalIterationSummary:
    """Literal RunReport iteration schema from Design §8.3."""

    def test_iteration_summary_has_exact_canonical_shape__tc_d2r_f5(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """TC-D2R-F5: summaries use exact keys, deterministic id, and node arrays."""
        # Given: one named raw file and one successful node call
        root = _build_multidatatile_root(tmp_path, 1)
        monkeypatch.chdir(root)

        @node(id="tc_d2r_f5_node")
        def _noop() -> None:
            return None

        @flow
        def _pipeline() -> None:
            _noop()

        runner = Runner(root=root, inputdata_path=root / "inputdata", unpacked_dir_path=root / "unpacked")
        runner.run_id = "tc-d2r-f5"

        # When: building the report from the primary execution result
        report = runner.iterate(_pipeline, ModeKind.multidatatile, RdeConfig())

        # Then: §8.3 is literal, with first-rawfile stem as deterministic id
        summary = report.iterations[0]
        assert set(summary) == {
            "index",
            "datatile_id",
            "status",
            "node_calls",
            "error",
            "title",
            "target",
            "stacktrace",
        }
        assert summary["index"] == 0
        assert summary["datatile_id"] == "file_0"
        assert summary["status"] == "completed"
        assert summary["error"] is None
        assert set(summary["node_calls"][0]) == {
            "call_id",
            "node_id",
            "seq",
            "status",
            "duration_ms",
        }
