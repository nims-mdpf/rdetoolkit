"""GA603: cast invoice ``custom`` values by schema and map labels to keys.

EP table
========

=========================  ==========================  ==================================  ================
API                        Partition                   Expected                            Test ID
=========================  ==========================  ==================================  ================
set_custom_fields          integer text / unit text    int, unit dropped (v1)              GA603-EP-001
set_custom_fields          number int-like / float     int preferred, else float (v1)      GA603-EP-002
set_custom_fields          boolean text / non-text     "true"/"false" or truthiness (v1)   GA603-EP-003
set_custom_fields          date / date-time / time     normalised text (v1)                GA603-EP-004
set_custom_fields          date objects                normalised text                     GA603-EP-005
set_custom_fields          string, other or no format  value unchanged                     GA603-EP-006
set_custom_fields          None / NaN / NaT            stored as None                      GA603-EP-007
set_custom_fields          pd.NA / NumPy NaN / NaT     stored as None                      GA603-EP-019
set_custom_fields          NumPy scalars               cast as the Python value            GA603-EP-020
set_custom_fields          undeclared key              StructuredError code 1              GA603-EP-008
set_custom_fields          uncastable value            StructuredError code 1, v1 message  GA603-EP-009
set_custom_fields          unparseable date / object   StructuredError code 1, chained     GA603-EP-010
set_custom_fields          unsupported schema type     StructuredError code 1              GA603-EP-011
set_custom_fields          no schema anywhere          ValueError                          GA603-EP-012
set_custom_fields          schema path / non-object    loaded / ValueError                 GA603-EP-013
set_custom_fields          cast=False                  verbatim, schema not read           GA603-EP-014
resolve_custom_key         ja / en label               key                                 GA603-EP-015
resolve_custom_key         unknown label               StructuredError code 1              GA603-EP-016
resolve_custom_key         label on two keys           StructuredError code 1, both keys   GA603-EP-017
resolve_custom_key         lang restriction            other language not matched          GA603-EP-018
=========================  ==========================  ==================================  ================

BV table
========

=========================  ==========================  ==================================  ================
API                        Boundary                    Expected                            Test ID
=========================  ==========================  ==================================  ================
set_custom_fields          empty updates               equal copy, input untouched         GA603-BV-001
set_custom_fields          existing vs new key         order kept, new key appended        GA603-BV-002
set_custom_fields          empty string for integer    StructuredError (v1)                GA603-BV-003
set_custom_fields          missing custom section      section created                     GA603-BV-004
set_custom_fields          integral vs fractional 3.x  int vs error for integer            GA603-BV-005
resolve_custom_key         ja == en on one key         one match, not ambiguous            GA603-BV-006
resolve_custom_key         surrounding whitespace      stripped before comparison          GA603-BV-007
resolve_custom_key         schema without custom       StructuredError (unknown)           GA603-BV-008
set_custom_fields          numpy_nullable Excel row    saved invoice.json, blanks null     GA603-BV-009
=========================  ==========================  ==================================  ================
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, strategies as st

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.nodes import read_excel, resolve_custom_key, save_invoice, set_custom_fields
from rdetoolkit.rde2util import castval
from rdetoolkit.types import InvoiceData, OutputContext

SCHEMA: dict[str, Any] = {
    "properties": {
        "custom": {
            "type": "object",
            "label": {"ja": "固有情報", "en": "Custom"},
            "properties": {
                "count": {"type": "integer", "label": {"ja": "回数", "en": "Count"}},
                "power": {"type": "number", "label": {"ja": "出力", "en": "Power"}},
                "enabled": {"type": "boolean", "label": {"ja": "有効", "en": "Enabled"}},
                "measured_date": {"type": "string", "format": "date", "label": {"ja": "測定日", "en": "Measured date"}},
                "measured_at": {"type": "string", "format": "date-time", "label": {"ja": "測定日時", "en": "Measured at"}},
                "start_time": {"type": "string", "format": "time", "label": {"ja": "開始時刻", "en": "Start time"}},
                "link": {"type": "string", "format": "uri", "label": {"ja": "リンク", "en": "Link"}},
                "operator": {"type": "string", "label": {"ja": "測定者", "en": "Operator"}},
                "xrd": {"type": "string", "label": {"ja": "XRD", "en": "XRD"}},
                "note_a": {"type": "string", "label": {"ja": "備考", "en": "Note"}},
                "note_b": {"type": "string", "label": {"ja": "備考", "en": "Remark"}},
                "tags": {"type": "array", "label": {"ja": "タグ", "en": "Tags"}},
            },
        },
    },
}


def _invoice(custom: dict[str, Any] | None = None, *, schema: dict[str, Any] | None = SCHEMA) -> InvoiceData:
    raw: dict[str, Any] = {"basic": {"dataName": "sample"}}
    if custom is not None:
        raw["custom"] = custom
    return InvoiceData(raw=raw, mode="invoice", schema=schema)


def _custom(updates: dict[str, Any]) -> dict[str, Any]:
    return set_custom_fields(_invoice({}), updates).raw["custom"]


def _cast_error(updates: dict[str, Any]) -> StructuredError:
    with pytest.raises(StructuredError) as info:
        set_custom_fields(_invoice({}), updates)
    return info.value


class TestCastBySchemaType:
    @pytest.mark.parametrize(("value", "expected"), [("12", 12), (" 12 mm", 12), (7, 7), ("-3", -3)])
    def test_integer_text_and_unit__ga603_ep_001(self, value: Any, expected: int) -> None:
        """GA603-EP-001: integer fields keep v1's digits-with-unit rule."""
        # Given: an integer field and text or int input
        # When: setting the value
        actual = _custom({"count": value})["count"]
        # Then: the value is the v1 integer, with the unit dropped
        assert actual == expected
        assert type(actual) is int
        assert actual == castval(value, "integer", None)

    @pytest.mark.parametrize(("value", "expected", "kind"), [("3", 3, int), ("3.0", 3.0, float), ("1e3", 1000.0, float), ("2.5 W", 2.5, float), (4, 4, int)])
    def test_number_prefers_int__ga603_ep_002(self, value: Any, expected: float, kind: type) -> None:
        """GA603-EP-002: number fields prefer an int when the text is integral (v1)."""
        # Given: a number field
        # When: setting integral and fractional values
        actual = _custom({"power": value})["power"]
        # Then: v1's int-first rule decides the Python type
        assert actual == expected
        assert type(actual) is kind
        assert actual == castval(value, "number", None)

    @pytest.mark.parametrize(("value", "expected"), [("true", True), (" FALSE ", False), (True, True), (0, False), (1, True)])
    def test_boolean_text_and_truthiness__ga603_ep_003(self, value: Any, *, expected: bool) -> None:
        """GA603-EP-003: boolean text is strict, other values use truthiness (v1)."""
        # Given: a boolean field
        # When: setting text and non-text values
        actual = _custom({"enabled": value})["enabled"]
        # Then: the v1 boolean is stored
        assert actual is expected
        assert actual == castval(value, "boolean", None)

    @pytest.mark.parametrize(
        ("key", "value", "expected"),
        [
            ("measured_date", "2023/07/19", "2023-07-19"),
            ("measured_date", "2023-07-19 10:20:30", "2023-07-19"),
            ("measured_at", "2023/07/19 10:20:30", "2023-07-19T10:20:30"),
            ("start_time", "2023/07/19 10:20:30", "10:20:30"),
        ],
    )
    def test_date_formats_normalised__ga603_ep_004(self, key: str, value: str, expected: str) -> None:
        """GA603-EP-004: date, date-time and time strings are normalised as in v1."""
        # Given: a formatted string field and a slash-separated date
        # When: setting the value
        actual = _custom({key: value})[key]
        # Then: the v1 castval normalisation is applied
        assert actual == expected
        fmt = SCHEMA["properties"]["custom"]["properties"][key]["format"]
        assert actual == castval(value, "string", fmt)

    @pytest.mark.parametrize(
        ("key", "value", "expected"),
        [
            ("measured_date", dt.date(2023, 7, 19), "2023-07-19"),
            ("measured_at", dt.date(2023, 7, 19), "2023-07-19T00:00:00"),
            ("measured_at", dt.datetime(2023, 7, 19, 10, 20, 30), "2023-07-19T10:20:30"),  # noqa: DTZ001 - spreadsheet datetimes are naive
            ("start_time", pd.Timestamp("2023-07-19 10:20:30"), "10:20:30"),
        ],
    )
    def test_date_objects_normalised__ga603_ep_005(self, key: str, value: Any, expected: str) -> None:
        """GA603-EP-005: spreadsheet date objects are accepted (v1 raised TypeError)."""
        # Given: date objects as read by openpyxl or pandas
        # When: setting the value
        actual = _custom({key: value})[key]
        # Then: the text equals the text of the same date given as a string
        assert actual == expected

    @pytest.mark.parametrize(("key", "value"), [("operator", "Taro"), ("operator", ""), ("operator", 5), ("link", "https://example.org/a"), ("xrd", "  padded ")])
    def test_string_unchanged__ga603_ep_006(self, key: str, value: Any) -> None:
        """GA603-EP-006: strings without a date format are stored unchanged."""
        # Given: a plain string field or a uri-formatted one
        # When: setting the value
        actual = _custom({key: value})[key]
        # Then: the value is unchanged (v1 failed on uri values: it tried to parse a date)
        assert actual == value

    @pytest.mark.parametrize("value", [None, float("nan"), pd.NaT])
    @pytest.mark.parametrize("key", ["count", "power", "enabled", "measured_date", "operator"])
    def test_missing_values_stored_as_none__ga603_ep_007(self, key: str, value: Any) -> None:
        """GA603-EP-007: None, NaN and NaT clear the field for every type."""
        # Given: a field holding a value and a missing spreadsheet cell
        invoice = _invoice({key: "old"})
        # When: setting the missing value
        actual = set_custom_fields(invoice, {key: value}).raw["custom"][key]
        # Then: the field is null instead of an error or False
        assert actual is None


    @pytest.mark.parametrize(
        "value",
        [pd.NA, np.float32("nan"), np.float64("nan"), np.datetime64("NaT", "ns"), np.timedelta64("NaT", "ns")],
        ids=["pd.NA", "float32-nan", "float64-nan", "datetime64-nat", "timedelta64-nat"],
    )
    @pytest.mark.parametrize("key", ["count", "power", "enabled", "measured_date", "operator"])
    def test_pandas_and_numpy_missing_values_stored_as_none__ga603_ep_019(self, key: str, value: Any) -> None:
        """GA603-EP-019: pandas / NumPy missing scalars clear the field like None."""
        # Given: a field holding a value and a missing cell as read by pandas or NumPy
        invoice = _invoice({key: "old"})
        # When: setting the missing value
        actual = set_custom_fields(invoice, {key: value}).raw["custom"][key]
        # Then: the field is null, not an error, True, or an unserializable scalar
        assert actual is None

    @pytest.mark.parametrize(
        ("key", "value", "expected"),
        [
            ("count", np.int64(3), 3),
            ("count", np.float32(3.0), 3),
            ("power", np.float32(2.5), 2.5),
            ("power", np.int32(4), 4),
            ("enabled", np.bool_(False), False),
            ("operator", np.int64(5), 5),
            ("operator", np.str_("Taro"), "Taro"),
            ("measured_date", np.datetime64("2023-07-19T10:20:30"), "2023-07-19"),
        ],
    )
    def test_numpy_scalars_cast_as_python_values__ga603_ep_020(self, key: str, value: Any, expected: Any) -> None:
        """GA603-EP-020: NumPy scalars are cast as the equal Python value."""
        # Given: a NumPy scalar as read from a pandas frame
        # When: setting the value
        actual = _custom({key: value})[key]
        # Then: the stored value is the plain Python value, so it serializes as JSON
        assert actual == expected
        assert type(actual) is type(expected)


