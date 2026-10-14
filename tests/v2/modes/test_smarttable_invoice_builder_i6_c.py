"""Session I6-C: the v2 SmartTable invoice builder against the frozen v1 oracle.

The subject is ``rdetoolkit.modes.smarttable.SmartTableInvoiceBuilder``, the v2
port of v1's ``SmartTableInvoiceInitializer``. Every merge rule is asserted by
comparing the three observable results -- the written tile ``invoice.json``,
the written ``meta/metadata.json`` and the returned row dictionary, or the
normalized error -- with v1's observation of byte-identical inputs.

UPDATED (Session K2-0, ruling #1): until K2-0 this module executed the v1
processor live. Every one of those observations is now a registered case of
``tests/v2/modes/fixtures/smarttable_builder/_freeze.py`` (family ``i6c``), frozen
from v1 by that generator; this module no longer imports
``rdetoolkit.processing``. The same frozen inputs also pin the merge rules the
live oracle never exercised (``deletion_coverage.md`` §2 G2-G8: TC-I6-C-BV-046,
EP-018..022, EV-035, the BV-040 variants and EP-009 ``overwrite``). A case not
frozen yet skips as ``pending freeze`` after the builder has run on it.

Equivalence partitions (EP):

| API | Partition | Rationale | Expected | Test ID |
| --- | --- | --- | --- | --- |
| ``build`` | ``basic/`` column | plain field assignment | equals v1 | TC-I6-C-EP-001 |
| ``build`` | ``custom/`` typed columns | schema-driven casting | equals v1 | TC-I6-C-EP-002 |
| ``build`` | ``sample/names`` without ``sampleId`` | new-sample registration | equals v1 | TC-I6-C-EP-003 |
| ``build`` | general/specific attributes | list merge by termId | equals v1 | TC-I6-C-EP-004 |
| ``build`` | ``meta/`` columns | metadata.json emission | equals v1 | TC-I6-C-EP-005 |
| ``build`` | empty cell over inherited value | clearing rule | equals v1 | TC-I6-C-EP-006 |
| ``build`` | no ``sample/ownerId`` column | ownerId := dataOwnerId | equals v1 | TC-I6-C-EP-007 |
| ``build`` | missing ``invoice_org`` | empty invoice template | equals v1 | TC-I6-C-EP-008 |
| ``build`` | existing ``metadata.json`` | constant section merge | equals v1 | TC-I6-C-EP-009 |
| ``build`` | existing ``metadata.json`` holding the same key (G8) | value and unit replaced, rest kept | equals v1 | TC-I6-C-EP-009[overwrite] |
| ``build`` | row dictionary | callback material | equals v1 | TC-I6-C-EP-010 |
| ``build`` | empty attribute cells while linking a sample | attribute clearing | equals v1 | TC-I6-C-EP-011 |
| ``build`` | base invoice without attribute containers | container creation | equals v1 | TC-I6-C-EP-012 |
| ``build`` | base invoice without ``basic`` | required-section repair | equals v1 | TC-I6-C-EP-013 |
| ``build`` | malformed specific-attribute key | ignored, not an error | equals v1 | TC-I6-C-EP-014 |
| ``build`` | metadata definition without a type | raw string stored | equals v1 | TC-I6-C-EP-015 |
| ``build`` | ``sample/sampleId`` empty (G3) | absent: new-sample clearing | equals v1 | TC-I6-C-EP-018 |
| ``build`` | ``sample/sampleId`` blank (G3) | absent: new-sample clearing | equals v1 | TC-I6-C-EP-019 |
| ``build`` | base ``basic.dataOwnerId`` missing / empty (G4) | inherited ``sample.ownerId`` kept | equals v1 | TC-I6-C-EP-020 |
| ``build`` | base attribute containers ``null`` (G5) | containers become lists | equals v1 | TC-I6-C-EP-021 |
| ``build`` | two classIds x two termIds (G6) | three distinct entries | equals v1 | TC-I6-C-EP-022 |

Negative / error partitions (EV):

| API | Partition | Rationale | Expected | Test ID |
| --- | --- | --- | --- | --- |
| ``build`` | custom field absent from schema | v1 rejects unknown fields | same StructuredError | TC-I6-C-EV-020 |
| ``build`` | schema whose custom field omits ``type`` | schema parsing rejects it | same StructuredError | TC-I6-C-EV-021 |
| ``build`` | integer cast failure | strict SmartTable casting | same StructuredError | TC-I6-C-EV-022 |
| ``build`` | boolean cast failure | strict SmartTable casting | same StructuredError | TC-I6-C-EV-023 |
| ``build`` | non-finite number | strict SmartTable casting | same StructuredError | TC-I6-C-EV-024 |
| ``build`` | meta key absent from metadata-def | undefined metadata | same StructuredError | TC-I6-C-EV-025 |
| ``build`` | ``variable`` metadata | unsupported mapping | same StructuredError | TC-I6-C-EV-026 |
| ``build`` | unsupported metadata type | unsupported mapping | same StructuredError | TC-I6-C-EV-027 |
| ``build`` | metadata-def.json missing | v1.7 #496 rejects the column (UPDATED K0-iii) | same StructuredError | TC-I6-C-EV-028 |
| ``build`` | sample attribute container is a scalar | container contract | same StructuredError | TC-I6-C-EV-029 |
| ``build`` | header-only row CSV | no data row | equals v1, row data ``None`` | TC-I6-C-EV-030 |
| ``build`` | missing row CSV | unreadable input | same StructuredError | TC-I6-C-EV-031 |
| ``build`` | non-numeric ``number`` cell | strict SmartTable casting | same StructuredError | TC-I6-C-EV-032 |
| ``build`` | metadata value of the wrong type | metadata-def contract | same StructuredError | TC-I6-C-EV-033 |
| ``build`` | metadata-def.json is not an object | file contract | same StructuredError | TC-I6-C-EV-034 |
| ``build`` | ``integer`` column holding ``"30.1"`` (G7) | decimal rejected | same StructuredError | TC-I6-C-EV-035 |

Boundary values (BV):

| API | Boundary | Rationale | Expected | Test ID |
| --- | --- | --- | --- | --- |
| ``build`` | ``number`` column holding ``"3"`` | int-before-float rule | ``3`` not ``3.0`` | TC-I6-C-BV-040 |
| ``build`` | ``"-1"`` / ``"0"`` / ``"0.0"`` number, ``"-1"`` integer (G7) | low magnitudes keep their type | equals v1 | TC-I6-C-BV-040[...] |
| ``build`` | two tiles of one run | later tiles must not inherit tile 0 | base invoice read once | TC-I6-C-BV-041 |
| ``build`` | new builder after content change | run boundary reloads | changed value observed | TC-I6-C-BV-042 |
| ``build`` | two builders, same path, changed content | same-root concurrency | independent snapshots | TC-I6-C-BV-043 |
| ``build`` | ``reset`` between two runs of one builder | run boundary | source is re-read | TC-I6-C-BV-044 |
| ``build`` | two tiles, two destinations, one run | snapshot is copied per tile | tile 0's row cannot reach tile 1 | TC-I6-C-BV-045 |
| ``build`` | boolean cells in mixed case / padded with blanks (G2) | case and blanks ignored | equals v1 | TC-I6-C-BV-046 |

BV-041..045 are v2-only run-ownership properties of the builder (v1 had a
class cache instead); they never had a v1 oracle and run as before.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.v2.modes.fixtures.smarttable_builder import _freeze
from tests.v2.modes.smarttable_builder_support import (
    assert_matches_frozen,
    failure_error,
    observe_v2,
    success_step,
)

_SAMPLE_SCHEMA = _freeze.SAMPLE_SCHEMA
_BASE_INVOICE = _freeze.BASE_INVOICE
_METADATA_DEF = _freeze.METADATA_DEF
_GENERAL_TERM = _freeze.GENERAL_TERM
_CLASS_ID = _freeze.CLASS_ID
_SPECIFIC_TERM = _freeze.SPECIFIC_TERM


def _materialize(
    root: Path,
    *,
    csv_text: str,
    invoice: dict[str, Any] | None,
    schema: dict[str, Any],
    metadata_def: Any,
    metadata: dict[str, Any] | None = None,
    write_rowfile: bool = True,
) -> dict[str, Path]:
    """Create one identical SmartTable tile input tree under ``root``."""
    tasksupport = root / "tasksupport"
    tasksupport.mkdir(parents=True, exist_ok=True)
    (root / "invoice").mkdir(parents=True, exist_ok=True)
    tile = root / "divided" / "0001"
    (tile / "invoice").mkdir(parents=True, exist_ok=True)
    (tile / "meta").mkdir(parents=True, exist_ok=True)

    rowfile = root / "temp" / "fsmarttable_case_0001.csv"
    rowfile.parent.mkdir(parents=True, exist_ok=True)
    if write_rowfile:
        rowfile.write_text(csv_text, encoding="utf-8")

    invoice_org = root / "invoice" / "invoice.json"
    if invoice is not None:
        invoice_org.write_text(json.dumps(invoice, ensure_ascii=False), encoding="utf-8")

    schema_path = tasksupport / "invoice.schema.json"
    schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")

    if metadata_def is not None:
        (tasksupport / "metadata-def.json").write_text(
            json.dumps(metadata_def, ensure_ascii=False),
            encoding="utf-8",
        )
    metadata_path = tile / "meta" / "metadata.json"
    if metadata is not None:
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")

    return {
        "rowfile": rowfile,
        "invoice_org": invoice_org,
        "schema_path": schema_path,
        "dist_path": tile / "invoice" / "invoice.json",
        "metadata_def_path": tasksupport / "metadata-def.json",
        "metadata_path": metadata_path,
    }


def _i6c(test_id: str, variant: str | None = None) -> str:
    """Return the builder case id of an I6-C test (family ``i6c``)."""
    return f"i6c/{test_id}" if variant is None else f"i6c/{test_id}__{variant}"


@pytest.mark.parametrize(
    "test_id",
    [pytest.param(test_id, id=test_id) for test_id, _csv_text, _invoice in _freeze.I6C_MERGE_ROWS],
)
def test_merge_rules_match_the_v1_initializer(tmp_path: Path, test_id: str) -> None:
    """TC-I6-C-EP-001..017: every merge rule reproduces the frozen v1 result exactly."""
    # Given: one SmartTable row and the base invoice v1 inherited from (frozen case)
    # When: the v2 builder builds the tile on the same inputs
    observed = observe_v2(tmp_path, _i6c(test_id))

    # Then: no step failed, and invoice, metadata and row dictionary equal v1's
    success_step(observed)
    assert_matches_frozen(_i6c(test_id), observed)


def test_meta_columns_match_the_v1_metadata_file__tc_i6_c_ep_005(tmp_path: Path) -> None:
    """TC-I6-C-EP-005: meta/ columns produce v1's metadata.json entries."""
    # Given: two meta columns, one of which declares a unit
    # When: the builder builds the tile
    observed = observe_v2(tmp_path, _i6c("TC-I6-C-EP-005"))

    # Then: the typed values and the unit survive the port
    step = success_step(observed)
    assert step["metadata"]["constant"] == {
        "comment": {"value": "memo-a"},
        "temperature": {"value": 20.5, "unit": "C"},
    }
    assert step["metadata"]["variable"] == []
    # And: the whole observation is v1's
    assert_matches_frozen(_i6c("TC-I6-C-EP-005"), observed)


