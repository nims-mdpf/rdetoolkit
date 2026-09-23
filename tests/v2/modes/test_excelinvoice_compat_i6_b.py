"""ExcelInvoice mode-specific v1 compatibility for Session I6-B (rulings #2, #3).

The frozen contract fixtures cover exactly one ExcelInvoice shape (two
registered rows plus a flat archive). The mode's real behaviour is decided by
``impl/input_controller.ExcelInvoiceChecker`` and the archive parsers it
selects, and those branches are unreachable from the frozen corpus. This module
therefore uses v1 itself as a **dynamic oracle**: each scenario is materialized
twice, run once through the isolated v1 worker
(``_generate._execute_v1_observation``, the same worker that froze the static
fixtures) and once through the v2 Runner, and the two observations are
compared. No fixture under ``fixtures/expected/`` is read or written here.

Session I6-B changed no ExcelInvoice production code: every scenario below is
already reproduced by the shared Core wiring that Session I6-1 installed, and
these tests exist so a later change cannot regress it silently.

Ruling #2 (Excel-file identity) is pinned observationally. v2 re-discovers the
workbook by extension from ``rawfiles + inputdata``
(``domain/invoice_service._first_matching``) instead of carrying v1's
``excel_invoice_files[0]`` on the tile plan. That is only safe if a v1-valid
ExcelInvoice run can never present a second candidate that wins; TC-EV-026 and
TC-EV-027 show v1 rejects the two ways inputdata could hold a second workbook,
and TC-EP-023 shows an ``.xlsx`` arriving through the archive does not displace
the inputdata workbook.

Known asymmetry, verified bounded here: v1 creates ``data/temp`` unconditionally
before running any input checker (``workflows.check_files_result`` calls
``StorageDir.get_specific_outputdir(True, "temp")``), while v2 creates it only
when a tile exists or the archive is actually unpacked. On the scenarios that
fail *before* unpacking, the whole observable difference is that one directory
entry; the tests assert the difference set exactly, so any further divergence
fails.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-I6-B-EP-020 | no archive | workbook only, N rows | N tiles, every tile ``rawfiles=()``, full v1 parity |
| TC-I6-B-EP-021 | broadcast | one unpacked group, N rows | the single group is reused by every tile, full v1 parity |
| TC-I6-B-EP-022 | one group per row | N unpacked folders, N rows | tiles pair up with folders, full v1 parity |
| TC-I6-B-EP-023 | identity | ``.xlsx`` inside the archive | the inputdata workbook still builds the invoices, full v1 parity |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-I6-B-EV-024 | count mismatch | 3 unpacked folders, 2 rows | v1 ``StructuredError`` verbatim, full v1 parity |
| TC-I6-B-EV-025 | blank row | empty row between data rows | v1 ``StructuredError`` verbatim, divergence bounded to ``data/temp/`` |
| TC-I6-B-EV-026 | identity | two ``*_excel_invoice.xlsx`` | v1 rejects before selection, divergence bounded |
| TC-I6-B-EV-027 | identity | stray ``.xlsx`` in inputdata | v1 rejects before selection, divergence bounded |
"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from rdetoolkit.core.flow import flow
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths
from tests.fixtures.excelinvoice import (
    EXCELINVOICE_ENTRYDATA_SHEET2,
    EXCELINVOICE_ENTRYDATA_SHEET3,
)
from tests.v2.contract.fixtures import _generate
from tests.v2.contract.observe import observe_v2_run, parity_view

_MODE = "excelinvoice"
_WORKBOOK = "data/inputdata/contract_excel_invoice.xlsx"
_ARCHIVE = "data/inputdata/excelinvoice_files.zip"
_OWNER_ID = "0" * 56
#: v1's ``StructuredError`` default code, published verbatim by v2 (§I6-0).
_STRUCTURED_ERROR_CODE = 1
#: The single directory v1 creates before parsing and v2 does not (see module docstring).
_UNPACK_DIRECTORY_GAP = frozenset({"data/temp/"})

#: The five artifact switches ``_generate.oracle_config`` freezes fixtures with.
#: Passing anything else would measure a configuration difference instead of an
#: implementation difference (contracts.md §I6-1 ruling #8).
_V2_OVERRIDES: dict[str, Any] = {
    "system": {
        "extended_mode": "invoice",
        "save_raw": True,
        "save_nonshared_raw": True,
        "save_thumbnail_image": False,
        "magic_variable": False,
    },
    "smarttable": {"save_table_file": False},
}

CaseBuilder = Callable[[Path], None]


@flow
def _noop_flow(paths: InputPaths) -> None:
    """Consume the tile without writing anything the Runner does not own."""
    assert paths.inputdata.is_dir()


# --------------------------------------------------------------------------
# Scenario construction
# --------------------------------------------------------------------------
def _rewrite_archive(root: Path, members: dict[str, bytes]) -> None:
    """Replace the committed archive with deterministic members."""
    path = root / _ARCHIVE
    path.unlink()
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 7, 15, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payload)


def _write_registration_sheet(path: Path, rows: list[list[str | None]]) -> None:
    """Rewrite sheet 1 of the committed workbook, keeping the term sheets."""
    general = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET2, columns=["term_id", "key_name"])
    specific = pd.DataFrame(
        EXCELINVOICE_ENTRYDATA_SHEET3,
        columns=["sample_class_id", "term_id", "key_name"],
    )
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(rows, columns=["invoiceList_format_id", "Sample_RDE_DataSet", ""]).to_excel(
            writer,
            sheet_name="invoice_form",
            index=False,
        )
        general.to_excel(writer, sheet_name="generalTerm", index=False)
        specific.to_excel(writer, sheet_name="specificTerm", index=False)


#: The three header rows every registration sheet carries before its data rows.
_SHEET_HEADER: list[list[str | None]] = [
    ["", "basic", "basic"],
    ["name", "dataName", "dataOwnerId"],
    ["Input filename", "Data name", "Data owner ID"],
]


def _base_case(root: Path) -> None:
    _generate._materialize_oracle_case(_MODE, root)  # noqa: SLF001 -- shared case assembly


def _build_without_archive(root: Path) -> None:
    _base_case(root)
    (root / _ARCHIVE).unlink()


def _build_single_group(root: Path) -> None:
    _base_case(root)
    _rewrite_archive(root, {"test_child1.txt": b"only registered child\n"})


def _build_group_per_row(root: Path) -> None:
    _base_case(root)
    _rewrite_archive(
        root,
        {"dirA/test_child1.txt": b"child one\n", "dirB/test_child2.txt": b"child two\n"},
    )


def _build_extra_group(root: Path) -> None:
    _base_case(root)
    _rewrite_archive(
        root,
        {
            "dirA/test_child1.txt": b"child one\n",
            "dirB/test_child2.txt": b"child two\n",
            "dirC/unregistered.txt": b"child three\n",
        },
    )


def _build_workbook_in_archive(root: Path) -> None:
    _base_case(root)
    _rewrite_archive(
        root,
        {
            # Deliberately sorts before the registered children so a candidate
            # list ordered by name alone would offer it first.
            "aaa_decoy.xlsx": b"not a workbook, only an extension\n",
            "test_child1.txt": b"excelinvoice child 1\n",
            "test_child2.txt": b"excelinvoice child 2\n",
        },
    )


def _build_blank_row(root: Path) -> None:
    _base_case(root)
    _write_registration_sheet(
        root / _WORKBOOK,
        [
            *_SHEET_HEADER,
            ["test_child1.txt", "test1", _OWNER_ID],
            [None, None, None],
            ["test_child2.txt", "test2", _OWNER_ID],
        ],
    )


def _build_two_workbooks(root: Path) -> None:
    _base_case(root)
    shutil.copy2(root / _WORKBOOK, root / "data/inputdata/second_excel_invoice.xlsx")


def _build_stray_workbook(root: Path) -> None:
    _base_case(root)
    shutil.copy2(root / _WORKBOOK, root / "data/inputdata/aaa_stray.xlsx")


# --------------------------------------------------------------------------
# Oracle / subject harness
# --------------------------------------------------------------------------
def _observe_v1(build: CaseBuilder) -> dict[str, Any]:
    """Run the scenario through the isolated v1 worker and observe it."""
    with tempfile.TemporaryDirectory(prefix="i6b-xls-oracle-") as temporary:
        root = Path(temporary) / "case"
        root.mkdir()
        build(root)
        # The same worker that froze the static fixtures; reusing it keeps the
        # oracle's config, normalization and observation identical to theirs.
        return _generate._execute_v1_observation(_MODE, "ok", root)  # noqa: SLF001


def _observe_v2(
    build: CaseBuilder,
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Any, dict[str, Any]]:
    """Run the same scenario through the v2 Runner and observe it."""
    root.mkdir()
    build(root)
    monkeypatch.chdir(root)
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        # The flow entry unpacks into data/temp, as v1 does (contracts.md §I6-1).
        unpacked_dir_path=root / "data" / "temp",
    )
    return runner.run(_noop_flow, **_V2_OVERRIDES), observe_v2_run(root)


def _tree_divergence(observed: dict[str, Any], oracle: dict[str, Any]) -> set[str]:
    """Return every output-tree entry present on exactly one side."""
    expected = parity_view(oracle)["output_tree"]
    actual = observed["output_tree"]
    return {
        entry
        for group in ("directories", "files")
        for entry in set(actual[group]) ^ set(expected[group])
    }


def _job_failed(root: Path) -> str:
    return _generate.normalize_snapshot(
        (root / "data" / "job.failed").read_text(encoding="utf-8"),
        roots=(root,),
    )


# --------------------------------------------------------------------------
# EP cases
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("build", "tiles", "case_id"),
    [
        pytest.param(_build_without_archive, 2, "TC-I6-B-EP-020", id="TC-I6-B-EP-020"),
        pytest.param(_build_single_group, 2, "TC-I6-B-EP-021", id="TC-I6-B-EP-021"),
        pytest.param(_build_group_per_row, 2, "TC-I6-B-EP-022", id="TC-I6-B-EP-022"),
        pytest.param(_build_workbook_in_archive, 2, "TC-I6-B-EP-023", id="TC-I6-B-EP-023"),
    ],
)
def test_successful_shapes_match_the_v1_oracle(
    build: CaseBuilder,
    tiles: int,
    case_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ExcelInvoice tile shapes reproduce the v1 observation exactly."""
    # Given: one ExcelInvoice shape, observed through the isolated v1 worker
    oracle = _observe_v1(build)
    assert oracle["exit_code"] == 0, case_id
    assert oracle["callback_count"] == tiles

    # When: running the identical input through the v2 Runner
    report, observed = _observe_v2(build, tmp_path / _MODE, monkeypatch)

    # Then: tiles, tree, raw digests and written invoices are all v1-identical
    assert report.status == "success"
    assert len(report.iterations) == tiles
    assert observed == parity_view(oracle)


