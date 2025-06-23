# Dataset Processor

The dataset processor executes custom dataset processing functions as part of the processing pipeline.

## Classes

### DatasetRunner

Executes user-provided custom dataset processing functions with comprehensive error handling and logging.

```python
class DatasetRunner(Processor):
    """Executes custom dataset processing functions."""
```

#### Methods

##### process

Execute custom dataset processing function if provided.

```python
def process(self, context: ProcessingContext) -> None
```

**Parameters:**
- `context` (ProcessingContext): Processing context containing dataset function and resources

**Behavior:**
- Checks if a custom dataset function is provided in the context
- Executes the function with input and output path parameters
- Handles function execution errors gracefully with logging
- Skips processing if no custom function is provided

**Custom Function Signature:**
The custom dataset function should accept two parameters:
- `srcpaths` (RdeInputDirPaths): Input directory paths and configuration
- `resource_paths` (RdeOutputResourcePath): Output resource paths

**Example:**
```python
from rdetoolkit.processing.processors import DatasetRunner

# Create and execute dataset runner
dataset_runner = DatasetRunner()
dataset_runner.process(context)
```

## Usage Examples

### Basic Dataset Function

```python
from rdetoolkit.processing.processors import DatasetRunner
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath

def simple_dataset_function(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    """Simple dataset processing function."""
    print(f"Processing {len(resource_paths.rawfiles)} files")

    # Process each raw file
    for raw_file in resource_paths.rawfiles:
        print(f"Processing file: {raw_file.name}")

        # Copy file to structured directory (example processing)
        structured_file = resource_paths.struct / raw_file.name
        resource_paths.struct.mkdir(parents=True, exist_ok=True)

        import shutil
        shutil.copy2(raw_file, structured_file)
        print(f"Copied to structured: {structured_file}")

# Create context with custom function
context = ProcessingContext(
    index="1",
    srcpaths=srcpaths,
    resource_paths=resource_paths,
    datasets_function=simple_dataset_function,
    mode_name="Invoice"
)

# Execute dataset processing
dataset_runner = DatasetRunner()
dataset_runner.process(context)
```

### Advanced Dataset Processing

```python
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
import json
import pandas as pd
from pathlib import Path

def advanced_dataset_function(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    """Advanced dataset processing with multiple file types."""

    config = srcpaths.config
    print(f"Processing in {config.system.extended_mode or 'standard'} mode")

    # Process different file types
    csv_files = [f for f in resource_paths.rawfiles if f.suffix == '.csv']
    image_files = [f for f in resource_paths.rawfiles if f.suffix.lower() in ['.jpg', '.png', '.tiff']]
    other_files = [f for f in resource_paths.rawfiles if f not in csv_files + image_files]

    # Process CSV files
    if csv_files:
        process_csv_files(csv_files, resource_paths)

    # Process image files
    if image_files:
        process_image_files(image_files, resource_paths, config)

    # Process other files
    if other_files:
        process_other_files(other_files, resource_paths)

    # Generate processing summary
    generate_processing_summary(resource_paths, len(csv_files), len(image_files), len(other_files))

def process_csv_files(csv_files: list[Path], resource_paths: RdeOutputResourcePath):
    """Process CSV files and create combined dataset."""
    combined_data = []

    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
            df['source_file'] = csv_file.name
            combined_data.append(df)
            print(f"Processed CSV: {csv_file.name} ({len(df)} rows)")
        except Exception as e:
            print(f"Error processing CSV {csv_file.name}: {e}")

    if combined_data:
        # Combine all CSV data
        combined_df = pd.concat(combined_data, ignore_index=True)

        # Save combined dataset
        output_file = resource_paths.struct / "combined_dataset.csv"
        resource_paths.struct.mkdir(parents=True, exist_ok=True)
        combined_df.to_csv(output_file, index=False)
        print(f"Created combined dataset: {output_file} ({len(combined_df)} rows)")

def process_image_files(image_files: list[Path], resource_paths: RdeOutputResourcePath, config):
    """Process image files with optional resizing."""
    from PIL import Image

    # Create image processing directories
    resource_paths.main_image.mkdir(parents=True, exist_ok=True)
    if config.save_thumbnail_image:
        resource_paths.thumbnail.mkdir(parents=True, exist_ok=True)

    for image_file in image_files:
        try:
            with Image.open(image_file) as img:
                # Save main image (potentially resized)
                main_image_path = resource_paths.main_image / image_file.name
                if img.size[0] > 1920 or img.size[1] > 1080:
                    img.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
                img.save(main_image_path)

                # Create thumbnail if enabled
                if config.save_thumbnail_image:
                    thumbnail_path = resource_paths.thumbnail / f"thumb_{image_file.name}"
                    img.thumbnail((200, 200), Image.Resampling.LANCZOS)
                    img.save(thumbnail_path)

                print(f"Processed image: {image_file.name}")

        except Exception as e:
            print(f"Error processing image {image_file.name}: {e}")

def process_other_files(other_files: list[Path], resource_paths: RdeOutputResourcePath):
    """Process other file types."""
    import shutil

    resource_paths.struct.mkdir(parents=True, exist_ok=True)

    for file in other_files:
        try:
            output_file = resource_paths.struct / file.name
            shutil.copy2(file, output_file)
            print(f"Copied file: {file.name}")
        except Exception as e:
            print(f"Error copying file {file.name}: {e}")

def generate_processing_summary(resource_paths: RdeOutputResourcePath, csv_count: int, image_count: int, other_count: int):
    """Generate processing summary."""
    summary = {
        "processing_summary": {
            "total_files": csv_count + image_count + other_count,
            "csv_files": csv_count,
            "image_files": image_count,
            "other_files": other_count,
            "output_directories": {
                "structured": str(resource_paths.struct),
                "main_image": str(resource_paths.main_image),
                "thumbnail": str(resource_paths.thumbnail),
                "meta": str(resource_paths.meta)
            }
        }
    }

    # Save summary
    summary_file = resource_paths.meta / "processing_summary.json"
    resource_paths.meta.mkdir(parents=True, exist_ok=True)

    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"Generated processing summary: {summary_file}")

# Usage
context_with_advanced_function = ProcessingContext(
    index="1",
    srcpaths=srcpaths,
    resource_paths=resource_paths,
    datasets_function=advanced_dataset_function,
    mode_name="MultiDataTile"
)

dataset_runner = DatasetRunner()
dataset_runner.process(context_with_advanced_function)
```

