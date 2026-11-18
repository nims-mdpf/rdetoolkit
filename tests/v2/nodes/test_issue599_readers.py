"""Issue 599 (readers): encoding and pandas options for the built-in input nodes.

EP table

| API | Partition | Rationale | Expected | Test ID |
|---|---|---|---|---|
| read_text | encoding=None, UTF-8 BOM / CP932 / UTF-8 | detection kept | decoded as before, BOM stripped | I599R-EP-001 |
| read_text | explicit encoding matching the bytes | forced codec | decoded with that codec only | I599R-EP-002 |
| read_text | explicit "utf-8" on a BOM file | strict use | BOM kept as U+FEFF | I599R-EP-003 |
| read_text | explicit codec that cannot decode | no silent fallback | UnicodeDecodeError | I599R-NEG-001 |
| read_text | unknown codec name | invalid | LookupError | I599R-NEG-002 |
| read_text | encoding passed positionally | keyword-only | TypeError | I599R-NEG-003 |
| read_csv_with_header | defaults on BOM / CP932 CSV | detection kept | first row is the header | I599R-EP-004 |
| read_csv_with_header | skiprows over preamble lines | instrument CSVs | header found below preamble | I599R-EP-005 |
| read_csv_with_header | names= with default header | pandas "infer" | no row consumed as header | I599R-EP-006 |
| read_csv_with_header | header=None, dtype=str, keep_default_na=False, sep | pass-through | blanks and "NA" stay strings | I599R-EP-007 |
| read_csv_with_header | explicit encoding | forced codec | decoded with that codec | I599R-EP-008 |
| read_csv_with_header | explicit codec that cannot decode | no silent fallback | UnicodeDecodeError | I599R-NEG-004 |
| read_csv_with_header | unknown codec name | invalid | LookupError | I599R-NEG-005 |
| read_csv_with_header | iterator=True / chunksize=n | not a DataFrame | ValueError, nothing read | I599R-NEG-006 |
| read_csv_with_header | filepath_or_buffer in kwargs | conflicting source | TypeError, no override | I599R-NEG-007 |
| read_csv_with_header | options positionally | keyword-only | TypeError | I599R-NEG-008 |
| read_excel | sheet omitted / str / int | single sheet | DataFrame | I599R-EP-009 |
| read_excel | sheet_name=None | all sheets | dict keyed by sheet name | I599R-EP-010 |
| read_excel | list of str and int | several sheets | dict keyed as given | I599R-EP-011 |
| read_excel | missing sheet in a list | invalid | ValueError | I599R-NEG-009 |
| read_excel | corrupt workbook | invalid | ValueError / BadZipFile | I599R-NEG-010 |
| all readers | direct call | @node transparency | inputs unchanged, handles released | I599R-EP-012 |
| all readers | flow with strict type check | recorded call | success, annotations hold | I599R-EP-013 |
| other io nodes | read_json / read_key_values / read_excel_fills / unzip_inputs | regression | unchanged results | I599R-EP-014 |

BV table

| API | Boundary | Rationale | Expected | Test ID |
|---|---|---|---|---|
| read_text | empty file, explicit encoding | zero bytes | "" | I599R-BV-001 |
| read_csv_with_header | skiprows=0 / chunksize=None / iterator=False | neutral values | DataFrame as default | I599R-BV-002 |
| read_excel | list with one sheet | minimal list | dict with one key | I599R-BV-003 |
| read_excel | empty list | zero sheets | ValueError (pandas) | I599R-NEG-011 |
| read_excel | sheet position == sheet count | off by one | ValueError | I599R-NEG-012 |
"""

from __future__ import annotations

import codecs
import json
import os
import sys
import zipfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from rdetoolkit.nodes import (
    read_csv_with_header,
    read_excel,
    read_excel_fills,
    read_json,
    read_key_values,
    read_text,
    unzip_inputs,
)

_JA = "温度,圧力\n"
# Short CP932 text is not detected reliably; detection tests use a longer sample.
_JA_LONG = "こんにちは世界。日本語の測定データを記録しています。温度と圧力の測定結果①㈱\n"


def _write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def _workbook(path: Path) -> Path:
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"a": [1, 2]}).to_excel(writer, sheet_name="first", index=False)
        pd.DataFrame({"b": ["x"]}).to_excel(writer, sheet_name="second", index=False)
    return path


