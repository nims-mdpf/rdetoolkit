"""Builtin input nodes for text, tabular files, and ZIP archives."""

from __future__ import annotations

import csv
import zipfile
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, overload

import chardet
import pandas as pd
from charset_normalizer import detect
from openpyxl import load_workbook
from openpyxl.styles.colors import COLOR_INDEX
from openpyxl.utils import column_index_from_string

from rdetoolkit.core.node import node
from rdetoolkit.rdelogger import get_logger
from rdetoolkit.rde2util import CharDecEncoding

_UTF8_FLAG = 0x800

logger = get_logger(__name__)


def _detect_encoding(path: Path) -> str:
    # The legacy usual-codec set omits CP932 and can replace it with MacCyrillic.
    primary = detect(path.read_bytes()).get("encoding")
    if primary is not None and primary.lower() == "cp932":
        return primary
    return CharDecEncoding.detect_text_file_encoding(path) or "utf-8"


def _zip_destination(base_dir: Path, filename: str) -> Path:
    """Mirror zipfile's member sanitization before checking existing symlinks."""
    name = filename.replace("/", os.path.sep)
    if os.path.altsep:
        name = name.replace(os.path.altsep, os.path.sep)
    name = os.path.splitdrive(name)[1]
    parts = [part for part in name.split(os.path.sep) if part not in {"", ".", ".."}]
    if os.path.sep == "\\":
        translation = str.maketrans(':<>|"?*', "_______")
        parts = [part.translate(translation).rstrip(" .") for part in parts]
    return base_dir.joinpath(*parts).resolve()


@node(tags=["builtin", "io"], version="2.0.0", idempotent=True)
def read_text(path: Path, *, encoding: str | None = None) -> str:
    """Read a text file using a detected or an explicit character encoding.

    Without ``encoding`` the legacy encoding preference is used while
    retaining primary CP932 detection; a UTF-8 BOM is detected as
    ``utf-8-sig`` and stripped. An explicit ``encoding`` is applied as given
    with strict error handling: bytes it cannot decode raise instead of being
    decoded with another codec. Pass ``"utf-8-sig"`` rather than ``"utf-8"``
    to strip a BOM.

    Args:
        path: Text file to read.
        encoding: Codec name, or None to detect it.

    Returns:
        Decoded text content.

    Raises:
        FileNotFoundError: If the file does not exist.
        LookupError: If ``encoding`` names no known codec.
        UnicodeDecodeError: If the file is not valid in ``encoding``.
    """
    source = Path(path)
    return source.read_text(encoding=_detect_encoding(source) if encoding is None else encoding)


@node(tags=["builtin", "io"], version="2.0.0", idempotent=True)
def read_csv_with_header(
    path: Path, *, encoding: str | None = None,
    skiprows: int | list[int] | Callable[[int], bool] | None = None,
    header: int | list[int] | Literal["infer"] | None = "infer", **pandas_kwargs: object,
) -> pd.DataFrame:
    """Read a CSV into a data frame, by default with its first row as the header.

    Without options this reads the first row as the column names, as before.
    ``skiprows`` and ``header`` have their ``pandas.read_csv`` meaning: with
    the default ``header="infer"`` the first row after ``skiprows`` is the
    header unless ``names`` is given, in which case every row is data. Other
    ``pandas.read_csv`` options such as ``sep``, ``dtype=str``,
    ``keep_default_na=False`` or ``names`` are passed through unchanged.

    Without ``encoding`` the legacy encoding preference is used while
    retaining primary CP932 detection; an explicit ``encoding`` is used as
    given and a decoding error is raised, never replaced by another codec.

    Args:
        path: CSV file to read.
        encoding: Codec name, or None to detect it.
        skiprows: Leading rows to skip, row positions, or a row predicate.
        header: Header row positions, ``"infer"``, or None for no header row.
        pandas_kwargs: Further ``pandas.read_csv`` options.

    Returns:
        Parsed data frame.

    Raises:
        ValueError: If ``iterator`` or ``chunksize`` is set, since pandas
            then returns a ``TextFileReader`` instead of a data frame.
        TypeError: If ``pandas_kwargs`` names a second source with
            ``filepath_or_buffer``.
        LookupError: If ``encoding`` names no known codec.
        UnicodeDecodeError: If the file is not valid in the codec.
    """
    active = {"iterator": bool(pandas_kwargs.get("iterator")), "chunksize": pandas_kwargs.get("chunksize") is not None}
    readers = [name for name, used in active.items() if used]
    if readers:
        msg = f"read_csv_with_header returns a DataFrame; {', '.join(readers)} would return a TextFileReader"
        raise ValueError(msg)
    source = Path(path)
    return pd.read_csv(
        source, encoding=_detect_encoding(source) if encoding is None else encoding,
        skiprows=skiprows, header=header, **pandas_kwargs,
    )


