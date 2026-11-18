"""GA620 EP/BV: every injected invoice carries ``tasksupport/invoice.schema.json``.

EP table
========

=================================  ==============================  ===========================================  ===========
Unit                               Partition                       Expected                                     Test ID
=================================  ==============================  ===========================================  ===========
Runner-injected ``InvoiceData``    each of the five modes          ``schema`` equals the tasksupport schema     GA620-EP-1
``set_custom_fields`` default      invoice mode, no ``schema=``    values cast by the tasksupport schema        GA620-EP-2
``InvoiceService.invariant_inv..``  invoice / MultiDataTile / RDEf  ``schema`` loaded from ``tasksupport``       GA620-EP-3
``_early_exit_invoice``            original SmartTable table tile  ``schema`` loaded from ``tasksupport``       GA620-EP-4
=================================  ==============================  ===========================================  ===========

BV table
========

=================================  ==============================  ===========================================  ===========
Unit                               Boundary                        Expected                                     Test ID
=================================  ==============================  ===========================================  ===========
``InvoiceService.invariant_inv..``  per-tile modes / empty input    still ``None`` (no invariant invoice)        GA620-BV-1
=================================  ==============================  ===========================================  ===========
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit import flow, workflows
from rdetoolkit.domain.invoice_service import InvoiceService
from rdetoolkit.modes.smarttable import _early_exit_invoice
from rdetoolkit.nodes import set_custom_fields
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import InvoiceData
from tests.v2.contract.fixtures import _generate

_MODES = ["invoice", "excelinvoice", "multidatatile", "smarttable", "rdeformat"]
_EXTENDED = {"multidatatile": "MultiDataTile", "rdeformat": "rdeformat"}


def _schema_of(data_root: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((data_root / "tasksupport" / "invoice.schema.json").read_text(encoding="utf-8"))
    return loaded


@pytest.mark.parametrize("mode", _MODES)
def test_injected_invoice_carries_the_schema__ga620_ep_1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    """GA620-EP-1: the injected invoice holds the tasksupport schema in every mode."""
    # Given: a real dataset for each processing mode
    _generate.materialize_sut_case(mode, tmp_path)
    monkeypatch.chdir(tmp_path)
    expected = _schema_of(tmp_path / "data")
    seen: list[dict[str, Any] | None] = []

    @flow
    def pipeline(invoice: InvoiceData) -> None:
        seen.append(None if invoice.schema is None else dict(invoice.schema))

    # When: running the v2 public entry
    config = {"system": {"extended_mode": _EXTENDED.get(mode), "save_thumbnail_image": False}}
    report = workflows.run(flow=pipeline, config=config)

    # Then: every tile's invoice carries the schema from tasksupport
    assert report.status == "success", report.error
    assert seen
    assert all(schema == expected for schema in seen)


def test_set_custom_fields_defaults_to_the_injected_schema__ga620_ep_2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GA620-EP-2: in invoice mode ``set_custom_fields`` needs no ``schema=``."""
    # Given: an invoice-mode dataset whose schema declares an integer custom field
    _generate.materialize_sut_case("invoice", tmp_path)
    monkeypatch.chdir(tmp_path)
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://rde.nims.go.jp/rde/dataset-templates/ga620/invoice.schema.json",
        "type": "object",
        "required": [],
        "properties": {
            "custom": {
                "type": "object",
                "label": {"ja": "固有情報", "en": "Custom"},
                "required": [],
                "properties": {"count": {"type": "integer", "label": {"ja": "回数", "en": "Count"}}},
            },
        },
    }
    (tmp_path / "data" / "tasksupport" / "invoice.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    results: list[Any] = []

    @flow
    def pipeline(invoice: InvoiceData) -> None:
        results.append(set_custom_fields(invoice, {"count": "12 mm"}).raw["custom"]["count"])

    # When: the flow updates custom without passing schema=
    report = workflows.run(flow=pipeline, config={"system": {"save_thumbnail_image": False}})

    # Then: the run succeeds instead of raising "No invoice schema", and the value is cast
    assert report.status == "success", report.error
    assert results == [12]


def _invariant_root(tmp_path: Path, *, inputs: bool = True) -> Path:
    root = tmp_path / "data"
    (root / "invoice").mkdir(parents=True)
    (root / "tasksupport").mkdir()
    (root / "inputdata").mkdir()
    if inputs:
        (root / "inputdata" / "sample.txt").write_text("x", encoding="utf-8")
    (root / "invoice" / "invoice.json").write_text(json.dumps({"basic": {"dataName": "n"}}), encoding="utf-8")
    (root / "tasksupport" / "invoice.schema.json").write_text(json.dumps({"properties": {}}), encoding="utf-8")
    return root


@pytest.mark.parametrize("mode", [ModeKind.invoice, ModeKind.multidatatile, ModeKind.rdeformat])
def test_invariant_invoice_loads_the_schema__ga620_ep_3(tmp_path: Path, mode: ModeKind) -> None:
    """GA620-EP-3: the shared invoice of the invariant modes carries the schema."""
    # Given: a data root with an invoice and its schema
    root = _invariant_root(tmp_path)
    # When: the service loads the invariant invoice
    invoice = InvoiceService().invariant_invoice(mode, data_root=root)
    # Then: the schema is the tasksupport file
    assert invoice is not None
    assert invoice.schema == {"properties": {}}


@pytest.mark.parametrize("mode", [ModeKind.excelinvoice, ModeKind.smarttable])
def test_per_tile_modes_have_no_invariant_invoice__ga620_bv_1(tmp_path: Path, mode: ModeKind) -> None:
    """GA620-BV-1: per-tile modes and an empty invoice-mode input keep returning ``None``."""
    # Given: a data root for a per-tile mode, and an empty invoice-mode input without invoice.json
    root = _invariant_root(tmp_path)
    empty = _invariant_root(tmp_path / "empty", inputs=False)
    (empty / "invoice" / "invoice.json").unlink()
    # When/Then: no invariant invoice is produced
    assert InvoiceService().invariant_invoice(mode, data_root=root) is None
    assert InvoiceService().invariant_invoice(ModeKind.invoice, data_root=empty) is None


def test_early_exit_invoice_loads_the_schema__ga620_ep_4(tmp_path: Path) -> None:
    """GA620-EP-4: the original-table tile's invoice carries the schema."""
    # Given: a tile invoice and the tasksupport schema
    invoice_dir = tmp_path / "divided" / "0001" / "invoice"
    invoice_dir.mkdir(parents=True)
    (invoice_dir / "invoice.json").write_text(json.dumps({"basic": {"dataName": "old"}}), encoding="utf-8")
    schema_path = tmp_path / "tasksupport" / "invoice.schema.json"
    schema_path.parent.mkdir()
    schema_path.write_text(json.dumps({"properties": {"custom": {}}}), encoding="utf-8")
    # When: the EarlyExit invoice is published
    prepared = _early_exit_invoice(
        table=Path("smarttable_x.csv"),
        invoice_dir=invoice_dir,
        invoice_org=tmp_path / "absent.json",
        schema_path=schema_path,
    )
    # Then: the returned invoice carries the schema
    assert prepared.invoice is not None
    assert prepared.invoice.schema == {"properties": {"custom": {}}}
