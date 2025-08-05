# Validation API

## Purpose

This module provides validation functionality for template files in RDEToolKit. It validates the structure and data validity of metadata files (metadata.json) and invoice files (invoice.json).

## Key Features

### Metadata Validation
- Structure validation of metadata.json files
- Schema validation using Pydantic models
- Detailed error message provision

### Invoice Validation
- Schema validation of invoice.json files
- Consistency verification with invoice.schema.json
- JSONSchema Draft 2020-12 compliant validation

---

::: src.rdetoolkit.validation.MetadataValidator

---

::: src.rdetoolkit.validation.metadata_validate

---

::: src.rdetoolkit.validation.InvoiceValidator

---

::: src.rdetoolkit.validation.invoice_validate

---

## Practical Usage

### Metadata File Validation

```python title="metadata_validation.py"
from rdetoolkit.validation import MetadataValidator, metadata_validate
from rdetoolkit.exceptions import MetadataValidationError
from pathlib import Path

# Basic metadata validation
try:
    metadata_path = Path("data/meta/metadata.json")
    metadata_validate(metadata_path)
    print("Metadata file is valid")
except MetadataValidationError as e:
    print(f"Metadata validation error: {e}")
except FileNotFoundError as e:
    print(f"File not found: {e}")

# Validation using MetadataValidator class
validator = MetadataValidator()

# Validate from file path
try:
    validated_data = validator.validate(path=metadata_path)
    print(f"Validated data: {validated_data}")
except ValueError as e:
    print(f"Validation error: {e}")

# Direct validation from JSON object
metadata_obj = {
    "basic": {
        "dataName": "Experiment Data 001",
        "description": "Temperature measurement experiment"
    },
    "sample": {
        "generalAttributes": [],
        "specificAttributes": []
    }
}

try:
    validated_data = validator.validate(json_obj=metadata_obj)
    print("JSON object is valid")
except ValueError as e:
    print(f"Validation error: {e}")
```

### Invoice File Validation

```python title="invoice_validation.py"
from rdetoolkit.validation import InvoiceValidator, invoice_validate
from rdetoolkit.exceptions import InvoiceSchemaValidationError
from pathlib import Path

# Basic invoice validation
try:
    invoice_path = Path("data/invoice/invoice.json")
    schema_path = Path("data/tasksupport/invoice.schema.json")
    
    invoice_validate(invoice_path, schema_path)
    print("Invoice file is valid")
except InvoiceSchemaValidationError as e:
    print(f"Invoice validation error: {e}")
except FileNotFoundError as e:
    print(f"File not found: {e}")

# Detailed validation using InvoiceValidator class
validator = InvoiceValidator(schema_path)

# Validate from file path
try:
    validated_data = validator.validate(path=invoice_path)
    print("Invoice file validation completed")
    print(f"Data name: {validated_data.get('basic', {}).get('dataName')}")
except InvoiceSchemaValidationError as e:
    print(f"Schema validation error: {e}")

# Direct validation from JSON object
invoice_obj = {
    "basic": {
        "dataName": "Experiment Data 001",
        "description": "Temperature measurement experiment",
        "tags": ["temperature", "measurement"]
    },
    "sample": {
        "generalAttributes": [],
        "specificAttributes": []
    }
}

try:
    validated_data = validator.validate(obj=invoice_obj)
    print("Invoice object is valid")
except InvoiceSchemaValidationError as e:
    print(f"Validation error: {e}")
```

### Batch Validation Processing

```python title="batch_validation.py"
from rdetoolkit.validation import metadata_validate, invoice_validate
from pathlib import Path
import logging

def validate_rde_files(data_dir: Path):
    """Batch validation of RDE file groups"""
    results = {
        "metadata": False,
        "invoice": False,
        "errors": []
    }
    
    # Validate metadata file
    metadata_path = data_dir / "meta" / "metadata.json"
    if metadata_path.exists():
        try:
            metadata_validate(metadata_path)
            results["metadata"] = True
            print(f"✓ Metadata validation successful: {metadata_path}")
        except Exception as e:
            results["errors"].append(f"Metadata error: {e}")
            print(f"✗ Metadata validation failed: {e}")
    
    # Validate invoice file
    invoice_path = data_dir / "invoice" / "invoice.json"
    schema_path = data_dir / "tasksupport" / "invoice.schema.json"
    
    if invoice_path.exists() and schema_path.exists():
        try:
            invoice_validate(invoice_path, schema_path)
            results["invoice"] = True
            print(f"✓ Invoice validation successful: {invoice_path}")
        except Exception as e:
            results["errors"].append(f"Invoice error: {e}")
            print(f"✗ Invoice validation failed: {e}")
    
    return results

# Usage example
data_directory = Path("data/experiment_001")
validation_results = validate_rde_files(data_directory)

if all([validation_results["metadata"], validation_results["invoice"]]):
    print("All file validations successful")
else:
    print("Validation errors found:")
    for error in validation_results["errors"]:
        print(f"  - {error}")
```
