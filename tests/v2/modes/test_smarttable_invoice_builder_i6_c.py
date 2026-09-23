"""Session I6-C: the v2 SmartTable invoice builder against the v1 oracle.

The subject is ``rdetoolkit.modes.smarttable.SmartTableInvoiceBuilder``, the v2
port of v1's ``SmartTableInvoiceInitializer``. Every merge rule is asserted by
running the v1 processor on byte-identical inputs in a sibling directory and
comparing the three observable results: the written tile ``invoice.json``, the
written ``meta/metadata.json`` and the returned row dictionary. The v1 class is
used **only here, as the oracle** — the v2 code path no longer references it.

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
| ``build`` | row dictionary | callback material | equals v1 | TC-I6-C-EP-010 |
| ``build`` | empty attribute cells while linking a sample | attribute clearing | equals v1 | TC-I6-C-EP-011 |
| ``build`` | base invoice without attribute containers | container creation | equals v1 | TC-I6-C-EP-012 |
| ``build`` | base invoice without ``basic`` | required-section repair | equals v1 | TC-I6-C-EP-013 |
| ``build`` | malformed specific-attribute key | ignored, not an error | equals v1 | TC-I6-C-EP-014 |
| ``build`` | metadata definition without a type | raw string stored | equals v1 | TC-I6-C-EP-015 |

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
| ``build`` | metadata-def.json missing | v1 skips the column | equals v1 | TC-I6-C-EV-028 |
| ``build`` | sample attribute container is a scalar | container contract | same StructuredError | TC-I6-C-EV-029 |
| ``build`` | header-only row CSV | no data row | equals v1, row data ``None`` | TC-I6-C-EV-030 |
| ``build`` | missing row CSV | unreadable input | same StructuredError | TC-I6-C-EV-031 |
| ``build`` | non-numeric ``number`` cell | strict SmartTable casting | same StructuredError | TC-I6-C-EV-032 |
| ``build`` | metadata value of the wrong type | metadata-def contract | same StructuredError | TC-I6-C-EV-033 |
| ``build`` | metadata-def.json is not an object | file contract | same StructuredError | TC-I6-C-EV-034 |

Boundary values (BV):

| API | Boundary | Rationale | Expected | Test ID |
| --- | --- | --- | --- | --- |
| ``build`` | ``number`` column holding ``"3"`` | int-before-float rule | ``3`` not ``3.0`` | TC-I6-C-BV-040 |
| ``build`` | two tiles of one run | later tiles must not inherit tile 0 | base invoice read once | TC-I6-C-BV-041 |
| ``build`` | new builder after content change | run boundary reloads | changed value observed | TC-I6-C-BV-042 |
| ``build`` | two builders, same path, changed content | same-root concurrency | independent snapshots | TC-I6-C-BV-043 |
| ``build`` | ``reset`` between two runs of one builder | run boundary | source is re-read | TC-I6-C-BV-044 |
| ``build`` | two tiles, two destinations, one run | snapshot is copied per tile | tile 0's row cannot reach tile 1 | TC-I6-C-BV-045 |
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.processing.processors.invoice import SmartTableInvoiceInitializer

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_SAMPLE_SCHEMA = json.loads(
    (_REPOSITORY_ROOT / "tests" / "samplefile" / "invoice.schema.json").read_text(encoding="utf-8"),
)
_OWNER_ID = "0" * 55 + "1"
_GENERAL_TERM = "3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e"
_CLASS_ID = "01cb3c01-37a4-5a43-d8ca-f523ca99a75b"
_SPECIFIC_TERM = "3250c45d-0ed6-1438-43b5-eb679918604a"

_BASE_INVOICE: dict[str, Any] = {
    "datasetId": "seed-dataset",
    "basic": {
        "dateSubmitted": "2026-09-01",
        "dataOwnerId": _OWNER_ID,
        "dataName": "inherited-name",
        "instrumentId": "inherited-instrument",
    },
    "custom": {"sample9": "inherited-custom"},
    "sample": {
        "sampleId": "00000000-0000-0000-0000-000000000001",
        "names": ["inherited-sample"],
        "description": "inherited description",
        "composition": "inherited composition",
        "referenceUrl": "https://example.invalid/inherited",
        "ownerId": "0" * 55 + "5",
        "generalAttributes": [{"termId": _GENERAL_TERM, "value": "inherited-general"}],
        "specificAttributes": [
            {"classId": _CLASS_ID, "termId": _SPECIFIC_TERM, "value": "inherited-specific"},
        ],
    },
}

#: A base invoice whose sample declares neither attribute container.
_NO_SAMPLE_ATTRIBUTE_INVOICE: dict[str, Any] = {
    "basic": {"dateSubmitted": "2026-09-01", "dataOwnerId": _OWNER_ID, "dataName": "inherited-name"},
    "custom": {},
    "sample": {"sampleId": "00000000-0000-0000-0000-000000000001"},
}

#: A base invoice with no ``basic`` section, which v1 tolerates.
_NO_BASIC_INVOICE: dict[str, Any] = {
    "datasetId": "seed-dataset",
    "custom": {},
    "sample": {"names": ["inherited-sample"]},
}

_METADATA_DEF: dict[str, Any] = {
    "comment": {"name": {"ja": "コメント", "en": "Comment"}, "schema": {"type": "string"}},
    "temperature": {
        "name": {"ja": "温度", "en": "Temperature"},
        "schema": {"type": "number"},
        "unit": "C",
    },
    # A definition that declares no type: v1 stores the raw string.
    "untyped": {"name": {"ja": "型なし", "en": "Untyped"}, "schema": {}},
}


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


def _run_v1_oracle(paths: dict[str, Path]) -> dict[str, Any] | None:
    """Execute the v1 initializer on the same inputs and return its row dict."""
    # The v1 class cache is process-global; clearing it keeps every oracle call
    # independent of the order tests run in.
    SmartTableInvoiceInitializer.clear_base_invoice_cache()
    tile = paths["dist_path"].parents[1]
    resource_paths = RdeOutputResourcePath(
        raw=tile / "raw",
        nonshared_raw=tile / "nonshared_raw",
        rawfiles=(paths["rowfile"],),
        struct=tile / "structured",
        main_image=tile / "main_image",
        other_image=tile / "other_image",
        meta=tile / "meta",
        thumbnail=tile / "thumbnail",
        logs=tile / "logs",
        invoice=paths["dist_path"].parent,
        invoice_schema_json=paths["schema_path"],
        invoice_org=paths["invoice_org"],
        smarttable_rowfile=paths["rowfile"],
        attachment=tile / "attachment",
    )
    context = ProcessingContext(
        index="0001",
        srcpaths=RdeInputDirPaths(
            inputdata=paths["rowfile"].parent,
            invoice=paths["invoice_org"].parent,
            tasksupport=paths["schema_path"].parent,
        ),
        resource_paths=resource_paths,
        datasets_function=None,
        mode_name="smarttable",
        smarttable_file=paths["rowfile"],
    )
    try:
        SmartTableInvoiceInitializer().process(context)
    finally:
        SmartTableInvoiceInitializer.clear_base_invoice_cache()
    return resource_paths.smarttable_row_data


def _run_v2_builder(paths: dict[str, Path]) -> dict[str, Any] | None:
    from rdetoolkit.modes.smarttable import SmartTableInvoiceBuilder  # noqa: PLC0415

    return SmartTableInvoiceBuilder().build(
        rowfile=paths["rowfile"],
        invoice_org=paths["invoice_org"],
        invoice_schema_path=paths["schema_path"],
        dist_path=paths["dist_path"],
        metadata_def_path=paths["metadata_def_path"],
        metadata_path=paths["metadata_path"],
    )


def _observe(paths: dict[str, Path], row_data: dict[str, Any] | None) -> dict[str, Any]:
    def _read(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    return {
        "invoice": _read(paths["dist_path"]),
        "metadata": _read(paths["metadata_path"]),
        "row_data": row_data,
    }


def _compare_with_v1(tmp_path: Path, **material: Any) -> dict[str, Any]:
    """Run both implementations on identical trees and assert they agree."""
    v1_paths = _materialize(tmp_path / "v1", **material)
    v2_paths = _materialize(tmp_path / "v2", **material)
    v1_observed = _observe(v1_paths, _run_v1_oracle(v1_paths))
    v2_observed = _observe(v2_paths, _run_v2_builder(v2_paths))
    assert v2_observed == v1_observed
    return v2_observed


def _compare_failure_with_v1(tmp_path: Path, **material: Any) -> StructuredError:
    """Assert both implementations reject identical inputs the same way."""
    v1_root = tmp_path / "v1"
    v2_root = tmp_path / "v2"
    v1_paths = _materialize(v1_root, **material)
    v2_paths = _materialize(v2_root, **material)
    with pytest.raises(StructuredError) as v1_error:
        _run_v1_oracle(v1_paths)
    with pytest.raises(StructuredError) as v2_error:
        _run_v2_builder(v2_paths)
    # The two trees differ only by their root directory, which a message may
    # legitimately quote; everything else must be byte-identical.
    assert str(v2_error.value).replace(str(v2_root), "<ROOT>") == str(v1_error.value).replace(str(v1_root), "<ROOT>")
    assert not v2_paths["dist_path"].exists() or v1_paths["dist_path"].exists()
    return v2_error.value


_HEADER_FULL = (
    "basic/dataName,custom/sample2,custom/sample3,custom/invert_phase_axis,"
    f"sample/names,sample/description,sample/generalAttributes.{_GENERAL_TERM},"
    f"sample/specificAttributes.{_CLASS_ID}.{_SPECIFIC_TERM},meta/comment,meta/temperature,inputdata1"
)

_MERGE_CASES: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
    (
        "TC-I6-C-EP-001",
        "basic/dataName\nrow-name\n",
        _BASE_INVOICE,
    ),
    (
        "TC-I6-C-EP-002",
        "custom/sample2,custom/sample3,custom/invert_phase_axis,custom/sample9\n2.5,7,true,text\n",
        _BASE_INVOICE,
    ),
    (
        "TC-I6-C-EP-003",
        "sample/names,sample/description\nnew-sample,fresh\n",
        _BASE_INVOICE,
    ),
    (
        "TC-I6-C-EP-004",
        f"sample/sampleId,sample/generalAttributes.{_GENERAL_TERM},"
        f"sample/specificAttributes.{_CLASS_ID}.{_SPECIFIC_TERM}\n"
        "00000000-0000-0000-0000-000000000009,general-a,specific-a\n",
        _BASE_INVOICE,
    ),
    (
        "TC-I6-C-EP-006",
        "basic/dataName,basic/instrumentId,custom/sample9\nkept,,\n",
        _BASE_INVOICE,
    ),
    (
        "TC-I6-C-EP-007",
        "sample/ownerId,basic/dataName\n" + "0" * 55 + "7,owned\n",
        _BASE_INVOICE,
    ),
    (
        "TC-I6-C-EP-008",
        "basic/dataName\nno-base\n",
        None,
    ),
    (
        "TC-I6-C-EP-010",
        _HEADER_FULL + "\nrow-name,2.5,7,false,new-sample,fresh,general-a,specific-a,memo,20.5,input/row.txt\n",
        _BASE_INVOICE,
    ),
    (
        # Empty attribute cells on a sample-linking row drop the inherited
        # entries instead of preserving them (no new-sample clearing applies).
        "TC-I6-C-EP-011",
        f"sample/sampleId,sample/generalAttributes.{_GENERAL_TERM},"
        f"sample/specificAttributes.{_CLASS_ID}.{_SPECIFIC_TERM},sample/composition\n"
        "00000000-0000-0000-0000-000000000009,,,\n",
        _BASE_INVOICE,
    ),
    (
        # A base invoice that declares no attribute containers at all.
        "TC-I6-C-EP-012",
        f"sample/sampleId,sample/generalAttributes.{_GENERAL_TERM},"
        f"sample/specificAttributes.{_CLASS_ID}.{_SPECIFIC_TERM}\n"
        "00000000-0000-0000-0000-000000000009,general-new,specific-new\n",
        _NO_SAMPLE_ATTRIBUTE_INVOICE,
    ),
    (
        # A base invoice with no ``basic`` section at all.
        "TC-I6-C-EP-013",
        "sample/sampleId\n00000000-0000-0000-0000-000000000009\n",
        _NO_BASIC_INVOICE,
    ),
    (
        # Malformed specific-attribute keys (no ``.<termId>``) are ignored,
        # both when they carry a value and when they are empty.
        "TC-I6-C-EP-014",
        "sample/sampleId,sample/specificAttributes.classonly,sample/specificAttributes.emptyonly\n"
        "00000000-0000-0000-0000-000000000009,specific-x,\n",
        _BASE_INVOICE,
    ),
    (
        # New-sample registration keeps its cleared fields cleared even when the
        # row leaves them empty, instead of re-running the empty-cell clearing.
        "TC-I6-C-EP-016",
        f"sample/names,sample/description,sample/composition,"
        f"sample/generalAttributes.{_GENERAL_TERM}\n"
        "new-sample,,,\n",
        _BASE_INVOICE,
    ),
    (
        # Attributes that do not match any inherited entry are appended after
        # the entries already present.
        "TC-I6-C-EP-017",
        "sample/sampleId,sample/generalAttributes.11111111-1111-1111-1111-111111111111,"
        f"sample/specificAttributes.{_CLASS_ID}.22222222-2222-2222-2222-222222222222\n"
        "00000000-0000-0000-0000-000000000009,general-added,specific-added\n",
        _BASE_INVOICE,
    ),
    (
        # A metadata definition without a declared type passes the raw string.
        "TC-I6-C-EP-015",
        "meta/untyped\nraw-value\n",
        _BASE_INVOICE,
    ),
)


@pytest.mark.parametrize(
    ("csv_text", "invoice"),
    [pytest.param(csv_text, invoice, id=case_id) for case_id, csv_text, invoice in _MERGE_CASES],
)
def test_merge_rules_match_the_v1_initializer(
    tmp_path: Path,
    csv_text: str,
    invoice: dict[str, Any] | None,
) -> None:
    """TC-I6-C-EP-001..010: every merge rule reproduces the v1 result exactly."""
    # Given: one SmartTable row and the base invoice v1 would inherit from
    # When: both implementations build the tile invoice
    # Then: invoice, metadata and row dictionary are identical
    _compare_with_v1(
        tmp_path,
        csv_text=csv_text,
        invoice=invoice,
        schema=_SAMPLE_SCHEMA,
        metadata_def=_METADATA_DEF,
    )


def test_meta_columns_match_the_v1_metadata_file__tc_i6_c_ep_005(tmp_path: Path) -> None:
    """TC-I6-C-EP-005: meta/ columns produce v1's metadata.json entries."""
    # Given: two meta columns, one of which declares a unit
    # When: both implementations build the tile
    observed = _compare_with_v1(
        tmp_path,
        csv_text="meta/comment,meta/temperature\nmemo-a,20.5\n",
        invoice=_BASE_INVOICE,
        schema=_SAMPLE_SCHEMA,
        metadata_def=_METADATA_DEF,
    )

    # Then: the typed values and the unit survive the port
    assert observed["metadata"]["constant"] == {
        "comment": {"value": "memo-a"},
        "temperature": {"value": 20.5, "unit": "C"},
    }
    assert observed["metadata"]["variable"] == []