class TestCastFailures:
    def test_undeclared_key__ga603_ep_008(self) -> None:
        """GA603-EP-008: a key outside the schema is rejected with the SmartTable message."""
        # Given/When: updating a key the schema does not declare
        error = _cast_error({"unknown_key": "1"})
        # Then: a StructuredError with code 1 names the field
        assert error.ecode == 1
        assert str(error) == "Field 'custom.unknown_key' is not defined in invoice.schema.json."

    @pytest.mark.parametrize(("key", "value", "expected_type"), [("count", "abc", "integer"), ("count", "1e3", "integer"), ("power", "W", "number"), ("enabled", "yes", "boolean"), ("count", True, "integer")])
    def test_uncastable_value__ga603_ep_009(self, key: str, value: Any, expected_type: str) -> None:
        """GA603-EP-009: an uncastable value raises the v1 _assign_invoice_val message."""
        # Given/When: a value that does not fit the declared type
        error = _cast_error({key: value})
        # Then: the v1 message and code 1, chained to the castval error
        assert error.ecode == 1
        assert str(error) == f"Value for invoice.json field 'custom.{key}' does not match the type defined in invoice.schema.json (expected: {expected_type})."
        assert isinstance(error.__cause__, StructuredError)

    @pytest.mark.parametrize(("key", "value", "cause"), [("measured_date", "not a date", ValueError), ("measured_date", "", ValueError), ("start_time", 12, TypeError), ("measured_at", dt.time(1, 2), TypeError)])
    def test_unparseable_date__ga603_ep_010(self, key: str, value: Any, cause: type[Exception]) -> None:
        """GA603-EP-010: date parser failures become the same StructuredError."""
        # Given/When: a value dateutil cannot parse (v1 leaked the parser error)
        error = _cast_error({key: value})
        # Then: the type mismatch is reported uniformly, with the parser error chained
        assert error.ecode == 1
        assert f"'custom.{key}'" in str(error)
        assert "(expected: string)" in str(error)
        assert isinstance(error.__cause__, cause)

    def test_unsupported_schema_type__ga603_ep_011(self) -> None:
        """GA603-EP-011: a non-scalar schema type cannot be cast."""
        # Given/When: an array-typed field
        error = _cast_error({"tags": ["a"]})
        # Then: v1's castval rejection is reported with the field name
        assert error.ecode == 1
        assert "(expected: array)" in str(error)

    def test_no_schema__ga603_ep_012(self) -> None:
        """GA603-EP-012: casting requires a schema from the argument or the invoice."""
        # Given: an invoice without a schema, as injected in invoice mode
        invoice = _invoice({}, schema=None)
        # When/Then: casting without schema= fails as a usage error
        with pytest.raises(ValueError, match="No invoice schema"):
            set_custom_fields(invoice, {"count": "1"})

    def test_schema_from_path_and_non_object__ga603_ep_013(self, tmp_path: Path) -> None:
        """GA603-EP-013: a schema path is read; a non-object root is rejected."""
        # Given: a schema file and a file whose root is a list
        good = tmp_path / "invoice.schema.json"
        good.write_text(json.dumps(SCHEMA, ensure_ascii=False), encoding="utf-8")
        bad = tmp_path / "list.json"
        bad.write_text("[]", encoding="utf-8")
        invoice = _invoice({}, schema=None)
        # When: casting with each path
        updated = set_custom_fields(invoice, {"count": "2"}, schema=good)
        # Then: the file schema applies, and the list root is a usage error
        assert updated.raw["custom"] == {"count": 2}
        assert updated.schema is None
        with pytest.raises(ValueError, match="must be an object"):
            set_custom_fields(invoice, {"count": "2"}, schema=bad)
        assert resolve_custom_key(good, "Count") == "count"

    def test_explicit_schema_overrides_invoice_schema(self) -> None:
        """GA603-EP-013: schema= takes precedence over invoice.schema."""
        # Given: an invoice schema where count is a string, and SCHEMA where it is an integer
        invoice = _invoice({}, schema={"properties": {"custom": {"properties": {"count": {"type": "string"}}}}})
        # When: passing SCHEMA explicitly
        actual = set_custom_fields(invoice, {"count": "3"}, schema=SCHEMA).raw["custom"]["count"]
        # Then: the explicit schema decides the type
        assert actual == 3

    def test_cast_false_is_verbatim__ga603_ep_014(self) -> None:
        """GA603-EP-014: cast=False stores values as given without reading a schema."""
        # Given: an invoice without a schema and an undeclared key
        invoice = _invoice({"count": 1}, schema=None)
        value = ["a"]
        # When: setting values without casting
        updated = set_custom_fields(invoice, {"count": "12 mm", "extra": value}, cast=False)
        # Then: the values are stored unchanged and copied
        assert updated.raw["custom"] == {"count": "12 mm", "extra": ["a"]}
        value.append("b")
        assert updated.raw["custom"]["extra"] == ["a"]


