"""SmartTable row data travels by value (Session I-REVIEW-A, ruling #2).

Reviews F1 and R4 reproduced the same defect: the row dictionary a v1 callback
receives as ``RdeOutputResourcePath.smarttable_row_data`` was kept in a
process-global dictionary keyed by the resolved data root
(``domain.invoice._TILE_ROW_DATA``), and ``InvoiceService.begin_run`` /
``end_run`` dropped **every** entry of that root. A second Runner starting or
finishing on the same root therefore erased the material of a run that was
still between tile preparation and its callback.

The handoff is now a value: ``TilePlan.prepare_invoice`` returns a
``TilePreparation``, the executor keeps it, and it reaches the invoker as
``TileMaterial``. Nothing outside the run can reach it.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-IRA-2-EP-020 | preparation | SmartTable tile | ``TilePreparation`` carries invoice **and** row data |
| TC-IRA-2-EP-021 | material | SmartTable material | the callback receives that row dictionary |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-IRA-2-EV-022 | interleave | run B begins/ends on A's root mid-run | A keeps its own row data |
| TC-IRA-2-EV-023 | non-SmartTable | tile without a row CSV | ``smarttable_row_data`` stays ``None`` |
| TC-IRA-2-EV-024 | API | ``domain.invoice`` | the module-global handoff no longer exists |
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.compat.v1.callback import to_legacy_dataset_paths
from rdetoolkit.core.context import RunContext
from rdetoolkit.domain.invoice_service import InvoiceService
from rdetoolkit.runner.iterator import iterate_tiles
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.paths import resolve_tile_paths
from rdetoolkit.runner.planner import TileMaterial, TilePreparation
from rdetoolkit.types import InputPaths, IterationInfo, OutputContext, RdeConfig
from tests.v2.contract.fixtures import _generate

_BARRIER_TIMEOUT = 10.0


def _smarttable_tiles(root: Path) -> list[tuple[IterationInfo, InputPaths, OutputContext]]:
    data_root = root / "data"
    return list(iterate_tiles(ModeKind.smarttable, data_root / "inputdata", data_root / "temp", data_root))


def _prepare(service: InvoiceService, root: Path, tile: tuple[Any, Any, Any]) -> TilePreparation:
    info, paths, out = tile
    invoice, row_data = service.prepare_tile(
        ModeKind.smarttable,
        paths=paths,
        invoice_dir=out.invoice,
        iteration_index=info.index,
        invariant_invoice=None,
        invoice_source=root / "data" / "invoice" / "invoice.json",
    )
    return TilePreparation(invoice=invoice, smarttable_row_data=row_data)


def test_preparation_carries_the_row_dictionary__tc_ira_2_ep_020(tmp_path: Path) -> None:
    """TC-IRA-2-EP-020: preparing a SmartTable tile yields its row data."""
    # Given: a SmartTable fixture and a run-owned invoice service
    root = tmp_path / "smarttable"
    _generate.materialize_sut_case("smarttable", root)
    service = InvoiceService()
    service.begin_run()

    # When: preparing tile 0
    preparation = _prepare(service, root, _smarttable_tiles(root)[0])

    # Then: both the invoice and the row dictionary are returned by value
    assert preparation.invoice is not None
    assert preparation.smarttable_row_data is not None
    assert "basic/dataName" in preparation.smarttable_row_data


def test_callback_receives_the_prepared_row_dictionary__tc_ira_2_ep_021(tmp_path: Path) -> None:
    """TC-IRA-2-EP-021: the material -- not a global -- feeds the v1 callback."""
    # Given: a prepared SmartTable tile
    root = tmp_path / "smarttable"
    _generate.materialize_sut_case("smarttable", root)
    service = InvoiceService()
    service.begin_run()
    info, paths, out = _smarttable_tiles(root)[0]
    preparation = _prepare(service, root, (info, paths, out))
    context = RunContext(paths=paths, out=out, config=RdeConfig(), iteration=info)
    material = TileMaterial(
        invoice_source=root / "data" / "invoice" / "invoice.json",
        smarttable_row_data=preparation.smarttable_row_data,
    )

    # When: converting the tile to v1 callback arguments
    legacy = to_legacy_dataset_paths(context, material=material)

    # Then: the callback sees exactly the dictionary the builder computed
    assert legacy.output_paths.smarttable_row_data == preparation.smarttable_row_data
    assert legacy.output_paths.smarttable_rowfile == paths.rawfiles[0]


def test_a_concurrent_run_cannot_erase_the_row_data__tc_ira_2_ev_022(tmp_path: Path) -> None:
    """TC-IRA-2-EV-022: run B's boundary never touches run A's tile material.

    This is review F1/R4's counterexample, reproduced with a barrier so B's
    ``begin_run``/``end_run`` land strictly between A's tile preparation and A's
    callback conversion -- the exact window the global dictionary lost.
    """
    # Given: two runs over one data root, and a barrier that orders them
    root = tmp_path / "smarttable"
    _generate.materialize_sut_case("smarttable", root)
    prepared = threading.Barrier(2, timeout=_BARRIER_TIMEOUT)
    interfered = threading.Barrier(2, timeout=_BARRIER_TIMEOUT)
    failures: list[BaseException] = []
    observed: list[Any] = []

    tiles = _smarttable_tiles(root)
    service_a = InvoiceService()
    service_a.begin_run()

    def run_a() -> None:
        try:
            preparation = _prepare(service_a, root, tiles[0])
            prepared.wait()
            interfered.wait()
            info, paths, out = tiles[0]
            legacy = to_legacy_dataset_paths(
                RunContext(paths=paths, out=out, config=RdeConfig(), iteration=info),
                material=TileMaterial(
                    invoice_source=root / "data" / "invoice" / "invoice.json",
                    smarttable_row_data=preparation.smarttable_row_data,
                ),
            )
            observed.append(legacy.output_paths.smarttable_row_data)
        except BaseException as exc:  # noqa: BLE001
            failures.append(exc)
            for barrier in (prepared, interfered):
                barrier.abort()

    def run_b() -> None:
        try:
            prepared.wait()
            service_b = InvoiceService()
            service_b.begin_run()
            _prepare(service_b, root, tiles[1])
            service_b.end_run()
            interfered.wait()
        except BaseException as exc:  # noqa: BLE001
            failures.append(exc)
            for barrier in (prepared, interfered):
                barrier.abort()

    # When: B opens and closes a run on the same root while A is mid-flight
    threads = [threading.Thread(target=run_a), threading.Thread(target=run_b)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=_BARRIER_TIMEOUT * 2)

    # Then: A still holds its own row dictionary
    assert failures == []
    assert observed and observed[0] is not None
    assert "basic/dataName" in observed[0]


def test_non_smarttable_material_stays_empty__tc_ira_2_ev_023(tmp_path: Path) -> None:
    """TC-IRA-2-EV-023: an ordinary tile advertises no SmartTable material."""
    # Given: a plain tile and material with no row data
    data_root = tmp_path / "data"
    rawfile = data_root / "inputdata" / "sample.txt"
    rawfile.parent.mkdir(parents=True, exist_ok=True)
    rawfile.write_text("raw", encoding="utf-8")
    tile = resolve_tile_paths(data_root, 0)
    context = RunContext(
        paths=InputPaths(
            inputdata=data_root / "inputdata",
            invoice=data_root / "invoice",
            tasksupport=data_root / "tasksupport",
            raw=rawfile,
            rawfiles=(rawfile,),
        ),
        out=OutputContext.from_resource_paths(tile),
        config=RdeConfig(),
        iteration=IterationInfo(index=0, total=1, mode="invoice"),
    )

    # When: converting the tile to v1 callback arguments
    legacy = to_legacy_dataset_paths(
        context,
        material=TileMaterial(invoice_source=data_root / "invoice" / "invoice.json"),
    )

    # Then: neither SmartTable field is advertised
    assert legacy.output_paths.smarttable_rowfile is None
    assert legacy.output_paths.smarttable_row_data is None


@pytest.mark.parametrize(
    "name",
    ["_TILE_ROW_DATA", "record_tile_row_data", "tile_row_data", "clear_tile_row_data"],
)
def test_module_global_handoff_is_gone__tc_ira_2_ev_024(name: str) -> None:
    """TC-IRA-2-EV-024: no process-global channel survives for tile material."""
    # Given / When: the invoice domain module
    import rdetoolkit.domain.invoice as module  # noqa: PLC0415

    # Then: the global handoff and its whole API are removed
    assert not hasattr(module, name)
