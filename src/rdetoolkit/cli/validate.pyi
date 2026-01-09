"""Type stubs for rdetoolkit.cli.validate module."""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from rdetoolkit.cmd.validate import ValidationResult

app: typer.Typer

class OutputFormat(str, Enum):
    TEXT = "text"
    JSON = "json"

def handle_validation_result(
    result: ValidationResult,
    format_type: OutputFormat,
    strict: bool,
    quiet: bool,
) -> None: ...

def handle_file_not_found(path: Path, file_type: str) -> None: ...

def handle_validation_error(error: Exception, error_type: str) -> None: ...

def invoice_schema(
    schema_path: Path,
    format_type: OutputFormat = OutputFormat.TEXT,
    strict: bool = False,
    quiet: bool = False,
) -> None: ...

def metadata_def(
    metadata_def_path: Path,
    format_type: OutputFormat = OutputFormat.TEXT,
    strict: bool = False,
    quiet: bool = False,
) -> None: ...

def invoice(
    invoice_path: Path,
    schema_path: Path,
    format_type: OutputFormat = OutputFormat.TEXT,
    strict: bool = False,
    quiet: bool = False,
) -> None: ...

def metadata(
    metadata_path: Path,
    schema_path: Path,
    format_type: OutputFormat = OutputFormat.TEXT,
    strict: bool = False,
    quiet: bool = False,
) -> None: ...

def validate_all(
    base_dir: Path,
    format_type: OutputFormat = OutputFormat.TEXT,
    strict: bool = False,
    quiet: bool = False,
) -> None: ...