class TestUpdateBoundaries:
    def test_empty_updates_copy__ga603_bv_001(self) -> None:
        """GA603-BV-001: no updates returns an equal copy and never mutates the input."""
        # Given: an invoice with nested content
        invoice = _invoice({"count": 1, "operator": "A"})
        # When: applying no updates, then one update
        same = set_custom_fields(invoice, {})
        changed = set_custom_fields(invoice, {"count": "5"})
        # Then: equal copies, independent of the original
        assert same == invoice
        assert same.raw is not invoice.raw
        assert invoice.raw["custom"] == {"count": 1, "operator": "A"}
        assert changed.raw["custom"]["count"] == 5
        assert changed.mode == invoice.mode
        assert changed.schema is invoice.schema

    def test_key_order__ga603_bv_002(self) -> None:
        """GA603-BV-002: existing keys keep their position; new keys are appended."""
        # Given: an invoice whose custom section has two keys
        invoice = _invoice({"operator": "A", "count": 1})
        # When: updating the second key and adding a new one
        custom = set_custom_fields(invoice, {"power": "2", "count": "3"}).raw["custom"]
        # Then: invoice.json key order is preserved
        assert list(custom) == ["operator", "count", "power"]

    def test_empty_string_integer__ga603_bv_003(self) -> None:
        """GA603-BV-003: an empty string is a value, not a missing cell (v1)."""
        # Given/When: an empty string for an integer field
        error = _cast_error({"count": ""})
        # Then: the v1 type mismatch is reported
        assert error.ecode == 1
        assert "(expected: integer)" in str(error)

    def test_missing_custom_section__ga603_bv_004(self) -> None:
        """GA603-BV-004: an invoice without a custom section receives one."""
        # Given: an invoice with no custom section
        invoice = _invoice(None)
        # When: setting a field
        updated = set_custom_fields(invoice, {"count": "1"})
        # Then: the section is created and the rest of the invoice is kept
        assert updated.raw == {"basic": {"dataName": "sample"}, "custom": {"count": 1}}

    def test_integral_float_for_integer__ga603_bv_005(self) -> None:
        """GA603-BV-005: 3.0 becomes 3, 3.5 is still rejected."""
        # Given/When: a pandas-style integral float and a fractional float
        actual = _custom({"count": 3.0})["count"]
        error = _cast_error({"count": 3.5})
        # Then: only the integral float is accepted
        assert actual == 3
        assert type(actual) is int
        assert "(expected: integer)" in str(error)


