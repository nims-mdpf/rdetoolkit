"""PR593 EP/BV coverage for file-layout errors combined with an empty form.

EP table (both public entries for NEG-1..5):
| Test ID | Input alongside an empty form | Expected |
| --- | --- | --- |
| PR593-NEG-1 | extra.txt | StructuredError 1, exact invalid-file message |
| PR593-NEG-2 | stray.xlsx | StructuredError 1, exact invalid-file message |
| PR593-NEG-3 | two ZIPs | StructuredError 1, exact ZIP-count message |
| PR593-NEG-4 | two ZIPs and extra.txt | ZIP-count error retains precedence |
| PR593-NEG-5 | second invoice workbook | StructuredError 1, workbook-count message |
| PR593-NEG-6 | each invalid layout above | preflight defers without reading workbook |
| PR593-NEG-7 | OS metadata and Office lock file | EmptyExcelInvoiceError 4004 |
| PR593-NEG-8 | invalid layout and missing invoice.json, both entries | pre-validation error 4003 |

BV table:
| Test ID | Boundary | Expected |
| --- | --- | --- |
| PR593-BV-1 | zero/one ZIP | EmptyExcelInvoiceError 4004, no extraction |
| PR593-BV-2 | missing directory / no workbook | preflight defers |
| PR593-PBT-1 | ZIP count 0..4 and optional extra file | 4004 only for valid layouts |
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

import pytest
from hypothesis import given, strategies as st

from rdetoolkit import flow, workflows
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.impl.input_controller import ExcelInvoiceChecker
from rdetoolkit.runner.iterator import EmptyExcelInvoiceError, reject_empty_excelinvoice
from rdetoolkit.runner.mode_resolver import ModeKind
from tests.v2.runner.test_ga_568_empty_excelinvoice import _formula_form_case

_INVALID_LAYOUTS = [
    pytest.param(("extra.txt",), "ERROR: input file should be EXCEL or ZIP file", id="PR593-NEG-1"),
    pytest.param(("stray.xlsx",), "ERROR: input file should be EXCEL or ZIP file", id="PR593-NEG-2"),
    pytest.param(("one.zip", "two.zip"), "ERROR: more than 1 zipped input files", id="PR593-NEG-3"),
    pytest.param(("one.zip", "two.zip", "extra.txt"), "ERROR: more than 1 zipped input files", id="PR593-NEG-4"),
    pytest.param(
        ("second_excel_invoice.xlsx",),
        "ERROR: more than 1 excelinvoice file list. file num: 2",
        id="PR593-NEG-5",
    ),
]


def _add_files(inputdata: Path, names: tuple[str, ...]) -> None:
    """Add files whose layout must be validated before reading their content."""
    for name in names:
        (inputdata / name).write_text("layout validation must precede content parsing", encoding="utf-8")


@pytest.mark.parametrize("entry", ["v1", "flow"])
@pytest.mark.parametrize(("names", "message"), _INVALID_LAYOUTS)
def test_empty_form_preserves_file_layout_error__pr593_neg_1_5(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry: str,
    names: tuple[str, ...],
    message: str,
) -> None:
    """PR593-NEG-1..5: both entries retain the checker's exact first error."""
    # Given: an empty form, valid invoice/schema and an invalid file layout
    _formula_form_case(tmp_path, keep_invoice=True, cached=True)
    data = tmp_path / "data"
    _add_files(data / "inputdata", names)
    monkeypatch.chdir(tmp_path)
    calls: list[str] = []

    def callback(srcpaths: Any, resource_paths: Any) -> None:
        calls.append("callback")

    @flow
    def pipeline() -> None:
        calls.append("flow")

    # When: running either public entry against the conflicting input errors
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
        assert report.error is not None
        assert report.error["code"] == 1
        assert report.error["name"] == "StructuredError"
        assert report.error["message"] == message

    # Then: no tile runs, and job.failed keeps the exact legacy code and message
    assert calls == []
    assert (data / "job.failed").read_text(encoding="utf-8") == f"ErrorCode=1\nErrorMessage={message}\n"
    assert not any((data / "temp").iterdir())
    assert not (data / "divided").exists()


@pytest.mark.parametrize(("names", "message"), _INVALID_LAYOUTS)
def test_preflight_defers_invalid_layout_without_reading__pr593_neg_6(
    tmp_path: Path, names: tuple[str, ...], message: str,
) -> None:
    """PR593-NEG-6: invalid layouts never reach the preflight workbook reader."""
    # Given: an empty workbook and a layout the checker must reject
    _formula_form_case(tmp_path, keep_invoice=True, cached=True)
    data = tmp_path / "data"
    _add_files(data / "inputdata", names)
    # When: probing the layout before normal validation
    with patch("rdetoolkit.runner.iterator.ExcelInvoiceFile") as reader:
        reject_empty_excelinvoice(ModeKind.excelinvoice, data / "inputdata")
    # Then: normal validation retains ownership of the error, with no I/O effects
    reader.assert_not_called()
    with pytest.raises(StructuredError) as raised:
        ExcelInvoiceChecker(data / "temp").parse(data / "inputdata")
    assert raised.value.ecode == 1
    assert str(raised.value) == message
    assert not (data / "temp").exists()


