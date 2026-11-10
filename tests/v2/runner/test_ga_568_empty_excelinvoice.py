"""GA568 EP/BV: reject an Excel invoice with headers but no data rows."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

import openpyxl
import pytest

from rdetoolkit import flow, workflows
from rdetoolkit.errors import RdeValidationError
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.runner.iterator import iterate_tiles, reject_empty_excelinvoice
from rdetoolkit.runner.mode_resolver import ModeKind
from tests.v2.contract.fixtures import _generate

_HEADERS = [["", "basic", "basic"], ["name", "dataName", "dataOwnerId"], ["Input filename", "Data name", "Data owner ID"]]
_WORKBOOK = "contract_excel_invoice.xlsx"
#: A formula cell openpyxl wrote: ``<c r="A5"><f>...</f><v /></c>``.
_FORMULA_CELL = re.compile(r'<c r="([A-Z]+\d+)"([^>]*)><f>(.*?)</f><v\s*/>(?:</v>)?</c>')


def _empty_case(root: Path, *, one_row: bool = False) -> None:
    _generate.materialize_sut_case("excelinvoice", root)
    rows = [*_HEADERS]
    if one_row:
        rows.append(["test_child1.txt", "tile", "0" * 56])
    _generate.write_excelinvoice_registration_sheet(root / "data" / "inputdata" / _WORKBOOK, rows)


def _cache_empty_formula_results(path: Path) -> None:
    """Store ``""`` as every formula's cached result, as Excel/LibreOffice save it.

    openpyxl writes formulas without a cached value; a spreadsheet application
    that recalculates a blank form stores ``t="str"`` and an empty ``<v>``.
    """
    rewritten = path.with_suffix(".tmp")
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(rewritten, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            payload = source.read(item.filename)
            if item.filename.startswith("xl/worksheets/sheet"):
                payload = _FORMULA_CELL.sub(r'<c r="\1"\2 t="str"><f>\3</f><v></v></c>', payload.decode()).encode()
            target.writestr(item, payload)
    rewritten.replace(path)


def _formula_form_case(root: Path, *, keep_invoice: bool, cached: bool) -> None:
    """Materialize the #588 blank form: header rows plus formula-only data rows.

    The only input is the workbook. Rows 5-9 hold formulas in the file-name
    and owner-id columns that evaluate to ``""``; every other cell is empty.

    Args:
        root: SUT working directory.
        keep_invoice: Whether ``data/invoice/invoice.json`` is provided.
        cached: Whether the formulas carry cached ``""`` results.
    """
    _generate.materialize_sut_case("excelinvoice", root)
    inputdata = root / "data" / "inputdata"
    for path in inputdata.iterdir():
        path.unlink()
    if not keep_invoice:
        (root / "data" / "invoice" / "invoice.json").unlink()
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "invoice_form"
    sheet.append(["invoiceList_format_id", "Sample_RDE_DataSet", None])
    for row in _HEADERS:
        sheet.append([value or None for value in row])
    for number in range(5, 10):
        sheet[f"A{number}"] = f'=IF(B{number}<>"",B{number}&".txt","")'
        sheet[f"C{number}"] = f'=IFERROR(VLOOKUP(B{number},Z:Z,1,FALSE),"")'
    workbook.create_sheet("generalTerm").append(["term_id", "key_name"])
    workbook.create_sheet("specificTerm").append(["sample_class_id", "term_id", "key_name"])
    workbook.save(inputdata / _WORKBOOK)
    if cached:
        _cache_empty_formula_results(inputdata / _WORKBOOK)


def _run_entry(root: Path, entry: str, calls: list[str]) -> None:
    """Run one public entry and assert its entry-specific empty-form outcome."""

    def callback(srcpaths: Any, resource_paths: Any) -> None:
        calls.append("callback")

    @flow
    def pipeline() -> None:
        calls.append("flow")

    config = {"system": {"save_thumbnail_image": False}}
    if entry == "v1":
        with pytest.raises(SystemExit) as raised:
            workflows.run(custom_dataset_function=callback, config=config)
        assert raised.value.code == 1
    else:
        report = workflows.run(flow=pipeline, config=config)
        assert report.status == "failed"
        assert report.mode == "excelinvoice"
        assert report.iterations == []
        assert report.error is not None and report.error["code"] == 4004
    text = (root / "data" / "job.failed").read_text(encoding="utf-8")
    if entry == "v1":
        assert text == "ErrorCode=999\nErrorMessage=Error: Please check the logs and code, then try again.\n"
    else:
        assert "ErrorCode=4004\n" in text


@pytest.mark.parametrize("entry", ["v1", "v2"])
def test_empty_excelinvoice_is_an_input_error__ga568_neg_1_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry: str) -> None:
    """GA568-NEG-1/2: no callback/flow runs and the right entry-specific code survives."""
    # Given: an Excel invoice with a valid header and zero data rows
    _empty_case(tmp_path)
    monkeypatch.chdir(tmp_path)
    calls: list[str] = []

    def callback(srcpaths: Any, resource_paths: Any) -> None:
        calls.append("callback")

    @flow
    def pipeline() -> None:
        calls.append("flow")

    # When: executing either public entry
    config = {"system": {"save_thumbnail_image": False}}
    if entry == "v1":
        with pytest.raises(SystemExit) as raised:
            workflows.run(custom_dataset_function=callback, config=config)
        assert raised.value.code == 1
    else:
        report = workflows.run(flow=pipeline, config=config)
        assert report.status == "failed"
        assert report.error is not None and report.error["code"] == 4004
        assert "data rows" in report.error["message"]
        assert "Add" in report.error["remediation"]
    # Then: the v1 frozen text or the v2 input-specific diagnostic is published
    text = (tmp_path / "data" / "job.failed").read_text(encoding="utf-8")
    if entry == "v1":
        assert text == "ErrorCode=999\nErrorMessage=Error: Please check the logs and code, then try again.\n"
    else:
        assert "ErrorCode=4004\n" in text
        assert "fix the flow" not in text
    assert calls == []


def test_iterator_rejects_zero_rows__ga568_bv_1(tmp_path: Path) -> None:
    """GA568-BV-1: detection belongs to iteration before post-validation."""
    # Given: the issue's zero-row workbook
    _empty_case(tmp_path)
    data = tmp_path / "data"
    # When: discovering its tiles directly
    with pytest.raises(RdeValidationError) as raised:
        list(iterate_tiles(ModeKind.excelinvoice, data / "inputdata", data / "temp", data))
    # Then: a catalogued input error replaces misleading output validation
    assert raised.value.code == 4004


def test_iterator_accepts_one_row__ga568_bv_2(tmp_path: Path) -> None:
    """GA568-BV-2: the smallest nonempty workbook still produces exactly one tile."""
    # Given: the same form with one valid registration row
    _empty_case(tmp_path, one_row=True)
    data = tmp_path / "data"
    # When: discovering tiles
    tiles = list(iterate_tiles(ModeKind.excelinvoice, data / "inputdata", data / "temp", data))
    # Then: the row is neither skipped nor duplicated
    assert len(tiles) == 1


def test_missing_invoice_sheet_keeps_existing_error__ga568_neg_3(tmp_path: Path) -> None:
    """GA568-NEG-3: a malformed workbook is distinct from an empty valid form."""
    # Given: the frozen missing-sheet workbook
    _generate._materialize_oracle_case("excelinvoice", tmp_path, zero_rows=True)
    data = tmp_path / "data"
    # When: discovering tiles
    with pytest.raises(StructuredError) as raised:
        list(iterate_tiles(ModeKind.excelinvoice, data / "inputdata", data / "temp", data))
    # Then: the existing v1 error remains intact
    assert raised.value.ecode == 1
    assert "no sheet" in str(raised.value)


@pytest.mark.parametrize("cached", [True, False], ids=["cached_empty", "uncalculated"])
@pytest.mark.parametrize("keep_invoice", [True, False], ids=["with_invoice", "without_invoice"])
@pytest.mark.parametrize("entry", ["v1", "v2"])
def test_formula_only_rows_are_no_data_rows__ga588_neg_1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry: str,
    keep_invoice: bool,
    cached: bool,
) -> None:
    """GA588-NEG-1: a blank form whose rows hold only ``""`` formulas is an empty form.

    The #588 report: such a form, the only input and without
    ``data/invoice/invoice.json``, ended in 4003 RequiredArtifactMissing on
    both entries because pre-validation required the invoice before the
    empty form was diagnosed. v1.7.1 published 999 for the same input.
    """
    # Given: the issue's blank template, with or without the run invoice
    _formula_form_case(tmp_path, keep_invoice=keep_invoice, cached=cached)
    monkeypatch.chdir(tmp_path)
    calls: list[str] = []
    # When / Then: the header-only outcome (999 v1 / 4004 flow), no 4003
    _run_entry(tmp_path, entry, calls)
    assert calls == []


@pytest.mark.parametrize("cached", [True, False], ids=["cached_empty", "uncalculated"])
def test_iterator_rejects_formula_only_rows__ga588_bv_1(tmp_path: Path, cached: bool) -> None:
    """GA588-BV-1: tile discovery sees no data rows in the formula-only form."""
    # Given: the blank formula form
    _formula_form_case(tmp_path, keep_invoice=True, cached=cached)
    data = tmp_path / "data"
    # When: discovering its tiles directly
    with pytest.raises(RdeValidationError) as raised:
        list(iterate_tiles(ModeKind.excelinvoice, data / "inputdata", data / "temp", data))
    # Then: the catalogued empty-input error is raised
    assert raised.value.code == 4004


def test_preflight_rejects_formula_only_rows__ga588_bv_2(tmp_path: Path) -> None:
    """GA588-BV-2: the pre-validation probe diagnoses the form without unpacking anything."""
    # Given: the blank formula form and no run invoice
    _formula_form_case(tmp_path, keep_invoice=False, cached=True)
    data = tmp_path / "data"
    # When: probing the input before pre-validation
    with pytest.raises(RdeValidationError) as raised:
        reject_empty_excelinvoice(ModeKind.excelinvoice, data / "inputdata")
    # Then: the empty-input code is raised and nothing was written
    assert raised.value.code == 4004
    assert not (data / "temp").exists()


def test_preflight_accepts_one_row__ga588_bv_3(tmp_path: Path) -> None:
    """GA588-BV-3: one registration row passes the probe; other modes are never probed."""
    # Given: the smallest nonempty form
    _empty_case(tmp_path, one_row=True)
    inputdata = tmp_path / "data" / "inputdata"
    # When / Then: probing returns without raising
    reject_empty_excelinvoice(ModeKind.excelinvoice, inputdata)
    # And: an empty form is not probed outside the excelinvoice mode
    _formula_form_case(tmp_path / "other", keep_invoice=True, cached=True)
    reject_empty_excelinvoice(ModeKind.invoice, tmp_path / "other" / "data" / "inputdata")


def test_preflight_leaves_malformed_workbook_to_existing_route__ga588_neg_2(tmp_path: Path) -> None:
    """GA588-NEG-2: the probe never replaces the existing malformed-workbook error."""
    # Given: the frozen missing-sheet workbook
    _generate._materialize_oracle_case("excelinvoice", tmp_path, zero_rows=True)
    # When / Then: probing is silent, so tile discovery still reports "no sheet"
    reject_empty_excelinvoice(ModeKind.excelinvoice, tmp_path / "data" / "inputdata")


def test_nonempty_form_without_invoice_keeps_4003__ga588_neg_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA588-NEG-3: a form with data rows still needs the run invoice (4003 unchanged)."""
    # Given: one registration row and no data/invoice/invoice.json
    _empty_case(tmp_path, one_row=True)
    (tmp_path / "data" / "invoice" / "invoice.json").unlink()
    monkeypatch.chdir(tmp_path)

    @flow
    def pipeline() -> None:
        pass

    # When: running the flow entry
    report = workflows.run(flow=pipeline, config={"system": {"save_thumbnail_image": False}})
    # Then: the pre-validation artifact error is unchanged
    assert report.error is not None and report.error["code"] == 4003
