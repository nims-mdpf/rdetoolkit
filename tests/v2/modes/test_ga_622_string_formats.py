"""GA622: string fields with a non-date ``format`` keep their value (#622).

``rde2util.castval`` used to hand every ``string`` value whose schema declares
any ``format`` to the date parser, so ``uri`` / ``uuid`` / ``markdown`` (or any
other non-date format) failed with a dateutil ``ParserError``. Only ``date``,
``date-time`` and ``time`` are date formats; every other format now leaves the
value unchanged, as a ``string`` field without a format already did. The
callers covered here are the v1 Excel invoice assignment
(``invoicefile._assign_invoice_val``) and the SmartTable ``custom/`` and
``meta/`` columns (``modes.smarttable``); the v2 ``set_custom_fields`` node
already had this rule.

EP table

| API | Partition | Rationale | Expected | Test ID |
|-----|-----------|-----------|----------|---------|
| ``castval`` | string, format uri / uuid / markdown / email / unknown | non-date format | value unchanged | ``GA622-EP-1`` |
| ``castval`` | string, format date / date-time / time | date format | converted as before | ``GA622-EP-2`` |
| ``_assign_invoice_val`` | custom uri / uuid / markdown field | Excel invoice path | value unchanged | ``GA622-EP-3`` |
| ``SmartTableInvoiceBuilder.build`` | ``custom/`` uri / uuid / markdown column | SmartTable custom path | tile invoice keeps the cell text | ``GA622-EP-4`` |
| ``SmartTableInvoiceBuilder.build`` | ``meta/`` column with format uri | SmartTable meta path | metadata keeps the cell text | ``GA622-EP-5`` |
| ``castval`` | string, date format, not a date | invalid | raises ``ValueError`` (dateutil ``ParserError``) | ``GA622-EP-6`` |
| ``_assign_invoice_val`` | custom date field, not a date | invalid | raises ``ValueError`` | ``GA622-EP-7`` |
| ``SmartTableInvoiceBuilder.build`` | ``custom/`` date / time column, not a date | invalid | raises ``StructuredError`` (code 1), no tile invoice | ``GA622-EP-8`` |
| ``SmartTableInvoiceBuilder.build`` | ``meta/`` date column, not a date | invalid | raises ``StructuredError`` (code 1), no metadata file | ``GA622-EP-9`` |

BV table

| API | Boundary | Rationale | Expected | Test ID |
|-----|----------|-----------|----------|---------|
| ``castval`` | int / numeric text / date-like text / empty text, format markdown or uri | type and text kept | value and type unchanged | ``GA622-BV-1`` |
| ``castval`` | empty or blank text, date format | smallest invalid date | raises ``ValueError`` | ``GA622-BV-2`` |
| ``castval`` | number / integer type with a non-date format | format ignored, type still enforced | raises ``StructuredError`` (code 1) | ``GA622-BV-3`` |
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.invoicefile._invoice import _assign_invoice_val
from rdetoolkit.modes.smarttable import SmartTableInvoiceBuilder
from rdetoolkit.rde2util import castval
from tests.v2.modes.fixtures.smarttable_builder import _freeze

_URI = "https://example.org/data/1"
_UUID = "0f8fad5b-d9cb-469f-a165-70867728950e"
_MARKDOWN = "# Note\n\n**bold** text"

#: ``tests/samplefile/invoice.schema.json`` declares sample5 / 6 / 7 as uri / uuid / markdown.
_NON_DATE_CUSTOM = (("sample5", _URI), ("sample6", _UUID), ("sample7", _MARKDOWN))

_METADATA_DEF: dict[str, Any] = {
    "link": {"name": {"ja": "リンク", "en": "Link"}, "schema": {"type": "string", "format": "uri"}},
    "measured": {"name": {"ja": "測定日", "en": "Measured"}, "schema": {"type": "string", "format": "date"}},
}


def _build_tile(tmp_path: Path, row: dict[str, str]) -> dict[str, Path]:
    """Write one SmartTable tile input tree for ``row`` and run the builder on it."""
    tasksupport = tmp_path / "tasksupport"
    tasksupport.mkdir()
    (tmp_path / "invoice").mkdir()
    tile = tmp_path / "divided" / "0001"
    (tile / "invoice").mkdir(parents=True)
    (tile / "meta").mkdir(parents=True)
    rowfile = tmp_path / "temp" / "fsmarttable_case_0001.csv"
    rowfile.parent.mkdir()
    rowfile.write_text(_freeze._row_csv(row), encoding="utf-8")
    invoice_org = tmp_path / "invoice" / "invoice.json"
    invoice_org.write_text(json.dumps(_freeze.BASE_INVOICE, ensure_ascii=False), encoding="utf-8")
    schema_path = tasksupport / "invoice.schema.json"
    schema_path.write_text(json.dumps(_freeze.SAMPLE_SCHEMA, ensure_ascii=False), encoding="utf-8")
    metadata_def_path = tasksupport / "metadata-def.json"
    metadata_def_path.write_text(json.dumps(_METADATA_DEF, ensure_ascii=False), encoding="utf-8")
    paths = {"invoice": tile / "invoice" / "invoice.json", "metadata": tile / "meta" / "metadata.json"}
    SmartTableInvoiceBuilder().build(
        rowfile=rowfile,
        invoice_org=invoice_org,
        invoice_schema_path=schema_path,
        dist_path=paths["invoice"],
        metadata_def_path=metadata_def_path,
        metadata_path=paths["metadata"],
    )
    return paths


@pytest.mark.parametrize(
    ("value", "fmt"),
    [
        pytest.param(_URI, "uri", id="uri"),
        pytest.param(_UUID, "uuid", id="uuid"),
        pytest.param(_MARKDOWN, "markdown", id="markdown"),
        pytest.param("someone@example.org", "email", id="email"),
        pytest.param("anything", "x-template-specific", id="unknown"),
    ],
)
def test_non_date_formats_keep_the_value__ga622_ep_1(value: str, fmt: str) -> None:
    """GA622-EP-1: a string with a non-date format is returned unchanged."""
    # Given: a string value and a schema format that is not a date format
    # When: casting it as a string field
    result = castval(value, "string", fmt)
    # Then: the value is returned exactly as given
    assert result == value


@pytest.mark.parametrize(
    ("value", "fmt", "expected"),
    [
        pytest.param("2026/11/13", "date", "2026-11-13", id="date"),
        pytest.param("2026-11-13 09:30:00", "date-time", "2026-11-13T09:30:00", id="date-time"),
        pytest.param("9:30", "time", "09:30:00", id="time"),
    ],
)
def test_date_formats_still_convert__ga622_ep_2(value: str, fmt: str, expected: str) -> None:
    """GA622-EP-2: date, date-time and time strings are still normalized."""
    # Given: a parseable date text and one of the three date formats
    # When: casting it as a string field
    result = castval(value, "string", fmt)
    # Then: the text is normalized exactly as before the fix
    assert result == expected


@pytest.mark.parametrize(("key", "value"), [pytest.param(key, value, id=key) for key, value in _NON_DATE_CUSTOM])
def test_excel_invoice_keeps_non_date_custom_values__ga622_ep_3(key: str, value: str) -> None:
    """GA622-EP-3: the Excel invoice custom assignment keeps uri / uuid / markdown values."""
    # Given: an invoice object and the sample schema's uri / uuid / markdown custom field
    invoice: dict[str, Any] = {"custom": {}}
    # When: assigning the cell value the way ExcelInvoiceFile does
    _assign_invoice_val(invoice, "custom", key, value, _freeze.SAMPLE_SCHEMA)
    # Then: the stored value is the cell value
    assert invoice["custom"][key] == value


def test_smarttable_keeps_non_date_custom_columns__ga622_ep_4(tmp_path: Path) -> None:
    """GA622-EP-4: SmartTable ``custom/`` uri / uuid / markdown columns reach the tile invoice unchanged."""
    # Given: one SmartTable row with uri / uuid / markdown custom columns
    row = {f"custom/{key}": value for key, value in _NON_DATE_CUSTOM}
    # When: the builder writes the tile invoice
    paths = _build_tile(tmp_path, row)
    # Then: each custom value equals its cell text
    custom = json.loads(paths["invoice"].read_text(encoding="utf-8"))["custom"]
    assert {key: custom[key] for key, _value in _NON_DATE_CUSTOM} == dict(_NON_DATE_CUSTOM)


def test_smarttable_keeps_non_date_meta_columns__ga622_ep_5(tmp_path: Path) -> None:
    """GA622-EP-5: a SmartTable ``meta/`` column with format uri reaches metadata.json unchanged."""
    # Given: one SmartTable row with a meta column whose definition declares format uri
    row = {"meta/link": _URI}
    # When: the builder writes the tile metadata
    paths = _build_tile(tmp_path, row)
    # Then: the constant value is the cell text
    metadata = json.loads(paths["metadata"].read_text(encoding="utf-8"))
    assert metadata["constant"]["link"] == {"value": _URI}


@pytest.mark.parametrize("fmt", ["date", "date-time", "time"])
def test_invalid_dates_are_still_rejected__ga622_ep_6(fmt: str) -> None:
    """GA622-EP-6: a date-formatted string that is not a date still fails."""
    # Given: a text that no date parser accepts and a date format
    # When: casting it as a string field
    # Then: the dateutil parser error (a ValueError) is raised as before
    with pytest.raises(ValueError, match="Unknown string format"):
        castval("not a date", "string", fmt)


def test_excel_invoice_rejects_an_invalid_date__ga622_ep_7() -> None:
    """GA622-EP-7: the Excel invoice custom assignment still rejects a non-date in a date field."""
    # Given: an invoice object and the sample schema's date-formatted custom field
    invoice: dict[str, Any] = {"custom": {}}
    # When: assigning a non-date cell value
    # Then: the parser error is raised and nothing is stored
    with pytest.raises(ValueError, match="Unknown string format"):
        _assign_invoice_val(invoice, "custom", "sample1", "not a date", _freeze.SAMPLE_SCHEMA)
    assert invoice["custom"] == {}


@pytest.mark.parametrize("column", ["custom/sample1", "custom/sample4"], ids=["date", "time"])
def test_smarttable_rejects_an_invalid_date_column__ga622_ep_8(tmp_path: Path, column: str) -> None:
    """GA622-EP-8: a SmartTable date / time custom column with a non-date still fails."""
    # Given: one SmartTable row whose date / time custom column is not a date
    row = {column: "not a date"}
    # When: the builder casts the row
    # Then: the builder reports the parser error as StructuredError (code 1) and writes no tile invoice
    with pytest.raises(StructuredError, match="Failed to initialize invoice from SmartTable: Unknown string format") as excinfo:
        _build_tile(tmp_path, row)
    assert excinfo.value.ecode == 1
    assert not (tmp_path / "divided" / "0001" / "invoice" / "invoice.json").exists()


def test_smarttable_rejects_an_invalid_date_meta_column__ga622_ep_9(tmp_path: Path) -> None:
    """GA622-EP-9: a SmartTable ``meta/`` date column with a non-date still fails."""
    # Given: one SmartTable row whose date-formatted meta column is not a date
    row = {"meta/measured": "not a date"}
    # When: the builder casts the row
    # Then: the builder reports the parser error as StructuredError (code 1) and writes no metadata file
    with pytest.raises(StructuredError, match="Failed to initialize invoice from SmartTable: Unknown string format") as excinfo:
        _build_tile(tmp_path, row)
    assert excinfo.value.ecode == 1
    assert not (tmp_path / "divided" / "0001" / "meta" / "metadata.json").exists()


@pytest.mark.parametrize(
    ("value", "fmt"),
    [
        pytest.param(12, "markdown", id="int-markdown"),
        pytest.param("12", "markdown", id="numeric-text-markdown"),
        pytest.param("2026-11-13", "markdown", id="date-like-text-markdown"),
        pytest.param("", "uri", id="empty-uri"),
    ],
)
def test_boundary_values_keep_value_and_type__ga622_bv_1(value: Any, fmt: str) -> None:
    """GA622-BV-1: a non-date format never changes the value or its type."""
    # Given: a boundary value (non-string, numeric or date-like text, empty text)
    original = copy.deepcopy(value)
    # When: casting it as a string field with a non-date format
    result = castval(value, "string", fmt)
    # Then: the same value of the same type comes back (a date-like markdown text is not normalized)
    assert result == original
    assert type(result) is type(original)


@pytest.mark.parametrize(("value", "fmt"), [pytest.param("", "date", id="empty-date"), pytest.param("   ", "date-time", id="blank-date-time")])
def test_empty_text_in_a_date_field_is_rejected__ga622_bv_2(value: str, fmt: str) -> None:
    """GA622-BV-2: empty or blank text is still not a date."""
    # Given: an empty or blank text and a date format
    # When: casting it as a string field
    # Then: the parser error (a ValueError) is raised
    with pytest.raises(ValueError, match="String does not contain a date"):
        castval(value, "string", fmt)


@pytest.mark.parametrize(
    ("value", "outtype", "fmt"),
    [pytest.param("abc", "number", "markdown", id="number-markdown"), pytest.param("1.5", "integer", "uri", id="integer-uri")],
)
def test_non_string_types_still_enforce_their_type__ga622_bv_3(value: str, outtype: str, fmt: str) -> None:
    """GA622-BV-3: a non-date format on a number / integer field does not relax the type check."""
    # Given: a text that is not of the declared numeric type, with a non-date format
    # When: casting it
    # Then: the type error is raised as StructuredError with code 1
    with pytest.raises(StructuredError) as excinfo:
        castval(value, outtype, fmt)
    assert excinfo.value.ecode == 1
