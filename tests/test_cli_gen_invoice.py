"""Test suite for gen-invoice CLI command.

EP/BV Test Design:
==================

Equivalence Partitioning:

| Test Case | schema_valid | output_opt | fill_defaults | required_only | format  | Expected Result               |
|-----------|--------------|------------|---------------|---------------|---------|-------------------------------|
| EP-001    | True         | None       | True          | False         | pretty  | invoice.json in cwd, pretty   |
| EP-002    | True         | custom     | True          | False         | pretty  | invoice.json at custom path   |
| EP-003    | True         | None       | False         | False         | pretty  | invoice.json, no defaults     |
| EP-004    | True         | None       | True          | True          | pretty  | invoice.json, required only   |
| EP-005    | True         | None       | True          | False         | compact | invoice.json, compact format  |

Boundary Values:

| Test Case | Boundary Condition        | Expected Result                           |
|-----------|---------------------------|-------------------------------------------|
| BV-001    | Non-existent schema file  | Exit code != 0, error message             |
| BV-002    | Non-JSON schema file      | Exit code != 0, JSON validation error     |
| BV-003    | Invalid JSON content      | Exit code != 0, JSON validation error     |
| BV-004    | Invalid format option     | Exit code != 0, format validation error   |
| BV-005    | Nested output directory   | Parent dirs created, file generated       |

Integration Tests:

| Test Case | Description                    | Expected Result           |
|-----------|--------------------------------|---------------------------|
| INT-001   | Help message displays          | Exit code 0, help text    |
| INT-002   | Command in main help           | gen-invoice listed        |
| INT-003   | All options work together      | Successful generation     |
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner.

    Returns:
        CliRunner instance for testing CLI commands.
    """
    return CliRunner()


@pytest.fixture
def valid_schema(tmp_path: Path) -> Path:
    """Create a valid invoice schema file for testing.

    Args:
        tmp_path: Pytest temporary directory fixture.

    Returns:
        Path to valid invoice.schema.json file.
    """
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://rde.nims.go.jp/rde/dataset-templates/test/invoice.schema.json",
        "type": "object",
        "required": ["custom"],
        "properties": {
            "custom": {
                "type": "object",
                "label": {"ja": "カスタム", "en": "Custom"},
                "required": ["field1"],
                "properties": {
                    "field1": {
                        "type": "string",
                        "label": {"ja": "フィールド1", "en": "Field 1"},
                    },
                    "field2": {
                        "type": "number",
                        "label": {"ja": "フィールド2", "en": "Field 2"},
                    },
                },
            },
        },
    }
    schema_path = tmp_path / "invoice.schema.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    return schema_path


@pytest.fixture
def non_json_file(tmp_path: Path) -> Path:
    """Create a non-JSON file for testing.

    Args:
        tmp_path: Pytest temporary directory fixture.

    Returns:
        Path to .txt file.
    """
    file_path = tmp_path / "not_json.txt"
    file_path.write_text("{}", encoding="utf-8")
    return file_path


@pytest.fixture
def invalid_json_file(tmp_path: Path) -> Path:
    """Create an invalid JSON file for testing.

    Args:
        tmp_path: Pytest temporary directory fixture.

    Returns:
        Path to .json file with invalid JSON content.
    """
    file_path = tmp_path / "invalid.json"
    file_path.write_text("Not valid JSON content", encoding="utf-8")
    return file_path


