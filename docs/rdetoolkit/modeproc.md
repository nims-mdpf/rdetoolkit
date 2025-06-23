# Mode Processing Module

The `rdetoolkit.modeproc` module provides specialized processing functions for different input modes in the RDE (Research Data Exchange) structuring pipeline. This module implements the core processing logic for various data input patterns and formats.

## Overview

The modeproc module handles different types of data processing modes, each tailored to specific input patterns and requirements:

- **Invoice Mode**: Standard invoice-based data processing
- **Excel Invoice Mode**: Processing with Excel-based invoice files
- **SmartTable Mode**: Advanced table-based processing with automated invoice generation
- **RDE Format Mode**: Processing using RDE format specifications
- **Multi-File Mode**: Handling multiple data files in parallel
- **Input File Classification**: Automatic detection and routing to appropriate processors

## Type Definitions

### _CallbackType

```python
_CallbackType = Callable[[RdeInputDirPaths, RdeOutputResourcePath], None]
```

A type alias for custom dataset processing functions that accept input paths and output resource paths.

## Functions

### invoice_mode_process

Process invoice-related data with standard RDE pipeline operations.

```python
def invoice_mode_process(
    index: str,
    srcpaths: RdeInputDirPaths,
    resource_paths: RdeOutputResourcePath,
    datasets_process_function: _CallbackType | None = None,
) -> WorkflowExecutionStatus
```

**Parameters:**

- `index` (str): Unique workflow execution identifier (run_id)
- `srcpaths` (RdeInputDirPaths): Input directory paths for source data
- `resource_paths` (RdeOutputResourcePath): Output resource paths for processed data
- `datasets_process_function` (_CallbackType | None): Optional custom dataset processing function

**Returns:**

- `WorkflowExecutionStatus`: Execution status containing run details, success/failure status, and error information

**Processing Steps:**

1. Copy input files to raw file directory
2. Execute custom dataset processing function (if provided)
3. Copy images to thumbnail directory
4. Replace `${filename}` placeholders in invoice with actual filenames
5. Update descriptions with features (errors ignored)
6. Validate metadata-def.json file
7. Validate invoice file against invoice schema

**Raises:**

- Propagates exceptions from `datasets_process_function`
- Validation errors during metadata or invoice validation

**Example:**

```python
from rdetoolkit.modeproc import invoice_mode_process
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
from pathlib import Path

def custom_invoice_processor(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    """Custom processing for invoice data."""
    print(f"Processing {len(resource_paths.rawfiles)} files")

    # Custom invoice processing logic
    for raw_file in resource_paths.rawfiles:
        if raw_file.suffix == '.csv':
            # Process CSV files
            processed_path = resource_paths.struct / f"processed_{raw_file.name}"
            # ... processing logic

# Setup paths
srcpaths = RdeInputDirPaths(
    inputdata=Path("data/inputdata"),
    invoice=Path("data/invoice"),
    tasksupport=Path("data/tasksupport")
)

resource_paths = RdeOutputResourcePath(
    raw=Path("data/raw"),
    rawfiles=(Path("data/inputdata/invoice.csv"),),
    struct=Path("data/structured"),
    # ... other paths
)

# Execute invoice mode processing
status = invoice_mode_process(
    index="001",
    srcpaths=srcpaths,
    resource_paths=resource_paths,
    datasets_process_function=custom_invoice_processor
)

print(f"Status: {status.status}")
print(f"Mode: {status.mode}")
```

### excel_invoice_mode_process

Process data using Excel-based invoice files with enhanced metadata handling.

```python
def excel_invoice_mode_process(
    srcpaths: RdeInputDirPaths,
    resource_paths: RdeOutputResourcePath,
    excel_invoice_file: Path,
    idx: int,
    datasets_process_function: _CallbackType | None = None,
) -> WorkflowExecutionStatus
```

**Parameters:**

