"""Invoice generation from JSON schema.

This module provides functionality to generate invoice.json files from
invoice.schema.json definitions. It supports flexible generation modes
with configurable default value strategies and validation.

The main entry point is `generate_invoice_from_schema()` which creates
a valid invoice structure based on schema requirements and properties.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rdetoolkit.fileops import readf_json, writef_json


def generate_invoice_from_schema(
    schema_path: Path | str,
    output_path: Path | str | None = None,
    *,
    fill_defaults: bool = True,
    required_only: bool = False,
) -> dict[str, Any]:
    """Generate invoice.json from invoice.schema.json.

    Creates a valid invoice.json file based on the structure and requirements
    defined in invoice.schema.json. Supports both minimal (required fields only)
    and complete (with defaults) generation modes.

    Args:
        schema_path: Path to invoice.schema.json file.
        output_path: Optional path to write generated invoice.json.
            If None, returns dict without writing to file.
        fill_defaults: If True, populate type-based default values.
            Honors 'default' and 'examples' from schema when present.
        required_only: If True, only include required fields from schema.
            If False, include all properties defined in schema.

    Returns:
        dict[str, Any]: Generated invoice data structure.

    Raises:
        FileNotFoundError: If schema_path does not exist.
        ValueError: If schema is invalid or missing required sections.
        InvoiceSchemaValidationError: If generated invoice fails validation.

    Examples:
        >>> # Generate with all defaults, write to file
        >>> invoice = generate_invoice_from_schema(
        ...     "invoice.schema.json",
        ...     "invoice.json",
        ...     fill_defaults=True
        ... )

        >>> # Generate required fields only, return dict
        >>> invoice = generate_invoice_from_schema(
        ...     "invoice.schema.json",
        ...     required_only=True
        ... )
    """
    # Convert to Path if string
    schema_path_obj = Path(schema_path) if isinstance(schema_path, str) else schema_path

    # Load and validate schema
    schema = _load_and_validate_schema(schema_path_obj)

    # Get required field list from schema
    schema_required = schema.required if schema.required else []

    # Build invoice structure
    invoice_data: dict[str, Any] = {}

    # Always include datasetId (system-required)
    invoice_data["datasetId"] = ""

    # Always include basic section (system-required)
    invoice_data["basic"] = _generate_basic_section(fill_defaults)

    # Process custom field if present and (not required_only mode or in required list)
    if schema.properties.custom is not None and (not required_only or "custom" in schema_required):
        invoice_data["custom"] = _process_custom_field(
            schema.properties.custom,
            fill_defaults=fill_defaults,
            required_only=required_only,
            required_fields=schema.properties.custom.required,
        )

    # Process sample field if present and (not required_only mode or in required list)
    if schema.properties.sample is not None and (not required_only or "sample" in schema_required):
        invoice_data["sample"] = _process_sample_field(
            schema.properties.sample,
            fill_defaults=fill_defaults,
        )

    # Validate generated invoice
    invoice_data = _validate_generated_invoice(invoice_data, schema_path_obj)

    # Write to file if output_path provided
    if output_path is not None:
        output_path_obj = Path(output_path) if isinstance(output_path, str) else output_path
        # Create parent directories if they don't exist
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        writef_json(output_path_obj, invoice_data)

    return invoice_data


def _get_default_value_for_type(
    value_type: str,
    *,
    schema_default: Any = None,
    schema_examples: list[Any] | None = None,
    fill_defaults: bool = True,
) -> Any:
    """Generate appropriate default value based on JSON schema type.

    Priority order:
    1. schema_default (if provided)
    2. first item from schema_examples (if fill_defaults=True and examples exist)
    3. type-based default value

    Args:
        value_type: JSON schema type ("string", "number", "integer", "boolean", "array", "object").
        schema_default: Explicit default value from schema.
        schema_examples: Example values from schema.
        fill_defaults: Whether to use examples and type-based defaults.

    Returns:
        Appropriate default value for the type.
    """
    # Priority 1: schema_default
    if schema_default is not None:
        return schema_default

    # Priority 2: schema_examples (only if fill_defaults=True)
    if fill_defaults and schema_examples and len(schema_examples) > 0:
        return schema_examples[0]

    # Priority 3: type-based defaults (only if fill_defaults=True)
    if not fill_defaults:
        return None

    # Type-based default values
    type_defaults: dict[str, Any] = {
        "string": "",
        "number": 0.0,
        "integer": 0,
        "boolean": False,
        "array": [],
        "object": {},
    }

    return type_defaults.get(value_type)


def _process_custom_field(
    custom_field: Any,  # CustomField from invoice_schema
    *,
    fill_defaults: bool,
    required_only: bool,
    required_fields: list[str],
) -> dict[str, Any]:
    """Process custom field section from schema.

    Args:
        custom_field: CustomField model from schema.
        fill_defaults: Whether to populate default values.
        required_only: Whether to only include required fields.
        required_fields: List of required field names.

    Returns:
        Dictionary with custom field data.
    """
    custom_data: dict[str, Any] = {}

    # Iterate through custom properties
    for field_name, meta_property in custom_field.properties.root.items():
        # If required_only mode, skip fields not in required list
        if required_only and field_name not in required_fields:
            continue

        # Get default value based on type
        default_value = _get_default_value_for_type(
            meta_property.value_type,
            schema_default=meta_property.default,
            schema_examples=meta_property.examples,
            fill_defaults=fill_defaults,
        )

        custom_data[field_name] = default_value

    return custom_data


def _process_sample_field(
    sample_field: Any,  # SampleField from invoice_schema
    *,
    fill_defaults: bool,
) -> dict[str, Any]:
    """Process sample field section from schema.

    Args:
        sample_field: SampleField model from schema.
        fill_defaults: Whether to populate default values.

    Returns:
        Dictionary with sample field data.
    """
    # Sample section has fixed structure based on INVOICE_JSON reference
    # Note: ownerId requires 56 alphanumeric characters pattern: ^([0-9a-zA-Z]{56})$
    placeholder_owner_id = "0" * 56 if fill_defaults else ""

    sample_data: dict[str, Any] = {
        "sampleId": "",
        "names": ["<Please enter a sample name>"] if fill_defaults else [],
        "composition": None,
        "referenceUrl": None,
        "description": None,
        "generalAttributes": [],
        "specificAttributes": [],
        "ownerId": placeholder_owner_id,
    }

    # Process generalAttributes if present in schema
    if hasattr(sample_field.properties, "generalAttributes") and sample_field.properties.generalAttributes is not None:
        general_attr = sample_field.properties.generalAttributes
        if hasattr(general_attr, "items") and general_attr.items.root is not None:
            # Build list of general attribute items with termId
            general_items = []
            for item in general_attr.items.root:
                if hasattr(item, "properties") and item.properties is not None:
                    term_id_obj = item.properties.term_id
                    general_items.append(
                        {
                            "termId": term_id_obj.const,
                            "value": "" if fill_defaults else None,
                        },
                    )
            sample_data["generalAttributes"] = general_items

    # Process specificAttributes if present in schema
    if hasattr(sample_field.properties, "specificAttributes") and sample_field.properties.specificAttributes is not None:
        specific_attr = sample_field.properties.specificAttributes
        if hasattr(specific_attr, "items") and specific_attr.items.root is not None:
            # Build list of specific attribute items with classId and termId
            specific_items = []
            for item in specific_attr.items.root:
                if hasattr(item, "properties") and item.properties is not None:
                    class_id_obj = item.properties.class_id
                    term_id_obj = item.properties.term_id
                    specific_items.append(
                        {
                            "classId": class_id_obj.const,
                            "termId": term_id_obj.const,
                            "value": "" if fill_defaults else None,
                        },
                    )
            sample_data["specificAttributes"] = specific_items

    return sample_data


def _generate_basic_section(fill_defaults: bool) -> dict[str, Any]:
    """Generate basic section with system-required fields.

    Args:
        fill_defaults: Whether to populate default values.

    Returns:
        Dictionary with basic section data.
    """
    # Basic section structure from INVOICE_JSON reference
    # Note: dataOwnerId requires 56 alphanumeric characters pattern: ^([0-9a-zA-Z]{56})$
    # Generate valid placeholder value
    placeholder_owner_id = "0" * 56 if fill_defaults else ""

    basic_data: dict[str, Any] = {
        "dateSubmitted": "",
        "dataOwnerId": placeholder_owner_id,
        "dataName": "",
        "instrumentId": None,
        "experimentId": None,
        "description": None,
    }

    return basic_data


def _load_and_validate_schema(schema_path: Path) -> Any:  # Returns InvoiceSchemaJson
    """Load and validate invoice schema.

    Args:
        schema_path: Path to schema file.

    Returns:
        Validated InvoiceSchemaJson model.

    Raises:
        FileNotFoundError: If schema file doesn't exist.
        ValueError: If schema is invalid.
    """
    # Check file exists
    if not schema_path.exists():
        emsg = f"Schema file not found: {schema_path}"
        raise FileNotFoundError(emsg)

    # Load JSON
    try:
        schema_data = readf_json(schema_path)
    except Exception as e:
        emsg = f"Failed to read schema file: {str(e)}"
        raise ValueError(emsg) from e

    # Validate with pydantic model
    try:
        from rdetoolkit.models.invoice_schema import InvoiceSchemaJson  # noqa: PLC0415

        schema = InvoiceSchemaJson(**schema_data)
    except Exception as e:
        emsg = f"Invalid schema structure: {str(e)}"
        raise ValueError(emsg) from e

    return schema


def _validate_generated_invoice(
    invoice_data: dict[str, Any],
    schema_path: Path,
) -> dict[str, Any]:
    """Validate generated invoice against schema.

    Args:
        invoice_data: Generated invoice data.
        schema_path: Path to schema for validation.

    Returns:
        Validated invoice data (may be modified by validator).

    Raises:
        InvoiceSchemaValidationError: If validation fails.
    """
    from rdetoolkit.validation import InvoiceValidator  # noqa: PLC0415

    validator = InvoiceValidator(schema_path)
    return validator.validate(obj=invoice_data)
