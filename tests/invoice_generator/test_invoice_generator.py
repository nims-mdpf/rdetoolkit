from __future__ import annotations

import json

import pytest

from rdetoolkit.exceptions import InvoiceSchemaValidationError
from rdetoolkit.invoice_generator import (
    _generate_basic_section,
    _get_default_value_for_type,
    _load_and_validate_schema,
    _process_custom_field,
    _process_sample_field,
    _validate_generated_invoice,
    generate_invoice_from_schema,
)


class TestGetDefaultValueForType:
    """Test suite for _get_default_value_for_type function.

    EP/BV Test Design:
    ==================

    | Test Case | value_type | schema_default | schema_examples | fill_defaults | Expected Result |
    |-----------|------------|----------------|-----------------|---------------|-----------------|
    | EP-001    | "string"   | None           | None            | True          | ""              |
    | EP-002    | "number"   | None           | None            | True          | 0.0             |
    | EP-003    | "integer"  | None           | None            | True          | 0               |
    | EP-004    | "boolean"  | None           | None            | True          | False           |
    | EP-005    | "array"    | None           | None            | True          | []              |
    | EP-006    | "object"   | None           | None            | True          | {}              |
    | EP-007    | "string"   | "custom"       | None            | True          | "custom"        |
    | EP-008    | "string"   | None           | ["example"]     | True          | "example"       |
    | EP-009    | "string"   | "default"      | ["example"]     | True          | "default"       |
    | EP-010    | "string"   | None           | None            | False         | None            |
    | EP-011    | "string"   | "custom"       | None            | False         | "custom"        |
    | EP-012    | "number"   | 5.5            | None            | True          | 5.5             |
    | BV-001    | "unknown"  | None           | None            | True          | None            |
    | BV-002    | "string"   | None           | []              | True          | ""              |
    """

    def test_ep001_string_type_with_fill_defaults(self):
        """Given: Type is "string", no default or examples, fill_defaults=True.

        When: Getting default value.
        """
        result = _get_default_value_for_type("string", fill_defaults=True)
        # Then: Returns empty string
        assert result == ""

    def test_ep002_number_type_with_fill_defaults(self):
        """Given: Type is "number", no default or examples, fill_defaults=True.

        When: Getting default value.
        """
        result = _get_default_value_for_type("number", fill_defaults=True)
        # Then: Returns 0.0
        assert result == 0.0

    def test_ep003_integer_type_with_fill_defaults(self):
        """Given: Type is "integer", no default or examples, fill_defaults=True.

        When: Getting default value.
        """
        result = _get_default_value_for_type("integer", fill_defaults=True)
        # Then: Returns 0
        assert result == 0

    def test_ep004_boolean_type_with_fill_defaults(self):
        """Given: Type is "boolean", no default or examples, fill_defaults=True.

        When: Getting default value.
        """
        result = _get_default_value_for_type("boolean", fill_defaults=True)
        # Then: Returns False
        assert result is False

    def test_ep005_array_type_with_fill_defaults(self):
        """Given: Type is "array", no default or examples, fill_defaults=True.

        When: Getting default value.
        """
        result = _get_default_value_for_type("array", fill_defaults=True)
        # Then: Returns empty list
        assert result == []

    def test_ep006_object_type_with_fill_defaults(self):
        """Given: Type is "object", no default or examples, fill_defaults=True.

        When: Getting default value.
        """
        result = _get_default_value_for_type("object", fill_defaults=True)
        # Then: Returns empty dict
        assert result == {}

    def test_ep007_schema_default_provided(self):
        """Given: Type is "string", schema_default="custom".

        When: Getting default value.
        """
        result = _get_default_value_for_type("string", schema_default="custom", fill_defaults=True)
        # Then: Returns schema_default (priority 1)
        assert result == "custom"

    def test_ep008_schema_examples_provided(self):
        """Given: Type is "string", schema_examples=["example"].

        When: Getting default value.
        """
        result = _get_default_value_for_type("string", schema_examples=["example"], fill_defaults=True)
        # Then: Returns first example (priority 2)
        assert result == "example"

    def test_ep009_both_default_and_examples_provided(self):
        """Given: Both schema_default and schema_examples provided.

        When: Getting default value.
        """
        result = _get_default_value_for_type("string", schema_default="default", schema_examples=["example"], fill_defaults=True)
        # Then: Returns schema_default (higher priority)
        assert result == "default"

    def test_ep010_fill_defaults_false_no_default(self):
        """Given: Type is "string", fill_defaults=False, no default.

        When: Getting default value.
        """
        result = _get_default_value_for_type("string", fill_defaults=False)
        # Then: Returns None
        assert result is None

    def test_ep011_fill_defaults_false_with_schema_default(self):
        """Given: Type is "string", fill_defaults=False, schema_default="custom".

        When: Getting default value.
        """
        result = _get_default_value_for_type("string", schema_default="custom", fill_defaults=False)
        # Then: Returns schema_default (still honored)
        assert result == "custom"

    def test_ep012_number_with_schema_default(self):
        """Given: Type is "number", schema_default=5.5.

        When: Getting default value.
        """
        result = _get_default_value_for_type("number", schema_default=5.5, fill_defaults=True)
        # Then: Returns schema_default
        assert result == 5.5

    def test_bv001_unknown_type(self):
        """Given: Type is "unknown", fill_defaults=True.

        When: Getting default value.
        """
        result = _get_default_value_for_type("unknown", fill_defaults=True)
        # Then: Returns None (no matching type)
        assert result is None

    def test_bv002_empty_examples_list(self):
        """Given: Type is "string", schema_examples=[] (empty list).

        When: Getting default value.
        """
        result = _get_default_value_for_type("string", schema_examples=[], fill_defaults=True)
        # Then: Returns type-based default (empty string)
        assert result == ""