def test_existing_metadata_is_merged_not_replaced__tc_i6_c_ep_009(tmp_path: Path) -> None:
    """TC-I6-C-EP-009: an existing metadata.json keeps its other keys."""
    # Given: a metadata.json a node already wrote for this tile
    # When: the builder applies one meta column
    observed = observe_v2(tmp_path, _i6c("TC-I6-C-EP-009"))

    # Then: the pre-existing constant and variable sections survive
    step = success_step(observed)
    assert step["metadata"]["constant"]["existing"] == {"value": "keep"}
    assert step["metadata"]["variable"] == [{"seq": 1}]
    assert_matches_frozen(_i6c("TC-I6-C-EP-009"), observed)


def test_existing_metadata_key_is_overwritten_with_its_unit__tc_i6_c_ep_009_overwrite(tmp_path: Path) -> None:
    """TC-I6-C-EP-009[overwrite] (G8): the same key is replaced, value and unit."""
    # Given: a metadata.json already holding ``comment`` with another unit
    # When: the builder applies a ``meta/comment`` column whose definition has a unit
    observed = observe_v2(tmp_path, _i6c("TC-I6-C-EP-009", "overwrite"))

    # Then: value and unit are both the new ones, every other key is kept
    step = success_step(observed)
    assert step["metadata"]["constant"]["comment"] == {"value": "new comment", "unit": "updated-unit"}
    assert step["metadata"]["constant"]["other"] == {"value": "preserve"}
    assert step["metadata"]["variable"] == [{"cycle": {"value": "A"}}]
    assert_matches_frozen(_i6c("TC-I6-C-EP-009", "overwrite"), observed)


