r"""Issue 599 (writers) EP/BV: output options for ``save_csv``, ``save_json`` and ``save_invoice``.

EP table
| API | Partition | Rationale | Expected | Test ID |
|---|---|---|---|---|
| save_csv | default call (with and without preamble) | byte parity | UTF-8, QUOTE_MINIMAL, os.linesep bytes as before | I599W-EP-001 |
| save_csv | utf-8-sig + Japanese + row preamble + CRLF | BOM CSV | one BOM, rows and table share CRLF | I599W-EP-002 |
| save_csv | str preamble + utf-8-sig + CRLF | verbatim | str kept as given, one BOM | I599W-EP-003 |
| save_csv | QUOTE_NONNUMERIC + float_format/header/index | combined options | rows and table quoted alike | I599W-EP-004 |
| save_csv | cp932 encoding | legacy encodings | bytes decode as cp932 | I599W-EP-005 |
| save_csv | blank_line_after_preamble with CRLF | same line ending | blank line is CRLF | I599W-EP-006 |
| save_json | default call | byte parity | indent 2, non-ASCII kept | I599W-EP-007 |
| save_json | indent=4 / ensure_ascii=True | options | stdlib json output, kind kept | I599W-EP-008 |
| save_json | indent=None | compact | one line, stdlib separators | I599W-EP-009 |
| save_invoice | default call | byte parity | indent 4, None kept, tile invoice.json | I599W-EP-010 |
| save_invoice | indent=2 | option | two-space output | I599W-EP-011 |
| save_invoice | drop_none=True, nested | sanitised invoice | None keys/items removed, 0/False/"" kept | I599W-EP-012 |
| save_invoice | InvoiceData / Mapping input | non-destructive | inputs unchanged | I599W-EP-013 |
| all | runtime vs .pyi | stub parity | same parameters, kinds, defaults | I599W-EP-014 |
| all | direct call / flow call | @node transparency | metadata kept, recorded in a run | I599W-EP-015 |
| save_csv | PBT text frames x options | invariant | file == options applied once, BOM count <= 1 | I599W-EP-016 |
| save_invoice | PBT nested JSON | invariant | no None left, idempotent, input unchanged | I599W-EP-017 |
| save_csv | missing values in rows and table, each supported quoting | same missing-value field | preamble None == table None/NaN | I599W-EP-018 |
| save_csv | quoting not int | invalid | TypeError, nothing written | I599W-NEG-001 |
| save_csv | quoting int outside MINIMAL/ALL/NONNUMERIC/NONE (incl. 4 QUOTE_STRINGS, 5 QUOTE_NOTNULL) | unsupported | ValueError, nothing written | I599W-NEG-012 |
| save_csv | lineterminator empty / not str | invalid | ValueError / TypeError, nothing written | I599W-NEG-002 |
| save_csv | unknown encoding | invalid | LookupError, nothing written | I599W-NEG-003 |
| save_csv | character the encoding lacks | encode failure | UnicodeEncodeError, nothing written | I599W-NEG-004 |
| save_csv | QUOTE_NONE with a delimiter in a field | serialization failure | csv.Error, nothing written | I599W-NEG-005 |
| all | new option passed positionally | keyword-only | TypeError, nothing written | I599W-NEG-006 |
| save_json | indent negative / bool / str | invalid | ValueError / TypeError, nothing written | I599W-NEG-007 |
| save_json | ensure_ascii not bool | invalid | TypeError, nothing written | I599W-NEG-008 |
| save_json | non-serializable / lone surrogate | serialization / encode failure | TypeError / UnicodeEncodeError, nothing written | I599W-NEG-009 |
| save_invoice | drop_none not bool / bad indent | invalid | TypeError / ValueError, nothing written | I599W-NEG-010 |
| save_invoice | non-serializable value | serialization failure | TypeError, nothing written | I599W-NEG-011 |

BV table
| API | Boundary | Rationale | Expected | Test ID |
|---|---|---|---|---|
| save_csv | lineterminator="\n" on every OS | explicit LF | no CR in the file | I599W-BV-001 |
| save_csv | utf-8-sig with empty preamble | BOM once | exactly one BOM | I599W-BV-002 |
| save_json | indent=0 | smallest indent | newlines, no spaces | I599W-BV-003 |
| save_invoice | dict emptied / list of only None | edge of removal | {} and [] kept | I599W-BV-004 |
| save_invoice | tuple in content | sequence kind | written as a JSON array | I599W-BV-005 |
"""

from __future__ import annotations

