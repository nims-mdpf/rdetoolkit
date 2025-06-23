# rde2util Module

The `rdetoolkit.rde2util` module provides essential utility functions and classes for RDE (Research Data Exchange) data processing and manipulation. This module includes metadata handling, file encoding detection, storage directory management, and various data conversion utilities.

## Overview

The rde2util module offers comprehensive utilities for RDE processing workflows:

- **Metadata Management**: Creation, validation, and processing of metadata structures
- **Storage Directory Operations**: Organized directory creation and management for RDE data
- **Character Encoding Detection**: Robust encoding detection for text files, including Japanese encodings
- **Data Type Conversion**: Flexible value casting and format conversion utilities
- **ZIP File Handling**: Specialized ZIP extraction for Japanese-encoded file names
- **JSON Operations**: Convenient JSON file reading and writing with encoding support
- **Value Processing**: Unit-value pair splitting and conversion utilities

## Classes

### Meta

A comprehensive class for initializing, processing, and managing metadata from definition files.

#### Constructor

```python
Meta(metadef_filepath: RdeFsPath, *, metafilepath: RdeFsPath | None = None)
```

**Parameters:**
- `metadef_filepath` (RdeFsPath): Path to the metadata definition file (metadata-def.json)
- `metafilepath` (RdeFsPath | None): Path to existing metadata file (currently not supported)

**Raises:**
- `StructuredError`: If `metafilepath` is provided (loading existing metadata not supported)

#### Attributes

- `metaConst` (dict[str, MetaItem]): Dictionary for constant metadata
- `metaVar` (list[dict[str, MetaItem]]): List of dictionaries for variable metadata
- `actions` (list[str]): List of metadata actions
- `referedmap` (dict[str, str | list | None]): Dictionary mapping references
- `metaDef` (dict[str, MetadataDefJson]): Metadata definition loaded from file

#### Methods

##### assign_vals

Register and validate metadata values according to the metadata definition.

```python
def assign_vals(
    self,
    entry_dict_meta: MetaType | RepeatedMetaType,
    *,
    ignore_empty_strvalue: bool = True,
) -> dict[str, set]
```

**Parameters:**
- `entry_dict_meta` (MetaType | RepeatedMetaType): Metadata key-value pairs to register
- `ignore_empty_strvalue` (bool): Whether to ignore empty string values (default: True)

**Returns:**
- `dict[str, set]`: Dictionary with 'assigned' and 'unknown' keys containing sets of processed keys

**Raises:**
- `StructuredError`: If 'action' is included in the metadata definition

**Functionality:**
- Validates and casts input metadata values according to metadata-def.json specifications
- Handles both constant and variable metadata types
- Processes unit references and action definitions
- Excludes None values from assignment

##### writefile

Write processed metadata to a file after handling units and actions.

```python
def writefile(self, meta_filepath: str, enc: str = "utf_8") -> dict[str, Any]
```

**Parameters:**
- `meta_filepath` (str): Output file path for metadata
- `enc` (str): File encoding (default: "utf_8")

**Returns:**
- `dict[str, Any]`: Dictionary with 'assigned' and 'unknown' keys showing processing results

**Functionality:**
- Processes units and actions for each metadata entry
- Sorts items according to metadata definition order
- Outputs structured JSON with constant and variable sections
- Returns summary of assigned vs. unassigned metadata keys

##### metadata_validation

Cast and validate metadata values according to specified formats.

```python
def metadata_validation(
    self,
    vsrc: str,
    outtype: str | None,
    outfmt: str | None,
    orgtype: str | None,
    outunit: str | None,
) -> dict[str, bool | int | float | str]
```

**Parameters:**
- `vsrc` (str): Input metadata value
- `outtype` (str | None): Target data type
- `outfmt` (str | None): Target format (for dates)
- `orgtype` (str | None): Original data type
- `outunit` (str | None): Unit specification

**Returns:**
- `dict[str, bool | int | float | str]`: Validated metadata with value and optional unit

**Example:**

```python
from rdetoolkit.rde2util import Meta
from pathlib import Path
import json

# Create metadata processor
meta = Meta("data/tasksupport/metadata-def.json")

# Prepare metadata to register
const_metadata = {
    "title": "Sample Dataset",
    "description": "A comprehensive research dataset",
    "creator": "Research Team",
    "created": "2024-01-01T00:00:00Z",
    "keywords": ["research", "data", "analysis"]
}

variable_metadata = {
    "temperature": ["25.5", "26.1", "24.8"],
    "pressure": ["1013.25", "1012.8", "1014.1"],
    "humidity": ["65", "67", "63"]
}

# Register metadata
const_result = meta.assign_vals(const_metadata)
var_result = meta.assign_vals(variable_metadata)

print(f"Constant metadata assigned: {const_result['assigned']}")
print(f"Variable metadata assigned: {var_result['assigned']}")

# Write metadata to file
output_result = meta.writefile("data/meta/metadata.json")
print(f"Total assigned keys: {len(output_result['assigned'])}")
print(f"Unassigned keys: {output_result['unknown']}")

# Example with unit handling
measurement_data = {
    "temperature": "25.5°C",
    "pressure": "1013.25hPa",
    "distance": "150.5m"
}

measurement_result = meta.assign_vals(measurement_data)
meta.writefile("data/meta/measurements.json")
```