def test_number_column_prefers_integers__tc_i6_c_bv_040(tmp_path: Path) -> None:
    """TC-I6-C-BV-040: a number-typed column holding an int stays an int."""
    # Given: a schema field typed ``number`` and an integral cell
    # When: the builder casts the value
    observed = observe_v2(tmp_path, _i6c("TC-I6-C-BV-040"))

    # Then: v1's int-before-float rule is preserved
    value = success_step(observed)["invoice"]["custom"]["sample2"]
    assert value == 3
    assert isinstance(value, int)
    assert_matches_frozen(_i6c("TC-I6-C-BV-040"), observed)


@pytest.mark.parametrize(
    ("variant", "field", "expected"),
    [
        pytest.param("number_minus_one", "sample2", -1, id="number_minus_one"),
        pytest.param("number_zero", "sample2", 0, id="number_zero"),
        pytest.param("number_zero_point_zero", "sample2", 0.0, id="number_zero_point_zero"),
        pytest.param("integer_minus_one", "sample3", -1, id="integer_minus_one"),
    ],
)
def test_low_magnitude_numbers_keep_their_type__tc_i6_c_bv_040(
    tmp_path: Path,
    variant: str,
    field: str,
    expected: float,
) -> None:
    """TC-I6-C-BV-040[...] (G7): values around zero keep v1's numeric type."""
    # Given: a numeric cell at the zero boundary
    # When: the builder casts it
    observed = observe_v2(tmp_path, _i6c("TC-I6-C-BV-040", variant))

    # Then: the value and its Python type are v1's (int stays int, 0.0 stays float)
    value = success_step(observed)["invoice"]["custom"][field]
    assert value == expected
    assert type(value) is type(expected)
    assert_matches_frozen(_i6c("TC-I6-C-BV-040", variant), observed)


