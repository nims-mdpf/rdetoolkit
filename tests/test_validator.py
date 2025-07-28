import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError
from rdetoolkit.exceptions import (
    InvoiceSchemaValidationError,
    MetadataValidationError,
)
from rdetoolkit.validation import (
    InvoiceValidator,
    MetadataValidator,
    invoice_validate,
    metadata_validate,
)
from jsonschema import validate


@pytest.fixture
def metadata_def_json_file():
    Path("temp").mkdir(parents=True, exist_ok=True)
    json_path = Path("temp").joinpath("test_metadata_def.json")
    json_data = {
        "constant": {"test_meta1": {"value": "value"}, "test_meta2": {"value": 100}, "test_meta3": {"value": True}},
        "variable": [
            {"test_meta1": {"value": "v1"}, "test_meta2": {"value": 200, "unit": "m"}, "test_meta3": {"value": False}},
            {"test_meta1": {"value": "v1"}, "test_meta2": {"value": 200, "unit": "m"}, "test_meta3": {"value": False}},
        ],
    }
    with open(json_path, mode="w", encoding="utf-8") as json_file:
        json.dump(json_data, json_file, ensure_ascii=False, indent=4)

    yield json_path

    if json_path.exists():
        json_path.unlink()
    if Path("temp").exists():
        shutil.rmtree("temp")


@pytest.fixture
def invalid_metadata_def_json_file():
    Path("temp").mkdir(parents=True, exist_ok=True)
    json_path = Path("temp").joinpath("test_metadata_def.json")
    json_data = {"dummy1": {"test_meta1": "value", "test_meta2": 100, "test_meta3": True}, "variable": ["test_meta1", "test_meta2", "test_meta3"]}
    with open(json_path, mode="w", encoding="utf-8") as json_file:
        json.dump(json_data, json_file, ensure_ascii=False, indent=4)

    yield json_path

    if json_path.exists():
        json_path.unlink()
    if Path("temp").exists():
        shutil.rmtree("temp")


def test_metadata_def_json_validation(metadata_def_json_file):
    instance = MetadataValidator()
    obj = instance.validate(path=metadata_def_json_file)
    assert isinstance(obj, dict)


def test_metadata_def_empty_json_validation():
    with pytest.raises(ValueError):
        instance = MetadataValidator()
        _ = instance.validate(json_obj={})


def test_invliad_metadata_def_json_validation(invalid_metadata_def_json_file):
    with pytest.raises(ValidationError):
        instance = MetadataValidator()
        _ = instance.validate(path=invalid_metadata_def_json_file)


def test_none_argments_metadata_def_json_validation():
    with pytest.raises(ValueError) as e:
        instance = MetadataValidator()
        _ = instance.validate()
    assert str(e.value) == "At least one of 'path' or 'json_obj' must be provided"


def test_two_argments_metadata_def_json_validation(invalid_metadata_def_json_file):
    data = {}
    with pytest.raises(ValueError) as e:
        instance = MetadataValidator()
        _ = instance.validate(path=invalid_metadata_def_json_file, json_obj=data)
    assert str(e.value) == "Both 'path' and 'json_obj' cannot be provided at the same time"


def test_metadata_json_validator():
    json_data = {
        "constant": {"test_meta1": {"value": 1}, "test_meta2": {"value": 100}, "test_meta3": {"value": True}},
        "variable": [
            {"test_meta1": {"value": "v1"}, "test_meta2": {"value": 200, "unit": "m"}, "test_meta3": {"value": False}},
            {"test_meta1": {"value": "v1"}, "test_meta2": {"value": 200, "unit": "m"}, "test_meta3": {"value": False}},
        ],
    }

    validator = MetadataValidator()
    try:
        validator.validate(json_obj=json_data)
    except Exception as e:
        pytest.fail(f"Validation raise an {e}")


