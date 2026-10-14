"""Session K2-0 (R3): the v1 SmartTable initializer tests, ported onto the v2 builder.

``tests/test_smarttable_invoice_initializer.py`` (19) and
``tests/test_smarttable_invoice_initializer_issue_429.py`` (6) pinned v1's
``SmartTableInvoiceInitializer``, which Phase K2 deletes. Orchestrator ruling R3
(``deletion_coverage.md`` §4): they are not deleted but **ported** with their
original TC ids onto ``SmartTableInvoiceBuilder``.

Each port runs the v2 builder on the inputs of the original test (registered as
family ``k2`` in ``tests/v2/modes/fixtures/smarttable_builder/_freeze.py``) and
asserts twice:

1. the original test's own expectations, transcribed literally (they run even
   while the frozen snapshot is pending);
2. equality with v1's frozen observation of the same inputs (invoice, metadata,
   row dictionary or error, source invoice) -- skipped as ``pending freeze``
   until the K2-0 freeze ritual.

Input deviations from the originals, none of which touches a rule under test:
owner hashes copied from ``tests/samplefile`` are synthetic (fixture PII policy,
TC-H4-PII-003), including TC-EP-004's CSV owner; the R3 inputs have no
metadata-def.json, exactly like the originals' work areas.

Equivalence partitions (EP), ``tests/test_smarttable_invoice_initializer.py``:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``build`` | two rows of one run, source mutated in between | ``sample.ownerId`` = ``basic.dataOwnerId`` | TC-EP-001 |
| ``InvoiceService.prepare_tile`` | SmartTable tile without a row CSV | StructuredError "No SmartTable row CSV file found" | TC-EP-002 |
| ``build`` | ``basic.dataOwnerId`` missing | warning, inherited ``sample.ownerId`` kept | TC-EP-003 |
| ``build`` | CSV ``sample/ownerId`` column | CSV value wins | TC-EP-004 |
| ``build`` | ``sample/names`` without ``sample/sampleId`` | dummy sample cleared | TC-EP-005 |
| ``build`` | ``sample/names`` + UUID ``sampleId`` | reference kept, no clearing | TC-EP-006 |
| ``build`` | no ``sample/`` column | sample untouched | TC-EP-007 |
| ``build`` | ``sample/sampleId`` column empty | new-sample clearing | TC-EP-008 |
| ``build`` | names only (Issue #389) | ownerId corrected after clearing | TC-EP-009 |
| ``build`` | blank fixed-header sample columns | cleared structure kept | TC-EP-010 |
| ``build`` | names + UUID + blank sample field | blank field removed | TC-EP-011 |
| ``build`` | ``generalAttributes`` null | list with the written term | TC-EP-012 |
| ``build`` | ``specificAttributes`` null | list with the written class/term | TC-EP-013 |

Boundary values (BV), same file:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| ``build`` | first row of a run | ``sample.ownerId`` = ``basic.dataOwnerId`` | TC-BV-001 |
| ``InvoiceService.prepare_tile`` | a tile of a non-SmartTable mode | no SmartTable invoice built (v2 form of v1's ValueError) | TC-BV-002 |
| ``build`` | ``basic.dataOwnerId`` = "" | warning, inherited ``sample.ownerId`` kept | TC-BV-003 |
| ``build`` | ``sample/sampleId`` = "" | absent: clearing | TC-BV-004 |
| ``build`` | ``sample/sampleId`` = UUID | no clearing | TC-BV-005 |
| ``build`` | ``sample/sampleId`` = blanks | absent: clearing | TC-BV-006 |

``tests/test_smarttable_invoice_initializer_issue_429.py``:

| API | Partition / boundary | Expected | Test ID |
| --- | --- | --- | --- |
| ``build`` | ``number`` with ``"30"`` | ``30`` (int), invoice validates | TC-EP-429-001 |
| ``build`` | ``number`` with ``"30.5"`` | ``30.5`` (float), invoice validates | TC-EP-429-002 |
| ``build`` | ``number`` with ``"abc"`` | StructuredError (expected: number) | TC-EP-429-005 |
| ``build`` | ``integer`` with ``"30.1"`` | StructuredError (expected: integer) | TC-EP-429-006 |
| ``build`` | ``boolean`` with ``"yes"`` | StructuredError (expected: boolean) | TC-EP-429-007 |
| ``build`` | custom field missing from the schema | StructuredError (not defined) | TC-EP-429-008 |

TC-BV-002 is the one port without a frozen value: v1 raised ``ValueError`` for a
processing context without a SmartTable file, a state the v2 builder cannot be
handed (it has no context). Its v2 form pins the property the guard protected:
outside SmartTable mode no row is ever merged into an invoice.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.domain.invoice_service import InvoiceService
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import InputPaths
from rdetoolkit.validation import invoice_validate
from tests.v2.modes.fixtures.smarttable_builder import _freeze
from tests.v2.modes.smarttable_builder_support import (
    assert_matches_frozen,
    failure_error,
    observe_v2,
    success_step,
)

_OWNER_WARNING = "basic.dataOwnerId is missing or empty"
_DUMMY_SAMPLE_ID = _freeze.R3_DUMMY_SAMPLE_INVOICE["sample"]["sampleId"]
_EXPLICIT_UUID = "12345678-abcd-ef01-2345-6789abcdef01"


def _k2(test_id: str) -> str:
    return f"k2/{test_id}"


def _ported(tmp_path: Path, test_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Observe the builder on a ported case; return (observation, last successful step)."""
    observed = observe_v2(tmp_path, _k2(test_id))
    return observed, success_step(observed)


