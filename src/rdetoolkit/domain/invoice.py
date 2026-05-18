"""Invoice parsing facade for v2 domain workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rdetoolkit.fileops import readf_json
from rdetoolkit.invoicefile import ExcelInvoiceFile, InvoiceFile, SmartTableFile
from rdetoolkit.types import InvoiceData


def load_invoice(invoice_path: str | Path, *, schema_path: str | Path | None = None) -> InvoiceData:
    """Load a JSON invoice file into v2 ``InvoiceData``.

    Args:
        invoice_path: Path to ``invoice.json``.
        schema_path: Optional path to ``invoice.schema.json`` to retain on the
            facade payload for downstream validation.

    Returns:
        Parsed invoice data.

    Raises:
        FileNotFoundError: If ``invoice_path`` does not exist.
        ValueError: If the invoice root is not a JSON object.
    """
    path = Path(invoice_path)
    if not path.exists():
        msg = f"Invoice file does not exist: {path}"
        raise FileNotFoundError(msg)
    raw: Any = readf_json(path)
    if not isinstance(raw, dict):
        msg = "Invoice JSON root must be an object"
        raise ValueError(msg)
    schema = readf_json(Path(schema_path)) if schema_path is not None else None
    return InvoiceData(raw=raw, mode="invoice", schema=schema)


def open_invoice_file(invoice_path: str | Path, *, schema_path: str | Path | None = None) -> InvoiceFile:
    """Open a JSON invoice using the legacy invoicefile implementation.

    Args:
        invoice_path: Path to ``invoice.json``.
        schema_path: Optional validation schema path.

    Returns:
        Legacy ``InvoiceFile`` instance.
    """
    schema = Path(schema_path) if schema_path is not None else None
    return InvoiceFile(Path(invoice_path), schema_path=schema)


def open_excel_invoice(invoice_path: str | Path) -> ExcelInvoiceFile:
    """Open an Excel invoice using the legacy invoicefile implementation.

    Args:
        invoice_path: Path to an Excel invoice workbook.

    Returns:
        Legacy ``ExcelInvoiceFile`` instance.
    """
    return ExcelInvoiceFile(Path(invoice_path))


def open_smarttable(table_path: str | Path) -> SmartTableFile:
    """Open a SmartTable using the legacy invoicefile implementation.

    Args:
        table_path: Path to a SmartTable file.

    Returns:
        Legacy ``SmartTableFile`` instance.
    """
    return SmartTableFile(Path(table_path))