def test_existing_metadata_is_merged_not_replaced__tc_i6_c_ep_009(tmp_path: Path) -> None:
    """TC-I6-C-EP-009: an existing metadata.json keeps its other keys."""
    # Given: a metadata.json a node already wrote for this tile
    # When: both implementations apply one meta column
    observed = _compare_with_v1(
        tmp_path,
        csv_text="meta/comment\nmemo-a\n",
        invoice=_BASE_INVOICE,
        schema=_SAMPLE_SCHEMA,
        metadata_def=_METADATA_DEF,
        metadata={"constant": {"existing": {"value": "keep"}}, "variable": [{"seq": 1}]},
    )

    # Then: the pre-existing constant and variable sections survive
    assert observed["metadata"]["constant"]["existing"] == {"value": "keep"}
    assert observed["metadata"]["variable"] == [{"seq": 1}]


def test_number_column_prefers_integers__tc_i6_c_bv_040(tmp_path: Path) -> None:
    """TC-I6-C-BV-040: a number-typed column holding an int stays an int."""
    # Given: a schema field typed ``number`` and an integral cell
    # When: both implementations cast the value
    observed = _compare_with_v1(
        tmp_path,
        csv_text="custom/sample2\n3\n",
        invoice=_BASE_INVOICE,
        schema=_SAMPLE_SCHEMA,
        metadata_def=_METADATA_DEF,
    )

    # Then: v1's int-before-float rule is preserved
    assert observed["invoice"]["custom"]["sample2"] == 3
    assert isinstance(observed["invoice"]["custom"]["sample2"], int)