- `srcpaths` (RdeInputDirPaths): Input directory paths for source data
- `resource_paths` (RdeOutputResourcePath): Output resource paths for processed data
- `excel_invoice_file` (Path): Path to the Excel invoice file
- `idx` (int): Index identifier for the data being processed
- `datasets_process_function` (_CallbackType | None): Optional custom dataset processing function

**Returns:**

- `WorkflowExecutionStatus`: Detailed execution status information

**Processing Steps:**

1. Overwrite Excel invoice file with processed data
2. Copy input files to raw file directory
3. Execute custom dataset processing function (if provided)
4. Replace `${filename}` placeholders in invoice
5. Copy images to thumbnail directory
6. Update descriptions with features (errors ignored)
7. Validate metadata-def.json file
8. Validate invoice file against schema

**Raises:**

- `StructuredError`: Issues with Excel invoice processing or validation
- Propagates exceptions from custom processing functions

**Example:**

```python
from rdetoolkit.modeproc import excel_invoice_mode_process
from pathlib import Path

def excel_data_processor(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    """Process data with Excel invoice context."""

    # Access Excel-specific processing
    for raw_file in resource_paths.rawfiles:
        if raw_file.suffix in ['.xlsx', '.xls']:
            # Excel-specific processing
            excel_data = pd.read_excel(raw_file)
            # Process Excel data...

        elif raw_file.suffix == '.csv':
            # CSV processing in Excel context
            csv_data = pd.read_csv(raw_file)
            # Process CSV data...

# Execute Excel invoice processing
excel_file = Path("data/inputdata/dataset_excel_invoice.xlsx")
status = excel_invoice_mode_process(
    srcpaths=srcpaths,
    resource_paths=resource_paths,
    excel_invoice_file=excel_file,
    idx=0,
    datasets_process_function=excel_data_processor
)
```

### smarttable_invoice_mode_process

Process SmartTable files to generate automated invoice data with intelligent table parsing.

```python
def smarttable_invoice_mode_process(
    index: str,
    srcpaths: RdeInputDirPaths,
    resource_paths: RdeOutputResourcePath,
    smarttable_file: Path,
    datasets_process_function: _CallbackType | None = None,
) -> WorkflowExecutionStatus
```

**Parameters:**

- `index` (str): Unique workflow execution identifier
- `srcpaths` (RdeInputDirPaths): Input directory paths
- `resource_paths` (RdeOutputResourcePath): Output resource paths
- `smarttable_file` (Path): Path to SmartTable file (.xlsx, .csv, .tsv)
- `datasets_process_function` (_CallbackType | None): Optional custom processing function

**Returns:**

- `WorkflowExecutionStatus`: Execution status with SmartTable-specific details

**Processing Steps:**

1. Initialize invoice from SmartTable file data
2. Copy input files to raw file directory
3. Execute custom dataset processing function (if provided)
4. Copy images to thumbnail directory
5. Replace filename placeholders in invoice
6. Update descriptions with features (errors ignored)
7. Validate metadata-def.json file
8. Validate invoice file against schema

**Raises:**

- `StructuredError`: SmartTable processing or validation errors
- Propagates exceptions from custom processing functions

**Supported SmartTable Formats:**

- Excel files (.xlsx, .xls)
- CSV files (.csv)
- TSV files (.tsv)

**Example:**

```python
from rdetoolkit.modeproc import smarttable_invoice_mode_process
from pathlib import Path
import pandas as pd

def smarttable_processor(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    """Custom processing for SmartTable data."""

    # SmartTable files are automatically processed for invoice generation
    # Custom processing can focus on data transformation

    for raw_file in resource_paths.rawfiles:
        if raw_file.suffix == '.csv':
            # Enhanced CSV processing with SmartTable context
            df = pd.read_csv(raw_file)

            # Apply SmartTable-aware transformations
            enhanced_df = df.copy()
            enhanced_df['processing_timestamp'] = pd.Timestamp.now()
            enhanced_df['smarttable_processed'] = True

            # Save enhanced data
            output_path = resource_paths.struct / f"enhanced_{raw_file.name}"
            enhanced_df.to_csv(output_path, index=False)

# Execute SmartTable processing
smarttable_file = Path("data/inputdata/smarttable_metadata.xlsx")
status = smarttable_invoice_mode_process(
    index="001",
    srcpaths=srcpaths,
    resource_paths=resource_paths,
    smarttable_file=smarttable_file,
    datasets_process_function=smarttable_processor
)

print(f"SmartTable processing status: {status.status}")
```

