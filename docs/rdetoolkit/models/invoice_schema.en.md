# Invoice Schema Models API

## Purpose

This module defines the data models for invoice schema validation in RDEToolKit. It provides structured schema definitions for validating invoice JSON files against predefined schemas, ensuring data consistency and integrity.

## Key Features

### Schema Validation Models
- Invoice schema structure definitions
- JSONSchema-compliant validation models
- Type-safe schema representation

### Data Integrity
- Comprehensive schema validation
- Error detection and reporting
- Schema compliance verification

---

::: src.rdetoolkit.models.invoice_schema

---

## Practical Usage

### Basic Schema Validation

```python title="basic_schema_validation.py"
from rdetoolkit.models.invoice_schema import InvoiceSchemaJson
from rdetoolkit.validation import InvoiceValidator
from pathlib import Path

# Load and validate invoice schema
schema_path = Path("data/tasksupport/invoice.schema.json")
validator = InvoiceValidator(schema_path)

# Validate invoice against schema
invoice_path = Path("data/invoice/invoice.json")
try:
    result = validator.validate(path=invoice_path)
    print("Invoice validation successful")
    print(f"Validated data keys: {list(result.keys())}")
except Exception as e:
    print(f"Validation error: {e}")
```
