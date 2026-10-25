"""RDEFormat invoice-stage narrowing against the v1 oracle (Session I6-A).

`RdeFormatModeHandler.invoice_stage_steps` drops the ``structured`` and
``magic`` steps because v1's RDEFormat pipeline
(``processing/factories.py::RDEFormatPipelineBuilder``) has neither
``StructuredInvoiceSaver`` nor ``VariableApplier``. The frozen fixtures cannot
detect that narrowing on their own: both steps are double-gated by
``save_invoice_to_structured`` and ``magic_variable``, and every frozen
observation was generated with both switches ``False``, so removing the
override changes no frozen artifact.

This module therefore compares a v2 Runner run with the v1 observation of the
same input made with both switches ``True`` (and ``basic.dataName`` seeded as
``${filename}`` so the magic variable has something to substitute). Until
Session K1 that v1 run happened here, live; it is now the registered generator
case ``rdeformat/ok__magic_structured`` (K1 ruling #6 item 6), frozen like every
other v1 observation. The committed fixture inputs are not modified: the case is
materialized into a temporary root by the shared ``_generate`` builder.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-I6-A-EP-025 | frozen parity | both gates ``True`` | v2 observation equals the frozen v1 observation (tree minus logs, raw digests, invoices, artifact digests) |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-I6-A-EV-026 | structured step | ``save_invoice_to_structured=True`` | no ``structured/invoice.json`` in any tile (v1 has no StructuredInvoiceSaver) |
| TC-I6-A-EV-027 | magic step | ``magic_variable=True`` | ``${filename}`` survives verbatim in every written invoice (v1 has no VariableApplier) |
| TC-I6-A-EV-028 | oracle sanity | the frozen v1 observation itself | v1 also writes neither artifact, so the comparison is not asserting v2 against v2 |
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.core.flow import flow
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths, InvoiceData
from tests.v2.contract.fixtures import _generate
from tests.v2.contract.frozen import frozen_observed
from tests.v2.contract.observe import parity_pair

_MODE = "rdeformat"

#: The registered v1 case: both invoice-stage gates on, dataName seeded.
_CASE_ID = "v1/rdeformat/ok__magic_structured"

#: Seeded into ``basic.dataName`` so ``magic_variable`` has a substitution to
#: make. v1's RDEFormat pipeline never performs it, so the literal must survive.
_MAGIC_DATA_NAME = _generate.FILENAME_TEMPLATE

_FLOW_CALLS: list[tuple[str, ...]] = []


@flow
def _counting_flow(paths: InputPaths, invoice: InvoiceData) -> None:
    """Record one invocation per tile without writing any artifact."""
    assert invoice.raw
    _FLOW_CALLS.append(tuple(path.name for path in paths.rawfiles))


def _materialize(root: Path) -> None:
    """Assemble the shared rdeformat case and seed the magic data name."""
    _generate.materialize_case(_generate.oracle_case(_CASE_ID), root)


def _v2_overrides() -> dict[str, Any]:
    """Return the v2 configuration the frozen v1 case ran with."""
    return {
        "system": {
            "extended_mode": "rdeformat",
            "save_raw": True,
            "save_nonshared_raw": True,
            "save_thumbnail_image": False,
            "magic_variable": True,
            "save_invoice_to_structured": True,
        },
        "smarttable": {"save_table_file": False},
    }


def _run_v2(root: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Run the eager v2 Runner over the same materialized case."""
    _materialize(root)
    monkeypatch.chdir(root)
    _FLOW_CALLS.clear()
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        # The flow entry unpacks into data/temp, as v1 does (contracts.md §I6-1).
        unpacked_dir_path=root / "data" / "temp",
    )
    return runner.run(_counting_flow, **_v2_overrides())


def _written_invoices(root: Path) -> dict[str, Any]:
    return _generate._invoice_outputs(root / "data")  # noqa: SLF001 -- frozen v1 walker is the contract


def _structured_invoices(root: Path) -> list[str]:
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("structured/invoice.json")
    )


def test_invoice_stage_matches_the_v1_oracle__tc_i6_a_ep_025(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-A-EP-025: with both gates on, v2 still reproduces v1 exactly."""
    # Given: the frozen v1 run with save_invoice_to_structured and
    # magic_variable enabled, over the shared rdeformat case
    expected = frozen_observed(_CASE_ID)
    # When: running the eager v2 Runner over the same input and configuration
    v2_root = tmp_path / "v2"
    report = _run_v2(v2_root, monkeypatch)

    # Then: the run succeeds with the same tile count and identical artifacts
    assert report.status == "success"
    assert len(report.iterations) == expected["callback_count"]
    actual, expected_view = parity_pair(v2_root, expected)
    assert actual == expected_view


def test_structured_invoice_is_never_written__tc_i6_a_ev_026(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-A-EV-026: the absent StructuredInvoiceSaver must stay absent."""
    # Given: a v2 run with save_invoice_to_structured explicitly enabled
    root = tmp_path / "v2"

    # When: the RDEFormat run completes both tiles
    report = _run_v2(root, monkeypatch)

    # Then: no tile exported invoice.json into structured/, unlike every other
    # mode, because v1's RDEFormat pipeline has no StructuredInvoiceSaver
    assert report.status == "success"
    assert _structured_invoices(root) == []


def test_magic_variable_is_never_applied__tc_i6_a_ev_027(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-A-EV-027: the absent VariableApplier must stay absent."""
    # Given: a v2 run with magic_variable enabled and a substitutable dataName
    root = tmp_path / "v2"

    # When: the RDEFormat run completes both tiles
    report = _run_v2(root, monkeypatch)

    # Then: every written invoice still carries the literal placeholder
    assert report.status == "success"
    invoices = _written_invoices(root)
    assert invoices, "the run must write at least one invoice for this to mean anything"
    for relative, invoice in invoices.items():
        assert invoice["basic"]["dataName"] == _MAGIC_DATA_NAME, relative


def test_the_v1_oracle_also_writes_neither_artifact__tc_i6_a_ev_028() -> None:
    """TC-I6-A-EV-028: the oracle itself proves the expectation is v1's, not v2's."""
    # Given: the frozen v1 run with both gates enabled
    expected = frozen_observed(_CASE_ID)
    assert expected["exit_code"] == 0

    # Then: v1 wrote no structured invoice and left the placeholder intact, so
    # TC-I6-A-EP-025 compares v2 against real v1 behavior rather than a guess
    assert [path for path in expected["output_tree"]["files"] if path.endswith("structured/invoice.json")] == []
    assert expected["invoices"]
    for relative, invoice in expected["invoices"].items():
        assert invoice["basic"]["dataName"] == _MAGIC_DATA_NAME, relative
