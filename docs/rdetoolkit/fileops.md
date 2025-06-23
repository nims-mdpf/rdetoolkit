# File Operations Module

The `rdetoolkit.fileops` module provides essential file operation utilities for RDE (Research Data Exchange) processing workflows. This module focuses on robust JSON file handling with automatic encoding detection and comprehensive error management.

## Overview

The fileops module offers reliable file operations with built-in safety features:

- **Automatic Encoding Detection**: Intelligent detection of file encodings for robust reading
- **Error Handling**: Comprehensive error management with structured exceptions
- **JSON Processing**: Specialized functions for JSON file reading and writing
- **Encoding Normalization**: Consistent encoding handling across different platforms
- **Logging Integration**: Built-in logging for debugging and monitoring
- **Path Flexibility**: Support for both string and Path object inputs

## Functions

### readf_json

Read a JSON file and return the parsed JSON object with automatic encoding detection.

```python
def readf_json(path: str | Path) -> dict[str, Any]
```

**Parameters:**
- `path` (str | Path): Path to the JSON file to read

**Returns:**
- `dict[str, Any]`: The parsed JSON object as a dictionary

**Raises:**
- `StructuredError`: If an error occurs while processing the file (file not found, invalid JSON, encoding issues, etc.)

**Features:**
- Automatic encoding detection using the core module's `detect_encoding` function
- Encoding normalization for cross-platform compatibility
- Comprehensive error handling with detailed error messages
- Logging integration for debugging and monitoring
- Support for both string paths and Path objects

**Example:**

```python
from rdetoolkit.fileops import readf_json
from pathlib import Path
import json

# Basic usage with string path
try:
    data = readf_json("data/config/settings.json")
    print(f"Loaded settings: {data}")
except StructuredError as e:
    print(f"Failed to load settings: {e}")

# Usage with Path object
config_path = Path("data/invoice/invoice.json")
try:
    invoice_data = readf_json(config_path)
    print(f"Invoice title: {invoice_data.get('basic', {}).get('title', 'Unknown')}")
    print(f"Sample count: {len(invoice_data.get('sample', {}).get('names', []))}")
except StructuredError as e:
    print(f"Failed to load invoice: {e}")

# Reading files with various encodings
file_paths = [
    "data/utf8_file.json",
    "data/shift_jis_file.json",
    "data/utf16_file.json"
]

for file_path in file_paths:
    try:
        data = readf_json(file_path)
        print(f"Successfully read {file_path}: {len(data)} keys")
    except StructuredError as e:
        print(f"Failed to read {file_path}: {e}")

# Error handling example
def safe_json_read(file_path: str) -> dict | None:
    """Safely read JSON file with error handling."""
    try:
        return readf_json(file_path)
    except StructuredError as e:
        print(f"Error reading {file_path}: {e}")
        return None

# Usage in batch processing
def load_multiple_configs(config_dir: Path) -> dict[str, dict]:
    """Load multiple JSON configuration files."""
    configs = {}

    for json_file in config_dir.glob("*.json"):
        try:
            config_data = readf_json(json_file)
            configs[json_file.stem] = config_data
            print(f"✓ Loaded config: {json_file.name}")
        except StructuredError as e:
            print(f"✗ Failed to load {json_file.name}: {e}")

    return configs

# Example usage
config_directory = Path("data/configs")
all_configs = load_multiple_configs(config_directory)
print(f"Loaded {len(all_configs)} configuration files")
```

### writef_json

Write a dictionary object to a JSON file with specified encoding.

```python
def writef_json(path: str | Path, obj: dict[str, Any], *, enc: str = "utf_8") -> dict[str, Any]
```

**Parameters:**
- `path` (str | Path): Path to the destination JSON file
- `obj` (dict[str, Any]): Dictionary object to be serialized and written
- `enc` (str): Encoding to use when writing the file (default: "utf_8")

**Returns:**
- `dict[str, Any]`: The same dictionary object that was written (for chaining operations)

**Features:**
- Pretty-printed JSON output with 4-space indentation
- Unicode support with `ensure_ascii=False` for international characters
- Flexible encoding specification
- Support for both string paths and Path objects
- Returns the input object for method chaining

**Example:**