@node(tags=["builtin", "io"], version="2.0.0", idempotent=True)
def read_key_values(
    path: Path, *, key: str = "key", value: str = "value",
    encoding: str | None = None, missing_ok: bool = False,
) -> dict[str, str]:
    """Read a two-column CSV such as ``tasksupport/default_value.csv`` into a dict.

    With the default options the result equals v1
    ``rde2util.get_default_values(path)``: the encoding is detected with
    chardet, rows are read with ``csv.DictReader`` and every value stays a
    string. chardet can misdetect a short, mostly ASCII Shift-JIS file, as
    in v1; pass ``encoding="cp932"`` for such files. The
    result can be merged with measured values for ``build_meta``, as in
    ``build_meta({**defaults, **measured}, metadef)``.

    Args:
        path: CSV file whose header row names the key and value columns.
        key: Header of the key column.
        value: Header of the value column.
        encoding: Text encoding, or None to detect it with chardet like v1.
        missing_ok: Whether a missing file returns an empty dict.

    Returns:
        One entry per data row; a repeated key keeps its last value.

    Raises:
        FileNotFoundError: If the file does not exist and ``missing_ok`` is false.
        ValueError: If a column is missing from the header, or a row has no
            cell for it.
    """
    source = Path(path)
    if missing_ok and not source.exists():
        return {}
    if encoding is None:
        encoding = chardet.detect(source.read_bytes())["encoding"]
    values: dict[str, str] = {}
    with source.open(encoding=encoding) as fin:
        reader = csv.DictReader(fin)
        columns = list(reader.fieldnames or [])
        for column in (key, value):
            if column not in columns:
                msg = f"read_key_values: column {column!r} not in the header of {source}: {columns}"
                raise ValueError(msg)
        for row in reader:
            row_key, row_value = row[key], row[value]
            if row_key is None or row_value is None:
                msg = f"read_key_values: {source} line {reader.line_num} has no {key!r}/{value!r} cell"
                raise ValueError(msg)
            values[row_key] = row_value
    return values


@overload
def read_excel(
    path: Path, *, sheet_name: str | int = 0, header: int | list[int] | None = 0,
    skiprows: int | list[int] | None = None, nrows: int | None = None,
    usecols: str | list[int] | list[str] | None = None, **pandas_kwargs: object,
) -> pd.DataFrame: ...


@overload
def read_excel(
    path: Path, *, sheet_name: None, header: int | list[int] | None = 0,
    skiprows: int | list[int] | None = None, nrows: int | None = None,
    usecols: str | list[int] | list[str] | None = None, **pandas_kwargs: object,
) -> dict[str, pd.DataFrame]: ...


@overload
def read_excel(
    path: Path, *, sheet_name: list[str], header: int | list[int] | None = 0,
    skiprows: int | list[int] | None = None, nrows: int | None = None,
    usecols: str | list[int] | list[str] | None = None, **pandas_kwargs: object,
) -> dict[str, pd.DataFrame]: ...


