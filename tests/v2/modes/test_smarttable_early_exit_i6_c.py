"""Session I6-C: ``smarttable.save_table_file=True`` (v1 EarlyExit) parity.

v1's ``SmartTableEarlyExitProcessor`` runs first in the SmartTable pipeline. For
the tile whose raw input is the original ``inputdata/smarttable_*.{xlsx,csv,tsv}``
it sets ``basic.dataName`` to the table's filename, copies the table into
``raw/`` and ``nonshared_raw/``, validates the tile, and raises
``SkipRemainingProcessorsError`` — the dataset callback and every later
processor are skipped while the tile still counts as a success.

v2 expresses that as a **pre-completed tile**: ``TilePlan.precompleted`` makes
the executor skip flow invocation and the post-invoke invoice stage while
recording the iteration as ``completed`` with an empty call log. The pre-invoke
raw stage still runs, which is what copies the table (the generic
``RawArtifactService`` already keeps the original table when
``save_table_file`` is on, exactly like v1's EarlyExit copy).

The expectation is not written by hand: it is the v1 observation of the same
input with ``save_table_file=True``. Until Session K1 this module ran v1 itself
in an isolated worker; that run is now the registered generator case
``smarttable/ok__save_table_file`` (K1 ruling #6 item 7, the v1.7.1 #503
semantics: the table registers first at ``divided/0001``), frozen like every
other v1 observation.

Equivalence partitions (EP):

| API | Partition | Rationale | Expected | Test ID |
| --- | --- | --- | --- | --- |
| ``TileExecutor.execute`` | ``precompleted`` tile | EarlyExit seam | no invoke, no post-invoke, completed | TC-I6-C-EP-070 |
| ``TileExecutor.execute`` | ordinary tile | default keeps old behavior | invoke and post-invoke both run | TC-I6-C-EP-071 |
| ``Runner.run`` | ``save_table_file=True`` | full v1 parity | artifacts equal the frozen v1 case | TC-I6-C-EP-072 |
| ``Runner.run`` | ``save_table_file=True`` | tile vs callback counts | iterations == v1 tiles, flow calls == v1 callbacks | TC-I6-C-EP-073 |

Boundary values / negatives (EV):

| API | Boundary | Rationale | Expected | Test ID |
| --- | --- | --- | --- | --- |
| ``Runner.run`` | ``save_table_file=False`` | the default must not change | no pre-completed tile, flow runs per tile | TC-I6-C-EV-074 |
| ``SmartTableModeHandler`` | table tile invoice | EarlyExit dataName rule | ``basic.dataName`` is the table filename | TC-I6-C-EV-075 |
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.api.request import FlowTarget
from rdetoolkit.core.flow import flow
from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.runner.execute import ExecutionResult
from rdetoolkit.runner.executor import TileExecutor
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.paths import resolve_tile_paths
from rdetoolkit.runner.planner import ExecutionPlan, TilePlan
from rdetoolkit.types import InputPaths, InvoiceData, IterationInfo, OutputContext, RdeConfig
from tests.v2.contract.fixtures import _generate
from tests.v2.contract.frozen import frozen_observed
from tests.v2.contract.observe import observe_v2_run, parity_pair

_MODE = "smarttable"
_FLOW_CALLS: list[tuple[str, ...]] = []

#: The registered v1 case this module's oracle is frozen as.
_CASE_ID = "v1/smarttable/ok__save_table_file"


@flow
def _counting_flow(paths: InputPaths, invoice: InvoiceData) -> None:
    """Record one flow invocation per tile."""
    assert invoice.raw
    _FLOW_CALLS.append(tuple(path.name for path in paths.rawfiles))


def _v2_overrides(*, save_table_file: bool) -> dict[str, Any]:
    """Return the v2 configuration the frozen v1 case ran with."""
    return {
        "system": {
            "extended_mode": "invoice",
            "save_raw": True,
            "save_nonshared_raw": True,
            "save_thumbnail_image": False,
            "magic_variable": False,
        },
        "smarttable": {"save_table_file": save_table_file},
    }


def _run_v2(root: Path, monkeypatch: pytest.MonkeyPatch, *, save_table_file: bool) -> Any:
    _generate._materialize_oracle_case(_MODE, root)  # noqa: SLF001
    monkeypatch.chdir(root)
    _FLOW_CALLS.clear()
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        # The flow entry unpacks into data/temp, as v1 does (contracts.md §I6-1).
        unpacked_dir_path=root / "data" / "temp",
    )
    return runner.run(_counting_flow, **_v2_overrides(save_table_file=save_table_file))


class _InvokerProbe:
    """Record whether the executor invoked the flow at all."""

    def __init__(self) -> None:
        self.calls: int = 0

    def invoke(self, *args: object, **kwargs: object) -> ExecutionResult:
        self.calls += 1
        return ExecutionResult(iteration_index=0, status="completed", call_records=(), outputs=())


class _RawProbe:
    """Record raw publication without touching the filesystem."""

    def __init__(self) -> None:
        self.calls: list[tuple[Path, ...]] = []

    def copy(self, source_files: tuple[Path, ...], **kwargs: object) -> None:
        self.calls.append(source_files)


class _InvoiceStageProbe:
    """Record the post-invoke invoice stages, in the order they are applied."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def apply_step(self, step: str, **kwargs: object) -> None:
        self.calls.append(step)


