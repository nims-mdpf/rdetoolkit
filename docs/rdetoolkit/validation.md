# Validation Module

The `rdetoolkit.validation` module provides comprehensive validation functionality for RDE (Research Data Exchange) template files and data structures. This module ensures data integrity and schema compliance for metadata definitions and invoice files.

## Overview

The validation module handles validation for critical RDE components:

- **Metadata Validation**: Validates metadata definition files against Pydantic schemas
- **Invoice Validation**: Validates invoice files against JSON Schema specifications
- **Schema Compliance**: Ensures data structure compliance with RDE standards
- **Error Reporting**: Provides detailed validation error messages and context
- **Flexible Input**: Supports validation from file paths or in-memory objects

## Classes

### MetadataValidator

A validator class for validating metadata definition files against the MetadataItem schema.

#### Constructor

```python
MetadataValidator()
```

Creates a new MetadataValidator instance with the MetadataItem schema.

#### Attributes

- `schema` (type[MetadataItem]): The Pydantic schema used for validation

#### Methods

##### validate

Validate JSON data against the MetadataItem schema.

```python
def validate(self, *, path: str | Path | None = None, json_obj: dict[str, Any] | None = None) -> dict[str, Any]
```

**Parameters:**
- `path` (str | Path | None): Path to the JSON file to validate (optional)
- `json_obj` (dict[str, Any] | None): JSON object to validate (optional)

**Returns:**
- `dict[str, Any]`: The validated JSON data

**Raises:**
- `ValueError`: If neither 'path' nor 'json_obj' is provided
- `ValueError`: If both 'path' and 'json_obj' are provided
- `ValueError`: If an unexpected validation error occurs
- `ValidationError`: If the data fails Pydantic validation

**Example:**

```python
from rdetoolkit.validation import MetadataValidator
from pathlib import Path

# Create validator instance
validator = MetadataValidator()

# Validate from file path
try:
    validated_data = validator.validate(path="data/metadata.json")
    print("Metadata validation successful")
    print(f"Validated keys: {list(validated_data.keys())}")
except ValueError as e:
    print(f"Validation error: {e}")

# Validate from JSON object
metadata_obj = {
    "title": "Sample Dataset",
    "description": "A sample dataset for testing",
    "creator": "Research Team",
    "created": "2024-01-01T00:00:00Z"
}

try:
    validated_data = validator.validate(json_obj=metadata_obj)
    print("Object validation successful")
except ValueError as e:
    print(f"Validation error: {e}")
```

### InvoiceValidator

A comprehensive validator class for validating invoice files against JSON Schema specifications with RDE-specific enhancements.

#### Constructor

```python
InvoiceValidator(schema_path: str | Path)
```

**Parameters:**
- `schema_path` (str | Path): Path to the invoice schema JSON file

**Raises:**
- `ValueError`: If the schema file is not a JSON file
- `InvoiceSchemaValidationError`: If the schema file itself is invalid

#### Attributes

- `schema_path` (str | Path): Path to the schema file
- `schema` (dict[str, Any]): Loaded and processed schema dictionary
- `pre_basic_info_schema` (str): Path to the basic information schema file

#### Methods

##### validate

Validate JSON data against the invoice schema.

```python
def validate(self, *, path: str | Path | None = None, obj: dict[str, Any] | None = None) -> dict[str, Any]
```

**Parameters:**
- `path` (str | Path | None): Path to the JSON file to validate (optional)
- `obj` (dict[str, Any] | None): JSON object to validate (optional)

**Returns:**
- `dict[str, Any]`: The validated and cleaned JSON data

**Raises:**
- `ValueError`: If neither 'path' nor 'obj' is provided
- `ValueError`: If both 'path' and 'obj' are provided
- `ValueError`: If the data is not a dictionary
- `InvoiceSchemaValidationError`: If validation against the schema fails

**Processing Steps:**
1. Load JSON data from file or object
2. Remove None values to handle system-generated invoices
3. Validate against basic information schema
4. Validate against full invoice schema
5. Provide detailed error reporting