class TestGenerateBasicSection:
    """Test suite for _generate_basic_section function.

    EP/BV Test Design:
    ==================

    | Test Case | fill_defaults | Expected Fields |
    |-----------|---------------|-----------------|
    | EP-001    | True          | All basic fields with defaults |
    | EP-002    | False         | All basic fields with defaults |
    """

    def test_ep001_with_fill_defaults_true(self):
        """Given: fill_defaults=True.

        When: Generating basic section.
        """
        result = _generate_basic_section(fill_defaults=True)
        # Then: Returns dict with all basic fields
        assert isinstance(result, dict)
        assert "dateSubmitted" in result
        assert "dataOwnerId" in result
        assert "dataName" in result
        assert "instrumentId" in result
        assert "experimentId" in result
        assert "description" in result
        assert result["dateSubmitted"] == ""
        assert result["dataOwnerId"] == "0" * 56  # 56-character placeholder
        assert result["dataName"] == ""
        assert result["instrumentId"] is None
        assert result["experimentId"] is None
        assert result["description"] is None

    def test_ep002_with_fill_defaults_false(self):
        """Given: fill_defaults=False.

        When: Generating basic section.
        """
        result = _generate_basic_section(fill_defaults=False)
        # Then: Returns same structure (basic section always has same fields)
        assert isinstance(result, dict)
        assert "dateSubmitted" in result
        assert "dataOwnerId" in result
        assert "dataName" in result
        assert result["instrumentId"] is None


class TestLoadAndValidateSchema:
    """Test suite for _load_and_validate_schema function.

    EP/BV Test Design:
    ==================

    | Test Case | schema_path | Expected Result |
    |-----------|-------------|-----------------|
    | EP-001    | valid schema file | InvoiceSchemaJson instance |
    | BV-001    | non-existent file | FileNotFoundError |
    | BV-002    | invalid JSON | ValueError |
    | BV-003    | invalid schema structure | ValueError |
    """

    def test_ep001_valid_schema_file(self, tmp_path):
        """Given: Valid schema file."""
        schema_path = tmp_path / "invoice.schema.json"
        schema_data = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://rde.nims.go.jp/test/invoice.schema.json",
            "description": "Test schema",
            "type": "object",
            "required": ["custom"],
            "properties": {
                "custom": {
                    "type": "object",
                    "label": {"ja": "固有情報", "en": "Custom"},
                    "required": ["field1"],
                    "properties": {
                        "field1": {
                            "label": {"ja": "フィールド１", "en": "field1"},
                            "type": "string",
                        },
                    },
                },
            },
        }
        with open(schema_path, "w") as f:
            json.dump(schema_data, f)

        # When: Loading and validating schema
        result = _load_and_validate_schema(schema_path)

        # Then: Returns InvoiceSchemaJson instance
        assert result is not None
        assert hasattr(result, "properties")
        assert result.properties.custom is not None

    def test_bv001_non_existent_file(self, tmp_path):
        """Given: Non-existent file path."""
        schema_path = tmp_path / "does_not_exist.json"

        # When/Then: Loading raises FileNotFoundError
        with pytest.raises(FileNotFoundError, match="Schema file not found"):
            _load_and_validate_schema(schema_path)

    def test_bv002_invalid_json(self, tmp_path):
        """Given: File with invalid JSON."""
        schema_path = tmp_path / "invalid.json"
        with open(schema_path, "w") as f:
            f.write("{invalid json}")

        # When/Then: Loading raises ValueError
        with pytest.raises(ValueError, match="Failed to read schema file"):
            _load_and_validate_schema(schema_path)

    def test_bv003_invalid_schema_structure(self, tmp_path):
        """Given: File with invalid schema structure."""
        schema_path = tmp_path / "invalid_schema.json"
        schema_data = {
            "invalid": "schema",
            "missing": "required fields",
        }
        with open(schema_path, "w") as f:
            json.dump(schema_data, f)

        # When/Then: Loading raises ValueError
        with pytest.raises(ValueError, match="Invalid schema structure"):
            _load_and_validate_schema(schema_path)