class _ImageProbe:
    """Record the post-invoke image stage."""

    def __init__(self) -> None:
        self.calls: int = 0

    def generate(self, **kwargs: object) -> None:
        self.calls += 1


def _write_tile_artifacts(tmp_path: Path) -> None:
    """Publish the artifacts a pre-completed tile must validate (ruling #6).

    v1's EarlyExit validated its tile *before* skipping the rest of the
    pipeline, so the executor now does the same. The probe tile therefore needs
    a real invoice and schema on disk.
    """
    data_root = tmp_path / "data"
    (data_root / "invoice").mkdir(parents=True, exist_ok=True)
    (data_root / "tasksupport").mkdir(parents=True, exist_ok=True)
    (data_root / "invoice" / "invoice.json").write_text(
        json.dumps(
            {
                "datasetId": "i6c-early-exit",
                "basic": {
                    "dateSubmitted": "2026-09-14",
                    "dataOwnerId": "0" * 56,
                    "dataName": "smarttable_full.xlsx",
                },
            },
        ),
        encoding="utf-8",
    )
    (data_root / "tasksupport" / "invoice.schema.json").write_text(
        json.dumps({"properties": {}}),
        encoding="utf-8",
    )


def _tile(tmp_path: Path, *, precompleted: bool) -> TilePlan:
    rawfile = tmp_path / "data" / "inputdata" / "smarttable_full.xlsx"
    _write_tile_artifacts(tmp_path)
    output_paths = resolve_tile_paths(tmp_path / "data", 0)
    return TilePlan(
        iteration=IterationInfo(index=0, total=1, mode="smarttable"),
        paths=InputPaths(
            inputdata=rawfile.parent,
            invoice=tmp_path / "data" / "invoice",
            tasksupport=tmp_path / "data" / "tasksupport",
            rawfiles=(rawfile,),
        ),
        out=OutputContext.from_resource_paths(output_paths),
        invoice=None,
        precompleted=precompleted,
    )


def _plan(tmp_path: Path, tile: TilePlan) -> ExecutionPlan:
    return ExecutionPlan(
        run_id="i6c-early-exit",
        target=FlowTarget(function=lambda: None),
        mode=ModeKind.smarttable,
        config=RdeConfig(),
        root=tmp_path,
        data_root=tmp_path,
        invoice_source=tmp_path / "data" / "invoice" / "invoice.json",
        error_policy="continue",
        tiles=(tile,),
    )


def _execute(tmp_path: Path, *, precompleted: bool) -> tuple[ExecutionResult, dict[str, Any]]:
    tile = _tile(tmp_path, precompleted=precompleted)
    invoker = _InvokerProbe()
    raw = _RawProbe()
    invoice_stage = _InvoiceStageProbe()
    image = _ImageProbe()
    executor = TileExecutor(
        event_sink=MemoryEventSink(),
        flow_invoker=invoker,  # type: ignore[arg-type]
        raw_artifact_service=raw,  # type: ignore[arg-type]
        image_artifact_service=image,  # type: ignore[arg-type]
        invoice_service=invoice_stage,  # type: ignore[arg-type]
    )
    result = executor.execute(_plan(tmp_path, tile), tile)
    return result, {"invoker": invoker.calls, "raw": raw.calls, "invoice": invoice_stage.calls, "image": image.calls}


def test_precompleted_tile_skips_invocation__tc_i6_c_ep_070(tmp_path: Path) -> None:
    """TC-I6-C-EP-070: a pre-completed tile is recorded without running the flow."""
    # Given: a tile the mode marked as already complete
    # When: the executor runs it
    result, probes = _execute(tmp_path, precompleted=True)

    # Then: no invocation, no post-invoke stage, and an empty call log
    assert probes["invoker"] == 0
    assert probes["invoice"] == []
    assert probes["image"] == 0
    assert result.status == "completed"
    assert result.call_records == ()
    assert result.outputs == ()
    assert result.error is None
    assert result.iteration_index == 0
    # And: the pre-invoke raw stage still ran, which is what copies the table
    assert len(probes["raw"]) == 1


