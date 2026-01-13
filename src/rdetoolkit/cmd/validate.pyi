from _typeshed import Incomplete as Incomplete
from dataclasses import dataclass
from pathlib import Path
from rdetoolkit.validation import InvoiceValidator as InvoiceValidator
from typing import Any, Optional, Union

@dataclass
class ValidationError:
    field: str
    error_type: str
    message: str

@dataclass
class ValidationWarning:
    field: str
    warning_type: str
    message: str

@dataclass
class ValidationResult:
    target: str
    is_valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationWarning]
    @property
    def has_errors(self) -> bool: ...
    @property
    def has_warnings(self) -> bool: ...

class OutputFormatter:
    def format(self, result: ValidationResult) -> str: ...

class TextFormatter(OutputFormatter):
    quiet: bool
    def __init__(self, quiet: bool = False) -> None: ...
    def format(self, result: ValidationResult) -> str: ...

class JsonFormatter(OutputFormatter):
    def format(self, result: ValidationResult) -> str: ...

def determine_exit_code(result: ValidationResult, strict: bool = False) -> int: ...
def create_formatter(format_type: str, quiet: bool = False) -> OutputFormatter: ...

class _ValidationErrorParser:
    def _parse_validation_errors(self, error_message: str) -> list[ValidationError]: ...
    def _parse_validation_exception(self, exc: Exception) -> list[ValidationError]: ...

class InvoiceSchemaCommand(_ValidationErrorParser):
    schema_path: Path
    def __init__(self, schema_path: Union[str, Path]) -> None: ...
    def execute(self) -> ValidationResult: ...

class MetadataDefCommand(_ValidationErrorParser):
    metadata_def_path: Path
    def __init__(self, metadata_def_path: Union[str, Path]) -> None: ...
    def execute(self) -> ValidationResult: ...

class InvoiceCommand(_ValidationErrorParser):
    invoice_path: Path
    schema_path: Path
    def __init__(self, invoice_path: Union[str, Path], schema_path: Union[str, Path]) -> None: ...
    def execute(self) -> ValidationResult: ...

class MetadataCommand(_ValidationErrorParser):
    metadata_path: Path
    schema_path: Path
    def __init__(self, metadata_path: Union[str, Path], schema_path: Union[str, Path]) -> None: ...
    def execute(self) -> ValidationResult: ...

@dataclass
class DiscoveredFile:
    path: Path
    file_type: str
    schema_path: Optional[Path] = None
    exists: bool = True

class ValidateAllCommand:
    project_dir: Path
    def __init__(self, project_dir: str | Optional[Path] = None) -> None: ...
    def execute(self) -> list[ValidationResult]: ...
    def _discover_files(self) -> list[DiscoveredFile]: ...