### StorageDir

A class for handling storage directory operations with support for indexed data organization.

**Note:** This class is deprecated. Use `rdetoolkit.core.DirectoryOps` instead.

#### Class Attributes

- `__nDigit` (int): Number of digits for divided data index (fixed value: 4)

#### Methods

##### get_datadir

Generate a data directory path based on index and optionally create it.

```python
@classmethod
def get_datadir(cls, is_mkdir: bool, idx: int = 0) -> str
```

**Parameters:**
- `is_mkdir` (bool): Whether to create the directory
- `idx` (int): Index for divided data (0 for base directory)

**Returns:**
- `str`: Path of the generated data directory

**Deprecation Warning:** Use `rdetoolkit.core.DirectoryOps` instead.

##### get_specific_outputdir

Generate and optionally create specific output directories.

```python
@classmethod
def get_specific_outputdir(cls, is_mkdir: bool, dir_basename: str, idx: int = 0) -> pathlib.Path
```

**Parameters:**
- `is_mkdir` (bool): Whether to create the directory
- `dir_basename` (str): Base name of the specific output directory
- `idx` (int): Index for divided data

**Returns:**
- `pathlib.Path`: Path of the specific output directory

**Supported Directory Types:**
- invoice, invoice_patch, inputdata, structured, temp, logs
- meta, thumbnail, main_image, other_image, attachment
- nonshared_raw, raw, tasksupport

**Example:**

```python
from rdetoolkit.rde2util import StorageDir
import warnings

# Suppress deprecation warnings for demonstration
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Create base data directory
base_dir = StorageDir.get_datadir(is_mkdir=True, idx=0)
print(f"Base directory: {base_dir}")  # "data"

# Create indexed data directory
indexed_dir = StorageDir.get_datadir(is_mkdir=True, idx=1)
print(f"Indexed directory: {indexed_dir}")  # "data/divided/0001"

# Create specific output directories
invoice_dir = StorageDir.get_specific_outputdir(True, "invoice", idx=0)
logs_dir = StorageDir.get_specific_outputdir(True, "logs", idx=1)
meta_dir = StorageDir.get_specific_outputdir(True, "meta", idx=2)

print(f"Invoice directory: {invoice_dir}")
print(f"Logs directory: {logs_dir}")
print(f"Meta directory: {meta_dir}")
```

### CharDecEncoding

A utility class for character encoding detection and conversion, with special support for Japanese text files.

#### Class Attributes

- `USUAL_ENCs` (tuple): Common encodings ("ascii", "shift_jis", "utf_8", "utf_8_sig", "euc_jp")

#### Methods

##### detect_text_file_encoding

Detect the encoding of a text file with enhanced Japanese support.

```python
@classmethod
def detect_text_file_encoding(cls, text_filepath: RdeFsPath) -> str
```

**Parameters:**
- `text_filepath` (RdeFsPath): Path to the text file to analyze

**Returns:**
- `str`: Detected encoding of the text file

**Raises:**
- `FileNotFoundError`: If the file path does not exist

**Features:**
- Uses charset_normalizer for initial detection
- Falls back to chardet for thorough analysis
- Handles Japanese encodings (Shift JIS → cp932 conversion)
- Normalizes encoding names for consistency

**Example:**

```python
from rdetoolkit.rde2util import CharDecEncoding
from pathlib import Path

# Detect encoding of various text files
files_to_check = [
    "data/input/japanese_text.txt",
    "data/input/english_text.txt",
    "data/input/mixed_encoding.csv"
]

for file_path in files_to_check:
    if Path(file_path).exists():
        try:
            encoding = CharDecEncoding.detect_text_file_encoding(file_path)
            print(f"{file_path}: {encoding}")

            # Read file with detected encoding
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
                print(f"  Successfully read {len(content)} characters")

        except FileNotFoundError:
            print(f"{file_path}: File not found")
        except Exception as e:
            print(f"{file_path}: Error - {e}")

# Batch encoding detection
def detect_encodings_in_directory(directory_path: Path) -> dict[str, str]:
    """Detect encodings for all text files in a directory."""
    results = {}

    for file_path in directory_path.glob("*.txt"):
        try:
            encoding = CharDecEncoding.detect_text_file_encoding(file_path)
            results[str(file_path)] = encoding
        except Exception as e:
            results[str(file_path)] = f"Error: {e}"

    return results

# Usage
input_dir = Path("data/input")
if input_dir.exists():
    encoding_results = detect_encodings_in_directory(input_dir)
    for file_path, encoding in encoding_results.items():
        print(f"{file_path}: {encoding}")
```

### ValueCaster

A utility class for value casting and date format conversion.

#### Methods

##### trycast

Safely attempt to cast a value string to a specified type.

