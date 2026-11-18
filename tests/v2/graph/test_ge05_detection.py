"""GE-05 (#711): conservative, explainable CSV-format inference.

``detect_table_format`` reads a bounded sample of a file (read-only), sniffs encoding,
delimiter, metadata block, header presence and transposed layout, and returns a
``DetectionDecision`` with every candidate, its confidence and its evidence. A reader is
selected only when the top candidate reaches ``SELECT_MIN_CONFIDENCE`` with a margin of
``SELECT_MIN_MARGIN``; otherwise ``reader="auto"`` / ``csv_format="auto"`` /
``ParserFactory.auto_detect`` raise ``AmbiguousFormatError`` naming the candidates and the
remedy (``--csv-format <id>``). Nothing is guessed: a numeric first row is never silently
dropped or turned into data. The legacy default ``csv_format="standard"`` is unchanged (O-4).

Interpretation recorded for the rule table of design.md §2.7: the "transposed" pattern and
the "``name,1,2,3`` + label column" pattern have identical cell types, so they are told
apart by shape: a file with at most as many rows as data columns (series in rows, more
points than series) is transposed (0.9); a taller file, or a truncated sample, is ambiguous
(standard 0.5 / transpose 0.5).

EP table (rule table rows and entry points)
===========================================

| API | Partition | Expected | Test ID |
|---|---|---|---|
| detect | text header, numeric data (incl. numeric first data row) | standard 0.95 selected, all rows kept | TC-GE05-EP-001 |
| detect | UTF-8 BOM | encoding utf-8-sig, clean first column name | TC-GE05-EP-002 |
| detect | Shift-JIS (cp932) / UTF-8 Japanese header | cp932 / utf-8, Japanese names read | TC-GE05-EP-003 |
| detect | quoted commas | delimiter ",", two columns, quotes honoured | TC-GE05-EP-004 |
| detect | leading "#" metadata lines | meta_block 0.9 selected, metadata column names | TC-GE05-EP-005 |
| detect | transposed (wide, label column, numeric row 1) | transpose 0.9 selected | TC-GE05-EP-006 |
| detect | tab-separated | delimiter tab, frame read with it | TC-GE05-EP-007 |
| detect | single column | delimiter ",", standard selected | TC-GE05-EP-008 |
| detect | header row only | standard 0.85, data_rows 0 | TC-GE05-EP-009 |
| read_table / render_graph | auto on a sniffable file | builtin reader with the detected encoding/delimiter; GraphResult.detection | TC-GE05-EP-010 |
| resolve_reader | forced id on an ambiguous file | forced=True, reads with that reader | TC-GE05-EP-011 |
| csv2graph | default csv_format | still "standard" (O-4): numeric header file plots | TC-GE05-EP-012 |
| ParserFactory.auto_detect | standard / transposed / tsv / sjis / meta block | parser for the detected format | TC-GE05-EP-013 |
| rdetoolkit plot --detect | sniffable / ambiguous | exit 0, explanation printed, nothing written | TC-GE05-EP-014 |
| DetectionDecision.explain | sniffed decision | encoding, delimiter, sample, columns, rows | TC-GE05-EP-015 |
| public surface | rdetoolkit.graph.detect_table_format; detection re-exports | same objects | TC-GE05-EP-016 |
| parsers | keyword-only encoding/delimiter | read with them; no-arg behaviour unchanged | TC-GE05-EP-017 |

Negative table
==============

| API | Partition | Expected | Test ID |
|---|---|---|---|
| detect / auto | every sampled row numeric (numeric header) | standard 0.5 / noheader 0.5, AmbiguousFormatError with --csv-format | TC-GE05-NEG-001 |
| detect / auto | mixed first row | standard 0.7 below threshold, ambiguous | TC-GE05-NEG-002 |
| detect / auto | first row ``name,1,2,3`` + label column, tall | standard 0.5 / transpose 0.5, ambiguous | TC-GE05-NEG-003 |
| detect / auto | two delimiters qualify | ambiguous, one candidate per delimiter | TC-GE05-NEG-004 |
| detect / auto | all-text rows | standard 0.6 / noheader 0.4, ambiguous | TC-GE05-NEG-005 |
| detect | empty file / blank lines only | InvalidCSVFormatError "empty", no parser called | TC-GE05-NEG-006 |
| detect | file larger than max_bytes | InvalidCSVFormatError before any read | TC-GE05-NEG-007 |
| detect | undecodable bytes | AmbiguousFormatError naming the encodings tried | TC-GE05-NEG-008 |
| detect | ragged rows (no consistent delimiter) | AmbiguousFormatError naming the field counts | TC-GE05-NEG-009 |
| detect | metadata block with BOM / tab | meta_block below threshold, ambiguous | TC-GE05-NEG-010 |
| detect | missing file | FileNotFoundError | TC-GE05-NEG-011 |
| csv2graph / render_graph | auto on an ambiguous file | AmbiguousFormatError, nothing written | TC-GE05-NEG-012 |
| ParserFactory.auto_detect | numeric header / empty / missing | AmbiguousFormatError / InvalidCSVFormatError / FileNotFoundError | TC-GE05-NEG-013 |
| rdetoolkit plot | --csv-format auto on an ambiguous file | exit 1, remedy printed, nothing written | TC-GE05-NEG-014 |
| detect / auto | any file | bytes and mtime unchanged | TC-GE05-NEG-015 |
| parsers | positional encoding | TypeError (keyword-only) | TC-GE05-NEG-016 |
| detect | first line longer than the sniff window | AmbiguousFormatError | TC-GE05-NEG-017 |
| rdetoolkit plot --detect | missing file / undecodable file | exit 1 / exit 0 with the encoding message | TC-GE05-NEG-018 |
| detect | selected reader cannot read the file | preview empty; read_table raises the reader error | TC-GE05-NEG-019 |

BV table
========

| API | Boundary | Expected | Test ID |
|---|---|---|---|
| detect | file of exactly SNIFF_MAX_BYTES / one byte more | truncated False / True | TC-GE05-BV-001 |
| detect | 5 MB file | at most SNIFF_MAX_BYTES read, truncated, data_rows None, header columns previewed, no parser | TC-GE05-BV-002 |
| detect | more than SNIFF_MAX_ROWS rows within the byte window | sampled_rows == SNIFF_MAX_ROWS, data_rows exact | TC-GE05-BV-003 |
| detect | st_size == max_bytes | accepted | TC-GE05-BV-004 |
| detect | transposed shape: rows == data columns / rows == data columns + 1 | transpose / ambiguous | TC-GE05-BV-005 |
| detect | truncated transposed-pattern sample | ambiguous (shape unknown) | TC-GE05-BV-006 |
| constants | bounds of §2.7 | 65536 / 50 / 2**30 / 0.8 / 0.2 | TC-GE05-BV-007 |
| detect | truncated metadata-block file | meta_block selected, no column preview | TC-GE05-BV-008 |
| selection | confidence 0.79 / 0.8, margin 0.19 / 0.2 | not selected / selected | TC-GE05-BV-009 |
| detect (fixture) | transposed.csv gap 0.6 with SELECT_MIN_MARGIN = 0.6 / 0.61 | selected / ambiguous (margin named, nothing read) | TC-GE05-BV-010 |
| detect (fixtures) | every committed detection fixture, shipped constants | selected iff top >= 0.8 and gap >= 0.2; no selected gap < 0.2 | TC-GE05-BV-011 |
"""