### rdeformat_mode_process

Process data using RDE format specifications with advanced structure handling.

```python
def rdeformat_mode_process(
    index: str,
    srcpaths: RdeInputDirPaths,
    resource_paths: RdeOutputResourcePath,
    datasets_process_function: _CallbackType | None = None,
) -> WorkflowExecutionStatus
```

**Parameters:**

- `index` (str): Unique workflow execution identifier
- `srcpaths` (RdeInputDirPaths): Input directory paths
- `resource_paths` (RdeOutputResourcePath): Output resource paths
- `datasets_process_function` (_CallbackType | None): Optional custom processing function

**Returns:**

- `WorkflowExecutionStatus`: Execution status for RDE format processing

**Processing Steps:**

1. Overwrite invoice file with RDE format specifications
2. Copy input files to raw file directory using RDE format rules
3. Execute custom dataset processing function (if provided)
4. Copy images to thumbnail directory
5. Update descriptions with features (errors ignored)
6. Validate metadata-def.json file
7. Validate invoice file against schema

**RDE Format Features:**

- Structured directory organization
- Predefined metadata schemas
- Standardized file naming conventions
- Automated validation pipelines

**Example:**

```python
from rdetoolkit.modeproc import rdeformat_mode_process
from pathlib import Path
import json

def rdeformat_processor(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    """Custom processing for RDE format data."""

    # RDE format provides structured processing
    rde_metadata = {
        "format_version": "2.0",
        "processing_mode": "rdeformat",
        "files_processed": []
    }

    for raw_file in resource_paths.rawfiles:
        # Process according to RDE format specifications
        if 'structured' in str(raw_file):
            # Handle structured data files
            structured_output = resource_paths.struct / raw_file.name
            # Copy and validate structured data
            import shutil
            shutil.copy2(raw_file, structured_output)

        elif 'meta' in str(raw_file):
            # Handle metadata files
            meta_output = resource_paths.meta / raw_file.name
            shutil.copy2(raw_file, meta_output)

        rde_metadata["files_processed"].append({
            "source": str(raw_file),
            "type": "structured" if 'structured' in str(raw_file) else "data"
        })

    # Save RDE processing metadata
    metadata_path = resource_paths.meta / "rde_processing_metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(rde_metadata, f, indent=2)

# Execute RDE format processing
status = rdeformat_mode_process(
    index="001",
    srcpaths=srcpaths,
    resource_paths=resource_paths,
    datasets_process_function=rdeformat_processor
)
```

### multifile_mode_process

Process multiple source files simultaneously with parallel processing capabilities.

```python
def multifile_mode_process(
    index: str,
    srcpaths: RdeInputDirPaths,
    resource_paths: RdeOutputResourcePath,
    datasets_process_function: _CallbackType | None = None,
) -> WorkflowExecutionStatus
```

**Parameters:**

- `index` (str): Unique workflow execution identifier
- `srcpaths` (RdeInputDirPaths): Input directory paths
- `resource_paths` (RdeOutputResourcePath): Output resource paths
- `datasets_process_function` (_CallbackType | None): Optional custom processing function

**Returns:**

- `WorkflowExecutionStatus`: Execution status for multi-file processing

**Processing Steps:**

