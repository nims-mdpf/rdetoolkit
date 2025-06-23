# Metadata Module

The `rdetoolkit.models.metadata` module provides Pydantic models for handling metadata extracted during RDE data structuring processes. This module implements validation rules for metadata values and provides a structured approach to managing both constant and variable metadata attributes.

## Overview

The metadata module implements a comprehensive validation system for metadata handling with the following capabilities:

- **Size Validation**: Automatic validation of metadata value sizes with configurable limits
- **Type Safety**: Strong typing with runtime validation using Pydantic models
- **Structured Storage**: Separation of constant and variable metadata types
- **UTF-8 Encoding Support**: Proper handling of multi-byte character encodings
- **Flexible Value Types**: Support for various data types while maintaining validation

## Constants

### MAX_VALUE_SIZE

The maximum allowed size for metadata values in bytes.

```python
MAX_VALUE_SIZE: Final[int] = 1024
```

This constant defines the size limit for individual metadata values. Values exceeding this limit will raise a validation error during model creation.

## Core Classes

### Variable

Model for handling variable-type metadata attributes.

#### Constructor for `Variable`

```python
Variable(variable: dict[str, Any])
```

**Parameters:**

- `variable` (dict[str, Any]): Dictionary containing variable metadata with string keys and any value types

#### Validation Rules for `Variable`

- All string values in the dictionary must not exceed `MAX_VALUE_SIZE` bytes when UTF-8 encoded
- Non-string values are not subject to size validation
- Empty dictionaries are allowed

#### Example: Variable

```python
from rdetoolkit.models.metadata import Variable

# Valid variable metadata
valid_variable = Variable(variable={
    "temperature": "25.5",
    "pressure": "1013.25",
    "humidity": "60%",
    "operator": "John Doe"
})

# Invalid - value too large (will raise ValueError)
try:
    large_value = "x" * 2000  # 2000 bytes
    invalid_variable = Variable(variable={"description": large_value})
except ValueError as e:
    print(f"Validation error: {e}")
```

### MetaValue

Model for handling individual metadata values with optional units.

#### Constructor for `MetaValue`

```python
MetaValue(value: Any, unit: str | None = None)
```

**Parameters:**

- `value` (Any): The metadata value (can be any type)
- `unit` (str | None): Optional unit description (default: None)

#### Validation Rules for `MetaValue`

- If `value` is a string, it must not exceed `MAX_VALUE_SIZE` bytes when UTF-8 encoded
- Non-string values are not subject to size validation
- The `unit` field is optional and can be None

#### Example: MetaValue

```python
from rdetoolkit.models.metadata import MetaValue

# Numeric value with unit
temperature = MetaValue(value=25.5, unit="°C")

# String value without unit
sample_id = MetaValue(value="SAMPLE_001")

# Complex value (not size-validated)
data_array = MetaValue(value=[1, 2, 3, 4, 5], unit="counts")

# Boolean value
is_calibrated = MetaValue(value=True)

print(temperature.value)  # 25.5
print(temperature.unit)   # "°C"
print(sample_id.unit)     # None
```

### ValidableItems

Container for collections of validatable metadata items.

#### Constructor for `ValidableItems`

```python
ValidableItems(root: list[dict[str, MetaValue]])
```

**Parameters:**

- `root` (list[dict[str, MetaValue]]): List of dictionaries mapping string keys to MetaValue instances

#### Methods

The class inherits from `RootModel` and provides standard list-like access to the underlying data.

#### Example: ValidableItems

```python
from rdetoolkit.models.metadata import ValidableItems, MetaValue

# Create metadata items
items = ValidableItems(root=[
    {
        "measurement_1": MetaValue(value=25.0, unit="°C"),
        "timestamp_1": MetaValue(value="2025-01-15T10:00:00Z")
    },
    {
        "measurement_2": MetaValue(value=26.5, unit="°C"),
        "timestamp_2": MetaValue(value="2025-01-15T10:05:00Z")
    }
])

# Access items
print(len(items.root))  # 2
print(items.root[0]["measurement_1"].value)  # 25.0
```

### MetadataItem

