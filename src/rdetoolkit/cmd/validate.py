"""Validation command implementation for rdetoolkit CLI."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from rdetoolkit.validation import InvoiceValidator, MetadataDefinitionValidator, MetadataValidator


@dataclass
class ValidationError:
    """Represents a validation error.

    Attributes:
        field: The field path where the error occurred
        error_type: The type of error (e.g., 'required', 'type', 'format')
        message: Human-readable error message
    """

    field: str
    error_type: str
    message: str


@dataclass
class ValidationWarning:
    """Represents a validation warning.

    Attributes:
        field: The field path where the warning occurred
        warning_type: The type of warning
        message: Human-readable warning message
    """

    field: str
    warning_type: str
    message: str


@dataclass
class ValidationResult:
    """Unified validation result structure.

    Attributes:
        target: Path or identifier being validated
        is_valid: Whether validation passed
        errors: List of validation errors
        warnings: List of validation warnings
    """

    target: str
    is_valid: bool
    errors: list[ValidationError]  # Python 3.9+: use list instead of List
    warnings: list[ValidationWarning]  # Python 3.9+: use list instead of List

    @property
    def has_errors(self) -> bool:
        """Check if result has errors.

        Returns:
            True if there are any errors, False otherwise
        """
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if result has warnings.

        Returns:
            True if there are any warnings, False otherwise
        """
        return len(self.warnings) > 0


class OutputFormatter(ABC):
    """Abstract base class for output formatters."""

    @abstractmethod
    def format(self, result: ValidationResult) -> str:
        """Format validation result for output.

        Args:
            result: Validation result to format

        Returns:
            Formatted string output
        """


class TextFormatter(OutputFormatter):
    """Human-readable text output formatter."""

    def __init__(self, quiet: bool = False) -> None:
        """Initialize text formatter.

        Args:
            quiet: If True, only show errors
        """
        self.quiet = quiet

    def format(self, result: ValidationResult) -> str:
        """Format validation result as human-readable text.

        Args:
            result: Validation result to format

        Returns:
            Human-readable text output
        """
        lines: list[str] = []

        # Header
        status = "✓ VALID" if result.is_valid else "✗ INVALID"
        lines.append(f"{status}: {result.target}")
        lines.append("")

        # Errors
        if result.errors:
            lines.append("Errors:")
            for idx, error in enumerate(result.errors, start=1):
                lines.append(f"  {idx}. Field: {error.field}")
                lines.append(f"     Type: {error.error_type}")
                lines.append(f"     Message: {error.message}")
            lines.append("")

        # Warnings (skip if quiet mode)
        if result.warnings and not self.quiet:
            lines.append("Warnings:")
            for idx, warning in enumerate(result.warnings, start=1):
                lines.append(f"  {idx}. Field: {warning.field}")
                lines.append(f"     Type: {warning.warning_type}")
                lines.append(f"     Message: {warning.message}")
            lines.append("")

        return "\n".join(lines)


class JsonFormatter(OutputFormatter):
    """Machine-readable JSON output formatter."""

    def format(self, result: ValidationResult) -> str:
        """Format validation result as JSON.

        Args:
            result: Validation result to format

        Returns:
            JSON string output
        """
        output = {
            "target": result.target,
            "valid": result.is_valid,
            "errors": [
                {
                    "field": error.field,
                    "type": error.error_type,
                    "message": error.message,
                }
                for error in result.errors
            ],
            "warnings": [
                {
                    "field": warning.field,
                    "type": warning.warning_type,
                    "message": warning.message,
                }
                for warning in result.warnings
            ],
        }

        return json.dumps(output, indent=2, ensure_ascii=False)


def determine_exit_code(result: ValidationResult, strict: bool = False) -> int:
    """Determine CLI exit code from validation result.

    Exit codes:
    - 0: Validation passed
    - 1: Validation failed (errors or warnings in strict mode)
    - 2: Usage/argument errors (handled by Typer)
    - 3: Internal errors (handled by exception handlers)

    Args:
        result: Validation result
        strict: If True, treat warnings as failures

    Returns:
        Exit code (0 or 1)
    """
    if result.has_errors:
        return 1
    if strict and result.has_warnings:
        return 1
    return 0