import ast
import copy
import csv
import inspect
import json
import os
from collections.abc import Callable, Mapping
from io import StringIO
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rdetoolkit.nodes import save_csv, save_invoice, save_json
from rdetoolkit.testing import make_output_context
from rdetoolkit.types import InvoiceData, OutputContext

NL = os.linesep
BOM = b"\xef\xbb\xbf"
STUB = Path(__file__).resolve().parents[3] / "src" / "rdetoolkit" / "nodes" / "structured.pyi"


def _frame() -> pd.DataFrame:
    return pd.DataFrame({"エネルギー": [100.0, 101.5], "強度": [1234, 1300], "名前": ["試料A", "b,c"]})


def _rows_text(rows: list[list[object]], *, quoting: int = csv.QUOTE_MINIMAL, lineterminator: str = NL) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer, quoting=quoting, lineterminator=lineterminator)
    writer.writerows(rows)
    return buffer.getvalue()


@pytest.fixture
def write_spy(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Record every ``OutputContext.write_bytes`` call while keeping its behaviour."""
    calls: list[tuple[str, str]] = []
    original = OutputContext.write_bytes

    def spy(self: OutputContext, kind: Any, filename: str, content: bytes) -> Path:
        calls.append((kind, filename))
        return original(self, kind, filename, content)

    monkeypatch.setattr(OutputContext, "write_bytes", spy)
    return calls


# ---------------------------------------------------------------- save_csv


class TestSaveCsvOptions:
    def test_default_call_keeps_bytes__i599w_ep_001(self, tmp_path: Path) -> None:
        """I599W-EP-001: default calls write the same bytes as before #599."""
        # Given: a frame with non-ASCII text and a row preamble
        frame = _frame()
        rows: list[list[object]] = [["#title", "試料"], ["#n", 3]]
        out = make_output_context(tmp_path)
        # When: saving without the new options
        plain = save_csv(frame, out, "plain.csv")
        lead = save_csv(frame, out, "lead.csv", preamble=rows, blank_line_after_preamble=True)
        # Then: bytes equal the pre-#599 UTF-8 / QUOTE_MINIMAL / os.linesep output
        table = frame.to_csv(index=False, lineterminator=NL)
        assert plain.read_bytes() == table.encode("utf-8")
        assert lead.read_bytes() == (_rows_text(rows) + NL + table).encode("utf-8")

    def test_bom_japanese_rows_crlf__i599w_ep_002(self, tmp_path: Path) -> None:
        """I599W-EP-002: utf-8-sig with a row preamble and CRLF writes one BOM."""
        # Given: Japanese rows and table
        frame = _frame()
        rows: list[list[object]] = [["#title", "日本語タイトル"], ["#dimension", "x", "y"]]
        # When: saving as a BOM CSV with CRLF
        path = save_csv(frame, make_output_context(tmp_path), "bom.csv", encoding="utf-8-sig", lineterminator="\r\n", preamble=rows)
        data = path.read_bytes()
        # Then: one BOM at the start, every line ends with CRLF
        assert data.startswith(BOM)
        assert data.count(BOM) == 1
        expected = _rows_text(rows, lineterminator="\r\n") + frame.to_csv(index=False, lineterminator="\r\n")
        assert data.decode("utf-8-sig") == expected
        assert data.count(b"\n") == data.count(b"\r\n")

    def test_str_preamble_verbatim__i599w_ep_003(self, tmp_path: Path) -> None:
        """I599W-EP-003: a str preamble keeps its own line endings and quoting."""
        # Given: a str preamble with LF line endings and unquoted text
        frame = _frame()
        text = "#title,生データ\n#x,a b\n"
        # When: saving with CRLF and QUOTE_ALL
        path = save_csv(
            frame,
            make_output_context(tmp_path),
            "raw.csv",
            preamble=text,
            encoding="utf-8-sig",
            lineterminator="\r\n",
            quoting=csv.QUOTE_ALL,
        )
        data = path.read_bytes()
        # Then: the preamble is unchanged, only the table uses the options
        assert data.count(BOM) == 1
        assert data.decode("utf-8-sig") == text + frame.to_csv(index=False, lineterminator="\r\n", quoting=csv.QUOTE_ALL)

    def test_nonnumeric_with_table_options__i599w_ep_004(self, tmp_path: Path) -> None:
        """I599W-EP-004: QUOTE_NONNUMERIC applies to rows and table with float_format/header/index."""
        # Given: a parameter table and a mixed-type preamble row
        frame = pd.DataFrame({"p": [1.0, 2.25]}, index=["a", "b"])
        rows: list[list[object]] = [["#param", 3, 1.5]]
        # When: saving with QUOTE_NONNUMERIC, CRLF and the existing table options
        path = save_csv(
            frame,
            make_output_context(tmp_path),
            "param.csv",
            quoting=csv.QUOTE_NONNUMERIC,
            lineterminator="\r\n",
            preamble=rows,
            float_format="%.3f",
            header=["value"],
            index=True,
        )
        # Then: rows follow csv.writer, the table follows DataFrame.to_csv, which
        # quotes float_format output because it is already text (v1 parity)
        expected = _rows_text(rows, quoting=csv.QUOTE_NONNUMERIC, lineterminator="\r\n") + frame.to_csv(
            quoting=csv.QUOTE_NONNUMERIC,
            lineterminator="\r\n",
            float_format="%.3f",
            header=["value"],
            index=True,
        )
        assert path.read_bytes() == expected.encode("utf-8")
        assert path.read_bytes() == b'"#param",3,1.5\r\n"","value"\r\n"a","1.000"\r\n"b","2.250"\r\n'

    def test_nonnumeric_numbers_unquoted__i599w_ep_004(self, tmp_path: Path) -> None:
        """I599W-EP-004: without float_format, QUOTE_NONNUMERIC leaves numbers bare in both parts."""
        # Given: the same table without float_format
        frame = pd.DataFrame({"p": [1.0, 2.25]}, index=["a", "b"])
        # When
        path = save_csv(
            frame,
            make_output_context(tmp_path),
            "param.csv",
            quoting=csv.QUOTE_NONNUMERIC,
            lineterminator="\r\n",
            preamble=[["#param", 3]],
            header=["value"],
            index=True,
        )
        # Then
        assert path.read_bytes() == b'"#param",3\r\n"","value"\r\n"a",1.0\r\n"b",2.25\r\n'

    @pytest.mark.parametrize(
        ("quoting", "line"),
        [(csv.QUOTE_MINIMAL, "a,,,1"), (csv.QUOTE_ALL, '"a","","","1"'), (csv.QUOTE_NONNUMERIC, '"a","","",1'), (csv.QUOTE_NONE, "a,,,1")],
        ids=["minimal", "all", "nonnumeric", "none"],
    )
    def test_missing_values_match__i599w_ep_018(self, tmp_path: Path, quoting: int, line: str) -> None:
        """I599W-EP-018: a missing value is written the same way in preamble rows and the table."""
        # Given: a None in a preamble row and None / NaN in the table
        frame = pd.DataFrame({"s": ["a"], "o": [None], "f": [float("nan")], "i": [1]})
        # When
        path = save_csv(frame, make_output_context(tmp_path), "m.csv", quoting=quoting, lineterminator="\n", preamble=[["a", None, None, 1]], header=False)
        # Then: both lines carry the same missing-value fields
        assert path.read_text(encoding="utf-8") == f"{line}\n{line}\n"

    def test_cp932_encoding__i599w_ep_005(self, tmp_path: Path) -> None:
        """I599W-EP-005: a legacy encoding is applied to the whole file."""
        # Given: Japanese content
        frame = _frame()
        # When: saving as cp932
        path = save_csv(frame, make_output_context(tmp_path), "sjis.csv", encoding="cp932", preamble=[["#題", "値"]])
        # Then: the file decodes as cp932 and is not UTF-8
        assert path.read_bytes().decode("cp932") == _rows_text([["#題", "値"]]) + frame.to_csv(index=False, lineterminator=NL)
        with pytest.raises(UnicodeDecodeError):
            path.read_bytes().decode("utf-8")

    def test_blank_line_uses_lineterminator__i599w_ep_006(self, tmp_path: Path) -> None:
        """I599W-EP-006: the blank line after the preamble uses the chosen line ending."""
        # Given: a preamble and a CRLF line ending
        frame = pd.DataFrame({"x": [1]})
        # When: saving with a blank line after the preamble
        path = save_csv(frame, make_output_context(tmp_path), "b.csv", preamble=[["#t"]], blank_line_after_preamble=True, lineterminator="\r\n")
        # Then: the blank line is CRLF
        assert path.read_bytes() == b"#t\r\n\r\nx\r\n1\r\n"

    def test_explicit_lf__i599w_bv_001(self, tmp_path: Path) -> None:
        """I599W-BV-001: an explicit LF line ending writes no CR on every OS."""
        # Given / When: an explicit LF line ending
        path = save_csv(_frame(), make_output_context(tmp_path), "lf.csv", lineterminator="\n", preamble=[["#t"]])
        # Then: no CR is written
        assert b"\r" not in path.read_bytes()

    @pytest.mark.parametrize("preamble", [None, "", []], ids=["none", "empty-str", "empty-rows"])
    def test_bom_without_preamble__i599w_bv_002(self, tmp_path: Path, preamble: Any) -> None:
        """I599W-BV-002: utf-8-sig writes one BOM even with no preamble text."""
        # Given / When: a BOM CSV with an empty preamble and a blank-line request
        path = save_csv(_frame(), make_output_context(tmp_path), "b.csv", encoding="utf-8-sig", preamble=preamble, blank_line_after_preamble=True)
        data = path.read_bytes()
        # Then: one BOM, no blank line, table first
        assert data.count(BOM) == 1
        assert data.decode("utf-8-sig") == _frame().to_csv(index=False, lineterminator=NL)


class TestSaveCsvFailures:
    @pytest.mark.parametrize("quoting", ["all", True, None, 1.0], ids=["str", "bool", "none", "float"])
    def test_bad_quoting__i599w_neg_001(self, tmp_path: Path, write_spy: list[Any], quoting: Any) -> None:
        """I599W-NEG-001: a quoting value that is not an int fails before writing."""
        # Given / When / Then: TypeError and no write
        with pytest.raises(TypeError, match="save_csv quoting must be an int"):
            save_csv(_frame(), make_output_context(tmp_path), "x.csv", quoting=quoting)
        assert write_spy == []

    @pytest.mark.parametrize("preamble", [None, [["#p", None]]], ids=["table", "rows"])
    @pytest.mark.parametrize("quoting", [4, 5, 99, -1], ids=["QUOTE_STRINGS", "QUOTE_NOTNULL", "99", "neg"])
    def test_unsupported_quoting__i599w_neg_012(self, tmp_path: Path, write_spy: list[Any], quoting: int, preamble: Any) -> None:
        """I599W-NEG-012: quoting modes whose missing values pandas and csv disagree on are rejected."""
        # Given: a table with a missing value
        frame = pd.DataFrame({"x": [None]})
        # When / Then: ValueError naming the supported constants, and no write
        with pytest.raises(ValueError, match="save_csv quoting must be one of csv.QUOTE_MINIMAL"):
            save_csv(frame, make_output_context(tmp_path), "x.csv", quoting=quoting, preamble=preamble)
        assert write_spy == []

    @pytest.mark.parametrize(("lineterminator", "error"), [("", ValueError), (1, TypeError), (b"\n", TypeError)], ids=["empty", "int", "bytes"])
    def test_bad_lineterminator__i599w_neg_002(self, tmp_path: Path, write_spy: list[Any], lineterminator: Any, error: type[Exception]) -> None:
        """I599W-NEG-002: an empty or non-str line ending fails before writing."""
        # Given / When / Then: the error and no write, even without a preamble
        with pytest.raises(error, match="lineterminator must"):
            save_csv(_frame(), make_output_context(tmp_path), "x.csv", lineterminator=lineterminator)
        assert write_spy == []

    def test_unknown_encoding__i599w_neg_003(self, tmp_path: Path, write_spy: list[Any]) -> None:
        """I599W-NEG-003: an unknown encoding fails before writing."""
        # Given / When / Then
        with pytest.raises(LookupError):
            save_csv(_frame(), make_output_context(tmp_path), "x.csv", encoding="no-such-codec")
        assert write_spy == []

    @pytest.mark.parametrize(("encoding", "preamble"), [("ascii", None), ("cp932", [["#😀"]]), ("latin-1", "#日本\n")])
    def test_unencodable__i599w_neg_004(self, tmp_path: Path, write_spy: list[Any], encoding: str, preamble: Any) -> None:
        """I599W-NEG-004: a character the encoding lacks fails before writing."""
        # Given / When / Then
        with pytest.raises(UnicodeEncodeError):
            save_csv(_frame(), make_output_context(tmp_path), "x.csv", encoding=encoding, preamble=preamble)
        assert write_spy == []
        assert not (tmp_path / "structured" / "x.csv").exists()

    @pytest.mark.parametrize("preamble", [None, [["a,b"]]], ids=["table", "rows"])
    def test_quote_none_needs_escape__i599w_neg_005(self, tmp_path: Path, write_spy: list[Any], preamble: Any) -> None:
        """I599W-NEG-005: QUOTE_NONE with a delimiter in a field fails before writing."""
        # Given: a field containing the delimiter
        frame = pd.DataFrame({"x": ["a,b"]}) if preamble is None else pd.DataFrame({"x": [1]})
        # When / Then: csv.Error and no write
        with pytest.raises(csv.Error):
            save_csv(frame, make_output_context(tmp_path), "x.csv", quoting=csv.QUOTE_NONE, preamble=preamble)
        assert write_spy == []

    def test_existing_contract_errors_kept(self, tmp_path: Path, write_spy: list[Any]) -> None:
        """I599W-NEG-005: MultiIndex and str rows still fail with their existing errors."""
        # Given: a MultiIndex frame and a str preamble row
        multi = pd.DataFrame([[1]], columns=pd.MultiIndex.from_tuples([("a", "b")]))
        out = make_output_context(tmp_path)
        # When / Then: ValueError / TypeError and no write
        with pytest.raises(ValueError, match="MultiIndex"):
            save_csv(multi, out, "x.csv", encoding="utf-8-sig")
        with pytest.raises(TypeError, match="preamble rows"):
            save_csv(_frame(), out, "x.csv", preamble=["#title"], lineterminator="\r\n")  # type: ignore[list-item]
        assert write_spy == []


# ---------------------------------------------------------------- save_json


class TestSaveJsonOptions:
    CONTENT: Mapping[str, Any] = {"名前": "試料", "n": [1, {"x": None}]}

    def test_default_call_keeps_bytes__i599w_ep_007(self, tmp_path: Path) -> None:
        """I599W-EP-007: the default call writes indent 2 with non-ASCII kept."""
        # Given / When
        path = save_json(self.CONTENT, make_output_context(tmp_path), "a.json")
        # Then
        assert path.read_bytes() == json.dumps(self.CONTENT, ensure_ascii=False, indent=2).encode("utf-8")

    def test_indent_and_ascii__i599w_ep_008(self, tmp_path: Path) -> None:
        """I599W-EP-008: indent and ensure_ascii follow the stdlib, kind is kept."""
        # Given
        out = make_output_context(tmp_path)
        # When: indent 4 with ASCII escapes in another directory
        path = save_json(self.CONTENT, out, "a.json", kind="meta", indent=4, ensure_ascii=True)
        # Then
        assert path.parent == out.meta
        assert path.read_bytes() == json.dumps(self.CONTENT, ensure_ascii=True, indent=4).encode("utf-8")
        assert b"\\u540d" in path.read_bytes()

    def test_compact__i599w_ep_009(self, tmp_path: Path) -> None:
        """I599W-EP-009: indent=None writes one line."""
        # Given / When
        path = save_json(self.CONTENT, make_output_context(tmp_path), "a.json", indent=None)
        # Then
        assert path.read_bytes() == '{"名前": "試料", "n": [1, {"x": null}]}'.encode()

    def test_indent_zero__i599w_bv_003(self, tmp_path: Path) -> None:
        """I599W-BV-003: indent=0 inserts newlines without spaces."""
        # Given / When
        path = save_json({"a": 1}, make_output_context(tmp_path), "a.json", indent=0)
        # Then
        assert path.read_bytes() == b'{\n"a": 1\n}'


class TestSaveJsonFailures:
    @pytest.mark.parametrize(("indent", "error"), [(-1, ValueError), (True, TypeError), ("2", TypeError), (1.5, TypeError)])
    def test_bad_indent__i599w_neg_007(self, tmp_path: Path, write_spy: list[Any], indent: Any, error: type[Exception]) -> None:
        """I599W-NEG-007: a negative, bool, str or float indent fails before writing."""
        # Given / When / Then
        with pytest.raises(error, match="save_json indent must"):
            save_json({"a": 1}, make_output_context(tmp_path), "a.json", indent=indent)
        assert write_spy == []

    @pytest.mark.parametrize("ensure_ascii", [1, "yes", None])
    def test_bad_ensure_ascii__i599w_neg_008(self, tmp_path: Path, write_spy: list[Any], ensure_ascii: Any) -> None:
        """I599W-NEG-008: a non-bool ensure_ascii fails before writing."""
        # Given / When / Then
        with pytest.raises(TypeError, match="save_json ensure_ascii must be a bool"):
            save_json({"a": 1}, make_output_context(tmp_path), "a.json", ensure_ascii=ensure_ascii)
        assert write_spy == []

    @pytest.mark.parametrize(("content", "error"), [({"a": object()}, TypeError), ({"a": "\ud800"}, UnicodeEncodeError)], ids=["object", "surrogate"])
    def test_serialize_and_encode_failures__i599w_neg_009(self, tmp_path: Path, write_spy: list[Any], content: Any, error: type[Exception]) -> None:
        """I599W-NEG-009: serialization and encoding failures happen before writing."""
        # Given / When / Then
        with pytest.raises(error):
            save_json(content, make_output_context(tmp_path), "a.json")
        assert write_spy == []

    def test_surrogate_escaped_with_ascii(self, tmp_path: Path) -> None:
        """I599W-EP-008: ensure_ascii=True escapes a lone surrogate instead of failing."""
        # Given / When
        path = save_json({"a": "\ud800"}, make_output_context(tmp_path), "a.json", ensure_ascii=True, indent=None)
        # Then
        assert path.read_bytes() == b'{"a": "\\ud800"}'


# ---------------------------------------------------------------- save_invoice


def _invoice_raw() -> dict[str, Any]:
    return {
        "datasetId": "d1",
        "basic": {"dataName": "名前", "description": None, "experimentId": ""},
        "custom": {"count": 0, "flag": False, "note": None, "nested": {"a": None, "b": [None, 0, None, {"c": None, "d": ""}]}},
        "sample": {"names": [None], "ownerId": None, "composition": {"x": None}},
    }


class TestSaveInvoiceOptions:
    def test_default_call_keeps_bytes__i599w_ep_010(self, tmp_path: Path) -> None:
        """I599W-EP-010: the default call writes indent 4 with None kept into the tile's invoice.json."""
        # Given
        out = make_output_context(tmp_path)
        raw = _invoice_raw()
        # When
        path = save_invoice(InvoiceData(raw=raw, mode="invoice"), out)
        # Then
        assert path == out.invoice / "invoice.json"
        assert path.read_bytes() == json.dumps(raw, ensure_ascii=False, indent=4).encode("utf-8")

    def test_indent_two__i599w_ep_011(self, tmp_path: Path) -> None:
        """I599W-EP-011: indent=2 writes two-space JSON."""
        # Given / When
        path = save_invoice(_invoice_raw(), make_output_context(tmp_path), indent=2)
        # Then
        assert path.read_bytes() == json.dumps(_invoice_raw(), ensure_ascii=False, indent=2).encode("utf-8")

    def test_drop_none_nested__i599w_ep_012(self, tmp_path: Path) -> None:
        """I599W-EP-012: drop_none removes None keys and items recursively, keeps 0/False/''."""
        # Given / When
        path = save_invoice(_invoice_raw(), make_output_context(tmp_path), drop_none=True)
        # Then: falsy non-None values survive, emptied containers stay (BV-004)
        assert json.loads(path.read_bytes()) == {
            "datasetId": "d1",
            "basic": {"dataName": "名前", "experimentId": ""},
            "custom": {"count": 0, "flag": False, "nested": {"b": [0, {"d": ""}]}},
            "sample": {"names": [], "composition": {}},
        }

    def test_drop_none_bytes_format(self, tmp_path: Path) -> None:
        """I599W-EP-012: drop_none keeps indent and non-ASCII formatting."""
        # Given / When
        path = save_invoice({"a": None, "名": "値"}, make_output_context(tmp_path), drop_none=True, indent=None)
        # Then
        assert path.read_bytes() == '{"名": "値"}'.encode()

    @pytest.mark.parametrize("wrap", [lambda raw: InvoiceData(raw=raw, mode="invoice"), dict, MappingProxyType], ids=["invoice-data", "dict", "proxy"])
    def test_inputs_unchanged__i599w_ep_013(self, tmp_path: Path, wrap: Callable[[dict[str, Any]], Any]) -> None:
        """I599W-EP-013: InvoiceData.raw and the input mapping are not modified."""
        # Given
        raw = _invoice_raw()
        before = copy.deepcopy(raw)
        content = wrap(raw)
        # When
        save_invoice(content, make_output_context(tmp_path), drop_none=True)
        # Then
        assert raw == before
        if isinstance(content, InvoiceData):
            assert content.raw == before

    def test_only_none_and_tuple__i599w_bv_004_bv_005(self, tmp_path: Path) -> None:
        """I599W-BV-004/005: all-None list becomes [], tuples are written as arrays."""
        # Given / When
        path = save_invoice({"a": [None, None], "t": (None, 1, (None,))}, make_output_context(tmp_path), drop_none=True, indent=None)
        # Then
        assert path.read_bytes() == b'{"a": [], "t": [1, []]}'


class TestSaveInvoiceFailures:
    @pytest.mark.parametrize(
        ("kwargs", "error"),
        [
            ({"drop_none": 1}, TypeError),
            ({"drop_none": "yes"}, TypeError),
            ({"indent": -4}, ValueError),
            ({"indent": False}, TypeError),
        ],
        ids=["drop-int", "drop-str", "indent-neg", "indent-bool"],
    )
    def test_bad_options__i599w_neg_010(self, tmp_path: Path, write_spy: list[Any], kwargs: dict[str, Any], error: type[Exception]) -> None:
        """I599W-NEG-010: invalid options fail before writing."""
        # Given / When / Then
        with pytest.raises(error, match="save_invoice (drop_none|indent) must"):
            save_invoice(_invoice_raw(), make_output_context(tmp_path), **kwargs)
        assert write_spy == []

    @pytest.mark.parametrize("drop_none", [False, True])
    def test_unserializable__i599w_neg_011(self, tmp_path: Path, write_spy: list[Any], drop_none: bool) -> None:
        """I599W-NEG-011: a non-JSON value fails before writing."""
        # Given / When / Then
        with pytest.raises(TypeError, match="not JSON serializable"):
            save_invoice({"custom": {"x": {1, 2}}}, make_output_context(tmp_path), drop_none=drop_none)
        assert write_spy == []


# ---------------------------------------------------------------- shared


class TestSignatureAndTransparency:
    EXPECTED = {
        "save_csv": {"encoding": "utf-8", "quoting": csv.QUOTE_MINIMAL, "lineterminator": None},
        "save_json": {"indent": 2, "ensure_ascii": False},
        "save_invoice": {"indent": 4, "drop_none": False},
    }

    @pytest.mark.parametrize("fn", [save_csv, save_json, save_invoice], ids=lambda f: f.__name__)
    def test_runtime_matches_stub__i599w_ep_014(self, fn: Callable[..., Any]) -> None:
        """I599W-EP-014: runtime and .pyi agree on names, kinds and defaults."""
        # Given: the stub's function definition
        tree = ast.parse(STUB.read_text(encoding="utf-8"))
        stub = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == fn.__name__)
        stub_pos = [a.arg for a in stub.args.args]
        stub_kw = {a.arg: ast.literal_eval(d) if not isinstance(d, ast.Attribute) else d.attr for a, d in zip(stub.args.kwonlyargs, stub.args.kw_defaults, strict=True)}  # type: ignore[arg-type]
        # When: reading the runtime signature
        params = inspect.signature(fn).parameters.values()
        runtime_pos = [p.name for p in params if p.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD]
        runtime_kw = {p.name: p.default for p in params if p.kind is inspect.Parameter.KEYWORD_ONLY}
        # Then: same positional prefix, same keyword-only defaults, new options keyword-only
        assert stub_pos == runtime_pos
        assert set(stub_kw) == set(runtime_kw)
        for name, default in self.EXPECTED[fn.__name__].items():
            assert runtime_kw[name] == default
        assert stub_kw.get("quoting", "QUOTE_MINIMAL") in ("QUOTE_MINIMAL", csv.QUOTE_MINIMAL)
        assert {k: v for k, v in stub_kw.items() if k != "quoting"} == {k: v for k, v in runtime_kw.items() if k != "quoting"}

    @pytest.mark.parametrize(
        ("call", "args"),
        [
            (save_csv, (pd.DataFrame({"x": [1]}), "x.csv", "utf-8")),
            (save_json, ({"a": 1}, "a.json", "struct", 4)),
            (save_invoice, ({"a": 1}, 4)),
        ],
        ids=["csv", "json", "invoice"],
    )
    def test_new_options_keyword_only__i599w_neg_006(self, tmp_path: Path, write_spy: list[Any], call: Callable[..., Any], args: tuple[Any, ...]) -> None:
        """I599W-NEG-006: new options cannot be passed positionally."""
        # Given: the output context in its positional slot
        out = make_output_context(tmp_path)
        positional = (args[0], out, *args[1:])
        # When / Then
        with pytest.raises(TypeError, match="positional argument"):
            call(*positional)
        assert write_spy == []

    @pytest.mark.parametrize("fn", [save_csv, save_json, save_invoice], ids=lambda f: f.__name__)
    def test_node_metadata_kept__i599w_ep_015(self, fn: Callable[..., Any]) -> None:
        """I599W-EP-015: @node keeps the function name and documents the new options."""
        # Given / When / Then
        doc = fn.__doc__ or ""
        assert fn.__name__ in {"save_csv", "save_json", "save_invoice"}
        for name in self.EXPECTED[fn.__name__]:
            assert f"{name}:" in doc

    def test_flow_call__i599w_ep_015(self, tmp_path: Path) -> None:
        """I599W-EP-015: inside a flow the options apply and each call is recorded."""
        from rdetoolkit.core.flow import flow
        from rdetoolkit.testing import run_flow

        captured: dict[str, bytes] = {}

        # Given: a flow using every new option
        @flow
        def write_all(out: OutputContext, invoice: InvoiceData) -> None:
            csv_path = save_csv(pd.DataFrame({"名": ["値"]}), out, "a.csv", encoding="utf-8-sig", lineterminator="\r\n", quoting=csv.QUOTE_ALL)
            json_path = save_json({"名": 1}, out, "a.json", indent=None, ensure_ascii=True)
            edited = {**invoice.raw, "basic": {**invoice.raw["basic"], "description": None}}
            invoice_path = save_invoice(edited, out, drop_none=True, indent=2)
            captured.update(csv=csv_path.read_bytes(), json=json_path.read_bytes(), invoice=invoice_path.read_bytes())

        fixture = tmp_path / "fixture"
        fixture.mkdir()
        (fixture / "in.txt").write_text("x", encoding="utf-8")
        # When: running it through the Runner
        report = run_flow(write_all, fixture)
        # Then: the run succeeds, the calls are recorded, and the bytes carry the options
        assert report.status == "success"
        calls = report.iterations[0]["node_calls"]
        assert [call["node_id"].rsplit(".", 1)[-1] for call in calls] == ["save_csv", "save_json", "save_invoice"]
        assert captured["csv"] == BOM + '"名"\r\n"値"\r\n'.encode()
        assert captured["json"] == b'{"\\u540d": 1}'
        written = json.loads(captured["invoice"])
        assert captured["invoice"] == json.dumps(written, ensure_ascii=False, indent=2).encode("utf-8")
        assert "description" not in written["basic"]
        assert not _has_none(written)
        assert written["basic"]["dataName"] == "test"
        assert b'"description"' not in captured["invoice"]