def _open_paths() -> set[str]:
    fd_dir = Path("/proc/self/fd")
    paths = set()
    for entry in fd_dir.iterdir():
        try:
            paths.add(os.readlink(entry))
        except OSError:
            continue
    return paths


@contextmanager
def _unchanged(path: Path) -> Iterator[None]:
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    yield
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


class TestReadText:
    @pytest.mark.parametrize("data, expected", [
        (codecs.BOM_UTF8 + _JA_LONG.encode("utf-8"), _JA_LONG),
        (_JA_LONG.encode("cp932"), _JA_LONG),
        (_JA_LONG.encode("utf-8"), _JA_LONG),
    ])
    def test_detection_is_kept__i599r_ep_001(self, tmp_path: Path, data: bytes, expected: str) -> None:
        """I599R-EP-001: without encoding the existing detection rule decodes the file."""
        # Given: a BOM, CP932 or plain UTF-8 file
        path = _write(tmp_path / "in.txt", data)
        # When: reading it without an encoding
        actual = read_text(path)
        # Then: the content is decoded and a BOM is not part of the text
        assert actual == expected

    @pytest.mark.parametrize("encoding", ["utf-8", "cp932", "euc_jp", "utf-16"])
    def test_explicit_encoding_is_used__i599r_ep_002(self, tmp_path: Path, encoding: str) -> None:
        """I599R-EP-002: an explicit encoding decodes the bytes with that codec."""
        # Given: a file encoded with a known codec
        path = _write(tmp_path / "in.txt", _JA.encode(encoding))
        # When: reading it with that codec
        actual = read_text(path, encoding=encoding)
        # Then: the text round-trips
        assert actual == _JA

    def test_explicit_utf8_keeps_bom__i599r_ep_003(self, tmp_path: Path) -> None:
        """I599R-EP-003: an explicit codec is applied verbatim, not the detected utf-8-sig."""
        # Given: a UTF-8 file with a BOM
        path = _write(tmp_path / "in.txt", codecs.BOM_UTF8 + b"x")
        # When: forcing plain UTF-8 and the BOM-aware variant
        plain, sig = read_text(path, encoding="utf-8"), read_text(path, encoding="utf-8-sig")
        # Then: only the BOM-aware codec strips the mark
        assert (plain, sig) == ("﻿x", "x")

    def test_empty_file__i599r_bv_001(self, tmp_path: Path) -> None:
        """I599R-BV-001: an empty file is an empty string with an explicit codec."""
        # Given: a zero-byte file
        path = _write(tmp_path / "in.txt", b"")
        # When / Then: reading with a codec gives ""
        assert read_text(path, encoding="cp932") == ""

    @pytest.mark.parametrize("data, encoding", [
        (_JA.encode("cp932"), "utf-8"),
        ("é".encode("latin-1"), "utf-8"),
        (_JA.encode("utf-8"), "ascii"),
    ])
    def test_decode_failure_is_not_hidden__i599r_neg_001(self, tmp_path: Path, data: bytes, encoding: str) -> None:
        """I599R-NEG-001: an explicit codec never falls back to a detected one."""
        # Given: bytes that are invalid in the requested codec
        path = _write(tmp_path / "in.txt", data)
        # When / Then: decoding fails instead of switching codecs
        with pytest.raises(UnicodeDecodeError):
            read_text(path, encoding=encoding)

    def test_unknown_codec__i599r_neg_002(self, tmp_path: Path) -> None:
        """I599R-NEG-002: an unknown codec name is rejected by Python's codec lookup."""
        # Given: any text file
        path = _write(tmp_path / "in.txt", b"x")
        # When / Then: an unknown codec raises LookupError
        with pytest.raises(LookupError):
            read_text(path, encoding="no-such-codec")

    def test_encoding_is_keyword_only__i599r_neg_003(self, tmp_path: Path) -> None:
        """I599R-NEG-003: the existing one-positional-argument signature is kept."""
        # Given: any text file
        path = _write(tmp_path / "in.txt", b"x")
        # When / Then: a positional encoding is rejected
        with pytest.raises(TypeError):
            read_text(path, "utf-8")  # type: ignore[misc]

    def test_missing_file__i599r_neg_013(self, tmp_path: Path) -> None:
        """I599R-NEG-013: a missing file still raises FileNotFoundError with a codec."""
        # Given: no file
        # When / Then: the OS error propagates unwrapped
        with pytest.raises(FileNotFoundError):
            read_text(tmp_path / "missing.txt", encoding="utf-8")

    @pytest.mark.property
    @given(st.text(alphabet=st.characters(codec="utf-8", exclude_categories=["Cs"])))
    def test_explicit_utf8_round_trip__i599r_pbt_001(self, text: str) -> None:
        """I599R-PBT-001: any UTF-8 text written as bytes reads back unchanged."""
        # Given: arbitrary text stored as UTF-8 bytes
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp) / "in.txt", text.encode("utf-8"))
            # When: reading it with the explicit codec
            actual = read_text(path, encoding="utf-8")
        # Then: newline translation aside, the text is unchanged
        assert actual == text.replace("\r\n", "\n").replace("\r", "\n")