```python
@staticmethod
def trycast(valstr: str, tp: Callable[[str], Any]) -> Any
```

**Parameters:**
- `valstr` (str): Value string to cast
- `tp` (Callable[[str], Any]): Type function to cast to

**Returns:**
- `Any`: Casted value if successful, None otherwise

##### convert_to_date_format

Convert a date string to a specified format.

```python
@staticmethod
def convert_to_date_format(value: str, fmt: str) -> str
```

**Parameters:**
- `value` (str): Date string to convert
- `fmt` (str): Target date format ("date-time", "date", "time")

**Returns:**
- `str`: Converted date string

**Raises:**
- `StructuredError`: If the format is unknown

**Example:**

```python
from rdetoolkit.rde2util import ValueCaster

# Test value casting
test_values = ["123", "45.67", "true", "invalid"]
test_types = [int, float, bool, str]

for value in test_values:
    for cast_type in test_types:
        result = ValueCaster.trycast(value, cast_type)
        if result is not None:
            print(f"'{value}' → {cast_type.__name__}: {result}")
        else:
            print(f"'{value}' → {cast_type.__name__}: Failed")

# Date format conversion
date_strings = [
    "2024-01-15T14:30:00Z",
    "2024-01-15 14:30:00",
    "Jan 15, 2024 2:30 PM"
]

formats = ["date-time", "date", "time"]

for date_str in date_strings:
    print(f"\nOriginal: {date_str}")
    for fmt in formats:
        try:
            converted = ValueCaster.convert_to_date_format(date_str, fmt)
            print(f"  {fmt}: {converted}")
        except Exception as e:
            print(f"  {fmt}: Error - {e}")
```

## Functions

### get_default_values

Read default values from a CSV file and return them as a dictionary.

```python
def get_default_values(default_values_filepath: RdeFsPath) -> dict[str, Any]
```

**Parameters:**
- `default_values_filepath` (RdeFsPath): Path to the CSV file containing default values

**Returns:**
- `dict[str, Any]`: Dictionary mapping keys to their corresponding default values

**CSV Format:**
- Must contain 'key' and 'value' columns
- Encoding is automatically detected

**Example:**

```python
from rdetoolkit.rde2util import get_default_values
from pathlib import Path
import csv

# Create sample default values CSV
default_csv_path = Path("data/config/default_values.csv")
default_csv_path.parent.mkdir(parents=True, exist_ok=True)

# Sample data
sample_defaults = [
    {"key": "default_temperature_unit", "value": "°C"},
    {"key": "default_pressure_unit", "value": "hPa"},
    {"key": "default_author", "value": "Research Team"},
    {"key": "default_language", "value": "en"},
    {"key": "max_file_size", "value": "100MB"}
]

# Write sample CSV
with open(default_csv_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['key', 'value'])
    writer.writeheader()
    writer.writerows(sample_defaults)

# Read default values
try:
    defaults = get_default_values(default_csv_path)
    print("Default values loaded:")
    for key, value in defaults.items():
        print(f"  {key}: {value}")

    # Use defaults in processing
    temperature_unit = defaults.get("default_temperature_unit", "K")
    author = defaults.get("default_author", "Unknown")

    print(f"\nUsing defaults:")
    print(f"Temperature unit: {temperature_unit}")
    print(f"Author: {author}")

except Exception as e:
    print(f"Error reading defaults: {e}")
```

### unzip_japanese_zip

Extract files from ZIP archives with Japanese filename encoding support.

```python
def unzip_japanese_zip(src_zipfilepath: str, dst_dirpath: str) -> None
```

**Parameters:**
- `src_zipfilepath` (str): Path to the source ZIP file
- `dst_dirpath` (str): Destination directory for extraction

**Returns:**
- `None`

**Features:**
- Handles Japanese-specific encodings (Shift JIS)
- Automatically decodes file names appropriately
- Creates destination directory structure

**Example:**

```python
from rdetoolkit.rde2util import unzip_japanese_zip
from pathlib import Path
import zipfile

# Create a sample ZIP file with Japanese filenames
def create_sample_japanese_zip():
    """Create a sample ZIP file for demonstration."""
    zip_path = Path("data/input/japanese_sample.zip")
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    # Create some sample files
    sample_files = {
        "english_file.txt": "This is an English file.",
        "データファイル.txt": "これは日本語のファイルです。",
        "測定結果.csv": "time,temperature,humidity\n2024-01-01,25.5,65\n"
    }

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename, content in sample_files.items():
            zf.writestr(filename, content.encode('utf-8'))

    return zip_path

# Extract ZIP with Japanese filename support
zip_file = create_sample_japanese_zip()
extract_dir = Path("data/extracted")

try:
    unzip_japanese_zip(str(zip_file), str(extract_dir))
    print(f"Successfully extracted to: {extract_dir}")

    # List extracted files
    if extract_dir.exists():
        print("Extracted files:")
        for file_path in extract_dir.rglob("*"):
            if file_path.is_file():
                print(f"  {file_path.name}")
                # Read and display content
                try:
                    content = file_path.read_text(encoding='utf-8')
                    print(f"    Content preview: {content[:50]}...")
                except Exception as e:
                    print(f"    Error reading content: {e}")

except Exception as e:
    print(f"Extraction failed: {e}")
```

