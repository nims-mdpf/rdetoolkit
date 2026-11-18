"""Conservative, explainable table-format detection (GE-05).

``detect_table_format`` reads at most ``SNIFF_MAX_BYTES`` of a file (opened read-only,
never rewritten), sniffs its encoding, delimiter, metadata block, header row and
transposed layout over at most ``SNIFF_MAX_ROWS`` rows, and returns a
``DetectionDecision`` listing every candidate reader with its confidence and evidence.
A reader is selected only when the best candidate reaches ``SELECT_MIN_CONFIDENCE``
with a margin of ``SELECT_MIN_MARGIN`` over the next one. Anything less is reported as
ambiguous instead of guessed, because a wrong guess silently drops a header or turns
data into column names.

Only the standard library and pandas are used (never ``rdetoolkit._core``).
"""

from __future__ import annotations

import codecs
import csv
import io
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Final

import pandas as pd

from rdetoolkit.graph.exceptions import AmbiguousFormatError, GraphPlottingError, InvalidCSVFormatError
from rdetoolkit.graph.readers.base import DetectionDecision, FormatCandidate
from rdetoolkit.graph.readers.builtin import configured_builtin_reader

SNIFF_MAX_BYTES: Final = 65536
SNIFF_MAX_ROWS: Final = 50
DEFAULT_MAX_TABLE_BYTES: Final = 2**30
SELECT_MIN_CONFIDENCE: Final = 0.8
SELECT_MIN_MARGIN: Final = 0.2

_DELIMITERS: Final = (",", "\t", ";")
_UTF8_SIG: Final = "utf-8-sig"
_PLAIN_ENCODINGS: Final = ("utf-8", "cp932")
#: Encoding and delimiter the legacy meta-block parser (``CSVParser``) can read.
_META_BLOCK_ENCODING: Final = "utf-8"
_META_BLOCK_DELIMITER: Final = ","
#: Numbers as pandas would parse them; stricter than ``float()`` (no ``1_000``).
_NUMBER: Final = re.compile(r"[+-]?(?:(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|nan|inf|infinity)", re.IGNORECASE)
#: Float tolerance for the margin comparison (confidences are short decimals).
_TOLERANCE: Final = 1e-9
_REMEDY: Final = (
    "Name the format with --csv-format <id>, csv_format=<id> or reader=<id> "
    "(builtin ids: meta_block, noheader, standard, transpose)."
)

Row = Sequence[str]


@dataclass(frozen=True, slots=True)
class _Sample:
    """The bytes detection may look at: complete lines only."""

    path: Path
    data: bytes
    read_bytes: int
    truncated: bool


@dataclass(frozen=True, slots=True)
class _Layout:
    """The decoded sample split into its metadata block and delimited rows."""

    encoding: str
    meta_lines: int
    body: str
    delimiter: str
    single_column: bool
    rows: tuple[Row, ...]
    total_rows: int | None


def _is_number(cell: str) -> bool:
    return _NUMBER.fullmatch(cell.strip()) is not None


def _is_blank(cell: str) -> bool:
    return not cell.strip()


def _numeric_or_blank(cells: Row) -> bool:
    return all(_is_blank(cell) or _is_number(cell) for cell in cells)


# --- reading and decoding the bounded sample ---------------------------------------------------


def _undecided(sample: _Sample, *, encoding: str | None = None) -> DetectionDecision:
    return DetectionDecision(selected=None, forced=False, candidates=(), encoding=encoding, sampled_bytes=sample.read_bytes, truncated=sample.truncated)