class TestReadCsvWithHeader:
    @pytest.mark.parametrize("data", [
        codecs.BOM_UTF8 + "名前,値\nあ,1\n".encode(),
        ("名前,値\n" + _JA_LONG.replace(",", "、").strip() + ",1\n").encode("cp932"),
    ])
    def test_defaults_are_kept__i599r_ep_004(self, tmp_path: Path, data: bytes) -> None:
        """I599R-EP-004: the first row stays the header and the codec is detected."""
        # Given: a BOM or CP932 CSV
        path = _write(tmp_path / "in.csv", data)
        # When: reading it with no options
        frame = read_csv_with_header(path)
        # Then: the columns come from the first row without a BOM
        assert list(frame.columns) == ["名前", "値"]
        assert frame["値"].tolist() == [1]

    def test_skiprows_over_preamble__i599r_ep_005(self, tmp_path: Path) -> None:
        """I599R-EP-005: preamble lines are skipped before the header row."""
        # Given: an instrument CSV with two preamble lines of other shapes
        path = _write(tmp_path / "in.csv", "装置,XRD-1\n測定日\nangle,count\n10,5\n".encode("cp932"))
        # When: skipping the preamble
        frame = read_csv_with_header(path, skiprows=2)
        # Then: the third line is the header
        assert frame.to_dict("list") == {"angle": [10], "count": [5]}

    @pytest.mark.parametrize("kwargs, expected_rows", [
        ({"names": ["p", "q"]}, [["a", "b"], ["1", "2"]]),
        ({"names": ["p", "q"], "header": 0}, [["1", "2"]]),
        ({}, [["1", "2"]]),
    ])
    def test_header_inference_follows_pandas__i599r_ep_006(
        self, tmp_path: Path, kwargs: dict[str, Any], expected_rows: list[list[str]],
    ) -> None:
        """I599R-EP-006: names= without header reads every row, as pandas does."""
        # Given: a CSV whose first row is a, b
        path = _write(tmp_path / "in.csv", b"a,b\n1,2\n")
        # When: reading with or without names
        frame = read_csv_with_header(path, dtype=str, **kwargs)
        expected = pd.read_csv(path, dtype=str, **kwargs)
        # Then: the result equals pandas with the same options
        pd.testing.assert_frame_equal(frame, expected)
        assert frame.values.tolist() == expected_rows

    def test_pandas_options_pass_through__i599r_ep_007(self, tmp_path: Path) -> None:
        """I599R-EP-007: header=None, dtype=str, keep_default_na=False and sep keep blank cells."""
        # Given: a semicolon CSV with an empty cell and an "NA" string
        path = _write(tmp_path / "in.csv", b"x;;NA\n1;2;\n")
        # When: reading every cell as text
        frame = read_csv_with_header(path, header=None, dtype=str, keep_default_na=False, sep=";")
        # Then: no value became NaN and no row became the header
        assert list(frame.columns) == [0, 1, 2]
        assert frame.values.tolist() == [["x", "", "NA"], ["1", "2", ""]]

    def test_explicit_encoding__i599r_ep_008(self, tmp_path: Path) -> None:
        """I599R-EP-008: an explicit encoding replaces detection."""
        # Given: a CP932 CSV
        path = _write(tmp_path / "in.csv", "名前\nあ\n".encode("cp932"))
        # When: reading with the codec named
        frame = read_csv_with_header(path, encoding="cp932")
        # Then: the content is decoded
        assert frame.to_dict("list") == {"名前": ["あ"]}

    @pytest.mark.parametrize("kwargs", [{"skiprows": 0}, {"chunksize": None}, {"iterator": False}, {"nrows": 1}])
    def test_neutral_values_still_return_frame__i599r_bv_002(self, tmp_path: Path, kwargs: dict[str, Any]) -> None:
        """I599R-BV-002: options that keep pandas returning a DataFrame are accepted."""
        # Given: a one-row CSV
        path = _write(tmp_path / "in.csv", b"a\n1\n")
        # When: reading with a neutral option value
        frame = read_csv_with_header(path, **kwargs)
        # Then: a DataFrame is returned
        assert isinstance(frame, pd.DataFrame)
        assert frame.to_dict("list") == {"a": [1]}

    def test_decode_failure_is_not_hidden__i599r_neg_004(self, tmp_path: Path) -> None:
        """I599R-NEG-004: an explicit codec never falls back to a detected one."""
        # Given: CP932 bytes
        path = _write(tmp_path / "in.csv", "名前\nあ\n".encode("cp932"))
        # When / Then: forcing UTF-8 fails
        with pytest.raises(UnicodeDecodeError):
            read_csv_with_header(path, encoding="utf-8")

    def test_unknown_codec__i599r_neg_005(self, tmp_path: Path) -> None:
        """I599R-NEG-005: an unknown codec name is rejected."""
        # Given: any CSV
        path = _write(tmp_path / "in.csv", b"a\n1\n")
        # When / Then: the codec lookup fails
        with pytest.raises(LookupError):
            read_csv_with_header(path, encoding="no-such-codec")

    @pytest.mark.parametrize("kwargs", [{"iterator": True}, {"chunksize": 1}, {"chunksize": 0}, {"iterator": True, "chunksize": 2}])
    def test_reader_options_are_rejected__i599r_neg_006(self, tmp_path: Path, kwargs: dict[str, Any]) -> None:
        """I599R-NEG-006: options that make pandas return a TextFileReader are refused."""
        # Given: a valid CSV
        path = _write(tmp_path / "in.csv", b"a\n1\n")
        # When / Then: the node refuses before opening a reader
        with _unchanged(path), pytest.raises(ValueError, match="DataFrame"):
            read_csv_with_header(path, **kwargs)

    def test_source_conflict_is_rejected__i599r_neg_007(self, tmp_path: Path) -> None:
        """I599R-NEG-007: a second source in the pandas options is never silently used."""
        # Given: two different CSV files
        path = _write(tmp_path / "in.csv", b"a\n1\n")
        other = _write(tmp_path / "other.csv", b"b\n2\n")
        # When / Then: naming another source fails
        with pytest.raises(TypeError):
            read_csv_with_header(path, filepath_or_buffer=other)

    @pytest.mark.parametrize("args", [("cp932",), ("utf-8", 1)])
    def test_options_are_keyword_only__i599r_neg_008(self, tmp_path: Path, args: tuple[object, ...]) -> None:
        """I599R-NEG-008: encoding and skiprows cannot be passed positionally."""
        # Given: any CSV
        path = _write(tmp_path / "in.csv", b"a\n1\n")
        # When / Then: positional options are rejected
        with pytest.raises(TypeError):
            read_csv_with_header(path, *args)  # type: ignore[misc]

    @pytest.mark.property
    @given(st.lists(st.sampled_from(["", "NA", "null", "x", " ", "0"]), min_size=1, max_size=6))
    def test_text_cells_survive__i599r_pbt_002(self, cells: list[str]) -> None:
        """I599R-PBT-002: with dtype=str and keep_default_na=False every cell is kept verbatim."""
        # Given: one header-less row of NA-like strings (a lone empty cell is an empty file to pandas)
        import tempfile

        assume(cells != [""])
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(Path(tmp) / "in.csv", (",".join(cells) + "\n").encode("utf-8"))
            # When: reading it as text
            frame = read_csv_with_header(path, header=None, dtype=str, keep_default_na=False, skip_blank_lines=False)
        # Then: the row equals the written cells
        assert frame.values.tolist() == [cells]