def test_missing_archive_leaves_every_tile_without_raw_inputs__tc_i6_b_ep_020(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-B-EP-020: without an archive v1 yields one empty tile per row."""
    # Given: the workbook alone, so ``_get_rawfiles`` short-circuits to ``[()] * N``
    oracle = _observe_v1(_build_without_archive)

    # When: running the same input through the v2 Runner
    _report, observed = _observe_v2(_build_without_archive, tmp_path / _MODE, monkeypatch)

    # Then: no raw artifact is published at all, on either side
    assert oracle["raw_sha256"] == {}
    assert observed["raw_sha256"] == {}


def test_single_group_is_broadcast_to_every_row__tc_i6_b_ep_021(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-B-EP-021: one unpacked group is reused by every registered row."""
    # Given: an archive whose members form a single group
    oracle = _observe_v1(_build_single_group)

    # When: running the same input through the v2 Runner
    _report, observed = _observe_v2(_build_single_group, tmp_path / _MODE, monkeypatch)

    # Then: both tiles publish the same single raw file
    assert sorted(observed["raw_sha256"]) == [
        "data/divided/0001/nonshared_raw/test_child1.txt",
        "data/divided/0001/raw/test_child1.txt",
        "data/nonshared_raw/test_child1.txt",
        "data/raw/test_child1.txt",
    ]
    assert observed["raw_sha256"] == parity_view(oracle)["raw_sha256"]


def test_archive_workbook_does_not_displace_the_inputdata_one__tc_i6_b_ep_023(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-B-EP-023: a second ``.xlsx`` reaching rawfiles never builds the invoice.

    The archive member is not a workbook at all, so selecting it would raise
    rather than silently produce different invoices — the assertion below fails
    loudly either way.
    """
    # Given: an archive carrying a decoy ``.xlsx`` alongside the registered files
    oracle = _observe_v1(_build_workbook_in_archive)

    # When: running the same input through the v2 Runner
    report, observed = _observe_v2(_build_workbook_in_archive, tmp_path / _MODE, monkeypatch)

    # Then: the decoy really did reach rawfiles, and the invoices are still v1's
    assert report.status == "success"
    assert "data/raw/aaa_decoy.xlsx" in observed["raw_sha256"]
    assert observed["invoices"] == parity_view(oracle)["invoices"]
    assert observed["invoices"]["data/invoice/invoice.json"]["basic"]["dataName"] == "test1"


# --------------------------------------------------------------------------
# BV / negative cases
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("build", "message", "divergence", "case_id"),
    [
        pytest.param(
            _build_extra_group,
            "Error! The input file and the description in the ExcelInvoice are not consistent.",
            frozenset(),
            "TC-I6-B-EV-024",
            id="TC-I6-B-EV-024",
        ),
        pytest.param(
            _build_blank_row,
            "Error! Blank lines exist between lines",
            _UNPACK_DIRECTORY_GAP,
            "TC-I6-B-EV-025",
            id="TC-I6-B-EV-025",
        ),
        pytest.param(
            _build_two_workbooks,
            "ERROR: more than 1 excelinvoice file list. file num: 2",
            _UNPACK_DIRECTORY_GAP,
            "TC-I6-B-EV-026",
            id="TC-I6-B-EV-026",
        ),
        pytest.param(
            _build_stray_workbook,
            "ERROR: input file should be EXCEL or ZIP file",
            _UNPACK_DIRECTORY_GAP,
            "TC-I6-B-EV-027",
            id="TC-I6-B-EV-027",
        ),
    ],
)
def test_rejected_shapes_match_the_v1_oracle(
    build: CaseBuilder,
    message: str,
    divergence: frozenset[str],
    case_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rejected ExcelInvoice shapes publish v1's own ``job.failed`` verbatim."""
    # Given: an input v1 refuses, observed through the isolated v1 worker
    oracle = _observe_v1(build)
    assert oracle["exit_code"] == 1, case_id
    assert oracle["callback_count"] == 0
    assert oracle["job_failed_text"] == f"ErrorCode={_STRUCTURED_ERROR_CODE}\nErrorMessage={message}\n"

    # When: running the identical input through the v2 Runner
    root = tmp_path / _MODE
    report, observed = _observe_v2(build, root, monkeypatch)

    # Then: the run fails before any tile, with v1's byte-identical job.failed
    assert report.status == "failed"
    assert report.iterations == []
    assert report.error is not None
    assert report.error["code"] == _STRUCTURED_ERROR_CODE
    assert report.error["name"] == "StructuredError"
    assert _job_failed(root) == oracle["job_failed_text"]

    # And: the artifacts agree, up to the one directory v1 pre-creates
    assert observed["raw_sha256"] == parity_view(oracle)["raw_sha256"]
    assert observed["invoices"] == parity_view(oracle)["invoices"]
    assert _tree_divergence(observed, oracle) == set(divergence)