def _assert_cleared_new_sample(sample: dict[str, Any], *, names: list[str]) -> None:
    assert sample["sampleId"] is None
    assert sample["description"] is None
    assert sample["names"] == names


# --------------------------------------------------------------------------
# tests/test_smarttable_invoice_initializer.py
# --------------------------------------------------------------------------


def test_owner_id_survives_a_source_mutation_between_rows__tc_ep_001(tmp_path: Path) -> None:
    """TC-EP-001: the second row of a run still gets ``basic.dataOwnerId``."""
    # Given: row 0 written over the source invoice, then ``sample.ownerId`` popped from it
    # When: the same run builds row 1 into the tile
    observed, step = _ported(tmp_path, "TC-EP-001")

    # Then: both rows were built and row 1's sample.ownerId is basic.dataOwnerId
    assert len(observed["steps"]) == 2
    assert step["invoice"]["sample"]["ownerId"] == _freeze.OWNER_ID
    assert_matches_frozen(_k2("TC-EP-001"), observed)


def test_first_row_sets_owner_id_from_data_owner__tc_bv_001(tmp_path: Path) -> None:
    """TC-BV-001: the first row of a run sets ``sample.ownerId`` from ``basic.dataOwnerId``."""
    # Given / When: one names-only row without an ownerId column
    observed, step = _ported(tmp_path, "TC-BV-001")

    # Then: ownerId is the data owner
    assert step["invoice"]["sample"]["ownerId"] == _freeze.OWNER_ID
    assert_matches_frozen(_k2("TC-BV-001"), observed)


def test_tile_without_row_csv_is_rejected__tc_ep_002(tmp_path: Path) -> None:
    """TC-EP-002: a SmartTable tile without a row CSV fails early."""
    # Given / When: a SmartTable tile whose paths carry no row CSV at all
    observed = observe_v2(tmp_path, _k2("TC-EP-002"))

    # Then: v1's StructuredError message, before any invoice is written
    assert failure_error(observed)["message"] == "No SmartTable row CSV file found"
    assert_matches_frozen(_k2("TC-EP-002"), observed)


