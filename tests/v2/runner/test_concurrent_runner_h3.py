"""Threaded concurrent Runner acceptance for Phase H3.

Equivalence partitions (EP):

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``Runner.run`` | two roots, each of five modes | matches isolated execution | TC-H3-CONC-001 |
| ``Runner.run`` | shared process, distinct roots | no invoice/output/report pollution | TC-H3-CONC-002 |

Boundary values (BV):

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| ``Runner.run`` | exactly two worker threads | both complete without process isolation | TC-H3-CONC-003 |
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from typing import Any

import pytest

from rdetoolkit import flow
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InvoiceData
from tests.v2.contract.fixtures import _generate

_MODES = ("invoice", "excelinvoice", "multidatatile", "rdeformat", "smarttable")


def _overrides(mode: str) -> dict[str, dict[str, str]]:
    extended = {"multidatatile": "MultiDataTile", "rdeformat": "rdeformat"}.get(mode)
    return {"system": {"extended_mode": extended}} if extended is not None else {}


def _runner(root: Path, run_id: str) -> Runner:
    return Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "unpacked",
        run_id_factory=lambda: run_id,
    )


def _snapshot(root: Path, report: Any) -> dict[str, Any]:
    output_files: dict[str, str] = {}
    for path in sorted((root / "data").rglob("*")):
        relative = path.relative_to(root / "data")
        if path.is_file() and "logs" not in relative.parts:
            output_files[str(relative)] = path.read_text(encoding="utf-8", errors="replace")
    invoice_files = {
        name: json.loads(value)
        for name, value in output_files.items()
        if name.endswith("invoice/invoice.json")
    }
    return {
        "report": {
            "status": report.status,
            "mode": report.mode,
            "iterations": [
                {
                    "index": iteration["index"],
                    "status": iteration["status"],
                    "datatile_id": iteration.get("datatile_id"),
                }
                for iteration in report.iterations
            ],
            "error": report.error,
        },
        "invoices": invoice_files,
        "outputs": output_files,
    }


@pytest.mark.parametrize("mode", _MODES)
def test_two_threaded_runners_match_isolated_execution__tc_h3_conc_001_003(
    tmp_path: Path,
    mode: str,
) -> None:
    """TC-H3-CONC-001..003: two distinct roots are isolated in every mode."""
    # Given: one isolated baseline and two identical roots for concurrent runs
    baseline_root = tmp_path / "baseline"
    roots = (tmp_path / "left", tmp_path / "right")
    for root in (baseline_root, *roots):
        _generate.materialize_sut_case(mode, root)

    @flow
    def isolated_flow(invoice: InvoiceData) -> None:
        assert invoice.raw

    baseline_report = _runner(baseline_root, "baseline").run(isolated_flow, **_overrides(mode))
    expected = _snapshot(baseline_root, baseline_report)
    barrier = Barrier(2)

    @flow
    def concurrent_flow(invoice: InvoiceData) -> None:
        assert invoice.raw
        barrier.wait(timeout=10)

    def execute(root: Path, run_id: str) -> dict[str, Any]:
        report = _runner(root, run_id).run(concurrent_flow, **_overrides(mode))
        return _snapshot(root, report)

    # When: two Runner instances execute simultaneously in separate threads
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(execute, root, name) for root, name in zip(roots, ("left", "right"), strict=True)]
        actual = [future.result(timeout=30) for future in futures]

    # Then: each result matches isolated execution and therefore cannot contain
    # paths, invoices, or report state from the sibling root
    assert actual == [expected, expected]