from __future__ import annotations

import contextlib
import shutil
from collections.abc import Iterator
from importlib.metadata import EntryPoint
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from typer.testing import CliRunner

import rdetoolkit.graph as graph_pkg
from rdetoolkit.graph import (
    AmbiguousFormatError,
    DetectionDecision,
    GraphSpec,
    InvalidCSVFormatError,
    OutputSpec,
    read_table,
    render_graph,
)
from rdetoolkit.graph.api.csv2graph import csv2graph
from rdetoolkit.graph.outputs import DirectorySink
from rdetoolkit.graph.parsers import CSVParser, NoHeaderParser, ParserFactory, StandardParser, TransposeParser
from rdetoolkit.graph.readers import base as readers_base
from rdetoolkit.graph.readers import detection, registry, resolve_reader
from rdetoolkit.graph.readers.detection import (
    DEFAULT_MAX_TABLE_BYTES,
    SELECT_MIN_CONFIDENCE,
    SELECT_MIN_MARGIN,
    SNIFF_MAX_BYTES,
    SNIFF_MAX_ROWS,
    detect_table_format,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _copy(name: str, directory: Path) -> Path:
    target = directory / name
    shutil.copyfile(FIXTURES / name, target)
    return target


def _write(directory: Path, name: str, content: str | bytes) -> Path:
    target = directory / name
    if isinstance(content, bytes):
        target.write_bytes(content)
    else:
        target.write_text(content, encoding="utf-8")
    return target


def _scores(decision: DetectionDecision) -> dict[str, float]:
    return {candidate.reader_id: candidate.confidence for candidate in decision.candidates}


def _written(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir()) if directory.exists() else []


@pytest.fixture(autouse=True)
def no_entry_points(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Detection must not depend on installed reader plugins."""

    def fake_entry_points(*, group: str) -> tuple[EntryPoint, ...]:
        return ()

    monkeypatch.setattr(registry.metadata, "entry_points", fake_entry_points)
    yield


@pytest.fixture
def parser_spy(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every call of the legacy parser classes (none expected when detection fails early)."""
    calls: list[str] = []
    for parser_type in (StandardParser, TransposeParser, NoHeaderParser):
        original = parser_type.parse

        def spy(self: Any, csv_path: Path, _original: Any = original, _name: str = parser_type.__name__) -> pd.DataFrame:
            calls.append(_name)
            return _original(self, csv_path)

        monkeypatch.setattr(parser_type, "parse", spy)
    return calls


# --- positive: one case per selecting rule ----------------------------------------------------


def test_header_with_numeric_first_data_row_keeps_every_row__tc_ge05_ep_001(tmp_path: Path) -> None:
    """TC-GE05-EP-001: a text header + numeric data is standard; the numeric first data row stays data."""
    # Given: a headered file whose first data row is fully numeric (the old heuristic chose noheader)
    path = _copy("simple.csv", tmp_path)
    # When
    decision = detect_table_format(path)
    data = read_table(path)
    # Then: standard is selected with high confidence and no row was dropped or reinterpreted
    assert (decision.selected, decision.forced) == ("standard", False)
    assert _scores(decision) == {"standard": 0.95}
    assert (decision.encoding, decision.delimiter, decision.truncated) == ("utf-8", ",", False)
    assert decision.preview_columns == ("time (s)", "voltage (V)")
    assert decision.data_rows == 4
    assert len(data.frame) == 4
    assert data.frame.iloc[0].tolist() == [0.0, 0.0]
    pd.testing.assert_frame_equal(data.frame, StandardParser().parse(path))


def test_bom_is_detected_and_stripped__tc_ge05_ep_002(tmp_path: Path) -> None:
    """TC-GE05-EP-002: a UTF-8 BOM selects utf-8-sig; the first column name has no BOM."""
    # Given
    path = _copy("bom_utf8.csv", tmp_path)
    # When
    decision = detect_table_format(path)
    data = read_table(path)
    # Then
    assert (decision.selected, decision.encoding) == ("standard", "utf-8-sig")
    assert list(data.frame.columns) == ["time (s)", "voltage (V)"]
    assert decision.preview_columns == ("time (s)", "voltage (V)")
    assert decision.data_rows == 3


@pytest.mark.parametrize(("name", "content", "encoding"), [
    ("sjis.csv", None, "cp932"),
    ("utf8_ja.csv", "時間 (s),電圧 (V)\n0,0.0\n1,0.5\n2,1.0\n", "utf-8"),
])
def test_shift_jis_and_utf8_japanese_headers__tc_ge05_ep_003(name: str, content: str | None, encoding: str, tmp_path: Path) -> None:
    """TC-GE05-EP-003: Shift-JIS (cp932) and UTF-8 Japanese headers are read with the right encoding."""
    # Given
    path = _copy(name, tmp_path) if content is None else _write(tmp_path, name, content)
    # When
    decision = detect_table_format(path)
    data = read_table(path)
    # Then
    assert (decision.selected, decision.encoding) == ("standard", encoding)
    assert list(data.frame.columns) == ["時間 (s)", "電圧 (V)"]
    assert data.frame["電圧 (V)"].tolist() == [0.0, 0.5, 1.0]


def test_quoted_commas_are_one_field__tc_ge05_ep_004(tmp_path: Path) -> None:
    """TC-GE05-EP-004: commas inside quotes neither split a field nor make the delimiter ambiguous."""
    # Given
    path = _copy("quoted_commas.csv", tmp_path)
    # When
    decision = detect_table_format(path)
    data = read_table(path)
    # Then
    assert (decision.selected, decision.delimiter) == ("standard", ",")
    assert list(data.frame.columns) == ["time, s", "signal, mV"]
    assert data.frame["signal, mV"].tolist() == [1.5, 2.5, 3.5]


def test_comment_metadata_selects_meta_block__tc_ge05_ep_005(tmp_path: Path) -> None:
    """TC-GE05-EP-005: leading '#' lines select the meta_block reader."""
    # Given
    path = _copy("comment_metadata.csv", tmp_path)
    # When
    decision = detect_table_format(path)
    data = read_table(path)
    # Then
    assert decision.selected == "meta_block"
    assert _scores(decision) == {"meta_block": 0.9}
    assert "5 leading '#' metadata lines" in " ".join(decision.candidates[0].evidence)
    expected_frame, expected_meta = CSVParser.parse(path)
    pd.testing.assert_frame_equal(data.frame, expected_frame)
    assert data.metadata["title"] == expected_meta["title"] == "Run 7"
    assert decision.preview_columns == ("Time (s)", "A (V)", "B (V)")
    assert decision.data_rows == 3


def test_transposed_file_selects_transpose__tc_ge05_ep_006(tmp_path: Path) -> None:
    """TC-GE05-EP-006: label column + numeric cells including row 1, wider than tall -> transpose."""
    # Given: 3 rows x 5 data columns
    path = _copy("transposed.csv", tmp_path)
    # When
    decision = detect_table_format(path)
    data = read_table(path)
    # Then
    assert decision.selected == "transpose"
    assert _scores(decision) == {"transpose": 0.9, "standard": 0.3}
    pd.testing.assert_frame_equal(data.frame, TransposeParser().parse(path))
    assert decision.preview_columns == ("time (s)", "voltage (V)", "current (A)")
    assert decision.data_rows == 5


def test_tab_separated_file__tc_ge05_ep_007(tmp_path: Path) -> None:
    """TC-GE05-EP-007: a TSV is read with the tab delimiter (the legacy path gave one column)."""
    # Given
    path = _copy("tabs.tsv", tmp_path)
    # When
    decision = detect_table_format(path)
    data = read_table(path)
    # Then
    assert (decision.selected, decision.delimiter) == ("standard", "\t")
    assert list(data.frame.columns) == ["time", "voltage"]
    assert data.frame["voltage"].tolist() == [1, 2, 4]
    assert list(StandardParser().parse(path).columns) == ["time\tvoltage"]


def test_single_column_file__tc_ge05_ep_008(tmp_path: Path) -> None:
    """TC-GE05-EP-008: a one-column file has no delimiter to sniff; comma is assumed and stated."""
    # Given
    path = _write(tmp_path, "one.csv", "y\n1\n2\n")
    # When
    decision = detect_table_format(path)
    # Then
    assert (decision.selected, decision.delimiter) == ("standard", ",")
    assert any("single column" in reason for reason in decision.candidates[0].evidence)
    assert decision.data_rows == 2


def test_header_only_file__tc_ge05_ep_009(tmp_path: Path) -> None:
    """TC-GE05-EP-009: a header row without data rows reads as standard with zero rows."""
    # Given
    path = _write(tmp_path, "header.csv", "a,b\n")
    # When
    decision = detect_table_format(path)
    # Then
    assert _scores(decision) == {"standard": 0.85}
    assert (decision.selected, decision.data_rows, decision.preview_columns) == ("standard", 0, ("a", "b"))


def test_auto_reads_with_detected_options_and_records_decision__tc_ge05_ep_010(tmp_path: Path) -> None:
    """TC-GE05-EP-010: render_graph under the default reader="auto" sniffs content and records why."""
    # Given
    path = _copy("tabs.tsv", tmp_path)
    out = tmp_path / "out"
    # When
    result = render_graph(path, GraphSpec(), output=OutputSpec(DirectorySink(out), base_name="t"))
    # Then
    assert isinstance(result.detection, DetectionDecision)
    assert (result.detection.selected, result.detection.delimiter, result.detection.forced) == ("standard", "\t", False)
    assert [series.label for series in result.plan.series] == ["Voltage"]
    assert _written(out) == ["t.png"]


def test_forced_reader_overrides_detection__tc_ge05_ep_011(tmp_path: Path, parser_spy: list[str]) -> None:
    """TC-GE05-EP-011: naming a reader skips detection, even for a file detection calls ambiguous."""
    # Given
    path = _copy("numeric_header.csv", tmp_path)
    # When
    selected, decision = resolve_reader("noheader", path)
    data = read_table(path, reader="noheader")
    # Then
    assert (decision.selected, decision.forced, decision.sampled_bytes) == ("noheader", True, 0)
    assert selected.reader_id == "noheader"
    assert len(data.frame) == 3
    assert list(data.frame.columns) == ["Column_0", "Column_1", "Column_2"]
    assert parser_spy == ["NoHeaderParser"]


def test_csv2graph_default_is_still_standard__tc_ge05_ep_012(tmp_path: Path) -> None:
    """TC-GE05-EP-012: O-4 — csv2graph(path) keeps csv_format="standard" and plots a numeric header."""
    # Given
    path = _copy("numeric_header.csv", tmp_path)
    # When
    csv2graph(path, no_individual=True)
    # Then
    assert _written(tmp_path) == ["numeric_header.csv", "numeric_header.png"]


@pytest.mark.parametrize(("name", "parser_type", "columns"), [
    ("simple.csv", StandardParser, ["time (s)", "voltage (V)"]),
    ("transposed.csv", TransposeParser, ["time (s)", "voltage (V)", "current (A)"]),
    ("tabs.tsv", StandardParser, ["time", "voltage"]),
    ("sjis.csv", StandardParser, ["時間 (s)", "電圧 (V)"]),
])
def test_parser_factory_auto_detect_uses_the_detector__tc_ge05_ep_013(name: str, parser_type: type, columns: list[str], tmp_path: Path) -> None:
    """TC-GE05-EP-013: ParserFactory.auto_detect returns the parser of the detected format and options."""
    # Given
    path = _copy(name, tmp_path)
    # When
    parser = ParserFactory.auto_detect(path)
    frame = parser.parse(path)
    # Then
    assert type(parser) is parser_type
    assert list(frame.columns) == columns


def test_parser_factory_auto_detect_meta_block__tc_ge05_ep_013b(tmp_path: Path) -> None:
    """TC-GE05-EP-013: a metadata block is parsed like CSVParser.parse (frame part)."""
    # Given
    path = _copy("comment_metadata.csv", tmp_path)
    # When
    frame = ParserFactory.auto_detect(path).parse(path)
    # Then
    pd.testing.assert_frame_equal(frame, CSVParser.parse(path)[0])


def test_parser_factory_numeric_first_data_row_is_not_removed__tc_ge05_ep_013c(tmp_path: Path) -> None:
    """TC-GE05-EP-013: the old heuristic returned NoHeaderParser here and turned the header into data."""
    # Given
    path = _write(tmp_path, "tv.csv", "t,v\n1,2\n3,4\n")
    # When
    frame = ParserFactory.auto_detect(path).parse(path)
    # Then
    assert list(frame.columns) == ["t", "v"]
    assert frame.to_numpy().tolist() == [[1, 2], [3, 4]]


@pytest.mark.parametrize(("name", "expected"), [
    ("simple.csv", ["selected: standard (auto)", "columns: time (s), voltage (V)", "data rows: 4"]),
    ("numeric_header.csv", ["selected: none (ambiguous)", "candidate noheader (0.50)", "candidate standard (0.50)"]),
])
def test_cli_detect_previews_without_plotting__tc_ge05_ep_014(name: str, expected: list[str], tmp_path: Path) -> None:
    """TC-GE05-EP-014: --detect prints the decision and exits 0 without writing anything."""
    # Given
    from rdetoolkit.cli.app import app

    path = _copy(name, tmp_path)
    before = path.read_bytes()
    # When
    outcome = CliRunner().invoke(app, ["plot", str(path), "--detect"])
    # Then
    assert outcome.exit_code == 0, outcome.output
    for line in expected:
        assert line in outcome.output
    assert _written(tmp_path) == [name]
    assert path.read_bytes() == before


def test_explain_reports_sample_columns_and_rows__tc_ge05_ep_015(tmp_path: Path) -> None:
    """TC-GE05-EP-015: explain() states encoding, delimiter, sample size, columns and row count."""
    # Given
    path = _copy("bom_utf8.csv", tmp_path)
    # When
    text = detect_table_format(path).explain()
    # Then
    assert text.splitlines()[0] == "selected: standard (auto)"
    for fragment in ("encoding: utf-8-sig", "delimiter: ','", f"sampled: {path.stat().st_size} bytes, 4 rows (complete)",
                     "columns: time (s), voltage (V)", "data rows: 3", "candidate standard (0.95)"):
        assert fragment in text


def test_public_surface__tc_ge05_ep_016() -> None:
    """TC-GE05-EP-016: detect_table_format is exported; the decision types are the GE-04 objects."""
    # Given/When/Then
    assert graph_pkg.detect_table_format is detect_table_format
    assert "detect_table_format" in graph_pkg.__all__
    assert detection.DetectionDecision is readers_base.DetectionDecision is graph_pkg.DetectionDecision
    assert detection.FormatCandidate is readers_base.FormatCandidate
    stub = (Path(graph_pkg.__file__).parent / "__init__.pyi").read_text(encoding="utf-8")
    assert "detect_table_format as detect_table_format" in stub


def test_parsers_accept_keyword_only_options__tc_ge05_ep_017(tmp_path: Path) -> None:
    """TC-GE05-EP-017: the legacy parsers read with an explicit encoding and delimiter."""
    # Given
    sjis = _copy("sjis.csv", tmp_path)
    tsv = _write(tmp_path, "t.tsv", "label\t0\t1\na\t1\t2\n")
    # When
    standard = StandardParser(encoding="cp932").parse(sjis)
    noheader = NoHeaderParser(encoding="cp932", delimiter=",").parse(sjis)
    transpose = TransposeParser(delimiter="\t").parse(tsv)
    # Then
    assert list(standard.columns) == ["時間 (s)", "電圧 (V)"]
    assert noheader.iloc[0].tolist() == ["時間 (s)", "電圧 (V)"]
    assert list(transpose.columns) == ["label", "a"]


# --- negative: ambiguity is an error, never a guess ------------------------------------------


def _assert_ambiguous(path: Path) -> AmbiguousFormatError:
    with pytest.raises(AmbiguousFormatError) as caught:
        read_table(path)
    error = caught.value
    assert isinstance(error, InvalidCSVFormatError)
    assert isinstance(error, ValueError)
    assert "--csv-format" in str(error)
    assert "reader=" in str(error)
    assert error.decision.selected is None
    return error


def test_numeric_header_is_ambiguous__tc_ge05_neg_001(tmp_path: Path) -> None:
    """TC-GE05-NEG-001: every row numeric -> standard 0.5 / noheader 0.5; no row is dropped silently."""
    # Given
    path = _copy("numeric_header.csv", tmp_path)
    # When
    decision = detect_table_format(path)
    error = _assert_ambiguous(path)
    # Then
    assert decision.selected is None
    assert _scores(decision) == {"noheader": 0.5, "standard": 0.5}
    assert [c.reader_id for c in error.decision.candidates] == ["noheader", "standard"]
    assert "candidate standard (0.50)" in str(error)
    assert decision.preview_columns == ()
    assert decision.data_rows is None


def test_mixed_first_row_is_ambiguous__tc_ge05_neg_002(tmp_path: Path) -> None:
    """TC-GE05-NEG-002: some numeric, some text in row 1 -> standard 0.7 is below the threshold."""
    # Given
    path = _copy("mixed.csv", tmp_path)
    # When
    error = _assert_ambiguous(path)
    # Then
    assert _scores(error.decision) == {"standard": 0.7, "noheader": 0.3}
    assert len(error.decision.candidates) >= 2


def test_label_column_with_numeric_header_is_ambiguous__tc_ge05_neg_003(tmp_path: Path) -> None:
    """TC-GE05-NEG-003: ``name,1,2,3`` over a taller label-column table -> standard 0.5 / transpose 0.5."""
    # Given: 5 rows, 3 data columns
    path = _write(tmp_path, "labels.csv", "name,1,2,3\na,0.1,0.2,0.3\nb,0.4,0.5,0.6\nc,0.7,0.8,0.9\nd,1.0,1.1,1.2\n")
    # When
    error = _assert_ambiguous(path)
    # Then
    assert _scores(error.decision) == {"standard": 0.5, "transpose": 0.5}


def test_two_qualifying_delimiters_are_ambiguous__tc_ge05_neg_004(tmp_path: Path) -> None:
    """TC-GE05-NEG-004: ',' and ';' both give a constant field count -> ambiguous, one candidate each."""
    # Given
    path = _write(tmp_path, "semi.csv", "a;b,c\n1;2,3\n4;5,6\n")
    # When
    error = _assert_ambiguous(path)
    # Then
    decision = error.decision
    assert decision.delimiter is None
    assert len(decision.candidates) == 2
    evidence = [" ".join(c.evidence) for c in decision.candidates]
    assert any("delimiter ','" in text for text in evidence)
    assert any("delimiter ';'" in text for text in evidence)
    assert all(c.confidence <= 0.5 for c in decision.candidates)


def test_all_text_rows_are_ambiguous__tc_ge05_neg_005(tmp_path: Path) -> None:
    """TC-GE05-NEG-005: no number anywhere -> header presence cannot be inferred."""
    # Given
    path = _write(tmp_path, "text.csv", "a,b\nc,d\n")
    # When
    error = _assert_ambiguous(path)
    # Then
    assert _scores(error.decision) == {"standard": 0.6, "noheader": 0.4}


@pytest.mark.parametrize("content", [b"", b"\n\n  \n"])
def test_empty_file_is_rejected__tc_ge05_neg_006(content: bytes, tmp_path: Path, parser_spy: list[str]) -> None:
    """TC-GE05-NEG-006: an empty (or blank-only) file fails as "empty" before any parser runs."""
    # Given
    path = _copy("empty.csv", tmp_path) if not content else _write(tmp_path, "blank.csv", content)
    # When/Then
    with pytest.raises(InvalidCSVFormatError, match="empty") as caught:
        detect_table_format(path)
    assert not isinstance(caught.value, AmbiguousFormatError)
    with pytest.raises(InvalidCSVFormatError, match="empty"):
        read_table(path)
    assert parser_spy == []


def test_oversize_file_rejected_before_reading__tc_ge05_neg_007(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE05-NEG-007: st_size > max_bytes fails before the file is opened."""
    # Given
    path = _copy("simple.csv", tmp_path)
    opened: list[Path] = []
    original_open = Path.open

    def spy_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        opened.append(self)
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", spy_open)
    # When/Then
    with pytest.raises(InvalidCSVFormatError, match=r"larger than the limit of 10 bytes") as caught:
        detect_table_format(path, max_bytes=10)
    assert not isinstance(caught.value, AmbiguousFormatError)
    assert opened == []


def test_undecodable_bytes_are_ambiguous__tc_ge05_neg_008(tmp_path: Path) -> None:
    """TC-GE05-NEG-008: neither strict UTF-8 nor strict cp932 -> AmbiguousFormatError naming both."""
    # Given
    path = _write(tmp_path, "bin.csv", b"a,b\n\x81\x20,1\n")
    # When/Then
    with pytest.raises(AmbiguousFormatError, match=r"utf-8.*cp932") as caught:
        detect_table_format(path)
    assert caught.value.decision.encoding is None
    assert "--csv-format" in str(caught.value)


def test_ragged_rows_are_ambiguous__tc_ge05_neg_009(tmp_path: Path) -> None:
    """TC-GE05-NEG-009: no delimiter gives a constant field count -> the layout is not guessed."""
    # Given
    path = _write(tmp_path, "ragged.csv", "a,b\n1,2,3\n4,5\n")
    # When/Then
    with pytest.raises(AmbiguousFormatError, match="same number of fields") as caught:
        read_table(path)
    assert caught.value.decision.delimiter is None
    assert "--csv-format" in str(caught.value)


@pytest.mark.parametrize(("name", "content"), [
    ("bom_meta.csv", b"\xef\xbb\xbf#title,Run\n0,1\n1,2\n"),
    ("tab_meta.csv", b"#title\tRun\n0\t1\n1\t2\n"),
])
def test_meta_block_outside_legacy_encoding_is_ambiguous__tc_ge05_neg_010(name: str, content: bytes, tmp_path: Path) -> None:
    """TC-GE05-NEG-010: the meta_block reader reads UTF-8 comma files only; otherwise it is not selected."""
    # Given
    path = _write(tmp_path, name, content)
    # When
    error = _assert_ambiguous(path)
    # Then
    assert _scores(error.decision) == {"meta_block": 0.6}
    assert "UTF-8, comma-separated" in " ".join(error.decision.candidates[0].evidence)


def test_missing_file__tc_ge05_neg_011(tmp_path: Path) -> None:
    """TC-GE05-NEG-011: a missing file is FileNotFoundError, as for the parsers."""
    # Given/When/Then
    with pytest.raises(FileNotFoundError, match="CSV file not found"):
        detect_table_format(tmp_path / "missing.csv")


def test_auto_on_ambiguous_file_writes_nothing__tc_ge05_neg_012(tmp_path: Path) -> None:
    """TC-GE05-NEG-012: csv2graph(csv_format="auto") and render_graph fail before any artifact."""
    # Given
    path = _copy("numeric_header.csv", tmp_path)
    out = tmp_path / "out"
    # When/Then
    with pytest.raises(AmbiguousFormatError, match="--csv-format"):
        csv2graph(path, csv_format="auto", output_dir=out)
    with pytest.raises(AmbiguousFormatError, match="--csv-format"):
        render_graph(path, output=OutputSpec(DirectorySink(out)))
    assert _written(tmp_path) == ["numeric_header.csv"]


@pytest.mark.parametrize(("name", "error_type", "pattern"), [
    ("numeric_header.csv", AmbiguousFormatError, "--csv-format"),
    ("empty.csv", InvalidCSVFormatError, "empty"),
    ("missing.csv", FileNotFoundError, "CSV file not found"),
])
def test_parser_factory_auto_detect_never_guesses__tc_ge05_neg_013(name: str, error_type: type[Exception], pattern: str, tmp_path: Path) -> None:
    """TC-GE05-NEG-013: IC-8 — auto_detect raises instead of guessing NoHeaderParser."""
    # Given
    path = _copy(name, tmp_path) if name != "missing.csv" else tmp_path / name
    # When/Then
    with pytest.raises(error_type, match=pattern):
        ParserFactory.auto_detect(path)


def test_cli_auto_on_ambiguous_file__tc_ge05_neg_014(tmp_path: Path) -> None:
    """TC-GE05-NEG-014: rdetoolkit plot --csv-format auto reports the remedy and writes nothing."""
    # Given
    from rdetoolkit.cli.app import app

    path = _copy("numeric_header.csv", tmp_path)
    # When
    outcome = CliRunner().invoke(app, ["plot", str(path), "--csv-format", "auto"])
    # Then
    assert outcome.exit_code == 1
    assert "--csv-format" in outcome.output
    assert _written(tmp_path) == ["numeric_header.csv"]


@pytest.mark.parametrize("name", ["simple.csv", "numeric_header.csv", "sjis.csv", "comment_metadata.csv", "transposed.csv"])
def test_detection_never_mutates_the_file__tc_ge05_neg_015(name: str, tmp_path: Path) -> None:
    """TC-GE05-NEG-015: detection and auto reading leave bytes and mtime unchanged."""
    # Given
    path = _copy(name, tmp_path)
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    # When
    detect_table_format(path)
    with contextlib.suppress(AmbiguousFormatError):
        read_table(path)
    # Then
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
    assert _written(tmp_path) == [name]


@pytest.mark.parametrize("parser_type", [StandardParser, TransposeParser, NoHeaderParser])
def test_parser_options_are_keyword_only__tc_ge05_neg_016(parser_type: type) -> None:
    """TC-GE05-NEG-016: the new options cannot be passed positionally."""
    # Given/When/Then
    with pytest.raises(TypeError):
        parser_type("utf-8")


def test_first_line_longer_than_window__tc_ge05_neg_017(tmp_path: Path) -> None:
    """TC-GE05-NEG-017: no complete line inside the sample -> nothing to decide on."""
    # Given
    path = _write(tmp_path, "wide.csv", "x" * (SNIFF_MAX_BYTES + 10))
    # When/Then
    with pytest.raises(AmbiguousFormatError, match="longer than") as caught:
        detect_table_format(path)
    assert caught.value.decision.truncated is True


def test_cli_detect_errors__tc_ge05_neg_018(tmp_path: Path) -> None:
    """TC-GE05-NEG-018: --detect on a missing file fails (exit 1); undecodable input is explained (exit 0)."""
    # Given
    from rdetoolkit.cli.app import app

    undecodable = _write(tmp_path, "bin.csv", b"a,b\n\x81\x20,1\n")
    # When
    missing = CliRunner().invoke(app, ["plot", str(tmp_path / "missing.csv"), "--detect"])
    explained = CliRunner().invoke(app, ["plot", str(undecodable), "--detect"])
    # Then
    assert missing.exit_code == 1
    assert "CSV file not found" in missing.output
    assert explained.exit_code == 0, explained.output
    assert "cp932" in explained.output
    assert _written(tmp_path) == ["bin.csv"]


# --- boundaries: bounded scanning ------------------------------------------------------------


def _rows_file(directory: Path, name: str, size: int) -> Path:
    """A headered file of exactly ``size`` bytes (rows of fixed width, last row padded)."""
    header = "a,b\n"
    row = "1,2\n"
    body_size = size - len(header)
    rows, rest = divmod(body_size, len(row))
    text = header + row * rows
    if rest:
        text = text[:-1] + "0" * rest + "\n"
    target = _write(directory, name, text)
    assert target.stat().st_size == size
    return target


@pytest.mark.parametrize(("extra", "truncated"), [(0, False), (1, True)])
def test_sample_window_boundary__tc_ge05_bv_001(extra: int, truncated: bool, tmp_path: Path) -> None:
    """TC-GE05-BV-001: a file of exactly SNIFF_MAX_BYTES is complete; one byte more is truncated."""
    # Given
    path = _rows_file(tmp_path, "edge.csv", SNIFF_MAX_BYTES + extra)
    # When
    decision = detect_table_format(path)
    # Then
    assert decision.truncated is truncated
    assert decision.sampled_bytes <= SNIFF_MAX_BYTES
    assert (decision.data_rows is None) is truncated


def test_large_file_reads_only_the_window__tc_ge05_bv_002(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, parser_spy: list[str]) -> None:
    """TC-GE05-BV-002: a 5 MB file: at most SNIFF_MAX_BYTES read, header previewed, row count unknown."""
    # Given
    path = _write(tmp_path, "big.csv", "time,signal\n" + "".join(f"{i},{i % 7}\n" for i in range(600_000)))
    assert path.stat().st_size > 5_000_000
    read_sizes: list[int] = []
    original_open = Path.open

    class CountingReader:
        def __init__(self, handle: Any) -> None:
            self._handle = handle

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *exc: object) -> None:
            self._handle.close()

        def read(self, size: int = -1) -> bytes:
            data: bytes = self._handle.read(size)
            read_sizes.append(len(data))
            return data

    def spy_open(self: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        handle = original_open(self, mode, *args, **kwargs)
        return CountingReader(handle) if self == path else handle

    monkeypatch.setattr(Path, "open", spy_open)
    # When
    decision = detect_table_format(path)
    # Then
    assert sum(read_sizes) <= SNIFF_MAX_BYTES
    assert decision.sampled_bytes <= SNIFF_MAX_BYTES
    assert (decision.selected, decision.truncated, decision.data_rows) == ("standard", True, None)
    assert decision.preview_columns == ("time", "signal")
    assert decision.sampled_rows == SNIFF_MAX_ROWS
    assert parser_spy == []
    assert "(truncated)" in decision.explain()


def test_rows_beyond_row_limit_inside_window__tc_ge05_bv_003(tmp_path: Path) -> None:
    """TC-GE05-BV-003: classification samples SNIFF_MAX_ROWS rows; the row count is still exact."""
    # Given
    path = _write(tmp_path, "rows.csv", "x,y\n" + "".join(f"{i},{i}\n" for i in range(SNIFF_MAX_ROWS + 25)))
    # When
    decision = detect_table_format(path)
    # Then
    assert decision.sampled_rows == SNIFF_MAX_ROWS
    assert (decision.truncated, decision.data_rows) == (False, SNIFF_MAX_ROWS + 25)


def test_size_equal_to_limit_is_accepted__tc_ge05_bv_004(tmp_path: Path) -> None:
    """TC-GE05-BV-004: the size limit is inclusive."""
    # Given
    path = _copy("simple.csv", tmp_path)
    # When
    decision = detect_table_format(path, max_bytes=path.stat().st_size)
    # Then
    assert decision.selected == "standard"


@pytest.mark.parametrize(("rows", "selected"), [(3, "transpose"), (4, None)])
def test_transposed_shape_boundary__tc_ge05_bv_005(rows: int, selected: str | None, tmp_path: Path) -> None:
    """TC-GE05-BV-005: transposed needs at most as many rows as data columns (3 data columns here)."""
    # Given
    lines = ["x,0,1,2"] + [f"s{i},1,2,3" for i in range(rows - 1)]
    path = _write(tmp_path, "shape.csv", "\n".join(lines) + "\n")
    # When
    decision = detect_table_format(path)
    # Then
    assert decision.selected == selected


def test_truncated_transposed_pattern_is_ambiguous__tc_ge05_bv_006(tmp_path: Path) -> None:
    """TC-GE05-BV-006: when the sample is truncated, the true shape is unknown -> ambiguous."""
    # Given: many columns but even more rows than fit in the window
    width = 5
    header = "x," + ",".join(str(i) for i in range(width))
    body = "".join(f"s{i}," + ",".join("1" for _ in range(width)) + "\n" for i in range(20_000))
    path = _write(tmp_path, "tall.csv", header + "\n" + body)
    # When
    decision = detect_table_format(path)
    # Then
    assert decision.truncated is True
    assert decision.selected is None
    assert _scores(decision) == {"standard": 0.5, "transpose": 0.5}


def test_bounds__tc_ge05_bv_007() -> None:
    """TC-GE05-BV-007: the scan bounds and selection thresholds of design.md §2.7."""
    # Given/When/Then
    assert (SNIFF_MAX_BYTES, SNIFF_MAX_ROWS, DEFAULT_MAX_TABLE_BYTES) == (65536, 50, 2**30)
    assert (SELECT_MIN_CONFIDENCE, SELECT_MIN_MARGIN) == (0.8, 0.2)


def test_truncated_meta_block_has_no_column_preview__tc_ge05_bv_008(tmp_path: Path) -> None:
    """TC-GE05-BV-008: a large metadata-block file is selected, but its names need the whole file."""
    # Given
    meta = "#title,Big\n#dimension,x,y\n#x,Time,s\n#y,Voltage,V\n#legend,A\n"
    path = _write(tmp_path, "big_meta.csv", meta + "".join(f"{i},{i % 5}\n" for i in range(20_000)))
    # When
    decision = detect_table_format(path)
    # Then
    assert (decision.selected, decision.truncated) == ("meta_block", True)
    assert (decision.preview_columns, decision.data_rows) == ((), None)


def test_preview_failure_leaves_preview_empty__tc_ge05_neg_019(tmp_path: Path) -> None:
    """TC-GE05-NEG-019: when the selected reader cannot read the file, detection still reports and the read fails typed."""
    # Given: a metadata block whose #dimension tag lacks a value (the legacy parser rejects it)
    path = _write(tmp_path, "badmeta.csv", "#dimension,x\n0,1\n1,2\n")
    # When
    decision = detect_table_format(path)
    # Then
    assert decision.selected == "meta_block"
    assert (decision.preview_columns, decision.data_rows) == ((), None)
    with pytest.raises(graph_pkg.InvalidMetadataError, match="dimension"):
        read_table(path)


@pytest.mark.parametrize(("scores", "expected"), [
    ((), None),
    ((0.95,), "a"),
    ((0.79,), None),
    ((0.9, 0.7), "a"),
    ((0.9, 0.71), None),
    ((0.8, 0.6), "a"),
])
def test_selection_threshold_and_margin__tc_ge05_bv_009(scores: tuple[float, ...], expected: str | None) -> None:
    """TC-GE05-BV-009: selection needs confidence >= 0.8 and a margin >= 0.2 (boundaries inclusive)."""
    # Given
    candidates = tuple(detection.FormatCandidate(name, score, ()) for name, score in zip("abc", scores, strict=False))
    # When/Then
    assert detection._select(candidates) == expected


def test_margin_rule_on_a_real_fixture__tc_ge05_bv_010(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE05-BV-010: the margin rule decides a real sniffed file at its boundary.

    The builtin scores leave a gap of at least 0.6 whenever the top candidate reaches
    0.8 (BV-011), so the shipped margin is never the deciding rule for a builtin file.
    Moving the margin onto the gap of ``transposed.csv`` (transpose 0.9, standard 0.3)
    crosses the boundary with real sniffing: inclusive at the gap, ambiguous above it.
    """
    # Given: the transposed fixture and its sniffed gap
    path = _copy("transposed.csv", tmp_path)
    first, second = detect_table_format(path).candidates[:2]
    gap = first.confidence - second.confidence
    assert (first.reader_id, second.reader_id) == ("transpose", "standard")
    # When: the margin equals the gap
    monkeypatch.setattr(detection, "SELECT_MIN_MARGIN", gap)
    at_boundary = detect_table_format(path)
    # Then: selected (the boundary is inclusive)
    assert at_boundary.selected == "transpose"
    # When: the margin is just above the gap
    monkeypatch.setattr(detection, "SELECT_MIN_MARGIN", gap + 0.01)
    above = detect_table_format(path)
    # Then: nothing selected, and reading under auto fails with the candidates named
    assert above.selected is None
    assert [c.reader_id for c in above.candidates] == ["transpose", "standard"]
    with pytest.raises(AmbiguousFormatError, match="transpose") as info:
        read_table(path)
    assert info.value.decision is not None
    assert info.value.decision.selected is None


DETECTION_FIXTURES = ["bom_utf8.csv", "comment_metadata.csv", "duplicate_labels.csv", "mixed.csv", "multi_unit.csv",
                      "numeric_header.csv", "quoted_commas.csv", "simple.csv", "sjis.csv", "tabs.tsv", "transposed.csv"]


@pytest.mark.parametrize("name", DETECTION_FIXTURES)
def test_fixture_selection_follows_threshold_and_margin__tc_ge05_bv_011(name: str) -> None:
    """TC-GE05-BV-011: on every committed fixture the decision is the threshold + margin rule."""
    # Given/When: the sniffed decision of a committed fixture
    decision = detect_table_format(FIXTURES / name)
    scores = [c.confidence for c in decision.candidates]
    gap = scores[0] - scores[1] if len(scores) > 1 else 1.0
    # Then: selected exactly when both rules hold, and a selection never has a gap below the margin
    expected = scores[0] >= SELECT_MIN_CONFIDENCE and gap >= SELECT_MIN_MARGIN - 1e-9
    assert (decision.selected is not None) == expected
    if decision.selected is not None:
        assert decision.selected == decision.candidates[0].reader_id
        assert gap >= SELECT_MIN_MARGIN
