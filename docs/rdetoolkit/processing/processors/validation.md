# Validation Processors

The `rdetoolkit.processing.processors.validation` module provides validation processors that ensure data integrity and compliance with schemas. These processors validate invoice files and metadata against predefined schemas and validation rules.

## Overview

The validation processors provide:

- **Invoice Validation**: Validate invoice.json files against JSON schemas
- **Metadata Validation**: Validate metadata.json files for completeness and format
- **Schema Compliance**: Ensure data structure compliance with RDE standards
- **Error Reporting**: Comprehensive error reporting for validation failures
- **Optional Validation**: Graceful handling when files don't exist

## Classes

### InvoiceValidator

Validates invoice files against JSON schema specifications.

#### Constructor

```python
InvoiceValidator()
```

No parameters required. Inherits from `Processor` base class.

#### Methods

##### process(context)

Validate invoice.json against schema.

```python
def process(context: ProcessingContext) -> None
```

**Parameters:**
- `context` (ProcessingContext): Processing context containing invoice and schema paths

**Returns:**
- `None`

**Raises:**
- `Exception`: If invoice validation fails

**Example:**
```python
from rdetoolkit.processing.processors.validation import InvoiceValidator

validator = InvoiceValidator()
validator.process(context)  # Validates invoice against schema
```

**Required Context Attributes:**
- `context.invoice_dst_filepath`: Path to invoice.json file to validate
- `context.schema_path`: Path to JSON schema file for validation

**Validation Process:**
1. Loads invoice.json file
2. Loads JSON schema file
3. Performs schema validation using jsonschema library
4. Reports any validation errors with detailed messages

### MetadataValidator

Validates metadata.json files for completeness and format compliance.

#### Constructor

```python
MetadataValidator()
```

No parameters required. Inherits from `Processor` base class.

#### Methods

##### process(context)

Validate metadata.json if it exists.

```python
def process(context: ProcessingContext) -> None
```

**Parameters:**
- `context` (ProcessingContext): Processing context containing metadata path

**Returns:**
- `None`

**Raises:**
- `Exception`: If metadata validation fails

**Example:**
```python
from rdetoolkit.processing.processors.validation import MetadataValidator

validator = MetadataValidator()
validator.process(context)  # Validates metadata if present
```

**Required Context Attributes:**
- `context.metadata_path`: Path to metadata.json file

**Validation Behavior:**
- If metadata.json doesn't exist, validation is skipped gracefully
- If metadata.json exists, it's validated for format and completeness
- Validation errors are logged and raised for pipeline handling

## Complete Usage Examples

### Basic Invoice Validation

```python
from rdetoolkit.processing.processors.validation import InvoiceValidator
from rdetoolkit.processing.context import ProcessingContext
from pathlib import Path

# Create invoice validator
validator = InvoiceValidator()

# Create processing context with paths
context = ProcessingContext(
    invoice_dst_filepath=Path("output/invoice.json"),
    schema_path=Path("schemas/invoice_schema.json"),
    # ... other parameters
)

# Validate invoice
try:
    validator.process(context)
    print("Invoice validation passed")
except Exception as e:
    print(f"Invoice validation failed: {e}")
```

### Basic Metadata Validation

```python
from rdetoolkit.processing.processors.validation import MetadataValidator
from pathlib import Path

# Create metadata validator
validator = MetadataValidator()

# Create processing context
context = ProcessingContext(
    metadata_path=Path("output/metadata.json"),
    # ... other parameters
)

# Validate metadata
try:
    validator.process(context)
    print("Metadata validation passed")
except Exception as e:
    print(f"Metadata validation failed: {e}")
```

### Combined Validation Pipeline

```python
from rdetoolkit.processing.processors.validation import InvoiceValidator, MetadataValidator
from rdetoolkit.processing.pipeline import ProcessingPipeline

# Create validation pipeline
pipeline = ProcessingPipeline()

# Add validation processors
pipeline.add_processor(InvoiceValidator())
pipeline.add_processor(MetadataValidator())

# Execute validation pipeline
try:
    pipeline.process(context)
    print("All validation checks passed")
except Exception as e:
    print(f"Validation failed: {e}")
```

### Validation with Error Handling

