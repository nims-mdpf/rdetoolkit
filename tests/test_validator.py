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