Main metadata container representing the complete metadata structure for a dataset.

#### Constructor

```python
MetadataItem(
    constant: dict[str, MetaValue],
    variable: ValidableItems
)
```

**Parameters:**

- `constant` (dict[str, MetaValue]): Dictionary of constant metadata that applies to all measurements
- `variable` (ValidableItems): Collection of variable metadata that changes between measurements

#### Example

```python
from rdetoolkit.models.metadata import MetadataItem, MetaValue, ValidableItems

# Define constant metadata
constant_meta = {
    "instrument": MetaValue(value="XRD_Analyzer_v2", unit=None),
    "operator": MetaValue(value="Dr. Smith"),
    "calibration_date": MetaValue(value="2025-01-01"),
    "lab_temperature": MetaValue(value=22.0, unit="°C")
}

# Define variable metadata
variable_meta = ValidableItems(root=[
    {
        "sample_temp": MetaValue(value=100.0, unit="°C"),
        "measurement_time": MetaValue(value="2025-01-15T10:00:00Z"),
        "scan_rate": MetaValue(value=0.5, unit="°/min")
    },
    {
        "sample_temp": MetaValue(value=150.0, unit="°C"),
        "measurement_time": MetaValue(value="2025-01-15T11:00:00Z"),
        "scan_rate": MetaValue(value=1.0, unit="°/min")
    }
])

# Create complete metadata
metadata = MetadataItem(
    constant=constant_meta,
    variable=variable_meta
)

# Access metadata
print(metadata.constant["instrument"].value)  # "XRD_Analyzer_v2"
print(metadata.variable.root[0]["sample_temp"].value)  # 100.0
```

## Complete Usage Examples

### Creating Metadata for Scientific Measurements

```python
from rdetoolkit.models.metadata import MetadataItem, MetaValue, ValidableItems

def create_xrd_metadata(measurements: list[dict]) -> MetadataItem:
    """Create metadata for XRD measurement series."""

    # Constant metadata - same for all measurements
    constant = {
        "instrument_model": MetaValue(value="Rigaku MiniFlex", unit=None),
        "x_ray_source": MetaValue(value="Cu Kα", unit=None),
        "wavelength": MetaValue(value=1.5406, unit="Å"),
        "detector_type": MetaValue(value="NaI scintillation"),
        "operator": MetaValue(value="Lab Technician A"),
        "facility": MetaValue(value="Materials Analysis Lab"),
        "calibration_standard": MetaValue(value="Si powder")
    }

    # Variable metadata - changes per measurement
    variable_data = []
    for i, measurement in enumerate(measurements):
        variable_data.append({
            "measurement_id": MetaValue(value=f"XRD_{i+1:03d}"),
            "sample_temperature": MetaValue(
                value=measurement.get("temperature", 25.0),
                unit="°C"
            ),
            "scan_range_start": MetaValue(
                value=measurement.get("start_angle", 10.0),
                unit="°"
            ),
            "scan_range_end": MetaValue(
                value=measurement.get("end_angle", 80.0),
                unit="°"
            ),
            "step_size": MetaValue(
                value=measurement.get("step_size", 0.02),
                unit="°"
            ),
            "scan_speed": MetaValue(
                value=measurement.get("scan_speed", 1.0),
                unit="°/min"
            ),
            "measurement_time": MetaValue(
                value=measurement.get("timestamp", "2025-01-15T10:00:00Z")
            )
        })

    return MetadataItem(
        constant=constant,
        variable=ValidableItems(root=variable_data)
    )

# Usage example
measurements = [
    {
        "temperature": 25.0,
        "start_angle": 10.0,
        "end_angle": 80.0,
        "step_size": 0.02,
        "scan_speed": 1.0,
        "timestamp": "2025-01-15T10:00:00Z"
    },
    {
        "temperature": 100.0,
        "start_angle": 15.0,
        "end_angle": 75.0,
        "step_size": 0.01,
        "scan_speed": 0.5,
        "timestamp": "2025-01-15T11:30:00Z"
    }
]

xrd_metadata = create_xrd_metadata(measurements)
print(f"Created metadata for {len(xrd_metadata.variable.root)} measurements")
```

