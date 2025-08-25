# RDE2Util API

## Purpose

This module provides various utility functions used in RDEToolKit's structured processing. It includes a wide range of support functions such as metadata management, storage operations, character encoding detection, and data type conversion.

## Key Features

### Metadata Management
- Creation, updating, and validation of metadata
- Conversion of dictionary format data to metadata
- Reading and writing metadata files

### Storage Operations
- Management and creation of data directories
- Dynamic generation of output directories
- Standardization of file paths

### Data Processing
- Automatic detection of character encoding
- Automatic data type conversion and casting
- Reading and writing JSON files
- Extraction of Japanese ZIP files

---

::: src.rdetoolkit.rde2util.Meta

---

::: src.rdetoolkit.rde2util.StorageDir

---

::: src.rdetoolkit.rde2util.get_default_values

---

::: src.rdetoolkit.rde2util.CharDecEncoding

---

::: src.rdetoolkit.rde2util.unzip_japanese_zip

---

::: src.rdetoolkit.rde2util.read_from_json_file

---

::: src.rdetoolkit.rde2util.write_to_json_file

---

::: src.rdetoolkit.rde2util.castval

---

::: src.rdetoolkit.rde2util.ValueCaster

---

::: src.rdetoolkit.rde2util.dict2meta

---

## Practical Usage

### Metadata Creation and Management

```python title="metadata_management.py"
from rdetoolkit.rde2util import Meta, dict2meta
from pathlib import Path

# Create metadata object
meta = Meta()

# Assign values
meta.assign_vals("temperature", 25.5, "℃")
meta.assign_vals("pressure", 1013.25, "hPa")
meta.assign_vals("humidity", 60, "%")

# Write metadata file
output_path = Path("data/meta/metadata.json")
meta.writefile(output_path)

# Convert dictionary to metadata
data_dict = {
    "experiment_id": "EXP001",
    "date": "2024-01-01",
    "researcher": "John Doe"
}
metadata = dict2meta(data_dict)
```

### Storage Directory Management

```python title="storage_management.py"
from rdetoolkit.rde2util import StorageDir

# Get data directory
data_dir = StorageDir.get_datadir()
print(f"Data directory: {data_dir}")

# Get specific output directories
rawfiles_dir = StorageDir.get_specific_outputdir(False, "rawfiles")
meta_dir = StorageDir.get_specific_outputdir(False, "meta")
thumbnail_dir = StorageDir.get_specific_outputdir(False, "thumbnail")

print(f"Raw data directory: {rawfiles_dir}")
print(f"Metadata directory: {meta_dir}")
print(f"Thumbnail directory: {thumbnail_dir}")
```

### Character Encoding Detection

```python title="encoding_detection.py"
from rdetoolkit.rde2util import CharDecEncoding
from pathlib import Path

# Create encoding detector
detector = CharDecEncoding()

# Detect text file encoding
text_file = Path("data/sample.txt")
encoding = detector.detect_text_file_encoding(text_file)
print(f"Detected encoding: {encoding}")

# Read file using detected encoding
with open(text_file, 'r', encoding=encoding) as f:
    content = f.read()
    print(f"File content: {content[:100]}...")
```

### Data Type Conversion

```python title="data_casting.py"
from rdetoolkit.rde2util import castval, ValueCaster

# Basic type conversion
int_value = castval("123", int)
float_value = castval("45.67", float)
bool_value = castval("true", bool)

print(f"Integer: {int_value}, Float: {float_value}, Boolean: {bool_value}")

# Advanced conversion using ValueCaster
caster = ValueCaster()
converted_values = caster.cast_multiple([
    ("100", int),
    ("3.14", float),
    ("yes", bool)
])
print(f"Conversion results: {converted_values}")
```

### JSON File Operations

```python title="json_operations.py"
from rdetoolkit.rde2util import read_from_json_file, write_to_json_file
from pathlib import Path

# Read JSON file
json_path = Path("data/config.json")
data = read_from_json_file(json_path)
print(f"Loaded data: {data}")

# Write JSON file
output_data = {
    "experiment": "sample_001",
    "parameters": {
        "temperature": 25.0,
        "pressure": 1013.25
    },
    "results": [1.2, 3.4, 5.6]
}

output_path = Path("data/output.json")
write_to_json_file(output_data, output_path)
print(f"Data saved to {output_path}")
```