**Example:**

```python
from rdetoolkit.validation import InvoiceValidator
from rdetoolkit.exceptions import InvoiceSchemaValidationError
from pathlib import Path

# Create validator with schema
schema_path = Path("data/tasksupport/invoice.schema.json")
validator = InvoiceValidator(schema_path)

# Validate invoice file
try:
    validated_data = validator.validate(path="data/invoice/invoice.json")
    print("Invoice validation successful")
    print(f"Invoice contains {len(validated_data.get('sample', {}))} samples")
except InvoiceSchemaValidationError as e:
    print(f"Invoice validation failed: {e}")

# Validate invoice object
invoice_obj = {
    "basic": {
        "title": "Research Dataset",
        "description": "Experimental data collection",
        "creator": "Research Lab"
    },
    "sample": {
        "generalAttributes": [
            {"key": "experiment_id", "value": "EXP001"},
            {"key": "date", "value": "2024-01-01"}
        ],
        "specificAttributes": [
            {"key": "temperature", "value": "25.5", "unit": "°C"},
            {"key": "pressure", "value": "1013.25", "unit": "hPa"}
        ]
    }
}

try:
    validated_data = validator.validate(obj=invoice_obj)
    print("Object validation successful")
except InvoiceSchemaValidationError as e:
    print(f"Validation failed: {e}")
```

## Functions

### metadata_validate

Validate a metadata definition file against the MetadataItem schema.

```python
def metadata_validate(path: str | Path) -> None
```

**Parameters:**
- `path` (str | Path): Path to the metadata definition file

**Returns:**
- `None`

**Raises:**
- `FileNotFoundError`: If the metadata file does not exist
- `MetadataValidationError`: If validation fails with detailed error information

**Example:**

```python
from rdetoolkit.validation import metadata_validate
from rdetoolkit.exceptions import MetadataValidationError
from pathlib import Path

# Validate metadata file
try:
    metadata_validate("data/meta/metadata.json")
    print("Metadata file is valid")
except FileNotFoundError as e:
    print(f"File not found: {e}")
except MetadataValidationError as e:
    print(f"Validation errors found:\n{e}")

# Example of handling validation errors
def validate_metadata_with_details(file_path: str) -> bool:
    """Validate metadata and return success status."""
    try:
        metadata_validate(file_path)
        return True
    except MetadataValidationError as e:
        print("Metadata validation failed with the following errors:")
        # The error message contains numbered validation errors
        print(e)
        return False
    except FileNotFoundError:
        print(f"Metadata file not found: {file_path}")
        return False

# Usage
success = validate_metadata_with_details("data/meta/metadata.json")
if success:
    print("Metadata validation passed")
else:
    print("Metadata validation failed - please fix errors and retry")
```

### invoice_validate

Validate an invoice file against its corresponding schema.

```python
def invoice_validate(path: str | Path, schema: str | Path) -> None
```

**Parameters:**
- `path` (str | Path): Path to the invoice.json file
- `schema` (str | Path): Path to the invoice.schema.json file

**Returns:**
- `None`

**Raises:**
- `FileNotFoundError`: If either the invoice file or schema file does not exist
- `InvoiceSchemaValidationError`: If validation fails

**Example:**