@pytest.mark.parametrize("mode", [ModeKind.invoice, ModeKind.multidatatile, ModeKind.rdeformat])
def test_non_smarttable_tile_never_merges_a_row__tc_bv_002(tmp_path: Path, mode: ModeKind) -> None:
    """TC-BV-002: outside SmartTable mode no SmartTable invoice is ever built.

    v1 guarded its initializer with ``ValueError("SmartTable file not provided
    ...")``; v2 has no such context, the mode decides. The row CSV is present
    and valid, so building it would succeed -- only the mode gate stops it.
    """
    # Given: a tile that carries a valid SmartTable row CSV
    rowfile = tmp_path / "temp" / "fsmarttable_case_0000.csv"
    rowfile.parent.mkdir(parents=True)
    rowfile.write_text("basic/dataName\nrow-name\n", encoding="utf-8")
    invoice_dir = tmp_path / "divided" / "0001" / "invoice"
    paths = InputPaths(
        inputdata=tmp_path / "inputdata",
        invoice=tmp_path / "invoice",
        tasksupport=tmp_path / "tasksupport",
        smarttable_rawfile=rowfile,
    )

    # When: a non-SmartTable mode prepares the tile without an invariant invoice
    prepared = InvoiceService().prepare_tile(
        mode,
        paths=paths,
        invoice_dir=invoice_dir,
        iteration_index=0,
        invariant_invoice=None,
        invoice_source=tmp_path / "invoice" / "invoice.json",
    )

    # Then: nothing was built, returned or written
    assert prepared == (None, None)
    assert not (invoice_dir / "invoice.json").exists()


@pytest.mark.parametrize("test_id", ["TC-EP-003", "TC-BV-003"])
def test_missing_data_owner_warns_and_keeps_sample_owner__tc_ep_003_bv_003(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    test_id: str,
) -> None:
    """TC-EP-003 / TC-BV-003: a missing or empty ``basic.dataOwnerId`` keeps ``sample.ownerId``."""
    # Given: a source invoice whose dataOwnerId is deleted (EP-003) or "" (BV-003)
    # When: a names-only row is built
    with caplog.at_level(logging.WARNING):
        observed, step = _ported(tmp_path, test_id)

    # Then: the warning is logged and the inherited sample.ownerId is preserved
    assert _OWNER_WARNING in caplog.text
    assert step["invoice"]["sample"]["ownerId"] == _freeze.SAMPLE_OWNER_ID
    assert_matches_frozen(_k2(test_id), observed)


def test_csv_owner_id_takes_precedence__tc_ep_004(tmp_path: Path) -> None:
    """TC-EP-004: a CSV ``sample/ownerId`` wins over ``basic.dataOwnerId``."""
    # Given / When: a row carrying its own ownerId
    observed, step = _ported(tmp_path, "TC-EP-004")

    # Then: the CSV value is written, not the data owner
    assert step["invoice"]["sample"]["ownerId"] == _freeze.CSV_OWNER_ID
    assert step["invoice"]["sample"]["ownerId"] != _freeze.OWNER_ID
    assert_matches_frozen(_k2("TC-EP-004"), observed)


def test_names_only_clears_the_dummy_sample__tc_ep_005(tmp_path: Path) -> None:
    """TC-EP-005: ``sample/names`` without ``sample/sampleId`` clears every dummy field."""
    # Given / When: a names-only row over a source with a filled dummy sample
    observed, step = _ported(tmp_path, "TC-EP-005")

    # Then: ids and texts are cleared, attribute structures kept with null values
    sample = step["invoice"]["sample"]
    _assert_cleared_new_sample(sample, names=["New Sample"])
    assert sample["composition"] is None
    assert sample["referenceUrl"] is None
    assert sample["generalAttributes"]
    assert all(attribute["value"] is None for attribute in sample["generalAttributes"])
    assert sample["specificAttributes"]
    assert all(attribute["value"] is None for attribute in sample["specificAttributes"])
    assert_matches_frozen(_k2("TC-EP-005"), observed)


@pytest.mark.parametrize(
    ("test_id", "sample_id", "names"),
    [
        pytest.param("TC-EP-006", _EXPLICIT_UUID, "Existing Sample", id="TC-EP-006"),
        pytest.param("TC-BV-005", "fedcba98-7654-3210-fedc-ba9876543210", "Sample BV-005", id="TC-BV-005"),
    ],
)
def test_explicit_sample_id_prevents_clearing__tc_ep_006_bv_005(
    tmp_path: Path,
    test_id: str,
    sample_id: str,
    names: str,
) -> None:
    """TC-EP-006 / TC-BV-005: a UUID ``sample/sampleId`` keeps the referenced sample."""
    # Given / When: names plus an explicit sampleId over a dummy sample
    observed, step = _ported(tmp_path, test_id)

    # Then: the sampleId is the given one and the dummy fields are not cleared
    sample = step["invoice"]["sample"]
    assert sample["sampleId"] == sample_id
    assert sample["description"] == "Dummy description"
    assert sample["names"] == [names]
    assert_matches_frozen(_k2(test_id), observed)