def _read_sample(path: Path, max_bytes: int) -> _Sample:
    """Check the size, then read at most ``SNIFF_MAX_BYTES``, cut back to the last complete line."""
    try:
        size = path.stat().st_size
    except FileNotFoundError as exc:
        msg = f"CSV file not found: {path}"
        raise FileNotFoundError(msg) from exc
    if size > max_bytes:
        msg = f"Table file {path.name!r} is {size} bytes, larger than the limit of {max_bytes} bytes; it is not read."
        raise InvalidCSVFormatError(msg)
    if size == 0:
        msg = f"Table file {path.name!r} is empty"
        raise InvalidCSVFormatError(msg)
    with path.open("rb") as handle:
        data = handle.read(SNIFF_MAX_BYTES)
    sample = _Sample(path=path, data=data, read_bytes=len(data), truncated=size > len(data))
    if not sample.truncated:
        return sample
    cut = data.rfind(b"\n")
    if cut < 0:
        msg = f"Cannot detect the format of {path.name!r}: its first line is longer than the {SNIFF_MAX_BYTES}-byte sniff window. {_REMEDY}"
        raise AmbiguousFormatError(msg, decision=_undecided(sample))
    return _Sample(path=path, data=data[: cut + 1], read_bytes=len(data), truncated=True)


def _decode(sample: _Sample) -> tuple[str, str]:
    """Decode strictly: BOM -> utf-8-sig; else utf-8; else cp932; else ambiguous."""
    tried = (_UTF8_SIG,) if sample.data.startswith(codecs.BOM_UTF8) else _PLAIN_ENCODINGS
    for encoding in tried:
        try:
            return encoding, sample.data.decode(encoding)
        except UnicodeDecodeError:
            continue
    msg = (
        f"Cannot detect the encoding of {sample.path.name!r}: the sampled bytes are not valid {' / '.join(tried)}. "
        f"Re-save the file as UTF-8, or use a reader for its encoding. {_REMEDY}"
    )
    raise AmbiguousFormatError(msg, decision=_undecided(sample))


def _split_metadata(text: str) -> tuple[int, str]:
    """Count the leading ``#`` lines (blank lines between them are skipped) and return the rest."""
    meta_lines = 0
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            break
        meta_lines += bool(stripped)
        offset += len(line)
    return meta_lines, text[offset:]


# --- delimiter ---------------------------------------------------------------------------------


def _rows(body: str, delimiter: str, limit: int | None) -> list[Row]:
    """Delimited non-blank rows of ``body`` (quotes honoured), at most ``limit``."""
    # csv.Error is impossible here: the sample (<= SNIFF_MAX_BYTES) is shorter than csv's field limit.
    reader = csv.reader(io.StringIO(body), delimiter=delimiter)
    non_blank = (row for row in reader if any(not _is_blank(cell) for cell in row))
    return list(islice(non_blank, limit))


def _field_counts(body: str) -> dict[str, set[int]]:
    return {delimiter: {len(row) for row in _rows(body, delimiter, SNIFF_MAX_ROWS)} for delimiter in _DELIMITERS}


def _delimiter_name(delimiter: str | None) -> str:
    return "tab" if delimiter == "\t" else repr(delimiter)


def _qualifying(counts: dict[str, set[int]]) -> tuple[str, ...]:
    """Delimiters giving one constant field count (> 1) on every sampled line."""
    return tuple(delimiter for delimiter, found in counts.items() if len(found) == 1 and min(found) > 1)


def _ragged_error(sample: _Sample, encoding: str, counts: dict[str, set[int]]) -> AmbiguousFormatError:
    seen = "; ".join(f"{_delimiter_name(delimiter)}: {sorted(found)}" for delimiter, found in counts.items())
    msg = (
        f"Cannot detect the layout of {sample.path.name!r}: no delimiter among ',', tab and ';' gives the same "
        f"number of fields on every sampled line (field counts {seen}). {_REMEDY}"
    )
    return AmbiguousFormatError(msg, decision=_undecided(sample, encoding=encoding))


def _layout(sample: _Sample, encoding: str, meta_lines: int, body: str, delimiter: str, *, single_column: bool) -> _Layout:
    rows = tuple(_rows(body, delimiter, SNIFF_MAX_ROWS))
    total = None if sample.truncated else len(_rows(body, delimiter, None))
    return _Layout(encoding=encoding, meta_lines=meta_lines, body=body, delimiter=delimiter, single_column=single_column, rows=rows, total_rows=total)


# --- candidates --------------------------------------------------------------------------------