@pytest.mark.parametrize("case, longchar", [("success", "a" * 1024), ("faild", "a" * 1025)])
def test_char_too_long_metadata_json_validation(case, longchar):
    json_data = {
        "constant": {"test_meta1": {"value": longchar}, "test_meta2": {"value": 100}, "test_meta3": {"value": True}},
        "variable": [
            {"test_meta1": {"value": "v1"}, "test_meta2": {"value": 200, "unit": "m"}, "test_meta3": {"value": False}},
            {"test_meta1": {"value": "v1"}, "test_meta2": {"value": 200, "unit": "m"}, "test_meta3": {"value": False}},
        ],
    }

    instance = MetadataValidator()
    if case == "success":
        obj = instance.validate(json_obj=json_data)
        assert isinstance(obj, dict)
    else:
        with pytest.raises(ValueError) as e:
            obj = instance.validate(json_obj=json_data)
        assert "Value error, Value size exceeds 1024 bytes" in str(e.value)


@pytest.fixture
def validator_instance():
    schema_path = Path(__file__).parent.joinpath("samplefile", "invoice.schema.json")
    yield InvoiceValidator(schema_path)


def test_validate_none_path_obj():
    schema_path = Path(__file__).parent.joinpath("samplefile", "invoice.schema.json")
    iv = InvoiceValidator(schema_path)

    with pytest.raises(ValueError) as e:
        iv.validate()
    assert str(e.value) == "At least one of 'path' or 'obj' must be provided"


def test_validate_both_path_obj():
    schema_path = Path(__file__).parent.joinpath("samplefile", "invoice.schema.json")
    iv = InvoiceValidator(schema_path)

    with pytest.raises(ValueError) as e:
        iv.validate(obj={}, path="dummy")
    assert str(e.value) == "Both 'path' and 'obj' cannot be provided at the same time"


def test_validate_json(validator_instance):
    invoice_path = Path(__file__).parent.joinpath("samplefile", "invoice.json")
    obj = validator_instance.validate(path=invoice_path)
    assert isinstance(obj, dict)


def test_metadata_def_validate(metadata_def_json_file):
    metadata_validate(metadata_def_json_file)


def test_invalid_metadata_def_validate(invalid_metadata_def_json_file):
    exception_msg = """Validation Errors in metadata.json. Please correct the following fields
1. Field: constant
   Type: missing
   Context: Field required
2. Field: variable.0
   Type: dict_type
   Context: Input should be a valid dictionary
3. Field: variable.1
   Type: dict_type
   Context: Input should be a valid dictionary
4. Field: variable.2
   Type: dict_type
   Context: Input should be a valid dictionary
"""
    with pytest.raises(MetadataValidationError) as e:
        metadata_validate(invalid_metadata_def_json_file)
    assert exception_msg == str(e.value)


def test_invoice_path_metadata_def_validate():
    path = "dummy.metadata-def.json"
    with pytest.raises(FileNotFoundError) as e:
        metadata_validate(path)
    assert "The schema and path do not exist" in str(e.value)


def test_invoice_validate():
    invoice_path = Path(__file__).parent.joinpath("samplefile", "invoice.json")
    schema_path = Path(__file__).parent.joinpath("samplefile", "invoice.schema.json")
    invoice_validate(invoice_path, schema_path)


def test_invalid_invoice_validate():
    """Input file: invoice_invalid.json
    "custom": {
        "sample1": null,
        "sample2": null,
        ....
    }
    """
    expect_msg = """Error in validating invoice.json:
1. Field: custom
   Type: required
   Context: 'sample1' is a required property
2. Field: custom
   Type: required
   Context: 'sample2' is a required property
3. Field: custom.sample4
   Type: format
   Context: '20:20:39+00:00' is not a 'time'
"""
    invoice_path = Path(__file__).parent.joinpath("samplefile", "invoice_invalid.json")
    schema_path = Path(__file__).parent.joinpath("samplefile", "invoice.schema.json")
    with pytest.raises(InvoiceSchemaValidationError) as e:
        invoice_validate(invoice_path, schema_path)
    assert expect_msg == str(e.value)


