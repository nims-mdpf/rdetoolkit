import pytest
from pathlib import Path
import json

from pydantic import ValidationError

from rdetoolkit.models.invoice_schema import Options
from rdetoolkit.models.invoice_schema import InvoiceSchemaJson, MetaProperty, LangLabels, Properties


@pytest.fixture
def invoice_schema_json_full():
    parent_path = Path(__file__).parent
    test_invoice_schema_json = Path(parent_path, "samplefile", "invoice.schema.full.json")
    with open(test_invoice_schema_json) as f:
        data = json.load(f)
    yield data


@pytest.fixture
def invoice_schema_json_none_sample():
    parent_path = Path(__file__).parent
    test_invoice_schema_json = Path(parent_path, "samplefile", "invoice.schema_none_sample.json")
    with open(test_invoice_schema_json) as f:
        data = json.load(f)
    yield data


@pytest.fixture
def invoice_schema_json_none_custom():
    parent_path = Path(__file__).parent
    test_invoice_schema_json = Path(parent_path, "samplefile", "invoice.schema_none_custom.json")
    with open(test_invoice_schema_json) as f:
        data = json.load(f)
    yield data


@pytest.fixture
def invoice_schema_json_none_generalAttributes():
    parent_path = Path(__file__).parent
    test_invoice_schema_json = Path(parent_path, "samplefile", "invoice.schema_none_generalAttributes.json")
    with open(test_invoice_schema_json) as f:
        data = json.load(f)
    yield data


@pytest.fixture
def invoice_schema_json_none_specificAttributes():
    parent_path = Path(__file__).parent
    test_invoice_schema_json = Path(parent_path, "samplefile", "invoice.schema_none_specificAttributes.json")
    with open(test_invoice_schema_json) as f:
        data = json.load(f)
    yield data


def test_invoice_scheam_json_full(invoice_schema_json_full):
    """Test case when all fields are specified in 'required'."""
    obj = InvoiceSchemaJson(**invoice_schema_json_full)
    assert isinstance(obj, InvoiceSchemaJson)


def test_invoice_scheam_json_none_sample(invoice_schema_json_none_sample):
    """Test case when 'sample' is specified in 'required', but the 'sample' field does not exist."""
    with pytest.raises(ValidationError) as e:
        _ = InvoiceSchemaJson(**invoice_schema_json_none_sample)
    assert "Value error, sample is required but is None" in str(e.value)


def test_invoice_scheam_json_none_custom(invoice_schema_json_none_custom):
    """Test case for creating an InvoiceSchemaJson object with None custom fields."""
    obj = InvoiceSchemaJson(**invoice_schema_json_none_custom)
    assert isinstance(obj, InvoiceSchemaJson)


def test_invoice_scheam_json_none_generalAttributes(invoice_schema_json_none_generalAttributes):
    """Test case for creating an InvoiceSchemaJson object with None generalAttributes."""
    obj = InvoiceSchemaJson(**invoice_schema_json_none_generalAttributes)
    assert isinstance(obj, InvoiceSchemaJson)


def test_invoice_scheam_json_none_specificAttributes(invoice_schema_json_none_specificAttributes):
    """Test case for creating an InvoiceSchemaJson object with None specificAttributes."""
    obj = InvoiceSchemaJson(**invoice_schema_json_none_specificAttributes)
    assert isinstance(obj, InvoiceSchemaJson)


def test_oprions_textare_row():
    with pytest.raises(ValueError) as e:
        _ = Options(widget='textarea')
    assert 'Value error, rows must be set when widget is "textarea"' in str(e.value)


def test_metaproperty_const_validation():
    # Test that a ValueError is raised when const is a different type than value_type
    with pytest.raises(ValueError) as e:
        MetaProperty(label=LangLabels(ja="Test", en="Test"), type="string", const=123)
    assert "Custom Validation: The two objects are of different types." in str(e.value)


def test_metaproperty_maximum_validation():
    # Test that a ValueError is raised when maximum is set but value_type is not integer or number
    with pytest.raises(ValueError) as e:
        MetaProperty(label=LangLabels(ja="Test", en="Test"), type="string", maximum=123)
    assert "Custom Validation: The field must be of type integer or number." in str(e.value)


def test_metaproperty_minlength_validation():
    # Test that a ValueError is raised when minLength is set but value_type is not string
    with pytest.raises(ValueError) as e:
        MetaProperty(label=LangLabels(ja="Test", en="Test"), type="integer", minLength=1)
    assert "Custom Validation: The field must be of type string." in str(e.value)


def test_create_invoice_schema_json():
    obj = InvoiceSchemaJson(
        version="https://json-schema.org/draft/2020-12/schema",
        schema_id="https://rde.nims.go.jp/rde/dataset-templates/dataset_template_custom_sample/invoice.schema.json",
        description="RDEデータセットテンプレートテスト用ファイル",
        type="object",
        properties=Properties(),
    )
    assert isinstance(obj.model_dump_json(), str)


def test_invoice_schema_json_serialization_aliases():
    """Test that InvoiceSchemaJson model correctly applies serialization aliases."""
    obj = InvoiceSchemaJson(
        version="https://json-schema.org/draft/2020-12/schema",
        schema_id="https://rde.nims.go.jp/rde/dataset-templates/dataset_template_custom_sample/invoice.schema.json",
        description="Test description",
        type="object",
        properties=Properties(),
    )

    # Test with by_alias=False (default)
    dumped_without_alias = obj.model_dump(by_alias=False)
    assert "version" in dumped_without_alias
    assert "schema_id" in dumped_without_alias
    assert "value_type" in dumped_without_alias
    assert "$schema" not in dumped_without_alias
    assert "$id" not in dumped_without_alias
    assert "type" not in dumped_without_alias

    # Test with by_alias=True
    dumped_with_alias = obj.model_dump(by_alias=True)
    assert "$schema" in dumped_with_alias
    assert dumped_with_alias["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "$id" in dumped_with_alias
    assert dumped_with_alias["$id"] == "https://rde.nims.go.jp/rde/dataset-templates/dataset_template_custom_sample/invoice.schema.json"
    assert "type" in dumped_with_alias
    assert dumped_with_alias["type"] == "object"

    # Ensure old keys are not present when using aliases
    assert "version" not in dumped_with_alias
    assert "schema_id" not in dumped_with_alias
    assert "value_type" not in dumped_with_alias


def test_find_field_custom_only_hit_returns_alias_dump(invoice_schema_json_full):
    schema = InvoiceSchemaJson(**invoice_schema_json_full)

    result = schema.find_field("sample1", custom_only=True)

    assert isinstance(result, dict)
    assert result.get("type") == "string"
    assert result.get("format") == "date"
    assert result.get("label") == {"ja": "サンプル１", "en": "sample1"}


def test_find_recursive_hit_in_custom(invoice_schema_json_full):
    schema = InvoiceSchemaJson(**invoice_schema_json_full)

    result = schema.find_field("sample3", custom_only=False)

    assert isinstance(result, dict)
    assert result.get("type") == "integer"
    assert result.get("format") is None
    assert result.get("label") == {"ja": "サンプル３", "en": "sample3"}


def test_find_field_not_found_returns_none(invoice_schema_json_full):
    schema = InvoiceSchemaJson(**invoice_schema_json_full)

    result = schema.find_field("dummy1", custom_only=False)

    assert result is None


def test_find_field_custom_only_when_custom_absent_returns_none():
    schema = InvoiceSchemaJson(type="object", properties=Properties())
    result = schema.find_field("sample1", custom_only=True)

    assert result is None
