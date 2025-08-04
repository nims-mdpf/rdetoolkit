# Metadata Models API

## Purpose

This module defines data models for metadata management in RDEToolKit. It provides structured metadata definitions, validation models, and type-safe representations for metadata files used in structured data processing.

## Key Features

### Metadata Structure Models
- Comprehensive metadata structure definitions
- Pydantic-based validation and serialization
- Type-safe metadata representation

### Data Validation
- Schema validation for metadata files
- Field validation with descriptive error messages
- Automatic type conversion and validation

---

::: src.rdetoolkit.models.metadata

---

## Practical Usage

### Basic Metadata Model Usage

```python title="basic_metadata.py"
from rdetoolkit.models.metadata import MetadataItem
from rdetoolkit.validation import metadata_validate
from pathlib import Path

# Validate metadata file
metadata_path = Path("data/meta/metadata.json")
try:
    metadata_validate(metadata_path)
    print("Metadata validation successful")
except Exception as e:
    print(f"Validation error: {e}")
```