def test_invalid_basic_info_invoice_validate():
    expect_msg = "Error in validating system standard field.\nPlease correct the following fields in invoice.json\nField: basic.dataOwnerId\nType: pattern\nContext: '' does not match '^([0-9a-zA-Z]{56})$'\n"
    invoice_path = Path(__file__).parent.joinpath("samplefile", "invoice_invalid_none_basic.json")
    schema_path = Path(__file__).parent.joinpath("samplefile", "invoice.schema.json")
    with pytest.raises(InvoiceSchemaValidationError) as e:
        invoice_validate(invoice_path, schema_path)
    assert expect_msg == str(e.value)


def test_invalid_sample_anyof_invoice_validate():
    """Test for error if anyOf conditions are not met"""
    expect_msg = "Type: anyOf"
    invoice_path = Path(__file__).parent.joinpath("samplefile", "invoice_invalid_sample_anyof.json")
    schema_path = Path(__file__).parent.joinpath("samplefile", "invoice.schema.json")
    with pytest.raises(InvoiceSchemaValidationError) as e:
        invoice_validate(invoice_path, schema_path)
    assert expect_msg in str(e.value)


def test_invalid_invoice_schema_not_support_value_validate():
    expect_msg = "Type: anyOf"
    invoice_path = Path(__file__).parent.joinpath("samplefile", "invoice_invalid_sample_anyof.json")
    schema_path = Path(__file__).parent.joinpath("samplefile", "invoice.schema.json")
    with pytest.raises(InvoiceSchemaValidationError) as e:
        invoice_validate(invoice_path, schema_path)
    assert expect_msg in str(e.value)


def test_invalid_filepath_invoice_json():
    invoice_path = Path(__file__).parent.joinpath("samplefile", "invoice_invalid_none_basic.json")
    schema_path = "dummy_invoice.schema.json"
    with pytest.raises(FileNotFoundError) as e:
        invoice_validate(invoice_path, schema_path)
    assert "The schema and path do not exist" in str(e.value)

    invoice_path = "dummy_invoice.json"
    schema_path = Path(__file__).parent.joinpath("samplefile", "invoice.schema.json")
    with pytest.raises(FileNotFoundError) as e:
        invoice_validate(invoice_path, schema_path)
    assert "The schema and path do not exist" in str(e.value)


@pytest.mark.parametrize(
    "input_data, expected",
    [
        # シンプルな辞書
        ({"a": 1, "b": None, "c": 3}, {"a": 1, "c": 3}),
        # ネストされた辞書
        ({"a": {"b": None, "c": 3}, "d": None}, {"a": {"c": 3}}),
        # リストの中に辞書
        ({"a": [1, None, 3, {"b": None, "c": 4}]}, {"a": [1, 3, {"c": 4}]}),
        # リスト
        ([1, None, 3, {"a": None, "b": 2}], [1, 3, {"b": 2}]),
        # 辞書の中にリスト
        ({"a": [None, 2, None], "b": None, "c": [1, 2, 3]}, {"a": [2], "c": [1, 2, 3]}),
        # 完全にNoneの辞書
        ({"a": None, "b": None}, {}),
        # 完全にNoneのリスト
        ([None, None, None], []),
        # Noneのない辞書
        ({"a": 1, "b": 2, "c": 3}, {"a": 1, "b": 2, "c": 3}),
        # Noneのないリスト
        ([1, 2, 3], [1, 2, 3]),
    ],
)
def test_remove_none_values(input_data, expected):
    schema_path = Path(__file__).parent.joinpath("samplefile", "invoice.schema.json")
    invoice = InvoiceValidator(schema_path)
    assert invoice._remove_none_values(input_data) == expected