### Handling Large Text Metadata with Validation

```python
from rdetoolkit.models.metadata import MetaValue, Variable
from pydantic import ValidationError

def safe_create_metadata(value: str, unit: str = None) -> MetaValue | None:
    """Safely create metadata with size validation."""
    try:
        return MetaValue(value=value, unit=unit)
    except ValidationError as e:
        print(f"Validation failed for value: {e}")
        return None

# Test with various value sizes
test_values = [
    "Short description",
    "Medium length description that might be acceptable",
    "Very long description that exceeds the maximum allowed size limit" * 50,  # Too long
    "日本語の説明文です。UTF-8エンコーディングでバイト数をチェックします。",
    "🌟 Unicode emoji and special characters 🔬",
]

metadata_items = []
for i, value in enumerate(test_values):
    meta = safe_create_metadata(value, "description")
    if meta:
        metadata_items.append({f"item_{i}": meta})
        print(f"✓ Created metadata for item {i}")
    else:
        print(f"✗ Failed to create metadata for item {i}")

print(f"Successfully created {len(metadata_items)} metadata items")
```

### Working with Complex Data Types

```python
from rdetoolkit.models.metadata import MetaValue, MetadataItem, ValidableItems
import json
from datetime import datetime

# Handling various data types
metadata_examples = {
    # Numeric values
    "temperature": MetaValue(value=25.5, unit="°C"),
    "pressure": MetaValue(value=1013.25, unit="hPa"),
    "count": MetaValue(value=12345, unit="counts"),

    # String values
    "sample_id": MetaValue(value="SAMPLE_2025_001"),
    "batch_number": MetaValue(value="BATCH_A001"),

    # Boolean values
    "is_calibrated": MetaValue(value=True),
    "quality_check_passed": MetaValue(value=False),

    # List/Array values (not size validated)
    "wavelengths": MetaValue(value=[400, 500, 600, 700], unit="nm"),
    "coordinates": MetaValue(value=[10.5, 20.3, 30.1], unit="mm"),

    # Dictionary values (not size validated)
    "settings": MetaValue(value={
        "gain": 1.5,
        "offset": 0.1,
        "mode": "auto"
    }),

    # None values
    "optional_field": MetaValue(value=None),
}

# Create metadata with mixed types
mixed_metadata = MetadataItem(
    constant=metadata_examples,
    variable=ValidableItems(root=[])
)

# Access and display metadata
for key, meta_value in mixed_metadata.constant.items():
    print(f"{key}: {meta_value.value} {meta_value.unit or ''}")
```

### Serialization and Deserialization

```python
from rdetoolkit.models.metadata import MetadataItem, MetaValue, ValidableItems
import json

# Create metadata
metadata = MetadataItem(
    constant={
        "instrument": MetaValue(value="Spectrometer X1", unit=None),
        "wavelength": MetaValue(value=632.8, unit="nm")
    },
    variable=ValidableItems(root=[
        {
            "power": MetaValue(value=10.0, unit="mW"),
            "exposure": MetaValue(value=1.0, unit="s")
        },
        {
            "power": MetaValue(value=20.0, unit="mW"),
            "exposure": MetaValue(value=0.5, unit="s")
        }
    ])
)

# Serialize to dictionary
metadata_dict = metadata.model_dump()
print("Serialized metadata:")
print(json.dumps(metadata_dict, indent=2))

# Serialize to JSON string
metadata_json = metadata.model_dump_json(indent=2)
print("\nJSON representation:")
print(metadata_json)

# Deserialize from dictionary
reconstructed = MetadataItem(**metadata_dict)
print(f"\nReconstructed metadata has {len(reconstructed.variable.root)} variable entries")

# Verify data integrity
original_instrument = metadata.constant["instrument"].value
reconstructed_instrument = reconstructed.constant["instrument"].value
assert original_instrument == reconstructed_instrument
print("✓ Data integrity verified")
```

### Batch Processing Metadata

