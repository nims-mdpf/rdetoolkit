"""Tests for rdetoolkit v2 event-stream completeness through a real
Runner.run() (Session D2, TC-EVT-completeness-001/002).

Written before implementation (TDD Red phase).
Target: make all tests pass in codex-worker Green phase.

Design authority: local/develop/v2/Design.md v2.1 §8.1/§8.2.
Session authority: local/develop/v2/tasks/session_d2.md Conflict #7 -- the
node.* event bridge is upgraded from D1-optional (Decision D1-C) to
D2-required: it must be replayed from ExecutionResult.call_records
(NodeCallRecord tuples, seq order) so every observed @node call also becomes
a node.started/node.completed (or node.failed) event.

Pinned ordering contract:
    run.started -> (iteration.started -> node.* -> iteration.completed) x N
    -> run.completed, in that exact order; every event carries a non-empty
    run_id shared by the whole run. A failed tile emits node.failed (never
    node.completed) before its iteration.completed.

Note: report/events.py's Event factories are out of this session's edit
boundary (session_d2.md Boundaries clause) and are frozen as-is;
Event.iteration_completed() carries no status field, so this file does not
assert on iteration.completed's payload content for the failure case --
only on event *ordering*, which is fully observable without editing
events.py.
"""
from __future__ import annotations

import json
from pathlib import Path

from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import IterationInfo


def _build_multidatatile_root(tmp_path: Path, file_count: int) -> Path:
    root = tmp_path / "run_root"
    (root / "inputdata").mkdir(parents=True)
    for i in range(file_count):
        (root / "inputdata" / f"file_{i}.txt").write_text(f"data-{i}", encoding="utf-8")
    (root / "unpacked").mkdir()
    (root / "invoice").mkdir()
    (root / "tasksupport").mkdir()
    (root / "invoice" / "invoice.json").write_text(
        json.dumps(
            {
                "datasetId": "event-fixture",
                "basic": {
                    "dateSubmitted": "2026-07-20",
                    "dataOwnerId": "0" * 56,
                    "dataName": "event-fixture",
                },
            },
        ),
        encoding="utf-8",
    )
    (root / "tasksupport" / "invoice.schema.json").write_text(
        json.dumps({"properties": {}}),
        encoding="utf-8",
    )
    return root


class TestEventStreamCompleteness:
    """TC-EVT-completeness-001: full ordering across a 2-tile successful run."""

    def test_run_started_then_per_tile_node_bridge_then_run_completed__tc_evt_001(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        root = _build_multidatatile_root(tmp_path, 2)
        monkeypatch.chdir(root)

        @node
        def _step(iteration: IterationInfo) -> None:
            return None

        @flow
        def _pipeline(iteration: IterationInfo) -> None:
            _step(iteration)

        sink = MemoryEventSink()
        runner = Runner(
            root=root,
            inputdata_path=root / "inputdata",
            unpacked_dir_path=root / "unpacked",
            event_sink=sink,
        )

        runner.run(_pipeline, system={"extended_mode": "MultiDataTile"})

        names = [event.name for event in sink.events]

        assert names[0] == "run.started"
        assert names[-1] == "run.completed"
        assert names.count("iteration.started") == 2
        assert names.count("iteration.completed") == 2
        assert names.count("node.started") == 2
        assert names.count("node.completed") == 2
        assert "node.failed" not in names

        body = names[1:-1]
        assert body == [
            "iteration.started", "node.started", "node.completed", "iteration.completed",
            "iteration.started", "node.started", "node.completed", "iteration.completed",
        ], f"unexpected per-tile event ordering: {body}"

        assert all(event.run_id for event in sink.events), "every event must carry a non-empty run_id"
        assert len({event.run_id for event in sink.events}) == 1, "all events share one run's run_id"


class TestEventStreamCompletenessOnFailure:
    """TC-EVT-completeness-002: a failed tile emits node.failed then
    iteration.completed, and never node.completed.
    """

    def test_failed_tile_emits_node_failed_before_iteration_completed__tc_evt_002(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        root = _build_multidatatile_root(tmp_path, 1)
        monkeypatch.chdir(root)

        @node
        def _boom(iteration: IterationInfo) -> None:
            msg = "tile boom"
            raise ValueError(msg)

        @flow
        def _failing_pipeline(iteration: IterationInfo) -> None:
            _boom(iteration)

        sink = MemoryEventSink()
        runner = Runner(
            root=root,
            inputdata_path=root / "inputdata",
            unpacked_dir_path=root / "unpacked",
            event_sink=sink,
        )

        runner.run(
            _failing_pipeline,
            system={"extended_mode": "MultiDataTile"},
            execution={"on_iteration_error": "continue"},
        )

        names = [event.name for event in sink.events]

        assert "node.completed" not in names, "a failed tile must never emit node.completed"
        assert "node.failed" in names, "a failed tile's @node call must be bridged as node.failed"
        assert "iteration.completed" in names

        failed_idx = names.index("node.failed")
        completed_idx = names.index("iteration.completed")
        assert failed_idx < completed_idx, "node.failed must precede iteration.completed for the failed tile"

        assert names[0] == "run.started"
        assert names[-1] == "run.completed"
        assert all(event.run_id for event in sink.events)
