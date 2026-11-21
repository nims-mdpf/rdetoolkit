"""Acceptance cases for #782: a blank-only undefined mapping column.

v1 skips a blank cell before it looks its column up in the schema, so a column
whose destination the invoice schema does not declare is ignored while every
cell in it is blank. The v2 preflight reports an unknown destination only when
at least one data row would actually write to it. Structural header errors stay
strict regardless of the cells.

| API | Partition / boundary | Expected | Test ID |
| --- | --- | --- | --- |
| validate | ``custom/`` / ``basic/`` / ``sample/`` undefined, every cell NaN or empty | ``()`` | ST782-P01 |
| validate | undefined column of whitespace-only cells | ``()`` | ST782-B01 |
| validate | undefined column, header-only table | ``()`` | ST782-B02 |
| validate | undefined column, one non-blank cell among blanks | unknown-destination diagnostic, no cell value | ST782-N01 |
| validate | structural header errors with blank-only cells | still reported | ST782-N02 |
| Runner vs ``workflows.run`` | blank-only undefined columns in the real table | both complete, same artifacts, same as without the columns | ST782-E01 |
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import openpyxl
import pytest

from rdetoolkit import workflows
from rdetoolkit.core.flow import flow
from rdetoolkit.fileops import writef_json
from rdetoolkit.modes.smarttable_validation import validate_smarttable_mapping
from rdetoolkit.runner.lifecycle import Runner
from tests.v2.contract.fixtures import _generate
from tests.v2.contract.observe import observe_v2_run

_UNDEFINED_HEADERS = ("custom/area_information", "basic/unknownField", "sample/unknownField")


def _files(root: Path, headers: list[str], rows: list[list[str]]) -> tuple[Path, Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    table = root / "smarttable_case.csv"
    with table.open("w", encoding="utf-8", newline="") as stream:
        csv.writer(stream).writerows([["display"] * len(headers), headers, *rows])
    schema = root / "invoice.schema.json"
    writef_json(
        schema,
        {"type": "object", "properties": {"custom": {"type": "object", "properties": {"count": {"type": "integer"}}}}},
    )
    return table, schema, root / "metadata-def.json"


@pytest.mark.parametrize("header", _UNDEFINED_HEADERS)
@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_blank_only_undefined_column_is_ignored__st782_p01_b01(tmp_path: Path, header: str, blank: str) -> None:
    # Given: an undefined destination whose cells are empty or whitespace in every row
    files = _files(tmp_path, ["basic/dataName", header], [["first", blank], ["second", ""]])
    # When: validating the table before rows run
    diagnostics = validate_smarttable_mapping(*files)
    # Then: the column is ignored as v1 ignores it
    assert diagnostics == ()


@pytest.mark.parametrize("header", _UNDEFINED_HEADERS)
def test_header_only_undefined_column_is_ignored__st782_b02(tmp_path: Path, header: str) -> None:
    # Given: a table with mapping headers and no data row
    files = _files(tmp_path, ["basic/dataName", header], [])
    # When / Then: nothing would be written to the undefined destination
    assert validate_smarttable_mapping(*files) == ()


@pytest.mark.parametrize(
    ("header", "reason"),
    [
        ("custom/area_information", "unknown_custom_field"),
        ("basic/unknownField", "unknown_invoice_field"),
        ("sample/unknownField", "unknown_invoice_field"),
    ],
)
def test_one_value_in_undefined_column_is_reported__st782_n01(tmp_path: Path, header: str, reason: str) -> None:
    # Given: an undefined destination that is blank except for one later row
    files = _files(tmp_path, ["basic/dataName", header], [["first", ""], ["second", " "], ["third", "SECRET-PAYLOAD"]])
    # When: validating the table before rows run
    diagnostics = validate_smarttable_mapping(*files)
    # Then: the header is rejected without leaking the cell value
    assert len(diagnostics) == 1
    assert (diagnostics[0].row, diagnostics[0].column, diagnostics[0].reason) == (2, header, reason)
    assert "SECRET-PAYLOAD" not in json.dumps(asdict(diagnostics[0]))


@pytest.mark.parametrize(
    ("headers", "reason"),
    [
        (["basic/dataName", "basic/dataName"], "duplicate_mapping"),
        (["basic/dataName", "custom/"], "invalid_mapping_path"),
        (["basic/dataName", "sample/specificAttributes.only"], "invalid_mapping_path"),
        (["basic/dataName", "inputdataX"], "invalid_mapping_path"),
        (["basic/dataName", "typo/field"], "unknown_mapping_prefix"),
    ],
)
def test_structural_header_errors_ignore_blank_cells__st782_n02(tmp_path: Path, headers: list[str], reason: str) -> None:
    # Given: a malformed mapping header over blank-only cells
    files = _files(tmp_path, headers, [["first", ""], ["second", ""]])
    # When: validating the table
    diagnostics = validate_smarttable_mapping(*files)
    # Then: the structural error is still reported from the header alone
    assert [item.reason for item in diagnostics] == [reason]


def test_missing_mapping_headers_ignore_blank_cells__st782_n02_missing(tmp_path: Path) -> None:
    # Given: descriptive columns only, without any mapping header
    files = _files(tmp_path, ["Notes"], [[""]])
    # When / Then: the absent mapping contract stays strict
    assert [item.reason for item in validate_smarttable_mapping(*files)] == ["missing_mapping_headers"]


# ---------------------------------------------------------------------------
# Entry parity on the registered SmartTable input
# ---------------------------------------------------------------------------


@flow(id="test.smarttable.blank_undefined.782")
def _noop_flow() -> None:
    """Leave every artifact to the Runner."""


def _noop_callback(*_args: Any, **_kwargs: Any) -> None:
    """Leave every artifact to the callback entry."""


def _stage(root: Path, *, add_blank_columns: bool) -> None:
    _generate._materialize_oracle_case("smarttable", root)  # noqa: SLF001
    if not add_blank_columns:
        return
    table = root / "data" / "inputdata" / "smarttable_full.xlsx"
    workbook = openpyxl.load_workbook(table)
    sheet = workbook.worksheets[0]
    for header in _UNDEFINED_HEADERS:
        column = sheet.max_column + 1
        sheet.cell(row=1, column=column, value="Shared column")
        sheet.cell(row=2, column=column, value=header)
    workbook.save(table)


def _run_flow(root: Path) -> dict[str, Any]:
    report = Runner(root=root, inputdata_path=root / "data" / "inputdata", unpacked_dir_path=root / "data" / "temp").run(_noop_flow)
    assert report.status == "success", report.error
    return observe_v2_run(root)


def _run_callback(root: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.chdir(root)
    workflows.run(custom_dataset_function=_noop_callback)
    assert not (root / "data" / "job.failed").exists()
    return observe_v2_run(root)


def _comparable(observed: dict[str, Any]) -> dict[str, Any]:
    return {key: observed[key] for key in ("output_tree", "invoices", "raw_sha256")}


def test_flow_and_callback_entries_agree_on_blank_undefined_columns__st782_e01(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: the template-shared table carrying undefined destinations left blank in every row
    _stage(flow_root := tmp_path / "flow", add_blank_columns=True)
    _stage(callback_root := tmp_path / "callback", add_blank_columns=True)
    _stage(baseline_root := tmp_path / "baseline", add_blank_columns=False)
    # When: running the same input through both public entries
    flow_observed = _run_flow(flow_root)
    callback_observed = _run_callback(callback_root, monkeypatch)
    baseline_observed = _run_flow(baseline_root)
    # Then: both entries register the sheet identically, as if the columns were absent
    assert _comparable(flow_observed) == _comparable(callback_observed)
    assert flow_observed["invoices"] == baseline_observed["invoices"]
    assert flow_observed["output_tree"] == baseline_observed["output_tree"]