### Conditional Dataset Processing

```python
def conditional_dataset_function(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    """Dataset function with conditional processing based on configuration."""

    config = srcpaths.config

    # Check processing mode
    if hasattr(config.system, 'extended_mode') and config.system.extended_mode:
        mode = config.system.extended_mode.lower()
        print(f"Processing in extended mode: {mode}")

        if mode == "rdeformat":
            process_rde_format_data(resource_paths)
        elif mode == "multidatatile":
            process_multi_data_tile(resource_paths, config)
        else:
            process_standard_data(resource_paths)
    else:
        process_standard_data(resource_paths)

    # Always generate metadata
    generate_metadata(resource_paths, config)

def process_rde_format_data(resource_paths: RdeOutputResourcePath):
    """Process data in RDE format mode."""
    print("Processing RDE format data...")

    # RDE format specific processing
    for raw_file in resource_paths.rawfiles:
        if raw_file.suffix == '.zip':
            extract_and_process_zip(raw_file, resource_paths)
        else:
            copy_file_to_structured(raw_file, resource_paths)

def process_multi_data_tile(resource_paths: RdeOutputResourcePath, config):
    """Process data in multi-data tile mode."""
    print("Processing multi-data tile...")

    # Group files by type for tile processing
    file_groups = group_files_by_type(resource_paths.rawfiles)

    for file_type, files in file_groups.items():
        process_file_group(file_type, files, resource_paths, config)

def process_standard_data(resource_paths: RdeOutputResourcePath):
    """Standard data processing."""
    print("Processing standard data...")

    import shutil
    resource_paths.struct.mkdir(parents=True, exist_ok=True)

    for raw_file in resource_paths.rawfiles:
        output_file = resource_paths.struct / raw_file.name
        shutil.copy2(raw_file, output_file)

def generate_metadata(resource_paths: RdeOutputResourcePath, config):
    """Generate metadata for processed data."""
    metadata = {
        "files_processed": len(resource_paths.rawfiles),
        "configuration": {
            "save_raw": config.save_raw,
            "save_thumbnail_image": config.save_thumbnail_image,
            "magic_variable": config.magic_variable
        },
        "processing_timestamp": pd.Timestamp.now().isoformat()
    }

    # Save metadata
    metadata_file = resource_paths.meta / "dataset_metadata.json"
    resource_paths.meta.mkdir(parents=True, exist_ok=True)

    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)

# Additional helper functions
def extract_and_process_zip(zip_file: Path, resource_paths: RdeOutputResourcePath):
    """Extract and process ZIP files."""
    import zipfile

    extract_dir = resource_paths.temp / f"extracted_{zip_file.stem}"
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    # Process extracted files
    for extracted_file in extract_dir.rglob('*'):
        if extracted_file.is_file():
            copy_file_to_structured(extracted_file, resource_paths)

def copy_file_to_structured(file: Path, resource_paths: RdeOutputResourcePath):
    """Copy file to structured directory."""
    import shutil

    resource_paths.struct.mkdir(parents=True, exist_ok=True)
    output_file = resource_paths.struct / file.name
    shutil.copy2(file, output_file)

def group_files_by_type(files: tuple[Path, ...]) -> dict[str, list[Path]]:
    """Group files by their extension."""
    groups = {}

    for file in files:
        ext = file.suffix.lower()
        if ext not in groups:
            groups[ext] = []
        groups[ext].append(file)

    return groups

def process_file_group(file_type: str, files: list[Path], resource_paths: RdeOutputResourcePath, config):
    """Process a group of files of the same type."""
    print(f"Processing {len(files)} {file_type} files")

    if file_type in ['.jpg', '.png', '.tiff'] and config.save_thumbnail_image:
        # Special handling for images
        process_image_files(files, resource_paths, config)
    else:
        # Standard file copying
        for file in files:
            copy_file_to_structured(file, resource_paths)

# Usage with conditional processing
context_conditional = ProcessingContext(
    index="1",
    srcpaths=srcpaths,
    resource_paths=resource_paths,
    datasets_function=conditional_dataset_function,
    mode_name="MultiDataTile"
)

dataset_runner = DatasetRunner()
dataset_runner.process(context_conditional)
```