```python
from rdetoolkit.validation import invoice_validate
from rdetoolkit.exceptions import InvoiceSchemaValidationError
from pathlib import Path

# Basic invoice validation
try:
    invoice_validate(
        path="data/invoice/invoice.json",
        schema="data/tasksupport/invoice.schema.json"
    )
    print("Invoice validation successful")
except FileNotFoundError as e:
    print(f"Required file not found: {e}")
except InvoiceSchemaValidationError as e:
    print(f"Invoice validation failed: {e}")

# Batch validation of multiple invoices
def validate_invoice_batch(invoice_dir: Path, schema_path: Path) -> dict[str, bool]:
    """Validate multiple invoice files."""
    results = {}

    for invoice_file in invoice_dir.glob("invoice_*.json"):
        try:
            invoice_validate(invoice_file, schema_path)
            results[invoice_file.name] = True
            print(f"✓ {invoice_file.name} - Valid")
        except (FileNotFoundError, InvoiceSchemaValidationError) as e:
            results[invoice_file.name] = False
            print(f"✗ {invoice_file.name} - Invalid: {e}")

    return results

# Usage
invoice_directory = Path("data/invoices/")
schema_file = Path("data/tasksupport/invoice.schema.json")
validation_results = validate_invoice_batch(invoice_directory, schema_file)

# Summary
total = len(validation_results)
valid = sum(validation_results.values())
print(f"Validation Summary: {valid}/{total} invoices are valid")
```

## Complete Usage Examples

### Comprehensive Validation Workflow

```python
from rdetoolkit.validation import MetadataValidator, InvoiceValidator, metadata_validate, invoice_validate
from rdetoolkit.exceptions import MetadataValidationError, InvoiceSchemaValidationError
from pathlib import Path
import json
from typing import Dict, List, Tuple

class ValidationManager:
    """Comprehensive validation manager for RDE files."""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.metadata_validator = MetadataValidator()
        self.validation_results = {
            "metadata": [],
            "invoices": [],
            "summary": {"total": 0, "valid": 0, "invalid": 0}
        }

    def validate_all_metadata(self, metadata_dir: Path) -> List[Dict[str, any]]:
        """Validate all metadata files in a directory."""
        results = []

        for metadata_file in metadata_dir.glob("metadata*.json"):
            result = {
                "file": str(metadata_file),
                "valid": False,
                "errors": []
            }

            try:
                self.metadata_validator.validate(path=metadata_file)
                result["valid"] = True
                print(f"✓ Metadata validation passed: {metadata_file.name}")
            except MetadataValidationError as e:
                result["errors"].append(str(e))
                print(f"✗ Metadata validation failed: {metadata_file.name}")
            except Exception as e:
                result["errors"].append(f"Unexpected error: {e}")
                print(f"✗ Unexpected error in {metadata_file.name}: {e}")

            results.append(result)
            self.validation_results["metadata"].append(result)

        return results

    def validate_all_invoices(self, invoice_dir: Path, schema_path: Path) -> List[Dict[str, any]]:
        """Validate all invoice files against schema."""
        results = []

        try:
            invoice_validator = InvoiceValidator(schema_path)
        except Exception as e:
            print(f"Failed to create invoice validator: {e}")
            return results

        for invoice_file in invoice_dir.glob("invoice*.json"):
            result = {
                "file": str(invoice_file),
                "valid": False,
                "errors": []
            }

            try:
                invoice_validator.validate(path=invoice_file)
                result["valid"] = True
                print(f"✓ Invoice validation passed: {invoice_file.name}")
            except InvoiceSchemaValidationError as e:
                result["errors"].append(str(e))
                print(f"✗ Invoice validation failed: {invoice_file.name}")
            except Exception as e:
                result["errors"].append(f"Unexpected error: {e}")
                print(f"✗ Unexpected error in {invoice_file.name}: {e}")

            results.append(result)
            self.validation_results["invoices"].append(result)

        return results

    def validate_project_structure(self) -> Dict[str, any]:
        """Validate entire project structure."""
        print("Starting comprehensive validation...")

        # Validate metadata files
        metadata_dir = self.base_path / "meta"
        if metadata_dir.exists():
            print("\n=== Metadata Validation ===")
            metadata_results = self.validate_all_metadata(metadata_dir)
        else:
            print("Metadata directory not found, skipping metadata validation")
            metadata_results = []

        # Validate invoice files
        invoice_dir = self.base_path / "invoice"
        schema_path = self.base_path / "tasksupport" / "invoice.schema.json"

        if invoice_dir.exists() and schema_path.exists():
            print("\n=== Invoice Validation ===")
            invoice_results = self.validate_all_invoices(invoice_dir, schema_path)
        else:
            print("Invoice directory or schema file not found, skipping invoice validation")
            invoice_results = []

        # Calculate summary
        all_results = metadata_results + invoice_results
        total = len(all_results)
        valid = sum(1 for r in all_results if r["valid"])
        invalid = total - valid

        self.validation_results["summary"] = {
            "total": total,
            "valid": valid,
            "invalid": invalid,
            "success_rate": (valid / total * 100) if total > 0 else 0
        }

        print(f"\n=== Validation Summary ===")
        print(f"Total files validated: {total}")
        print(f"Valid files: {valid}")
        print(f"Invalid files: {invalid}")
        print(f"Success rate: {self.validation_results['summary']['success_rate']:.1f}%")

        return self.validation_results

    def save_validation_report(self, output_path: Path) -> None:
        """Save detailed validation report to JSON file."""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.validation_results, f, indent=2, ensure_ascii=False)
        print(f"Validation report saved to: {output_path}")

# Usage example
def main():
    # Setup validation manager
    project_path = Path("data")
    validator = ValidationManager(project_path)

    # Run comprehensive validation
    results = validator.validate_project_structure()

    # Save detailed report
    report_path = project_path / "validation_report.json"
    validator.save_validation_report(report_path)

    # Return success status
    return results["summary"]["invalid"] == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
```

