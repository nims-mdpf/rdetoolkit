"""A strict return-type mismatch must keep the executed node's record (RC1 F06).

Review ``interrogate_v2.0.0rc1`` F06: ``CallLogRecorder.call_node`` checked
the return value outside the failure-record boundary, so a node whose body
had already run (and had side effects) vanished from the call log: the tile
error carried ``call_id="unknown"`` and no node event was emitted.

An argument mismatch is different on purpose: it is detected before the body
runs, so there is no executed call to record and the log stays empty.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-RC1-F06-EP-001 | strict return mismatch | ``-> int`` returning ``"s"`` | 3002 + one failed record |
| TC-RC1-F06-EP-002 | tile boundary | same node inside a flow (run_tile) | error call_id = record call_id, node.failed emitted |
| TC-RC1-F06-EP-003 | Runner | same flow through ``Runner.run`` | report error call_id = record call_id |
| TC-RC1-F06-EP-004 | nesting | mismatch in an inner node | inner and outer both failed, unique seq |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-RC1-F06-NEG-001 | argument mismatch | strict, wrong argument | 3002, body not run, no record |
| TC-RC1-F06-NEG-002 | warn return mismatch | ``-> int`` returning ``"s"`` | warning, completed record |
| TC-RC1-F06-NEG-003 | matching return | ``-> int`` returning 1 | completed record with outputs |
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rdetoolkit import flow
from rdetoolkit.core.calllog import CallLogRecorder
from rdetoolkit.core.context import RunContext
from rdetoolkit.core.node import node
from rdetoolkit.errors import RdeExecutionError
from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.runner.execute import TileExecutionError, run_tile
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import IterationInfo, RdeConfig

_SIDE_EFFECTS: list[str] = []
_WRONG_RETURN_ID = "tests.v2.core.rc1_f06.wrong_return"


@node(id=_WRONG_RETURN_ID)
def wrong_return(label: str) -> int:
    _SIDE_EFFECTS.append(label)
    return label  # type: ignore[return-value]


@node(id="tests.v2.core.rc1_f06.right_return")
def right_return(value: int) -> int:
    return value


@node(id="tests.v2.core.rc1_f06.outer")
def outer(label: str) -> int:
    return wrong_return(label)


@flow(id="tests.v2.core.rc1_f06.flow")
def wrong_return_flow() -> int:
    return wrong_return("flow")


@pytest.fixture(autouse=True)
def _reset_side_effects() -> None:
    _SIDE_EFFECTS.clear()


class TestRecorderKeepsTheFailedCall:
    def test_return_mismatch_appends_one_failed_record__tc_rc1_f06_ep_001(self) -> None:
        # Given: strict recording and a node lying about its return type
        with CallLogRecorder(type_check="strict") as recorder:
            # When: the node runs and its return value is checked
            with pytest.raises(RdeExecutionError) as exc_info:
                wrong_return("s")

        # Then: the 3002 is raised after the body ran, and the call is recorded as failed
        error = exc_info.value
        assert error.code == 3002
        assert _SIDE_EFFECTS == ["s"]
        records = recorder.records
        assert len(records) == 1
        record = records[0]
        assert record.status == "failed"
        assert record.node_id == _WRONG_RETURN_ID
        assert record.call_id == f"{_WRONG_RETURN_ID}#1"
        assert record.seq == 1
        assert record.outputs == ()
        assert record.error == {"type": "RdeExecutionError", "message": str(error)}
        assert set(record.inputs) == {"label"}
        assert record.duration_ms >= 0

    def test_nested_return_mismatch_records_both_calls__tc_rc1_f06_ep_004(self) -> None:
        # Given: an outer node calling the lying node
        with CallLogRecorder(type_check="strict") as recorder:
            # When: the inner return check fails
            with pytest.raises(RdeExecutionError):
                outer("nested")

        # Then: inner and outer are both failed records with unique, ordered seq
        assert [(record.node_id, record.status) for record in recorder.records] == [
            (_WRONG_RETURN_ID, "failed"),
            ("tests.v2.core.rc1_f06.outer", "failed"),
        ]
        assert [record.seq for record in recorder.records] == [1, 2]

    def test_argument_mismatch_runs_nothing_and_records_nothing__tc_rc1_f06_neg_001(self) -> None:
        # Given: strict recording and a wrong argument type
        with CallLogRecorder(type_check="strict") as recorder:
            # When: the pre-execution argument check fails
            with pytest.raises(RdeExecutionError) as exc_info:
                wrong_return(1)  # type: ignore[arg-type]

        # Then: the body never ran, so there is no executed call to record
        assert exc_info.value.code == 3002
        assert _SIDE_EFFECTS == []
        assert recorder.records == ()

    def test_warn_return_mismatch_stays_completed__tc_rc1_f06_neg_002(self) -> None:
        # Given: warn mode
        with CallLogRecorder(type_check="warn") as recorder, pytest.warns(UserWarning, match="return"):
            # When: the lying node runs
            result = wrong_return("w")

        # Then: the value is returned and the call is a completed record
        assert result == "w"
        assert [record.status for record in recorder.records] == ["completed"]
        assert recorder.records[0].outputs[0].type_name == "str"

    def test_matching_return_is_a_completed_record__tc_rc1_f06_neg_003(self) -> None:
        # Given / When: a truthful node in strict mode
        with CallLogRecorder(type_check="strict") as recorder:
            assert right_return(1) == 1

        # Then: one completed record with its output summary
        assert [record.status for record in recorder.records] == ["completed"]
        assert recorder.records[0].outputs[0].type_name == "int"


class TestTileAndRunnerSeeTheFailedCall:
    def test_tile_error_points_at_the_recorded_call__tc_rc1_f06_ep_002(self) -> None:
        # Given: a strict tile whose flow calls the lying node
        sink = MemoryEventSink()
        sink.open("rc1-f06")
        config = RdeConfig(execution={"type_check": "strict"})
        context = RunContext(config=config, iteration=IterationInfo(index=0, total=1, mode="invoice"))

        # When: the tile runs
        with pytest.raises(TileExecutionError) as exc_info:
            run_tile(wrong_return_flow, context, event_sink=sink, run_id="rc1-f06", config=config)

        # Then: the error names the failed record and its node events are emitted
        result = exc_info.value.result
        assert len(result.call_records) == 1
        record = result.call_records[0]
        assert record.status == "failed"
        assert result.error is not None
        assert result.error["code"] == 3002
        assert result.error["call_id"] == record.call_id
        assert result.error["call_id"] != "unknown"
        node_events = [(event.name, event.payload.get("call_id")) for event in sink.events if event.name.startswith("node.")]
        assert node_events == [("node.started", record.call_id), ("node.failed", record.call_id)]

    def test_run_report_error_points_at_the_recorded_call__tc_rc1_f06_ep_003(self, tmp_path: Path) -> None:
        # Given: a valid one-tile input tree run in strict mode
        for name in ("inputdata", "invoice", "tasksupport"):
            (tmp_path / name).mkdir()
        (tmp_path / "inputdata" / "a.txt").write_text("a", encoding="utf-8")
        invoice = {"datasetId": "f06", "basic": {"dateSubmitted": "2026-11-08", "dataOwnerId": "0" * 56, "dataName": "f06"}}
        (tmp_path / "invoice" / "invoice.json").write_text(json.dumps(invoice), encoding="utf-8")
        (tmp_path / "tasksupport" / "invoice.schema.json").write_text(json.dumps({"properties": {}}), encoding="utf-8")
        sink = MemoryEventSink()

        # When: the Runner executes the flow
        report = Runner(root=tmp_path, event_sink=sink).run(wrong_return_flow, execution={"type_check": "strict"})

        # Then: the run failed with 3002 at the recorded call, and job.failed exists
        assert report.status == "failed"
        assert report.error is not None
        assert report.error["code"] == 3002
        failed_ids = [event.payload.get("call_id") for event in sink.events if event.name == "node.failed"]
        assert len(failed_ids) == 1
        assert report.error["call_id"] == failed_ids[0] == f"{_WRONG_RETURN_ID}#1"
        assert (tmp_path / "job.failed").exists()