def create_formatter(format_type: str, quiet: bool = False) -> OutputFormatter:
    """Create output formatter based on format type.

    Args:
        format_type: Format type ("text" or "json")
        quiet: If True, only show errors (text format only)

    Returns:
        Output formatter instance

    Raises:
        ValueError: If format_type is not supported
    """
    if format_type == "text":
        return TextFormatter(quiet=quiet)
    if format_type == "json":
        return JsonFormatter()

    msg = f"Unsupported format type: {format_type}"
    raise ValueError(msg)


def _build_validation_error(error_data: dict[str, str]) -> ValidationError:
    """Build a ValidationError from parsed error data.

    Args:
        error_data: Parsed error fields from a validation error message.

    Returns:
        ValidationError instance.
    """
    return ValidationError(
        field=error_data.get("field", ""),
        error_type=error_data.get("type", ""),
        message=error_data.get("context", ""),
    )


def _parse_validation_errors(error_message: str) -> list[ValidationError]:
    """Parse validation errors from exception message.

    Args:
        error_message: Error message from validation exceptions.

    Returns:
        List of ValidationError objects.
    """
    errors: list[ValidationError] = []

    lines = error_message.split("\n")
    current_error: Optional[dict[str, str]] = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if current_error:
                errors.append(_build_validation_error(current_error))
                current_error = None
            continue

        if line[:1].isdigit() and ". Field:" in line:
            if current_error:
                errors.append(_build_validation_error(current_error))
            current_error = {}
            field = line.split("Field:", 1)[1].strip()
            current_error["field"] = field
        elif line.startswith("Type:") and current_error is not None:
            current_error["type"] = line.split("Type:", 1)[1].strip()
        elif line.startswith("Context:") and current_error is not None:
            current_error["context"] = line.split("Context:", 1)[1].strip()

    if current_error:
        errors.append(_build_validation_error(current_error))

    return errors


class _ValidationErrorParser:
    """Shared validation error parser for command classes."""

    def _parse_validation_errors(self, error_message: str) -> list[ValidationError]:
        """Parse validation errors from exception message.

        Args:
            error_message: Error message from validation exceptions.

        Returns:
            List of ValidationError objects.
        """
        return _parse_validation_errors(error_message)

    def _parse_validation_exception(self, exc: Exception) -> list[ValidationError]:
        """Parse validation errors from an exception, with fallback.

        Args:
            exc: Validation exception to parse.

        Returns:
            List of ValidationError objects.
        """
        errors = self._parse_validation_errors(str(exc))
        if errors:
            return errors

        message = str(exc) or f"Validation failed with {type(exc).__name__}."
        return [
            ValidationError(
                field="",
                error_type=type(exc).__name__,
                message=message,
            ),
        ]


class InvoiceSchemaCommand(_ValidationErrorParser):
    """Command to validate invoice schema JSON files.

    This command validates the structure and content of invoice.schema.json
    files using the InvoiceValidator's pre-validation logic.
    """

    def __init__(self, schema_path: str | Path) -> None:
        """Initialize invoice schema validation command.

        Args:
            schema_path: Path to invoice schema JSON file
        """
        self.schema_path = Path(schema_path) if isinstance(schema_path, str) else schema_path

    def execute(self) -> ValidationResult:
        """Execute invoice schema validation.

        Returns:
            ValidationResult with validation outcome

        Raises:
            FileNotFoundError: If schema file does not exist
        """
        if not self.schema_path.exists():
            msg = f"Schema file not found: {self.schema_path}"
            raise FileNotFoundError(msg)

        errors: list[ValidationError] = []
        warnings: list[ValidationWarning] = []

        try:
            # Use InvoiceValidator's pre-validation logic
            # InvoiceValidator's __init__ performs schema validation
            _ = InvoiceValidator(self.schema_path)

        except Exception as e:
            # Parse validation errors from exception message
            # InvoiceValidator raises InvoiceSchemaValidationError with structured messages
            errors = self._parse_validation_exception(e)

        is_valid = len(errors) == 0

        return ValidationResult(
            target=str(self.schema_path),
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
        )