```python
from rdetoolkit.fileops import writef_json
from pathlib import Path
import datetime

# Basic usage
data = {
    "title": "Sample Dataset",
    "description": "This is a test dataset",
    "created": datetime.datetime.now().isoformat(),
    "version": "1.0.0"
}

output_path = "data/output/sample.json"
written_data = writef_json(output_path, data)
print(f"Written data keys: {list(written_data.keys())}")

# Usage with Path object and custom encoding
metadata = {
    "experiment_id": "EXP_2024_001",
    "researcher": "田中太郎",  # Japanese characters
    "location": "東京大学",
    "measurements": [
        {"temperature": 25.5, "unit": "°C"},
        {"pressure": 1013.25, "unit": "hPa"}
    ]
}

output_path = Path("data/metadata/experiment_metadata.json")
writef_json(output_path, metadata, enc="utf_8")

# Method chaining example
def create_and_save_config(name: str, settings: dict) -> dict:
    """Create configuration and save to file."""
    config = {
        "name": name,
        "created_at": datetime.datetime.now().isoformat(),
        "settings": settings,
        "version": "1.0"
    }

    file_path = f"data/configs/{name.lower()}.json"
    return writef_json(file_path, config)

# Usage
app_config = create_and_save_config("Application", {
    "debug": True,
    "log_level": "INFO",
    "max_workers": 4
})

# Batch writing example
def save_multiple_files(data_dict: dict[str, dict], output_dir: Path) -> list[Path]:
    """Save multiple dictionaries as separate JSON files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    saved_files = []

    for filename, data in data_dict.items():
        file_path = output_dir / f"{filename}.json"
        try:
            writef_json(file_path, data)
            saved_files.append(file_path)
            print(f"✓ Saved: {file_path}")
        except Exception as e:
            print(f"✗ Failed to save {file_path}: {e}")

    return saved_files

# Example data
datasets = {
    "dataset_a": {
        "samples": 100,
        "type": "experimental",
        "status": "completed"
    },
    "dataset_b": {
        "samples": 250,
        "type": "observational",
        "status": "in_progress"
    }
}

output_directory = Path("data/datasets")
saved_paths = save_multiple_files(datasets, output_directory)
print(f"Saved {len(saved_paths)} dataset files")
```

## Complete Usage Examples

### JSON Configuration Manager

