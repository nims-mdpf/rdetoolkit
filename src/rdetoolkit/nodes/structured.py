"""Builtin nodes for canonical structured-data output."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from rdetoolkit.core.node import node
from rdetoolkit.types import OutputContext


@node(tags=["builtin", "structured"], version="2.0.0", idempotent=True)
def save_csv(df: pd.DataFrame, out: OutputContext, filename: str) -> Path:
    """Save a data frame as a one-header-row UTF-8 CSV.

    Migrated from ``retired/outputcontext_save_methods_v20.py::save_csv``.
    Multi-level columns are rejected because they serialize as multiple
    header rows, violating the v2 structured-data contract.

    Args:
        df: Data frame with a flat column index.
        out: Output resource context.
        filename: Simple output filename.

    Returns:
        Path to the CSV under ``out.struct``.

    Raises:
        ValueError: If the data frame would require multiple header rows.
    """
    if df.columns.nlevels != 1:
        msg = "save_csv requires a one-row header; MultiIndex columns are not supported"
        raise ValueError(msg)
    content = df.to_csv(index=False).encode("utf-8")
    return out.write_bytes("struct", filename, content)


@node(tags=["builtin", "structured"], version="2.0.0", idempotent=True)
def save_json(content: object, out: OutputContext, filename: str) -> Path:
    """Save JSON-serializable content under the structured-data directory.

    Migrated from ``retired/outputcontext_save_methods_v20.py::save_bytes``
    with canonical JSON encoding added at the node boundary.

    Args:
        content: JSON-serializable value.
        out: Output resource context.
        filename: Simple output filename.

    Returns:
        Path to the JSON file under ``out.struct``.
    """
    encoded = json.dumps(content, ensure_ascii=False, indent=2).encode("utf-8")
    return out.write_bytes("struct", filename, encoded)