### castval

Format and cast string values based on specified type and format specifications.

```python
def castval(valstr: Any, outtype: str | None, outfmt: str | None) -> bool | int | float | str
```

**Parameters:**
- `valstr` (Any): String to be converted
- `outtype` (str | None): Target output type ("boolean", "integer", "number", "string")
- `outfmt` (str | None): Output format (for date formatting)

**Returns:**
- `bool | int | float | str`: Converted value

**Raises:**
- `StructuredError`: If type is unknown or casting fails

**Supported Types:**
- **boolean**: Converts to boolean
- **integer**: Converts to integer (handles unit-value pairs)
- **number**: Converts to float (handles unit-value pairs)
- **string**: Returns string, applies date formatting if specified

**Example:**

```python
from rdetoolkit.rde2util import castval
from rdetoolkit.exceptions import StructuredError

# Test various value casting scenarios
test_cases = [
    # Boolean casting
    ("true", "boolean", None),
    ("false", "boolean", None),
    ("1", "boolean", None),

    # Integer casting
    ("42", "integer", None),
    ("42.5m", "integer", None),  # With units
    ("-123", "integer", None),

    # Number casting
    ("3.14159", "number", None),
    ("25.5°C", "number", None),  # With units
    ("1.23e-4", "number", None),

    # String casting
    ("Hello World", "string", None),
    ("2024-01-15T14:30:00", "string", "date-time"),
    ("2024-01-15T14:30:00", "string", "date"),
    ("2024-01-15T14:30:00", "string", "time"),
]

print("Value casting examples:")
for valstr, outtype, outfmt in test_cases:
    try:
        result = castval(valstr, outtype, outfmt)
        result_type = type(result).__name__
        print(f"'{valstr}' → {outtype}/{outfmt} → {result} ({result_type})")
    except StructuredError as e:
        print(f"'{valstr}' → {outtype}/{outfmt} → Error: {e}")
    except Exception as e:
        print(f"'{valstr}' → {outtype}/{outfmt} → Unexpected error: {e}")

# Practical usage in data processing
def process_measurement_data(raw_data: dict[str, str]) -> dict[str, any]:
    """Process raw measurement data with type casting."""

    # Define expected types for each field
    field_types = {
        "temperature": ("number", None),
        "pressure": ("number", None),
        "humidity": ("integer", None),
        "is_valid": ("boolean", None),
        "timestamp": ("string", "date-time"),
        "location": ("string", None)
    }

    processed_data = {}

    for field, value in raw_data.items():
        if field in field_types:
            outtype, outfmt = field_types[field]
            try:
                processed_data[field] = castval(value, outtype, outfmt)
            except Exception as e:
                print(f"Warning: Failed to cast {field}='{value}': {e}")
                processed_data[field] = value  # Keep original value
        else:
            processed_data[field] = value

    return processed_data

# Example usage
raw_measurements = {
    "temperature": "25.5°C",
    "pressure": "1013.25hPa",
    "humidity": "65",
    "is_valid": "true",
    "timestamp": "2024-01-15T14:30:00Z",
    "location": "Laboratory A",
    "notes": "Clear weather"
}

processed = process_measurement_data(raw_measurements)
print("\nProcessed measurement data:")
for field, value in processed.items():
    print(f"  {field}: {value} ({type(value).__name__})")
```

### dict2meta

Convert dictionary data into structured metadata and write to a file.

```python
def dict2meta(
    metadef_filepath: pathlib.Path,
    metaout_filepath: pathlib.Path,
    const_info: MetaType,
    val_info: MetaType
) -> dict[str, set[Any]]
```

**Parameters:**
- `metadef_filepath` (pathlib.Path): Path to metadata definition file
- `metaout_filepath` (pathlib.Path): Output path for processed metadata
- `const_info` (MetaType): Dictionary with constant metadata
- `val_info` (MetaType): Dictionary with variable metadata

**Returns:**
- `dict[str, set[Any]]`: Dictionary with 'assigned' and 'unknown' metadata fields

**Example:**