```python
from rdetoolkit.models.metadata import MetadataItem, MetaValue, ValidableItems
from typing import List, Dict, Any

def process_measurement_batch(
    constant_data: Dict[str, Any],
    measurements: List[Dict[str, Any]]
) -> MetadataItem:
    """Process a batch of measurements into structured metadata."""

    # Convert constant data
    constant_meta = {}
    for key, value in constant_data.items():
        if isinstance(value, dict) and "value" in value:
            # Handle pre-structured data
            constant_meta[key] = MetaValue(
                value=value["value"],
                unit=value.get("unit")
            )
        else:
            # Handle simple values
            constant_meta[key] = MetaValue(value=value)

    # Convert variable data
    variable_data = []
    for measurement in measurements:
        measurement_meta = {}
        for key, value in measurement.items():
            if isinstance(value, dict) and "value" in value:
                measurement_meta[key] = MetaValue(
                    value=value["value"],
                    unit=value.get("unit")
                )
            else:
                measurement_meta[key] = MetaValue(value=value)
        variable_data.append(measurement_meta)

    return MetadataItem(
        constant=constant_meta,
        variable=ValidableItems(root=variable_data)
    )

# Example usage
batch_constant = {
    "experiment_id": "EXP_2025_001",
    "instrument": "High-res Spectrometer",
    "operator": "Dr. Johnson",
    "lab_conditions": {
        "value": "Standard atmosphere",
        "unit": None
    }
}

batch_measurements = [
    {
        "sample_id": "S001",
        "temperature": {"value": 20.0, "unit": "°C"},
        "intensity": {"value": 1500, "unit": "counts"},
        "timestamp": "2025-01-15T09:00:00Z"
    },
    {
        "sample_id": "S002",
        "temperature": {"value": 25.0, "unit": "°C"},
        "intensity": {"value": 1750, "unit": "counts"},
        "timestamp": "2025-01-15T09:15:00Z"
    }
]

batch_metadata = process_measurement_batch(batch_constant, batch_measurements)
print(f"Processed batch with {len(batch_metadata.variable.root)} measurements")
```

## Error Handling

### Validation Errors

The metadata module raises `ValueError` exceptions when validation fails:

#### Size Limit Exceeded

```python
from rdetoolkit.models.metadata import MetaValue, Variable
from pydantic import ValidationError

# Test size limit for MetaValue
try:
    large_value = "x" * 2000  # Exceeds 1024 byte limit
    invalid_meta = MetaValue(value=large_value)
except ValidationError as e:
    print(f"MetaValue validation failed: {e}")

# Test size limit for Variable
try:
    large_description = "y" * 2000  # Exceeds 1024 byte limit
    invalid_variable = Variable(variable={"description": large_description})
except ValidationError as e:
    print(f"Variable validation failed: {e}")
```

#### UTF-8 Encoding Considerations

```python
from rdetoolkit.models.metadata import MetaValue

# Multi-byte characters count as multiple bytes
japanese_text = "これは日本語のテストです。" * 50  # May exceed byte limit
try:
    meta = MetaValue(value=japanese_text)
    print("✓ Japanese text accepted")
except ValidationError as e:
    print(f"✗ Japanese text too large: {e}")

# Emoji and special characters
emoji_text = "🔬" * 300  # Each emoji is 4 bytes in UTF-8
try:
    meta = MetaValue(value=emoji_text)
    print("✓ Emoji text accepted")
except ValidationError as e:
    print(f"✗ Emoji text too large: {e}")
```

### Best Practices

1. **Validate Input Sizes**: Check string sizes before creating metadata:

   ```python
   def safe_create_meta_value(value: Any, unit: str = None) -> MetaValue | None:
       if isinstance(value, str):
           byte_size = len(value.encode('utf-8'))
           if byte_size > 1024:
               print(f"Warning: Value size {byte_size} bytes exceeds limit")
               return None
       return MetaValue(value=value, unit=unit)
   ```