1. Overwrite invoice file for multi-file context
2. Copy all input files to raw file directory
3. Execute custom dataset processing function (if provided)
4. Replace filename placeholders for all files
5. Copy images to thumbnail directory
6. Update descriptions with features (errors ignored)
7. Validate metadata-def.json file
8. Validate invoice file against schema

**Multi-File Features:**

- Parallel processing of multiple files
- Batch operations on file groups
- Coordinated metadata generation
- Error tolerance configuration

**Example:**

```python
from rdetoolkit.modeproc import multifile_mode_process
from pathlib import Path
import concurrent.futures
import pandas as pd

def multifile_processor(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    """Custom processing for multiple files."""

    def process_single_file(raw_file: Path) -> dict:
        """Process a single file and return metadata."""
        file_info = {
            "filename": raw_file.name,
            "size": raw_file.stat().st_size,
            "type": raw_file.suffix,
            "processed": False
        }

        try:
            if raw_file.suffix == '.csv':
                # Process CSV files
                df = pd.read_csv(raw_file)
                processed_path = resource_paths.struct / f"processed_{raw_file.name}"

                # Add processing metadata to DataFrame
                df['file_source'] = raw_file.name
                df['processing_index'] = resource_paths.rawfiles.index(raw_file)

                df.to_csv(processed_path, index=False)
                file_info["processed"] = True
                file_info["rows"] = len(df)

            elif raw_file.suffix in ['.txt', '.log']:
                # Process text files
                content = raw_file.read_text(encoding='utf-8')
                processed_path = resource_paths.struct / f"processed_{raw_file.name}"

                # Add processing header
                processed_content = f"# Processed from {raw_file.name}\n{content}"
                processed_path.write_text(processed_content, encoding='utf-8')

                file_info["processed"] = True
                file_info["lines"] = len(content.splitlines())

        except Exception as e:
            file_info["error"] = str(e)

        return file_info

    # Process files in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_file = {
            executor.submit(process_single_file, raw_file): raw_file
            for raw_file in resource_paths.rawfiles
        }

        results = []
        for future in concurrent.futures.as_completed(future_to_file):
            file_result = future.result()
            results.append(file_result)

    # Save batch processing results
    batch_metadata = {
        "total_files": len(resource_paths.rawfiles),
        "processed_files": sum(1 for r in results if r.get("processed", False)),
        "failed_files": sum(1 for r in results if "error" in r),
        "file_details": results
    }

    metadata_path = resource_paths.meta / "multifile_batch_metadata.json"
    import json
    with open(metadata_path, 'w') as f:
        json.dump(batch_metadata, f, indent=2)

# Execute multi-file processing
status = multifile_mode_process(
    index="001",
    srcpaths=srcpaths,
    resource_paths=resource_paths,
    datasets_process_function=multifile_processor
)

print(f"Processed {len(resource_paths.rawfiles)} files with status: {status.status}")
```

### copy_input_to_rawfile

Copy input raw files to a specified directory.

```python
def copy_input_to_rawfile(raw_dir_path: Path, raw_files: tuple[Path, ...]) -> None
```

**Parameters:**

- `raw_dir_path` (Path): Target directory for copying raw files
- `raw_files` (tuple[Path, ...]): Tuple of source file paths to copy

**Returns:**

- `None`

**Example:**

```python
from rdetoolkit.modeproc import copy_input_to_rawfile
from pathlib import Path

# Setup source files and target directory
raw_files = (
    Path("data/input/file1.csv"),
    Path("data/input/file2.txt"),
    Path("data/input/file3.json")
)

target_dir = Path("data/raw")
target_dir.mkdir(parents=True, exist_ok=True)

# Copy files to raw directory
copy_input_to_rawfile(target_dir, raw_files)

# Verify files were copied
for file in raw_files:
    copied_file = target_dir / file.name
    assert copied_file.exists(), f"File {file.name} not copied"
```

### copy_input_to_rawfile_for_rdeformat

Copy input files to appropriate directories based on RDE format directory structure.