```python
from rdetoolkit.rde2util import dict2meta
from pathlib import Path
import json

# Setup file paths
metadef_path = Path("data/tasksupport/metadata-def.json")
output_path = Path("data/meta/processed_metadata.json")

# Prepare constant metadata (applies to entire dataset)
constant_metadata = {
    "title": "Environmental Monitoring Dataset",
    "description": "Temperature and humidity measurements from IoT sensors",
    "creator": "Environmental Research Lab",
    "created": "2024-01-15T00:00:00Z",
    "keywords": ["environment", "IoT", "monitoring", "sensors"],
    "license": "CC BY 4.0",
    "language": "en"
}

# Prepare variable metadata (varies by measurement)
variable_metadata = {
    "sensor_id": ["TEMP001", "TEMP002", "TEMP003"],
    "location": ["Building A", "Building B", "Building C"],
    "temperature": ["23.5", "24.1", "22.8"],
    "humidity": ["65", "68", "62"],
    "battery_level": ["85", "92", "78"],
    "last_calibration": ["2024-01-01", "2024-01-02", "2024-01-01"]
}

try:
    # Convert dictionaries to structured metadata
    result = dict2meta(
        metadef_filepath=metadef_path,
        metaout_filepath=output_path,
        const_info=constant_metadata,
        val_info=variable_metadata
    )

    print("Metadata processing completed successfully!")
    print(f"Assigned fields: {result['assigned']}")
    print(f"Unknown fields: {result['unknown']}")

    # Verify output file
    if output_path.exists():
        with open(output_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        print(f"\nGenerated metadata structure:")
        print(f"  Constant fields: {list(metadata.get('constant', {}).keys())}")
        print(f"  Variable entries: {len(metadata.get('variable', []))}")

        # Display sample variable entry
        if metadata.get('variable'):
            sample_entry = metadata['variable'][0]
            print(f"  Sample variable entry: {list(sample_entry.keys())}")

except Exception as e:
    print(f"Error processing metadata: {e}")

# Advanced usage with error handling and validation
def create_metadata_with_validation(
    metadef_path: Path,
    output_path: Path,
    const_data: dict,
    var_data: dict
) -> bool:
    """Create metadata with comprehensive validation."""

    try:
        # Validate input data
        if not metadef_path.exists():
            raise FileNotFoundError(f"Metadata definition not found: {metadef_path}")

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Process metadata
        result = dict2meta(metadef_path, output_path, const_data, var_data)

        # Check for unassigned fields
        if result['unknown']:
            print(f"Warning: Some fields were not assigned: {result['unknown']}")

        # Validate output
        if not output_path.exists():
            raise RuntimeError("Output file was not created")

        print(f"Metadata successfully created: {output_path}")
        return True

    except Exception as e:
        print(f"Metadata creation failed: {e}")
        return False

# Usage with validation
success = create_metadata_with_validation(
    metadef_path, output_path, constant_metadata, variable_metadata
)
```

### Deprecated Functions

#### read_from_json_file

**Deprecated:** Use `rdetoolkit.fileops.readf_json` instead.

```python
def read_from_json_file(invoice_file_path: RdeFsPath) -> dict[str, Any]
```

#### write_to_json_file

**Deprecated:** Use `rdetoolkit.fileops.writef_json` instead.

```python
def write_to_json_file(invoicefile_path: RdeFsPath, invoiceobj: dict[str, Any], enc: str = "utf_8") -> None
```

## Complete Usage Examples

### Comprehensive Metadata Processing Pipeline