_FAILURE_CASES: tuple[tuple[str, str, dict[str, Any], Any], ...] = (
    ("TC-I6-C-EV-020", "custom/unknown_field\nvalue\n", _SAMPLE_SCHEMA, _METADATA_DEF),
    (
        # ``type`` is required by ``InvoiceSchemaJson``, so a custom field that
        # omits it makes schema parsing itself fail — v1's separate "does not
        # define a type" guard is unreachable through a parsed schema.
        "TC-I6-C-EV-021",
        "custom/untyped\nvalue\n",
        {
            "properties": {
                "custom": {"type": "object", "label": {"ja": "c", "en": "c"}, "properties": {"untyped": {"label": {"ja": "u", "en": "u"}}}},
            },
        },
        _METADATA_DEF,
    ),
    ("TC-I6-C-EV-022", "custom/sample3\nnot-an-int\n", _SAMPLE_SCHEMA, _METADATA_DEF),
    ("TC-I6-C-EV-023", "custom/invert_phase_axis\nyes\n", _SAMPLE_SCHEMA, _METADATA_DEF),
    ("TC-I6-C-EV-024", "custom/sample2\ninf\n", _SAMPLE_SCHEMA, _METADATA_DEF),
    ("TC-I6-C-EV-025", "meta/undefined\nvalue\n", _SAMPLE_SCHEMA, _METADATA_DEF),
    (
        "TC-I6-C-EV-026",
        "meta/comment\nvalue\n",
        _SAMPLE_SCHEMA,
        {"comment": {"variable": True, "schema": {"type": "string"}}},
    ),
    (
        "TC-I6-C-EV-027",
        "meta/comment\nvalue\n",
        _SAMPLE_SCHEMA,
        {"comment": {"schema": {"type": "array"}}},
    ),
    # A ``number`` cell that is not a number at all (neither int nor float).
    ("TC-I6-C-EV-032", "custom/sample2\nnot-a-number\n", _SAMPLE_SCHEMA, _METADATA_DEF),
    # A metadata value that does not match its declared type.
    ("TC-I6-C-EV-033", "meta/temperature\nnot-a-number\n", _SAMPLE_SCHEMA, _METADATA_DEF),
    # metadata-def.json is valid JSON but not an object.
    ("TC-I6-C-EV-034", "meta/comment\nvalue\n", _SAMPLE_SCHEMA, ["not", "an", "object"]),
)