@overload
def read_excel(
    path: Path, *, sheet_name: list[int], header: int | list[int] | None = 0,
    skiprows: int | list[int] | None = None, nrows: int | None = None,
    usecols: str | list[int] | list[str] | None = None, **pandas_kwargs: object,
) -> dict[int, pd.DataFrame]: ...


@overload
def read_excel(
    path: Path, *, sheet_name: list[str | int], header: int | list[int] | None = 0,
    skiprows: int | list[int] | None = None, nrows: int | None = None,
    usecols: str | list[int] | list[str] | None = None, **pandas_kwargs: object,
) -> dict[str | int, pd.DataFrame]: ...


@node(tags=["builtin", "io"], version="2.0.0", idempotent=True)
def read_excel(
    path: Path, *, sheet_name: str | int | list[str] | list[int] | list[str | int] | None = 0, header: int | list[int] | None = 0,
    skiprows: int | list[int] | None = None, nrows: int | None = None,
    usecols: str | list[int] | list[str] | None = None, **pandas_kwargs: object,
) -> pd.DataFrame | dict[str, pd.DataFrame] | dict[int, pd.DataFrame] | dict[str | int, pd.DataFrame]:
    """Read one, several or all worksheets using pandas row and column options.

    This is the node form of the pandas-backed Excel reads used by v1 RDE
    processing code. One sheet, selected by name or position, is returned as
    a data frame. ``sheet_name=None`` returns every sheet in a dict keyed by
    sheet name; a list returns the listed sheets in a dict keyed by the list
    items as given, so ``["raw", 0]`` gives the keys ``"raw"`` and ``0``.

    Args:
        path: Excel workbook to read.
        sheet_name: Worksheet name or zero-based position, a list of them,
            or None for all worksheets.
        header: Header row positions, or None for unlabelled source data.
        skiprows: Number or positions of rows to skip.
        nrows: Maximum number of data rows to read.
        usecols: pandas column selection.
        pandas_kwargs: Additional pandas Excel reader options.

    Returns:
        A data frame for one sheet, or a dict of data frames for None or a list.

    Raises:
        ValueError: If a selected sheet does not exist, the list is empty, or
            the file is not a recognisable workbook.
        zipfile.BadZipFile: If an ``.xlsx`` container is corrupt.
    """
    return pd.read_excel(Path(path), sheet_name=sheet_name, header=header, skiprows=skiprows, nrows=nrows, usecols=usecols, **pandas_kwargs)


def _fill_colour(cell: Any) -> str | None:
    fill = cell.fill
    if fill is None or fill.fill_type is None:
        return None
    colour = fill.fgColor
    if colour.type == "rgb":
        return str(colour.rgb)
    if colour.type == "indexed":
        return COLOR_INDEX[colour.indexed] if 0 <= colour.indexed < len(COLOR_INDEX) else f"indexed:{colour.indexed}"
    return f"theme:{colour.theme}"


def _column_number(column: str | int) -> int:
    if isinstance(column, int):
        if column < 0:
            msg = f"read_excel_fills column position must be zero or positive, got {column}"
            raise ValueError(msg)
        return column + 1
    return column_index_from_string(column.upper())


def _rows_with_values(sheet: Any, first_row: int) -> list[tuple[Any, ...]]:
    rows = list(sheet.iter_rows(min_row=first_row))
    # pandas drops trailing rows without values, even when they are styled.
    while rows and all(cell.value is None for cell in rows[-1]):
        rows.pop()
    return rows