class InvoiceCommand(_ValidationErrorParser):
    """Command to validate invoice data files against schema.

    This command validates invoice.json files using the InvoiceValidator
    to ensure data conforms to the invoice schema.
    """

    def __init__(
        self,
        invoice_path: str | Path,
        schema_path: str | Path,
    ) -> None:
        """Initialize invoice validation command.

        Args:
            invoice_path: Path to invoice.json file
            schema_path: Path to invoice.schema.json file
        """
        self.invoice_path = Path(invoice_path) if isinstance(invoice_path, str) else invoice_path
        self.schema_path = Path(schema_path) if isinstance(schema_path, str) else schema_path

    def execute(self) -> ValidationResult:
        """Execute invoice validation.

        Returns:
            ValidationResult with validation outcome

        Raises:
            FileNotFoundError: If invoice or schema file does not exist
        """
        if not self.invoice_path.exists():
            msg = f"Invoice file not found: {self.invoice_path}"
            raise FileNotFoundError(msg)

        if not self.schema_path.exists():
            msg = f"Schema file not found: {self.schema_path}"
            raise FileNotFoundError(msg)

        errors: list[ValidationError] = []
        warnings: list[ValidationWarning] = []

        try:
            validator = InvoiceValidator(self.schema_path)
            # validate() method returns the validated data if successful
            # or raises InvoiceSchemaValidationError on failure
            _ = validator.validate(path=self.invoice_path)

        except Exception as e:
            # Parse validation errors from exception message
            errors = self._parse_validation_exception(e)

        is_valid = len(errors) == 0

        return ValidationResult(
            target=str(self.invoice_path),
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
        )


class MetadataDefCommand(_ValidationErrorParser):
    """Command to validate metadata definition JSON files.

    This command validates metadata definition files using the
    MetadataDefinitionValidator (for metadata-def.json structure).

    Note:
        This is separate from MetadataCommand which validates metadata.json
        data files against metadata definition schemas.
    """

    def __init__(self, metadata_def_path: str | Path) -> None:
        """Initialize metadata definition validation command.

        Args:
            metadata_def_path: Path to metadata definition JSON file
        """
        self.metadata_def_path = (
            Path(metadata_def_path)
            if isinstance(metadata_def_path, str)
            else metadata_def_path
        )

    def execute(self) -> ValidationResult:
        """Execute metadata definition validation.

        Returns:
            ValidationResult with validation outcome

        Raises:
            FileNotFoundError: If metadata definition file does not exist
        """
        if not self.metadata_def_path.exists():
            msg = f"Metadata definition file not found: {self.metadata_def_path}"
            raise FileNotFoundError(msg)

        errors: list[ValidationError] = []
        warnings: list[ValidationWarning] = []

        try:
            # Use MetadataDefinitionValidator for metadata-def.json
            validator = MetadataDefinitionValidator()
            # validate() with path parameter validates the file
            _ = validator.validate(path=self.metadata_def_path)

        except Exception as e:
            # Parse validation errors from exception message
            errors = self._parse_validation_exception(e)

        is_valid = len(errors) == 0

        return ValidationResult(
            target=str(self.metadata_def_path),
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
        )


class MetadataCommand(_ValidationErrorParser):
    """Command to validate metadata data files against definition schema.

    This command validates metadata.json files using the MetadataValidator
    to ensure data conforms to the metadata definition.
    """

    def __init__(
        self,
        metadata_path: str | Path,
        schema_path: str | Path,
    ) -> None:
        """Initialize metadata validation command.

        Args:
            metadata_path: Path to metadata.json file
            schema_path: Path to metadata definition JSON file
        """
        self.metadata_path = Path(metadata_path) if isinstance(metadata_path, str) else metadata_path
        self.schema_path = Path(schema_path) if isinstance(schema_path, str) else schema_path

    def execute(self) -> ValidationResult:
        """Execute metadata validation.

        Returns:
            ValidationResult with validation outcome

        Raises:
            FileNotFoundError: If metadata or schema file does not exist
        """
        if not self.metadata_path.exists():
            msg = f"Metadata file not found: {self.metadata_path}"
            raise FileNotFoundError(msg)

        if not self.schema_path.exists():
            msg = f"Metadata definition file not found: {self.schema_path}"
            raise FileNotFoundError(msg)

        errors: list[ValidationError] = []
        warnings: list[ValidationWarning] = []

        try:
            # First validate the schema/definition itself
            validator = MetadataValidator()
            _ = validator.validate(path=self.schema_path)

            # Then validate the metadata data against the schema
            # Note: Current MetadataValidator validates individual items,
            # not data against a separate schema. This is a structural difference
            # from invoice validation. We validate that the metadata file
            # conforms to MetadataItem structure.
            _ = validator.validate(path=self.metadata_path)

        except Exception as e:
            # Parse validation errors from exception message
            errors = self._parse_validation_exception(e)

        is_valid = len(errors) == 0

        return ValidationResult(
            target=str(self.metadata_path),
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
        )