@pytest.mark.parametrize(
    ("csv_text", "schema", "metadata_def"),
    [
        pytest.param(csv_text, schema, metadata_def, id=case_id)
        for case_id, csv_text, schema, metadata_def in _FAILURE_CASES
    ],
)
def test_rejected_rows_fail_exactly_like_v1(
    tmp_path: Path,
    csv_text: str,
    schema: dict[str, Any],
    metadata_def: Any,
) -> None:
    """TC-I6-C-EV-020..027: rejected rows raise v1's StructuredError message."""
    # Given: a row v1 refuses to merge
    # When: both implementations process it
    # Then: the same StructuredError text reaches the caller
    _compare_failure_with_v1(
        tmp_path,
        csv_text=csv_text,
        invoice=_BASE_INVOICE,
        schema=schema,
        metadata_def=metadata_def,
    )


def test_scalar_attribute_container_is_rejected__tc_i6_c_ev_029(tmp_path: Path) -> None:
    """TC-I6-C-EV-029: a non-list attribute container is a StructuredError."""
    # Given: an inherited sample whose generalAttributes is not a list
    broken = json.loads(json.dumps(_BASE_INVOICE))
    broken["sample"]["generalAttributes"] = "not-a-list"

    # When: a general attribute column targets that container
    error = _compare_failure_with_v1(
        tmp_path,
        csv_text=f"sample/sampleId,sample/generalAttributes.{_GENERAL_TERM}\nkeep,general-a\n",
        invoice=broken,
        schema=_SAMPLE_SCHEMA,
        metadata_def=_METADATA_DEF,
    )

    # Then: the container contract is reported, not a TypeError
    assert "generalAttributes" in str(error)