### Advanced Validation with Custom Rules

```python
from rdetoolkit.validation import MetadataValidator, InvoiceValidator
from pathlib import Path
import json
from typing import Any, Dict, List

class CustomValidationRules:
    """Custom validation rules for specific business logic."""

    @staticmethod
    def validate_metadata_completeness(metadata: Dict[str, Any]) -> List[str]:
        """Validate that metadata contains all required fields for production."""
        errors = []

        required_fields = ["title", "description", "creator", "created", "keywords"]
        for field in required_fields:
            if field not in metadata or not metadata[field]:
                errors.append(f"Required field '{field}' is missing or empty")

        # Validate date format
        if "created" in metadata:
            try:
                from datetime import datetime
                datetime.fromisoformat(metadata["created"].replace("Z", "+00:00"))
            except ValueError:
                errors.append("Field 'created' must be in ISO 8601 format")

        # Validate keywords
        if "keywords" in metadata:
            if not isinstance(metadata["keywords"], list) or len(metadata["keywords"]) < 3:
                errors.append("Field 'keywords' must be a list with at least 3 items")

        return errors

    @staticmethod
    def validate_invoice_data_quality(invoice: Dict[str, Any]) -> List[str]:
        """Validate invoice data quality and consistency."""
        errors = []

        # Check if sample data exists
        if "sample" not in invoice:
            errors.append("Invoice must contain 'sample' section")
            return errors

        sample = invoice["sample"]

        # Validate general attributes
        if "generalAttributes" in sample:
            gen_attrs = sample["generalAttributes"]
            if not isinstance(gen_attrs, list) or len(gen_attrs) == 0:
                errors.append("generalAttributes must be a non-empty list")

            # Check for duplicate keys
            keys = [attr.get("key") for attr in gen_attrs if isinstance(attr, dict)]
            if len(keys) != len(set(keys)):
                errors.append("Duplicate keys found in generalAttributes")

        # Validate specific attributes
        if "specificAttributes" in sample:
            spec_attrs = sample["specificAttributes"]
            if not isinstance(spec_attrs, list):
                errors.append("specificAttributes must be a list")

            # Validate units for numeric values
            for attr in spec_attrs:
                if isinstance(attr, dict) and "value" in attr:
                    try:
                        float(attr["value"])
                        if "unit" not in attr:
                            errors.append(f"Numeric attribute '{attr.get('key', 'unknown')}' should have a unit")
                    except ValueError:
                        pass  # Non-numeric value, unit not required

        return errors

class EnhancedValidator:
    """Enhanced validator with custom rules and reporting."""

    def __init__(self):
        self.metadata_validator = MetadataValidator()
        self.custom_rules = CustomValidationRules()

    def validate_metadata_enhanced(self, path: Path) -> Dict[str, Any]:
        """Enhanced metadata validation with custom rules."""
        result = {
            "file": str(path),
            "schema_valid": False,
            "custom_valid": False,
            "schema_errors": [],
            "custom_errors": [],
            "data": None
        }

        try:
            # Schema validation
            validated_data = self.metadata_validator.validate(path=path)
            result["schema_valid"] = True
            result["data"] = validated_data

            # Custom rules validation
            custom_errors = self.custom_rules.validate_metadata_completeness(validated_data)
            if custom_errors:
                result["custom_errors"] = custom_errors
            else:
                result["custom_valid"] = True

        except Exception as e:
            result["schema_errors"] = [str(e)]

        return result

    def validate_invoice_enhanced(self, invoice_path: Path, schema_path: Path) -> Dict[str, Any]:
        """Enhanced invoice validation with custom rules."""
        result = {
            "file": str(invoice_path),
            "schema_valid": False,
            "custom_valid": False,
            "schema_errors": [],
            "custom_errors": [],
            "data": None
        }

        try:
            # Schema validation
            invoice_validator = InvoiceValidator(schema_path)
            validated_data = invoice_validator.validate(path=invoice_path)
            result["schema_valid"] = True
            result["data"] = validated_data

            # Custom rules validation
            custom_errors = self.custom_rules.validate_invoice_data_quality(validated_data)
            if custom_errors:
                result["custom_errors"] = custom_errors
            else:
                result["custom_valid"] = True

        except Exception as e:
            result["schema_errors"] = [str(e)]

        return result

# Usage example
def validate_with_custom_rules():
    """Example of using enhanced validation with custom rules."""

    validator = EnhancedValidator()

    # Validate metadata with custom rules
    metadata_path = Path("data/meta/metadata.json")
    if metadata_path.exists():
        result = validator.validate_metadata_enhanced(metadata_path)

        print(f"Metadata Validation Results for {metadata_path.name}:")
        print(f"  Schema Valid: {result['schema_valid']}")
        print(f"  Custom Rules Valid: {result['custom_valid']}")

        if result['schema_errors']:
            print("  Schema Errors:")
            for error in result['schema_errors']:
                print(f"    - {error}")

        if result['custom_errors']:
            print("  Custom Rule Violations:")
            for error in result['custom_errors']:
                print(f"    - {error}")

    # Validate invoice with custom rules
    invoice_path = Path("data/invoice/invoice.json")
    schema_path = Path("data/tasksupport/invoice.schema.json")

    if invoice_path.exists() and schema_path.exists():
        result = validator.validate_invoice_enhanced(invoice_path, schema_path)

        print(f"\nInvoice Validation Results for {invoice_path.name}:")
        print(f"  Schema Valid: {result['schema_valid']}")
        print(f"  Custom Rules Valid: {result['custom_valid']}")

        if result['schema_errors']:
            print("  Schema Errors:")
            for error in result['schema_errors']:
                print(f"    - {error}")

        if result['custom_errors']:
            print("  Custom Rule Violations:")
            for error in result['custom_errors']:
                print(f"    - {error}")

# Run enhanced validation
validate_with_custom_rules()
```

