# Exceptions API

## Purpose

This module defines specialized exception classes for RDEToolKit. It provides exception handling specific to structured processing, metadata validation, invoice schema validation, and other functionality.

## Key Features

### Specialized Exception Classes
- Exceptions specific to structured processing
- Error handling for each mode
- Metadata validation errors
- Invoice schema validation errors

### Error Classification
- Function-specific error classification
- Detailed error information provision
- Debugging support information

---

::: src.rdetoolkit.exceptions.StructuredError

---

::: src.rdetoolkit.exceptions.InvoiceModeError

---

::: src.rdetoolkit.exceptions.ExcelInvoiceModeError

---

::: src.rdetoolkit.exceptions.MultiDataTileModeError

---

::: src.rdetoolkit.exceptions.RdeFormatModeError

---

::: src.rdetoolkit.exceptions.InvoiceSchemaValidationError

---

::: src.rdetoolkit.exceptions.MetadataValidationError

---

## Practical Usage

### Structured Processing Error Handling

```python title="structured_error_handling.py"
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.workflows import run

def safe_structured_processing(dataset_function):
    """Safe structured processing execution"""
    try:
        result = run(custom_dataset_function=dataset_function)
        print(f"Structured processing completed: {result}")
        return result
        
    except StructuredError as e:
        print(f"Structured processing error: {e}")
        print(f"Error type: {type(e).__name__}")
        
        if hasattr(e, 'error_code'):
            print(f"Error code: {e.error_code}")
        if hasattr(e, 'context'):
            print(f"Error context: {e.context}")
            
        return {"status": "error", "error": str(e)}
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {"status": "unexpected_error", "error": str(e)}

# Usage example
def problematic_dataset_function(srcpaths, resource_paths):
    raise StructuredError("Error occurred in dataset processing")

result = safe_structured_processing(problematic_dataset_function)
print(f"Final result: {result}")
```

### Mode-Specific Error Handling

```python title="mode_specific_errors.py"
from rdetoolkit.exceptions import (
    InvoiceModeError, 
    ExcelInvoiceModeError, 
    MultiDataTileModeError, 
    RdeFormatModeError
)

def handle_mode_specific_error(mode: str, operation):
    """Mode-specific error handling"""
    try:
        return operation()
    except InvoiceModeError as e:
        print(f"Invoice mode error: {e}")
        return {"status": "invoice_error", "error": str(e)}
    except ExcelInvoiceModeError as e:
        print(f"ExcelInvoice mode error: {e}")
        return {"status": "excel_invoice_error", "error": str(e)}
    except MultiDataTileModeError as e:
        print(f"MultiDataTile mode error: {e}")
        return {"status": "multidatatile_error", "error": str(e)}
    except RdeFormatModeError as e:
        print(f"RdeFormat mode error: {e}")
        return {"status": "rdeformat_error", "error": str(e)}

# Usage examples
def invoice_operation():
    raise InvoiceModeError("Error occurred in Invoice processing")

def excel_operation():
    raise ExcelInvoiceModeError("Error occurred in ExcelInvoice processing")

result1 = handle_mode_specific_error("Invoice", invoice_operation)
result2 = handle_mode_specific_error("ExcelInvoice", excel_operation)
```

### Validation Error Handling

```python title="validation_errors.py"
from rdetoolkit.exceptions import MetadataValidationError, InvoiceSchemaValidationError
from rdetoolkit.validation import metadata_validate, invoice_validate
from pathlib import Path

def comprehensive_validation(data_dir: Path):
    """Comprehensive validation processing"""
    results = {"metadata": None, "invoice": None, "errors": []}
    
    # Metadata validation
    metadata_path = data_dir / "meta" / "metadata.json"
    try:
        metadata_validate(metadata_path)
        results["metadata"] = "valid"
        print(f"✓ Metadata validation successful: {metadata_path}")
    except MetadataValidationError as e:
        results["metadata"] = "invalid"
        results["errors"].append(f"Metadata error: {e}")
        print(f"✗ Metadata validation failed: {e}")
    
    # Invoice validation
    invoice_path = data_dir / "invoice" / "invoice.json"
    schema_path = data_dir / "tasksupport" / "invoice.schema.json"
    try:
        invoice_validate(invoice_path, schema_path)
        results["invoice"] = "valid"
        print(f"✓ Invoice validation successful: {invoice_path}")
    except InvoiceSchemaValidationError as e:
        results["invoice"] = "invalid"
        results["errors"].append(f"Invoice error: {e}")
        print(f"✗ Invoice validation failed: {e}")
    
    return results

# Usage example
data_directory = Path("data/experiment_001")
validation_results = comprehensive_validation(data_directory)

if all([validation_results["metadata"] == "valid", validation_results["invoice"] == "valid"]):
    print("All validations successful")
else:
    print("Validation errors found:")
    for error in validation_results["errors"]:
        print(f"  - {error}")
```