```python
from rdetoolkit.fileops import readf_json, writef_json
from rdetoolkit.exceptions import StructuredError
from pathlib import Path
import datetime
import json
from typing import Dict, Any, Optional, List

class JSONConfigManager:
    """A comprehensive JSON configuration file manager."""

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.loaded_configs: Dict[str, Dict[str, Any]] = {}

    def load_config(self, config_name: str) -> Optional[Dict[str, Any]]:
        """Load a single configuration file."""
        config_path = self.config_dir / f"{config_name}.json"

        try:
            config_data = readf_json(config_path)
            self.loaded_configs[config_name] = config_data
            print(f"✓ Loaded config: {config_name}")
            return config_data
        except StructuredError as e:
            print(f"✗ Failed to load config {config_name}: {e}")
            return None

    def save_config(self, config_name: str, config_data: Dict[str, Any]) -> bool:
        """Save a configuration file."""
        config_path = self.config_dir / f"{config_name}.json"

        try:
            # Add metadata
            config_with_meta = {
                "_metadata": {
                    "saved_at": datetime.datetime.now().isoformat(),
                    "version": "1.0",
                    "config_name": config_name
                },
                **config_data
            }

            writef_json(config_path, config_with_meta)
            self.loaded_configs[config_name] = config_with_meta
            print(f"✓ Saved config: {config_name}")
            return True
        except Exception as e:
            print(f"✗ Failed to save config {config_name}: {e}")
            return False

    def load_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """Load all JSON configuration files in the directory."""
        configs = {}

        for json_file in self.config_dir.glob("*.json"):
            config_name = json_file.stem
            config_data = self.load_config(config_name)
            if config_data:
                configs[config_name] = config_data

        return configs

    def get_config(self, config_name: str, key: str = None, default: Any = None) -> Any:
        """Get configuration value with optional key path."""
        if config_name not in self.loaded_configs:
            config_data = self.load_config(config_name)
            if not config_data:
                return default

        config = self.loaded_configs[config_name]

        if key is None:
            return config

        # Support nested key access like "database.host"
        keys = key.split('.')
        value = config

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def update_config(self, config_name: str, updates: Dict[str, Any]) -> bool:
        """Update an existing configuration."""
        if config_name not in self.loaded_configs:
            if not self.load_config(config_name):
                return False

        config = self.loaded_configs[config_name].copy()
        config.update(updates)

        return self.save_config(config_name, config)

    def backup_configs(self, backup_dir: Path) -> List[Path]:
        """Create backup copies of all configuration files."""
        backup_dir.mkdir(parents=True, exist_ok=True)
        backed_up_files = []

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        for config_name, config_data in self.loaded_configs.items():
            backup_filename = f"{config_name}_backup_{timestamp}.json"
            backup_path = backup_dir / backup_filename

            try:
                writef_json(backup_path, config_data)
                backed_up_files.append(backup_path)
                print(f"✓ Backed up: {backup_filename}")
            except Exception as e:
                print(f"✗ Failed to backup {config_name}: {e}")

        return backed_up_files

    def validate_config_schema(self, config_name: str, required_keys: List[str]) -> bool:
        """Validate that a configuration contains required keys."""
        config = self.get_config(config_name)
        if not config:
            return False

        missing_keys = [key for key in required_keys if key not in config]
        if missing_keys:
            print(f"Config {config_name} missing required keys: {missing_keys}")
            return False

        return True

# Usage example
def demonstrate_config_manager():
    """Demonstrate the JSON configuration manager."""

    # Setup manager
    config_dir = Path("data/configs")
    manager = JSONConfigManager(config_dir)

    # Create sample configurations
    database_config = {
        "host": "localhost",
        "port": 5432,
        "database": "research_db",
        "username": "researcher",
        "pool_size": 10,
        "ssl": True
    }

    app_config = {
        "name": "RDE Toolkit",
        "debug": False,
        "log_level": "INFO",
        "features": {
            "auto_backup": True,
            "compression": True,
            "validation": True
        },
        "limits": {
            "max_file_size": "100MB",
            "max_concurrent_jobs": 4
        }
    }

    processing_config = {
        "batch_size": 50,
        "timeout": 300,
        "retry_attempts": 3,
        "output_format": "json",
        "compression": "gzip"
    }

    # Save configurations
    manager.save_config("database", database_config)
    manager.save_config("application", app_config)
    manager.save_config("processing", processing_config)

    # Load and use configurations
    db_host = manager.get_config("database", "host")
    app_name = manager.get_config("application", "name")
    debug_mode = manager.get_config("application", "debug", False)

    print(f"Database host: {db_host}")
    print(f"Application name: {app_name}")
    print(f"Debug mode: {debug_mode}")

    # Update configuration
    manager.update_config("application", {
        "debug": True,
        "log_level": "DEBUG"
    })

    # Validate configurations
    required_db_keys = ["host", "port", "database", "username"]
    is_valid = manager.validate_config_schema("database", required_db_keys)
    print(f"Database config valid: {is_valid}")

    # Load all configurations
    all_configs = manager.load_all_configs()
    print(f"Loaded {len(all_configs)} configurations")

    # Create backups
    backup_dir = Path("data/backups")
    backed_up_files = manager.backup_configs(backup_dir)
    print(f"Created {len(backed_up_files)} backup files")

if __name__ == "__main__":
    demonstrate_config_manager()
```

### Advanced JSON Processing Pipeline

