"""Builders for lightweight v2 workflow tests."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from rdetoolkit.domain.output import create_output_context
from rdetoolkit.domain.paths import resolve_input_paths
from rdetoolkit.types import InputPaths, InvoiceData, OutputContext


def make_input_paths(tmp_path: Path, files: Iterable[str] = (), *, invoice_org: Path | None = None) -> InputPaths:
    """Create a minimal on-disk input tree for tests.

    Args:
        tmp_path: Root directory under which the RDE input directories are
            created.
        files: Optional file names to create under ``inputdata``.
        invoice_org: Run-level invoice source. Defaults to
            ``invoice/invoice.json``, as the Runner selects outside the
            backup modes; the file itself is not created.

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
    paths = resolve_input_paths(root)
    return replace(paths, invoice_org=paths.invoice / "invoice.json" if invoice_org is None else Path(invoice_org))


def make_output_context(tmp_path: Path) -> OutputContext:
    """Create a test output context with all canonical directories present."""
    return create_output_context(tmp_path, create=True)


def make_invoice(overrides: Mapping[str, Any] | None = None) -> InvoiceData:
    """Create minimal invoice data for tests.

    Args:
        overrides: Optional invoice sections (``basic``, ``custom``, etc.).
            Bare measurement keys are placed inside ``custom``.

    Returns:
        Invoice data with non-empty raw content.
    """
    raw: dict[str, Any] = {"basic": {"dataName": "test"}}
    if overrides:
        _merge_invoice_overrides(raw, overrides)
    return InvoiceData(raw=raw, mode="invoice")


def _merge_invoice_overrides(raw: dict[str, Any], overrides: Mapping[str, Any]) -> None:
    sections = {"datasetId", "basic", "custom", "sample", "attachments"}
    raw.update({key: value for key, value in overrides.items() if key in sections})
    custom = dict(raw.get("custom", {}))
    custom.update({key: value for key, value in overrides.items() if key not in sections})
    if custom or "custom" in overrides:
        raw["custom"] = custom