## Error Handling

### Exception Types

The validation module raises specific exceptions for different error conditions:

#### MetadataValidationError
Raised when metadata validation fails against the Pydantic schema.

```python
from rdetoolkit.exceptions import MetadataValidationError

try:
    metadata_validate("invalid_metadata.json")
except MetadataValidationError as e:
    print(f"Metadata validation failed: {e}")
    # Error message contains detailed field-by-field errors
```

#### InvoiceSchemaValidationError
Raised when invoice validation fails against the JSON schema.

```python
from rdetoolkit.exceptions import InvoiceSchemaValidationError

try:
    invoice_validate("invalid_invoice.json", "invoice.schema.json")
except InvoiceSchemaValidationError as e:
    print(f"Invoice validation failed: {e}")
    # Error message contains detailed validation errors with field paths
```

### Error Message Format

Validation errors provide detailed, structured information:

```
Validation Errors in metadata.json. Please correct the following fields
1. Field: title
   Type: missing
   Context: Field required

2. Field: created
   Type: value_error
   Context: invalid datetime format

3. Field: keywords.0
   Type: type_error
   Context: str type expected
```

### Best Practices for Error Handling

1. **Catch Specific Exceptions**:
   ```python
   def safe_validate_metadata(file_path: str) -> Tuple[bool, List[str]]:
       """Safely validate metadata and return status with errors."""
       try:
           metadata_validate(file_path)
           return True, []
       except FileNotFoundError:
           return False, [f"File not found: {file_path}"]
       except MetadataValidationError as e:
           return False, [str(e)]
       except Exception as e:
           return False, [f"Unexpected error: {e}"]
   ```

