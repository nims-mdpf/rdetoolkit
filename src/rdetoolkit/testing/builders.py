"""Builders for lightweight v2 workflow tests."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from rdetoolkit.domain.output import create_output_context
from rdetoolkit.domain.paths import resolve_input_paths
from rdetoolkit.types import InputPaths, InvoiceData, OutputContext


def make_input_paths(tmp_path: Path, files: Iterable[str] = ()) -> InputPaths:
    """Create a minimal on-disk input tree for tests.

    Args:
        tmp_path: Root directory under which the RDE input directories are
            created.
        files: Optional file names to create under ``inputdata``.

    Returns:
        Input path bundle for the created tree.
    """
    root = Path(tmp_path)
    inputdata = root / "inputdata"
    for name in ("inputdata", "invoice", "tasksupport"):
        (root / name).mkdir(parents=True, exist_ok=True)
    for filename in files:
        path = inputdata / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    return resolve_input_paths(root)


def make_output_context(tmp_path: Path) -> OutputContext:
    """Create a test output context with all canonical directories present."""
    return create_output_context(tmp_path, create=True)


def make_invoice(overrides: Mapping[str, Any] | None = None) -> InvoiceData:
    """Create minimal invoice data for tests.

    Args:
        overrides: Optional top-level values merged into the raw invoice dict.

    Returns:
        Invoice data with non-empty raw content.
    """
    raw: dict[str, Any] = {"basic": {"dataName": "test"}}
    if overrides:
        raw.update(dict(overrides))
    return InvoiceData(raw=raw, mode="invoice")