```python
def copy_input_to_rawfile_for_rdeformat(resource_paths: RdeOutputResourcePath) -> None
```

**Parameters:**

- `resource_paths` (RdeOutputResourcePath): Resource paths containing source files and target directories

**Returns:**

- `None`

**Directory Mapping:**

- `raw` → `resource_paths.raw`
- `main_image` → `resource_paths.main_image`
- `other_image` → `resource_paths.other_image`
- `meta` → `resource_paths.meta`
- `structured` → `resource_paths.struct`
- `logs` → `resource_paths.logs`
- `nonshared_raw` → `resource_paths.nonshared_raw`

**Example:**

```python
from rdetoolkit.modeproc import copy_input_to_rawfile_for_rdeformat
from rdetoolkit.models.rde2types import RdeOutputResourcePath
from pathlib import Path

# Setup resource paths with RDE format structure
resource_paths = RdeOutputResourcePath(
    raw=Path("data/raw"),
    rawfiles=(
        Path("data/temp/raw/data.csv"),
        Path("data/temp/main_image/image.jpg"),
        Path("data/temp/meta/metadata.json"),
        Path("data/temp/structured/analysis.txt")
    ),
    struct=Path("data/structured"),
    main_image=Path("data/main_image"),
    other_image=Path("data/other_image"),
    meta=Path("data/meta"),
    logs=Path("data/logs"),
    # ... other paths
)

# Create target directories
for attr_name in ['raw', 'struct', 'main_image', 'other_image', 'meta', 'logs', 'nonshared_raw']:
    getattr(resource_paths, attr_name).mkdir(parents=True, exist_ok=True)

# Copy files according to RDE format rules
copy_input_to_rawfile_for_rdeformat(resource_paths)

# Files are automatically placed in correct directories based on their path structure
```

### selected_input_checker

Determine and return the appropriate input file checker based on file patterns and mode settings.

```python
def selected_input_checker(src_paths: RdeInputDirPaths, unpacked_dir_path: Path, mode: str | None) -> IInputFileChecker
```

**Parameters:**

- `src_paths` (RdeInputDirPaths): Source input file paths
- `unpacked_dir_path` (Path): Directory path for unpacked files
- `mode` (str | None): Processing mode specification

**Returns:**

- `IInputFileChecker`: Appropriate checker instance for the detected file type

**Checker Selection Logic:**

1. **SmartTableChecker**: If files starting with `smarttable_` and extensions `.xlsx`, `.csv`, `.tsv` are found
2. **ExcelInvoiceChecker**: If Excel files ending with `_excel_invoice` are found
3. **RDEFormatChecker**: If mode is `"rdeformat"`
4. **MultiFileChecker**: If mode is `"multidatatile"`
5. **InvoiceChecker**: Default fallback for standard invoice processing

**Example:**

```python
from rdetoolkit.modeproc import selected_input_checker
from rdetoolkit.models.rde2types import RdeInputDirPaths
from pathlib import Path

# Setup input paths
src_paths = RdeInputDirPaths(
    inputdata=Path("data/inputdata"),
    invoice=Path("data/invoice"),
    tasksupport=Path("data/tasksupport")
)

unpacked_dir = Path("data/temp")

# Test different scenarios

# Scenario 1: SmartTable files detected
# Files: smarttable_metadata.xlsx, data.csv
checker = selected_input_checker(src_paths, unpacked_dir, None)
print(f"Checker type: {checker.checker_type}")  # "smarttable"

# Scenario 2: Excel invoice files detected
# Files: dataset_excel_invoice.xlsx, data.zip
checker = selected_input_checker(src_paths, unpacked_dir, None)
print(f"Checker type: {checker.checker_type}")  # "excel_invoice"

# Scenario 3: RDE format mode
checker = selected_input_checker(src_paths, unpacked_dir, "rdeformat")
print(f"Checker type: {checker.checker_type}")  # "rdeformat"

# Scenario 4: Multi-file mode
checker = selected_input_checker(src_paths, unpacked_dir, "multidatatile")
print(f"Checker type: {checker.checker_type}")  # "multifile"

# Scenario 5: Default invoice mode
checker = selected_input_checker(src_paths, unpacked_dir, None)
print(f"Checker type: {checker.checker_type}")  # "invoice"
```