class TestResolveCustomKey:
    @pytest.mark.parametrize(("label", "expected"), [("回数", "count"), ("Count", "count"), ("測定日", "measured_date"), ("Measured date", "measured_date")])
    def test_ja_and_en_labels__ga603_ep_015(self, label: str, expected: str) -> None:
        """GA603-EP-015: either label language resolves to the key."""
        # Given/When: a ja or en label
        # Then: the custom key is returned
        assert resolve_custom_key(SCHEMA, label) == expected

    @pytest.mark.parametrize("label", ["Unknown", "count", "固有情報", ""])
    def test_unknown_label__ga603_ep_016(self, label: str) -> None:
        """GA603-EP-016: keys, section labels and unknown text are not labels."""
        # Given/When: text that is no custom field label
        with pytest.raises(StructuredError) as info:
            resolve_custom_key(SCHEMA, label)
        # Then: code 1 and a message naming the label
        assert info.value.ecode == 1
        assert str(info.value) == f"Label '{label}' does not match any custom field label in invoice.schema.json."

    def test_ambiguous_label__ga603_ep_017(self) -> None:
        """GA603-EP-017: a label shared by two keys is rejected, naming both."""
        # Given/When: the ja label carried by note_a and note_b
        with pytest.raises(StructuredError) as info:
            resolve_custom_key(SCHEMA, "備考")
        # Then: both keys are listed in schema order
        assert info.value.ecode == 1
        assert str(info.value) == "Label '備考' matches more than one custom field in invoice.schema.json: note_a, note_b."

    def test_lang_restriction__ga603_ep_018(self) -> None:
        """GA603-EP-018: lang restricts matching, which also disambiguates."""
        # Given: labels that exist in one language only, and a ja label shared by two keys
        # When/Then: the other language does not match; distinct en labels stay unique
        assert resolve_custom_key(SCHEMA, "Note", lang="en") == "note_a"
        assert resolve_custom_key(SCHEMA, "Remark", lang="en") == "note_b"
        with pytest.raises(StructuredError, match="more than one"):
            resolve_custom_key(SCHEMA, "備考", lang="ja")
        with pytest.raises(StructuredError, match="does not match any"):
            resolve_custom_key(SCHEMA, "Count", lang="ja")
        with pytest.raises(StructuredError, match="does not match any"):
            resolve_custom_key(SCHEMA, "回数", lang="en")

    def test_same_label_in_both_languages__ga603_bv_006(self) -> None:
        """GA603-BV-006: one key whose ja and en labels are equal matches once."""
        # Given/When/Then: the XRD label is on one key only
        assert resolve_custom_key(SCHEMA, "XRD") == "xrd"

    def test_whitespace_stripped__ga603_bv_007(self) -> None:
        """GA603-BV-007: spreadsheet cell whitespace is ignored."""
        # Given/When/Then: a label with surrounding spaces and a newline
        assert resolve_custom_key(SCHEMA, "  出力\n") == "power"

    @pytest.mark.parametrize("schema", [{}, {"properties": []}, {"properties": {"custom": {"properties": {"x": "bad"}}}}])
    def test_schema_without_custom__ga603_bv_008(self, schema: dict[str, Any]) -> None:
        """GA603-BV-008: a schema without usable custom definitions has no labels."""
        # Given/When: a schema lacking custom field definitions
        with pytest.raises(StructuredError, match="does not match any"):
            resolve_custom_key(schema, "Count")
        # Then: setting a field also reports it as undeclared
        with pytest.raises(StructuredError, match="is not defined"):
            set_custom_fields(_invoice({}, schema=schema), {"x": "1"})