```python
from rdetoolkit.rde2util import Meta, get_default_values, CharDecEncoding, dict2meta
from pathlib import Path
import json
import csv
from typing import Dict, List, Any

class MetadataProcessor:
    """Comprehensive metadata processing pipeline."""

    def __init__(self, config_dir: Path, output_dir: Path):
        self.config_dir = config_dir
        self.output_dir = output_dir
        self.defaults = {}
        self.encoding_cache = {}

        # Load default values
        defaults_file = config_dir / "default_values.csv"
        if defaults_file.exists():
            self.defaults = get_default_values(defaults_file)

    def detect_file_encodings(self, file_paths: List[Path]) -> Dict[str, str]:
        """Detect encodings for multiple files with caching."""

        for file_path in file_paths:
            if str(file_path) not in self.encoding_cache:
                try:
                    encoding = CharDecEncoding.detect_text_file_encoding(file_path)
                    self.encoding_cache[str(file_path)] = encoding
                    print(f"Detected encoding for {file_path.name}: {encoding}")
                except Exception as e:
                    print(f"Encoding detection failed for {file_path.name}: {e}")
                    self.encoding_cache[str(file_path)] = "utf-8"  # Fallback

        return {path: self.encoding_cache[str(Path(path))] for path in file_paths}

    def process_csv_metadata(self, csv_path: Path) -> Dict[str, List[str]]:
        """Process CSV file and extract metadata with proper encoding."""

        # Detect encoding
        encoding = CharDecEncoding.detect_text_file_encoding(csv_path)

        metadata = {}

        try:
            with open(csv_path, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f)

                # Initialize metadata structure
                for fieldname in reader.fieldnames:
                    metadata[fieldname] = []

                # Read data
                for row in reader:
                    for fieldname, value in row.items():
                        metadata[fieldname].append(value or "")

            print(f"Processed CSV: {csv_path.name} ({len(metadata)} fields)")
            return metadata

        except Exception as e:
            print(f"Error processing CSV {csv_path.name}: {e}")
            return {}

    def create_comprehensive_metadata(
        self,
        metadef_path: Path,
        csv_files: List[Path],
        additional_const: Dict[str, Any] = None
    ) -> Path:
        """Create comprehensive metadata from multiple sources."""

        # Setup output path
        output_path = self.output_dir / "comprehensive_metadata.json"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Start with defaults
        constant_metadata = self.defaults.copy()

        # Add additional constants
        if additional_const:
            constant_metadata.update(additional_const)

        # Process CSV files for variable metadata
        variable_metadata = {}

        for csv_file in csv_files:
            if csv_file.exists():
                csv_data = self.process_csv_metadata(csv_file)
                variable_metadata.update(csv_data)

        # Apply defaults to missing variable data
        max_length = max(len(values) for values in variable_metadata.values()) if variable_metadata else 0

        for key, default_value in self.defaults.items():
            if key not in constant_metadata and key not in variable_metadata:
                variable_metadata[key] = [default_value] * max_length

        # Create metadata using dict2meta
        try:
            result = dict2meta(
                metadef_filepath=metadef_path,
                metaout_filepath=output_path,
                const_info=constant_metadata,
                val_info=variable_metadata
            )

            print(f"Metadata creation completed:")
            print(f"  Output: {output_path}")
            print(f"  Assigned fields: {len(result['assigned'])}")
            print(f"  Unknown fields: {len(result['unknown'])}")

            if result['unknown']:
                print(f"  Unknown fields: {result['unknown']}")

            return output_path

        except Exception as e:
            print(f"Metadata creation failed: {e}")
            raise

    def validate_metadata_output(self, metadata_path: Path) -> bool:
        """Validate the generated metadata file."""

        if not metadata_path.exists():
            print("Metadata file does not exist")
            return False

        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            # Check structure
            required_sections = ['constant', 'variable']
            for section in required_sections:
                if section not in metadata:
                    print(f"Missing section: {section}")
                    return False

            # Validate constant metadata
            const_count = len(metadata['constant'])
            var_count = len(metadata['variable'])

            print(f"Validation results:")
            print(f"  Constant metadata entries: {const_count}")
            print(f"  Variable metadata entries: {var_count}")

            # Check for required fields
            required_const_fields = ['title', 'description', 'creator']
            missing_fields = [field for field in required_const_fields
                            if field not in metadata['constant']]

            if missing_fields:
                print(f"  Missing required constant fields: {missing_fields}")
                return False

            print("  Metadata validation passed")
            return True

        except json.JSONDecodeError as e:
            print(f"Invalid JSON format: {e}")
            return False
        except Exception as e:
            print(f"Validation error: {e}")
            return False

# Usage example
def main():
    """Main processing example."""

    # Setup paths
    config_dir = Path("data/config")
    output_dir = Path("data/meta")
    metadef_path = Path("data/tasksupport/metadata-def.json")

    # Sample CSV files
    csv_files = [
        Path("data/measurements/temperature.csv"),
        Path("data/measurements/humidity.csv"),
        Path("data/measurements/pressure.csv")
    ]

    # Create sample data for demonstration
    config_dir.mkdir(parents=True, exist_ok=True)

    # Create default values CSV
    defaults_csv = config_dir / "default_values.csv"
    with open(defaults_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['key', 'value'])
        writer.writerows([
            ['default_temperature_unit', '°C'],
            ['default_pressure_unit', 'hPa'],
            ['default_humidity_unit', '%'],
            ['creator', 'Automated Processing System'],
            ['language', 'en']
        ])

    # Initialize processor
    processor = MetadataProcessor(config_dir, output_dir)

    # Additional constant metadata
    additional_constants = {
        "title": "Multi-Sensor Environmental Data",
        "description": "Comprehensive environmental monitoring dataset",
        "created": "2024-01-15T00:00:00Z",
        "keywords": ["environment", "sensors", "monitoring"]
    }

    try:
        # Process metadata
        output_path = processor.create_comprehensive_metadata(
            metadef_path=metadef_path,
            csv_files=csv_files,
            additional_const=additional_constants
        )

        # Validate output
        if processor.validate_metadata_output(output_path):
            print("✅ Metadata processing completed successfully")
        else:
            print("❌ Metadata validation failed")

    except Exception as e:
        print(f"❌ Processing failed: {e}")

if __name__ == "__main__":
    main()
```

### Advanced Value Processing and Unit Handling

