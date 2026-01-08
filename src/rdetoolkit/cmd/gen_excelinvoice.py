from __future__ import annotations

import pathlib
from typing import Literal

import typer

from rdetoolkit.exceptions import InvoiceSchemaValidationError
from rdetoolkit.invoicefile import ExcelInvoiceFile
from rdetoolkit.rdelogger import get_logger

logger = get_logger(__name__)


class GenerateExcelInvoiceCommand:

    def __init__(self, invoice_schema_file: pathlib.Path, output_path: pathlib.Path, mode: Literal["file", "folder"]) -> None:
        self.invoice_schema_file = invoice_schema_file
        self.output_path = output_path
        self.mode = mode

    def invoke(self) -> None:
        """Generate an Excel invoice template from the provided schema."""
        rule_excelinvoice_suffix = '_excel_invoice.xlsx'
        typer.echo("📄 Generating ExcelInvoice template...")
        typer.echo(f"- Schema: {self.invoice_schema_file}")
        typer.echo(f"- Output: {self.output_path}")
        typer.echo(f"- Mode: {self.mode}")

        if not self.output_path.name.endswith(rule_excelinvoice_suffix):
            typer.echo(typer.style(f"🔥 Warning: The output file name '{self.output_path.name}' must end with '{rule_excelinvoice_suffix}'.", fg=typer.colors.YELLOW))
            raise typer.Abort

        try:
            if not self.invoice_schema_file.exists():
                emsg = f"Schema file not found: {self.invoice_schema_file}"
                raise FileNotFoundError(emsg)
            ExcelInvoiceFile.generate_template(self.invoice_schema_file, self.output_path, self.mode)
            typer.echo(typer.style(f"✨ ExcelInvoice template generated successfully! : {self.output_path}", fg=typer.colors.GREEN))
        except InvoiceSchemaValidationError as e:
            logger.error(f"File error: {e}")
            typer.echo(typer.style(f"🔥 Schema Error: {e}", fg=typer.colors.RED))
            raise typer.Abort from e
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            typer.echo(typer.style(f"🔥 Error: An unexpected error occurred: {e}", fg=typer.colors.RED))
            raise typer.Abort from e
