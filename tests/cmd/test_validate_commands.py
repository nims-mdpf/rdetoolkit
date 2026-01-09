"""Comprehensive tests for validate commands in rdetoolkit CLI.

This module tests all validation commands:
1. validate invoice-schema <path>
2. validate invoice <invoice.json> --schema <schema.json>
3. validate metadata-def <path>
4. validate metadata <metadata.json> --schema <schema.json>
5. validate all [project_dir]

===============================================================================
TEST DESIGN TABLES
===============================================================================

Equivalence Partitioning Table
| API | Input/State Partition | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| InvoiceSchemaCommand.execute | Valid invoice schema file | Normal path | is_valid=True, no errors | TC-EP-001 |
| InvoiceSchemaCommand.execute | Invalid JSON format (malformed) | Invalid input | is_valid=False, parse errors | TC-EP-002 |
| InvoiceSchemaCommand.execute | Invalid schema structure | Schema violation | is_valid=False, validation errors | TC-EP-003 |
| InvoiceSchemaCommand.execute | Non-existent schema file | Missing file | FileNotFoundError raised | TC-EP-004 |
| InvoiceCommand.execute | Valid invoice + valid schema | Normal path | is_valid=True, no errors | TC-EP-005 |
| InvoiceCommand.execute | Invalid invoice data | Data violation | is_valid=False, validation errors | TC-EP-006 |
| InvoiceCommand.execute | Malformed invoice JSON | Invalid input | is_valid=False, parse errors | TC-EP-007 |
| InvoiceCommand.execute | Non-existent invoice file | Missing file | FileNotFoundError raised | TC-EP-008 |
| InvoiceCommand.execute | Non-existent schema file | Missing dependency | FileNotFoundError raised | TC-EP-009 |
| MetadataDefCommand.execute | Valid metadata definition | Normal path | is_valid=True, no errors | TC-EP-010 |
| MetadataDefCommand.execute | Invalid metadata structure | Schema violation | is_valid=False, validation errors | TC-EP-011 |
| MetadataDefCommand.execute | Malformed JSON | Invalid input | is_valid=False, parse errors | TC-EP-012 |
| MetadataDefCommand.execute | Non-existent file | Missing file | FileNotFoundError raised | TC-EP-013 |
| MetadataCommand.execute | Valid metadata + valid def | Normal path | is_valid=True, no errors | TC-EP-014 |
| MetadataCommand.execute | Invalid metadata data | Data violation | is_valid=False, validation errors | TC-EP-015 |
| MetadataCommand.execute | Non-existent metadata file | Missing file | FileNotFoundError raised | TC-EP-016 |
| MetadataCommand.execute | Non-existent schema file | Missing dependency | FileNotFoundError raised | TC-EP-017 |
| ValidateAllCommand.execute | Valid project with all files | Normal path | All valid results | TC-EP-018 |
| ValidateAllCommand.execute | Project with invalid files | Mixed validation | Some invalid results | TC-EP-019 |
| ValidateAllCommand.execute | Empty project directory | Empty input | Empty result list | TC-EP-020 |
| ValidateAllCommand.execute | Non-existent project dir | Missing directory | FileNotFoundError raised | TC-EP-021 |
| determine_exit_code | valid result, strict=False | Normal success | Exit code 0 | TC-EP-022 |
| determine_exit_code | has errors, strict=False | Validation failure | Exit code 1 | TC-EP-023 |
| determine_exit_code | has warnings, strict=False | Warnings in normal | Exit code 0 | TC-EP-024 |
| determine_exit_code | has warnings, strict=True | Warnings in strict | Exit code 1 | TC-EP-025 |
| TextFormatter.format | Result with errors | Error display | Formatted error text | TC-EP-026 |
| TextFormatter.format | Result with warnings, quiet=False | Warning display | Formatted warnings | TC-EP-027 |
| TextFormatter.format | Result with warnings, quiet=True | Quiet mode | Warnings hidden | TC-EP-028 |
| JsonFormatter.format | Valid result | JSON output | Valid JSON structure | TC-EP-029 |
| JsonFormatter.format | Result with errors/warnings | JSON with issues | Complete JSON output | TC-EP-030 |
| create_formatter | format="text" | Text formatter | TextFormatter instance | TC-EP-031 |
| create_formatter | format="json" | JSON formatter | JsonFormatter instance | TC-EP-032 |
| create_formatter | format="invalid" | Invalid format | ValueError raised | TC-EP-033 |

Boundary Value Table
| API | Boundary | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| InvoiceSchemaCommand.execute | Empty JSON file | Minimum content | Validation error | TC-BV-001 |
| InvoiceSchemaCommand.execute | Schema at path boundary (deep nesting) | Path handling | Correct validation | TC-BV-002 |
| InvoiceCommand.execute | Empty invoice data | Minimum content | Validation error | TC-BV-003 |
| MetadataDefCommand.execute | Minimal valid metadata-def | Minimum valid | is_valid=True | TC-BV-004 |
| MetadataDefCommand.execute | Empty metadata array | Boundary case | is_valid=False | TC-BV-005 |
| ValidateAllCommand.execute | Project with no RDE files | Zero files | Empty results | TC-BV-006 |
| ValidateAllCommand.execute | Project with only schema files | Partial files | Only schema results | TC-BV-007 |
| TextFormatter.format | Zero errors, zero warnings | Empty issues | Success message only | TC-BV-008 |
| determine_exit_code | Zero errors/warnings | Minimum issues | Exit code 0 | TC-BV-009 |

Test execution (local env):
- pytest tests/cmd/test_validate_commands.py -v --cov=rdetoolkit.cmd.validate --cov-branch --cov-report=term-missing
- tox -e py312-module -- tests/cmd/test_validate_commands.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.cmd.validate import (
    InvoiceCommand,
    InvoiceSchemaCommand,
    JsonFormatter,
    MetadataCommand,
    MetadataDefCommand,
    TextFormatter,
    ValidateAllCommand,
    ValidationError,
    ValidationResult,
    ValidationWarning,
    create_formatter,
    determine_exit_code,
)


# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def valid_invoice_schema(tmp_path: Path) -> Path:
    """Create a valid invoice schema JSON file.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to valid invoice schema file
    """
    # Given: A minimal valid invoice schema following InvoiceSchemaJson model
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://rde.nims.go.jp/rde/dataset-templates/test/invoice.schema.json",
        "description": "Test invoice schema",
        "type": "object",
        "required": ["custom"],
        "properties": {
            "custom": {
                "type": "object",
                "label": {"ja": "カスタム", "en": "Custom"},
                "properties": {
                    "testField": {
                        "label": {"ja": "テスト", "en": "Test"},
                        "type": "string",
                    },
                },
                "required": ["testField"],
            },
        },
    }
    schema_path = tmp_path / "invoice.schema.json"
    schema_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    return schema_path


@pytest.fixture
def invalid_invoice_schema_malformed(tmp_path: Path) -> Path:
    """Create a malformed JSON file.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to malformed JSON file
    """
    # Given: A malformed JSON file
    schema_path = tmp_path / "invalid.schema.json"
    schema_path.write_text("{invalid json content", encoding="utf-8")
    return schema_path


@pytest.fixture
def valid_invoice_data(tmp_path: Path) -> Path:
    """Create a valid invoice data file.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to valid invoice data file
    """
    # Given: A valid invoice data file matching system requirements
    invoice = {
        "basic": {
            "dateSubmitted": "2024-01-01",
            "dataOwnerId": "a" * 56,  # 56 alphanumeric characters
            "dataName": "Test Data",
        },
        "datasetId": "test-dataset-001",
        "custom": {"testField": "test value"},
    }
    invoice_path = tmp_path / "invoice.json"
    invoice_path.write_text(json.dumps(invoice, indent=2), encoding="utf-8")
    return invoice_path


@pytest.fixture
def invalid_invoice_data(tmp_path: Path) -> Path:
    """Create an invalid invoice data file (missing required fields).

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to invalid invoice data file
    """
    # Given: An invalid invoice with wrong field type (dataOwnerId should be 56 chars)
    invoice = {
        "basic": {
            "dateSubmitted": "2024-01-01",
            "dataOwnerId": "short",  # Invalid: must be 56 alphanumeric characters
            "dataName": "Test Data",
        },
        "datasetId": "test-dataset-001",
        "custom": {"testField": "test"},
    }
    invoice_path = tmp_path / "invalid_invoice.json"
    invoice_path.write_text(json.dumps(invoice, indent=2), encoding="utf-8")
    return invoice_path


@pytest.fixture
def valid_metadata_def(tmp_path: Path) -> Path:
    """Create a valid metadata definition file.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to valid metadata definition file
    """
    # Given: A minimal valid metadata definition
    metadata_def = {
        "constant": {"author": {"value": "Test Author"}},
        "variable": [{"temperature": {"value": 300, "unit": "K"}}],
    }
    metadata_path = tmp_path / "metadata-def.json"
    metadata_path.write_text(json.dumps(metadata_def, indent=2), encoding="utf-8")
    return metadata_path


@pytest.fixture
def invalid_metadata_def_malformed(tmp_path: Path) -> Path:
    """Create a malformed metadata definition file.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to malformed metadata definition file
    """
    # Given: A malformed JSON file
    metadata_path = tmp_path / "invalid_metadata.json"
    metadata_path.write_text("[{invalid json}", encoding="utf-8")
    return metadata_path


@pytest.fixture
def empty_json_file(tmp_path: Path) -> Path:
    """Create an empty JSON file.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to empty JSON file
    """
    # Given: An empty JSON file
    empty_path = tmp_path / "empty.json"
    empty_path.write_text("{}", encoding="utf-8")
    return empty_path


@pytest.fixture
def rde_project_structure(tmp_path: Path) -> Path:
    """Create a minimal RDE project structure.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to project root directory
    """
    # Given: A standard RDE project structure
    project = tmp_path / "rde_project"
    project.mkdir()

    # Container schemas
    container_tasksupport = project / "container" / "data" / "tasksupport"
    container_tasksupport.mkdir(parents=True)
    (container_tasksupport / "invoice.schema.json").write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "https://rde.nims.go.jp/rde/dataset-templates/test/invoice.schema.json",
                "description": "Test schema",
                "type": "object",
                "required": ["custom"],
                "properties": {
                    "custom": {
                        "type": "object",
                        "label": {"ja": "カスタム", "en": "Custom"},
                        "properties": {},
                        "required": [],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    (container_tasksupport / "metadata-def.json").write_text(
        json.dumps({"constant": {}, "variable": []}),
        encoding="utf-8",
    )

    # Input data
    input_invoice = project / "input" / "invoice"
    input_invoice.mkdir(parents=True)
    (input_invoice / "invoice.json").write_text(
        json.dumps(
            {
                "basic": {
                    "dateSubmitted": "2024-01-01",
                    "dataOwnerId": "a" * 56,
                    "dataName": "Test",
                },
                "datasetId": "test-001",
                "custom": {},
            }
        ),
        encoding="utf-8",
    )

    return project


# ============================================================================
# INVOICE SCHEMA VALIDATION TESTS
# ============================================================================


def test_invoice_schema_valid_file__tc_ep_001(valid_invoice_schema: Path) -> None:
    """Test validation of a valid invoice schema file.

    Given: A valid invoice schema JSON file
    When: Executing InvoiceSchemaCommand
    Then: Validation passes with no errors

    Test ID: TC-EP-001
    """
    # Arrange
    command = InvoiceSchemaCommand(valid_invoice_schema)

    # Act
    result = command.execute()

    # Assert
    assert result.is_valid is True
    assert len(result.errors) == 0
    assert len(result.warnings) == 0
    assert result.target == str(valid_invoice_schema)


def test_invoice_schema_malformed_json__tc_ep_002(invalid_invoice_schema_malformed: Path) -> None:
    """Test validation of a malformed JSON file.

    Given: A malformed JSON file (invalid syntax)
    When: Executing InvoiceSchemaCommand
    Then: Validation fails with errors

    Test ID: TC-EP-002
    """
    # Arrange
    command = InvoiceSchemaCommand(invalid_invoice_schema_malformed)

    # Act
    result = command.execute()

    # Assert
    assert result.is_valid is False
    assert len(result.errors) > 0
    assert result.target == str(invalid_invoice_schema_malformed)


def test_invoice_schema_file_not_found__tc_ep_004(tmp_path: Path) -> None:
    """Test validation with non-existent schema file.

    Given: A path to a non-existent schema file
    When: Executing InvoiceSchemaCommand
    Then: FileNotFoundError is raised

    Test ID: TC-EP-004
    """
    # Arrange
    non_existent = tmp_path / "nonexistent.schema.json"
    command = InvoiceSchemaCommand(non_existent)

    # Act & Assert
    with pytest.raises(FileNotFoundError, match="Schema file not found"):
        command.execute()


def test_invoice_schema_empty_json__tc_bv_001(tmp_path: Path) -> None:
    """Test validation of an empty JSON file.

    Given: An empty JSON file ({}) named invoice.schema.json
    When: Executing InvoiceSchemaCommand
    Then: Validation fails with errors

    Test ID: TC-BV-001
    """
    # Arrange
    empty_schema = tmp_path / "invoice.schema.json"
    empty_schema.write_text("{}", encoding="utf-8")
    command = InvoiceSchemaCommand(empty_schema)

    # Act
    result = command.execute()

    # Assert
    assert result.is_valid is False
    assert len(result.errors) > 0


# ============================================================================
# INVOICE DATA VALIDATION TESTS
# ============================================================================


def test_invoice_valid_data__tc_ep_005(valid_invoice_data: Path, valid_invoice_schema: Path) -> None:
    """Test validation of valid invoice data against schema.

    Given: Valid invoice data and valid schema
    When: Executing InvoiceCommand
    Then: Validation passes with no errors

    Test ID: TC-EP-005
    """
    # Arrange
    command = InvoiceCommand(valid_invoice_data, valid_invoice_schema)

    # Act
    result = command.execute()

    # Assert
    assert result.is_valid is True
    assert len(result.errors) == 0
    assert result.target == str(valid_invoice_data)


def test_invoice_invalid_data__tc_ep_006(invalid_invoice_data: Path, valid_invoice_schema: Path) -> None:
    """Test validation of invalid invoice data (pattern mismatch).

    Given: Invoice data with invalid dataOwnerId pattern (too short)
    When: Executing InvoiceCommand
    Then: Validation fails with errors

    Test ID: TC-EP-006
    """
    # Arrange
    command = InvoiceCommand(invalid_invoice_data, valid_invoice_schema)

    # Act
    result = command.execute()

    # Assert
    assert result.is_valid is False
    assert len(result.errors) > 0
    assert result.target == str(invalid_invoice_data)


def test_invoice_file_not_found__tc_ep_008(tmp_path: Path, valid_invoice_schema: Path) -> None:
    """Test validation with non-existent invoice file.

    Given: A path to a non-existent invoice file
    When: Executing InvoiceCommand
    Then: FileNotFoundError is raised

    Test ID: TC-EP-008
    """
    # Arrange
    non_existent = tmp_path / "nonexistent_invoice.json"
    command = InvoiceCommand(non_existent, valid_invoice_schema)

    # Act & Assert
    with pytest.raises(FileNotFoundError, match="Invoice file not found"):
        command.execute()


def test_invoice_schema_not_found__tc_ep_009(valid_invoice_data: Path, tmp_path: Path) -> None:
    """Test validation with non-existent schema file.

    Given: Valid invoice but non-existent schema
    When: Executing InvoiceCommand
    Then: FileNotFoundError is raised

    Test ID: TC-EP-009
    """
    # Arrange
    non_existent_schema = tmp_path / "nonexistent.schema.json"
    command = InvoiceCommand(valid_invoice_data, non_existent_schema)

    # Act & Assert
    with pytest.raises(FileNotFoundError, match="Schema file not found"):
        command.execute()


def test_invoice_empty_data__tc_bv_003(empty_json_file: Path, valid_invoice_schema: Path) -> None:
    """Test validation of empty invoice data.

    Given: An empty JSON file ({}) as invoice data
    When: Executing InvoiceCommand
    Then: Validation fails with errors

    Test ID: TC-BV-003
    """
    # Arrange
    command = InvoiceCommand(empty_json_file, valid_invoice_schema)

    # Act
    result = command.execute()

    # Assert
    assert result.is_valid is False
    assert len(result.errors) > 0
    assert result.target == str(empty_json_file)


# ============================================================================
# METADATA DEFINITION VALIDATION TESTS
# ============================================================================


def test_metadata_def_valid_file__tc_ep_010(valid_metadata_def: Path) -> None:
    """Test validation of a valid metadata definition file.

    Given: A valid metadata definition JSON file
    When: Executing MetadataDefCommand
    Then: Validation passes with no errors

    Test ID: TC-EP-010
    """
    # Arrange
    command = MetadataDefCommand(valid_metadata_def)

    # Act
    result = command.execute()

    # Assert
    assert result.is_valid is True
    assert len(result.errors) == 0
    assert result.target == str(valid_metadata_def)


def test_metadata_def_malformed_json__tc_ep_012(invalid_metadata_def_malformed: Path) -> None:
    """Test validation of a malformed metadata definition file.

    Given: A malformed JSON file
    When: Executing MetadataDefCommand
    Then: Validation fails with errors

    Test ID: TC-EP-012
    """
    # Arrange
    command = MetadataDefCommand(invalid_metadata_def_malformed)

    # Act
    result = command.execute()

    # Assert
    assert result.is_valid is False
    assert len(result.errors) > 0
    assert result.target == str(invalid_metadata_def_malformed)


def test_metadata_def_file_not_found__tc_ep_013(tmp_path: Path) -> None:
    """Test validation with non-existent metadata definition file.

    Given: A path to a non-existent file
    When: Executing MetadataDefCommand
    Then: FileNotFoundError is raised

    Test ID: TC-EP-013
    """
    # Arrange
    non_existent = tmp_path / "nonexistent_metadata.json"
    command = MetadataDefCommand(non_existent)

    # Act & Assert
    with pytest.raises(FileNotFoundError, match="Metadata definition file not found"):
        command.execute()


def test_metadata_def_minimal_valid__tc_bv_004(tmp_path: Path) -> None:
    """Test validation of minimal valid metadata definition.

    Given: A minimal valid metadata definition with one item
    When: Executing MetadataDefCommand
    Then: Validation passes

    Test ID: TC-BV-004
    """
    # Arrange
    minimal_metadata = tmp_path / "minimal_metadata.json"
    minimal_metadata.write_text(
        json.dumps({"constant": {"test": {"value": "value"}}, "variable": []}),
        encoding="utf-8",
    )
    command = MetadataDefCommand(minimal_metadata)

    # Act
    result = command.execute()

    # Assert
    assert result.is_valid is True


def test_metadata_def_empty_array__tc_bv_005(tmp_path: Path) -> None:
    """Test validation of empty metadata array.

    Given: An empty metadata array []
    When: Executing MetadataDefCommand
    Then: Validation fails with errors

    Test ID: TC-BV-005
    """
    # Arrange
    empty_metadata = tmp_path / "empty_metadata.json"
    empty_metadata.write_text(json.dumps([]), encoding="utf-8")
    command = MetadataDefCommand(empty_metadata)

    # Act
    result = command.execute()

    # Assert
    assert result.is_valid is False
    assert len(result.errors) > 0


# ============================================================================
# METADATA DATA VALIDATION TESTS
# ============================================================================


def test_metadata_valid_data__tc_ep_014(valid_metadata_def: Path) -> None:
    """Test validation of valid metadata data.

    Given: Valid metadata data and definition
    When: Executing MetadataCommand
    Then: Validation passes with no errors

    Test ID: TC-EP-014
    """
    # Arrange
    # Use the same file for both data and definition in this test
    command = MetadataCommand(valid_metadata_def, valid_metadata_def)

    # Act
    result = command.execute()

    # Assert
    assert result.is_valid is True
    assert len(result.errors) == 0


def test_metadata_file_not_found__tc_ep_016(tmp_path: Path, valid_metadata_def: Path) -> None:
    """Test validation with non-existent metadata file.

    Given: A path to a non-existent metadata file
    When: Executing MetadataCommand
    Then: FileNotFoundError is raised

    Test ID: TC-EP-016
    """
    # Arrange
    non_existent = tmp_path / "nonexistent.json"
    command = MetadataCommand(non_existent, valid_metadata_def)

    # Act & Assert
    with pytest.raises(FileNotFoundError, match="Metadata file not found"):
        command.execute()


def test_metadata_schema_not_found__tc_ep_017(valid_metadata_def: Path, tmp_path: Path) -> None:
    """Test validation with non-existent schema file.

    Given: Valid metadata but non-existent definition
    When: Executing MetadataCommand
    Then: FileNotFoundError is raised

    Test ID: TC-EP-017
    """
    # Arrange
    non_existent_schema = tmp_path / "nonexistent_def.json"
    command = MetadataCommand(valid_metadata_def, non_existent_schema)

    # Act & Assert
    with pytest.raises(FileNotFoundError, match="Metadata definition file not found"):
        command.execute()


# ============================================================================
# VALIDATE ALL COMMAND TESTS
# ============================================================================


def test_validate_all_valid_project__tc_ep_018(rde_project_structure: Path) -> None:
    """Test validate all on a valid project.

    Given: A valid RDE project with all files
    When: Executing ValidateAllCommand
    Then: All validations pass

    Test ID: TC-EP-018
    """
    # Arrange
    command = ValidateAllCommand(rde_project_structure)

    # Act
    results = command.execute()

    # Assert
    assert len(results) > 0
    # At least schema files should be validated
    assert all(isinstance(r, ValidationResult) for r in results)


def test_validate_all_empty_project__tc_ep_020(tmp_path: Path) -> None:
    """Test validate all on an empty project.

    Given: An empty directory with no RDE files
    When: Executing ValidateAllCommand
    Then: Returns empty result list

    Test ID: TC-EP-020
    """
    # Arrange
    empty_project = tmp_path / "empty_project"
    empty_project.mkdir()
    command = ValidateAllCommand(empty_project)

    # Act
    results = command.execute()

    # Assert
    assert len(results) == 0


def test_validate_all_project_not_found__tc_ep_021(tmp_path: Path) -> None:
    """Test validate all with non-existent project directory.

    Given: A path to a non-existent directory
    When: Executing ValidateAllCommand
    Then: FileNotFoundError is raised

    Test ID: TC-EP-021
    """
    # Arrange
    non_existent = tmp_path / "nonexistent_project"
    command = ValidateAllCommand(non_existent)

    # Act & Assert
    with pytest.raises(FileNotFoundError, match="Project directory not found"):
        command.execute()


def test_validate_all_no_rde_files__tc_bv_006(tmp_path: Path) -> None:
    """Test validate all on project with no RDE files.

    Given: A directory structure without any RDE files
    When: Executing ValidateAllCommand
    Then: Returns empty results

    Test ID: TC-BV-006
    """
    # Arrange
    project = tmp_path / "non_rde_project"
    project.mkdir()
    (project / "somefile.txt").write_text("not rde", encoding="utf-8")
    command = ValidateAllCommand(project)

    # Act
    results = command.execute()

    # Assert
    assert len(results) == 0


def test_validate_all_only_schema_files__tc_bv_007(tmp_path: Path) -> None:
    """Test validate all on project with only schema files.

    Given: A project with schema files but no data files
    When: Executing ValidateAllCommand
    Then: Only schema validations are returned

    Test ID: TC-BV-007
    """
    # Arrange
    project = tmp_path / "schema_only_project"
    container_tasksupport = project / "container" / "data" / "tasksupport"
    container_tasksupport.mkdir(parents=True)
    (container_tasksupport / "invoice.schema.json").write_text(
        json.dumps(
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": {},
            }
        ),
        encoding="utf-8",
    )
    command = ValidateAllCommand(project)

    # Act
    results = command.execute()

    # Assert
    assert len(results) > 0
    # Should have at least the schema file validated


# ============================================================================
# EXIT CODE DETERMINATION TESTS
# ============================================================================


def test_determine_exit_code_valid_result__tc_ep_022() -> None:
    """Test exit code for valid result in normal mode.

    Given: A valid validation result
    When: Determining exit code with strict=False
    Then: Returns exit code 0

    Test ID: TC-EP-022
    """
    # Arrange
    result = ValidationResult(target="test.json", is_valid=True, errors=[], warnings=[])

    # Act
    exit_code = determine_exit_code(result, strict=False)

    # Assert
    assert exit_code == 0


def test_determine_exit_code_has_errors__tc_ep_023() -> None:
    """Test exit code when validation has errors.

    Given: A validation result with errors
    When: Determining exit code
    Then: Returns exit code 1

    Test ID: TC-EP-023
    """
    # Arrange
    result = ValidationResult(
        target="test.json",
        is_valid=False,
        errors=[ValidationError(field="test", error_type="required", message="Missing field")],
        warnings=[],
    )

    # Act
    exit_code = determine_exit_code(result, strict=False)

    # Assert
    assert exit_code == 1


def test_determine_exit_code_warnings_normal_mode__tc_ep_024() -> None:
    """Test exit code for warnings in normal mode.

    Given: A validation result with warnings only
    When: Determining exit code with strict=False
    Then: Returns exit code 0

    Test ID: TC-EP-024
    """
    # Arrange
    result = ValidationResult(
        target="test.json",
        is_valid=True,
        errors=[],
        warnings=[ValidationWarning(field="test", warning_type="deprecated", message="Deprecated field")],
    )

    # Act
    exit_code = determine_exit_code(result, strict=False)

    # Assert
    assert exit_code == 0


def test_determine_exit_code_warnings_strict_mode__tc_ep_025() -> None:
    """Test exit code for warnings in strict mode.

    Given: A validation result with warnings only
    When: Determining exit code with strict=True
    Then: Returns exit code 1

    Test ID: TC-EP-025
    """
    # Arrange
    result = ValidationResult(
        target="test.json",
        is_valid=True,
        errors=[],
        warnings=[ValidationWarning(field="test", warning_type="deprecated", message="Deprecated field")],
    )

    # Act
    exit_code = determine_exit_code(result, strict=True)

    # Assert
    assert exit_code == 1


def test_determine_exit_code_no_issues__tc_bv_009() -> None:
    """Test exit code with zero errors and warnings.

    Given: A validation result with no errors or warnings
    When: Determining exit code
    Then: Returns exit code 0

    Test ID: TC-BV-009
    """
    # Arrange
    result = ValidationResult(target="test.json", is_valid=True, errors=[], warnings=[])

    # Act
    exit_code = determine_exit_code(result, strict=True)

    # Assert
    assert exit_code == 0


# ============================================================================
# TEXT FORMATTER TESTS
# ============================================================================


def test_text_formatter_with_errors__tc_ep_026() -> None:
    """Test text formatter with validation errors.

    Given: A validation result with errors
    When: Formatting as text
    Then: Errors are displayed in human-readable format

    Test ID: TC-EP-026
    """
    # Arrange
    result = ValidationResult(
        target="test.json",
        is_valid=False,
        errors=[
            ValidationError(field="field1", error_type="required", message="Field is required"),
            ValidationError(field="field2", error_type="type", message="Invalid type"),
        ],
        warnings=[],
    )
    formatter = TextFormatter(quiet=False)

    # Act
    output = formatter.format(result)

    # Assert
    assert "✗ INVALID" in output
    assert "test.json" in output
    assert "Errors:" in output
    assert "field1" in output
    assert "field2" in output
    assert "required" in output
    assert "type" in output


def test_text_formatter_with_warnings_normal__tc_ep_027() -> None:
    """Test text formatter with warnings in normal mode.

    Given: A validation result with warnings
    When: Formatting as text with quiet=False
    Then: Warnings are displayed

    Test ID: TC-EP-027
    """
    # Arrange
    result = ValidationResult(
        target="test.json",
        is_valid=True,
        errors=[],
        warnings=[ValidationWarning(field="field1", warning_type="deprecated", message="Field deprecated")],
    )
    formatter = TextFormatter(quiet=False)

    # Act
    output = formatter.format(result)

    # Assert
    assert "✓ VALID" in output
    assert "Warnings:" in output
    assert "field1" in output
    assert "deprecated" in output


def test_text_formatter_with_warnings_quiet__tc_ep_028() -> None:
    """Test text formatter with warnings in quiet mode.

    Given: A validation result with warnings
    When: Formatting as text with quiet=True
    Then: Warnings are hidden

    Test ID: TC-EP-028
    """
    # Arrange
    result = ValidationResult(
        target="test.json",
        is_valid=True,
        errors=[],
        warnings=[ValidationWarning(field="field1", warning_type="deprecated", message="Field deprecated")],
    )
    formatter = TextFormatter(quiet=True)

    # Act
    output = formatter.format(result)

    # Assert
    assert "✓ VALID" in output
    assert "Warnings:" not in output
    assert "field1" not in output


def test_text_formatter_no_issues__tc_bv_008() -> None:
    """Test text formatter with no errors or warnings.

    Given: A validation result with no issues
    When: Formatting as text
    Then: Only success message is displayed

    Test ID: TC-BV-008
    """
    # Arrange
    result = ValidationResult(target="test.json", is_valid=True, errors=[], warnings=[])
    formatter = TextFormatter(quiet=False)

    # Act
    output = formatter.format(result)

    # Assert
    assert "✓ VALID" in output
    assert "test.json" in output
    assert "Errors:" not in output
    assert "Warnings:" not in output


# ============================================================================
# JSON FORMATTER TESTS
# ============================================================================


def test_json_formatter_valid_result__tc_ep_029() -> None:
    """Test JSON formatter with valid result.

    Given: A valid validation result
    When: Formatting as JSON
    Then: Valid JSON structure is returned

    Test ID: TC-EP-029
    """
    # Arrange
    result = ValidationResult(target="test.json", is_valid=True, errors=[], warnings=[])
    formatter = JsonFormatter()

    # Act
    output = formatter.format(result)

    # Assert
    data = json.loads(output)
    assert data["target"] == "test.json"
    assert data["valid"] is True
    assert data["errors"] == []
    assert data["warnings"] == []


def test_json_formatter_with_issues__tc_ep_030() -> None:
    """Test JSON formatter with errors and warnings.

    Given: A validation result with errors and warnings
    When: Formatting as JSON
    Then: Complete JSON output with all issues

    Test ID: TC-EP-030
    """
    # Arrange
    result = ValidationResult(
        target="test.json",
        is_valid=False,
        errors=[ValidationError(field="field1", error_type="required", message="Required field")],
        warnings=[ValidationWarning(field="field2", warning_type="deprecated", message="Deprecated")],
    )
    formatter = JsonFormatter()

    # Act
    output = formatter.format(result)

    # Assert
    data = json.loads(output)
    assert data["target"] == "test.json"
    assert data["valid"] is False
    assert len(data["errors"]) == 1
    assert data["errors"][0]["field"] == "field1"
    assert data["errors"][0]["type"] == "required"
    assert len(data["warnings"]) == 1
    assert data["warnings"][0]["field"] == "field2"


# ============================================================================
# FORMATTER FACTORY TESTS
# ============================================================================


def test_create_formatter_text__tc_ep_031() -> None:
    """Test factory creates text formatter.

    Given: Format type "text"
    When: Creating formatter
    Then: Returns TextFormatter instance

    Test ID: TC-EP-031
    """
    # Arrange & Act
    formatter = create_formatter("text", quiet=False)

    # Assert
    assert isinstance(formatter, TextFormatter)
    assert formatter.quiet is False


def test_create_formatter_json__tc_ep_032() -> None:
    """Test factory creates JSON formatter.

    Given: Format type "json"
    When: Creating formatter
    Then: Returns JsonFormatter instance

    Test ID: TC-EP-032
    """
    # Arrange & Act
    formatter = create_formatter("json")

    # Assert
    assert isinstance(formatter, JsonFormatter)


def test_create_formatter_invalid__tc_ep_033() -> None:
    """Test factory raises error for invalid format.

    Given: Invalid format type
    When: Creating formatter
    Then: ValueError is raised

    Test ID: TC-EP-033
    """
    # Arrange & Act & Assert
    with pytest.raises(ValueError, match="Unsupported format type"):
        create_formatter("invalid")


# ============================================================================
# ADDITIONAL COVERAGE TESTS
# ============================================================================


def test_validation_result_properties() -> None:
    """Test ValidationResult property methods.

    Given: ValidationResult instances with various error/warning states
    When: Accessing has_errors and has_warnings properties
    Then: Properties return correct boolean values
    """
    # Given: Result with errors
    result_with_errors = ValidationResult(
        target="test.json",
        is_valid=False,
        errors=[ValidationError(field="test", error_type="required", message="Missing")],
        warnings=[],
    )

    # Then: has_errors is True, has_warnings is False
    assert result_with_errors.has_errors is True
    assert result_with_errors.has_warnings is False

    # Given: Result with warnings
    result_with_warnings = ValidationResult(
        target="test.json",
        is_valid=True,
        errors=[],
        warnings=[ValidationWarning(field="test", warning_type="deprecated", message="Deprecated")],
    )

    # Then: has_errors is False, has_warnings is True
    assert result_with_warnings.has_errors is False
    assert result_with_warnings.has_warnings is True

    # Given: Result with neither
    result_clean = ValidationResult(target="test.json", is_valid=True, errors=[], warnings=[])

    # Then: Both are False
    assert result_clean.has_errors is False
    assert result_clean.has_warnings is False


def test_text_formatter_quiet_mode_initialization() -> None:
    """Test TextFormatter initialization with quiet mode.

    Given: TextFormatter with quiet=True
    When: Creating formatter
    Then: Quiet flag is set correctly
    """
    # Arrange & Act
    formatter = TextFormatter(quiet=True)

    # Assert
    assert formatter.quiet is True


def test_invoice_schema_command_string_path() -> None:
    """Test InvoiceSchemaCommand with string path.

    Given: A string path instead of Path object
    When: Creating command
    Then: Path is correctly converted

    Test ID: TC-EP-034 (Additional)
    """
    # Arrange
    path_str = "/tmp/test.json"
    command = InvoiceSchemaCommand(path_str)

    # Assert
    assert command.schema_path == Path(path_str)


def test_invoice_command_string_paths() -> None:
    """Test InvoiceCommand with string paths.

    Given: String paths instead of Path objects
    When: Creating command
    Then: Paths are correctly converted

    Test ID: TC-EP-035 (Additional)
    """
    # Arrange
    invoice_str = "/tmp/invoice.json"
    schema_str = "/tmp/schema.json"
    command = InvoiceCommand(invoice_str, schema_str)

    # Assert
    assert command.invoice_path == Path(invoice_str)
    assert command.schema_path == Path(schema_str)


def test_metadata_def_command_string_path() -> None:
    """Test MetadataDefCommand with string path.

    Given: A string path instead of Path object
    When: Creating command
    Then: Path is correctly converted

    Test ID: TC-EP-036 (Additional)
    """
    # Arrange
    path_str = "/tmp/metadata.json"
    command = MetadataDefCommand(path_str)

    # Assert
    assert command.metadata_def_path == Path(path_str)


def test_metadata_command_string_paths() -> None:
    """Test MetadataCommand with string paths.

    Given: String paths instead of Path objects
    When: Creating command
    Then: Paths are correctly converted

    Test ID: TC-EP-037 (Additional)
    """
    # Arrange
    metadata_str = "/tmp/metadata.json"
    schema_str = "/tmp/schema.json"
    command = MetadataCommand(metadata_str, schema_str)

    # Assert
    assert command.metadata_path == Path(metadata_str)
    assert command.schema_path == Path(schema_str)


def test_validate_all_command_default_project_dir() -> None:
    """Test ValidateAllCommand with default project directory.

    Given: No project_dir specified (None)
    When: Creating command
    Then: Uses current working directory

    Test ID: TC-EP-038 (Additional)
    """
    # Arrange & Act
    command = ValidateAllCommand(project_dir=None)

    # Assert
    assert command.project_dir == Path.cwd()


def test_validate_all_command_string_path() -> None:
    """Test ValidateAllCommand with string path.

    Given: A string path instead of Path object
    When: Creating command
    Then: Path is correctly converted

    Test ID: TC-EP-039 (Additional)
    """
    # Arrange
    path_str = "/tmp/project"
    command = ValidateAllCommand(project_dir=path_str)

    # Assert
    assert command.project_dir == Path(path_str)
