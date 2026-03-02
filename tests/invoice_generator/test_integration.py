"""Integration tests for invoice generator with real schemas.

These tests verify end-to-end invoice generation workflow without
full validation to avoid format-specific validation errors.
"""

import json
from pathlib import Path

from rdetoolkit.invoice_generator import generate_invoice_from_schema


class TestInvoiceGeneratorIntegration:
    """Integration tests for invoice generation workflow.

    Test Design - End-to-End Workflow:
    ┌─────────────────┬────────────────────────────────────┬─────────────────────┐
    │ Test Case       │ Description                        │ Expected Result     │
    ├─────────────────┼────────────────────────────────────┼─────────────────────┤
    │ EP001           │ Minimal schema generation          │ Basic structure only│
    │ EP002           │ Schema with custom fields          │ Custom section added│
    └─────────────────┴────────────────────────────────────┴─────────────────────┘
    """

    def test_ep001_generate_minimal_schema(self, tmp_path: Path) -> None:
        """EP001: Generate invoice from minimal valid schema.

        Tests:
        - Minimal schema is accepted
        - Basic structure is created with system-required fields
        - No custom or sample sections when schema has no properties
        - Output file is written successfully with UTF-8 encoding
        """
        # Given: Minimal valid schema (only required fields, no properties)
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://rde.nims.go.jp/test",
            "type": "object",
            "properties": {},
        }
        schema_path = tmp_path / "minimal.schema.json"
        with open(schema_path, "w", encoding="utf-8") as f:
            json.dump(schema, f)

        output_path = tmp_path / "invoice.json"

        # When: Generate invoice
        result = generate_invoice_from_schema(
            schema_path,
            output_path,
            fill_defaults=True,
        )

        # Then: Basic structure created
        assert "datasetId" in result, "datasetId should be present"
        assert "basic" in result, "basic section should be present"
        assert result["datasetId"] == "", "datasetId should be empty string"
        assert isinstance(result["basic"], dict), "basic should be dictionary"
        assert "dateSubmitted" in result["basic"], "dateSubmitted should be present"
        assert "dataOwnerId" in result["basic"], "dataOwnerId should be present"
        assert "dataName" in result["basic"], "dataName should be present"

        # Then: No custom or sample sections (schema has no properties)
        assert "custom" not in result, "custom section should not be present"
        assert "sample" not in result, "sample section should not be present"

        # Then: Output file exists with UTF-8 encoding
        assert output_path.exists(), "Output file should be created"
        with open(output_path, encoding="utf-8") as f:
            loaded = json.load(f)
            assert loaded == result, "File content should match generated data"

    def test_ep002_generate_with_custom_fields(self, tmp_path: Path) -> None:
        """EP002: Generate invoice from schema with custom fields.

        Tests:
        - Custom fields are correctly extracted from schema
        - Required and optional custom fields are included
        - Default values are properly assigned based on type
        - Output matches expected structure
        """
        # Given: Schema with custom fields
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://rde.nims.go.jp/test",
            "type": "object",
            "required": ["custom"],
            "properties": {
                "custom": {
                    "type": "object",
                    "label": {"ja": "固有情報", "en": "Custom"},
                    "required": ["requiredField"],
                    "properties": {
                        "requiredField": {
                            "type": "string",
                            "label": {"ja": "必須", "en": "Required"},
                            "default": "req_default",
                        },
                        "optionalField": {
                            "type": "number",
                            "label": {"ja": "任意", "en": "Optional"},
                        },
                    },
                }
            },
        }
        schema_path = tmp_path / "with_custom.schema.json"
        with open(schema_path, "w", encoding="utf-8") as f:
            json.dump(schema, f)

        output_path = tmp_path / "invoice.json"

        # When: Generate invoice with all fields
        result = generate_invoice_from_schema(
            schema_path,
            output_path,
            fill_defaults=True,
            required_only=False,
        )

        # Then: Custom section populated correctly
        assert "custom" in result, "custom section should be present"
        assert "requiredField" in result["custom"], "Required field should be present"
        assert result["custom"]["requiredField"] == "req_default", "Should use schema default"
        assert "optionalField" in result["custom"], "Optional field should be present"
        assert result["custom"]["optionalField"] == 0.0, "Should use type default"

        # Then: Basic sections also present
        assert "datasetId" in result, "datasetId should be present"
        assert "basic" in result, "basic section should be present"

        # Then: Output file written correctly
        assert output_path.exists(), "Output file should be created"
        with open(output_path, encoding="utf-8") as f:
            loaded = json.load(f)
            assert loaded == result, "File content should match generated data"