2. **Handle Large Text Data**: Truncate or summarize large text values:

   ```python
   def truncate_large_text(text: str, max_bytes: int = 1000) -> str:
       if len(text.encode('utf-8')) <= max_bytes:
           return text

       # Truncate while respecting UTF-8 boundaries
       encoded = text.encode('utf-8')
       truncated = encoded[:max_bytes]

       # Ensure we don't break in the middle of a character
       try:
           return truncated.decode('utf-8') + "..."
       except UnicodeDecodeError:
           # Back off until we find a valid boundary
           for i in range(max_bytes - 1, max_bytes - 4, -1):
               try:
                   return encoded[:i].decode('utf-8') + "..."
               except UnicodeDecodeError:
                   continue
           return "..."
   ```

3. **Use Type Hints**: Improve code clarity and IDE support:

   ```python
   from typing import Dict, List, Any, Optional

   def create_metadata_from_dict(
       data: Dict[str, Any]
   ) -> Optional[MetadataItem]:
       try:
           # Process data...
           return MetadataItem(constant=constant, variable=variable)
       except ValidationError:
           return None
   ```

4. **Separate Large Data**: Store large data separately and reference it:

   ```python
   # Instead of storing large data directly
   large_data = [1] * 10000  # Large array

   # Store a reference or summary
   metadata = MetaValue(
       value="large_dataset_ref_001",
       unit="dataset_id"
   )
   ```

5. **Validate Before Batch Operations**: Check data validity before processing:

   ```python
   def validate_measurement_data(measurements: List[Dict]) -> bool:
       for measurement in measurements:
           for key, value in measurement.items():
               if isinstance(value, str):
                   if len(value.encode('utf-8')) > 1024:
                       print(f"Invalid measurement {key}: value too large")
                       return False
       return True
   ```

## Performance Notes

- Validation occurs at object creation time, not during access
- String size validation uses UTF-8 encoding for accurate byte counting
- Non-string values bypass size validation for optimal performance
- Pydantic models provide efficient serialization and deserialization
- Large datasets should be referenced rather than embedded directly

## Integration Examples

### Working with File Metadata

```python
from rdetoolkit.models.metadata import MetadataItem, MetaValue, ValidableItems
from pathlib import Path
import json

def extract_file_metadata(file_path: Path) -> MetadataItem:
    """Extract metadata from a file and create structured metadata."""

    stat = file_path.stat()

    constant = {
        "file_name": MetaValue(value=file_path.name),
        "file_extension": MetaValue(value=file_path.suffix),
        "file_size": MetaValue(value=stat.st_size, unit="bytes"),
        "creation_time": MetaValue(value=stat.st_ctime),
        "modification_time": MetaValue(value=stat.st_mtime),
    }

    # Variable data might come from file contents
    variable = ValidableItems(root=[])

    return MetadataItem(constant=constant, variable=variable)

# Usage
file_metadata = extract_file_metadata(Path("data.txt"))
```

### Database Storage

```python
from rdetoolkit.models.metadata import MetadataItem
import sqlite3
import json

def store_metadata_in_db(metadata: MetadataItem, db_path: str, record_id: str):
    """Store metadata in a database."""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            id TEXT PRIMARY KEY,
            constant_data TEXT,
            variable_data TEXT
        )
    """)

    # Serialize metadata
    constant_json = json.dumps(metadata.model_dump()["constant"])
    variable_json = json.dumps(metadata.model_dump()["variable"])

    # Insert data
    cursor.execute("""
        INSERT OR REPLACE INTO metadata (id, constant_data, variable_data)
        VALUES (?, ?, ?)
    """, (record_id, constant_json, variable_json))

    conn.commit()
    conn.close()

def load_metadata_from_db(db_path: str, record_id: str) -> MetadataItem:
    """Load metadata from database."""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT constant_data, variable_data FROM metadata WHERE id = ?
    """, (record_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        constant_data = json.loads(row[0])
        variable_data = json.loads(row[1])

        return MetadataItem(
            constant=constant_data,
            variable=variable_data
        )
    else:
        raise ValueError(f"No metadata found for ID: {record_id}")
```

## See Also

- [Invoice Schema Module](invoice_schema.md) - For schema validation and structure definitions
- [Invoice Module](invoice.md) - For invoice template and term management
- [Core Module](../core.md) - For file operations and directory management
- [Pydantic Documentation](https://docs.pydantic.dev/) - For advanced validation patterns