class TestProcessCustomField:
    """Test suite for _process_custom_field function.

    EP/BV Test Design:
    ==================

    | Test Case | fill_defaults | required_only | num_fields | Expected Result |
    |-----------|---------------|---------------|------------|-----------------|
    | EP-001    | True          | False         | 3          | All fields with defaults |
    | EP-002    | False         | False         | 3          | All fields with None |
    | EP-003    | True          | True          | 2 required | Only required fields |
    """

    def test_ep001_fill_defaults_all_fields(self, tmp_path):
        """Given: Valid schema with custom fields, fill_defaults=True, required_only=False."""
        schema_path = tmp_path / "invoice.schema.json"
        schema_data = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://rde.nims.go.jp/test/invoice.schema.json",
            "description": "Test schema",
            "type": "object",
            "required": ["custom"],
            "properties": {
                "custom": {
                    "type": "object",
                    "label": {"ja": "固有情報", "en": "Custom"},
                    "required": ["field1"],
                    "properties": {
                        "field1": {"label": {"ja": "フィールド１", "en": "field1"}, "type": "string"},
                        "field2": {"label": {"ja": "フィールド２", "en": "field2"}, "type": "number"},
                        "field3": {"label": {"ja": "フィールド３", "en": "field3"}, "type": "integer"},
                    },
                },
            },
        }
        with open(schema_path, "w") as f:
            json.dump(schema_data, f)

        schema = _load_and_validate_schema(schema_path)

        # When: Processing custom field with fill_defaults=True, required_only=False
        result = _process_custom_field(
            schema.properties.custom,
            fill_defaults=True,
            required_only=False,
            required_fields=schema.properties.custom.required,
        )

        # Then: Returns all fields with defaults
        assert isinstance(result, dict)
        assert "field1" in result
        assert "field2" in result
        assert "field3" in result
        assert result["field1"] == ""
        assert result["field2"] == 0.0
        assert result["field3"] == 0

    def test_ep002_no_fill_defaults_all_fields(self, tmp_path):
        """Given: Valid schema with custom fields, fill_defaults=False."""
        schema_path = tmp_path / "invoice.schema.json"
        schema_data = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://rde.nims.go.jp/test/invoice.schema.json",
            "description": "Test schema",
            "type": "object",
            "required": ["custom"],
            "properties": {
                "custom": {
                    "type": "object",
                    "label": {"ja": "固有情報", "en": "Custom"},
                    "required": ["field1"],
                    "properties": {
                        "field1": {"label": {"ja": "フィールド１", "en": "field1"}, "type": "string"},
                        "field2": {"label": {"ja": "フィールド２", "en": "field2"}, "type": "number"},
                    },
                },
            },
        }
        with open(schema_path, "w") as f:
            json.dump(schema_data, f)

        schema = _load_and_validate_schema(schema_path)

        # When: Processing custom field with fill_defaults=False
        result = _process_custom_field(
            schema.properties.custom,
            fill_defaults=False,
            required_only=False,
            required_fields=schema.properties.custom.required,
        )

        # Then: Returns all fields with None
        assert isinstance(result, dict)
        assert "field1" in result
        assert "field2" in result
        assert result["field1"] is None
        assert result["field2"] is None

    def test_ep003_required_only_mode(self, tmp_path):
        """Given: Valid schema with required and optional fields, required_only=True."""
        schema_path = tmp_path / "invoice.schema.json"
        schema_data = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://rde.nims.go.jp/test/invoice.schema.json",
            "description": "Test schema",
            "type": "object",
            "required": ["custom"],
            "properties": {
                "custom": {
                    "type": "object",
                    "label": {"ja": "固有情報", "en": "Custom"},
                    "required": ["field1", "field2"],
                    "properties": {
                        "field1": {"label": {"ja": "フィールド１", "en": "field1"}, "type": "string"},
                        "field2": {"label": {"ja": "フィールド２", "en": "field2"}, "type": "number"},
                        "field3": {"label": {"ja": "フィールド３", "en": "field3"}, "type": "integer"},
                    },
                },
            },
        }
        with open(schema_path, "w") as f:
            json.dump(schema_data, f)

        schema = _load_and_validate_schema(schema_path)

        # When: Processing custom field with required_only=True
        result = _process_custom_field(
            schema.properties.custom,
            fill_defaults=True,
            required_only=True,
            required_fields=schema.properties.custom.required,
        )

        # Then: Returns only required fields
        assert isinstance(result, dict)
        assert "field1" in result
        assert "field2" in result
        assert "field3" not in result  # field3 is not required

    def test_ep004_with_schema_default_values(self, tmp_path):
        """Given: Schema with default values."""
        schema_path = tmp_path / "invoice.schema.json"
        schema_data = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://rde.nims.go.jp/test/invoice.schema.json",
            "description": "Test schema",
            "type": "object",
            "required": ["custom"],
            "properties": {
                "custom": {
                    "type": "object",
                    "label": {"ja": "固有情報", "en": "Custom"},
                    "required": ["field1"],
                    "properties": {
                        "field1": {"label": {"ja": "フィールド１", "en": "field1"}, "type": "string", "default": "custom_default"},
                        "field2": {"label": {"ja": "フィールド２", "en": "field2"}, "type": "number", "examples": [99.9]},
                    },
                },
            },
        }
        with open(schema_path, "w") as f:
            json.dump(schema_data, f)

        schema = _load_and_validate_schema(schema_path)

        # When: Processing custom field
        result = _process_custom_field(
            schema.properties.custom,
            fill_defaults=True,
            required_only=False,
            required_fields=schema.properties.custom.required,
        )

        # Then: Uses schema defaults and examples
        assert result["field1"] == "custom_default"
        assert result["field2"] == 99.9


