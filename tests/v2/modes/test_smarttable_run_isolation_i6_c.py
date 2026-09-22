"""Session I6-C: SmartTable runs sharing one root stay independent.

Before I6-C the base invoice lived in a v1 **class** attribute keyed by the
resolved source path, and the run boundary evicted that key process-wide. Two
runs over one root therefore shared one snapshot, and starting a run could
evict the snapshot a concurrently executing run was still using. The base
invoice is now owned by the run's ``InvoiceService``.

Equivalence partitions (EP):

| API | Partition | Rationale | Expected | Test ID |
| --- | --- | --- | --- | --- |
| ``InvoiceService.prepare_tile`` | two runs, one root, source replaced | overlapping runs | each keeps its own snapshot | TC-I6-C-CONC-001 |
| ``InvoiceService.begin_run`` | second run starts mid-first-run | instance-owned material | first run's snapshot survives | TC-I6-C-CONC-002 |

Boundary values (BV):

| API | Boundary | Rationale | Expected | Test ID |
| --- | --- | --- | --- | --- |
| ``InvoiceService.prepare_tile`` | two threads, one root, two different base invoices | minimum real concurrency, discriminating content | each run's tiles carry its own snapshot | TC-I6-C-CONC-003 |
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from typing import Any

from rdetoolkit.domain.invoice_service import InvoiceService
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import InputPaths

_OWNER_ID = "0" * 55 + "1"

_INVOICE_SCHEMA: dict[str, Any] = {
    "required": ["sample"],
    "properties": {
        "sample": {"type": "object", "label": {"ja": "サンプル", "en": "Sample"}, "properties": {}},
    },
}


def _source_invoice(data_name: str) -> dict[str, Any]:
    return {
        "datasetId": "seed-dataset",
        "basic": {
            "dateSubmitted": "2026-09-07",
            "dataOwnerId": _OWNER_ID,
            "dataName": data_name,
        },
        "sample": {"sampleId": "00000000-0000-0000-0000-000000000001"},
    }


def _materialize_root(root: Path, data_name: str) -> Path:
    """Create one shared SmartTable data root and return its source invoice."""
    data_root = root / "data"
    (data_root / "inputdata").mkdir(parents=True)
    (data_root / "invoice").mkdir()
    (data_root / "tasksupport").mkdir()
    (data_root / "inputdata" / "fsmarttable_shared_0000.csv").write_text(
        "basic/instrumentId\nshared-instrument\n",
        encoding="utf-8",
    )
    (data_root / "tasksupport" / "invoice.schema.json").write_text(
        json.dumps(_INVOICE_SCHEMA),
        encoding="utf-8",
    )
    source = data_root / "invoice" / "invoice.json"
    source.write_text(json.dumps(_source_invoice(data_name)), encoding="utf-8")
    return source


def _prepare(service: InvoiceService, root: Path, destination: str) -> Path:
    """Prepare one SmartTable tile invoice under ``destination``."""
    data_root = root / "data"
    service.prepare_tile(
        ModeKind.smarttable,
        paths=InputPaths(
            inputdata=data_root / "inputdata",
            invoice=data_root / "invoice",
            tasksupport=data_root / "tasksupport",
            rawfiles=(data_root / "inputdata" / "fsmarttable_shared_0000.csv",),
        ),
        invoice_dir=data_root / destination / "invoice",
        iteration_index=0,
        invariant_invoice=None,
        invoice_source=data_root / "invoice" / "invoice.json",
    )
    return data_root / destination / "invoice" / "invoice.json"


def _data_name(path: Path) -> str:
    name: str = json.loads(path.read_text(encoding="utf-8"))["basic"]["dataName"]
    return name


def test_two_runs_over_one_root_keep_their_own_base_invoice__tc_i6_c_conc_001(tmp_path: Path) -> None:
    """TC-I6-C-CONC-001: a replaced source invoice reaches only the later run."""
    # Given: one root and two overlapping runs, the first already started
    source = _materialize_root(tmp_path, "first-content")
    first = InvoiceService()
    second = InvoiceService()
    first.begin_run()
    first_tile = _prepare(first, tmp_path, "first")

    # When: the shared source is replaced and the second run prepares its tile
    source.write_text(json.dumps(_source_invoice("second-content")), encoding="utf-8")
    second.begin_run()
    second_tile = _prepare(second, tmp_path, "second")
    later_first_tile = _prepare(first, tmp_path, "first_later")

    # Then: each run keeps the content it started with
    assert _data_name(first_tile) == "first-content"
    assert _data_name(second_tile) == "second-content"
    assert _data_name(later_first_tile) == "first-content"


def test_starting_a_run_does_not_evict_another_runs_snapshot__tc_i6_c_conc_002(tmp_path: Path) -> None:
    """TC-I6-C-CONC-002: ``begin_run`` releases only its own run's material."""
    # Given: a run that already snapshotted the shared source invoice
    source = _materialize_root(tmp_path, "first-content")
    first = InvoiceService()
    first.begin_run()
    _prepare(first, tmp_path, "first")

    # When: a second run over the same root starts and ends while the first
    # run is still executing, with the source replaced in between
    second = InvoiceService()
    second.begin_run()
    source.write_text(json.dumps(_source_invoice("second-content")), encoding="utf-8")
    second.end_run()
    survivor = _prepare(first, tmp_path, "first_later")

    # Then: the first run's snapshot survived both boundaries of the second
    assert _data_name(survivor) == "first-content"


def test_two_threads_hold_different_base_invoices__tc_i6_c_conc_003(tmp_path: Path) -> None:
    """TC-I6-C-CONC-003: overlapping runs each keep the content they read.

    The interleaving is pinned by barriers rather than by timing, and the two
    runs deliberately read **different** content from the same path: run A
    snapshots the original invoice, run B then replaces the file and snapshots
    the replacement, and only afterwards does run A build a second tile. A
    process-global cache keyed by path — which is how v1 held the base invoice —
    cannot satisfy this, because run B's ``begin_run`` would evict the entry run
    A is still using and run A's later tile would inherit run B's content.
    """
    # Given: one shared root and two runs whose lifetimes overlap
    source = _materialize_root(tmp_path, "run-a-content")
    snapshot_taken = Barrier(2, timeout=30)
    replacement_done = Barrier(2, timeout=30)
    results: dict[str, str] = {}

    def run_a() -> None:
        service = InvoiceService()
        service.begin_run()
        results["a_first"] = _data_name(_prepare(service, tmp_path, "a_first"))
        snapshot_taken.wait()
        # Run B replaces the shared source and reads it here.
        replacement_done.wait()
        results["a_later"] = _data_name(_prepare(service, tmp_path, "a_later"))
        service.end_run()

    def run_b() -> None:
        snapshot_taken.wait()
        source.write_text(json.dumps(_source_invoice("run-b-content")), encoding="utf-8")
        service = InvoiceService()
        service.begin_run()
        results["b_first"] = _data_name(_prepare(service, tmp_path, "b_first"))
        service.end_run()
        replacement_done.wait()

    # When: both runs execute simultaneously in separate threads
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_a), pool.submit(run_b)]
        for future in futures:
            future.result(timeout=60)

    # Then: every tile carries the content of the run that built it
    assert results == {
        "a_first": "run-a-content",
        "a_later": "run-a-content",
        "b_first": "run-b-content",
    }
    assert json.loads((tmp_path / "data" / "a_later" / "invoice" / "invoice.json").read_text(encoding="utf-8"))[
        "basic"
    ]["instrumentId"] == "shared-instrument"