def test_rows_without_sample_columns_keep_the_sample__tc_ep_007(tmp_path: Path) -> None:
    """TC-EP-007: no ``sample/`` column -> the inherited sample is untouched."""
    # Given / When: a basic-only row
    observed, step = _ported(tmp_path, "TC-EP-007")

    # Then: the dummy sample survives as it was
    sample = step["invoice"]["sample"]
    assert sample["sampleId"] == _DUMMY_SAMPLE_ID
    assert sample["description"] == "Dummy description"
    assert sample["composition"] == "Dummy composition"
    assert_matches_frozen(_k2("TC-EP-007"), observed)


@pytest.mark.parametrize(
    ("test_id", "names"),
    [
        pytest.param("TC-EP-008", ["Brand New"], id="TC-EP-008"),
        pytest.param("TC-BV-004", ["Sample BV-004"], id="TC-BV-004"),
        pytest.param("TC-BV-006", ["Brand New BV-006"], id="TC-BV-006"),
    ],
)
def test_empty_or_blank_sample_id_clears_the_dummy_sample__tc_ep_008_bv_004_bv_006(
    tmp_path: Path,
    test_id: str,
    names: list[str],
) -> None:
    """TC-EP-008 / TC-BV-004 / TC-BV-006: an "" or blank sampleId is absent."""
    # Given / When: names plus a sampleId cell that is "" or only blanks
    observed, step = _ported(tmp_path, test_id)

    # Then: the new-sample clearing ran
    _assert_cleared_new_sample(step["invoice"]["sample"], names=names)
    assert_matches_frozen(_k2(test_id), observed)


def test_owner_id_is_corrected_after_new_sample_clearing__tc_ep_009(tmp_path: Path) -> None:
    """TC-EP-009 (Issue #389): the owner correction still runs after clearing."""
    # Given / When: a names-only row over a dummy sample
    observed, step = _ported(tmp_path, "TC-EP-009")

    # Then: the sample is cleared and its owner is the data owner
    assert step["invoice"]["sample"]["sampleId"] is None
    assert step["invoice"]["sample"]["ownerId"] == _freeze.OWNER_ID
    assert_matches_frozen(_k2("TC-EP-009"), observed)


def test_blank_fixed_headers_keep_the_cleared_structure__tc_ep_010(tmp_path: Path) -> None:
    """TC-EP-010: blank fixed-header sample columns do not delete cleared entries."""
    # Given: the dummy sample's first general and specific attribute
    general = _freeze.R3_SAMPLE_INVOICE["sample"]["generalAttributes"][0]["termId"]
    specific = _freeze.R3_SAMPLE_INVOICE["sample"]["specificAttributes"][0]

    # When: a new-sample row leaves those columns (and description) blank
    observed, step = _ported(tmp_path, "TC-EP-010")

    # Then: scalars stay cleared and the attribute entries survive with null values
    sample = step["invoice"]["sample"]
    assert sample["sampleId"] is None
    assert sample["description"] is None
    assert {"termId": general, "value": None} in sample["generalAttributes"]
    assert {**specific, "value": None} in sample["specificAttributes"]
    assert_matches_frozen(_k2("TC-EP-010"), observed)


def test_existing_sample_rows_still_drop_blank_fields__tc_ep_011(tmp_path: Path) -> None:
    """TC-EP-011: a sample-linking row still applies the generic blank-cell clearing."""
    # Given / When: names, an explicit sampleId and a blank description
    observed, step = _ported(tmp_path, "TC-EP-011")

    # Then: the sampleId is kept and the blank field is removed
    sample = step["invoice"]["sample"]
    assert sample["sampleId"] == _EXPLICIT_UUID
    assert "description" not in sample
    assert_matches_frozen(_k2("TC-EP-011"), observed)