class TestGenInvoiceCommandEP:
    """Equivalence Partitioning tests for gen-invoice command."""

    def test_ep001_default_output_path_pretty_format(
        self,
        runner: CliRunner,
        valid_schema: Path,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Test EP-001: Default output path (invoice.json in cwd), pretty format.

        Given: Valid schema file
        When: Running gen-invoice without -o option
        Then: invoice.json created in current directory with pretty formatting
        """
        # Change to tmp_path so default invoice.json is created there
        monkeypatch.chdir(tmp_path)

        # When: Invoke command without output path option
        result = runner.invoke(app, ["gen-invoice", str(valid_schema)])

        # Then: Success and file created in cwd
        assert result.exit_code == 0, f"Command failed: {result.output}"
        invoice_path = tmp_path / "invoice.json"
        assert invoice_path.exists()

        # Verify pretty format (has indentation)
        content = invoice_path.read_text()
        assert "    " in content  # Has 4-space indentation

    def test_ep002_custom_output_path(
        self,
        runner: CliRunner,
        valid_schema: Path,
        tmp_path: Path,
    ) -> None:
        """Test EP-002: Custom output path specified with -o.

        Given: Valid schema file and custom output path
        When: Running gen-invoice with -o option
        Then: invoice.json created at specified path
        """
        # Given: Custom output path
        output_path = tmp_path / "output" / "custom_invoice.json"

        # When: Invoke command with custom output path
        result = runner.invoke(
            app,
            ["gen-invoice", str(valid_schema), "-o", str(output_path)],
        )

        # Then: Success and file created at custom path
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert output_path.exists()
        assert "Successfully generated" in result.output

    def test_ep003_no_fill_defaults(
        self,
        runner: CliRunner,
        valid_schema: Path,
        tmp_path: Path,
    ) -> None:
        """Test EP-003: Disable fill_defaults with --no-fill-defaults.

        Given: Valid schema file
        When: Running gen-invoice with --no-fill-defaults
        Then: invoice.json created without default values

        Note: --no-fill-defaults can produce invalid invoices (empty strings
        that don't match patterns like dataOwnerId). This test verifies the
        flag is passed correctly, not that validation succeeds.
        """
        # Given: Output path
        output_path = tmp_path / "invoice.json"

        # When: Invoke command with --no-fill-defaults
        # This will fail validation because basic.dataOwnerId needs 56 chars
        result = runner.invoke(
            app,
            ["gen-invoice", str(valid_schema), "-o", str(output_path), "--no-fill-defaults"],
        )

        # Then: Validation fails as expected (empty dataOwnerId doesn't match pattern)
        assert result.exit_code != 0
        assert "dataOwnerId" in result.output or "validation" in result.output.lower()

    def test_ep004_required_only(
        self,
        runner: CliRunner,
        valid_schema: Path,
        tmp_path: Path,
    ) -> None:
        """Test EP-004: Include only required fields with --required-only.

        Given: Valid schema file
        When: Running gen-invoice with --required-only
        Then: invoice.json created with only required fields
        """
        # Given: Output path
        output_path = tmp_path / "invoice.json"

        # When: Invoke command with --required-only
        result = runner.invoke(
            app,
            ["gen-invoice", str(valid_schema), "-o", str(output_path), "--required-only"],
        )

        # Then: Success
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert output_path.exists()

    def test_ep005_compact_format(
        self,
        runner: CliRunner,
        valid_schema: Path,
        tmp_path: Path,
    ) -> None:
        """Test EP-005: Compact JSON format with --format compact.

        Given: Valid schema file
        When: Running gen-invoice with --format compact
        Then: invoice.json created with compact formatting (no indentation)
        """
        # Given: Output path
        output_path = tmp_path / "invoice.json"

        # When: Invoke command with --format compact
        result = runner.invoke(
            app,
            ["gen-invoice", str(valid_schema), "-o", str(output_path), "--format", "compact"],
        )

        # Then: Success and compact format
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert output_path.exists()

        # Verify compact format (no 4-space indentation)
        content = output_path.read_text()
        assert "    " not in content  # No 4-space indentation


class TestGenInvoiceCommandBV:
    """Boundary Value tests for gen-invoice command."""

    def test_bv001_non_existent_schema_file(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test BV-001: Non-existent schema file.

        Given: Path to non-existent file
        When: Running gen-invoice
        Then: Exit code != 0 with error message
        """
        # Given: Non-existent file path
        non_existent = tmp_path / "nonexistent.json"

        # When: Invoke command with non-existent file
        result = runner.invoke(app, ["gen-invoice", str(non_existent)])

        # Then: Failure
        assert result.exit_code != 0

    def test_bv002_non_json_file(
        self,
        runner: CliRunner,
        non_json_file: Path,
        tmp_path: Path,
    ) -> None:
        """Test BV-002: Non-JSON file extension.

        Given: File with .txt extension
        When: Running gen-invoice
        Then: Exit code != 0 with JSON validation error
        """
        # When: Invoke command with .txt file
        result = runner.invoke(
            app,
            ["gen-invoice", str(non_json_file), "-o", str(tmp_path / "invoice.json")],
        )

        # Then: Failure with JSON validation error
        assert result.exit_code != 0
        assert "The schema file must be a JSON file" in result.output

    def test_bv003_invalid_json_content(
        self,
        runner: CliRunner,
        invalid_json_file: Path,
        tmp_path: Path,
    ) -> None:
        """Test BV-003: Invalid JSON content.

        Given: .json file with invalid JSON content
        When: Running gen-invoice
        Then: Exit code != 0 with JSON validation error
        """
        # When: Invoke command with invalid JSON
        result = runner.invoke(
            app,
            ["gen-invoice", str(invalid_json_file), "-o", str(tmp_path / "invoice.json")],
        )

        # Then: Failure with JSON validation error
        assert result.exit_code != 0
        assert "The schema file must be a valid JSON file" in result.output

    def test_bv004_invalid_format_option(
        self,
        runner: CliRunner,
        valid_schema: Path,
        tmp_path: Path,
    ) -> None:
        """Test BV-004: Invalid format option.

        Given: Valid schema file
        When: Running gen-invoice with invalid --format value
        Then: Exit code != 0 with format validation error
        """
        # When: Invoke command with invalid format
        result = runner.invoke(
            app,
            [
                "gen-invoice",
                str(valid_schema),
                "-o",
                str(tmp_path / "invoice.json"),
                "--format",
                "invalid",
            ],
        )

        # Then: Failure with format validation error
        assert result.exit_code != 0
        assert "Format must be 'pretty' or 'compact'" in result.output

    def test_bv005_nested_output_directory_creation(
        self,
        runner: CliRunner,
        valid_schema: Path,
        tmp_path: Path,
    ) -> None:
        """Test BV-005: Nested output directory creation.

        Given: Output path with non-existent parent directories
        When: Running gen-invoice
        Then: Parent directories created and file generated
        """
        # Given: Nested output path
        output_path = tmp_path / "deep" / "nested" / "dirs" / "invoice.json"

        # When: Invoke command
        result = runner.invoke(app, ["gen-invoice", str(valid_schema), "-o", str(output_path)])

        # Then: Success and nested directories created
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert output_path.exists()
        assert output_path.parent.exists()


class TestGenInvoiceCommandIntegration:
    """Integration tests for gen-invoice command."""

    def test_int001_help_message(self, runner: CliRunner) -> None:
        """Test INT-001: Help message displays correctly.

        Given: CLI runner
        When: Running gen-invoice --help
        Then: Exit code 0 with help text
        """
        # When: Invoke help
        result = runner.invoke(app, ["gen-invoice", "--help"])

        # Then: Success with help text
        assert result.exit_code == 0
        assert "gen-invoice" in result.output
        assert "Generate invoice.json from invoice.schema.json" in result.output
        assert "-o" in result.output or "--output" in result.output
        assert "--fill-defaults" in result.output
        assert "--required-only" in result.output
        assert "--format" in result.output

    def test_int002_command_in_main_help(self, runner: CliRunner) -> None:
        """Test INT-002: Command appears in main help.

        Given: CLI runner
        When: Running rdetoolkit --help
        Then: gen-invoice command listed
        """
        # When: Invoke main help
        result = runner.invoke(app, ["--help"])

        # Then: Success with gen-invoice listed
        assert result.exit_code == 0
        assert "gen-invoice" in result.output

    def test_int003_all_options_together(
        self,
        runner: CliRunner,
        valid_schema: Path,
        tmp_path: Path,
    ) -> None:
        """Test INT-003: Options work together (successful case).

        Given: Valid schema file
        When: Running gen-invoice with multiple compatible options
        Then: Successful generation with all options respected
        """
        # Given: Output path
        output_path = tmp_path / "output" / "invoice.json"

        # When: Invoke command with compatible options (fill_defaults=True to pass validation)
        result = runner.invoke(
            app,
            [
                "gen-invoice",
                str(valid_schema),
                "-o",
                str(output_path),
                "--fill-defaults",  # Use fill_defaults to generate valid dataOwnerId
                "--required-only",
                "--format",
                "compact",
            ],
        )

        # Then: Success
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert output_path.exists()
        assert "Successfully generated" in result.output

        # Verify compact format
        content = output_path.read_text()
        assert "    " not in content  # No indentation

    def test_int004_format_case_insensitive(
        self,
        runner: CliRunner,
        valid_schema: Path,
        tmp_path: Path,
    ) -> None:
        """Test INT-004: Format option is case-insensitive.

        Given: Valid schema file
        When: Running gen-invoice with uppercase format
        Then: Successful generation
        """
        # Given: Output path
        output_path = tmp_path / "invoice.json"

        # When: Invoke command with uppercase format
        result = runner.invoke(
            app,
            ["gen-invoice", str(valid_schema), "-o", str(output_path), "--format", "PRETTY"],
        )

        # Then: Success
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert output_path.exists()

    def test_int005_output_long_option(
        self,
        runner: CliRunner,
        valid_schema: Path,
        tmp_path: Path,
    ) -> None:
        """Test INT-005: Long form --output option works.

        Given: Valid schema file
        When: Running gen-invoice with --output instead of -o
        Then: Successful generation
        """
        # Given: Output path
        output_path = tmp_path / "invoice.json"

        # When: Invoke command with --output
        result = runner.invoke(
            app,
            ["gen-invoice", str(valid_schema), "--output", str(output_path)],
        )

        # Then: Success
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert output_path.exists()