## WorkflowExecutionStatus

All processing functions return a `WorkflowExecutionStatus` object containing:

### Attributes

- `run_id` (str): Unique identifier for workflow execution (zero-padded to 4 digits)
- `title` (str): Descriptive title for the workflow execution
- `status` (str): Execution status (`"success"` or `"failed"`)
- `mode` (str): Processing mode used (e.g., `"invoice"`, `"rdeformat"`, `"Excelinvoice"`)
- `error_code` (int | None): Error code if execution failed
- `error_message` (str | None): Error message if execution failed
- `stacktrace` (str | None): Stack trace for debugging if execution failed
- `target` (str): Target directory or file path related to execution

### Example Status Handling

```python
from rdetoolkit.modeproc import invoice_mode_process

status = invoice_mode_process(
    index="001",
    srcpaths=srcpaths,
    resource_paths=resource_paths
)

if status.status == "success":
    print(f"Processing completed successfully")
    print(f"Mode: {status.mode}")
    print(f"Target: {status.target}")
else:
    print(f"Processing failed: {status.error_message}")
    print(f"Error code: {status.error_code}")
    if status.stacktrace:
        print(f"Stack trace: {status.stacktrace}")
```

## Error Handling

### Exception Types

- **StructuredError**: Raised for structured processing failures
- **Validation Errors**: During metadata or invoice schema validation
- **File Operation Errors**: During file copying or directory operations
- **Custom Function Errors**: Propagated from user-defined processing functions

### Best Practices

1. **Handle Custom Function Errors**:

   ```python
   def safe_processor(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
       try:
           # Your processing logic
           pass
       except Exception as e:
           logger.error(f"Custom processing failed: {e}")
           # Don't re-raise to allow workflow to continue
   ```

2. **Validate Inputs**:

   ```python
   def validated_processor(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
       if not resource_paths.rawfiles:
           print("No files to process")
           return

       for raw_file in resource_paths.rawfiles:
           if not raw_file.exists():
               print(f"Warning: File not found: {raw_file}")
               continue
           # Process file...
   ```

3. **Use Appropriate Error Tolerance**:

   ```python
   # In workflows.run() configuration
   config = Config(
       multidata_tile=MultiDataTileSettings(
           ignore_errors=True  # Continue processing on individual failures
       )
   )
   ```

## Integration Examples

### Complete Processing Workflow