class TestProcessSampleField:
    """Test suite for _process_sample_field function.

    EP/BV Test Design:
    ==================

    | Test Case | fill_defaults | generalAttributes | specificAttributes | Expected Result |
    |-----------|---------------|-------------------|--------------------|-----------------|
    | EP-001    | True          | None              | None               | Basic sample structure |
    | EP-002    | False         | None              | None               | Basic sample structure (no defaults) |
    | EP-003    | True          | 2 items           | None               | With generalAttributes |
    | EP-004    | True          | None              | 2 items            | With specificAttributes |
    """

    def test_ep001_basic_sample_with_fill_defaults(self, tmp_path):
        """Given: Schema with sample but no attributes."""
        schema_path = tmp_path / "invoice.schema.json"
        schema_data = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://rde.nims.go.jp/test/invoice.schema.json",
            "description": "Test schema",
            "type": "object",
            "required": ["sample"],
            "properties": {
                "sample": {
                    "type": "object",
                    "label": {"ja": "試料情報", "en": "Sample"},
                    "properties": {},
                },
            },
        }
        with open(schema_path, "w") as f:
            json.dump(schema_data, f)

        schema = _load_and_validate_schema(schema_path)

        # When: Processing sample field with fill_defaults=True
        result = _process_sample_field(schema.properties.sample, fill_defaults=True)

        # Then: Returns basic sample structure
        assert isinstance(result, dict)
        assert "sampleId" in result
        assert "names" in result
        assert "composition" in result
        assert "generalAttributes" in result
        assert "specificAttributes" in result
        assert result["sampleId"] == ""
        assert result["names"] == ["<Please enter a sample name>"]
        assert result["generalAttributes"] == []
        assert result["specificAttributes"] == []

    def test_ep002_basic_sample_without_fill_defaults(self, tmp_path):
        """Given: Schema with sample, fill_defaults=False."""
        schema_path = tmp_path / "invoice.schema.json"
        schema_data = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://rde.nims.go.jp/test/invoice.schema.json",
            "description": "Test schema",
            "type": "object",
            "required": ["sample"],
            "properties": {
                "sample": {
                    "type": "object",
                    "label": {"ja": "試料情報", "en": "Sample"},
                    "properties": {},
                },
            },
        }
        with open(schema_path, "w") as f:
            json.dump(schema_data, f)

        schema = _load_and_validate_schema(schema_path)

        # When: Processing sample field with fill_defaults=False
        result = _process_sample_field(schema.properties.sample, fill_defaults=False)

        # Then: Returns sample structure with minimal defaults
        assert result["names"] == []

    def test_ep003_with_general_attributes(self, tmp_path):
        """Given: Schema with generalAttributes."""
        schema_path = tmp_path / "invoice.schema.json"
        schema_data = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://rde.nims.go.jp/test/invoice.schema.json",
            "description": "Test schema",
            "type": "object",
            "required": ["sample"],
            "properties": {
                "sample": {
                    "type": "object",
                    "label": {"ja": "試料情報", "en": "Sample"},
                    "properties": {
                        "generalAttributes": {
                            "type": "array",
                            "items": [
                                {"type": "object", "required": ["termId"], "properties": {"termId": {"const": "term-id-1"}}},
                                {"type": "object", "required": ["termId"], "properties": {"termId": {"const": "term-id-2"}}},
                            ],
                        },
                    },
                },
            },
        }
        with open(schema_path, "w") as f:
            json.dump(schema_data, f)

        schema = _load_and_validate_schema(schema_path)

        # When: Processing sample field
        result = _process_sample_field(schema.properties.sample, fill_defaults=True)

        # Then: Returns sample with generalAttributes
        assert len(result["generalAttributes"]) == 2
        assert result["generalAttributes"][0]["termId"] == "term-id-1"
        assert result["generalAttributes"][0]["value"] == ""
        assert result["generalAttributes"][1]["termId"] == "term-id-2"

    def test_ep004_with_specific_attributes(self, tmp_path):
        """Given: Schema with specificAttributes."""
        schema_path = tmp_path / "invoice.schema.json"
        schema_data = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://rde.nims.go.jp/test/invoice.schema.json",
            "description": "Test schema",
            "type": "object",
            "required": ["sample"],
            "properties": {
                "sample": {
                    "type": "object",
                    "label": {"ja": "試料情報", "en": "Sample"},
                    "properties": {
                        "specificAttributes": {
                            "type": "array",
                            "items": [
                                {
                                    "type": "object",
                                    "required": ["classId", "termId"],
                                    "properties": {"classId": {"const": "class-id-1"}, "termId": {"const": "term-id-1"}},
                                },
                                {
                                    "type": "object",
                                    "required": ["classId", "termId"],
                                    "properties": {"classId": {"const": "class-id-2"}, "termId": {"const": "term-id-2"}},
                                },
                            ],
                        },
                    },
                },
            },
        }
        with open(schema_path, "w") as f:
            json.dump(schema_data, f)

        schema = _load_and_validate_schema(schema_path)

        # When: Processing sample field
        result = _process_sample_field(schema.properties.sample, fill_defaults=True)

        # Then: Returns sample with specificAttributes
        assert len(result["specificAttributes"]) == 2
        assert result["specificAttributes"][0]["classId"] == "class-id-1"
        assert result["specificAttributes"][0]["termId"] == "term-id-1"
        assert result["specificAttributes"][0]["value"] == ""
        assert result["specificAttributes"][1]["classId"] == "class-id-2"