def test_allow_invoice_json():
    invoice_path = Path(__file__).parent.joinpath("samplefile", "invoice_allow_none.json")
    schema_path = Path(__file__).parent.joinpath("samplefile", "invoice.schema.json")
    invoice = InvoiceValidator(schema_path)
    data = invoice.validate(path=invoice_path)
    assert data["custom"]["sample1"] == "2023-01-01"
    assert data["custom"]["sample2"] == 1.0
    assert data["custom"]["sample7"] == "#h1"
    # Noneの値は削除されているため、存在しない
    assert not data["custom"].get("sample3")


def test_validate_required_fields_only():
    """Test that _validate_required_fields_only correctly uses SchemaValidationError.

    This test ensures that the fix for issue #198 (ValidationError.__new__() error)
    doesn't regress by verifying that SchemaValidationError is used correctly.
    """
    # Create a minimal schema with only required fields
    Path("temp").mkdir(parents=True, exist_ok=True)
    schema_path = Path("temp").joinpath("test_schema.json")
    schema_data = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "basic": {"type": "object"},
            "datasetId": {"type": "string"},
            "custom": {"type": "object"}
        },
        "required": ["basic", "datasetId", "custom"]  # Only these fields are allowed
    }

    # Create invoice data with an extra field that's not in required
    invoice_path = Path("temp").joinpath("test_invoice.json")
    invoice_data = {
        "basic": {
            "dataOwnerId": "12345678901234567890123456789012345678901234567890123456",
            "dateSubmitted": "2024-01-01",
            "dataName": "Test Data"
        },
        "datasetId": "test123",
        "custom": {"field1": "value1"},
        "extraField": "This field is not in required list"  # This should trigger error
    }

    try:
        # Write test files
        with open(schema_path, "w") as f:
            json.dump(schema_data, f)
        with open(invoice_path, "w") as f:
            json.dump(invoice_data, f)

        # Test that validation fails with correct error
        with pytest.raises(InvoiceSchemaValidationError) as exc_info:
            invoice_validate(invoice_path, schema_path)

        error_msg = str(exc_info.value)
        # Verify error message contains expected content
        assert "Field 'extraField' is not allowed" in error_msg
        assert "required_fields_only" in error_msg
        assert "Only required fields" in error_msg

    finally:
        # Clean up
        if schema_path.exists():
            schema_path.unlink()
        if invoice_path.exists():
            invoice_path.unlink()
        if Path("temp").exists():
            shutil.rmtree("temp")


def test_restructured_invoice_validation():
    """Test validation with restructured invoice (sampleWhenRestructured pattern)"""
    invoice_path = Path(__file__).parent.joinpath("samplefile", "invoice_restructured.json")
    schema_path = Path(__file__).parent.joinpath("samplefile", "invoice_schema_with_sample.json")

    # Should not raise any exception
    invoice_validate(invoice_path, schema_path)


def test_restructured_sample_pattern_matches():
    """Test that sampleWhenRestructured pattern correctly matches restructured data"""
    schema_path = Path(__file__).parent.joinpath("samplefile", "invoice_schema_with_sample.json")
    invoice_path = Path(__file__).parent.joinpath("samplefile", "invoice_restructured.json")

    validator = InvoiceValidator(schema_path)
    result = validator.validate(path=invoice_path)

    # Verify the restructured data is properly validated
    assert isinstance(result, dict)
    assert result["sample"]["sampleId"] == "019a6150-6f3b-4384-8f12-8f8950f51098"
    # Verify that null values are properly handled (removed by _remove_none_values)
    assert "names" not in result["sample"]
    assert "ownerId" not in result["sample"]


def test_restructured_pattern_with_basic_schema():
    """Test that restructured pattern works with invoice_basic_and_sample.schema_.json"""

    # Load the basic schema directly
    basic_schema_path = Path(__file__).parent.parent / "src" / "rdetoolkit" / "static" / "invoice_basic_and_sample.schema_.json"

    with open(basic_schema_path, "r") as f:
        schema = json.load(f)

    # Load restructured invoice data
    with open(Path(__file__).parent.joinpath("samplefile", "invoice_restructured.json"), "r") as f:
        data = json.load(f)

    # Should validate successfully against the basic schema
    validate(instance=data, schema=schema)


