"""Builtin nodes for canonical structured-data output."""

from __future__ import annotations

import codecs
import csv
import json
import os
from io import StringIO
from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Any, Literal, cast

import pandas as pd

from rdetoolkit.core.node import node
from rdetoolkit.types import InvoiceData, OutputContext, OutputKind

# csv.writer is typed with the six stdlib constants; save_csv accepts any int and lets csv validate it.
_CsvQuoting = Literal[0, 1, 2, 3, 4, 5]


@node(tags=["builtin", "structured"], version="2.0.0", idempotent=True)
def save_csv(
    df: pd.DataFrame,
    out: OutputContext,
    filename: str,
    *,
    float_format: str | None = None,
    header: bool | list[str] = True,
    index: bool = False,
    preamble: Sequence[Sequence[object]] | str | None = None,
    blank_line_after_preamble: bool = False,
    encoding: str = "utf-8",
    quoting: int = csv.QUOTE_MINIMAL,
    lineterminator: str | None = None,
) -> Path:
    """Save a data frame as CSV with optional headers, numeric formatting and dialect.

    Migrated from ``retired/outputcontext_save_methods_v20.py::save_csv``.
    Multi-level columns are rejected because they serialize as multiple
    header rows, violating the v2 structured-data contract.

    A ``preamble`` writes a block of lines before the table, such as the
    ``#title`` / ``#legend`` metadata header that ``rdetoolkit.graph`` parses.
    Rows may have different numbers of fields and are written with the same
    ``quoting`` and ``lineterminator`` as the table. The preamble and the
    table are encoded together once, so ``encoding="utf-8-sig"`` writes a
    single byte order mark at the start of the file.

    The defaults write the same bytes as before these options existed:
    UTF-8, ``csv.QUOTE_MINIMAL`` and the platform line ending.

    Nothing is written when an error below is raised.

    Args:
        df: Data frame with a flat column index.
        out: Output resource context.
        filename: Simple output filename.
        float_format: Optional pandas floating-point format string.
        header: Whether to write headers, or explicit column aliases.
        index: Whether to write the data frame's index.
        preamble: Rows written before the table, or a str written verbatim
            (it should end with its own line ending; ``quoting`` and
            ``lineterminator`` do not change it).
        blank_line_after_preamble: Write one empty line, using
            ``lineterminator``, between a non-empty preamble and the table.
        encoding: Codec used for the whole file, for example ``"utf-8-sig"``
            or ``"cp932"``.
        quoting: A ``csv`` module quoting constant such as
            ``csv.QUOTE_NONNUMERIC``, applied to preamble rows and the table.
            The table follows ``DataFrame.to_csv``: values formatted by
            ``float_format`` are text, so ``QUOTE_NONNUMERIC`` quotes them.
        lineterminator: Line ending for preamble rows and the table;
            ``None`` uses ``os.linesep``.

    Returns:
        Path to the CSV under ``out.struct``.

    Raises:
        ValueError: If the data frame would require multiple header rows, or
            ``lineterminator`` is empty.
        TypeError: If a preamble row is a single string instead of a
            sequence of fields, ``quoting`` is not a csv quoting constant, or
            ``lineterminator`` is not a str.
        LookupError: If ``encoding`` is not a known text codec.
        UnicodeEncodeError: If the text contains a character ``encoding``
            cannot represent.
        csv.Error: If a field cannot be written with ``quoting``, such as a
            delimiter under ``csv.QUOTE_NONE``.
    """
    if df.columns.nlevels != 1:
        msg = "save_csv requires a one-row header; MultiIndex columns are not supported"
        raise ValueError(msg)
    terminator = _csv_terminator(lineterminator)
    codecs.lookup(encoding)
    lead = _preamble_text(preamble, quoting=quoting, lineterminator=terminator)
    if lead and blank_line_after_preamble:
        lead += terminator
    table = df.to_csv(index=index, header=header, float_format=float_format, quoting=quoting, lineterminator=terminator)
    return out.write_bytes("struct", filename, (lead + table).encode(encoding))


def _csv_terminator(lineterminator: str | None) -> str:
    if lineterminator is None:
        return os.linesep
    if not isinstance(lineterminator, str):
        msg = f"save_csv lineterminator must be a str or None, not {type(lineterminator).__name__}"
        raise TypeError(msg)
    if not lineterminator:
        msg = "save_csv lineterminator must not be empty"
        raise ValueError(msg)
    return lineterminator


def _preamble_text(preamble: Sequence[Sequence[object]] | str | None, *, quoting: int, lineterminator: str) -> str:
    buffer = StringIO()
    # Built before the preamble check so a bad quoting value fails on every call.
    writer = csv.writer(buffer, quoting=cast("_CsvQuoting", quoting), lineterminator=lineterminator)
    if preamble is None or isinstance(preamble, str):
        return preamble or ""
    for row in preamble:
        if isinstance(row, (str, bytes)):
            msg = f"save_csv preamble rows must be sequences of fields, not {type(row).__name__}: {row!r}"
            raise TypeError(msg)
        writer.writerow(row)
    return buffer.getvalue()


