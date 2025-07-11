# Workflows Module

The `rdetoolkit.workflows` module provides the core workflow functionality for RDE (Research Data Exchange) data structuring processes. This module orchestrates the complete data processing pipeline, from input validation to structured output generation.

## Overview

The workflows module serves as the main entry point for RDE data processing operations. It handles:

- **Input File Classification**: Automatic detection and classification of input data types
- **Mode Processing**: Support for multiple processing modes (Invoice, ExcelInvoice, SmartTable, etc.)
- **Directory Management**: Creation and management of output directory structures
- **Workflow Execution**: Coordinated execution of the complete structuring pipeline
- **Error Handling**: Comprehensive error management with structured reporting

## Functions

### check_files

Classify input files to determine the appropriate processing pattern.

```python
def check_files(srcpaths: RdeInputDirPaths, *, mode: str | None) -> tuple[RawFiles, Path | None, Path | None]
```

**Parameters:**
- `srcpaths` (RdeInputDirPaths): Input directory paths containing source data
- `mode` (str | None): Processing mode override (optional)

**Returns:**
- `tuple[RawFiles, Path | None, Path | None]`: A tuple containing:
  - `RawFiles`: List of tuples with registered data file path groups
  - `Path | None`: Excel invoice file path (if present)
  - `Path | None`: SmartTable file path (if present)

**Processing Modes:**

1. **Invoice Mode**
   - File mode: Single file processing (e.g., `sample.txt`)
   - Folder mode: Multiple file processing (e.g., `sample1.txt`, `sample2.txt`)
   - No input: Empty input processing

2. **ExcelInvoice Mode**
   - File mode: ZIP file with Excel invoice (e.g., `sample.zip` + `*_excel_invoice.xlsx`)
   - Folder mode: Compressed folder with Excel invoice
   - Excel-only: Excel invoice file without data files

3. **Format Mode**
   - ZIP files with RDE format specification (e.g., `*.zip`, `tasksupport/rdeformat.txt`)

4. **Multiple Files Mode**
   - Flat structure with multiple files (e.g., `sample1.txt`, `sample2.txt`, `sample3.txt`)

**Examples:**

```python
from rdetoolkit.workflows import check_files
from rdetoolkit.models.rde2types import RdeInputDirPaths
from pathlib import Path

# Setup input paths
srcpaths = RdeInputDirPaths(
    inputdata=Path("data/inputdata"),
    invoice=Path("data/invoice"),
    tasksupport=Path("data/tasksupport")
)

# Invoice mode - single file
rawfiles, excel_file, smarttable_file = check_files(srcpaths, mode="invoice")
# Returns: ([(Path('data/inputdata/sample.txt'),)], None, None)

# Invoice mode - multiple files
rawfiles, excel_file, smarttable_file = check_files(srcpaths, mode="invoice")
# Returns: ([(Path('data/inputdata/sample1.txt'), Path('data/inputdata/sample2.txt'))], None, None)

# ExcelInvoice mode - with data files
rawfiles, excel_file, smarttable_file = check_files(srcpaths, mode="excelinvoice")
# Returns: ([(Path('data/temp/sample.txt'),)], Path("data/inputdata/dataset_excel_invoice.xlsx"), None)

# SmartTable mode
rawfiles, excel_file, smarttable_file = check_files(srcpaths, mode="smarttable")
# Returns: ([(Path('data/temp/sample.txt'),)], None, Path("data/inputdata/dataset_smarttable.xlsx"))
```

**Note:**
- Destination paths differ between modes:
  - Invoice: `/data/inputdata/<registered_files>`
  - ExcelInvoice/SmartTable: `/data/temp/<registered_files>`
- The function automatically detects file patterns and selects appropriate processing mode

### generate_folder_paths_iterator

Generate an iterator for RDE output folder paths with proper directory structure.

```python
def generate_folder_paths_iterator(
    raw_files_group: RawFiles,
    invoice_org_filepath: Path,
    invoice_schema_filepath: Path,
) -> Generator[RdeOutputResourcePath, None, None]
```

**Parameters:**
- `raw_files_group` (RawFiles): List of tuples containing raw file paths
- `invoice_org_filepath` (Path): Path to `invoice_org.json` file
- `invoice_schema_filepath` (Path): Path to `invoice.schema.json` file

**Yields:**
- `RdeOutputResourcePath`: Named tuple containing all output folder paths for RDE resources

**Raises:**
- `StructuredError`: When the structured process fails to process correctly

**Directory Structure:**

The iterator creates the following directory structure for each data tile:

```
data/
├── raw/                    # Raw data files
├── structured/            # Processed/structured data
├── main_image/           # Primary images
├── other_image/          # Additional images
├── thumbnail/            # Thumbnail images
├── meta/                 # Metadata files
├── logs/                 # Processing logs
├── invoice/              # Invoice data
├── temp/                 # Temporary files
├── nonshared_raw/        # Non-shared raw data
├── invoice_patch/        # Invoice patches
└── attachment/           # File attachments
```

**Example:**