### Error-Resilient Dataset Processing

```python
def resilient_dataset_function(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    """Dataset function with comprehensive error handling."""

    processing_log = []
    successful_files = 0
    failed_files = 0

    try:
        print(f"Starting processing of {len(resource_paths.rawfiles)} files")

        for i, raw_file in enumerate(resource_paths.rawfiles):
            file_log = {
                "file": str(raw_file),
                "index": i,
                "status": "pending"
            }

            try:
                # Process individual file
                process_single_file(raw_file, resource_paths, srcpaths.config)

                file_log["status"] = "success"
                successful_files += 1
                print(f"✓ Processed {raw_file.name}")

            except Exception as e:
                file_log["status"] = "failed"
                file_log["error"] = str(e)
                failed_files += 1
                print(f"✗ Failed to process {raw_file.name}: {e}")

            processing_log.append(file_log)

    except Exception as e:
        print(f"Critical error in dataset processing: {e}")
        raise

    finally:
        # Always save processing log
        save_processing_log(processing_log, resource_paths, successful_files, failed_files)

def process_single_file(raw_file: Path, resource_paths: RdeOutputResourcePath, config) -> None:
    """Process a single file with error handling."""

    # Validate file exists and is readable
    if not raw_file.exists():
        raise FileNotFoundError(f"File not found: {raw_file}")

    if not raw_file.is_file():
        raise ValueError(f"Path is not a file: {raw_file}")

    # Process based on file type
    file_ext = raw_file.suffix.lower()

    if file_ext == '.csv':
        process_csv_file(raw_file, resource_paths)
    elif file_ext in ['.jpg', '.png', '.tiff']:
        process_image_file(raw_file, resource_paths, config)
    elif file_ext == '.json':
        process_json_file(raw_file, resource_paths)
    else:
        process_generic_file(raw_file, resource_paths)

def process_csv_file(csv_file: Path, resource_paths: RdeOutputResourcePath):
    """Process CSV file with validation."""
    try:
        df = pd.read_csv(csv_file)

        if len(df) == 0:
            raise ValueError("CSV file is empty")

        # Save processed CSV
        output_file = resource_paths.struct / csv_file.name
        resource_paths.struct.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_file, index=False)

    except pd.errors.EmptyDataError:
        raise ValueError("CSV file contains no data")
    except pd.errors.ParserError as e:
        raise ValueError(f"CSV parsing error: {e}")

def process_image_file(image_file: Path, resource_paths: RdeOutputResourcePath, config):
    """Process image file with validation."""
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(image_file) as img:
            # Validate image
            img.verify()

        # Process image (reopen after verify)
        with Image.open(image_file) as img:
            output_file = resource_paths.main_image / image_file.name
            resource_paths.main_image.mkdir(parents=True, exist_ok=True)

            # Resize if too large
            if img.size[0] > 2000 or img.size[1] > 2000:
                img.thumbnail((2000, 2000), Image.Resampling.LANCZOS)

            img.save(output_file)

    except UnidentifiedImageError:
        raise ValueError("File is not a valid image")
    except Exception as e:
        raise ValueError(f"Image processing error: {e}")

def process_json_file(json_file: Path, resource_paths: RdeOutputResourcePath):
    """Process JSON file with validation."""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Validate JSON structure (example validation)
        if not isinstance(data, dict):
            raise ValueError("JSON must be an object")

        # Save processed JSON
        output_file = resource_paths.struct / json_file.name
        resource_paths.struct.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")

def process_generic_file(file: Path, resource_paths: RdeOutputResourcePath):
    """Process generic file by copying."""
    import shutil

    output_file = resource_paths.struct / file.name
    resource_paths.struct.mkdir(parents=True, exist_ok=True)
    shutil.copy2(file, output_file)

def save_processing_log(processing_log: list, resource_paths: RdeOutputResourcePath, successful: int, failed: int):
    """Save processing log with summary."""

    log_data = {
        "summary": {
            "total_files": len(processing_log),
            "successful": successful,
            "failed": failed,
            "success_rate": successful / len(processing_log) if processing_log else 0
        },
        "files": processing_log,
        "timestamp": pd.Timestamp.now().isoformat()
    }

    # Save log
    log_file = resource_paths.logs / "dataset_processing.log"
    resource_paths.logs.mkdir(parents=True, exist_ok=True)

    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    print(f"Processing complete: {successful}/{len(processing_log)} files successful")
    print(f"Processing log saved: {log_file}")

# Usage with error-resilient processing
context_resilient = ProcessingContext(
    index="1",
    srcpaths=srcpaths,
    resource_paths=resource_paths,
    datasets_function=resilient_dataset_function,
    mode_name="Invoice"
)

dataset_runner = DatasetRunner()
dataset_runner.process(context_resilient)
```