def test_missing_metadata_definition_skips_meta_columns__tc_i6_c_ev_028(tmp_path: Path) -> None:
    """TC-I6-C-EV-028: without metadata-def.json v1 skips meta columns silently."""
    # Given: a meta column but no metadata definition file
    # When: both implementations build the tile
    observed = _compare_with_v1(
        tmp_path,
        csv_text="basic/dataName,meta/comment\nrow-name,memo-a\n",
        invoice=_BASE_INVOICE,
        schema=_SAMPLE_SCHEMA,
        metadata_def=None,
    )

    # Then: the invoice is written and no metadata.json is produced
    assert observed["invoice"]["basic"]["dataName"] == "row-name"
    assert observed["metadata"] is None


def test_header_only_row_csv_writes_the_base_invoice__tc_i6_c_ev_030(tmp_path: Path) -> None:
    """TC-I6-C-EV-030: a CSV without data rows yields no row dictionary."""
    # Given: a row CSV containing only its header
    # When: both implementations build the tile
    observed = _compare_with_v1(
        tmp_path,
        csv_text="basic/dataName\n",
        invoice=_BASE_INVOICE,
        schema=_SAMPLE_SCHEMA,
        metadata_def=_METADATA_DEF,
    )

    # Then: the inherited invoice is written unchanged and no row data exists
    assert observed["row_data"] is None
    assert observed["invoice"]["basic"]["dataName"] == "inherited-name"


def test_missing_row_csv_is_rejected__tc_i6_c_ev_031(tmp_path: Path) -> None:
    """TC-I6-C-EV-031: an unreadable row CSV fails like v1."""
    # Given / When / Then: both implementations raise the same StructuredError
    _compare_failure_with_v1(
        tmp_path,
        csv_text="basic/dataName\nrow-name\n",
        invoice=_BASE_INVOICE,
        schema=_SAMPLE_SCHEMA,
        metadata_def=_METADATA_DEF,
        write_rowfile=False,
    )


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
