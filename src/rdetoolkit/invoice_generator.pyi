"""Type stubs for rdetoolkit.invoice_generator module."""

from __future__ import annotations

from pathlib import Path
from typing import Any

def generate_invoice_from_schema(
    schema_path: Path | str,
    output_path: Path | str | None = None,
    *,
    fill_defaults: bool = True,
    required_only: bool = False,
) -> dict[str, Any]: ...