### No Custom Function Handling

```python
def test_without_custom_function():
    """Test DatasetRunner when no custom function is provided."""

    # Context without custom function
    context_no_function = ProcessingContext(
        index="1",
        srcpaths=srcpaths,
        resource_paths=resource_paths,
        datasets_function=None,  # No custom function
        mode_name="Invoice"
    )

    dataset_runner = DatasetRunner()
    dataset_runner.process(context_no_function)  # Should skip processing gracefully

    print("DatasetRunner completed (no custom function provided)")

# Test
test_without_custom_function()
```

## Error Handling

### Function Execution Errors

The DatasetRunner handles errors in custom dataset functions gracefully:

```python
def error_prone_function(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    """Function that may raise errors."""

    # This will raise an error
    raise ValueError("Something went wrong in custom processing")

# Create context with error-prone function
context_with_error = ProcessingContext(
    index="1",
    srcpaths=srcpaths,
    resource_paths=resource_paths,
    datasets_function=error_prone_function,
    mode_name="Invoice"
)

# DatasetRunner will catch and log the error
dataset_runner = DatasetRunner()
try:
    dataset_runner.process(context_with_error)
except Exception as e:
    print(f"Custom function error was handled: {e}")
```

### Validation and Safety

```python
def safe_dataset_function(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    """Dataset function with safety checks."""

    # Validate input parameters
    if not resource_paths.rawfiles:
        print("Warning: No raw files to process")
        return

    # Validate output directories can be created
    required_dirs = [resource_paths.struct, resource_paths.meta]
    for dir_path in required_dirs:
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise PermissionError(f"Cannot create directory {dir_path}: {e}")

    # Safe file processing
    for raw_file in resource_paths.rawfiles:
        if raw_file.exists() and raw_file.is_file():
            try:
                # Process file safely
                process_file_safely(raw_file, resource_paths)
            except Exception as e:
                print(f"Warning: Failed to process {raw_file.name}: {e}")
                # Continue with other files
        else:
            print(f"Warning: Skipping invalid file: {raw_file}")

def process_file_safely(file: Path, resource_paths: RdeOutputResourcePath):
    """Process file with safety checks."""
    import shutil

    # Check file size (avoid processing extremely large files)
    file_size = file.stat().st_size
    max_size = 100 * 1024 * 1024  # 100MB limit

    if file_size > max_size:
        raise ValueError(f"File too large: {file_size} bytes")

    # Copy file safely
    output_file = resource_paths.struct / file.name
    shutil.copy2(file, output_file)

# Usage with safe function
context_safe = ProcessingContext(
    index="1",
    srcpaths=srcpaths,
    resource_paths=resource_paths,
    datasets_function=safe_dataset_function,
    mode_name="Invoice"
)

dataset_runner = DatasetRunner()
dataset_runner.process(context_safe)
```

## Performance Considerations

- **Memory Usage**: Avoid loading large files entirely into memory
- **I/O Operations**: Minimize disk I/O through efficient file handling
- **Error Recovery**: Implement graceful error handling for partial failures
- **Progress Tracking**: Provide feedback for long-running operations
- **Resource Cleanup**: Ensure proper cleanup of temporary resources

## See Also

- [Processing Context](../context.md) - Context management and configuration
- [Pipeline Architecture](../pipeline.md) - Core pipeline classes
- [File Processors](files.md) - File copying and management
- [Validation Processors](validation.md) - Data validation