```python
from rdetoolkit.fileops import readf_json, writef_json
from rdetoolkit.exceptions import StructuredError
from pathlib import Path
import datetime
import hashlib
import shutil
from typing import Dict, Any, List, Optional, Callable
import json

class JSONProcessingPipeline:
    """Advanced JSON file processing pipeline with validation and transformation."""

    def __init__(self, input_dir: Path, output_dir: Path, working_dir: Path):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.working_dir = working_dir
        self.backup_dir = working_dir / "backups"

        # Create directories
        for directory in [self.output_dir, self.working_dir, self.backup_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        self.processing_log = []
        self.transformations: List[Callable[[Dict[str, Any]], Dict[str, Any]]] = []

    def add_transformation(self, transform_func: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        """Add a transformation function to the pipeline."""
        self.transformations.append(transform_func)

    def process_file(self, input_path: Path) -> Optional[Dict[str, Any]]:
        """Process a single JSON file through the pipeline."""

        start_time = datetime.datetime.now()

        try:
            # Read input file
            original_data = readf_json(input_path)

            # Create backup
            backup_path = self.backup_dir / f"{input_path.stem}_backup_{start_time.strftime('%Y%m%d_%H%M%S')}.json"
            writef_json(backup_path, original_data)

            # Apply transformations
            processed_data = original_data.copy()

            for i, transform_func in enumerate(self.transformations):
                try:
                    processed_data = transform_func(processed_data)
                    print(f"  ✓ Applied transformation {i+1}")
                except Exception as e:
                    print(f"  ✗ Transformation {i+1} failed: {e}")
                    # Continue with previous data

            # Add processing metadata
            processed_data["_processing_info"] = {
                "original_file": str(input_path),
                "processed_at": datetime.datetime.now().isoformat(),
                "transformations_applied": len(self.transformations),
                "backup_file": str(backup_path),
                "file_hash": self._calculate_file_hash(input_path)
            }

            # Save processed file
            output_path = self.output_dir / f"processed_{input_path.name}"
            writef_json(output_path, processed_data)

            # Log processing
            processing_time = (datetime.datetime.now() - start_time).total_seconds()
            log_entry = {
                "input_file": str(input_path),
                "output_file": str(output_path),
                "backup_file": str(backup_path),
                "processing_time": processing_time,
                "status": "success",
                "transformations_count": len(self.transformations)
            }
            self.processing_log.append(log_entry)

            print(f"✓ Processed: {input_path.name} -> {output_path.name} ({processing_time:.2f}s)")
            return processed_data

        except StructuredError as e:
            error_entry = {
                "input_file": str(input_path),
                "status": "failed",
                "error": str(e),
                "processing_time": (datetime.datetime.now() - start_time).total_seconds()
            }
            self.processing_log.append(error_entry)
            print(f"✗ Failed to process: {input_path.name} - {e}")
            return None

    def process_batch(self, pattern: str = "*.json") -> Dict[str, Any]:
        """Process all JSON files matching the pattern."""

        input_files = list(self.input_dir.glob(pattern))
        print(f"Found {len(input_files)} files to process")

        results = {
            "total_files": len(input_files),
            "successful": 0,
            "failed": 0,
            "processed_files": []
        }

        for input_file in input_files:
            processed_data = self.process_file(input_file)
            if processed_data:
                results["successful"] += 1
                results["processed_files"].append(str(input_file))
            else:
                results["failed"] += 1

        # Save processing log
        log_path = self.working_dir / f"processing_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        writef_json(log_path, {
            "batch_summary": results,
            "processing_log": self.processing_log
        })

        print(f"\nBatch processing completed:")
        print(f"  Successful: {results['successful']}")
        print(f"  Failed: {results['failed']}")
        print(f"  Log saved: {log_path}")

        return results

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def validate_output(self, schema_validator: Optional[Callable[[Dict[str, Any]], bool]] = None) -> Dict[str, Any]:
        """Validate all output files."""

        validation_results = {
            "total_files": 0,
            "valid_files": 0,
            "invalid_files": 0,
            "validation_errors": []
        }

        for output_file in self.output_dir.glob("processed_*.json"):
            validation_results["total_files"] += 1

            try:
                data = readf_json(output_file)

                # Basic validation
                is_valid = True
                if "_processing_info" not in data:
                    is_valid = False
                    validation_results["validation_errors"].append({
                        "file": str(output_file),
                        "error": "Missing processing info"
                    })

                # Custom validation
                if schema_validator and is_valid:
                    if not schema_validator(data):
                        is_valid = False
                        validation_results["validation_errors"].append({
                            "file": str(output_file),
                            "error": "Schema validation failed"
                        })

                if is_valid:
                    validation_results["valid_files"] += 1
                else:
                    validation_results["invalid_files"] += 1

            except StructuredError as e:
                validation_results["invalid_files"] += 1
                validation_results["validation_errors"].append({
                    "file": str(output_file),
                    "error": f"Read error: {e}"
                })

        # Save validation report
        report_path = self.working_dir / f"validation_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        writef_json(report_path, validation_results)

        return validation_results

# Example transformations
def add_timestamp_transformation(data: Dict[str, Any]) -> Dict[str, Any]:
    """Add timestamp to data."""
    data["timestamp"] = datetime.datetime.now().isoformat()
    return data

def normalize_keys_transformation(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize all keys to lowercase."""
    if isinstance(data, dict):
        return {k.lower(): normalize_keys_transformation(v) if isinstance(v, dict) else v
                for k, v in data.items()}
    return data

def add_version_transformation(data: Dict[str, Any]) -> Dict[str, Any]:
    """Add version information."""
    data["version"] = "1.0.0"
    data["format_version"] = "rde_2024"
    return data

# Usage example
def demonstrate_json_pipeline():
    """Demonstrate the JSON processing pipeline."""

    # Setup pipeline
    input_dir = Path("data/input_json")
    output_dir = Path("data/processed_json")
    working_dir = Path("data/working")

    pipeline = JSONProcessingPipeline(input_dir, output_dir, working_dir)

    # Add transformations
    pipeline.add_transformation(add_timestamp_transformation)
    pipeline.add_transformation(normalize_keys_transformation)
    pipeline.add_transformation(add_version_transformation)

    # Create sample input files
    input_dir.mkdir(parents=True, exist_ok=True)

    sample_data = [
        {
            "Name": "Dataset A",
            "Description": "Sample dataset for testing",
            "Type": "experimental",
            "Samples": 100
        },
        {
            "Title": "Research Data B",
            "Author": "Research Team",
            "Status": "completed",
            "Results": {"accuracy": 0.95, "precision": 0.92}
        }
    ]

    for i, data in enumerate(sample_data):
        sample_path = input_dir / f"sample_{i+1}.json"
        writef_json(sample_path, data)

    # Process batch
    results = pipeline.process_batch()

    # Validate output
    def custom_validator(data: Dict[str, Any]) -> bool:
        """Custom validation function."""
        required_fields = ["timestamp", "version", "_processing_info"]
        return all(field in data for field in required_fields)

    validation_results = pipeline.validate_output(custom_validator)

    print(f"\nValidation Results:")
    print(f"  Valid files: {validation_results['valid_files']}")
    print(f"  Invalid files: {validation_results['invalid_files']}")

    if validation_results["validation_errors"]:
        print("  Validation errors:")
        for error in validation_results["validation_errors"]:
            print(f"    {error['file']}: {error['error']}")

if __name__ == "__main__":
    demonstrate_json_pipeline()
```