def _layout_evidence(layout: _Layout) -> tuple[str, ...]:
    if layout.single_column:
        return ("single column: no ',', tab or ';' delimiter found; comma assumed",)
    width = len(layout.rows[0]) if layout.rows else 0
    return (f"delimiter {_delimiter_name(layout.delimiter)} gives {width} fields on every sampled line",)


def _meta_candidate(layout: _Layout) -> FormatCandidate:
    reason = f"{layout.meta_lines} leading '#' metadata lines"
    if (layout.encoding, layout.delimiter) == (_META_BLOCK_ENCODING, _META_BLOCK_DELIMITER) or (layout.single_column and layout.encoding == _META_BLOCK_ENCODING):
        return FormatCandidate("meta_block", 0.9, (reason,))
    limit = f"the meta_block reader reads UTF-8, comma-separated files only (detected {layout.encoding}, delimiter {_delimiter_name(layout.delimiter)})"
    return FormatCandidate("meta_block", 0.6, (reason, limit))


def _numeric_header_candidates() -> tuple[FormatCandidate, ...]:
    return (
        FormatCandidate("standard", 0.5, ("every sampled row is numeric: row 1 may be a header of numeric names",)),
        FormatCandidate("noheader", 0.5, ("every sampled row is numeric: row 1 may be the first data row",)),
    )


def _label_column_pattern(rows: Sequence[Row]) -> bool:
    """First column non-numeric on every row; every other cell numeric, row 1 included."""
    labels = all(not _is_number(row[0]) for row in rows)
    first_numeric = all(_is_number(cell) for cell in rows[0][1:])
    return labels and first_numeric and all(_numeric_or_blank(row[1:]) for row in rows[1:])


def _transpose_candidates(layout: _Layout) -> tuple[FormatCandidate, ...]:
    data_columns = len(layout.rows[0]) - 1
    pattern = "the first column is text on every row and every other cell is numeric, row 1 included"
    if layout.total_rows is not None and layout.total_rows <= data_columns:
        shape = f"{layout.total_rows} rows for {data_columns} data columns: series in rows"
        return (
            FormatCandidate("transpose", 0.9, (pattern, shape)),
            FormatCandidate("standard", 0.3, ("row 1 could be a header of numeric names",)),
        )
    rows = "more rows than the sample" if layout.total_rows is None else f"{layout.total_rows} rows"
    shape = f"{rows} for {data_columns} data columns: a label column under a numeric header is equally plausible"
    return (
        FormatCandidate("standard", 0.5, (pattern, shape, "row 1 may be a header of numeric names over a label column")),
        FormatCandidate("transpose", 0.5, (pattern, shape, "rows may be series with x values in row 1")),
    )


def _header_candidates(rows: Sequence[Row]) -> tuple[FormatCandidate, ...]:
    rest = rows[1:]
    if not rest:
        return (FormatCandidate("standard", 0.85, ("row 1 is text and is the only row: a header without data rows",)),)
    if any(_is_number(cell) for row in rest for cell in row):
        return (FormatCandidate("standard", 0.95, ("row 1 is all text and later rows contain numbers: a header row",)),)
    return (
        FormatCandidate("standard", 0.6, ("row 1 is text, but so is every later row",)),
        FormatCandidate("noheader", 0.4, ("no row contains a number: row 1 may be data",)),
    )


def _mixed_candidates(first: Row) -> tuple[FormatCandidate, ...]:
    numbers = sum(_is_number(cell) for cell in first)
    reason = f"row 1 mixes {len(first) - numbers} text and {numbers} numeric cells"
    return (
        FormatCandidate("standard", 0.7, (reason, "row 1 may be a header with numeric names")),
        FormatCandidate("noheader", 0.3, (reason, "row 1 may be a data row with text values")),
    )


def _all_numeric(rows: Sequence[Row]) -> bool:
    """Row 1 fully numeric and every later row numeric (blanks allowed)."""
    return all(_is_number(cell) for cell in rows[0]) and all(_numeric_or_blank(row) for row in rows[1:])


