# Invoice Schema Models API

## Purpose

This module defines validator models used in RDEToolKit's invoice schema (invoice.schema.json). It provides functionality for invoice data structure validation and schema compliance verification.

## Key Features

### Schema Models
- Schema definition for entire invoice
- Schema validation for basic information
- Schema validation for sample information
- Custom field management

### Data Validation
- JSONSchema-based validation
- Type safety assurance
- Multilingual label management

---

::: src.rdetoolkit.models.invoice_schema.InvoiceSchemaJson

---

::: src.rdetoolkit.models.invoice_schema.Properties

---

::: src.rdetoolkit.models.invoice_schema.DatasetId

---

::: src.rdetoolkit.models.invoice_schema.BasicItems

---

::: src.rdetoolkit.models.invoice_schema.BasicItemsValue

---

::: src.rdetoolkit.models.invoice_schema.SampleField

---

::: src.rdetoolkit.models.invoice_schema.SampleProperties

---

::: src.rdetoolkit.models.invoice_schema.SamplePropertiesWhenAdding

---

::: src.rdetoolkit.models.invoice_schema.SpecificAttribute

---

::: src.rdetoolkit.models.invoice_schema.SampleSpecificItems

---

::: src.rdetoolkit.models.invoice_schema.SpecificProperty

---

::: src.rdetoolkit.models.invoice_schema.SpecificChildProperty

---

::: src.rdetoolkit.models.invoice_schema.GeneralAttribute

---

::: src.rdetoolkit.models.invoice_schema.SampleGeneralItems

---

::: src.rdetoolkit.models.invoice_schema.GeneralProperty

---

::: src.rdetoolkit.models.invoice_schema.GeneralChildProperty

---

::: src.rdetoolkit.models.invoice_schema.ClassId

---

::: src.rdetoolkit.models.invoice_schema.TermId

---

::: src.rdetoolkit.models.invoice_schema.CustomField

---

::: src.rdetoolkit.models.invoice_schema.CustomItems

---

::: src.rdetoolkit.models.invoice_schema.MetaProperty

---

::: src.rdetoolkit.models.invoice_schema.Options

---

::: src.rdetoolkit.models.invoice_schema.Placeholder

---

::: src.rdetoolkit.models.invoice_schema.LangLabels

---

## Practical Usage

### Basic Schema Validation

```python title="basic_schema_validation.py"
from rdetoolkit.models.invoice_schema import InvoiceSchemaJson, BasicItems

# Create basic items
basic_items = BasicItems(
    dataName="Experimental Data 001",
    description="Temperature measurement experiment",
    tags=["temperature", "measurement"]
)

print(f"Data name: {basic_items.dataName}")
print(f"Description: {basic_items.description}")
print(f"Tags: {basic_items.tags}")

# Invoice schema validation
schema_data = {
    "type": "object",
    "properties": {
        "basic": {"$ref": "#/definitions/BasicItems"},
        "sample": {"$ref": "#/definitions/SampleField"}
    },
    "required": ["basic"]
}

invoice_schema = InvoiceSchemaJson(**schema_data)
print(f"✓ Invoice schema created successfully")
```

### Custom Field Management

```python title="custom_fields.py"
from rdetoolkit.models.invoice_schema import CustomField, CustomItems, LangLabels

# Create multilingual labels
lang_labels = LangLabels(
    ja="カスタム温度",
    en="Custom Temperature"
)

# Create custom field
custom_field = CustomField(
    field_id="custom_temp_001",
    field_type="number",
    labels=lang_labels,
    required=True,
    default_value=25.0,
    unit="℃"
)

print(f"Custom field ID: {custom_field.field_id}")
print(f"Japanese label: {custom_field.labels.ja}")
print(f"English label: {custom_field.labels.en}")
print(f"Default value: {custom_field.default_value}")

# Manage custom items
custom_items = CustomItems(
    fields=[custom_field],
    category="measurement",
    description="Custom fields related to measurement"
)

print(f"Number of custom items: {len(custom_items.fields)}")
print(f"Category: {custom_items.category}")
```

### Attribute and Property Management

```python title="attributes_properties.py"
from rdetoolkit.models.invoice_schema import (
    GeneralAttribute, SpecificAttribute, 
    GeneralProperty, SpecificProperty
)

# Create general attribute
general_attr = GeneralAttribute(
    term_id="TEMP001",
    name="temperature",
    data_type="number",
    unit="℃",
    required=True
)

# Create general property
general_prop = GeneralProperty(
    attribute=general_attr,
    validation_rules={
        "minimum": -273.15,
        "maximum": 1000.0
    },
    display_order=1
)

print(f"General attribute: {general_attr.name}")
print(f"Data type: {general_attr.data_type}")
print(f"Validation rules: {general_prop.validation_rules}")

# Create specific attribute
specific_attr = SpecificAttribute(
    class_id="MAT001",
    term_id="DENSITY001",
    name="density",
    data_type="number",
    unit="g/cm³",
    required=False
)

# Create specific property
specific_prop = SpecificProperty(
    attribute=specific_attr,
    class_specific_rules={
        "material_type": "solid",
        "measurement_method": "displacement"
    },
    display_order=2
)

print(f"Specific attribute: {specific_attr.name}")
print(f"Class ID: {specific_attr.class_id}")
print(f"Class-specific rules: {specific_prop.class_specific_rules}")
```