## Error Handling

### Exception Types

The fileops module raises `StructuredError` for various error conditions:

```python
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.fileops import readf_json, writef_json

# Handle file reading errors
try:
    data = readf_json("nonexistent.json")
except StructuredError as e:
    print(f"Read error: {e}")

# Handle file writing errors
try:
    # This might fail due to permissions, disk space, etc.
    writef_json("/readonly/path/file.json", {"test": "data"})
except Exception as e:
    print(f"Write error: {e}")
```

### Common Error Scenarios

1. **File Not Found**:
   ```python
   def safe_json_read(path: str) -> dict | None:
       """Safely read JSON with file existence check."""
       if not Path(path).exists():
           print(f"File not found: {path}")
           return None

       try:
           return readf_json(path)
       except StructuredError as e:
           print(f"Error reading {path}: {e}")
           return None
   ```

2. **Invalid JSON Format**:
   ```python
   def validate_json_file(path: str) -> bool:
       """Validate JSON file format."""
       try:
           readf_json(path)
           return True
       except StructuredError as e:
           if "JSON" in str(e).upper():
               print(f"Invalid JSON format in {path}")
           return False
   ```

3. **Encoding Issues**:
   ```python
   def handle_encoding_issues(path: str) -> dict | None:
       """Handle files with encoding issues."""
       try:
           return readf_json(path)
       except StructuredError as e:
           if "encoding" in str(e).lower():
               print(f"Encoding issue in {path}: {e}")
               # Could implement fallback encoding detection
           return None
   ```

### Best Practices for Error Handling

