# RDE2 Types Module

The `rdetoolkit.models.rde2types` module provides comprehensive type definitions, data structures, and utility classes for RDE (Research Data Exchange) version 2 systems. This module defines essential types, path management utilities, and configuration structures used throughout the RDE processing pipeline.

## Overview

The RDE2 types module implements a complete type system for managing research data workflows with the following capabilities:

- **Type Aliases**: Comprehensive type definitions for file paths, metadata, and data structures
- **Path Management**: Structured handling of input and output directory paths
- **Configuration Management**: Default configuration creation and management
- **Data Structures**: TypedDict definitions for JSON schema validation
- **Legacy Support**: Deprecated features with migration warnings

## Type Aliases

The module defines several type aliases for improved code clarity and type safety.

### File Path Types

```python
ZipFilesPathList = Sequence[Path]
UnZipFilesPathList = Sequence[Path]
ExcelInvoicePathList = Sequence[Path]
OtherFilesPathList = Sequence[Path]
PathTuple = tuple[Path, ...]
RdeFsPath = Union[str, Path]
```

- **ZipFilesPathList**: Sequence of ZIP file paths
- **UnZipFilesPathList**: Sequence of extracted file paths
- **ExcelInvoicePathList**: Sequence of Excel invoice file paths
- **OtherFilesPathList**: Sequence of other file paths
- **PathTuple**: Tuple of Path objects
- **RdeFsPath**: Union type for filesystem paths (string or Path)

### Data Structure Types

```python
InputFilesGroup = tuple[ZipFilesPathList, ExcelInvoicePathList, OtherFilesPathList]
RawFiles = Sequence[PathTuple]
MetaType = dict[str, Union[str, int, float, list, bool]]
RepeatedMetaType = dict[str, list[Union[str, int, float]]]
MetaItem = dict[str, Union[str, int, float, bool]]
```

- **InputFilesGroup**: Grouped input files by type
- **RawFiles**: Sequence of raw file tuples
- **MetaType**: Flexible metadata dictionary type
- **RepeatedMetaType**: Metadata with repeated values
- **MetaItem**: Individual metadata item type

### Example Usage

```python
from rdetoolkit.models.rde2types import (
    ZipFilesPathList, InputFilesGroup, MetaType, RdeFsPath
)
from pathlib import Path

# File path collections
zip_files: ZipFilesPathList = [
    Path("data1.zip"),
    Path("data2.zip"),
    Path("data3.zip")
]

excel_files: ExcelInvoicePathList = [
    Path("invoice1.xlsx"),
    Path("invoice2.xlsx")
]

other_files: OtherFilesPathList = [
    Path("readme.txt"),
    Path("config.json")
]

# Group files
input_group: InputFilesGroup = (zip_files, excel_files, other_files)

# Metadata example
metadata: MetaType = {
    "temperature": 25.5,
    "pressure": 1013.25,
    "sample_id": "SAMPLE_001",
    "measurements": [1.1, 2.2, 3.3],
    "is_calibrated": True
}

# Flexible path handling
def process_path(path: RdeFsPath) -> Path:
    return Path(path) if isinstance(path, str) else path
```

## Configuration Functions

### create_default_config()

Creates and returns a default configuration object for RDE processing.

```python
def create_default_config() -> Config
```

**Returns:**

- `Config`: A default configuration object with standard settings

**Example:**

```python
from rdetoolkit.models.rde2types import create_default_config

# Create default configuration
config = create_default_config()

print(config.system.extended_mode)  # None
print(config.system.save_raw)       # True
print(config.system.save_thumbnail_image)  # False
print(config.system.magic_variable)  # False
print(config.multidata_tile.ignore_errors)  # False
```

## Path Management Classes

### RdeInputDirPaths

Data class for managing input directory paths in RDE processing.

#### RdeInputDirPaths Constructor

```python
RdeInputDirPaths(
    inputdata: Path,
    invoice: Path,
    tasksupport: Path,
    config: Config = field(default_factory=create_default_config)
)
```

**Parameters:**

- `inputdata` (Path): Path to the input data directory
- `invoice` (Path): Path to the invoice directory containing invoice.json
- `tasksupport` (Path): Path to the task support data directory
- `config` (Config): Configuration object (defaults to `create_default_config()`)

#### Properties

##### default_csv

Returns the path to the 'default_value.csv' file.

```python
@property
def default_csv(self) -> Path
```

**Returns:**

- `Path`: Path to the default_value.csv file

**Behavior:**

- If `tasksupport` is set, uses that path
- Otherwise, uses the default path under 'data/tasksupport'