@pytest.mark.parametrize(
    ("variant", "expected"),
    [
        pytest.param(
            "mixed_case",
            {"invert_phase_axis": False, "enable_feature": True, "flag_lowercase": True, "flag_mixed": False},
            id="mixed_case",
        ),
        pytest.param("padded", {"invert_phase_axis": True, "enable_feature": False}, id="padded"),
    ],
)
def test_boolean_cells_ignore_case_and_blanks__tc_i6_c_bv_046(
    tmp_path: Path,
    variant: str,
    expected: dict[str, bool],
) -> None:
    """TC-I6-C-BV-046 (G2, #292/#429): boolean cells are case- and blank-insensitive."""
    # Given: boolean cells as Excel writes them (TRUE/FALSE) or padded with blanks
    # When: the builder casts them
    observed = observe_v2(tmp_path, _i6c("TC-I6-C-BV-046", variant))

    # Then: each is a real bool -- "FALSE" is not truthy text
    custom = success_step(observed)["invoice"]["custom"]
    for field, value in expected.items():
        assert custom[field] is value
    assert_matches_frozen(_i6c("TC-I6-C-BV-046", variant), observed)


@pytest.mark.parametrize("test_id", ["TC-I6-C-EP-018", "TC-I6-C-EP-019"])
def test_empty_or_blank_sample_id_registers_a_new_sample__tc_i6_c_ep_018_019(tmp_path: Path, test_id: str) -> None:
    """TC-I6-C-EP-018/019 (G3): an empty or blank sampleId is no sample reference."""
    # Given: ``sample/names`` with a ``sample/sampleId`` cell that is "" or blanks
    # When: the builder builds the tile
    observed = observe_v2(tmp_path, _i6c(test_id))

    # Then: the inherited sample is cleared and the new name registered
    sample = success_step(observed)["invoice"]["sample"]
    assert sample["sampleId"] is None
    assert sample["description"] is None
    assert sample["names"] == ["new-sample"]
    assert_matches_frozen(_i6c(test_id), observed)