```python
from rdetoolkit.modeproc import selected_input_checker, invoice_mode_process
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def comprehensive_processor(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    """Comprehensive data processing function."""

    logger.info(f"Starting processing of {len(resource_paths.rawfiles)} files")

    processing_summary = {
        "files_processed": 0,
        "files_failed": 0,
        "processing_details": []
    }

    for raw_file in resource_paths.rawfiles:
        try:
            file_detail = {"filename": raw_file.name, "status": "processing"}

            if raw_file.suffix == '.csv':
                # CSV processing
                import pandas as pd
                df = pd.read_csv(raw_file)

                # Data validation
                if df.empty:
                    raise ValueError("CSV file is empty")

                # Data transformation
                df['processed_timestamp'] = pd.Timestamp.now()
                df['source_file'] = raw_file.name

                # Save processed data
                output_path = resource_paths.struct / f"enhanced_{raw_file.name}"
                df.to_csv(output_path, index=False)

                file_detail.update({
                    "status": "success",
                    "rows_processed": len(df),
                    "output_file": str(output_path)
                })
                processing_summary["files_processed"] += 1

            elif raw_file.suffix in ['.txt', '.log']:
                # Text file processing
                content = raw_file.read_text(encoding='utf-8')

                # Text analysis
                lines = content.splitlines()
                word_count = len(content.split())

                # Enhanced content with metadata
                enhanced_content = f"""# Processing Metadata
# Original file: {raw_file.name}
# Lines: {len(lines)}
# Words: {word_count}
# Processed: {pd.Timestamp.now()}

{content}
"""

                # Save enhanced content
                output_path = resource_paths.struct / f"enhanced_{raw_file.name}"
                output_path.write_text(enhanced_content, encoding='utf-8')

                file_detail.update({
                    "status": "success",
                    "lines_processed": len(lines),
                    "words": word_count,
                    "output_file": str(output_path)
                })
                processing_summary["files_processed"] += 1

            else:
                # Handle other file types
                import shutil
                output_path = resource_paths.struct / raw_file.name
                shutil.copy2(raw_file, output_path)

                file_detail.update({
                    "status": "copied",
                    "output_file": str(output_path)
                })
                processing_summary["files_processed"] += 1

        except Exception as e:
            logger.error(f"Failed to process {raw_file.name}: {e}")
            file_detail.update({
                "status": "failed",
                "error": str(e)
            })
            processing_summary["files_failed"] += 1

        processing_summary["processing_details"].append(file_detail)

    # Save processing summary
    summary_path = resource_paths.meta / "processing_summary.json"
    import json
    with open(summary_path, 'w') as f:
        json.dump(processing_summary, f, indent=2, default=str)

    logger.info(f"Processing complete: {processing_summary['files_processed']} successful, {processing_summary['files_failed']} failed")

# Setup and execute processing
srcpaths = RdeInputDirPaths(
    inputdata=Path("data/inputdata"),
    invoice=Path("data/invoice"),
    tasksupport=Path("data/tasksupport")
)

# Automatically select appropriate checker
checker = selected_input_checker(srcpaths, Path("data/temp"), None)
raw_files, excel_file, smarttable_file = checker.parse(srcpaths.inputdata)

# Execute processing based on detected type
for idx, raw_file_group in enumerate(raw_files):
    resource_paths = RdeOutputResourcePath(
        raw=Path(f"data/raw/{idx:04d}"),
        rawfiles=raw_file_group,
        struct=Path(f"data/structured/{idx:04d}"),
        # ... setup other paths
    )

    # Create directories
    for attr_name in ['raw', 'struct', 'meta', 'main_image', 'thumbnail']:
        getattr(resource_paths, attr_name).mkdir(parents=True, exist_ok=True)

    # Execute appropriate processing mode
    if smarttable_file:
        from rdetoolkit.modeproc import smarttable_invoice_mode_process
        status = smarttable_invoice_mode_process(
            str(idx), srcpaths, resource_paths, smarttable_file, comprehensive_processor
        )
    elif excel_file:
        from rdetoolkit.modeproc import excel_invoice_mode_process
        status = excel_invoice_mode_process(
            srcpaths, resource_paths, excel_file, idx, comprehensive_processor
        )
    else:
        status = invoice_mode_process(
            str(idx), srcpaths, resource_paths, comprehensive_processor
        )

    print(f"Batch {idx}: {status.status} ({status.mode})")
```

## Performance Considerations

- **File I/O Optimization**: Use efficient file operations for large datasets
- **Memory Management**: Process files in chunks for large datasets
- **Parallel Processing**: Utilize multi-threading for independent file processing
- **Error Recovery**: Implement graceful error handling to continue processing other files
- **Progress Tracking**: Provide feedback for long-running operations

## See Also

- [Workflows Module](../workflows.md) - For orchestrating mode processing
- [Core Module](../core.md) - For directory management and file operations
- [Configuration Guide](../config.md) - For configuring processing behavior
- [Input Controllers](../input_controllers.md) - For file type detection and validation