#### Usage Example

```python
from rdetoolkit.models.rde2types import RdeInputDirPaths, create_default_config
from pathlib import Path

# Create input paths configuration
input_paths = RdeInputDirPaths(
    inputdata=Path("input/data"),
    invoice=Path("input/invoices"),
    tasksupport=Path("support"),
    config=create_default_config()
)

# Access paths
print(input_paths.inputdata)     # input/data
print(input_paths.invoice)       # input/invoices
print(input_paths.tasksupport)   # support
print(input_paths.default_csv)   # support/default_value.csv

# With None tasksupport (uses default)
input_paths_default = RdeInputDirPaths(
    inputdata=Path("input/data"),
    invoice=Path("input/invoices"),
    tasksupport=None
)
print(input_paths_default.default_csv)  # data/tasksupport/default_value.csv
```

### RdeOutputResourcePath

Data class for managing output resource paths in RDE processing.

#### ValueUnitPair Initialization

```python
RdeOutputResourcePath(
    raw: Path,
    nonshared_raw: Path,
    rawfiles: tuple[Path, ...],
    struct: Path,
    main_image: Path,
    other_image: Path,
    meta: Path,
    thumbnail: Path,
    logs: Path,
    invoice: Path,
    invoice_schema_json: Path,
    invoice_org: Path,
    temp: Path | None = None,
    invoice_patch: Path | None = None,
    attachment: Path | None = None
)
```

**Parameters:**

- `raw` (Path): Path for raw data storage
- `nonshared_raw` (Path): Path for non-shared raw data
- `rawfiles` (tuple[Path, ...]): Tuple of input file paths for single data tile
- `struct` (Path): Path for structured data storage
- `main_image` (Path): Path for main image files
- `other_image` (Path): Path for other image files
- `meta` (Path): Path for metadata files
- `thumbnail` (Path): Path for thumbnail images
- `logs` (Path): Path for log files
- `invoice` (Path): Path for invoice files
- `invoice_schema_json` (Path): Path for invoice.schema.json
- `invoice_org` (Path): Path for original invoice.json backup
- `temp` (Path | None): Optional path for temporary files
- `invoice_patch` (Path | None): Optional path for modified invoices
- `attachment` (Path | None): Optional path for attachment files

#### Example Usage: Name

```python
from rdetoolkit.models.rde2types import RdeOutputResourcePath
from pathlib import Path

# Create output resource paths
output_paths = RdeOutputResourcePath(
    raw=Path("output/raw"),
    nonshared_raw=Path("output/nonshared_raw"),
    rawfiles=(Path("file1.txt"), Path("file2.txt"), Path("file3.txt")),
    struct=Path("output/structured"),
    main_image=Path("output/images/main"),
    other_image=Path("output/images/other"),
    meta=Path("output/metadata"),
    thumbnail=Path("output/thumbnails"),
    logs=Path("output/logs"),
    invoice=Path("output/invoices"),
    invoice_schema_json=Path("output/schema/invoice.schema.json"),
    invoice_org=Path("output/backup/invoice_original.json"),
    temp=Path("output/temp"),
    invoice_patch=Path("output/patches"),
    attachment=Path("output/attachments")
)

# Access paths
print(output_paths.raw)           # output/raw
print(output_paths.struct)        # output/structured
print(output_paths.main_image)    # output/images/main
print(len(output_paths.rawfiles)) # 3

# Optional paths
if output_paths.temp:
    print(f"Temp directory: {output_paths.temp}")

if output_paths.attachment:
    print(f"Attachment directory: {output_paths.attachment}")
```

## TypedDict Definitions

### Name

TypedDict for representing multilingual names.

```python
class Name(TypedDict):
    ja: str  # Japanese name
    en: str  # English name
```

#### Example: Name

```python
from rdetoolkit.models.rde2types import Name

# Create multilingual name
sample_name: Name = {
    "ja": "サンプル材料",
    "en": "Sample Material"
}

print(sample_name["ja"])  # サンプル材料
print(sample_name["en"])  # Sample Material

# Type checking
def process_name(name: Name) -> str:
    return f"{name['en']} ({name['ja']})"

result = process_name(sample_name)
print(result)  # Sample Material (サンプル材料)
```

### Schema

TypedDict for schema definitions with optional fields.

```python
class Schema(TypedDict, total=False):
    type: str    # Schema type
    format: str  # Schema format
```

#### Example: Schema