2. **Provide User-Friendly Error Messages**:
   ```python
   def validate_with_user_feedback(metadata_path: str):
       """Validate with user-friendly error reporting."""
       success, errors = safe_validate_metadata(metadata_path)

       if success:
           print("✅ Validation successful!")
       else:
           print("❌ Validation failed:")
           for error in errors:
               print(f"   {error}")
           print("\nPlease fix the errors and try again.")
   ```

3. **Implement Retry Logic**:
   ```python
   def validate_with_retry(file_path: str, max_retries: int = 3) -> bool:
       """Validate with retry logic for transient errors."""
       for attempt in range(max_retries):
           try:
               metadata_validate(file_path)
               return True
           except FileNotFoundError:
               return False  # Don't retry for missing files
           except MetadataValidationError:
               return False  # Don't retry for validation errors
           except Exception as e:
               if attempt == max_retries - 1:
                   raise  # Re-raise on final attempt
               print(f"Attempt {attempt + 1} failed: {e}. Retrying...")
               time.sleep(1)  # Brief delay before retry

       return False
   ```

## Performance Notes

### Optimization Strategies

1. **Schema Caching**: InvoiceValidator caches loaded schemas to avoid repeated file I/O
2. **Lazy Loading**: Validators only load schemas when first used
3. **Memory Management**: Large JSON files are processed efficiently with streaming where possible
4. **Validation Short-Circuiting**: Validation stops at first critical error to save processing time

### Performance Considerations

- **File Size**: Large invoice files (>10MB) may require additional memory
- **Schema Complexity**: Complex schemas with many nested validations impact performance
- **Batch Processing**: Use validator instances for multiple files to benefit from schema caching
- **Error Reporting**: Detailed error collection can impact performance for large files with many errors

### Performance Best Practices

```python
# Efficient batch validation
def efficient_batch_validation(file_paths: List[Path], schema_path: Path):
    """Efficiently validate multiple files using cached validator."""

    # Create validator once for all files
    invoice_validator = InvoiceValidator(schema_path)
    metadata_validator = MetadataValidator()

    results = []
    for file_path in file_paths:
        try:
            if file_path.name.startswith('metadata'):
                metadata_validator.validate(path=file_path)
            elif file_path.name.startswith('invoice'):
                invoice_validator.validate(path=file_path)
            results.append((file_path, True, None))
        except Exception as e:
            results.append((file_path, False, str(e)))

    return results
```

## See Also

- [Core Module](core.md) - For file operations and encoding detection
- [Models - Metadata](models/metadata.md) - For metadata data structures
- [Models - Invoice Schema](models/invoice_schema.md) - For invoice schema definitions
- [Exceptions](exceptions.md) - For validation exception types
- [File Operations](fileops.md) - For JSON file reading utilities
- [Usage - Validation](../usage/validation.md) - For practical validation examples
- [Usage - Structured Process](../../usage/structured_process/structured.md) - For validation in workflows
- [Usage - Error Handling](../../usage/structured_process/errorhandling.md) - For error handling strategies
