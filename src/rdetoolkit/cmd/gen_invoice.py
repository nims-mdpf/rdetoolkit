"""CLI command for generating invoice.json from schema.

This module provides the GenerateInvoiceCommand class which implements
the CLI functionality for the 'rdetoolkit gen-invoice' command. It handles
user input, calls the invoice generator service, and manages output formatting.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import typer

from rdetoolkit.rdelogger import get_logger

logger = get_logger(__name__)


class GenerateInvoiceCommand:
    """Command to generate invoice.json from invoice.schema.json.

    This command provides CLI functionality to create invoice.json files
    from invoice schema definitions, supporting various generation modes
    and output formats.

    Attributes:
        schema_path: Path to invoice.schema.json file.
        output_path: Path where invoice.json will be written.
        fill_defaults: Whether to populate type-based default values.
        required_only: Whether to include only required fields.
        output_format: Output JSON format ("pretty" or "compact").

    Example:
        >>> cmd = GenerateInvoiceCommand(
        ...     schema_path=Path("invoice.schema.json"),
        ...     output_path=Path("invoice.json"),
        ...     fill_defaults=True,
        ...     required_only=False,
        ...     output_format="pretty"
        ... )
        >>> cmd.invoke()
    """

    def __init__(
        self,
        schema_path: Path,
        output_path: Path,
        *,
        fill_defaults: bool = True,
        required_only: bool = False,
        output_format: Literal["pretty", "compact"] = "pretty",
    ) -> None:
        """Initialize the command with configuration.

        Args:
            schema_path: Path to invoice.schema.json file.
            output_path: Path where invoice.json will be written.
            fill_defaults: If True, populate type-based default values.
            required_only: If True, only include required fields.
            output_format: Output format ("pretty" or "compact").
        """
        self.schema_path = schema_path
        self.output_path = output_path
        self.fill_defaults = fill_defaults
        self.required_only = required_only
        self.output_format = output_format

    def invoke(self) -> None:
        """Execute the invoice generation command.

        Process flow:
        1. Validate schema file exists
        2. Generate invoice using generator service
        3. Write to output path with appropriate formatting
        4. Display success/error messages

        Raises:
            typer.Abort: If generation or validation fails.
        """
        from rdetoolkit.exceptions import InvoiceSchemaValidationError  # noqa: PLC0415
        from rdetoolkit.invoice_generator import generate_invoice_from_schema  # noqa: PLC0415

        try:
            self._info_msg(f"Generating invoice from schema: {self.schema_path}")

            # Generate invoice
            invoice_data = generate_invoice_from_schema(
                self.schema_path,
                output_path=None,  # Get dict first, then format and write
                fill_defaults=self.fill_defaults,
                required_only=self.required_only,
            )

            # Write with appropriate formatting
            self._write_invoice(invoice_data)

            self._success_msg(f"Successfully generated: {self.output_path}")

        except FileNotFoundError as e:
            logger.exception(e)
            self._error_msg(f"Schema file not found: {self.schema_path}")
            raise typer.Abort from e

        except InvoiceSchemaValidationError as e:
            logger.exception(e)
            self._error_msg(f"Generated invoice failed validation: {e}")
            raise typer.Abort from e

        except Exception as e:
            logger.exception(e)
            self._error_msg(f"Failed to generate invoice: {e}")
            raise typer.Abort from e

    def _write_invoice(self, invoice_data: dict[str, Any]) -> None:
        """Write invoice data to file with specified format.

        Args:
            invoice_data: Invoice data dictionary to write.
        """
        # Ensure parent directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        if self.output_format == "pretty":
            # Pretty format with 4-space indentation
            with open(self.output_path, "w", encoding="utf-8") as f:
                json.dump(invoice_data, f, indent=4, ensure_ascii=False)
        else:  # compact
            # Compact format without indentation
            with open(self.output_path, "w", encoding="utf-8") as f:
                json.dump(invoice_data, f, ensure_ascii=False, separators=(",", ":"))

    def _info_msg(self, msg: str) -> None:
        """Display info message to user.

        Args:
            msg: Message to display.
        """
        typer.echo(msg)

    def _success_msg(self, msg: str) -> None:
        """Display success message to user.

        Args:
            msg: Message to display.
        """
        typer.echo(typer.style(msg, fg=typer.colors.GREEN))

    def _error_msg(self, msg: str) -> None:
        """Display error message to user.

        Args:
            msg: Message to display.
        """
        typer.echo(typer.style(f"Error! {msg}", fg=typer.colors.RED))