# ---------------------------------------------------------------- properties

_text = st.text(alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\r\n\x00"), max_size=6)
_json = st.recursive(
    st.none() | st.booleans() | st.integers(-5, 5) | st.just("") | st.text(max_size=3),
    lambda inner: st.lists(inner, max_size=4) | st.dictionaries(st.text(max_size=3), inner, max_size=4),
    max_leaves=20,
)


def _has_none(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, dict):
        return any(_has_none(v) for v in value.values())
    if isinstance(value, list):
        return any(_has_none(v) for v in value)
    return False


@pytest.mark.property
@settings(deadline=None)
@given(
    cells=st.lists(_text, min_size=1, max_size=4),
    rows=st.lists(st.lists(_text | st.integers(-9, 9), max_size=3), max_size=3),
    encoding=st.sampled_from(["utf-8", "utf-8-sig", "utf-16"]),
    quoting=st.sampled_from([csv.QUOTE_MINIMAL, csv.QUOTE_ALL, csv.QUOTE_NONNUMERIC]),
    lineterminator=st.sampled_from(["\n", "\r\n"]),
    blank=st.booleans(),
)
def test_save_csv_applies_options_once__i599w_ep_016(
    tmp_path_factory: pytest.TempPathFactory,
    cells: list[str],
    rows: list[list[object]],
    encoding: str,
    quoting: int,
    lineterminator: str,
    blank: bool,
) -> None:
    """I599W-EP-016: the file is the preamble and table encoded once with the same options."""
    # Given: a one-column text frame and random preamble rows
    frame = pd.DataFrame({"c": cells})
    out = make_output_context(tmp_path_factory.mktemp("p"))
    # When
    path = save_csv(frame, out, "p.csv", encoding=encoding, quoting=quoting, lineterminator=lineterminator, preamble=rows, blank_line_after_preamble=blank)
    # Then
    lead = _rows_text(rows, quoting=quoting, lineterminator=lineterminator)
    if lead and blank:
        lead += lineterminator
    expected = lead + frame.to_csv(index=False, quoting=quoting, lineterminator=lineterminator)
    data = path.read_bytes()
    assert data == expected.encode(encoding)
    assert data.count(BOM) <= 1


@pytest.mark.property
@settings(deadline=None)
@given(content=st.dictionaries(st.text(max_size=3), _json, max_size=4))
def test_drop_none_invariants__i599w_ep_017(tmp_path_factory: pytest.TempPathFactory, content: dict[str, Any]) -> None:
    """I599W-EP-017: no None remains, dropping twice equals once, the input is unchanged."""
    # Given
    before = copy.deepcopy(content)
    out = make_output_context(tmp_path_factory.mktemp("i"))
    # When
    once = json.loads(save_invoice(content, out, drop_none=True).read_bytes())
    twice = json.loads(save_invoice(once, out, drop_none=True).read_bytes())
    # Then
    assert not _has_none(once)
    assert once == twice
    assert content == before
