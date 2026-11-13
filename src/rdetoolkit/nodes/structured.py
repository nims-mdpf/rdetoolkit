"""Builtin nodes for canonical structured-data output."""

from __future__ import annotations

import csv
import json
import os
from io import StringIO
from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from rdetoolkit.core.node import node
from rdetoolkit.types import InvoiceData, OutputContext, OutputKind


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
) -> Path:
    """Save a data frame as UTF-8 CSV with optional headers and numeric formatting.

    Migrated from ``retired/outputcontext_save_methods_v20.py::save_csv``.
    Multi-level columns are rejected because they serialize as multiple
    header rows, violating the v2 structured-data contract.

    A ``preamble`` writes a block of lines before the table, such as the
    ``#title`` / ``#legend`` metadata header that ``rdetoolkit.graph`` parses.
    Rows may have different numbers of fields and are written with the same
    csv dialect and line ending as the table.

    Args:
        df: Data frame with a flat column index.
        out: Output resource context.
        filename: Simple output filename.
        float_format: Optional pandas floating-point format string.
        header: Whether to write headers, or explicit column aliases.
        index: Whether to write the data frame's index.
        preamble: Rows written before the table, or a str written verbatim
            (it should end with its own line ending).
        blank_line_after_preamble: Write one empty line between a non-empty
            preamble and the table.

    Returns:
        Path to the CSV under ``out.struct``.

    Raises:
        ValueError: If the data frame would require multiple header rows.
        TypeError: If a preamble row is a single string instead of a
            sequence of fields.
    """
    if df.columns.nlevels != 1:
        msg = "save_csv requires a one-row header; MultiIndex columns are not supported"
        raise ValueError(msg)
    lead = _preamble_text(preamble)
    if lead and blank_line_after_preamble:
        lead += os.linesep
    table = df.to_csv(index=index, header=header, float_format=float_format, lineterminator=os.linesep)
    return out.write_bytes("struct", filename, (lead + table).encode("utf-8"))


def _preamble_text(preamble: Sequence[Sequence[object]] | str | None) -> str:
    if preamble is None or isinstance(preamble, str):
        return preamble or ""
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator=os.linesep)
    for row in preamble:
        if isinstance(row, (str, bytes)):
            msg = f"save_csv preamble rows must be sequences of fields, not {type(row).__name__}: {row!r}"
            raise TypeError(msg)
        writer.writerow(row)
    return buffer.getvalue()


@node(tags=["builtin", "structured"], version="2.0.0", idempotent=True)
def save_json(content: object, out: OutputContext, filename: str, *, kind: OutputKind = "struct") -> Path:
    """Save JSON-serializable content under a selected output directory.

    Migrated from ``retired/outputcontext_save_methods_v20.py::save_bytes``
    with canonical JSON encoding added at the node boundary.

    Args:
        content: JSON-serializable value.
        out: Output resource context.
        filename: Simple output filename.
        kind: Output directory kind, defaulting to structured data.

    Returns:
        Path to the JSON file under the selected directory.
    """
    encoded = json.dumps(content, ensure_ascii=False, indent=2).encode("utf-8")
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
def save_invoice(content: InvoiceData | Mapping[str, Any], out: OutputContext) -> Path:
    """Save an edited invoice using the v1 JSON formatting contract.

    This writes only the current tile's ``invoice.json``. The run-level
    ``InputPaths.invoice_org`` is read-only input: writing it so that later
    tiles inherit a value is not supported (#603). Compute tile-specific
    values in the tile's flow, for example with ``set_custom_fields``.

    Args:
        content: Parsed invoice or its raw JSON object.
        out: Output resource context for the current tile.

    Returns:
        Path to the tile's invoice.json, with four-space indentation and
        non-ASCII characters preserved.
    """
    raw = content.raw if isinstance(content, InvoiceData) else dict(content)
    encoded = json.dumps(raw, ensure_ascii=False, indent=4).encode("utf-8")
    return out.write_bytes("invoice", "invoice.json", encoded)
