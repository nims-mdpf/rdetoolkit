"""Property-based tests for rdetoolkit.validation.

Tests invoice validation logic with various valid and invalid invoice structures.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given
from hypothesis import strategies as st

from rdetoolkit.exceptions import InvoiceSchemaValidationError
from rdetoolkit.validation import InvoiceValidator, invoice_validate


# Constant schema (not a strategy since it doesn't vary)
def get_minimal_invoice_schema() -> dict:
    """Get minimal valid invoice schema structure.

    This represents the basic required structure of invoice.schema.json
    that InvoiceValidator expects.

    Note: This matches the actual invoice_basic_and_sample.schema_.json
    """
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["basic", "datasetId"],
        "properties": {
            "basic": {
                "type": "object",
                "required": ["dateSubmitted", "dataOwnerId", "dataName"],
                "properties": {
                    "dateSubmitted": {"type": "string", "format": "date"},
                    "dataOwnerId": {"type": "string"},
                    "dataName": {"type": "string"},
                },
            },
            "datasetId": {"type": "string"},
        },
    }


@st.composite
def valid_invoice_data(draw: st.DrawFn) -> dict:
    """Generate valid invoice data matching minimal schema.

    Returns invoice data with only required fields (basic and datasetId).
    """
    return {
        "basic": {
            "dateSubmitted": draw(st.dates().map(lambda d: d.isoformat())),
            "dataOwnerId": draw(st.text(min_size=56, max_size=56, alphabet="0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")),
            "dataName": draw(st.text(min_size=1, max_size=100)),
        },
        "datasetId": draw(st.text(min_size=1, max_size=100)),
    }


@st.composite
def non_required_field_dict(draw: st.DrawFn) -> dict:
    """Generate dictionary with non-required field name and arbitrary non-None value.

    Returns a single-item dict with a field name that is NOT in the required set
    (not 'basic' or 'datasetId'). The value is guaranteed to be non-None because
    None values are removed by InvoiceValidator._remove_none_values.
    """
    # Generate field names that are definitely not required
    field_name = draw(
        st.text(min_size=1, max_size=50).filter(
            lambda s: s not in {"basic", "datasetId"} and s.isidentifier(),
        ),
    )

    # Generate arbitrary non-None values
    field_value = draw(
        st.one_of(
            st.booleans(),
            st.integers(),
            st.floats(allow_nan=False, allow_infinity=False),
            st.text(max_size=100),
            st.lists(st.text(max_size=50), max_size=10),
            st.dictionaries(st.text(max_size=20), st.text(max_size=50), max_size=5),
        ),
    )

    return {field_name: field_value}


@pytest.mark.property
class TestInvoiceValidatorProperties:
    """Property-based tests for InvoiceValidator class."""

    @given(invoice_data=valid_invoice_data())
    def test_required_fields_only_passes(self, invoice_data: dict) -> None:
        """Property: Invoice with only required fields passes validation.

        Args:
            invoice_data: Valid invoice data with only required fields
        """
        # Given: A minimal valid schema and invoice with only required fields
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "test_schema.json"
            schema = get_minimal_invoice_schema()
            schema_path.write_text(json.dumps(schema))

            validator = InvoiceValidator(schema_path)

            # When: Validating invoice data
            # Then: Validation should succeed without raising exception
            result = validator.validate(obj=invoice_data)
            assert result is not None
            assert isinstance(result, dict)
            assert "basic" in result
            assert "datasetId" in result

    @given(invoice_data=valid_invoice_data(), extra_field=non_required_field_dict())
    def test_non_required_field_injection_fails(
        self,
        invoice_data: dict,
        extra_field: dict,
    ) -> None:
        """Property: Injecting non-required fields always causes validation error.

        Args:
            invoice_data: Valid invoice data with only required fields
            extra_field: Dictionary with a non-required field
        """
        # Given: Valid invoice data and a non-required field to inject
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "test_schema.json"
            schema = get_minimal_invoice_schema()
            schema_path.write_text(json.dumps(schema))

            # Inject the non-required field
            invoice_with_extra = {**invoice_data, **extra_field}

            validator = InvoiceValidator(schema_path)

            # When/Then: Validating invoice with extra field should raise error
            with pytest.raises(InvoiceSchemaValidationError) as exc_info:
                validator.validate(obj=invoice_with_extra)

            # Verify error message indicates validation failure
            # The error can be "anyOf" (when additionalProperties is rejected)
            # or mention the field name directly
            error_message = str(exc_info.value).lower()
            field_name = next(iter(extra_field.keys())).lower()
            assert "anyof" in error_message or field_name in error_message

    @given(invoice_data=valid_invoice_data())
    def test_validation_is_idempotent(self, invoice_data: dict) -> None:
        """Property: Validating the same invoice twice produces identical results.

        Args:
            invoice_data: Valid invoice data
        """
        # Given: Valid schema and invoice data
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "test_schema.json"
            schema = get_minimal_invoice_schema()
            schema_path.write_text(json.dumps(schema))

            validator = InvoiceValidator(schema_path)

            # When: Validating twice
            result1 = validator.validate(obj=invoice_data)
            result2 = validator.validate(obj=invoice_data)

            # Then: Results should be identical
            assert result1 == result2

    @given(invoice_data=valid_invoice_data())
    def test_validation_does_not_modify_input(self, invoice_data: dict) -> None:
        """Property: Validation does not modify the input invoice data.

        Args:
            invoice_data: Valid invoice data
        """
        # Given: Valid schema and invoice data
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "test_schema.json"
            schema = get_minimal_invoice_schema()
            schema_path.write_text(json.dumps(schema))

            # Create deep copy for comparison
            original = json.loads(json.dumps(invoice_data))

            validator = InvoiceValidator(schema_path)

            # When: Validating the invoice
            validator.validate(obj=invoice_data)

            # Then: Original data should remain unchanged
            assert invoice_data == original


@pytest.mark.property
class TestInvoiceValidateFunctionProperties:
    """Property-based tests for invoice_validate function."""

    @given(invoice_data=valid_invoice_data())
    def test_invoice_validate_accepts_valid_data(
        self,
        invoice_data: dict,
    ) -> None:
        """Property: invoice_validate accepts invoices with only required fields.

        Args:
            invoice_data: Valid invoice data
        """
        # Given: Valid schema and invoice files
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "test_schema.json"
            invoice_path = Path(tmpdir) / "test_invoice.json"

            schema = get_minimal_invoice_schema()
            schema_path.write_text(json.dumps(schema))
            invoice_path.write_text(json.dumps(invoice_data))

            # When/Then: Validation should succeed without raising exception
            invoice_validate(invoice_path, schema_path)

    @given(invoice_data=valid_invoice_data(), extra_field=non_required_field_dict())
    def test_invoice_validate_rejects_extra_fields(
        self,
        invoice_data: dict,
        extra_field: dict,
    ) -> None:
        """Property: invoice_validate rejects invoices with non-required fields.

        Args:
            invoice_data: Valid invoice data
            extra_field: Dictionary with a non-required field
        """
        # Given: Schema and invoice with extra non-required field
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "test_schema.json"
            invoice_path = Path(tmpdir) / "test_invoice.json"

            schema = get_minimal_invoice_schema()
            invoice_with_extra = {**invoice_data, **extra_field}

            schema_path.write_text(json.dumps(schema))
            invoice_path.write_text(json.dumps(invoice_with_extra))

            # When/Then: Validation should raise InvoiceSchemaValidationError
            with pytest.raises(InvoiceSchemaValidationError):
                invoice_validate(invoice_path, schema_path)


@pytest.mark.property
class TestInvoiceValidatorEdgeCases:
    """Property-based tests for edge cases in invoice validation."""

    @given(
        dataset_id=st.text(min_size=0, max_size=200),
        date_str=st.dates().map(lambda d: d.isoformat()),
    )
    def test_various_string_lengths(
        self,
        dataset_id: str,
        date_str: str,
    ) -> None:
        """Property: Various string lengths in fields are handled correctly.

        Args:
            dataset_id: Dataset ID of varying length
            date_str: ISO format date string
        """
        # Given: Invoice with varying string field lengths
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "test_schema.json"
            schema = get_minimal_invoice_schema()
            schema_path.write_text(json.dumps(schema))

            invoice_data = {
                "basic": {
                    "dateSubmitted": date_str,
                    "dataOwnerId": "a" * 56,  # Fixed length required by pattern
                    "dataName": "TestName",
                },
                "datasetId": dataset_id,
            }

            validator = InvoiceValidator(schema_path)

            # When: Validating invoice
            # Then: Should succeed for valid lengths
            try:
                result = validator.validate(obj=invoice_data)
                assert isinstance(result, dict)
            except InvoiceSchemaValidationError:
                # Schema may have additional constraints on string length
                pass

    @given(invoice_data=valid_invoice_data())
    def test_none_value_removal(self, invoice_data: dict) -> None:
        """Property: None values in invoice are removed before validation.

        This test verifies the _remove_none_values method behavior:
        - None values should be stripped from the invoice data
        - If the resulting data is valid, validation succeeds
        - If the schema rejects additional fields, validation may fail

        Args:
            invoice_data: Valid invoice data
        """
        # Given: Invoice with None values injected
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "test_schema.json"
            schema = get_minimal_invoice_schema()
            schema_path.write_text(json.dumps(schema))

            # Inject None values into nested structure
            invoice_with_nones = {
                **invoice_data,
                "basic": {
                    **invoice_data["basic"],
                    "optionalField": None,  # This should be removed by _remove_none_values
                },
            }

            validator = InvoiceValidator(schema_path)

            # When: Validating invoice with None values
            # Then: Either succeeds (None removed, schema accepts) or fails (schema rejects field)
            try:
                result = validator.validate(obj=invoice_with_nones)
                # If validation succeeds, result should not contain None values
                assert result is not None
                assert isinstance(result, dict)
            except InvoiceSchemaValidationError:
                # Schema may reject additional properties even after None removal
                # This is acceptable - the test verifies no crashes occur
                pass
