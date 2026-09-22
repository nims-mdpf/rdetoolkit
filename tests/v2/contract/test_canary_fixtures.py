"""Contracts for five real-data canary observations frozen from the v1 SUT.

Equivalence partitions prepared before implementation:

| Family | Partition | Expected | Test IDs |
| --- | --- | --- | --- |
| real canary | invoice | frozen match and v1 mode ``invoice`` | TC-H4-CANARY-001 |
| real canary | ExcelInvoice | frozen match and v1 mode ``Excelinvoice`` | TC-H4-CANARY-002 |
| real canary | MultiDataTile | frozen match and v1 mode ``MultiDataTile`` | TC-H4-CANARY-003 |
| real canary | RDEFormat | frozen match and v1 mode ``rdeformat`` | TC-H4-CANARY-004 |
| real canary | SmartTable | frozen match and v1 mode ``SmartTableInvoice`` | TC-H4-CANARY-005 |
| effective config | imported YAML plus assembly normalization | frozen model and source reproduce execution | TC-H4-CANARY-006 |
| invoice config | ``save_nonshared_raw: false`` | no ``nonshared_raw`` artifact is frozen | TC-H4-CANARY-007 |

Boundary values prepared before implementation:

| Family | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| frozen inventory | exactly five OK-only paths | no synthetic/error snapshot is replaced | TC-H4-CANARY-BV-001 |
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.v2.contract.fixtures import _generate
from tests.v2.contract.observe import pending_freeze_view

_CASES = [
    pytest.param("invoice", id="TC-H4-CANARY-001"),
    pytest.param("excelinvoice", id="TC-H4-CANARY-002"),
    pytest.param("multidatatile", id="TC-H4-CANARY-003"),
    pytest.param("rdeformat", id="TC-H4-CANARY-004"),
    pytest.param("smarttable", id="TC-H4-CANARY-005"),
]

_EXPECTED_V1_MODE_LABELS = {
    "excelinvoice": "Excelinvoice",
    "invoice": "invoice",
    "multidatatile": "MultiDataTile",
    "rdeformat": "rdeformat",
    "smarttable": "SmartTableInvoice",
}


@pytest.mark.parametrize("mode", _CASES)
def test_real_canary_matches_frozen_v1_observation(mode: str) -> None:
    """TC-H4-CANARY-001..005: real inputs retain their v1 OK contract."""
    # Given: an OK-only snapshot frozen by the canonical generator
    snapshot_path = _generate.CANARY_EXPECTED_ROOT / mode / "ok.json"
    fixture: dict[str, Any] = json.loads(snapshot_path.read_text(encoding="utf-8"))
    # When: executing the v1 SUT against the same imported real input
    actual = _generate.run_v1_canary_sut(mode)
    # Then: every normalized primary observation matches the frozen oracle
    assert fixture["case"]["entry"] == "custom_dataset_function"
    assert fixture["case"]["family"] == "canary"
    assert fixture["case"]["mode"] == mode
    assert fixture["case"]["outcome"] == "ok"
    assert fixture["case"]["effective_config"] == _generate.canary_effective_config_record(mode)
    # ``artifact_sha256`` is observed but not yet frozen (Session I-REVIEW-B
    # ruling #1 ritual step (a)); every already-frozen key stays mandatory.
    assert pending_freeze_view(actual, fixture["observed"]) == fixture["observed"]
    assert actual["exit_code"] == 0
    assert actual["callback_count"] >= 1
    status_modes = {
        status["mode"] for status in actual["legacy_return"]["statuses"]
    }
    assert status_modes == {_EXPECTED_V1_MODE_LABELS[mode]}
    if mode == "excelinvoice":
        divided_invoices = {
            path: invoice
            for path, invoice in actual["invoices"].items()
            if path.startswith("data/divided/")
        }
        divided_tile_roots = {
            path.split("/", maxsplit=3)[2]
            for path in actual["output_tree"]["directories"]
            if path.startswith("data/divided/000")
        }
        assert actual["callback_count"] == 2
        assert len(actual["invoices"]) == 2
        assert len(divided_invoices) == 1
        assert divided_tile_roots == {"0001"}
        assert {
            invoice["basic"]["dataName"] for invoice in actual["invoices"].values()
        } == {"CrossBeam550_手動_1.tif", "CrossBeam550_自動_1.tif"}


def test_invoice_canary_honors_nonshared_raw_setting__tc_h4_canary_007() -> None:
    """TC-H4-CANARY-007: imported invoice config disables nonshared raw output."""
    # Given: the frozen invoice canary and its recorded effective v1 Config
    path = _generate.CANARY_EXPECTED_ROOT / "invoice" / "ok.json"
    fixture: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    effective = fixture["case"]["effective_config"]
    # When: inspecting the reproducibility condition and observed output tree
    files = fixture["observed"]["output_tree"]["files"]
    # Then: the imported false value is effective and no nonshared artifact exists
    assert effective["config"]["system"]["save_nonshared_raw"] is False
    assert effective["source"]["path"] == "data/tasksupport/rdeconfig.yaml"
    assert all("/nonshared_raw/" not in item for item in files)


def test_canary_snapshot_inventory_is_five_ok_only__tc_h4_canary_bv_001() -> None:
    """TC-H4-CANARY-BV-001: canary adds five OK snapshots and no error cases."""
    # Given: the generator's real-canary inventory
    snapshots = sorted(_generate.CANARY_EXPECTED_ROOT.rglob("*.json"))
    # When: rendering paths relative to the fixture root
    relative = [path.relative_to(_generate.FIXTURE_ROOT) for path in snapshots]
    # Then: the sorted inventory is exactly one OK snapshot per mode
    assert relative == [
        Path("expected/canary") / mode / "ok.json"
        for mode in ("excelinvoice", "invoice", "multidatatile", "rdeformat", "smarttable")
    ]
