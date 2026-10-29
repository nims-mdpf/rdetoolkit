"""Release PR #553 review fix F6-2 (Session K4-F6).

``seq`` is the run-global call order and ``call_id`` is unique within a run
(Design §3.4). One ``CallSequence`` per run is shared by every tile's recorder,
on the flow entry and on the v1 callback entry alike.

EP table:

| TC-ID            | Partition                                                   | Expected                                              |
|------------------|-------------------------------------------------------------|-------------------------------------------------------|
| TC-K4F6-EP-002   | two recorders share one CallSequence                         | seq 1,2 then 3,4; call ids unique                     |
| TC-K4F6-EP-003   | two-tile MultiDataTile run, flow entry                      | call ids unique, seq strictly increasing across tiles |
| TC-K4F6-EP-004   | two-tile MultiDataTile run, v1 callback entry               | call ids unique, seq strictly increasing across tiles |

BV table:

| TC-ID            | Boundary                                                    | Expected                                              |
|------------------|-------------------------------------------------------------|-------------------------------------------------------|
| TC-K4F6-BV-001   | single-tile invoice run                                      | seq starts at 1, call ids "<node>#1", "<node>#2"      |
| TC-K4F6-BV-002   | standalone recorder (no sequence)                            | private counter starts at 1 per recorder              |
| TC-K4F6-BV-003   | a fresh CallSequence                                         | first next() is 1                                     |
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rdetoolkit.api.request import LegacyCallbackTarget, RunRequest
from rdetoolkit.core.calllog import CallLogRecorder, CallSequence
from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import IterationInfo
from tests.v2.contract.fixtures import _generate


@node(id="k4f6_step")
def _step(iteration: IterationInfo) -> int:
    return iteration.index


@flow
def _two_step_flow(iteration: IterationInfo) -> None:
    _step(iteration)
    _step(iteration)


def _two_step_callback(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    iteration = IterationInfo(index=0, total=1, mode="invoice")
    _step(iteration)
    _step(iteration)


def _runner(root: Path, run_id: str) -> Runner:
    return Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "unpacked",
        run_id_factory=lambda: run_id,
    )


def _node_calls(report: RunReport) -> list[dict[str, Any]]:
    """Every call record in the report, in iteration order then recorded order."""
    return [call for iteration in report.iterations for call in iteration["node_calls"]]


def _assert_run_global_sequence(report: RunReport, *, tiles: int) -> None:
    assert report.status == "success", report.error
    assert len(report.iterations) == tiles
    calls = _node_calls(report)
    assert len(calls) == 2 * tiles
    call_ids = [call["call_id"] for call in calls]
    seqs = [call["seq"] for call in calls]
    assert len(set(call_ids)) == len(call_ids), call_ids
    assert seqs == list(range(1, 2 * tiles + 1))


# --- F6-2: unit ----------------------------------------------------------------


def test_fresh_call_sequence_starts_at_one__tc_k4f6_bv_003() -> None:
    """TC-K4F6-BV-003: a fresh run-scoped counter hands out 1 first."""
    # Given: a fresh sequence
    sequence = CallSequence()

    # When / Then: it counts from 1
    assert [sequence.next(), sequence.next()] == [1, 2]


def test_recorders_sharing_a_sequence_number_globally__tc_k4f6_ep_002() -> None:
    """TC-K4F6-EP-002: two tiles' recorders on one sequence number 1,2 then 3,4."""
    # Given: two recorders sharing one sequence
    sequence = CallSequence()
    first = CallLogRecorder(iteration_index=0, sequence=sequence)
    second = CallLogRecorder(iteration_index=1, sequence=sequence)
    info = IterationInfo(index=0, total=2, mode="invoice")

    # When: each records two calls
    with first:
        _step(info)
        _step(info)
    with second:
        _step(info)
        _step(info)

    # Then: seq continues across recorders and call ids never repeat
    assert [record.seq for record in first.records] == [1, 2]
    assert [record.seq for record in second.records] == [3, 4]
    call_ids = [record.call_id for record in (*first.records, *second.records)]
    assert call_ids == ["k4f6_step#1", "k4f6_step#2", "k4f6_step#3", "k4f6_step#4"]


def test_standalone_recorders_keep_a_private_counter__tc_k4f6_bv_002() -> None:
    """TC-K4F6-BV-002: a recorder built without a sequence still starts at 1."""
    # Given: two independent recorders
    info = IterationInfo(index=0, total=1, mode="invoice")
    first = CallLogRecorder()
    second = CallLogRecorder()

    # When: each records one call
    with first:
        _step(info)
    with second:
        _step(info)

    # Then: neither shares numbering with the other
    assert [record.seq for record in first.records] == [1]
    assert [record.seq for record in second.records] == [1]


# --- F6-2: Runner level ----------------------------------------------------------


def test_two_tile_flow_run_numbers_calls_run_globally__tc_k4f6_ep_003(tmp_path: Path) -> None:
    """TC-K4F6-EP-003: the flow entry shares one sequence across MultiDataTile tiles."""
    # Given: a materialized two-tile MultiDataTile input family
    _generate.materialize_sut_case("multidatatile", tmp_path)

    # When: running a flow that calls one node twice per tile
    report = _runner(tmp_path, "k4f6-ep-003").run(_two_step_flow, system={"extended_mode": "MultiDataTile"})

    # Then: call ids are unique and seq strictly increases across tiles
    _assert_run_global_sequence(report, tiles=2)


def test_two_tile_callback_run_numbers_calls_run_globally__tc_k4f6_ep_004(tmp_path: Path) -> None:
    """TC-K4F6-EP-004: the v1 callback entry shares one sequence across MultiDataTile tiles."""
    # Given: a materialized two-tile MultiDataTile input family and a v1 callback
    _generate.materialize_sut_case("multidatatile", tmp_path)
    request = RunRequest(
        root=tmp_path,
        target=LegacyCallbackTarget(function=_two_step_callback),
        config_source={"system": {"extended_mode": "MultiDataTile"}},
    )

    # When: running it through the Runner
    report = _runner(tmp_path, "k4f6-ep-004").run(request)

    # Then: call ids are unique and seq strictly increases across tiles
    _assert_run_global_sequence(report, tiles=2)


def test_single_tile_run_starts_at_one__tc_k4f6_bv_001(tmp_path: Path) -> None:
    """TC-K4F6-BV-001: a single-tile run still numbers its calls from 1."""
    # Given: a materialized single-tile invoice input family
    _generate.materialize_sut_case("invoice", tmp_path)

    # When: running a flow that calls one node twice
    report = _runner(tmp_path, "k4f6-bv-001").run(_two_step_flow)

    # Then: the call log starts at 1
    _assert_run_global_sequence(report, tiles=1)
    assert [call["call_id"] for call in _node_calls(report)] == ["k4f6_step#1", "k4f6_step#2"]