@pytest.mark.parametrize("variant", ["missing", "empty"])
def test_missing_data_owner_keeps_the_inherited_sample_owner__tc_i6_c_ep_020(tmp_path: Path, variant: str) -> None:
    """TC-I6-C-EP-020 (G4): without ``basic.dataOwnerId`` the sample owner is not touched."""
    # Given: a base invoice whose dataOwnerId is absent or ""
    # When: the builder registers a new sample
    observed = observe_v2(tmp_path, _i6c("TC-I6-C-EP-020", variant))

    # Then: the inherited sample.ownerId survives
    assert success_step(observed)["invoice"]["sample"]["ownerId"] == _freeze.SAMPLE_OWNER_ID
    assert_matches_frozen(_i6c("TC-I6-C-EP-020", variant), observed)


def test_null_attribute_containers_become_lists__tc_i6_c_ep_021(tmp_path: Path) -> None:
    """TC-I6-C-EP-021 (G5): ``null`` attribute containers are normalized before writing."""
    # Given: a base invoice whose two attribute containers are null
    # When: the row sets one general and one specific attribute
    observed = observe_v2(tmp_path, _i6c("TC-I6-C-EP-021"))

    # Then: both containers are lists holding exactly the written entries
    sample = success_step(observed)["invoice"]["sample"]
    assert sample["generalAttributes"] == [{"termId": _GENERAL_TERM, "value": "general-n"}]
    assert sample["specificAttributes"] == [{"classId": _CLASS_ID, "termId": _SPECIFIC_TERM, "value": "specific-n"}]
    assert_matches_frozen(_i6c("TC-I6-C-EP-021"), observed)


def test_specific_attributes_map_class_and_term__tc_i6_c_ep_022(tmp_path: Path) -> None:
    """TC-I6-C-EP-022 (G6): two classIds x two termIds give three distinct entries."""
    # Given: three specific-attribute columns over two classes
    # When: the builder applies them to a sample without attributes
    observed = observe_v2(tmp_path, _i6c("TC-I6-C-EP-022"))

    # Then: each (classId, termId) pair is its own entry, in column order
    assert success_step(observed)["invoice"]["sample"]["specificAttributes"] == [
        {"classId": "class1", "termId": "term1", "value": "value1"},
        {"classId": "class1", "termId": "term2", "value": "value2"},
        {"classId": "class2", "termId": "term1", "value": "value3"},
    ]
    assert_matches_frozen(_i6c("TC-I6-C-EP-022"), observed)


@pytest.mark.parametrize(
    "test_id",
    [pytest.param(test_id, id=test_id) for test_id, *_rest in _freeze.I6C_FAILURE_ROWS],
)
def test_rejected_rows_fail_exactly_like_v1(tmp_path: Path, test_id: str) -> None:
    """TC-I6-C-EV-020..034: rejected rows raise v1's StructuredError message."""
    # Given: a row v1 refused to merge (frozen case)
    # When: the builder processes it
    observed = observe_v2(tmp_path, _i6c(test_id))

    # Then: a StructuredError, with v1's text, code and written files
    failure_error(observed)
    assert_matches_frozen(_i6c(test_id), observed)


def test_integer_column_rejects_a_decimal__tc_i6_c_ev_035(tmp_path: Path) -> None:
    """TC-I6-C-EV-035 (G7): an ``integer`` column refuses ``"30.1"``."""
    # Given / When: a decimal cell in an integer-typed custom column
    observed = observe_v2(tmp_path, _i6c("TC-I6-C-EV-035"))

    # Then: the v1 type-mismatch message names the field and the type
    assert failure_error(observed)["message"] == (
        "Value for invoice.json field 'custom.sample3' does not match the type "
        "defined in invoice.schema.json (expected: integer)."
    )
    assert_matches_frozen(_i6c("TC-I6-C-EV-035"), observed)


def test_scalar_attribute_container_is_rejected__tc_i6_c_ev_029(tmp_path: Path) -> None:
    """TC-I6-C-EV-029: a non-list attribute container is a StructuredError."""
    # Given: an inherited sample whose generalAttributes is not a list
    # When: a general attribute column targets that container
    observed = observe_v2(tmp_path, _i6c("TC-I6-C-EV-029"))

    # Then: the container contract is reported, not a TypeError
    assert "generalAttributes" in failure_error(observed)["message"]
    assert_matches_frozen(_i6c("TC-I6-C-EV-029"), observed)