```python
from rdetoolkit.models.rde2types import Schema

# Complete schema
full_schema: Schema = {
    "type": "string",
    "format": "date-time"
}

# Partial schema (total=False allows this)
partial_schema: Schema = {
    "type": "number"
    # format is optional
}

# Type checking function
def validate_schema(schema: Schema) -> bool:
    return "type" in schema

print(validate_schema(full_schema))    # True
print(validate_schema(partial_schema)) # True
```

### MetadataDefJson

Comprehensive TypedDict for metadata definition structure.

```python
class MetadataDefJson(TypedDict):
    name: Name           # Multilingual name
    schema: Schema       # Schema definition
    unit: str           # Unit of measurement
    description: str     # Description
    uri: str            # URI reference
    originalName: str    # Original name
    originalType: str    # Original type
    mode: str           # Processing mode
    order: str          # Order specification
    valiable: int       # Variable identifier
    _feature: bool      # Feature flag
    action: str         # Action specification
```

#### Example: MetadataDefJson

```python
from rdetoolkit.models.rde2types import MetadataDefJson, Name, Schema

# Create complete metadata definition
metadata_def: MetadataDefJson = {
    "name": {
        "ja": "温度",
        "en": "Temperature"
    },
    "schema": {
        "type": "number",
        "format": "float"
    },
    "unit": "°C",
    "description": "Sample temperature measurement",
    "uri": "http://example.com/temperature",
    "originalName": "temp_sensor_1",
    "originalType": "float64",
    "mode": "measurement",
    "order": "ascending",
    "valiable": 1,
    "_feature": True,
    "action": "record"
}

# Access metadata fields
print(metadata_def["name"]["en"])  # Temperature
print(metadata_def["unit"])        # °C
print(metadata_def["schema"]["type"])  # number
```

## Data Classes

### ValueUnitPair

Simple dataclass for value-unit pairs.

#### ValueUnitPair Constructor

```python
ValueUnitPair(value: str, unit: str)
```

**Parameters:**

- `value` (str): The value component
- `unit` (str): The unit component

#### Example

```python
from rdetoolkit.models.rde2types import ValueUnitPair

# Create value-unit pairs
temperature = ValueUnitPair(value="25.5", unit="°C")
pressure = ValueUnitPair(value="1013.25", unit="hPa")
distance = ValueUnitPair(value="10.0", unit="mm")

print(f"Temperature: {temperature.value} {temperature.unit}")  # Temperature: 25.5 °C
print(f"Pressure: {pressure.value} {pressure.unit}")          # Pressure: 1013.25 hPa

# Use in collections
measurements = [
    ValueUnitPair("25.5", "°C"),
    ValueUnitPair("1013.25", "hPa"),
    ValueUnitPair("60", "%RH")
]

for measurement in measurements:
    print(f"{measurement.value} {measurement.unit}")
```

## Legacy Classes (Deprecated)

### RdeFormatFlags

**⚠️ Warning: This class is deprecated and scheduled for removal.**

Legacy class for managing RDE format flags. This class is no longer used and will be removed in future versions.

#### Constructor

```python
RdeFormatFlags()
```

**Warning Behavior:**

- Emits a `FutureWarning` when instantiated
- Functionality is preserved for backward compatibility

#### Example (Not Recommended): RdeFormatFlags

```python
from rdetoolkit.models.rde2types import RdeFormatFlags
import warnings

# This will emit a deprecation warning
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    flags = RdeFormatFlags()

# Migration: Remove usage of RdeFormatFlags
# Use configuration objects instead
```

## Complete Usage Examples

### Setting Up RDE Processing Pipeline

```python
from rdetoolkit.models.rde2types import (
    RdeInputDirPaths, RdeOutputResourcePath, create_default_config,
    ZipFilesPathList, ExcelInvoicePathList, OtherFilesPathList, InputFilesGroup
)
from pathlib import Path

def setup_rde_pipeline(base_input: Path, base_output: Path):
    """Set up complete RDE processing pipeline paths."""

    # Configure input paths
    input_paths = RdeInputDirPaths(
        inputdata=base_input / "data",
        invoice=base_input / "invoices",
        tasksupport=base_input / "support",
        config=create_default_config()
    )

    # Configure output paths
    output_paths = RdeOutputResourcePath(
        raw=base_output / "raw",
        nonshared_raw=base_output / "nonshared_raw",
        rawfiles=tuple(),  # Will be populated during processing
        struct=base_output / "structured",
        main_image=base_output / "images" / "main",
        other_image=base_output / "images" / "other",
        meta=base_output / "metadata",
        thumbnail=base_output / "thumbnails",
        logs=base_output / "logs",
        invoice=base_output / "invoices",
        invoice_schema_json=base_output / "schema" / "invoice.schema.json",
        invoice_org=base_output / "backup" / "invoice_original.json",
        temp=base_output / "temp",
        invoice_patch=base_output / "patches",
        attachment=base_output / "attachments"
    )

    return input_paths, output_paths

# Usage
input_paths, output_paths = setup_rde_pipeline(
    Path("project/input"),
    Path("project/output")
)

print(f"Input data: {input_paths.inputdata}")
print(f"Output structure: {output_paths.struct}")
print(f"Default CSV: {input_paths.default_csv}")
```