@dataclass
class DiscoveredFile:
    """Represents a discovered RDE file in a project.

    Attributes:
        path: Absolute path to the file
        file_type: Type of file (invoice-schema, metadata-def, invoice, metadata)
        schema_path: Path to schema file (for invoice/metadata validation)
        exists: Whether the file exists
    """

    path: Path
    file_type: str
    schema_path: Optional[Path] = None
    exists: bool = True


class ValidateAllCommand:
    """Command to discover and validate all standard RDE files in a project.

    This command implements automatic discovery of RDE files based on the
    standard project layout created by the 'init' command, then validates
    each discovered file.

    Standard RDE project structure:
    - container/data/tasksupport/invoice.schema.json
    - container/data/tasksupport/metadata-def.json
    - template/tasksupport/invoice.schema.json
    - template/tasksupport/metadata-def.json
    - input/invoice/invoice.json (with schema discovery)
    - input/metadata/metadata.json (with schema discovery, optional)
    """

    def __init__(self, project_dir: Union[str, Path, None] = None) -> None:
        """Initialize validate-all command.

        Args:
            project_dir: Root directory of RDE project (defaults to current directory)
        """
        self.project_dir = Path.cwd() if project_dir is None else Path(project_dir)

    def execute(self) -> list[ValidationResult]:
        """Execute validation for all discovered files.

        Returns:
            List of ValidationResult objects for all validations

        Raises:
            FileNotFoundError: If project directory does not exist
        """
        if not self.project_dir.exists():
            msg = f"Project directory not found: {self.project_dir}"
            raise FileNotFoundError(msg)

        # Discover files
        discovered = self._discover_files()

        if not discovered:
            # No standard files found
            return []

        # Validate each file
        results: list[ValidationResult] = []
        for file_info in discovered:
            if not file_info.exists:
                # Add warning for missing expected files
                results.append(
                    ValidationResult(
                        target=str(file_info.path),
                        is_valid=True,
                        errors=[],
                        warnings=[
                            ValidationWarning(
                                field="",
                                warning_type="missing_file",
                                message=f"Expected file not found: {file_info.path}",
                            ),
                        ],
                    ),
                )
                continue

            # Validate based on file type
            try:
                result = self._validate_file(file_info)
                results.append(result)
            except Exception as e:
                # Convert exceptions to validation errors
                results.append(
                    ValidationResult(
                        target=str(file_info.path),
                        is_valid=False,
                        errors=[
                            ValidationError(
                                field="",
                                error_type="validation_error",
                                message=str(e),
                            ),
                        ],
                        warnings=[],
                    ),
                )

        return results

    def _discover_files(self) -> list[DiscoveredFile]:
        """Discover standard RDE files in the project directory.

        Returns:
            List of DiscoveredFile objects
        """
        discovered: list[DiscoveredFile] = []

        # Discover schema files
        container_schemas = self._discover_container_schemas()
        template_schemas = self._discover_template_schemas()
        discovered.extend(container_schemas)
        discovered.extend(template_schemas)

        # Discover data files (need schema paths)
        container_invoice_schema = self.project_dir / "container" / "data" / "tasksupport" / "invoice.schema.json"
        template_invoice_schema = self.project_dir / "templates" / "tasksupport" / "invoice.schema.json"
        container_metadata_def = self.project_dir / "container" / "data" / "tasksupport" / "metadata-def.json"
        template_metadata_def = self.project_dir / "templates" / "tasksupport" / "metadata-def.json"

        data_files = self._discover_data_files(
            container_invoice_schema,
            template_invoice_schema,
            container_metadata_def,
            template_metadata_def,
        )
        discovered.extend(data_files)

        return discovered

    def _discover_container_schemas(self) -> list[DiscoveredFile]:
        """Discover schema files in container/data/tasksupport/.

        Returns:
            List of discovered schema files
        """
        discovered: list[DiscoveredFile] = []
        container_tasksupport = self.project_dir / "container" / "data" / "tasksupport"

        invoice_schema = container_tasksupport / "invoice.schema.json"
        if invoice_schema.exists():
            discovered.append(
                DiscoveredFile(
                    path=invoice_schema,
                    file_type="invoice-schema",
                    exists=True,
                ),
            )

        metadata_def = container_tasksupport / "metadata-def.json"
        if metadata_def.exists():
            discovered.append(
                DiscoveredFile(
                    path=metadata_def,
                    file_type="metadata-def",
                    exists=True,
                ),
            )

        return discovered

    def _discover_template_schemas(self) -> list[DiscoveredFile]:
        """Discover schema files in templates/tasksupport/.

        Returns:
            List of discovered schema files
        """
        discovered: list[DiscoveredFile] = []
        template_tasksupport = self.project_dir / "templates" / "tasksupport"

        invoice_schema = template_tasksupport / "invoice.schema.json"
        if invoice_schema.exists():
            discovered.append(
                DiscoveredFile(
                    path=invoice_schema,
                    file_type="invoice-schema",
                    exists=True,
                ),
            )

        metadata_def = template_tasksupport / "metadata-def.json"
        if metadata_def.exists():
            discovered.append(
                DiscoveredFile(
                    path=metadata_def,
                    file_type="metadata-def",
                    exists=True,
                ),
            )

        return discovered

    def _discover_data_files(
        self,
        container_invoice_schema: Path,
        template_invoice_schema: Path,
        container_metadata_def: Path,
        template_metadata_def: Path,
    ) -> list[DiscoveredFile]:
        """Discover data files in input/.

        Args:
            container_invoice_schema: Path to container invoice schema
            template_invoice_schema: Path to template invoice schema
            container_metadata_def: Path to container metadata definition
            template_metadata_def: Path to template metadata definition

        Returns:
            List of discovered data files
        """
        discovered: list[DiscoveredFile] = []

        # Invoice data file
        input_invoice = self.project_dir / "input" / "invoice" / "invoice.json"
        invoice_schema = self._find_schema(container_invoice_schema, template_invoice_schema)
        if input_invoice.exists() and invoice_schema:
            discovered.append(
                DiscoveredFile(
                    path=input_invoice,
                    file_type="invoice",
                    schema_path=invoice_schema,
                    exists=True,
                ),
            )

        # Metadata data file (optional)
        input_metadata = self.project_dir / "input" / "metadata" / "metadata.json"
        metadata_schema = self._find_schema(container_metadata_def, template_metadata_def)
        if input_metadata.exists() and metadata_schema:
            discovered.append(
                DiscoveredFile(
                    path=input_metadata,
                    file_type="metadata",
                    schema_path=metadata_schema,
                    exists=True,
                ),
            )

        return discovered

    def _find_schema(self, container_path: Path, template_path: Path) -> Optional[Path]:
        """Find schema file, preferring container over template.

        Args:
            container_path: Path to container schema
            template_path: Path to template schema

        Returns:
            Path to schema file, or None if not found
        """
        if container_path.exists():
            return container_path
        if template_path.exists():
            return template_path
        return None

    def _validate_file(self, file_info: DiscoveredFile) -> ValidationResult:
        """Validate a single file based on its type.

        Args:
            file_info: Information about the file to validate

        Returns:
            ValidationResult for the file
        """
        if file_info.file_type == "invoice-schema":
            invoice_schema_cmd = InvoiceSchemaCommand(file_info.path)
            return invoice_schema_cmd.execute()

        if file_info.file_type == "metadata-def":
            metadata_def_cmd = MetadataDefCommand(file_info.path)
            return metadata_def_cmd.execute()

        if file_info.file_type == "invoice":
            if not file_info.schema_path:
                msg = f"Cannot validate invoice without schema: {file_info.path}"
                raise ValueError(msg)
            invoice_cmd = InvoiceCommand(file_info.path, file_info.schema_path)
            return invoice_cmd.execute()

        if file_info.file_type == "metadata":
            if not file_info.schema_path:
                msg = f"Cannot validate metadata without schema: {file_info.path}"
                raise ValueError(msg)
            metadata_cmd = MetadataCommand(file_info.path, file_info.schema_path)
            return metadata_cmd.execute()

        msg = f"Unknown file type: {file_info.file_type}"
        raise ValueError(msg)