class TestSpreadsheetRoundTrip:
    def test_numpy_nullable_excel_row_saved__ga603_bv_009(self, tmp_path: Path, output_context: OutputContext) -> None:
        """GA603-BV-009: a nullable Excel row with blank cells is cast and saved."""
        # Given: a workbook row with values and blank cells, read with nullable dtypes
        workbook = tmp_path / "custom.xlsx"
        pd.DataFrame(
            {"回数": [3, None], "出力": [None, 1.5], "有効": [None, True], "測定者": [None, "Taro"], "測定日": ["2023/07/19", None]},
        ).to_excel(workbook, index=False)
        frame = read_excel(workbook, dtype_backend="numpy_nullable")
        row = {label: frame[label].iloc[0] for label in frame.columns}  # cells keep pd.NA / NumPy scalars
        assert row["測定者"] is pd.NA
        # When: mapping labels to keys, casting by schema, and saving the invoice
        updates = {resolve_custom_key(SCHEMA, label): value for label, value in row.items()}
        path = save_invoice(set_custom_fields(_invoice({}), updates), output_context)
        # Then: the saved invoice holds the cast values and null for the blank cells
        custom = json.loads(path.read_text(encoding="utf-8"))["custom"]
        assert custom == {"count": 3, "power": None, "enabled": None, "operator": None, "measured_date": "2023-07-19"}


class TestNodeAndProperties:
    def test_registered_builtin_node(self) -> None:
        """set_custom_fields is a builtin invoice node; resolve_custom_key is a plain helper."""
        # Given/When: the public functions
        spec = set_custom_fields.__node_spec__  # type: ignore[attr-defined]
        # Then: the node carries the builtin tags; the helper is not a node
        assert spec.id == "rdetoolkit.nodes.invoice.set_custom_fields"
        assert {"builtin", "invoice"} <= set(spec.tags)
        assert not hasattr(resolve_custom_key, "__node_spec__")

    @pytest.mark.property
    @given(st.integers(min_value=-(10**12), max_value=10**12), st.sampled_from(["", " ", " mm", "K"]))
    def test_numeric_text_matches_v1(self, number: int, unit: str) -> None:
        """Numeric text with a unit casts exactly like v1 castval, for both numeric types."""
        # Given: integral text with an optional unit
        text = f"{number}{unit}"
        # When: setting both numeric fields
        custom = _custom({"count": text, "power": text})
        # Then: each value equals the v1 result and is idempotent on re-cast
        assert custom["count"] == castval(text, "integer", None) == number
        assert custom["power"] == castval(text, "number", None)
        assert _custom({"count": custom["count"]})["count"] == custom["count"]