1. **Graceful Degradation**:
   ```python
   def robust_config_loader(config_paths: list[str]) -> dict:
       """Load configuration with fallback options."""
       for path in config_paths:
           try:
               return readf_json(path)
           except StructuredError:
               continue

       # Return default configuration
       return {"default": True}
   ```

2. **Batch Processing with Error Recovery**:
   ```python
   def process_json_files_safely(file_paths: list[str]) -> dict:
       """Process multiple files with error recovery."""
       results = {"successful": [], "failed": []}

       for path in file_paths:
           try:
               data = readf_json(path)
               # Process data...
               results["successful"].append(path)
           except StructuredError as e:
               results["failed"].append({"path": path, "error": str(e)})

       return results
   ```

## Performance Notes

### Optimization Features

1. **Automatic Encoding Detection**: Efficient encoding detection reduces read errors
2. **Streaming JSON**: Uses standard library JSON for memory-efficient processing
3. **Error Caching**: Logging integration helps identify recurring issues
4. **Path Object Support**: Flexible input types reduce conversion overhead

### Performance Best Practices

```python
# Efficient batch processing
def process_large_json_files(file_paths: list[Path]) -> None:
    """Process large JSON files efficiently."""

    for file_path in file_paths:
        try:
            # Read once
            data = readf_json(file_path)

            # Process in memory
            processed = transform_data(data)

            # Write once
            output_path = file_path.parent / f"processed_{file_path.name}"
            writef_json(output_path, processed)

        except StructuredError as e:
            print(f"Skipping {file_path}: {e}")

# Memory-conscious processing for large files
def process_large_dataset(input_path: Path, output_path: Path) -> None:
    """Process large JSON datasets with memory management."""

    try:
        # For very large files, consider streaming JSON parsers
        data = readf_json(input_path)

        # Process in chunks if data is very large
        if isinstance(data, dict) and len(data) > 10000:
            # Process in smaller chunks
            chunk_size = 1000
            keys = list(data.keys())

            for i in range(0, len(keys), chunk_size):
                chunk_keys = keys[i:i + chunk_size]
                chunk_data = {k: data[k] for k in chunk_keys}
                # Process chunk...

        writef_json(output_path, data)

    except StructuredError as e:
        print(f"Processing failed: {e}")
```

## Integration Examples

### Integration with Other RDE Modules

```python
from rdetoolkit.fileops import readf_json, writef_json
from rdetoolkit.validation import invoice_validate
from rdetoolkit.rde2util import Meta
from pathlib import Path

def integrated_processing_example():
    """Example of integrating fileops with other RDE modules."""

    # Read invoice using fileops
    invoice_path = Path("data/invoice/invoice.json")
    invoice_data = readf_json(invoice_path)

    # Validate using validation module
    schema_path = Path("data/tasksupport/invoice.schema.json")
    try:
        invoice_validate(invoice_path, schema_path)
        print("Invoice validation passed")
    except Exception as e:
        print(f"Invoice validation failed: {e}")

    # Process metadata using rde2util
    metadef_path = Path("data/tasksupport/metadata-def.json")
    meta_output_path = Path("data/meta/metadata.json")

    if metadef_path.exists():
        meta = Meta(metadef_path)
        # Use fileops for reading additional data
        metadata_input = readf_json("data/input/metadata_input.json")
        meta.assign_vals(metadata_input)
        meta.writefile(str(meta_output_path))

    # Save processed results using fileops
    results = {
        "invoice_valid": True,
        "metadata_processed": True,
        "processing_timestamp": "2024-01-01T00:00:00Z"
    }

    writef_json("data/output/processing_results.json", results)
```

## See Also

- [Core Module](core.md) - For encoding detection and file handling utilities
- [Validation](validation.md) - For JSON schema validation functionality
- [RDE2 Utilities](rde2util.md) - For metadata processing utilities
- [Invoice File](invoicefile.md) - For invoice-specific file operations
- [Exceptions](exceptions.md) - For StructuredError and other exception types
- [RDE Logger](rdelogger.md) - For logging functionality used in fileops
- [Usage - Structured Process](../usage/structured_process/structured.md) - For file operations in workflows
- [Usage - Configuration](../usage/config/config.md) - For configuration file handling