@node(tags=["builtin", "io"], version="2.0.0", idempotent=True)
def read_excel_fills(
    path: Path, *, column: str | int, sheet_name: str | int = 0, header: int | None = 0,
    skiprows: int = 0, nrows: int | None = None,
) -> list[str | None]:
    """Read the fill colour of one column for every data row of a worksheet.

    Templates that select rows by cell colour combine this with
    ``read_excel``: called with the same ``sheet_name``, ``header``,
    ``skiprows`` and ``nrows``, the result has one entry per data-frame row,
    so it can be assigned as a column. As in pandas, trailing rows without
    values are not data rows, even when they are filled.

    Args:
        path: Excel workbook to read.
        column: Column letter (``"A"``) or zero-based position.
        sheet_name: Worksheet name or zero-based position.
        header: Zero-based header row after ``skiprows``, or None for no header.
        skiprows: Number of leading worksheet rows to skip.
        nrows: Maximum number of data rows to read.

    Returns:
        One entry per data row: the ARGB hex string of an RGB or indexed fill,
        ``"theme:<n>"`` for a theme colour, or None for an unfilled cell.

    Raises:
        KeyError: If the named worksheet does not exist.
        IndexError: If the worksheet position does not exist.
        ValueError: If the column or row selection is invalid.
    """
    if skiprows < 0 or (header is not None and header < 0) or (nrows is not None and nrows < 0):
        msg = "read_excel_fills row selections must be zero or positive"
        raise ValueError(msg)
    column_number = _column_number(column)
    workbook = load_workbook(Path(path))
    try:
        sheet = workbook[sheet_name] if isinstance(sheet_name, str) else workbook.worksheets[sheet_name]
        rows = _rows_with_values(sheet, skiprows + 1)
    finally:
        workbook.close()
    data_rows = rows if header is None else rows[header + 1:]
    if nrows is not None:
        data_rows = data_rows[:nrows]
    return [_fill_colour(sheet.cell(row=row[0].row, column=column_number)) for row in data_rows]


@node(tags=["builtin", "io"], version="2.0.0", idempotent=True)
def read_json(path: Path) -> Any:
    """Read JSON using legacy encoding preferences with primary CP932 support.

    Args:
        path: JSON file to read.

    Returns:
        The decoded JSON value.

    Raises:
        OSError: If the source cannot be read.
        json.JSONDecodeError: If the source is not valid JSON.
    """
    source = Path(path)
    return json.loads(source.read_text(encoding=_detect_encoding(source)))


@node(tags=["builtin", "io"], version="2.0.0", idempotent=False)
def unzip_inputs(src_zip: Path, dst_dir: Path, *, include_dirs: bool = False) -> list[Path]:
    """Extract a ZIP archive while repairing Shift-JIS member names.

    Ported from ``rde2util.unzip_japanese_zip`` and its filename decoder.
    Each member's destination is resolved -- symlinks already present in
    ``dst_dir`` included -- and a member that would land outside ``dst_dir``
    is skipped with a warning, the containment policy of
    ``impl._zip_encoding.extract_zip_with_encoding``. Without it a member named
    like a pre-existing outward link overwrote the file behind the link.

    Args:
        src_zip: ZIP archive to extract.
        dst_dir: Destination directory.
        include_dirs: Whether directory entries of the archive, including
            empty directories, are returned as well.

    Returns:
        Extracted file paths in archive order, including repeated members.
        Directory entries are included only with ``include_dirs``; unsafe
        destinations are always excluded. Paths are absolute, matching the
        resolved extraction directory.
    """
    base_dir = Path(dst_dir).resolve()
    extracted: list[Path] = []
    with zipfile.ZipFile(Path(src_zip)) as archive:
        for member in archive.infolist():
            if not member.flag_bits & _UTF8_FLAG:
                member.filename = member.filename.encode("cp437").decode("cp932")
            destination = (base_dir / member.filename).resolve()
            sanitized = _zip_destination(base_dir, member.filename)
            if not destination.is_relative_to(base_dir) or not sanitized.is_relative_to(base_dir):
                logger.warning(
                    f"Skipping unsafe zip entry {member.filename!r}: path resolves outside {str(base_dir)!r}",
                )
                continue
            extracted_path = archive.extract(member, base_dir)
            if include_dirs or not member.is_dir():
                extracted.append(Path(extracted_path))
    return extracted