class TestValidateGeneratedInvoice:
    """Test suite for _validate_generated_invoice function.

    EP/BV Test Design:
    ==================

    | Test Case | invoice_data | schema | Expected Result |
    |-----------|--------------|--------|-----------------|
    | EP-001    | valid        | valid  | Validated data  |
    | BV-001    | invalid      | valid  | InvoiceSchemaValidationError |
    """

    def test_ep001_valid_invoice_data(self, tmp_path):
        """Given: Valid invoice data and schema."""
        schema_path = tmp_path / "invoice.schema.json"
        schema_data = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://rde.nims.go.jp/test/invoice.schema.json",
            "description": "Test schema",
            "type": "object",
            "required": ["custom"],
            "properties": {
                "custom": {
                    "type": "object",
                    "label": {"ja": "固有情報", "en": "Custom"},
                    "required": ["field1"],
                    "properties": {
                        "field1": {"label": {"ja": "フィールド１", "en": "field1"}, "type": "string"},
                    },
                },
            },
        }
        with open(schema_path, "w") as f:
            json.dump(schema_data, f)

        invoice_data = {
            "datasetId": "",
            "basic": {
                "dateSubmitted": "",
                "dataOwnerId": "0" * 56,  # Valid 56-character pattern
                "dataName": "test",
                "instrumentId": None,
                "experimentId": None,
                "description": None,
            },
            "custom": {"field1": ""},
        }

        # When: Validating invoice data
        result = _validate_generated_invoice(invoice_data, schema_path)

        # Then: Returns validated data without errors
        assert result is not None
        assert "datasetId" in result
        assert "basic" in result
        assert "custom" in result

    def test_bv001_invalid_invoice_data(self, tmp_path):
        """Given: Invalid invoice data (missing required field)."""
        schema_path = tmp_path / "invoice.schema.json"
        schema_data = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://rde.nims.go.jp/test/invoice.schema.json",
            "description": "Test schema",
            "type": "object",
            "required": ["custom"],
            "properties": {
                "custom": {
                    "type": "object",
                    "label": {"ja": "固有情報", "en": "Custom"},
                    "required": ["field1"],
                    "properties": {
                        "field1": {"label": {"ja": "フィールド１", "en": "field1"}, "type": "string"},
                    },
                },
            },
        }
        with open(schema_path, "w") as f:
            json.dump(schema_data, f)

        invoice_data = {
            "datasetId": "",
            "basic": {
                "dateSubmitted": "",
                "dataOwnerId": "invalid",  # Too short
                "dataName": "test",
            },
            "custom": {},  # Missing required field1
        }

        # When/Then: Validating raises InvoiceSchemaValidationError
        with pytest.raises(InvoiceSchemaValidationError):
            _validate_generated_invoice(invoice_data, schema_path)