class TestReadExcel:
    @pytest.mark.parametrize("kwargs, expected", [
        ({}, {"a": [1, 2]}),
        ({"sheet_name": "second"}, {"b": ["x"]}),
        ({"sheet_name": 1}, {"b": ["x"]}),
    ])
    def test_single_sheet_is_frame__i599r_ep_009(self, tmp_path: Path, kwargs: dict[str, Any], expected: dict[str, list[object]]) -> None:
        """I599R-EP-009: one selected sheet is returned as a DataFrame."""
        # Given: a two-sheet workbook
        path = _workbook(tmp_path / "in.xlsx")
        # When: selecting one sheet or none
        frame = read_excel(path, **kwargs)
        # Then: the result is that sheet's DataFrame
        assert isinstance(frame, pd.DataFrame)
        assert frame.to_dict("list") == expected

    def test_all_sheets_is_dict__i599r_ep_010(self, tmp_path: Path) -> None:
        """I599R-EP-010: sheet_name=None returns every sheet keyed by its name."""
        # Given: a two-sheet workbook
        path = _workbook(tmp_path / "in.xlsx")
        # When: reading all sheets
        sheets = read_excel(path, sheet_name=None)
        # Then: the keys and frames equal pandas
        expected = pd.read_excel(path, sheet_name=None)
        assert list(sheets) == ["first", "second"]
        for name, frame in expected.items():
            pd.testing.assert_frame_equal(sheets[name], frame)

    @pytest.mark.parametrize("selection", [["second", 0], [1], ["first"]])
    def test_listed_sheets_keep_keys__i599r_ep_011_bv_003(self, tmp_path: Path, selection: list[str | int]) -> None:
        """I599R-EP-011 / I599R-BV-003: a list returns a dict keyed exactly as requested."""
        # Given: a two-sheet workbook
        path = _workbook(tmp_path / "in.xlsx")
        # When: reading the listed sheets with header options passed through
        sheets = read_excel(path, sheet_name=selection, header=0)
        # Then: keys keep their str/int form and order
        assert list(sheets) == selection
        expected = pd.read_excel(path, sheet_name=selection, header=0)
        for key, frame in expected.items():
            pd.testing.assert_frame_equal(sheets[key], frame)

    @pytest.mark.parametrize("selection", [["missing"], ["first", "missing"], [2], []])
    def test_invalid_sheet_lists__i599r_neg_009_011_012(self, tmp_path: Path, selection: list[str | int]) -> None:
        """I599R-NEG-009/011/012: missing, out-of-range or empty sheet lists raise ValueError."""
        # Given: a two-sheet workbook
        path = _workbook(tmp_path / "in.xlsx")
        # When / Then: pandas' ValueError propagates and the file is untouched
        with _unchanged(path), pytest.raises(ValueError):
            read_excel(path, sheet_name=selection)

    @pytest.mark.parametrize("data, error", [
        (b"not a workbook", ValueError),
        (b"PK\x03\x04broken", zipfile.BadZipFile),
        (b"", ValueError),
    ])
    @pytest.mark.parametrize("sheet_name", [0, None, ["first"]])
    def test_corrupt_workbook__i599r_neg_010(
        self, tmp_path: Path, data: bytes, error: type[Exception], sheet_name: Any,
    ) -> None:
        """I599R-NEG-010: a corrupt workbook raises for single and multi-sheet reads."""
        # Given: bytes that are not a workbook
        path = _write(tmp_path / "in.xlsx", data)
        # When / Then: the parser error propagates unwrapped
        with _unchanged(path), pytest.raises(error):
            read_excel(path, sheet_name=sheet_name)


