# Processing Context

The `rdetoolkit.processing.context` module provides the `ProcessingContext` class, which encapsulates all the information needed for processing operations across different modes.

## Overview

The `ProcessingContext` serves as a centralized container for all processing-related data, configuration, and resources. It provides a consistent interface for processors to access input paths, output resources, and mode-specific information.

## Classes

### ProcessingContext

A dataclass that encapsulates all information needed for processing operations in different modes (RDEFormat, MultiFile, ExcelInvoice, etc.).

#### Constructor

```python
@dataclass
class ProcessingContext:
    index: str
    srcpaths: RdeInputDirPaths
    resource_paths: RdeOutputResourcePath
    datasets_function: DatasetCallback | None
    mode_name: str
    excel_file: Path | None = None
    excel_index: int | None = None
    smarttable_file: Path | None = None
```

**Parameters:**
- `index` (str): Processing index identifier
- `srcpaths` (RdeInputDirPaths): Input directory paths configuration
- `resource_paths` (RdeOutputResourcePath): Output resource paths
- `datasets_function` (Optional[DatasetCallback]): Custom dataset processing function
- `mode_name` (str): Processing mode name
- `excel_file` (Optional[Path]): Excel invoice file path (for Excel mode)
- `excel_index` (Optional[int]): Excel processing index (for Excel mode)
- `smarttable_file` (Optional[Path]): SmartTable file path (for SmartTable mode)

#### Properties

##### basedir

Get the base directory for the processing operation.

```python
@property
def basedir(self) -> str
```

**Returns:**
- `str`: Base directory path from the first raw file, or empty string if no raw files

**Example:**
```python
context = ProcessingContext(...)
print(f"Base directory: {context.basedir}")
```

##### invoice_dst_filepath

Get the destination invoice file path.

```python
@property
def invoice_dst_filepath(self) -> Path
```

**Returns:**
- `Path`: Path to the output invoice.json file

**Example:**
```python
invoice_path = context.invoice_dst_filepath
# Returns: Path("data/divided/0001/invoice/invoice.json")
```

##### schema_path

Get the invoice schema file path.

```python
@property
def schema_path(self) -> Path
```

**Returns:**
- `Path`: Path to the invoice.schema.json file in tasksupport directory

**Example:**
```python
schema_path = context.schema_path
# Returns: Path("data/tasksupport/invoice.schema.json")
```

##### metadata_def_path

Get the metadata definition file path.

```python
@property
def metadata_def_path(self) -> Path
```

**Returns:**
- `Path`: Path to the metadata-def.json file in tasksupport directory

**Example:**
```python
metadata_def = context.metadata_def_path
# Returns: Path("data/tasksupport/metadata-def.json")
```

##### metadata_path

Get the metadata.json file path.

```python
@property
def metadata_path(self) -> Path
```

**Returns:**
- `Path`: Path to the output metadata.json file

**Example:**
```python
metadata_path = context.metadata_path
# Returns: Path("data/divided/0001/meta/metadata.json")
```

##### dataset_paths

Unified view that exposes both input and output paths as a single object for
callbacks using the new signature.

```python
@property
def dataset_paths(self) -> RdeDatasetPaths
```

**Returns:**
- `RdeDatasetPaths`: Wrapper combining `RdeInputDirPaths` and `RdeOutputResourcePath`

**Example:**
```python
paths = context.dataset_paths
print(paths.inputdata)        # Same as context.srcpaths.inputdata
print(paths.struct)           # Same as context.resource_paths.struct
```

##### is_excel_mode

Check if this is Excel invoice processing mode.

```python
@property
def is_excel_mode(self) -> bool
```

**Returns:**
- `bool`: True if both excel_file and excel_index are set

**Example:**
```python
if context.is_excel_mode:
    print("Processing in Excel invoice mode")
```

##### excel_invoice_file

Get the Excel invoice file path (for Excel mode only).

```python
@property
def excel_invoice_file(self) -> Path
```

**Returns:**
- `Path`: Path to the Excel invoice file

**Raises:**
- `ValueError`: If excel_file is not set for this context

**Example:**
```python
if context.is_excel_mode:
    excel_file = context.excel_invoice_file
    print(f"Excel file: {excel_file}")
```

##### is_smarttable_mode

Check if this is SmartTable processing mode.

```python
@property
def is_smarttable_mode(self) -> bool
```

**Returns:**
- `bool`: True if smarttable_file is set

**Example:**
```python
if context.is_smarttable_mode:
    print("Processing in SmartTable mode")
```

##### smarttable_invoice_file

Get the SmartTable file path (for SmartTable mode only).

```python
@property
def smarttable_invoice_file(self) -> Path
```