```python
from rdetoolkit.processing.processors.validation import InvoiceValidator, MetadataValidator
import logging

# Setup logging
logger = logging.getLogger(__name__)

def validate_with_detailed_logging(context):
    """Validate with detailed error logging."""

    # Invoice validation
    invoice_validator = InvoiceValidator()
    try:
        invoice_validator.process(context)
        logger.info("Invoice validation: PASSED")
    except Exception as e:
        logger.error(f"Invoice validation: FAILED - {e}")
        raise

    # Metadata validation
    metadata_validator = MetadataValidator()
    try:
        metadata_validator.process(context)
        logger.info("Metadata validation: PASSED")
    except Exception as e:
        logger.error(f"Metadata validation: FAILED - {e}")
        raise

    logger.info("All validation checks completed successfully")

# Execute validation
try:
    validate_with_detailed_logging(context)
except Exception as e:
    logger.error(f"Validation pipeline failed: {e}")
```

### Conditional Validation

```python
from rdetoolkit.processing.processors.validation import InvoiceValidator, MetadataValidator
from pathlib import Path

def conditional_validation(context):
    """Perform validation based on file existence."""

    validation_results = {
        "invoice_validated": False,
        "metadata_validated": False,
        "errors": []
    }

    # Check if invoice exists before validation
    if context.invoice_dst_filepath.exists():
        try:
            invoice_validator = InvoiceValidator()
            invoice_validator.process(context)
            validation_results["invoice_validated"] = True
        except Exception as e:
            validation_results["errors"].append(f"Invoice validation: {e}")
    else:
        validation_results["errors"].append("Invoice file not found")

    # Check if metadata exists before validation
    if context.metadata_path.exists():
        try:
            metadata_validator = MetadataValidator()
            metadata_validator.process(context)
            validation_results["metadata_validated"] = True
        except Exception as e:
            validation_results["errors"].append(f"Metadata validation: {e}")
    else:
        print("Metadata file not found - skipping validation")

    return validation_results

# Execute conditional validation
results = conditional_validation(context)
print(f"Validation results: {results}")
```

### Custom Validation Workflow

```python
from rdetoolkit.processing.processors.validation import InvoiceValidator, MetadataValidator
import json
from pathlib import Path

class ValidationWorkflow:
    """Custom validation workflow with reporting."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.validation_report = {
            "timestamp": None,
            "invoice_validation": {"status": "pending", "errors": []},
            "metadata_validation": {"status": "pending", "errors": []},
            "overall_status": "pending"
        }

    def run_validation(self, context):
        """Run complete validation workflow."""
        import datetime

        self.validation_report["timestamp"] = datetime.datetime.now().isoformat()

        # Invoice validation
        self._validate_invoice(context)

        # Metadata validation
        self._validate_metadata(context)

        # Determine overall status
        self._determine_overall_status()

        # Save validation report
        self._save_report()

        return self.validation_report

    def _validate_invoice(self, context):
        """Validate invoice with error capture."""
        try:
            validator = InvoiceValidator()
            validator.process(context)
            self.validation_report["invoice_validation"]["status"] = "passed"
        except Exception as e:
            self.validation_report["invoice_validation"]["status"] = "failed"
            self.validation_report["invoice_validation"]["errors"].append(str(e))

    def _validate_metadata(self, context):
        """Validate metadata with error capture."""
        try:
            validator = MetadataValidator()
            validator.process(context)
            self.validation_report["metadata_validation"]["status"] = "passed"
        except Exception as e:
            self.validation_report["metadata_validation"]["status"] = "failed"
            self.validation_report["metadata_validation"]["errors"].append(str(e))

    def _determine_overall_status(self):
        """Determine overall validation status."""
        invoice_passed = self.validation_report["invoice_validation"]["status"] == "passed"
        metadata_passed = self.validation_report["metadata_validation"]["status"] == "passed"

        if invoice_passed and metadata_passed:
            self.validation_report["overall_status"] = "passed"
        else:
            self.validation_report["overall_status"] = "failed"

    def _save_report(self):
        """Save validation report to file."""
        report_path = self.output_dir / "validation_report.json"
        with open(report_path, 'w') as f:
            json.dump(self.validation_report, f, indent=2)

# Usage
workflow = ValidationWorkflow(Path("output"))
report = workflow.run_validation(context)
print(f"Validation completed. Overall status: {report['overall_status']}")
```

## Schema Validation Details

### Invoice Schema Validation

The invoice validation process follows these steps:

1. **Schema Loading**: Load JSON schema from `context.schema_path`
2. **Invoice Loading**: Load invoice data from `context.invoice_dst_filepath`
3. **Validation**: Use jsonschema library to validate structure
4. **Error Reporting**: Provide detailed error messages for failures

