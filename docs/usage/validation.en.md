# Validation Features

## Overview

RDEToolKit implements comprehensive validation features to ensure the integrity and quality of RDE-related files. By performing pre-checks during local development, you can prevent errors when registering with RDE.

## Prerequisites

- RDEToolKit installation
- Basic understanding of template files
- Python 3.9 or higher

## Validation Target Files

Main files subject to validation in RDEToolKit:

- **invoice.schema.json**: Invoice schema file
- **invoice.json**: Invoice data file
- **metadata-def.json**: Metadata definition file
- **metadata.json**: Metadata file

!!! warning "Important"
    These files can be modified within structured processing, making pre-validation crucial.

!!! note "Related Documentation"
    [About Template Files](metadata_definition_file.en.md)

## invoice.schema.json Validation

### Overview

`invoice.schema.json` is a schema file that configures RDE screens. It provides check functionality to verify that necessary fields are defined when modifying during structured processing or creating definition files locally.

### Basic Usage

```python title="invoice.schema.json Validation"
import json
from pydantic import ValidationError

from rdetoolkit.validation import InvoiceValidator
from rdetoolkit.exceptions import InvoiceSchemaValidationError

# Schema definition
schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://rde.nims.go.jp/rde/dataset-templates/dataset_template_custom_sample/invoice.schema.json",
    "description": "RDE dataset template sample custom information invoice",
    "type": "object",
    "required": ["custom", "sample"],
    "properties": {
        "custom": {
            "type": "object",
            "label": {"ja": "固有情報", "en": "Custom Information"},
            "required": ["sample1"],
            "properties": {
                "sample1": {
                    "label": {"ja": "サンプル１", "en": "sample1"},
                    "type": "string",
                    "format": "date",
                    "options": {"unit": "A"}
                },
                "sample2": {
                    "label": {"ja": "サンプル２", "en": "sample2"},
                    "type": "number",
                    "options": {"unit": "b"}
                },
            },
        },
        "sample": {
            "type": "object",
            "label": {"ja": "試料情報", "en": "Sample Information"},
            "properties": {
                "generalAttributes": {
                    "type": "array",
                    "items": [
                        {
                            "type": "object",
                            "required": ["termId"],
                            "properties": {
                                "termId": {
                                    "const": "3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e"
                                }
                            }
                        }
                    ],
                },
                "specificAttributes": {"type": "array", "items": []},
            },
        },
    },
}

# Data example
data = {
    "datasetId": "1s1199df4-0d1v-41b0-1dea-23bf4dh09g12",
    "basic": {
        "dateSubmitted": "",
        "dataOwnerId": "0c233ef274f28e611de4074638b4dc43e737ab993132343532343430",
        "dataName": "test-dataset",
        "instrumentId": None,
        "experimentId": None,
        "description": None,
    },
    "custom": {"sample1": "2023-01-01", "sample2": 1.0},
    "sample": {
        "sampleId": "",
        "names": ["test"],
        "composition": None,
        "referenceUrl": None,
        "description": None,
        "generalAttributes": [
            {"termId": "3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e", "value": None}
        ],
        "specificAttributes": [],
        "ownerId": "de17c7b3f0ff5126831c2d519f481055ba466ddb6238666132316439",
    },
}

# Save schema file
with open("temp/invoice.schema.json", "w") as f:
    json.dump(schema, f, ensure_ascii=False, indent=2)

# Execute validation
validator = InvoiceValidator("temp/invoice.schema.json")
try:
    validator.validate(obj=data)
    print("Validation successful")
except ValidationError as validation_error:
    raise InvoiceSchemaValidationError from validation_error
```

### Handling Validation Errors

When `invoice.schema.json` validation errors occur, `pydantic_core._pydantic_core.ValidationError` is raised.