def test_missing_metadata_definition_skips_meta_columns__tc_i6_c_ev_028(tmp_path: Path) -> None:
    """TC-I6-C-EV-028 (UPDATED, K0-iii): without metadata-def.json a meta column fails.

    v1.7 (#496) replaced the silent skip with a ``StructuredError``; the frozen
    oracle is the merged v1.7.1 initializer, so the expectation follows it.
    """
    # Given: a meta column but no metadata definition file
    # When: the builder processes the row
    observed = observe_v2(tmp_path, _i6c("TC-I6-C-EV-028"))

    # Then: the message names the missing definition file, as v1's does
    assert failure_error(observed)["message"].startswith("metadata-def.json not found: ")
    assert_matches_frozen(_i6c("TC-I6-C-EV-028"), observed)


def test_header_only_row_csv_writes_the_base_invoice__tc_i6_c_ev_030(tmp_path: Path) -> None:
    """TC-I6-C-EV-030: a CSV without data rows yields no row dictionary."""
    # Given: a row CSV containing only its header
    # When: the builder builds the tile
    observed = observe_v2(tmp_path, _i6c("TC-I6-C-EV-030"))

    # Then: the inherited invoice is written unchanged and no row data exists
    step = success_step(observed)
    assert step["row_data"] is None
    assert step["invoice"]["basic"]["dataName"] == "inherited-name"
    assert_matches_frozen(_i6c("TC-I6-C-EV-030"), observed)


def test_missing_row_csv_is_rejected__tc_i6_c_ev_031(tmp_path: Path) -> None:
    """TC-I6-C-EV-031: an unreadable row CSV fails like v1."""
    # Given / When: a row CSV reference whose file does not exist
    observed = observe_v2(tmp_path, _i6c("TC-I6-C-EV-031"))

    # Then: v1's generic wrapper message is kept and nothing was written
    step = observed["steps"][-1]
    assert failure_error(observed)["message"].startswith("Failed to initialize invoice from SmartTable: ")
    assert step["invoice"] is None
    assert_matches_frozen(_i6c("TC-I6-C-EV-031"), observed)


def test_one_run_reads_the_base_invoice_once__tc_i6_c_bv_041(tmp_path: Path) -> None:
    """TC-I6-C-BV-041: later tiles never inherit an earlier tile's invoice.

    v1's SmartTable tile 0 writes its merged invoice back over
    ``data/invoice/invoice.json``; the class cache is what stopped tiles 1..N
    from inheriting it. The run-owned builder must keep that property without
    the class cache.
    """
    from rdetoolkit.modes.smarttable import SmartTableInvoiceBuilder  # noqa: PLC0415

    # Given: a builder that already produced tile 0 into the source invoice path
    paths = _materialize(
        tmp_path / "run",
        csv_text="basic/dataName\ntile-zero\n",
        invoice=_BASE_INVOICE,
        schema=_SAMPLE_SCHEMA,
        metadata_def=_METADATA_DEF,
    )
    builder = SmartTableInvoiceBuilder()
    builder.build(
        rowfile=paths["rowfile"],
        invoice_org=paths["invoice_org"],
        invoice_schema_path=paths["schema_path"],
        dist_path=paths["invoice_org"],
        metadata_def_path=paths["metadata_def_path"],
        metadata_path=paths["metadata_path"],
    )
    assert json.loads(paths["invoice_org"].read_text(encoding="utf-8"))["basic"]["dataName"] == "tile-zero"

    # When: the same run builds a second tile whose row leaves dataName empty
    paths["rowfile"].write_text("basic/instrumentId\ntile-one\n", encoding="utf-8")
    builder.build(
        rowfile=paths["rowfile"],
        invoice_org=paths["invoice_org"],
        invoice_schema_path=paths["schema_path"],
        dist_path=paths["dist_path"],
        metadata_def_path=paths["metadata_def_path"],
        metadata_path=paths["metadata_path"],
    )

    # Then: the second tile inherits the run's original invoice, not tile 0's
    second = json.loads(paths["dist_path"].read_text(encoding="utf-8"))
    assert second["basic"]["dataName"] == "inherited-name"
    assert second["basic"]["instrumentId"] == "tile-one"