class TestGenerateInvoiceFromSchema:
    """Test suite for generate_invoice_from_schema function.

    EP/BV Test Design:
    ==================

    | Test Case | schema_path | output_path | fill_defaults | required_only | Expected Result |
    |-----------|-------------|-------------|---------------|---------------|-----------------|
    | EP-001    | valid       | None        | True          | False         | dict with all fields + defaults |
    | EP-002    | valid       | valid path  | True          | False         | file created + dict returned |
    | EP-003    | valid       | None        | False         | False         | dict with all fields and preserved `None` |
    | EP-004    | valid       | None        | True          | True          | dict with required fields only |
    | BV-001    | non-existent| None        | True          | False         | FileNotFoundError |
    | BV-002    | invalid     | None        | True          | False         | ValueError |
    """

    def test_ep001_generate_with_defaults_return_dict(self, tmp_path):
        """Given: Valid schema file."""
        schema_path = tmp_path / "invoice.schema.json"
        schema_data = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://rde.nims.go.jp/test/invoice.schema.json",
            "description": "Test schema",
            "type": "object",
            "required": ["custom"],
            "properties": {
                "custom": {
                    "type": "object",
                    "label": {"ja": "固有情報", "en": "Custom"},
                    "required": ["field1"],
                    "properties": {
                        "field1": {"label": {"ja": "フィールド１", "en": "field1"}, "type": "string"},
                        "field2": {"label": {"ja": "フィールド２", "en": "field2"}, "type": "number"},
                    },
                },
            },
        }
        with open(schema_path, "w") as f:
            json.dump(schema_data, f)

        # When: Generate with fill_defaults=True, required_only=False
        result = generate_invoice_from_schema(schema_path, fill_defaults=True, required_only=False)

        # Then: Returns dict with all fields and default values
        assert isinstance(result, dict)
        assert "datasetId" in result
        assert "basic" in result
        assert "custom" in result
        assert result["datasetId"] == ""
        assert result["basic"]["dateSubmitted"] == ""
        assert result["custom"]["field1"] == ""
        assert result["custom"]["field2"] == 0.0

    def test_ep002_generate_and_write_to_file(self, tmp_path):
        """Given: Valid schema file and output path."""
        schema_path = tmp_path / "invoice.schema.json"
        output_path = tmp_path / "output" / "invoice.json"
        schema_data = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://rde.nims.go.jp/test/invoice.schema.json",
            "description": "Test schema",
            "type": "object",
            "required": ["custom"],
            "properties": {
                "custom": {
                    "type": "object",
                    "label": {"ja": "固有情報", "en": "Custom"},
                    "required": ["field1"],
                    "properties": {
                        "field1": {"label": {"ja": "フィールド１", "en": "field1"}, "type": "string"},
                    },
                },
            },
        }
        with open(schema_path, "w") as f:
            json.dump(schema_data, f)

        # When: Generate with output_path specified
        result = generate_invoice_from_schema(schema_path, output_path=output_path, fill_defaults=True, required_only=False)

        # Then: File is created and dict is returned
        assert output_path.exists()
        assert isinstance(result, dict)
        assert "datasetId" in result

        # Verify file content
        with open(output_path) as f:
            file_data = json.load(f)
        assert file_data == result

    def test_ep003_generate_without_fill_defaults(self, tmp_path):
        """Given: Valid schema file, fill_defaults=False."""
        schema_path = tmp_path / "invoice.schema.json"
        schema_data = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://rde.nims.go.jp/test/invoice.schema.json",
            "description": "Test schema",
            "type": "object",
            "required": ["custom"],
            "properties": {
                "custom": {
                    "type": "object",
                    "label": {"ja": "固有情報", "en": "Custom"},
                    "required": [],
                    "properties": {
                        "field1": {"label": {"ja": "フィールド１", "en": "field1"}, "type": "string"},
                        "field2": {"label": {"ja": "フィールド２", "en": "field2"}, "type": "string", "default": "x"},
                    },
                },
            },
        }
        with open(schema_path, "w") as f:
            json.dump(schema_data, f)

        # When: Generate with fill_defaults=False
        result = generate_invoice_from_schema(schema_path, fill_defaults=False, required_only=False)

        # Then: System-required ID stays valid and custom keys are preserved
        assert result["basic"]["dataOwnerId"] == "0" * 56
        assert "field1" in result["custom"]
        assert "field2" in result["custom"]
        assert result["custom"]["field1"] is None
        assert result["custom"]["field2"] == "x"

    def test_ep004_generate_required_only(self, tmp_path):
        """Given: Valid schema with required and optional fields (custom required, sample optional)."""
        schema_path = tmp_path / "invoice.schema.json"
        schema_data = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://rde.nims.go.jp/test/invoice.schema.json",
            "description": "Test schema",
            "type": "object",
            "required": ["custom"],  # Only custom is required, sample is not
            "properties": {
                "custom": {
                    "type": "object",
                    "label": {"ja": "固有情報", "en": "Custom"},
                    "required": ["field1"],
                    "properties": {
                        "field1": {"label": {"ja": "フィールド１", "en": "field1"}, "type": "string"},
                    },
                },
                # sample is intentionally not included, as it's optional and should be skipped
            },
        }
        with open(schema_path, "w") as f:
            json.dump(schema_data, f)

        # When: Generate with required_only=True
        result = generate_invoice_from_schema(schema_path, fill_defaults=True, required_only=True)

        # Then: Returns dict with only required fields
        assert isinstance(result, dict)
        assert "datasetId" in result  # system-required
        assert "basic" in result  # system-required
        assert "custom" in result  # in schema's required list
        assert "sample" not in result  # not in schema's required list

    def test_bv001_non_existent_schema_file(self, tmp_path):
        """Given: Non-existent schema file."""
        schema_path = tmp_path / "does_not_exist.json"

        # When/Then: Generate raises FileNotFoundError
        with pytest.raises(FileNotFoundError):
            generate_invoice_from_schema(schema_path)

    def test_bv002_invalid_schema_file(self, tmp_path):
        """Given: Invalid schema file."""
        schema_path = tmp_path / "invalid.json"
        with open(schema_path, "w") as f:
            f.write("{invalid json}")

        # When/Then: Generate raises ValueError
        with pytest.raises(ValueError):
            generate_invoice_from_schema(schema_path)

    def test_ep005_generate_with_sample_attributes(self, tmp_path):
        """Given: Schema with both generalAttributes and specificAttributes."""
        schema_path = tmp_path / "invoice.schema.json"
        schema_data = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://rde.nims.go.jp/test/invoice.schema.json",
            "description": "Test schema",
            "type": "object",
            "required": ["custom", "sample"],
            "properties": {
                "custom": {
                    "type": "object",
                    "label": {"ja": "固有情報", "en": "Custom"},
                    "required": ["field1"],
                    "properties": {
                        "field1": {"label": {"ja": "フィールド１", "en": "field1"}, "type": "string"},
                    },
                },
                "sample": {
                    "type": "object",
                    "label": {"ja": "試料情報", "en": "Sample"},
                    "properties": {
                        "generalAttributes": {
                            "type": "array",
                            "items": [
                                {"type": "object", "required": ["termId"], "properties": {"termId": {"const": "gen-term-1"}}},
                            ],
                        },
                        "specificAttributes": {
                            "type": "array",
                            "items": [
                                {
                                    "type": "object",
                                    "required": ["classId", "termId"],
                                    "properties": {"classId": {"const": "class-1"}, "termId": {"const": "spec-term-1"}},
                                },
                            ],
                        },
                    },
                },
            },
        }
        with open(schema_path, "w") as f:
            json.dump(schema_data, f)

        # When: Generate invoice
        result = generate_invoice_from_schema(schema_path, fill_defaults=True, required_only=False)

        # Then: Returns dict with sample attributes populated
        assert "sample" in result
        assert len(result["sample"]["generalAttributes"]) == 1
        assert result["sample"]["generalAttributes"][0]["termId"] == "gen-term-1"
        assert len(result["sample"]["specificAttributes"]) == 1
        assert result["sample"]["specificAttributes"][0]["classId"] == "class-1"
        assert result["sample"]["specificAttributes"][0]["termId"] == "spec-term-1"

    def test_ep006_string_paths(self, tmp_path):
        """Given: Schema path as string (not Path object)."""
        schema_path = tmp_path / "invoice.schema.json"
        output_path = tmp_path / "invoice.json"
        schema_data = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://rde.nims.go.jp/test/invoice.schema.json",
            "description": "Test schema",
            "type": "object",
            "required": ["custom"],
            "properties": {
                "custom": {
                    "type": "object",
                    "label": {"ja": "固有情報", "en": "Custom"},
                    "required": ["field1"],
                    "properties": {
                        "field1": {"label": {"ja": "フィールド１", "en": "field1"}, "type": "string"},
                    },
                },
            },
        }
        with open(schema_path, "w") as f:
            json.dump(schema_data, f)

        # When: Generate with string paths
        result = generate_invoice_from_schema(str(schema_path), output_path=str(output_path), fill_defaults=True, required_only=False)

        # Then: Works correctly with string paths
        assert output_path.exists()
        assert isinstance(result, dict)

    def test_ep007_with_boolean_fields(self, tmp_path):
        """Given: Schema with boolean fields."""
        schema_path = tmp_path / "invoice.schema.json"
        schema_data = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://rde.nims.go.jp/test/invoice.schema.json",
            "description": "Test schema",
            "type": "object",
            "required": ["custom"],
            "properties": {
                "custom": {
                    "type": "object",
                    "label": {"ja": "固有情報", "en": "Custom"},
                    "required": ["flag"],
                    "properties": {
                        "flag": {"label": {"ja": "フラグ", "en": "flag"}, "type": "boolean"},
                    },
                },
            },
        }
        with open(schema_path, "w") as f:
            json.dump(schema_data, f)

        # When: Generate invoice
        result = generate_invoice_from_schema(schema_path, fill_defaults=True, required_only=False)

        # Then: Boolean field has False as default
        assert result["custom"]["flag"] is False

    def test_ep008_schema_with_no_custom_or_sample(self, tmp_path):
        """Given: Schema with neither custom nor sample properties."""
        schema_path = tmp_path / "invoice.schema.json"
        schema_data = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://rde.nims.go.jp/test/invoice.schema.json",
            "description": "Test schema",
            "type": "object",
            "properties": {},
        }
        with open(schema_path, "w") as f:
            json.dump(schema_data, f)

        # When: Generate invoice
        result = generate_invoice_from_schema(schema_path, fill_defaults=True, required_only=False)

        # Then: Only basic and datasetId are present
        assert "datasetId" in result
        assert "basic" in result
        assert "custom" not in result
        assert "sample" not in result