_CALLS: list[tuple[Callable[..., Any], str, bytes, dict[str, Any]]] = [
    (read_text, "in.txt", _JA_LONG.encode("cp932"), {}),
    (read_text, "in.txt", _JA.encode("cp932"), {"encoding": "cp932"}),
    (read_csv_with_header, "in.csv", b"a\n1\n", {"skiprows": 0, "dtype": str}),
]


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="open handles are listed through /proc")
class TestResources:
    @pytest.mark.parametrize("reader, name, data, kwargs", _CALLS)
    def test_text_inputs_unchanged_and_closed__i599r_ep_012(
        self, tmp_path: Path, reader: Callable[..., object], name: str, data: bytes, kwargs: dict[str, Any],
    ) -> None:
        """I599R-EP-012: reading leaves the input byte-identical and holds no handle."""
        # Given: an input file
        path = _write(tmp_path / name, data)
        # When: reading it directly
        with _unchanged(path):
            reader(path, **kwargs)
        # Then: no descriptor still points at it
        assert str(path) not in _open_paths()

    @pytest.mark.parametrize("sheet_name", [0, None, ["second", 0], ["missing"]])
    def test_workbook_unchanged_and_closed__i599r_ep_012(self, tmp_path: Path, sheet_name: Any) -> None:
        """I599R-EP-012: workbook reads release the file, also after a failed lookup."""
        # Given: a two-sheet workbook
        path = _workbook(tmp_path / "in.xlsx")
        # When: reading (or failing to read) the selection
        with _unchanged(path), suppress(ValueError):
            read_excel(path, sheet_name=sheet_name)
        # Then: no descriptor still points at the workbook
        assert str(path) not in _open_paths()