```python
from rdetoolkit.workflows import generate_folder_paths_iterator
from pathlib import Path

# Example raw files
raw_files_group = [
    (Path('data/temp/sample1.txt'),),
    (Path('data/temp/sample2.txt'),),
    (Path('data/temp/sample3.txt'),)
]

# Invoice file paths
invoice_org = Path("data/invoice/invoice_org.json")
invoice_schema = Path("data/tasksupport/invoice.schema.json")

# Generate folder paths
for idx, resource_path in enumerate(generate_folder_paths_iterator(
    raw_files_group, invoice_org, invoice_schema
)):
    print(f"Data tile {idx}:")
    print(f"  Raw: {resource_path.raw}")
    print(f"  Structured: {resource_path.struct}")
    print(f"  Main Image: {resource_path.main_image}")
    print(f"  Thumbnail: {resource_path.thumbnail}")
    # ... other paths
```

**RdeOutputResourcePath Attributes:**

- `raw`: Raw data directory
- `rawfiles`: Tuple of source raw file paths
- `struct`: Structured data directory
- `main_image`: Main image directory
- `other_image`: Other images directory
- `thumbnail`: Thumbnail directory
- `meta`: Metadata directory
- `logs`: Logs directory
- `invoice`: Invoice directory
- `invoice_schema_json`: Invoice schema file path
- `invoice_org`: Original invoice file path
- `temp`: Temporary directory
- `nonshared_raw`: Non-shared raw data directory
- `invoice_patch`: Invoice patch directory
- `attachment`: Attachment directory

### run

Execute the complete RDE structuring processing pipeline.

```python
def run(*, custom_dataset_function: _CallbackType | None = None, config: Config | None = None) -> str
```

**Parameters:**
- `custom_dataset_function` (_CallbackType | None): User-defined structuring function (optional)
- `config` (Config | None): Configuration for the structuring process (optional, defaults loaded automatically)

**Returns:**
- `str`: JSON representation of workflow execution results

**Raises:**
- `StructuredError`: If a structured error occurs during processing
- `Exception`: If a generic error occurs during processing

**Callback Function Type:**

```python
_CallbackType = Callable[[RdeInputDirPaths, RdeOutputResourcePath], None]
```

The custom dataset function receives:
- `RdeInputDirPaths`: Parsed input directory paths
- `RdeOutputResourcePath`: Output directory paths for the current data tile

**Processing Modes:**

The function evaluates execution modes in the following order:

1. **SmartTableInvoice**: If SmartTable file is detected
2. **ExcelInvoice**: If Excel invoice file is detected
3. **RDEFormat**: If `extended_mode = "rdeformat"` in config
4. **MultiDataTile**: If `extended_mode = "multidatatile"` in config
5. **Invoice**: Default mode for standard invoice processing

**Examples:**

#### Basic Usage

```python
from rdetoolkit.workflows import run

# Execute with default configuration
result = run()
print("Workflow completed:", result)
```

#### With Custom Processing Function

```python
from rdetoolkit.workflows import run
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
import shutil

def custom_dataset(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    """Custom processing function for special data handling."""

    # Custom processing logic
    for raw_file in resource_paths.rawfiles:
        # Copy raw files to structured directory with processing
        processed_file = resource_paths.struct / f"processed_{raw_file.name}"
        shutil.copy2(raw_file, processed_file)

        # Additional custom processing...
        print(f"Processed: {raw_file} -> {processed_file}")

# Execute with custom function
result = run(custom_dataset_function=custom_dataset)
```

#### With Custom Configuration

```python
from rdetoolkit.workflows import run
from rdetoolkit.models.config import Config, SystemSettings, MultiDataTileSettings

# Standard configuration
config = Config(
    save_raw=True,
    save_main_image=False,
    save_thumbnail_image=False,
    magic_variable=False
)

result = run(config=config)

# Advanced configuration with extended mode
advanced_config = Config(
    system=SystemSettings(
        extended_mode="MultiDataTile",
        save_raw=False,
        save_nonshared_raw=True,
        save_thumbnail_image=True
    ),
    multidata_tile=MultiDataTileSettings(
        ignore_errors=False
    )
)

result = run(config=advanced_config)
```

#### Complete Workflow Example

```python
from rdetoolkit.workflows import run
from rdetoolkit.models.config import Config, SystemSettings
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
from pathlib import Path
import json

def advanced_custom_processor(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    """Advanced custom processing with metadata generation."""

    # Process each raw file
    metadata = {
        "processed_files": [],
        "processing_timestamp": "2024-01-01T00:00:00Z",
        "source_count": len(resource_paths.rawfiles)
    }

    for raw_file in resource_paths.rawfiles:
        if raw_file.suffix.lower() in ['.txt', '.csv']:
            # Text file processing
            content = raw_file.read_text(encoding='utf-8')
            processed_content = content.upper()  # Example processing

            # Save processed file
            output_file = resource_paths.struct / f"processed_{raw_file.name}"
            output_file.write_text(processed_content, encoding='utf-8')

            metadata["processed_files"].append({
                "source": str(raw_file),
                "output": str(output_file),
                "size": len(processed_content)
            })

    # Save metadata
    meta_file = resource_paths.meta / "processing_metadata.json"
    meta_file.write_text(json.dumps(metadata, indent=2), encoding='utf-8')

# Configuration for advanced processing
config = Config(
    system=SystemSettings(
        extended_mode="MultiDataTile",
        save_raw=True,
        save_nonshared_raw=False,
        save_thumbnail_image=True
    ),
    multidata_tile=MultiDataTileSettings(
        ignore_errors=True  # Continue processing even if some tiles fail
    )
)

# Execute advanced workflow
try:
    result_json = run(
        custom_dataset_function=advanced_custom_processor,
        config=config
    )

    # Parse and display results
    results = json.loads(result_json)
    print(f"Processed {len(results.get('statuses', []))} data tiles")

    for status in results.get('statuses', []):
        print(f"Tile {status['run_id']}: {status['status']} ({status['mode']})")

except Exception as e:
    print(f"Workflow failed: {e}")
```