**Common Invoice Validation Errors:**
```python
# Missing required fields
{
    "error": "ValidationError",
    "message": "'dataName' is a required property",
    "path": "$.basic"
}

# Invalid data types
{
    "error": "ValidationError",
    "message": "'25.5' is not of type 'number'",
    "path": "$.sample.generalAttributes[0].value"
}

# Invalid enum values
{
    "error": "ValidationError",
    "message": "'invalid_status' is not one of ['active', 'inactive', 'pending']",
    "path": "$.basic.status"
}
```

### Metadata Validation

Metadata validation checks for:

- **File Format**: Valid JSON structure
- **Required Fields**: Presence of mandatory metadata fields
- **Data Types**: Correct data types for all fields
- **Value Constraints**: Valid values within acceptable ranges

**Example Metadata Structure:**
```json
{
    "version": "1.0",
    "created": "2024-01-01T00:00:00Z",
    "modified": "2024-01-01T00:00:00Z",
    "description": "Sample metadata",
    "keywords": ["research", "data"],
    "contributors": [
        {
            "name": "John Doe",
            "role": "researcher"
        }
    ]
}
```

## Error Handling

### Validation Error Types

#### Schema Validation Errors
```python
try:
    validator.process(context)
except jsonschema.ValidationError as e:
    print(f"Schema validation failed: {e.message}")
    print(f"Failed at path: {e.absolute_path}")
    print(f"Invalid value: {e.instance}")
```

#### File Not Found Errors
```python
try:
    validator.process(context)
except FileNotFoundError as e:
    print(f"Validation file not found: {e}")
    # Handle missing schema or data files
```

#### JSON Parse Errors
```python
try:
    validator.process(context)
except json.JSONDecodeError as e:
    print(f"Invalid JSON format: {e}")
    print(f"Error at line {e.lineno}, column {e.colno}")
```

### Best Practices

1. **Always handle validation errors gracefully**:
   ```python
   try:
       validator.process(context)
   except Exception as e:
       logger.error(f"Validation failed: {e}")
       # Decide whether to continue or abort processing
   ```

2. **Verify file existence before validation**:
   ```python
   if context.invoice_dst_filepath.exists():
       validator.process(context)
   else:
       logger.warning("Invoice file not found for validation")
   ```

3. **Use appropriate logging levels**:
   ```python
   logger.debug("Starting validation process")
   try:
       validator.process(context)
       logger.info("Validation completed successfully")
   except Exception as e:
       logger.error(f"Validation failed: {e}")
   ```

4. **Validate schema files themselves**:
   ```python
   if not context.schema_path.exists():
       raise FileNotFoundError(f"Schema file not found: {context.schema_path}")

   # Optionally validate schema format
   try:
       with open(context.schema_path) as f:
           json.load(f)
   except json.JSONDecodeError as e:
       raise ValueError(f"Invalid schema file format: {e}")
   ```

## Integration with Processing Pipeline

### Pipeline Integration

```python
from rdetoolkit.processing.pipeline import ProcessingPipeline
from rdetoolkit.processing.processors.validation import InvoiceValidator, MetadataValidator

# Create processing pipeline
pipeline = ProcessingPipeline()

# Add other processors first
# pipeline.add_processor(InvoiceInitializer())
# pipeline.add_processor(FileProcessor())

# Add validation processors at the end
pipeline.add_processor(InvoiceValidator())
pipeline.add_processor(MetadataValidator())

# Execute pipeline with validation
pipeline.process(context)
```

### Validation-First Approach

```python
# Validate before processing
def validate_inputs(context):
    """Validate inputs before main processing."""
    if context.metadata_path.exists():
        metadata_validator = MetadataValidator()
        metadata_validator.process(context)

# Validate after processing
def validate_outputs(context):
    """Validate outputs after main processing."""
    invoice_validator = InvoiceValidator()
    invoice_validator.process(context)

# Main processing workflow
validate_inputs(context)
# ... main processing ...
validate_outputs(context)
```

## Performance Notes

- Validation processors are lightweight with minimal overhead
- JSON schema validation performance depends on schema complexity
- File I/O operations are optimized for typical file sizes
- Validation errors include detailed path information for debugging
- Logging is optimized to minimize performance impact

## See Also

- [Processing Context](../context.md) - For understanding processing context structure
- [Pipeline Documentation](../pipeline.md) - For processor pipeline integration
- [Invoice Processors](invoice.md) - For invoice creation and initialization
- [Validation Module](../../validation.md) - For core validation functions