### File Organization and Processing

```python
from rdetoolkit.models.rde2types import (
    ZipFilesPathList, ExcelInvoicePathList, OtherFilesPathList,
    InputFilesGroup, RawFiles, PathTuple
)
from pathlib import Path

def organize_input_files(input_dir: Path) -> InputFilesGroup:
    """Organize input files by type."""

    all_files = list(input_dir.rglob("*"))

    # Categorize files
    zip_files: ZipFilesPathList = [f for f in all_files if f.suffix == ".zip"]
    excel_files: ExcelInvoicePathList = [f for f in all_files if f.suffix in [".xlsx", ".xls"]]
    other_files: OtherFilesPathList = [f for f in all_files if f.suffix not in [".zip", ".xlsx", ".xls"]]

    return (zip_files, excel_files, other_files)

def process_raw_files(input_group: InputFilesGroup) -> RawFiles:
    """Process input files into raw file groups."""

    zip_files, excel_files, other_files = input_group

    raw_groups = []

    # Group ZIP files with related files
    for zip_file in zip_files:
        related_files = [f for f in other_files if f.stem == zip_file.stem]
        file_group: PathTuple = (zip_file, *related_files)
        raw_groups.append(file_group)

    # Handle standalone Excel files
    for excel_file in excel_files:
        file_group: PathTuple = (excel_file,)
        raw_groups.append(file_group)

    return raw_groups

# Usage example
input_dir = Path("input/experiment_data")
file_groups = organize_input_files(input_dir)
raw_files = process_raw_files(file_groups)

print(f"Found {len(file_groups[0])} ZIP files")
print(f"Found {len(file_groups[1])} Excel files")
print(f"Created {len(raw_files)} raw file groups")
```

### Metadata Handling

```python
from rdetoolkit.models.rde2types import (
    MetaType, RepeatedMetaType, MetaItem, MetadataDefJson,
    Name, Schema, ValueUnitPair
)

def create_measurement_metadata() -> MetaType:
    """Create measurement metadata."""

    metadata: MetaType = {
        "experiment_id": "EXP_2025_001",
        "temperature": 25.5,
        "pressure": 1013.25,
        "humidity": 60,
        "measurements": [1.1, 2.2, 3.3, 4.4],
        "is_calibrated": True,
        "sample_count": 100
    }

    return metadata

def create_repeated_metadata() -> RepeatedMetaType:
    """Create metadata with repeated measurements."""

    repeated_meta: RepeatedMetaType = {
        "temperatures": [20.0, 21.5, 23.0, 24.5, 26.0],
        "pressures": [1010.0, 1011.5, 1013.0, 1014.5, 1016.0],
        "humidity_values": [58, 59, 60, 61, 62]
    }

    return repeated_meta

def create_metadata_definition() -> MetadataDefJson:
    """Create a complete metadata definition."""

    metadata_def: MetadataDefJson = {
        "name": {
            "ja": "温度測定",
            "en": "Temperature Measurement"
        },
        "schema": {
            "type": "number",
            "format": "float"
        },
        "unit": "°C",
        "description": "Sample temperature during measurement",
        "uri": "http://example.com/schema/temperature",
        "originalName": "temp_sensor_reading",
        "originalType": "float64",
        "mode": "continuous",
        "order": "chronological",
        "valiable": 1,
        "_feature": True,
        "action": "measure"
    }

    return metadata_def

# Usage
measurement_meta = create_measurement_metadata()
repeated_meta = create_repeated_metadata()
meta_def = create_metadata_definition()

# Create value-unit pairs from metadata
value_units = [
    ValueUnitPair(str(measurement_meta["temperature"]), "°C"),
    ValueUnitPair(str(measurement_meta["pressure"]), "hPa"),
    ValueUnitPair(str(measurement_meta["humidity"]), "%RH")
]

for vu in value_units:
    print(f"{vu.value} {vu.unit}")
```

### Configuration and Path Management