def test_one_tile_never_mutates_the_run_snapshot__tc_i6_c_bv_045(tmp_path: Path) -> None:
    """TC-I6-C-BV-045: merging a row must not edit the snapshot in place.

    TC-I6-C-BV-041 exercises the same property through the file v1 overwrites,
    so it would also pass if the snapshot survived only because it is re-read.
    This one removes the filesystem from the loop entirely: both tiles write to
    *different* destinations, so nothing feeds the source invoice back. The
    only thing that can carry tile 0's row into tile 1 is a shared mutable
    snapshot — the deep copy the builder takes per tile.
    """
    from rdetoolkit.modes.smarttable import SmartTableInvoiceBuilder  # noqa: PLC0415

    # Given: one run whose first tile sets several nested fields
    paths = _materialize(
        tmp_path / "run",
        csv_text=(
            f"basic/dataName,custom/sample9,sample/composition,"
            f"sample/generalAttributes.{_GENERAL_TERM}\n"
            "tile-zero,custom-zero,composition-zero,general-zero\n"
        ),
        invoice=_BASE_INVOICE,
        schema=_SAMPLE_SCHEMA,
        metadata_def=_METADATA_DEF,
    )
    builder = SmartTableInvoiceBuilder()
    first_dist = paths["dist_path"].parent / "first.json"
    builder.build(
        rowfile=paths["rowfile"],
        invoice_org=paths["invoice_org"],
        invoice_schema_path=paths["schema_path"],
        dist_path=first_dist,
        metadata_def_path=paths["metadata_def_path"],
        metadata_path=paths["metadata_path"],
    )
    assert json.loads(first_dist.read_text(encoding="utf-8"))["basic"]["dataName"] == "tile-zero"

    # When: the same run builds a second tile that sets none of those fields
    paths["rowfile"].write_text("basic/instrumentId\ntile-one\n", encoding="utf-8")
    builder.build(
        rowfile=paths["rowfile"],
        invoice_org=paths["invoice_org"],
        invoice_schema_path=paths["schema_path"],
        dist_path=paths["dist_path"],
        metadata_def_path=paths["metadata_def_path"],
        metadata_path=paths["metadata_path"],
    )

    # Then: tile 1 shows the inherited values, including the nested containers
    second = json.loads(paths["dist_path"].read_text(encoding="utf-8"))
    assert second["basic"]["dataName"] == "inherited-name"
    assert second["custom"]["sample9"] == "inherited-custom"
    assert second["sample"]["composition"] == "inherited composition"
    assert second["sample"]["generalAttributes"] == [
        {"termId": _GENERAL_TERM, "value": "inherited-general"},
    ]
    # And: the source invoice on disk was never touched by either tile
    assert json.loads(paths["invoice_org"].read_text(encoding="utf-8")) == _BASE_INVOICE


def test_a_new_run_reloads_a_changed_base_invoice__tc_i6_c_bv_042(tmp_path: Path) -> None:
    """TC-I6-C-BV-042: a new builder observes content changed between runs."""
    from rdetoolkit.modes.smarttable import SmartTableInvoiceBuilder  # noqa: PLC0415

    # Given: one completed build over a base invoice
    paths = _materialize(
        tmp_path / "run",
        csv_text="basic/instrumentId\nfirst\n",
        invoice=_BASE_INVOICE,
        schema=_SAMPLE_SCHEMA,
        metadata_def=_METADATA_DEF,
    )
    first_builder = SmartTableInvoiceBuilder()
    first_builder.build(
        rowfile=paths["rowfile"],
        invoice_org=paths["invoice_org"],
        invoice_schema_path=paths["schema_path"],
        dist_path=paths["dist_path"],
        metadata_def_path=paths["metadata_def_path"],
        metadata_path=paths["metadata_path"],
    )

    # When: the source invoice changes and a new run builds the same tile
    changed = json.loads(json.dumps(_BASE_INVOICE))
    changed["basic"]["dataName"] = "second-run"
    paths["invoice_org"].write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
    SmartTableInvoiceBuilder().build(
        rowfile=paths["rowfile"],
        invoice_org=paths["invoice_org"],
        invoice_schema_path=paths["schema_path"],
        dist_path=paths["dist_path"],
        metadata_def_path=paths["metadata_def_path"],
        metadata_path=paths["metadata_path"],
    )

    # Then: the new run sees the changed content
    assert json.loads(paths["dist_path"].read_text(encoding="utf-8"))["basic"]["dataName"] == "second-run"


