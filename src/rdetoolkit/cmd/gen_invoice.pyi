"""Type stubs for rdetoolkit.cmd.gen_invoice module."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

class GenerateInvoiceCommand:
    """Command class for generating invoice.json from invoice.schema.json."""

    schema_path: Path
    output_path: Path
    fill_defaults: bool
    required_only: bool
    output_format: Literal["pretty", "compact"]

    def __init__(
        self,
        schema_path: Path,
        output_path: Path,
        fill_defaults: bool = True,
        required_only: bool = False,
        output_format: Literal["pretty", "compact"] = "pretty",
    ) -> None: ...
    def invoke(self) -> None: ...
