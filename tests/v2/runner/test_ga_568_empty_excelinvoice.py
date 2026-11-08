"""GA568 EP/BV: reject an Excel invoice with headers but no data rows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rdetoolkit import flow, workflows
from rdetoolkit.errors import RdeValidationError
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.runner.iterator import iterate_tiles
from rdetoolkit.runner.mode_resolver import ModeKind
from tests.v2.contract.fixtures import _generate

_HEADERS = [["", "basic", "basic"], ["name", "dataName", "dataOwnerId"], ["Input filename", "Data name", "Data owner ID"]]


def _empty_case(root: Path, *, one_row: bool = False) -> None:
    _generate.materialize_sut_case("excelinvoice", root)
    rows = [*_HEADERS]
    if one_row:
        rows.append(["test_child1.txt", "tile", "0" * 56])
    _generate.write_excelinvoice_registration_sheet(root / "data" / "inputdata" / "contract_excel_invoice.xlsx", rows)


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