```python
from rdetoolkit.rde2util import ValueCaster, castval, Meta
from rdetoolkit.exceptions import StructuredError
import re
from typing import Dict, Any, Tuple, List
from pathlib import Path

class AdvancedValueProcessor:
    """Advanced value processing with unit handling and validation."""

    def __init__(self):
        self.unit_conversions = {
            # Temperature
            '°F': lambda x: (x - 32) * 5/9,  # Fahrenheit to Celsius
            'K': lambda x: x - 273.15,       # Kelvin to Celsius

            # Pressure
            'psi': lambda x: x * 6894.76,    # PSI to Pa
            'bar': lambda x: x * 100000,     # Bar to Pa
            'atm': lambda x: x * 101325,     # Atmosphere to Pa

            # Distance
            'ft': lambda x: x * 0.3048,      # Feet to meters
            'in': lambda x: x * 0.0254,      # Inches to meters
            'km': lambda x: x * 1000,        # Kilometers to meters
        }

        self.target_units = {
            'temperature': '°C',
            'pressure': 'Pa',
            'distance': 'm'
        }

    def parse_value_with_unit(self, value_str: str) -> Tuple[float, str]:
        """Parse a string containing a value and unit."""

        # Regular expression to extract numeric value and unit
        pattern = r'^([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*(.*)$'
        match = re.match(pattern, value_str.strip())

        if match:
            value_part = match.group(1)
            unit_part = match.group(2).strip()

            try:
                numeric_value = float(value_part)
                return numeric_value, unit_part
            except ValueError:
                raise ValueError(f"Cannot parse numeric value: {value_part}")
        else:
            raise ValueError(f"Cannot parse value-unit pair: {value_str}")

    def convert_unit(self, value: float, from_unit: str, measurement_type: str) -> Tuple[float, str]:
        """Convert a value from one unit to the target unit for the measurement type."""

        target_unit = self.target_units.get(measurement_type)
        if not target_unit:
            return value, from_unit  # No conversion available

        if from_unit == target_unit:
            return value, target_unit  # Already in target unit

        if from_unit in self.unit_conversions:
            converted_value = self.unit_conversions[from_unit](value)
            return converted_value, target_unit
        else:
            # Unknown unit, keep original
            return value, from_unit

    def process_measurement_values(
        self,
        measurements: Dict[str, List[str]],
        measurement_types: Dict[str, str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Process measurement values with unit conversion and validation."""

        processed_data = {}

        for measurement_name, values in measurements.items():
            measurement_type = measurement_types.get(measurement_name, 'unknown')
            processed_values = []

            for value_str in values:
                try:
                    # Parse value and unit
                    numeric_value, unit = self.parse_value_with_unit(value_str)

                    # Convert unit if possible
                    converted_value, target_unit = self.convert_unit(
                        numeric_value, unit, measurement_type
                    )

                    # Create processed entry
                    processed_entry = {
                        'original_value': value_str,
                        'numeric_value': converted_value,
                        'unit': target_unit,
                        'original_unit': unit,
                        'converted': unit != target_unit
                    }

                    processed_values.append(processed_entry)

                except Exception as e:
                    # Handle parsing errors
                    processed_entry = {
                        'original_value': value_str,
                        'error': str(e),
                        'numeric_value': None,
                        'unit': None
                    }
                    processed_values.append(processed_entry)

            processed_data[measurement_name] = processed_values

        return processed_data

    def create_metadata_with_processing(
        self,
        metadef_path: Path,
        output_path: Path,
        raw_measurements: Dict[str, List[str]],
        measurement_types: Dict[str, str],
        constant_metadata: Dict[str, Any]
    ) -> bool:
        """Create metadata with advanced value processing."""

        try:
            # Process measurements
            processed_measurements = self.process_measurement_values(
                raw_measurements, measurement_types
            )

            # Prepare variable metadata for Meta class
            variable_metadata = {}

            for measurement_name, processed_values in processed_measurements.items():
                # Extract numeric values and units for metadata
                numeric_values = []
                units = []

                for entry in processed_values:
                    if entry.get('numeric_value') is not None:
                        numeric_values.append(str(entry['numeric_value']))
                        units.append(entry.get('unit', ''))
                    else:
                        numeric_values.append('')
                        units.append('')

                variable_metadata[measurement_name] = numeric_values
                if any(units):  # Add unit information if available
                    variable_metadata[f"{measurement_name}_unit"] = units

            # Create metadata using Meta class
            meta = Meta(metadef_path)

            # Assign constant metadata
            const_result = meta.assign_vals(constant_metadata)
            print(f"Assigned constant metadata: {const_result['assigned']}")

            # Assign variable metadata
            var_result = meta.assign_vals(variable_metadata)
            print(f"Assigned variable metadata: {var_result['assigned']}")

            # Write metadata file
            output_result = meta.writefile(str(output_path))
            print(f"Metadata written to: {output_path}")
            print(f"Total assigned: {len(output_result['assigned'])}")
            print(f"Unknown fields: {output_result['unknown']}")

            # Create processing report
            report_path = output_path.parent / f"{output_path.stem}_processing_report.json"
            processing_report = {
                'processing_summary': {
                    'total_measurements': len(raw_measurements),
                    'processed_measurements': len(processed_measurements),
                    'conversion_summary': {}
                },
                'detailed_processing': processed_measurements
            }

            # Add conversion summary
            for measurement_name, processed_values in processed_measurements.items():
                converted_count = sum(1 for entry in processed_values if entry.get('converted', False))
                error_count = sum(1 for entry in processed_values if 'error' in entry)

                processing_report['processing_summary']['conversion_summary'][measurement_name] = {
                    'total_values': len(processed_values),
                    'converted_values': converted_count,
                    'error_values': error_count
                }

            with open(report_path, 'w', encoding='utf-8') as f:
                import json
                json.dump(processing_report, f, indent=2, ensure_ascii=False)

            print(f"Processing report saved to: {report_path}")
            return True

        except Exception as e:
            print(f"Advanced processing failed: {e}")
            return False

# Usage example
def demonstrate_advanced_processing():
    """Demonstrate advanced value processing capabilities."""

    # Setup processor
    processor = AdvancedValueProcessor()

    # Sample raw measurements with various units
    raw_measurements = {
        'temperature': ['25.5°C', '78.2°F', '298.15K', '22.1°C'],
        'pressure': ['1013.25hPa', '14.7psi', '1.01bar', '101325Pa'],
        'distance': ['150.5m', '5.2ft', '30.5in', '0.1km'],
        'humidity': ['65%', '70%', '58%', '72%']
    }

    # Define measurement types for unit conversion
    measurement_types = {
        'temperature': 'temperature',
        'pressure': 'pressure',
        'distance': 'distance',
        'humidity': 'humidity'  # No conversion defined
    }

    # Process measurements
    processed = processor.process_measurement_values(raw_measurements, measurement_types)

    # Display processing results
    print("Advanced Processing Results:")
    print("=" * 50)

    for measurement, values in processed.items():
        print(f"\n{measurement.upper()}:")
        for i, entry in enumerate(values):
            print(f"  {i+1}. {entry['original_value']}")
            if entry.get('error'):
                print(f"     Error: {entry['error']}")
            else:
                print(f"     → {entry['numeric_value']:.2f} {entry['unit']}")
                if entry.get('converted'):
                    print(f"     (converted from {entry['original_unit']})")

    # Create metadata with processing
    metadef_path = Path("data/tasksupport/metadata-def.json")
    output_path = Path("data/meta/advanced_metadata.json")

    constant_metadata = {
        'title': 'Advanced Processed Measurements',
        'description': 'Measurements with unit conversion and validation',
        'creator': 'Advanced Processing System',
        'processing_method': 'unit_conversion_and_validation'
    }

    success = processor.create_metadata_with_processing(
        metadef_path=metadef_path,
        output_path=output_path,
        raw_measurements=raw_measurements,
        measurement_types=measurement_types,
        constant_metadata=constant_metadata
    )

    if success:
        print("\n✅ Advanced processing completed successfully")
    else:
        print("\n❌ Advanced processing failed")

if __name__ == "__main__":
    demonstrate_advanced_processing()
```