@pytest.mark.parametrize(
    "pattern_name, invoice_file, expected_sample_id, expected_has_names",
    [
        ("sampleWhenAdding", "invoice_sample_adding.json", "", True),
        ("sampleWhenRef", "invoice_sample_ref.json", "019a6150-6f3b-4384-8f12-8f8950f51098", True),
        ("sampleWhenAddingExcelInvoice", "invoice_sample_excel.json", "", True),
        ("sampleWhenRestructured", "invoice_restructured.json", "019a6150-6f3b-4384-8f12-8f8950f51098", False),
    ]
)
def test_all_sample_patterns(pattern_name, invoice_file, expected_sample_id, expected_has_names):
    """Test that all sample patterns work correctly"""
    invoice_path = Path(__file__).parent.joinpath("samplefile", invoice_file)

    # Use a schema that requires sample
    schema_path = Path(__file__).parent.joinpath("samplefile", "invoice_schema_with_sample.json")

    # Should validate successfully
    invoice_validate(invoice_path, schema_path)

    # Verify pattern-specific behavior
    validator = InvoiceValidator(schema_path)
    result = validator.validate(path=invoice_path)

    if expected_sample_id:
        assert result["sample"]["sampleId"] == expected_sample_id

    # For restructured pattern, names should be removed due to null value
    # For other patterns, names should be present
    if expected_has_names:
        assert "names" in result["sample"]
    else:
        assert "names" not in result["sample"]  # Removed by _remove_none_values


def test_invalid_restructured_sample_id():
    """Test that invalid sampleId format fails validation for restructured pattern"""
    Path("temp").mkdir(parents=True, exist_ok=True)

    # Create invalid restructured invoice with bad sampleId format
    invalid_invoice_path = Path("temp").joinpath("invalid_restructured.json")
    invalid_invoice_data = {
        "datasetId": "test-dataset",
        "basic": {
            "dateSubmitted": "2024-01-15",
            "dataOwnerId": "051d5eab8a6a8bea98f07bbdb6f7eac8623c54783930316135393066",
            "dataName": "Invalid Test Data"
        },
        "sample": {
            "sampleId": "invalid-uuid-format",  # Invalid UUID format
            "names": None,
            "ownerId": None
        }
    }

    schema_path = Path(__file__).parent.joinpath("samplefile", "invoice_schema_with_sample.json")

    try:
        with open(invalid_invoice_path, "w") as f:
            json.dump(invalid_invoice_data, f)

        # Should raise validation error due to invalid UUID pattern
        with pytest.raises(InvoiceSchemaValidationError) as exc_info:
            invoice_validate(invalid_invoice_path, schema_path)

        # Verify error is related to pattern validation
        error_msg = str(exc_info.value)
        assert "pattern" in error_msg.lower() or "anyof" in error_msg.lower()

    finally:
        if invalid_invoice_path.exists():
            invalid_invoice_path.unlink()
        if Path("temp").exists():
            shutil.rmtree("temp")


def test_existing_patterns_still_work_after_restructured_addition():
    """Test that existing sample patterns still work after adding sampleWhenRestructured"""
    # Test with existing sample files that should still validate
    existing_test_cases = [
        ("invoice.json", "invoice.schema.json"),
        ("invoice_allow_none.json", "invoice.schema.json"),
    ]

    for invoice_file, schema_file in existing_test_cases:
        invoice_path = Path(__file__).parent.joinpath("samplefile", invoice_file)
        schema_path = Path(__file__).parent.joinpath("samplefile", schema_file)

        # Should still validate successfully
        invoice_validate(invoice_path, schema_path)