```python
from rdetoolkit.models.rde2types import (
    RdeInputDirPaths, RdeOutputResourcePath, create_default_config,
    RdeFsPath
)
from pathlib import Path

class RdeProcessor:
    """Example RDE processor using type-safe paths."""

    def __init__(self, input_base: RdeFsPath, output_base: RdeFsPath):
        self.input_base = Path(input_base)
        self.output_base = Path(output_base)

        # Initialize paths
        self.input_paths = RdeInputDirPaths(
            inputdata=self.input_base / "data",
            invoice=self.input_base / "invoices",
            tasksupport=self.input_base / "support",
            config=create_default_config()
        )

        self.output_paths = None

    def setup_output_structure(self, raw_files: tuple[Path, ...]):
        """Set up output directory structure."""

        self.output_paths = RdeOutputResourcePath(
            raw=self.output_base / "raw",
            nonshared_raw=self.output_base / "nonshared",
            rawfiles=raw_files,
            struct=self.output_base / "structured",
            main_image=self.output_base / "images" / "main",
            other_image=self.output_base / "images" / "other",
            meta=self.output_base / "metadata",
            thumbnail=self.output_base / "thumbnails",
            logs=self.output_base / "logs",
            invoice=self.output_base / "invoices",
            invoice_schema_json=self.output_base / "schema" / "invoice.schema.json",
            invoice_org=self.output_base / "backup" / "invoice.json",
            temp=self.output_base / "temp",
            invoice_patch=self.output_base / "patches",
            attachment=self.output_base / "attachments"
        )

        # Create directories
        self._create_directories()

    def _create_directories(self):
        """Create all necessary output directories."""

        if not self.output_paths:
            return

        directories = [
            self.output_paths.raw,
            self.output_paths.nonshared_raw,
            self.output_paths.struct,
            self.output_paths.main_image,
            self.output_paths.other_image,
            self.output_paths.meta,
            self.output_paths.thumbnail,
            self.output_paths.logs,
            self.output_paths.invoice,
            self.output_paths.invoice_schema_json.parent,
            self.output_paths.invoice_org.parent,
        ]

        # Add optional directories if they exist
        if self.output_paths.temp:
            directories.append(self.output_paths.temp)
        if self.output_paths.invoice_patch:
            directories.append(self.output_paths.invoice_patch)
        if self.output_paths.attachment:
            directories.append(self.output_paths.attachment)

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def get_config(self):
        """Get the current configuration."""
        return self.input_paths.config

# Usage
processor = RdeProcessor("project/input", "project/output")

# Setup with sample raw files
raw_files = (
    Path("data1.txt"),
    Path("data2.txt"),
    Path("image1.png")
)

processor.setup_output_structure(raw_files)

config = processor.get_config()
print(f"Save raw: {config.system.save_raw}")
print(f"Extended mode: {config.system.extended_mode}")
```

## Type Safety Best Practices

1. **Use Type Hints**: Always use the provided type aliases for better code clarity:

   ```python
   from rdetoolkit.models.rde2types import ZipFilesPathList, MetaType

   def process_zip_files(files: ZipFilesPathList) -> MetaType:
       return {"file_count": len(files)}
   ```

2. **Path Type Consistency**: Use `RdeFsPath` for functions that accept both strings and Path objects:

   ```python
   from rdetoolkit.models.rde2types import RdeFsPath
   from pathlib import Path

   def normalize_path(path: RdeFsPath) -> Path:
       return Path(path)
   ```

3. **TypedDict Validation**: Use TypedDict definitions for structured data:

   ```python
   from rdetoolkit.models.rde2types import Name, MetadataDefJson

   def validate_name(name: Name) -> bool:
       return "ja" in name and "en" in name
   ```

4. **Configuration Consistency**: Always use the default configuration factory:

   ```python
   from rdetoolkit.models.rde2types import create_default_config

   # Preferred
   config = create_default_config()

   # Modify as needed
   config.system.save_raw = False
   ```

## Migration from Legacy Features

If you're using deprecated features like `RdeFormatFlags`, migrate to the new configuration system:

```python
# Old (deprecated)
from rdetoolkit.models.rde2types import RdeFormatFlags
flags = RdeFormatFlags()  # Emits deprecation warning

# New (recommended)
from rdetoolkit.models.rde2types import create_default_config
config = create_default_config()
# Configure as needed through the Config object
```

## See Also

- [Config Module](config.md) - For detailed configuration management
- [Core Module](../core.md) - For directory operations and file handling
- [Metadata Module](metadata.md) - For metadata validation and processing
- [Python Typing Documentation](https://docs.python.org/3/library/typing.html) - For advanced type hints