def test_null_general_attributes_are_normalized__tc_ep_012(tmp_path: Path) -> None:
    """TC-EP-012: a null ``generalAttributes`` container becomes the written list."""
    # Given / When: the restructured invoice (null containers) and one general term
    observed, step = _ported(tmp_path, "TC-EP-012")

    # Then: exactly the requested term is written
    assert step["invoice"]["sample"]["generalAttributes"] == [
        {"termId": "7cc57dfb-8b70-4b3a-5315-fbce4cbf73d0", "value": "pellet"},
    ]
    assert_matches_frozen(_k2("TC-EP-012"), observed)


def test_null_specific_attributes_are_normalized__tc_ep_013(tmp_path: Path) -> None:
    """TC-EP-013: a null ``specificAttributes`` container becomes the written list."""
    # Given / When: the restructured invoice (null containers) and one class/term
    observed, step = _ported(tmp_path, "TC-EP-013")

    # Then: exactly the requested class/term entry is written
    assert step["invoice"]["sample"]["specificAttributes"] == [
        {"classId": _freeze.CLASS_ID, "termId": _freeze.SPECIFIC_TERM, "value": "single crystal"},
    ]
    assert_matches_frozen(_k2("TC-EP-013"), observed)


# --------------------------------------------------------------------------
# tests/test_smarttable_invoice_initializer_issue_429.py
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("test_id", "expected"),
    [
        pytest.param("TC-EP-429-001", 30, id="TC-EP-429-001"),
        pytest.param("TC-EP-429-002", 30.5, id="TC-EP-429-002"),
    ],
)
def test_number_strings_are_cast_and_validate__tc_ep_429_001_002(
    tmp_path: Path,
    test_id: str,
    expected: float,
) -> None:
    """TC-EP-429-001/002: number cells are stored as numbers and the invoice validates."""
    # Given / When: an integer-like or decimal cell in a ``number`` custom field
    observed, step = _ported(tmp_path, test_id)

    # Then: the stored value has the original test's value and type
    value = step["invoice"]["custom"]["process_key_temperature"]
    assert value == expected
    assert type(value) is type(expected)
    # And: the written invoice passes schema validation, as in the original
    root = tmp_path / "v2"
    invoice_validate(root / "invoice" / "invoice.json", root / "tasksupport" / "invoice.schema.json")
    assert_matches_frozen(_k2(test_id), observed)


@pytest.mark.parametrize(
    ("test_id", "message"),
    [
        pytest.param(
            "TC-EP-429-005",
            "Value for invoice.json field 'custom.process_key_temperature' does not match the type "
            "defined in invoice.schema.json (expected: number).",
            id="TC-EP-429-005",
        ),
        pytest.param(
            "TC-EP-429-006",
            "Value for invoice.json field 'custom.process_key_temperature' does not match the type "
            "defined in invoice.schema.json (expected: integer).",
            id="TC-EP-429-006",
        ),
        pytest.param(
            "TC-EP-429-007",
            "Value for invoice.json field 'custom.enable_feature' does not match the type "
            "defined in invoice.schema.json (expected: boolean).",
            id="TC-EP-429-007",
        ),
        pytest.param(
            "TC-EP-429-008",
            "Field 'custom.process_key_temperature' is not defined in invoice.schema.json.",
            id="TC-EP-429-008",
        ),
    ],
)
def test_invalid_custom_values_fail_early__tc_ep_429_005_008(
    tmp_path: Path,
    test_id: str,
    message: str,
) -> None:
    """TC-EP-429-005..008: invalid custom cells raise the v1 StructuredError messages."""
    # Given / When: a cell its schema type rejects, or a field the schema lacks
    observed = observe_v2(tmp_path, _k2(test_id))

    # Then: the original tests' message, before the invoice is touched
    error = failure_error(observed)
    assert re.fullmatch(re.escape(message), error["message"])
    assert_matches_frozen(_k2(test_id), observed)