def _transposed_pattern(rows: Sequence[Row]) -> bool:
    return len(rows) > 1 and len(rows[0]) > 1 and _label_column_pattern(rows)


def _content_candidates(layout: _Layout) -> tuple[FormatCandidate, ...]:
    rows = layout.rows
    if _all_numeric(rows):
        return _numeric_header_candidates()
    if _transposed_pattern(rows):
        return _transpose_candidates(layout)
    if not any(_is_number(cell) for cell in rows[0]):
        return _header_candidates(rows)
    return _mixed_candidates(rows[0])


def _candidates(layout: _Layout) -> tuple[FormatCandidate, ...]:
    found = (_meta_candidate(layout),) if layout.meta_lines else _content_candidates(layout)
    evidence = _layout_evidence(layout)
    with_layout = (FormatCandidate(c.reader_id, c.confidence, (*c.evidence, *evidence)) for c in found)
    return _ordered(with_layout)


def _ordered(candidates: Iterable[FormatCandidate]) -> tuple[FormatCandidate, ...]:
    return tuple(sorted(candidates, key=lambda c: (-c.confidence, c.reader_id)))


def _select(candidates: Sequence[FormatCandidate]) -> str | None:
    if not candidates or candidates[0].confidence < SELECT_MIN_CONFIDENCE:
        return None
    if len(candidates) > 1 and candidates[0].confidence - candidates[1].confidence < SELECT_MIN_MARGIN - _TOLERANCE:
        return None
    return candidates[0].reader_id


def _delimiter_conflict(sample: _Sample, encoding: str, meta_lines: int, body: str, delimiters: tuple[str, ...]) -> tuple[FormatCandidate, ...]:
    """One capped candidate per qualifying delimiter, so the conflict is visible and never selected."""
    found: list[FormatCandidate] = []
    for delimiter in delimiters:
        layout = _layout(sample, encoding, meta_lines, body, delimiter, single_column=False)
        best = _candidates(layout)[0]
        reasons = (f"delimiter {_delimiter_name(delimiter)} also gives a constant field count", *best.evidence)
        found.append(FormatCandidate(best.reader_id, min(best.confidence, 0.5), reasons))
    return tuple(found)


# --- preview -----------------------------------------------------------------------------------


def _preview(sample: _Sample, layout: _Layout, selected: str | None) -> tuple[tuple[str, ...], int | None]:
    """Column names and row count the selected reader produces (exact only for a complete sample)."""
    if selected is None:
        return (), None
    if sample.truncated:
        return _truncated_preview(layout, selected), None
    reader = configured_builtin_reader(selected, encoding=layout.encoding, delimiter=layout.delimiter)
    try:
        frame = reader.read(sample.path).frame
    except (GraphPlottingError, ValueError):  # pandas parser errors are ValueErrors
        return (), None
    return tuple(str(name) for name in frame.columns), len(frame)


def _truncated_preview(layout: _Layout, selected: str) -> tuple[str, ...]:
    """Header names are known from the sample; meta-block names need the whole file.

    ``noheader`` and ``transpose`` are never selected from a truncated sample (their
    confidence stays below the threshold), so only ``standard`` and ``meta_block`` reach here.
    """
    if selected != "standard":
        return ()
    header = pd.read_csv(io.StringIO(layout.body), sep=layout.delimiter, nrows=0)
    return tuple(str(name) for name in header.columns)


# --- public ------------------------------------------------------------------------------------


def _single_column(sample: _Sample, encoding: str, delimiters: tuple[str, ...], counts: dict[str, set[int]]) -> bool:
    """With no qualifying delimiter, only a one-field-per-line file is readable; anything else is ragged."""
    if delimiters:
        return False
    if all(found <= {1} for found in counts.values()):
        return True
    raise _ragged_error(sample, encoding, counts)


@dataclass(frozen=True, slots=True)
class _Sniffed:
    """What the sample says: a layout (``None`` when two delimiters qualify) and the candidates."""

    encoding: str
    layout: _Layout | None
    candidates: tuple[FormatCandidate, ...]


