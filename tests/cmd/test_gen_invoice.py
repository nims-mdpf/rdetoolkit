from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from rdetoolkit.cmd.gen_invoice import GenerateInvoiceCommand
from rdetoolkit.exceptions import InvoiceSchemaValidationError


class TestGenerateInvoiceCommand:
    """Test suite for GenerateInvoiceCommand.

    EP/BV Test Design:
    ==================

    | Test Case | schema_exists | generator_returns | fill_defaults | required_only | format  | Expected Result               |
    |-----------|---------------|-------------------|---------------|---------------|---------|-------------------------------|
    | EP-001    | True          | valid dict        | True          | False         | pretty  | File created, pretty JSON     |
    | EP-002    | True          | valid dict        | False         | False         | pretty  | File created, no defaults     |
    | EP-003    | True          | valid dict        | True          | True          | pretty  | File created, required only   |
    | EP-004    | True          | valid dict        | True          | False         | compact | File created, compact JSON    |
    | BV-001    | False         | N/A               | True          | False         | pretty  | typer.Abort, FileNotFoundError|
    | BV-002    | True          | raises ValueError | True          | False         | pretty  | typer.Abort, validation error |
    | BV-003    | True          | raises ValidationErr | True       | False         | pretty  | typer.Abort, error msg        |
    | BV-004    | True          | raises Exception  | True          | False         | pretty  | typer.Abort, generic error    |

    Message Display Tests:
    - Info message shown at start
    - Success message shown on completion
    - Error messages shown on failures
    - typer.Abort raised on all errors

    Output Tests:
    - File created at correct path
    - Parent directories created
    - Pretty format has indentation
    - Compact format has no whitespace
    """

    def test_ep001_successful_generation_pretty_format_with_defaults(self, tmp_path: Path) -> None:
        """Test successful generation with pretty format and defaults.

        Test Case: EP-001
        Scenario: Valid schema, pretty format, fill defaults
        """
        # Given: Valid schema and command configured for pretty format
        schema_path = tmp_path / "invoice.schema.json"
        output_path = tmp_path / "output" / "invoice.json"

        cmd = GenerateInvoiceCommand(
            schema_path=schema_path,
            output_path=output_path,
            fill_defaults=True,
            required_only=False,
            output_format="pretty",
        )

        # When: Invoke command with mocked generator
        with patch("rdetoolkit.invoice_generator.generate_invoice_from_schema") as mock_gen:
            mock_gen.return_value = {"datasetId": "test123", "basic": {"dataName": "Test"}}
            cmd.invoke()

        # Then: File created with pretty formatting
        assert output_path.exists()
        content = output_path.read_text()
        assert "    " in content  # Indentation indicates pretty format
        assert '"datasetId"' in content
        assert '"test123"' in content

        # Verify generator was called with correct parameters
        mock_gen.assert_called_once_with(
            schema_path,
            output_path=None,
            fill_defaults=True,
            required_only=False,
        )

    def test_ep002_successful_generation_without_defaults(self, tmp_path: Path) -> None:
        """Test successful generation without default values.

        Test Case: EP-002
        Scenario: Valid schema, no defaults
        """
        # Given: Command configured to not fill defaults
        schema_path = tmp_path / "invoice.schema.json"
        output_path = tmp_path / "invoice.json"

        cmd = GenerateInvoiceCommand(
            schema_path=schema_path,
            output_path=output_path,
            fill_defaults=False,
            required_only=False,
            output_format="pretty",
        )

        # When: Invoke command with mocked generator
        with patch("rdetoolkit.invoice_generator.generate_invoice_from_schema") as mock_gen:
            mock_gen.return_value = {"datasetId": "", "basic": {}}
            cmd.invoke()

        # Then: File created successfully
        assert output_path.exists()

        # Verify generator was called with fill_defaults=False
        mock_gen.assert_called_once_with(
            schema_path,
            output_path=None,
            fill_defaults=False,
            required_only=False,
        )

    def test_ep003_successful_generation_required_only(self, tmp_path: Path) -> None:
        """Test successful generation with required fields only.

        Test Case: EP-003
        Scenario: Valid schema, required fields only
        """
        # Given: Command configured for required fields only
        schema_path = tmp_path / "invoice.schema.json"
        output_path = tmp_path / "invoice.json"

        cmd = GenerateInvoiceCommand(
            schema_path=schema_path,
            output_path=output_path,
            fill_defaults=True,
            required_only=True,
            output_format="pretty",
        )

        # When: Invoke command with mocked generator
        with patch("rdetoolkit.invoice_generator.generate_invoice_from_schema") as mock_gen:
            mock_gen.return_value = {"datasetId": "test", "basic": {}}
            cmd.invoke()

        # Then: File created successfully
        assert output_path.exists()

        # Verify generator was called with required_only=True
        mock_gen.assert_called_once_with(
            schema_path,
            output_path=None,
            fill_defaults=True,
            required_only=True,
        )

    def test_ep004_successful_generation_compact_format(self, tmp_path: Path) -> None:
        """Test successful generation with compact format.

        Test Case: EP-004
        Scenario: Valid schema, compact format
        """
        # Given: Command configured for compact format
        schema_path = tmp_path / "invoice.schema.json"
        output_path = tmp_path / "invoice.json"

        cmd = GenerateInvoiceCommand(
            schema_path=schema_path,
            output_path=output_path,
            fill_defaults=True,
            required_only=False,
            output_format="compact",
        )

        # When: Invoke command with mocked generator
        with patch("rdetoolkit.invoice_generator.generate_invoice_from_schema") as mock_gen:
            mock_gen.return_value = {"datasetId": "test", "basic": {"dataName": "Test"}}
            cmd.invoke()

        # Then: File created with compact formatting (no indentation)
        assert output_path.exists()
        content = output_path.read_text()

        # Verify compact format (no indentation whitespace)
        assert "    " not in content  # No 4-space indentation
        assert '{"datasetId":"test"' in content  # Compact separators

    def test_bv001_schema_not_found_raises_abort(self, tmp_path: Path) -> None:
        """Test that non-existent schema raises typer.Abort.

        Test Case: BV-001
        Scenario: Schema file does not exist
        """
        # Given: Non-existent schema path
        schema_path = tmp_path / "nonexistent.json"
        output_path = tmp_path / "invoice.json"

        cmd = GenerateInvoiceCommand(
            schema_path=schema_path,
            output_path=output_path,
        )

        # When/Then: Invoke raises typer.Abort due to FileNotFoundError
        with patch("rdetoolkit.invoice_generator.generate_invoice_from_schema") as mock_gen:
            mock_gen.side_effect = FileNotFoundError("Schema file not found")

            with pytest.raises(typer.Abort):
                cmd.invoke()

    def test_bv002_invalid_schema_raises_abort(self, tmp_path: Path) -> None:
        """Test that invalid schema structure raises typer.Abort.

        Test Case: BV-002
        Scenario: Schema file has invalid structure
        """
        # Given: Command with valid path
        schema_path = tmp_path / "invoice.schema.json"
        output_path = tmp_path / "invoice.json"

        cmd = GenerateInvoiceCommand(
            schema_path=schema_path,
            output_path=output_path,
        )

        # When/Then: Invoke raises typer.Abort due to ValueError
        with patch("rdetoolkit.invoice_generator.generate_invoice_from_schema") as mock_gen:
            mock_gen.side_effect = ValueError("Invalid schema structure")

            with pytest.raises(typer.Abort):
                cmd.invoke()

    def test_bv003_validation_failure_raises_abort(self, tmp_path: Path) -> None:
        """Test that validation failure raises typer.Abort.

        Test Case: BV-003
        Scenario: Generated invoice fails validation
        """
        # Given: Command with valid configuration
        schema_path = tmp_path / "invoice.schema.json"
        output_path = tmp_path / "invoice.json"

        cmd = GenerateInvoiceCommand(
            schema_path=schema_path,
            output_path=output_path,
        )

        # When/Then: Invoke raises typer.Abort due to validation error
        with patch("rdetoolkit.invoice_generator.generate_invoice_from_schema") as mock_gen:
            mock_gen.side_effect = InvoiceSchemaValidationError("Validation failed")

            with pytest.raises(typer.Abort):
                cmd.invoke()

    def test_bv004_generic_exception_raises_abort(self, tmp_path: Path) -> None:
        """Test that generic exceptions raise typer.Abort.

        Test Case: BV-004
        Scenario: Unexpected error during generation
        """
        # Given: Command with valid configuration
        schema_path = tmp_path / "invoice.schema.json"
        output_path = tmp_path / "invoice.json"

        cmd = GenerateInvoiceCommand(
            schema_path=schema_path,
            output_path=output_path,
        )

        # When/Then: Invoke raises typer.Abort due to generic exception
        with patch("rdetoolkit.invoice_generator.generate_invoice_from_schema") as mock_gen:
            mock_gen.side_effect = RuntimeError("Unexpected error")

            with pytest.raises(typer.Abort):
                cmd.invoke()

    def test_parent_directory_creation(self, tmp_path: Path) -> None:
        """Test that parent directories are created automatically.

        Scenario: Output path has non-existent parent directories
        """
        # Given: Output path with nested non-existent directories
        schema_path = tmp_path / "invoice.schema.json"
        output_path = tmp_path / "deep" / "nested" / "path" / "invoice.json"

        cmd = GenerateInvoiceCommand(
            schema_path=schema_path,
            output_path=output_path,
        )

        # When: Invoke command
        with patch("rdetoolkit.invoice_generator.generate_invoice_from_schema") as mock_gen:
            mock_gen.return_value = {"datasetId": "test", "basic": {}}
            cmd.invoke()

        # Then: Parent directories created and file exists
        assert output_path.parent.exists()
        assert output_path.exists()

    def test_message_display_info(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Test that info messages are displayed correctly.

        Scenario: Verify info message output
        """
        # Given: Command instance
        schema_path = tmp_path / "invoice.schema.json"
        output_path = tmp_path / "invoice.json"

        cmd = GenerateInvoiceCommand(
            schema_path=schema_path,
            output_path=output_path,
        )

        # When: Invoke command
        with patch("rdetoolkit.invoice_generator.generate_invoice_from_schema") as mock_gen:
            mock_gen.return_value = {"datasetId": "test", "basic": {}}
            cmd.invoke()

        # Then: Info message displayed
        captured = capsys.readouterr()
        assert "Generating invoice from schema" in captured.out
        assert str(schema_path) in captured.out

    def test_message_display_success(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Test that success messages are displayed correctly.

        Scenario: Verify success message output
        """
        # Given: Command instance
        schema_path = tmp_path / "invoice.schema.json"
        output_path = tmp_path / "invoice.json"

        cmd = GenerateInvoiceCommand(
            schema_path=schema_path,
            output_path=output_path,
        )

        # When: Invoke command successfully
        with patch("rdetoolkit.invoice_generator.generate_invoice_from_schema") as mock_gen:
            mock_gen.return_value = {"datasetId": "test", "basic": {}}
            cmd.invoke()

        # Then: Success message displayed
        captured = capsys.readouterr()
        assert "Successfully generated" in captured.out
        assert str(output_path) in captured.out

    def test_message_display_error_file_not_found(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Test that error messages are displayed for FileNotFoundError.

        Scenario: Verify error message output for missing schema
        """
        # Given: Command instance
        schema_path = tmp_path / "nonexistent.json"
        output_path = tmp_path / "invoice.json"

        cmd = GenerateInvoiceCommand(
            schema_path=schema_path,
            output_path=output_path,
        )

        # When: Invoke command with missing schema
        with patch("rdetoolkit.invoice_generator.generate_invoice_from_schema") as mock_gen:
            mock_gen.side_effect = FileNotFoundError("Schema not found")

            with pytest.raises(typer.Abort):
                cmd.invoke()

        # Then: Error message displayed
        captured = capsys.readouterr()
        assert "Error!" in captured.out
        assert "Schema file not found" in captured.out
        assert str(schema_path) in captured.out

    def test_message_display_error_validation(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Test that error messages are displayed for validation errors.

        Scenario: Verify error message output for validation failure
        """
        # Given: Command instance
        schema_path = tmp_path / "invoice.schema.json"
        output_path = tmp_path / "invoice.json"

        cmd = GenerateInvoiceCommand(
            schema_path=schema_path,
            output_path=output_path,
        )

        # When: Invoke command with validation error
        with patch("rdetoolkit.invoice_generator.generate_invoice_from_schema") as mock_gen:
            mock_gen.side_effect = InvoiceSchemaValidationError("Validation failed")

            with pytest.raises(typer.Abort):
                cmd.invoke()

        # Then: Error message displayed
        captured = capsys.readouterr()
        assert "Error!" in captured.out
        assert "Generated invoice failed validation" in captured.out

    def test_message_display_error_generic(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Test that error messages are displayed for generic exceptions.

        Scenario: Verify error message output for unexpected errors
        """
        # Given: Command instance
        schema_path = tmp_path / "invoice.schema.json"
        output_path = tmp_path / "invoice.json"

        cmd = GenerateInvoiceCommand(
            schema_path=schema_path,
            output_path=output_path,
        )

        # When: Invoke command with generic error
        with patch("rdetoolkit.invoice_generator.generate_invoice_from_schema") as mock_gen:
            mock_gen.side_effect = RuntimeError("Unexpected error")

            with pytest.raises(typer.Abort):
                cmd.invoke()

        # Then: Error message displayed
        captured = capsys.readouterr()
        assert "Error!" in captured.out
        assert "Failed to generate invoice" in captured.out

    def test_write_invoice_pretty_format_details(self, tmp_path: Path) -> None:
        """Test detailed pretty format output characteristics.

        Scenario: Verify pretty format JSON structure
        """
        # Given: Command with pretty format
        schema_path = tmp_path / "invoice.schema.json"
        output_path = tmp_path / "invoice.json"

        cmd = GenerateInvoiceCommand(
            schema_path=schema_path,
            output_path=output_path,
            output_format="pretty",
        )

        test_data = {
            "datasetId": "test123",
            "basic": {"dataName": "Test Data", "description": "Test"},
            "custom": {"field1": "value1"},
        }

        # When: Write invoice data
        cmd._write_invoice(test_data)

        # Then: Verify pretty format characteristics
        content = output_path.read_text()
        data = json.loads(content)

        # Verify data integrity
        assert data == test_data

        # Verify formatting (indentation)
        lines = content.split("\n")
        assert any(line.startswith("    ") for line in lines)  # 4-space indentation

    def test_write_invoice_compact_format_details(self, tmp_path: Path) -> None:
        """Test detailed compact format output characteristics.

        Scenario: Verify compact format JSON structure
        """
        # Given: Command with compact format
        schema_path = tmp_path / "invoice.schema.json"
        output_path = tmp_path / "invoice.json"

        cmd = GenerateInvoiceCommand(
            schema_path=schema_path,
            output_path=output_path,
            output_format="compact",
        )

        test_data = {
            "datasetId": "test123",
            "basic": {"dataName": "Test Data"},
        }

        # When: Write invoice data
        cmd._write_invoice(test_data)

        # Then: Verify compact format characteristics
        content = output_path.read_text()
        data = json.loads(content)

        # Verify data integrity
        assert data == test_data

        # Verify formatting (no indentation, compact separators)
        assert "\n" not in content or content.count("\n") == 0  # Single line or minimal newlines
        assert ", " not in content  # Compact separator (no space after comma)
        assert ": " not in content  # Compact separator (no space after colon)

    def test_logger_exception_called_on_errors(self, tmp_path: Path) -> None:
        """Test that logger.exception is called for all error types.

        Scenario: Verify logging for error conditions
        """
        # Given: Command instance
        schema_path = tmp_path / "invoice.schema.json"
        output_path = tmp_path / "invoice.json"

        cmd = GenerateInvoiceCommand(
            schema_path=schema_path,
            output_path=output_path,
        )

        # When/Then: Verify logging for FileNotFoundError
        with patch("rdetoolkit.invoice_generator.generate_invoice_from_schema") as mock_gen, patch("rdetoolkit.cmd.gen_invoice.logger") as mock_logger:
            mock_gen.side_effect = FileNotFoundError("Schema not found")

            with pytest.raises(typer.Abort):
                cmd.invoke()

            assert mock_logger.exception.called

        # When/Then: Verify logging for InvoiceSchemaValidationError
        with patch("rdetoolkit.invoice_generator.generate_invoice_from_schema") as mock_gen, patch("rdetoolkit.cmd.gen_invoice.logger") as mock_logger:
            mock_gen.side_effect = InvoiceSchemaValidationError("Validation failed")

            with pytest.raises(typer.Abort):
                cmd.invoke()

            assert mock_logger.exception.called

        # When/Then: Verify logging for generic Exception
        with patch("rdetoolkit.invoice_generator.generate_invoice_from_schema") as mock_gen, patch("rdetoolkit.cmd.gen_invoice.logger") as mock_logger:
            mock_gen.side_effect = RuntimeError("Unexpected error")

            with pytest.raises(typer.Abort):
                cmd.invoke()

            assert mock_logger.exception.called