def test_ordinary_tile_keeps_the_full_pipeline__tc_i6_c_ep_071(tmp_path: Path) -> None:
    """TC-I6-C-EP-071: the default flag value changes nothing for other tiles."""
    # Given: the same tile without the flag
    # When: the executor runs it
    result, probes = _execute(tmp_path, precompleted=False)

    # Then: the flow and both post-invoke stages run exactly as before, and the
    # SmartTable sequence is the v1 invoice pipeline's order (ruling #5)
    assert probes["invoker"] == 1
    assert probes["invoice"] == ["structured", "magic", "description"]
    assert probes["image"] == 1
    assert result.status == "completed"
    assert len(probes["raw"]) == 1


def test_save_table_file_matches_the_v1_oracle__tc_i6_c_ep_072_073(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-C-EP-072/073: artifacts and both counts equal the frozen v1 run."""
    # Given: v1's observation of the same fixture with save_table_file=True
    expected = frozen_observed(_CASE_ID)
    assert expected["exit_code"] == 0

    # When: the v2 Runner executes the same input and configuration
    report = _run_v2(tmp_path / "v2", monkeypatch, save_table_file=True)

    # Then: every compared artifact matches the frozen oracle
    assert report.status == "success"
    actual, expected_view = parity_pair(tmp_path / "v2", expected)
    assert actual == expected_view

    # And: the table tile is an iteration, but it never invoked the flow
    assert len(report.iterations) == len(expected["invoices"])
    assert [iteration["status"] for iteration in report.iterations] == ["completed"] * len(expected["invoices"])
    assert len(_FLOW_CALLS) == expected["callback_count"]
    assert len(report.iterations) == len(_FLOW_CALLS) + 1

    # And: exactly one iteration carries no node call at all — the tile whose
    # flow was never invoked. The counting flow calls no node, so this is
    # asserted through the flow-call ledger above rather than the call log.
    assert all(iteration["node_calls"] == [] for iteration in report.iterations)
    assert sorted(iteration["index"] for iteration in report.iterations) == list(range(len(expected["invoices"])))


def test_table_tile_invoice_carries_the_table_name__tc_i6_c_ev_075(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-C-EV-075: the EarlyExit dataName rule reaches the tile invoice.

    UPDATED (K0-iii, v1.7.1 #503): the table tile is ``divided/0001``, whose
    invoice v1 seeds from ``invoice_org`` before renaming it.
    """
    # Given: v1's own value for the table tile
    expected = frozen_observed(_CASE_ID)

    # When: running v2 with the same configuration
    _run_v2(tmp_path / "v2", monkeypatch, save_table_file=True)

    # Then: the divided/0001 invoice names the table file, as v1's EarlyExit does
    table_invoice = "data/divided/0001/invoice/invoice.json"
    observed = observe_v2_run(tmp_path / "v2")["invoices"][table_invoice]
    assert observed["basic"]["dataName"] == "smarttable_full.xlsx"
    assert observed == expected["invoices"][table_invoice]
    # And: the run-level invoice is the last row's, not the table's
    assert observe_v2_run(tmp_path / "v2")["invoices"]["data/invoice/invoice.json"]["basic"]["dataName"] != "smarttable_full.xlsx"
    # And: the table itself was published as raw material of its own tile
    assert "data/divided/0001/raw/smarttable_full.xlsx" in observe_v2_run(tmp_path / "v2")["raw_sha256"]


def test_default_configuration_has_no_precompleted_tile__tc_i6_c_ev_074(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-C-EV-074: with save_table_file off, every tile still runs the flow."""
    # Given / When: the same fixture with the default SmartTable configuration
    report = _run_v2(tmp_path / "v2", monkeypatch, save_table_file=False)

    # Then: no tile is pre-completed — the flow ran once per iteration
    assert report.status == "success"
    assert len(_FLOW_CALLS) == len(report.iterations)
    assert all(iteration["status"] == "completed" for iteration in report.iterations)
    # And: no raw file of the original table exists, because v1 does not copy
    # it when the table is not saved.
    assert not any("smarttable_full.xlsx" in path for path in observe_v2_run(tmp_path / "v2")["raw_sha256"])