!!! note "Reference"
    [pydantic_core._pydantic_core.ValidationError - Pydantic](https://docs.pydantic.dev/latest/errors/validation_errors/)

#### Reading Error Messages

Error messages display the following information:

- **Field causing the error**
- **Error type**
- **Error message**

```shell title="Error Example"
1. Field: required.0
   Type: literal_error
   Context: Input should be 'custom' or 'sample'
```

This example indicates that the `required` field must contain `custom` or `sample`.

#### Common Errors and Fixes

**Error Example:**
```json title="Problematic Schema"
{
    "required": ["custom"], // sample is defined but not included
    "properties": {
        "custom": { /* ... */ },
        "sample": { /* ... */ }
    }
}
```

**Fix:**
```json title="Corrected Schema"
{
    "required": ["custom", "sample"], // Include both
    "properties": {
        "custom": { /* ... */ },
        "sample": { /* ... */ }
    }
}
```

## invoice.json Validation

### Overview

`invoice.json` validation requires the corresponding `invoice.schema.json`. It checks data integrity according to constraints defined in the schema.

### Basic Usage

```python title="invoice.json Validation"
# Using the schema and data from above
validator = InvoiceValidator("temp/invoice.schema.json")
try:
    validator.validate(obj=data)
    print("invoice.json validation successful")
except ValidationError as validation_error:
    print(f"Validation error: {validation_error}")
```

### Sample Information Validation

When developing structured processing in a local environment, you need to prepare `invoice.json` (invoice) in advance. When defining sample information, the following two cases are expected:

#### 1. Adding New Sample Information

In this case, `sampleId`, `names`, and `ownerId` in the `sample` field are required.

```json title="New Sample Information"
"sample": {
    "sampleId": "de1132316439",
    "names": ["test"],
    "composition": null,
    "referenceUrl": null,
    "description": null,
    "generalAttributes": [
        {"termId": "3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e", "value": null}
    ],
    "specificAttributes": [],
    "ownerId": "de17c7b3f0ff5126831c2d519f481055ba466ddb6238666132316439"
}
```

#### 2. Referencing Existing Sample Information

In this case, only `sampleId` in the `sample` field is required.

```json title="Existing Sample Information Reference"
"sample": {
    "sampleId": "de1132316439",
    "names": [],
    "composition": null,
    "referenceUrl": null,
    "description": null,
    "generalAttributes": [
        {"termId": "3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e", "value": null}
    ],
    "specificAttributes": [],
    "ownerId": "de17c7b3f0ff5126831c2d519f481055ba466ddb6238666132316439"
}
```

### Sample Information Validation Errors

If neither of the above two cases is satisfied, validation errors will occur.

```shell title="Sample Information Error Example"
Error: Error in validating system standard field.
Please correct the following fields in invoice.json
Field: sample
Type: anyOf
Context: {'sampleId': '', 'names': 'test', 'generalAttributes': [...], 'specificAttributes': [], 'ownerId': ''} is not valid under any of the given schemas
```

### Other Validation Errors

When there are deficiencies or invalid values in the `basic` items of `invoice.json`, `jsonschema` validation errors occur.

```shell title="Basic Information Error Example"
Error: Error in validating system standard item in invoice.schema.json.
Please correct the following fields in invoice.json
Field: basic.dataOwnerId
Type: pattern
Context: String does not match expected pattern
```

## metadata-def.json Validation

### Overview

`metadata-def.json` is a file that defines the structure and constraints of metadata. Validation of this file ensures the integrity of metadata schemas.

### Basic Usage

```python title="metadata-def.json Validation"
from rdetoolkit.validation import MetadataValidator

# Metadata definition file validation
metadata_validator = MetadataValidator("path/to/metadata-def.json")
try:
    metadata_validator.validate_schema()
    print("metadata-def.json validation successful")
except ValidationError as e:
    print(f"Metadata definition validation error: {e}")
```

## metadata.json Validation

### Overview

`metadata.json` is the actual metadata file based on the schema defined in `metadata-def.json`.

### Basic Usage

```python title="metadata.json Validation"
# Metadata file validation
try:
    metadata_validator.validate_data("path/to/metadata.json")
    print("metadata.json validation successful")
except ValidationError as e:
    print(f"Metadata validation error: {e}")
```

## Integrated Validation

### Automatic Validation in Workflows

Validation is automatically executed when running RDEToolKit workflows:

```python title="Workflow Integrated Validation"
from rdetoolkit import workflows

def my_dataset_function(rde):
    # Data processing logic
    rde.set_metadata({"status": "processed"})
    return 0

# Automatic validation is executed during workflow execution
try:
    result = workflows.run(my_dataset_function)
    print("Workflow execution successful")
except Exception as e:
    print(f"Workflow execution error (including validation): {e}")
```

## Best Practices

### Validation Strategy During Development

1. **Staged Validation**
   - Validate schema files first
   - Validate data files later

2. **Continuous Checking**
   - Automatic validation on file changes
   - Validation in CI/CD pipelines

3. **Error Handling**
   - Utilize detailed error messages
   - Gradual error correction

### Troubleshooting

#### Common Issues and Solutions

1. **Schema Syntax Errors**
   - Check JSON syntax
   - Verify required fields

2. **Data Type Mismatches**
   - Compare with types defined in schema
   - Check default values

3. **Reference Errors**
   - Verify file paths
   - Check file existence

## Practical Example

### Complete Validation Workflow

```python title="Complete Validation Example"
import json
from pathlib import Path
from rdetoolkit.validation import InvoiceValidator, MetadataValidator
from rdetoolkit.exceptions import InvoiceSchemaValidationError

def validate_all_files(project_dir: Path):
    """Validate all files in the project"""
    
    # 1. invoice.schema.json validation
    schema_path = project_dir / "tasksupport" / "invoice.schema.json"
    invoice_path = project_dir / "invoice" / "invoice.json"
    
    try:
        invoice_validator = InvoiceValidator(schema_path)
        print("✓ invoice.schema.json validation successful")
        
        # 2. invoice.json validation
        with open(invoice_path) as f:
            invoice_data = json.load(f)
        
        invoice_validator.validate(obj=invoice_data)
        print("✓ invoice.json validation successful")
        
    except ValidationError as e:
        print(f"✗ Invoice validation error: {e}")
        return False
    
    # 3. metadata-def.json validation
    metadata_def_path = project_dir / "tasksupport" / "metadata-def.json"
    metadata_path = project_dir / "metadata.json"
    
    try:
        metadata_validator = MetadataValidator(metadata_def_path)
        metadata_validator.validate_schema()
        print("✓ metadata-def.json validation successful")
        
        # 4. metadata.json validation
        if metadata_path.exists():
            metadata_validator.validate_data(metadata_path)
            print("✓ metadata.json validation successful")
        
    except ValidationError as e:
        print(f"✗ Metadata validation error: {e}")
        return False
    
    print("🎉 All file validation completed")
    return True

# Usage example
project_directory = Path("./my_rde_project")
validate_all_files(project_directory)
```

## Next Steps

- Learn schema definition details in [Template Files](metadata_definition_file.en.md)
- Understand validation usage in [Structured Processing](../user-guide/structured-processing.en.md)
- Check detailed validation features in [API Reference](../rdetoolkit/validation.md)