## Error Handling

### Exception Types

The rde2util module raises `StructuredError` for various error conditions:

```python
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.rde2util import Meta, castval

# Handle metadata processing errors
try:
    meta = Meta("invalid_path.json")
except StructuredError as e:
    print(f"Metadata initialization failed: {e}")

# Handle value casting errors
try:
    result = castval("invalid_number", "integer", None)
except StructuredError as e:
    print(f"Value casting failed: {e}")
```

### Best Practices for Error Handling

1. **Graceful Degradation**:
   ```python
   def safe_metadata_processing(metadef_path, output_path, data):
       """Process metadata with graceful error handling."""
       try:
           meta = Meta(metadef_path)
           result = meta.assign_vals(data)
           meta.writefile(output_path)
           return True, result
       except StructuredError as e:
           print(f"Structured error: {e}")
           return False, None
       except Exception as e:
           print(f"Unexpected error: {e}")
           return False, None
   ```

2. **Validation Before Processing**:
   ```python
   def validate_before_processing(metadef_path, data):
       """Validate inputs before processing."""
       if not Path(metadef_path).exists():
           raise FileNotFoundError(f"Metadata definition not found: {metadef_path}")

       if not data:
           raise ValueError("No data provided for processing")

       # Additional validation...
   ```

## Performance Notes

### Optimization Strategies

1. **Encoding Detection Caching**: Cache encoding detection results for frequently accessed files
2. **Batch Processing**: Process multiple files in batches to reduce I/O overhead
3. **Memory Management**: Use generators for large datasets to reduce memory usage
4. **Unit Conversion Caching**: Cache unit conversion functions for repeated operations

### Performance Best Practices

```python
# Efficient batch processing
def efficient_file_processing(file_paths: List[Path]) -> Dict[str, str]:
    """Efficiently process multiple files with caching."""
    encoding_cache = {}

    for file_path in file_paths:
        if str(file_path) not in encoding_cache:
            encoding = CharDecEncoding.detect_text_file_encoding(file_path)
            encoding_cache[str(file_path)] = encoding

    return encoding_cache
```

## See Also

- [Core Module](../core.md) - For directory operations and file handling
- [File Operations](../fileops.md) - For JSON file reading and writing utilities
- [Models - RDE2 Types](../models/rde2types.md) - For type definitions used in this module
- [Models - Metadata](../models/metadata.md) - For metadata structure definitions
- [Validation](../validation.md) - For metadata validation functionality
- [Exceptions](../exceptions.md) - For StructuredError and other exception types
- [Usage - Structured Process](../../usage/structured_process/structured.md) - For metadata processing in workflows
- [Usage - Metadata Definition](../../usage/metadata_definition_file.md) - For metadata definition file usage
