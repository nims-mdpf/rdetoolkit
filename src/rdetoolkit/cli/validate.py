"""Validate CLI commands for rdetoolkit."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Optional

import typer

if TYPE_CHECKING:
    from rdetoolkit.cmd.validate import ValidationResult

app = typer.Typer(
    name="validate",
    help="""Validate RDE schema and data files.

All validate commands use standardized exit codes:
  0 = Success (validation passed)
  1 = Validation failure (data/schema issues)
  2 = Usage error (invalid arguments, missing files)
""",
    no_args_is_help=True,
)


class OutputFormat(str, Enum):
    """Output format options."""

    TEXT = "text"
    JSON = "json"


def handle_validation_result(
    result: ValidationResult,
    format_type: OutputFormat,
    strict: bool,
    quiet: bool,
) -> None:
    """Handle validation result output and exit code.

    Args:
        result: Validation result
        format_type: Output format (text or json)
        strict: Treat warnings as failures
        quiet: Only show errors (text format only)

    Raises:
        typer.Exit: Always raises to exit with appropriate code
    """
    from rdetoolkit.cmd.validate import create_formatter, determine_exit_code

    formatter = create_formatter(format_type.value, quiet=quiet)
    output = formatter.format(result)
    typer.echo(output)

    exit_code = determine_exit_code(result, strict=strict)
    raise typer.Exit(code=exit_code)


def handle_file_not_found(path: Path, file_type: str) -> None:
    """Handle file not found error.

    Args:
        path: Path that was not found
        file_type: Description of file type (e.g., "schema", "invoice")

    Raises:
        typer.Exit: Always raises with exit code 2
    """
    msg = f"Error: {file_type} file not found: {path}"
    typer.echo(msg, err=True)
    raise typer.Exit(code=2)


def handle_validation_error(error: Exception, error_type: str) -> None:
    """Handle validation errors.

    Args:
        error: Exception that occurred
        error_type: Description of error type

    Raises:
        typer.Exit: Always raises with appropriate exit code
    """
    # Map known exceptions to exit code 1 (validation failure)
    from rdetoolkit.exceptions import (
        InvoiceSchemaValidationError,
        MetadataValidationError,
    )

    if isinstance(error, (InvoiceSchemaValidationError, MetadataValidationError)):
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error

    # All other errors (including internal errors) map to exit code 2
    # This includes unexpected exceptions that indicate configuration or usage issues
    msg = f"Error during {error_type}: {error}"
    typer.echo(msg, err=True)
    raise typer.Exit(code=2) from error


# Common options for validation commands
FormatOption = Annotated[
    OutputFormat,
    typer.Option(
        "--format",
        "-f",
        help="Output format: text (human-readable) or json (machine-readable)",
    ),
]

StrictOption = Annotated[
    bool,
    typer.Option(
        "--strict/--no-strict",
        help="Treat warnings as failures",
    ),
]

QuietOption = Annotated[
    bool,
    typer.Option(
        "--quiet",
        "-q",
        help="Only show errors (text format only)",
    ),
]


@app.command("invoice-schema")
def invoice_schema(
    schema_path: Annotated[
        Path,
        typer.Argument(
            help="Path to invoice.schema.json file",
            exists=True,
            dir_okay=False,
            resolve_path=True,
        ),
    ],
    format_type: FormatOption = OutputFormat.TEXT,
    strict: StrictOption = False,
    quiet: QuietOption = False,
) -> None:
    """Validate invoice schema JSON file structure and content.

    Validates that the invoice schema file conforms to the expected structure
    and contains valid field definitions.

    Exit Codes:
        0: Success - validation passed
        1: Validation failure - schema structure issues found
        2: Usage error - file not found or invalid arguments

    Examples:
        rdetoolkit validate invoice-schema tasksupport/invoice.schema.json
        rdetoolkit validate invoice-schema schema.json --format json
    """
    from rdetoolkit.cmd.validate import InvoiceSchemaCommand

    try:
        command = InvoiceSchemaCommand(schema_path)
        result = command.execute()
        handle_validation_result(result, format_type, strict, quiet)
    except typer.Exit:
        # Re-raise typer.Exit to let Typer handle it properly
        raise
    except FileNotFoundError:
        handle_file_not_found(schema_path, "Schema")
    except Exception as e:
        handle_validation_error(e, "invoice schema validation")


@app.command("metadata-def")
def metadata_def(
    metadata_def_path: Annotated[
        Path,
        typer.Argument(
            help="Path to metadata definition JSON file",
            exists=True,
            dir_okay=False,
            resolve_path=True,
        ),
    ],
    format_type: FormatOption = OutputFormat.TEXT,
    strict: StrictOption = False,
    quiet: QuietOption = False,
) -> None:
    """Validate metadata definition JSON file structure.

    Validates that the metadata definition file conforms to the expected
    structure defined by the MetadataItem schema.

    Exit Codes:
        0: Success - validation passed
        1: Validation failure - definition structure issues found
        2: Usage error - file not found or invalid arguments

    Examples:
        rdetoolkit validate metadata-def tasksupport/metadata_def.json
        rdetoolkit validate metadata-def metadata_def.json --format json
    """
    from rdetoolkit.cmd.validate import MetadataDefCommand

    try:
        command = MetadataDefCommand(metadata_def_path)
        result = command.execute()
        handle_validation_result(result, format_type, strict, quiet)
    except typer.Exit:
        # Re-raise typer.Exit to let Typer handle it properly
        raise
    except FileNotFoundError:
        handle_file_not_found(metadata_def_path, "Metadata definition")
    except Exception as e:
        handle_validation_error(e, "metadata definition validation")


@app.command("invoice")
def invoice(
    invoice_path: Annotated[
        Path,
        typer.Argument(
            help="Path to invoice.json file",
            exists=True,
            dir_okay=False,
            resolve_path=True,
        ),
    ],
    schema_path: Annotated[
        Path,
        typer.Option(
            "--schema",
            "-s",
            help="Path to invoice.schema.json file",
            exists=True,
            dir_okay=False,
            resolve_path=True,
        ),
    ],
    format_type: FormatOption = OutputFormat.TEXT,
    strict: StrictOption = False,
    quiet: QuietOption = False,
) -> None:
    """Validate invoice data file against schema.

    Validates that the invoice.json file conforms to the structure and
    constraints defined in the invoice.schema.json file.

    Exit Codes:
        0: Success - validation passed
        1: Validation failure - data violates schema constraints
        2: Usage error - files not found or invalid arguments

    Examples:
        rdetoolkit validate invoice raw/invoice.json --schema tasksupport/invoice.schema.json
        rdetoolkit validate invoice invoice.json -s schema.json --format json
    """
    from rdetoolkit.cmd.validate import InvoiceCommand

    try:
        command = InvoiceCommand(invoice_path, schema_path)
        result = command.execute()
        handle_validation_result(result, format_type, strict, quiet)
    except typer.Exit:
        # Re-raise typer.Exit to let Typer handle it properly
        raise
    except FileNotFoundError:
        # Determine which file is missing
        if not invoice_path.exists():
            handle_file_not_found(invoice_path, "Invoice")
        elif not schema_path.exists():
            handle_file_not_found(schema_path, "Schema")
        else:
            raise
    except Exception as e:
        handle_validation_error(e, "invoice validation")


@app.command("metadata")
def metadata(
    metadata_path: Annotated[
        Path,
        typer.Argument(
            help="Path to metadata.json file",
            exists=True,
            dir_okay=False,
            resolve_path=True,
        ),
    ],
    schema_path: Annotated[
        Path,
        typer.Option(
            "--schema",
            "-s",
            help="Path to metadata definition JSON file",
            exists=True,
            dir_okay=False,
            resolve_path=True,
        ),
    ],
    format_type: FormatOption = OutputFormat.TEXT,
    strict: StrictOption = False,
    quiet: QuietOption = False,
) -> None:
    """Validate metadata data file against definition schema.

    Validates that the metadata.json file conforms to the structure
    defined in the metadata definition file.

    Exit Codes:
        0: Success - validation passed
        1: Validation failure - data violates definition constraints
        2: Usage error - files not found or invalid arguments

    Examples:
        rdetoolkit validate metadata raw/metadata.json --schema tasksupport/metadata_def.json
        rdetoolkit validate metadata metadata.json -s metadata_def.json --format json
    """
    from rdetoolkit.cmd.validate import MetadataCommand

    try:
        command = MetadataCommand(metadata_path, schema_path)
        result = command.execute()
        handle_validation_result(result, format_type, strict, quiet)
    except typer.Exit:
        # Re-raise typer.Exit to let Typer handle it properly
        raise
    except FileNotFoundError:
        # Determine which file is missing
        if not metadata_path.exists():
            handle_file_not_found(metadata_path, "Metadata")
        elif not schema_path.exists():
            handle_file_not_found(schema_path, "Metadata definition")
        else:
            raise
    except Exception as e:
        handle_validation_error(e, "metadata validation")


@app.command("all")
def validate_all(
    project_dir: Annotated[
        Optional[Path],
        typer.Argument(
            help="Root directory of RDE project (defaults to current directory)",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = None,
    format_type: FormatOption = OutputFormat.TEXT,
    strict: StrictOption = False,
    quiet: QuietOption = False,
) -> None:
    """Discover and validate all standard RDE files in a project.

    This command automatically discovers and validates files in the standard
    RDE project structure created by the 'init' command:
    - container/data/tasksupport/invoice.schema.json
    - container/data/tasksupport/metadata-def.json
    - templates/tasksupport/invoice.schema.json
    - templates/tasksupport/metadata-def.json
    - input/invoice/invoice.json (with schema)
    - input/metadata/metadata.json (if exists, with schema)

    Exit Codes:
        0: Success - all validations passed
        1: Validation failure - one or more validations failed
        2: Usage error - project directory not found or invalid arguments

    Examples:
        rdetoolkit validate all
        rdetoolkit validate all /path/to/project
        rdetoolkit validate all --format json
        rdetoolkit validate all --strict
    """
    from rdetoolkit.cmd.validate import ValidateAllCommand, create_formatter

    try:
        # Use current directory if project_dir is None
        base_dir = project_dir if project_dir is not None else Path.cwd()
        command = ValidateAllCommand(base_dir)
        results = command.execute()

        if not results:
            # No standard files found
            msg = "No standard RDE files found in project directory."
            typer.echo(msg)
            if not quiet:
                typer.echo("\nExpected file locations:")
                typer.echo("  - container/data/tasksupport/invoice.schema.json")
                typer.echo("  - container/data/tasksupport/metadata-def.json")
                typer.echo("  - templates/tasksupport/invoice.schema.json")
                typer.echo("  - templates/tasksupport/metadata-def.json")
                typer.echo("  - input/invoice/invoice.json")
                typer.echo("  - input/metadata/metadata.json (optional)")
            raise typer.Exit(code=0)

        # Format output based on format type
        if format_type == OutputFormat.JSON:
            # JSON format: array of results
            import json

            json_output = [
                {
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
                for result in results
            ]
            typer.echo(json.dumps(json_output, indent=2, ensure_ascii=False))
        else:
            # Text format: show each file validation
            formatter = create_formatter(format_type.value, quiet=quiet)
            for result in results:
                text_output = formatter.format(result)
                typer.echo(text_output)

        # Determine exit code: 0 only if ALL pass
        any_errors = any(result.has_errors for result in results)
        any_warnings = any(result.has_warnings for result in results)

        if any_errors:
            raise typer.Exit(code=1)
        if strict and any_warnings:
            raise typer.Exit(code=1)

        raise typer.Exit(code=0)

    except typer.Exit:
        # Re-raise typer.Exit to let Typer handle it properly
        raise
    except FileNotFoundError:
        project_path = project_dir if project_dir else Path.cwd()
        handle_file_not_found(project_path, "Project directory")
    except Exception as e:
        handle_validation_error(e, "validate all")