## Workflow Execution Process

The `run` function follows this execution sequence:

### 1. Initialization
- Initialize logging system
- Create workflow result manager
- Setup input directory paths

### 2. Configuration Loading
- Load configuration from `tasksupport` directory
- Apply user-provided configuration overrides
- Validate configuration settings

### 3. Input Analysis
- Classify input files using `check_files`
- Determine processing mode
- Backup invoice files if needed

### 4. Resource Path Generation
- Generate output directory structure
- Create iterator for processing multiple data tiles
- Setup progress tracking

### 5. Data Processing
- Iterate through each data tile
- Execute mode-specific processing:
  - **SmartTableInvoice**: Process with SmartTable integration
  - **ExcelInvoice**: Process with Excel invoice data
  - **RDEFormat**: Process using RDE format specifications
  - **MultiDataTile**: Process multiple data tiles with error tolerance
  - **Invoice**: Standard invoice processing
- Execute custom dataset function if provided
- Track processing status and errors

### 6. Result Compilation
- Collect all processing statuses
- Generate comprehensive workflow results
- Return JSON representation of results

## Error Handling

### Structured Errors

The module provides comprehensive error handling for structured processing failures:

```python
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.workflows import run

try:
    result = run()
except StructuredError as e:
    print(f"Structured processing error: {e}")
    # Handle specific structured errors
except Exception as e:
    print(f"General error: {e}")
    # Handle other exceptions
```

### Error Status Creation

Failed processing creates detailed error status information:

```python
# Error status structure
{
    "run_id": "0",
    "title": "Structured Process Failed: Invoice",
    "status": "failed",
    "mode": "Invoice",
    "error_code": 999,
    "error_message": "Detailed error description",
    "stacktrace": "Full stack trace",
    "target": "processed_file1.txt,processed_file2.txt"
}
```

### Best Practices

1. **Always handle exceptions** in custom dataset functions:
   ```python
   def safe_custom_processor(srcpaths, resource_paths):
       try:
           # Your processing logic
           pass
       except Exception as e:
           print(f"Custom processing failed: {e}")
           # Log error but don't re-raise to continue workflow
   ```

2. **Use appropriate configuration** for error tolerance:
   ```python
   # For production: strict error handling
   config = Config(
       multidata_tile=MultiDataTileSettings(ignore_errors=False)
   )

   # For development: continue on errors
   config = Config(
       multidata_tile=MultiDataTileSettings(ignore_errors=True)
   )
   ```

3. **Validate inputs** in custom functions:
   ```python
   def validated_processor(srcpaths, resource_paths):
       if not resource_paths.rawfiles:
           print("No raw files to process")
           return

       for raw_file in resource_paths.rawfiles:
           if not raw_file.exists():
               print(f"Raw file not found: {raw_file}")
               continue
           # Process file...
   ```

## Performance Considerations

- **Memory Management**: The module uses iterators to avoid loading all data tiles into memory simultaneously
- **Progress Tracking**: Built-in progress bars provide real-time processing feedback
- **Parallel Processing**: Consider using multiprocessing for CPU-intensive custom functions
- **Error Recovery**: Configure error tolerance based on your processing requirements

## Integration Examples

### With Configuration Management

```python
from rdetoolkit.workflows import run
from rdetoolkit.models.config import load_config, Config
from pathlib import Path

# Load configuration from file
config_path = Path("config/custom_config.yaml")
config = load_config(str(config_path))

# Modify configuration programmatically
config.system.save_raw = True
config.system.save_thumbnail_image = False

result = run(config=config)
```

### with Logging Integration

```python
import logging
from rdetoolkit.workflows import run

# Setup custom logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('workflow.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def logged_processor(srcpaths, resource_paths):
    logger.info(f"Processing {len(resource_paths.rawfiles)} files")
    # Your processing logic
    logger.info("Processing completed successfully")

result = run(custom_dataset_function=logged_processor)
```

## See Also

- [Configuration Guide](../usage/config/config.md) - For detailed configuration options
- [Core Module](core.md) - For directory management and file operations
- [Models](models/rde2types.md) - For data type definitions and structures
- [Mode Processing](modeproc.md) - For specific processing mode implementations