def test_two_builders_over_one_root_stay_independent__tc_i6_c_bv_043(tmp_path: Path) -> None:
    """TC-I6-C-BV-043: same source path, different runs, independent snapshots."""
    from rdetoolkit.modes.smarttable import SmartTableInvoiceBuilder  # noqa: PLC0415

    # Given: one run that already snapshotted the shared base invoice
    paths = _materialize(
        tmp_path / "run",
        csv_text="basic/instrumentId\nleft\n",
        invoice=_BASE_INVOICE,
        schema=_SAMPLE_SCHEMA,
        metadata_def=_METADATA_DEF,
    )
    left = SmartTableInvoiceBuilder()
    right = SmartTableInvoiceBuilder()
    left_dist = paths["dist_path"].parent / "left.json"
    right_dist = paths["dist_path"].parent / "right.json"
    left.build(
        rowfile=paths["rowfile"],
        invoice_org=paths["invoice_org"],
        invoice_schema_path=paths["schema_path"],
        dist_path=left_dist,
        metadata_def_path=paths["metadata_def_path"],
        metadata_path=paths["metadata_path"],
    )

    # When: the shared source is replaced and both runs build another tile
    changed = json.loads(json.dumps(_BASE_INVOICE))
    changed["basic"]["dataName"] = "replaced"
    paths["invoice_org"].write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
    right.build(
        rowfile=paths["rowfile"],
        invoice_org=paths["invoice_org"],
        invoice_schema_path=paths["schema_path"],
        dist_path=right_dist,
        metadata_def_path=paths["metadata_def_path"],
        metadata_path=paths["metadata_path"],
    )
    left.build(
        rowfile=paths["rowfile"],
        invoice_org=paths["invoice_org"],
        invoice_schema_path=paths["schema_path"],
        dist_path=left_dist,
        metadata_def_path=paths["metadata_def_path"],
        metadata_path=paths["metadata_path"],
    )

    # Then: each run keeps its own snapshot of the same path
    assert json.loads(left_dist.read_text(encoding="utf-8"))["basic"]["dataName"] == "inherited-name"
    assert json.loads(right_dist.read_text(encoding="utf-8"))["basic"]["dataName"] == "replaced"


def test_reset_releases_the_run_snapshot__tc_i6_c_bv_044(tmp_path: Path) -> None:
    """TC-I6-C-BV-044: ``reset`` makes the next build reload the source."""
    from rdetoolkit.modes.smarttable import SmartTableInvoiceBuilder  # noqa: PLC0415

    # Given: a builder holding a snapshot of the base invoice
    paths = _materialize(
        tmp_path / "run",
        csv_text="basic/instrumentId\nfirst\n",
        invoice=_BASE_INVOICE,
        schema=_SAMPLE_SCHEMA,
        metadata_def=_METADATA_DEF,
    )
    builder = SmartTableInvoiceBuilder()
    builder.build(
        rowfile=paths["rowfile"],
        invoice_org=paths["invoice_org"],
        invoice_schema_path=paths["schema_path"],
        dist_path=paths["dist_path"],
        metadata_def_path=paths["metadata_def_path"],
        metadata_path=paths["metadata_path"],
    )

    # When: the source changes and the builder is reset between runs
    changed = json.loads(json.dumps(_BASE_INVOICE))
    changed["basic"]["dataName"] = "after-reset"
    paths["invoice_org"].write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
    builder.reset()
    builder.build(
        rowfile=paths["rowfile"],
        invoice_org=paths["invoice_org"],
        invoice_schema_path=paths["schema_path"],
        dist_path=paths["dist_path"],
        metadata_def_path=paths["metadata_def_path"],
        metadata_path=paths["metadata_path"],
    )

    # Then: the reloaded snapshot is used
    assert json.loads(paths["dist_path"].read_text(encoding="utf-8"))["basic"]["dataName"] == "after-reset"
