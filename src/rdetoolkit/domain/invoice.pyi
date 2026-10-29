from pathlib import Path
from typing import Any
from rdetoolkit.invoicefile import ExcelInvoiceFile as ExcelInvoiceFile, InvoiceFile as InvoiceFile, SmartTableFile as SmartTableFile
from rdetoolkit.modes.smarttable import SmartTableInvoiceBuilder as SmartTableInvoiceBuilder
from rdetoolkit.types import InvoiceData as InvoiceData

def load_invoice(invoice_path: str | Path, *, schema_path: str | Path | None = None) -> InvoiceData: ...
def open_invoice_file(invoice_path: str | Path, *, schema_path: str | Path | None = None) -> InvoiceFile: ...
def open_excel_invoice(invoice_path: str | Path) -> ExcelInvoiceFile: ...
def open_smarttable(table_path: str | Path) -> SmartTableFile: ...
def build_excelinvoice_tile_invoice(
    *,
    excel_path: Path,
    invoice_org: Path,
    invoice_schema_path: Path,
    dist_path: Path,
    idx: int,
) -> InvoiceData: ...
def smarttable_invoice_builder() -> SmartTableInvoiceBuilder: ...
def build_smarttable_tile_invoice(
    *,
    smarttable_rowfile: Path,
    invoice_org: Path,
    invoice_schema_path: Path,
    dist_path: Path,
    builder: SmartTableInvoiceBuilder | None = ...,
) -> tuple[InvoiceData, dict[str, Any] | None]: ...