**Returns:**
- `Path`: Path to the SmartTable file

**Raises:**
- `ValueError`: If smarttable_file is not set for this context

**Example:**
```python
if context.is_smarttable_mode:
    smarttable_file = context.smarttable_invoice_file
    print(f"SmartTable file: {smarttable_file}")
```

## Usage Examples

### Basic Context Creation

```python
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
from pathlib import Path

# Create input and output paths
srcpaths = RdeInputDirPaths(
    inputdata=Path("data/inputdata"),
    invoice=Path("data/invoice"),
    tasksupport=Path("data/tasksupport")
)

resource_paths = RdeOutputResourcePath(
    raw=Path("data/divided/0001/raw"),
    rawfiles=(Path("data/temp/sample.txt"),),
    struct=Path("data/divided/0001/structured"),
    main_image=Path("data/divided/0001/main_image"),
    # ... other paths
)

# Create processing context
context = ProcessingContext(
    index="1",
    srcpaths=srcpaths,
    resource_paths=resource_paths,
    datasets_function=None,
    mode_name="Invoice"
)
```

### Excel Mode Context

```python
# Create context for Excel invoice processing
excel_context = ProcessingContext(
    index="1",
    srcpaths=srcpaths,
    resource_paths=resource_paths,
    datasets_function=None,
    mode_name="ExcelInvoice",
    excel_file=Path("data/inputdata/dataset_excel_invoice.xlsx"),
    excel_index=1
)

# Check mode and access Excel-specific properties
if excel_context.is_excel_mode:
    excel_file = excel_context.excel_invoice_file
    print(f"Processing Excel file: {excel_file}")
```

### SmartTable Mode Context

```python
# Create context for SmartTable processing
smarttable_context = ProcessingContext(
    index="1",
    srcpaths=srcpaths,
    resource_paths=resource_paths,
    datasets_function=None,
    mode_name="SmartTableInvoice",
    smarttable_file=Path("data/inputdata/smarttable_data.csv")
)

# Check mode and access SmartTable-specific properties
if smarttable_context.is_smarttable_mode:
    smarttable_file = smarttable_context.smarttable_invoice_file
    print(f"Processing SmartTable file: {smarttable_file}")
```

### Using Context in Processors

```python
from rdetoolkit.processing.pipeline import Processor

class CustomProcessor(Processor):
    def process(self, context: ProcessingContext) -> None:
        # Access input configuration
        config = context.srcpaths.config

        # Get output paths
        raw_dir = context.resource_paths.raw
        structured_dir = context.resource_paths.struct

        # Check processing mode
        if context.is_excel_mode:
            excel_file = context.excel_invoice_file
            # Process Excel-specific logic
        elif context.is_smarttable_mode:
            smarttable_file = context.smarttable_invoice_file
            # Process SmartTable-specific logic
        else:
            # Standard processing logic
            pass

        # Access common paths
        invoice_dst = context.invoice_dst_filepath
        metadata_path = context.metadata_path
```

### Context with Custom Dataset Function

```python
def custom_dataset_function(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    """Custom processing function."""
    print(f"Processing {len(resource_paths.rawfiles)} files")
    # Custom processing logic here

# Create context with custom function
context = ProcessingContext(
    index="1",
    srcpaths=srcpaths,
    resource_paths=resource_paths,
    datasets_function=custom_dataset_function,
    mode_name="MultiDataTile"
)
```

## Error Handling

### Safe Property Access

```python
# Safe access to mode-specific properties
try:
    if context.is_excel_mode:
        excel_file = context.excel_invoice_file
        print(f"Excel file: {excel_file}")
except ValueError as e:
    print(f"Excel file not available: {e}")

try:
    if context.is_smarttable_mode:
        smarttable_file = context.smarttable_invoice_file
        print(f"SmartTable file: {smarttable_file}")
except ValueError as e:
    print(f"SmartTable file not available: {e}")
```

### Path Validation

```python
# Validate paths before processing
if not context.schema_path.exists():
    raise FileNotFoundError(f"Schema file not found: {context.schema_path}")

if not context.metadata_def_path.exists():
    print(f"Warning: Metadata definition not found: {context.metadata_def_path}")
```

## Best Practices

1. **Immutable Context**: Treat the context as immutable during processing
2. **Path Validation**: Always validate paths before using them
3. **Mode Checking**: Use mode properties to conditionally access mode-specific data
4. **Error Handling**: Handle ValueError exceptions when accessing mode-specific properties
5. **Resource Management**: Use context paths consistently across processors

## See Also

- [Pipeline Architecture](pipeline.md) - Core pipeline and processor classes
- [Processors](processors/index.md) - Individual processor implementations
- [Models](../models/rde2types.md) - Data type definitions