def _json_bytes(content: object, *, indent: int | None, ensure_ascii: bool, caller: str) -> bytes:
    if indent is not None and (isinstance(indent, bool) or not isinstance(indent, int)):
        msg = f"{caller} indent must be an int or None, not {type(indent).__name__}"
        raise TypeError(msg)
    if indent is not None and indent < 0:
        msg = f"{caller} indent must not be negative: {indent}"
        raise ValueError(msg)
    if not isinstance(ensure_ascii, bool):
        msg = f"{caller} ensure_ascii must be a bool, not {type(ensure_ascii).__name__}"
        raise TypeError(msg)
    return json.dumps(content, ensure_ascii=ensure_ascii, indent=indent).encode("utf-8")


@node(tags=["builtin", "structured"], version="2.0.0", idempotent=True)
def save_json(
    content: object,
    out: OutputContext,
    filename: str,
    *,
    kind: OutputKind = "struct",
    indent: int | None = 2,
    ensure_ascii: bool = False,
) -> Path:
    r"""Save JSON-serializable content as UTF-8 under a selected output directory.

    Migrated from ``retired/outputcontext_save_methods_v20.py::save_bytes``
    with canonical JSON encoding added at the node boundary. The defaults
    write two-space indentation with non-ASCII characters preserved.

    Nothing is written when an error below is raised.

    Args:
        content: JSON-serializable value.
        out: Output resource context.
        filename: Simple output filename.
        kind: Output directory kind, defaulting to structured data.
        indent: Spaces per indentation level; ``None`` writes the whole
            value on one line with the ``json`` module's default separators.
        ensure_ascii: Escape non-ASCII characters as ``\uXXXX``.

    Returns:
        Path to the JSON file under the selected directory.

    Raises:
        TypeError: If ``indent`` is not an int or ``None`` (a bool is
            rejected), ``ensure_ascii`` is not a bool, or ``content`` is not
            JSON-serializable.
        ValueError: If ``indent`` is negative.
        UnicodeEncodeError: If ``content`` holds a lone surrogate and
            ``ensure_ascii`` is false.
    """
    encoded = _json_bytes(content, indent=indent, ensure_ascii=ensure_ascii, caller="save_json")
    return out.write_bytes(kind, filename, encoded)


@node(tags=["builtin", "structured"], version="2.0.0", idempotent=True)
def save_text(text: str, out: OutputContext, filename: str, *, kind: OutputKind = "struct", encoding: str = "utf-8") -> Path:
    """Save a text artifact in a selected output directory.

    Args:
        text: Text to encode and save.
        out: Output resource context.
        filename: Simple output filename.
        kind: Output directory kind.
        encoding: Character encoding used for the text bytes.

    Returns:
        Path to the saved text file.
    """
    return out.write_bytes(kind, filename, text.encode(encoding))


@node(tags=["builtin", "invoice"], version="2.0.0", idempotent=True)
def save_invoice(
    content: InvoiceData | Mapping[str, Any],
    out: OutputContext,
    *,
    indent: int | None = 4,
    drop_none: bool = False,
) -> Path:
    """Save an edited invoice using the v1 JSON formatting contract.

    This writes only the current tile's ``invoice.json``. The run-level
    ``InputPaths.invoice_org`` is read-only input: writing it so that later
    tiles inherit a value is not supported (#603). Compute tile-specific
    values in the tile's flow, for example with ``set_custom_fields``.

    With ``drop_none=True`` the written JSON omits every ``None`` value of a
    mapping and every ``None`` item of a list or tuple, at any depth, as v1
    ``InvoiceFile.overwrite`` sanitised invoices. ``0``, ``False``, ``""``
    and containers left empty are kept. The removal works on a copy:
    ``InvoiceData.raw`` and the given mapping are not modified.

    Nothing is written when an error below is raised.

    Args:
        content: Parsed invoice or its raw JSON object.
        out: Output resource context for the current tile.
        indent: Spaces per indentation level; ``None`` writes one line.
        drop_none: Omit ``None`` entries recursively from the written JSON.

    Returns:
        Path to the tile's invoice.json, UTF-8 with non-ASCII characters
        preserved and four-space indentation by default.

    Raises:
        TypeError: If ``indent`` is not an int or ``None`` (a bool is
            rejected), ``drop_none`` is not a bool, or the invoice holds a
            value that is not JSON-serializable.
        ValueError: If ``indent`` is negative.
    """
    if not isinstance(drop_none, bool):
        msg = f"save_invoice drop_none must be a bool, not {type(drop_none).__name__}"
        raise TypeError(msg)
    raw: object = content.raw if isinstance(content, InvoiceData) else dict(content)
    if drop_none:
        raw = _without_none(raw)
    encoded = _json_bytes(raw, indent=indent, ensure_ascii=False, caller="save_invoice")
    return out.write_bytes("invoice", "invoice.json", encoded)


def _without_none(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _without_none(item) for key, item in value.items() if item is not None}
    if isinstance(value, (list, tuple)):
        return [_without_none(item) for item in value if item is not None]
    return value