def test_flow_uses_new_options_under_strict_typing__i599r_ep_013(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """I599R-EP-013: the options work inside a recorded flow with strict type checks."""
    from rdetoolkit import flow, workflows
    from rdetoolkit.nodes import save_text
    from rdetoolkit.types import InputPaths, OutputContext
    from tests.v2.runner.test_event_log_robustness_k4 import _build_tree

    # Given: a dataset with a CP932 text, a preamble CSV and a two-sheet workbook
    _build_tree(tmp_path / "data")
    inputs = tmp_path / "data/inputdata"
    (inputs / "file_0.txt").unlink()
    _write(inputs / "a.txt", "測定\n".encode("cp932"))
    _write(inputs / "b.csv", b"# preamble\nx,y\n1,\n")
    _workbook(inputs / "c.xlsx")
    monkeypatch.chdir(tmp_path)

    @flow
    def pipeline(paths: InputPaths, out: OutputContext) -> None:
        by_name = {path.name: path for path in paths.rawfiles}
        text = read_text(by_name["a.txt"], encoding="cp932")
        table = read_csv_with_header(by_name["b.csv"], skiprows=1, dtype=str, keep_default_na=False)
        sheets = read_excel(by_name["c.xlsx"], sheet_name=None)
        listed = read_excel(by_name["c.xlsx"], sheet_name=["second", 0])
        single = read_excel(by_name["c.xlsx"], sheet_name="second")
        summary = {
            "text": text, "table": table.values.tolist(), "sheets": sorted(sheets),
            "listed": list(listed), "single": single.columns.tolist(),
        }
        save_text(json.dumps(summary, ensure_ascii=False), out, "summary.json")

    # When: running it with strict argument and return checks
    report = workflows.run(flow=pipeline, config={"execution": {"type_check": "strict"}})
    # Then: the run succeeds with the expected values
    assert report.status == "success", report.error
    summary = json.loads((tmp_path / "data/structured/summary.json").read_text(encoding="utf-8"))
    assert summary == {
        "text": "測定\n", "table": [["1", ""]], "sheets": ["first", "second"],
        "listed": ["second", 0], "single": ["b"],
    }


class TestNeighbourRegression:
    def test_neighbour_nodes_are_unchanged__i599r_ep_014(self, tmp_path: Path) -> None:
        """I599R-EP-014: read_json, read_key_values, read_excel_fills and unzip_inputs keep their results."""
        # Given: inputs for each neighbouring node
        json_path = _write(tmp_path / "in.json", json.dumps({"k": _JA_LONG}, ensure_ascii=False).encode("cp932"))
        kv_path = _write(tmp_path / "kv.csv", b"key,value\na,1\n")
        workbook = _workbook(tmp_path / "in.xlsx")
        archive = tmp_path / "in.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("m.txt", "x")
        # When: calling them directly
        decoded = read_json(json_path)
        values = read_key_values(kv_path)
        fills = read_excel_fills(workbook, column="A", sheet_name="first")
        extracted = unzip_inputs(archive, tmp_path / "out")
        # Then: the results are those of the unchanged nodes
        assert decoded == {"k": _JA_LONG}
        assert values == {"a": "1"}
        assert fills == [None, None]
        assert [path.name for path in extracted] == ["m.txt"]