def _sniff(sample: _Sample) -> _Sniffed:
    encoding, text = _decode(sample)
    meta_lines, body = _split_metadata(text)
    if not meta_lines and not body.strip():
        msg = f"Table file {sample.path.name!r} is empty (blank lines only)"
        raise InvalidCSVFormatError(msg)
    counts = _field_counts(body)
    delimiters = _qualifying(counts)
    if len(delimiters) > 1:
        return _Sniffed(encoding, None, _ordered(_delimiter_conflict(sample, encoding, meta_lines, body, delimiters)))
    single_column = _single_column(sample, encoding, delimiters, counts)
    layout = _layout(sample, encoding, meta_lines, body, (*delimiters, ",")[0], single_column=single_column)
    return _Sniffed(encoding, layout, _candidates(layout))


def _decision(sample: _Sample, sniffed: _Sniffed) -> DetectionDecision:
    layout = sniffed.layout
    if layout is None:
        return DetectionDecision(selected=None, forced=False, candidates=sniffed.candidates, encoding=sniffed.encoding,
                                 sampled_bytes=sample.read_bytes, truncated=sample.truncated)
    selected = _select(sniffed.candidates)
    columns, data_rows = _preview(sample, layout, selected)
    return DetectionDecision(
        selected=selected,
        forced=False,
        candidates=sniffed.candidates,
        encoding=layout.encoding,
        delimiter=layout.delimiter,
        sampled_bytes=sample.read_bytes,
        sampled_rows=len(layout.rows),
        truncated=sample.truncated,
        preview_columns=columns,
        data_rows=data_rows,
    )


def detect_table_format(path: str | Path, *, max_bytes: int = DEFAULT_MAX_TABLE_BYTES) -> DetectionDecision:
    """Detect the table format of ``path`` from a bounded, read-only sample.

    Args:
        path: The file.
        max_bytes: Files larger than this are rejected before anything is read.

    Returns:
        The decision: ``selected`` is a builtin reader id, or ``None`` when no candidate
        is confident enough (the candidates and their evidence say why).

    Raises:
        FileNotFoundError: If the file does not exist.
        InvalidCSVFormatError: If the file is empty or larger than ``max_bytes``.
        AmbiguousFormatError: If the encoding or the line layout cannot be determined
            (``.decision`` carries no candidates then).
    """
    sample = _read_sample(Path(path), max_bytes)
    return _decision(sample, _sniff(sample))


def ambiguity_error(path: Path, decision: DetectionDecision) -> AmbiguousFormatError:
    """Build the error for a decision without a selection: candidates, evidence and remedy.

    Args:
        path: The file.
        decision: The ambiguous decision.

    Returns:
        The error, carrying ``decision``.
    """
    names = ", ".join(f"{c.reader_id} ({c.confidence:.2f})" for c in decision.candidates) or "none"
    msg = (
        f"Ambiguous table format for {path.name!r}: no candidate reaches confidence {SELECT_MIN_CONFIDENCE} "
        f"with a margin of {SELECT_MIN_MARGIN} (candidates: {names}). {_REMEDY}\n{decision.explain()}"
    )
    return AmbiguousFormatError(msg, decision=decision)


def require_selection(path: Path, decision: DetectionDecision) -> str:
    """Return the selected reader id, or raise the ambiguity error.

    Args:
        path: The file the decision is about.
        decision: A decision from ``detect_table_format``.

    Returns:
        ``decision.selected``.

    Raises:
        AmbiguousFormatError: If nothing was selected.
    """
    if decision.selected is None:
        raise ambiguity_error(path, decision)
    return decision.selected


__all__ = [
    "DEFAULT_MAX_TABLE_BYTES",
    "SELECT_MIN_CONFIDENCE",
    "SELECT_MIN_MARGIN",
    "SNIFF_MAX_BYTES",
    "SNIFF_MAX_ROWS",
    "DetectionDecision",
    "FormatCandidate",
    "ambiguity_error",
    "detect_table_format",
    "require_selection",
]