def test_preflight_ignores_system_files__pr593_neg_7(tmp_path: Path) -> None:
    """PR593-NEG-7: OS metadata and Office lock files do not hide an empty form."""
    # Given: an empty form plus files the checker excludes
    _formula_form_case(tmp_path, keep_invoice=True, cached=True)
    data = tmp_path / "data"
    _add_files(data / "inputdata", (".DS_Store", "~$lock_excel_invoice.xlsx"))
    # When: probing the form
    with pytest.raises(EmptyExcelInvoiceError) as raised:
        reject_empty_excelinvoice(ModeKind.excelinvoice, data / "inputdata")
    # Then: the empty-form diagnostic remains available without creating outputs
    assert raised.value.code == 4004
    assert not (data / "temp").exists()


@pytest.mark.parametrize("entry", ["v1", "flow"])
@pytest.mark.parametrize("names", [("extra.txt",), ("one.zip", "two.zip")], ids=["extra_file", "multiple_zips"])
def test_invalid_layout_keeps_missing_invoice_priority__pr593_neg_8(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry: str, names: tuple[str, ...],
) -> None:
    """PR593-NEG-8: deferred layout errors do not bypass invoice pre-validation."""
    # Given: an empty form, an invalid layout and no invoice.json
    _formula_form_case(tmp_path, keep_invoice=False, cached=True)
    data = tmp_path / "data"
    _add_files(data / "inputdata", names)
    monkeypatch.chdir(tmp_path)
    calls: list[str] = []

    def callback(srcpaths: Any, resource_paths: Any) -> None:
        calls.append("callback")

    @flow
    def pipeline() -> None:
        calls.append("flow")

    # When: either public entry defers the invalid layout to normal validation
    config = {"system": {"save_thumbnail_image": False}}
    if entry == "v1":
        with pytest.raises(SystemExit) as raised:
            workflows.run(custom_dataset_function=callback, config=config)
        assert raised.value.code == 1
    else:
        report = workflows.run(flow=pipeline, config=config)
        assert report.status == "failed"
        assert report.iterations == []
        assert report.error is not None
        assert report.error["code"] == 4003
        assert report.error["name"] == "RequiredArtifactMissing"

    # Then: invoice pre-validation retains its existing priority over layout checks
    error = (data / "job.failed").read_text(encoding="utf-8")
    assert error.startswith("ErrorCode=4003\n")
    assert "invoice/invoice.json" in error
    assert calls == []


@pytest.mark.parametrize("zip_count", [0, 1])
def test_preflight_accepts_valid_archive_counts__pr593_bv_1(tmp_path: Path, zip_count: int) -> None:
    """PR593-BV-1: zero or one archive permits the empty-form diagnostic."""
    # Given: an empty form and a valid number of archives
    _formula_form_case(tmp_path, keep_invoice=False, cached=True)
    data = tmp_path / "data"
    _add_files(data / "inputdata", tuple(f"archive{index}.ZIP" for index in range(zip_count)))
    # When: probing before the missing invoice is validated
    with pytest.raises(EmptyExcelInvoiceError) as raised:
        reject_empty_excelinvoice(ModeKind.excelinvoice, data / "inputdata")
    # Then: layout checks never read or unpack the archive
    assert raised.value.code == 4004
    assert not (data / "temp").exists()


@pytest.mark.parametrize("create_directory", [False, True], ids=["missing_directory", "no_workbook"])
def test_preflight_defers_missing_candidates__pr593_bv_2(tmp_path: Path, create_directory: bool) -> None:
    """PR593-BV-2: no workbook candidate leaves existing diagnostics in charge."""
    # Given: an absent or empty input directory
    inputdata = tmp_path / "inputdata"
    if create_directory:
        inputdata.mkdir()
    # When: probing for an empty Excel invoice
    reject_empty_excelinvoice(ModeKind.excelinvoice, inputdata)
    # Then: probing creates no output and does not reject unrelated input states
    assert inputdata.exists() is create_directory


@pytest.mark.property
@given(zip_count=st.integers(min_value=0, max_value=4), extra_file=st.booleans())
def test_empty_form_diagnostic_requires_valid_layout__pr593_pbt_1(zip_count: int, extra_file: bool) -> None:
    """PR593-PBT-1: only checker-valid layouts may trigger the empty-form error."""
    # Given: an empty form with generated archive counts and an optional extra file
    with TemporaryDirectory() as directory:
        root = Path(directory)
        _formula_form_case(root, keep_invoice=True, cached=True)
        data = root / "data"
        names = tuple(f"archive{index}.zip" for index in range(zip_count))
        if extra_file:
            names += ("extra.txt",)
        _add_files(data / "inputdata", names)
        # When / Then: invalid layouts defer; valid layouts diagnose the empty form
        if zip_count > 1 or extra_file:
            reject_empty_excelinvoice(ModeKind.excelinvoice, data / "inputdata")
        else:
            with pytest.raises(EmptyExcelInvoiceError) as raised:
                reject_empty_excelinvoice(ModeKind.excelinvoice, data / "inputdata")
            assert raised.value.code == 4004
        assert not (data / "temp").exists()
