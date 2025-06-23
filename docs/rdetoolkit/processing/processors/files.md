# File Processors

The file processors handle file operations including copying raw files to designated directories with support for different processing modes.

## Classes

### FileCopier

Standard file copier for raw files. Handles copying files based on configuration settings to appropriate output directories.

```python
class FileCopier(Processor):
    """Standard file copier for raw files."""
```

#### Methods

##### process

Execute file copying operations based on configuration.

```python
def process(self, context: ProcessingContext) -> None
```

**Parameters:**
- `context` (ProcessingContext): Processing context containing configuration and file paths

**Configuration Dependencies:**
- `config.save_raw`: If True, copies files to raw directory
- `config.save_nonshared_raw`: If True, copies files to nonshared_raw directory

**Example:**
```python
from rdetoolkit.processing.processors import FileCopier

file_copier = FileCopier()
file_copier.process(context)
```

**Behavior:**
- Copies files to `raw` directory if `save_raw` is enabled
- Copies files to `nonshared_raw` directory if `save_nonshared_raw` is enabled
- Creates target directories if they don't exist
- Handles file copying errors gracefully with logging

### RDEFormatFileCopier

Specialized file copier for RDEFormat mode. Copies files by matching directory structure patterns.

```python
class RDEFormatFileCopier(Processor):
    """Specialized copier for RDEFormat mode."""
```

#### Methods

##### process

Execute RDEFormat-specific file copying operations.

```python
def process(self, context: ProcessingContext) -> None
```

**Parameters:**
- `context` (ProcessingContext): Processing context containing configuration and file paths

**Configuration Dependencies:**
- `config.save_raw`: Controls whether files are copied to raw directory

**Example:**
```python
from rdetoolkit.processing.processors import RDEFormatFileCopier

rde_copier = RDEFormatFileCopier()
rde_copier.process(context)
```

**Behavior:**
- Copies files by directory structure matching
- Preserves original directory organization
- Only operates when `save_raw` is enabled
- Designed for RDEFormat mode processing

### SmartTableFileCopier

Specialized file copier for SmartTable mode. Copies files while excluding SmartTable-generated CSV files.

```python
class SmartTableFileCopier(Processor):
    """Specialized copier for SmartTable mode."""
```

#### Methods

##### process

Execute SmartTable-specific file copying operations.

```python
def process(self, context: ProcessingContext) -> None
```

**Parameters:**
- `context` (ProcessingContext): Processing context containing configuration and file paths

**Configuration Dependencies:**
- `config.save_raw`: If True, copies filtered files to raw directory
- `config.save_nonshared_raw`: If True, copies filtered files to nonshared_raw directory

**Example:**
```python
from rdetoolkit.processing.processors import SmartTableFileCopier

smarttable_copier = SmartTableFileCopier()
smarttable_copier.process(context)
```

**Behavior:**
- Filters out SmartTable-generated CSV files before copying
- Identifies SmartTable CSVs by naming pattern (contains `_smarttable_`)
- Copies remaining files to appropriate directories based on configuration
- Maintains file organization while excluding auto-generated content

## Usage Examples

### Basic File Copying

```python
from rdetoolkit.processing.processors import FileCopier
from rdetoolkit.processing.context import ProcessingContext

# Standard file copying
file_copier = FileCopier()
file_copier.process(context)

# Check what was copied
if context.srcpaths.config.save_raw:
    print(f"Files copied to: {context.resource_paths.raw}")
if context.srcpaths.config.save_nonshared_raw:
    print(f"Files copied to: {context.resource_paths.nonshared_raw}")
```

### Mode-Specific File Copying

```python
from rdetoolkit.processing.processors import (
    FileCopier, RDEFormatFileCopier, SmartTableFileCopier
)

def copy_files_by_mode(context: ProcessingContext):
    """Copy files using appropriate copier for the mode."""

    if context.mode_name.lower() == "rdeformat":
        copier = RDEFormatFileCopier()
    elif context.mode_name.lower() == "smarttableinvoice":
        copier = SmartTableFileCopier()
    else:
        copier = FileCopier()

    print(f"Using {copier.get_name()} for {context.mode_name} mode")
    copier.process(context)

# Usage
copy_files_by_mode(context)
```

### Custom File Filtering

```python
from rdetoolkit.processing.processors import FileCopier
from pathlib import Path

class FilteredFileCopier(FileCopier):
    """File copier with custom filtering logic."""

    def __init__(self, allowed_extensions=None):
        self.allowed_extensions = allowed_extensions or ['.txt', '.pdf', '.jpg', '.png']

    def process(self, context: ProcessingContext) -> None:
        # Filter files before copying
        original_files = context.resource_paths.rawfiles
        filtered_files = [
            f for f in original_files
            if f.suffix.lower() in self.allowed_extensions
        ]

        # Temporarily replace rawfiles for copying
        context.resource_paths = context.resource_paths._replace(
            rawfiles=tuple(filtered_files)
        )

        # Perform copying
        super().process(context)

        # Restore original file list
        context.resource_paths = context.resource_paths._replace(
            rawfiles=original_files
        )

        print(f"Copied {len(filtered_files)} of {len(original_files)} files")

# Usage
filtered_copier = FilteredFileCopier(['.pdf', '.txt'])
filtered_copier.process(context)
```

### Parallel File Copying

```python
from rdetoolkit.processing.processors import FileCopier
import concurrent.futures
import shutil

class ParallelFileCopier(FileCopier):
    """File copier with parallel processing support."""

    def __init__(self, max_workers=4):
        self.max_workers = max_workers

    def _copy_files(self, source_files, target_dir):
        """Copy files in parallel."""
        target_dir.mkdir(parents=True, exist_ok=True)

        def copy_single_file(source_file):
            target_file = target_dir / source_file.name
            shutil.copy2(source_file, target_file)
            return source_file, target_file

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(copy_single_file, f) for f in source_files]

            results = []
            for future in concurrent.futures.as_completed(futures):
                try:
                    source, target = future.result()
                    results.append((source, target))
                except Exception as e:
                    print(f"Error copying file: {e}")

            return results

# Usage
parallel_copier = ParallelFileCopier(max_workers=8)
parallel_copier.process(context)
```

### File Copy Verification

```python
from rdetoolkit.processing.processors import FileCopier
import hashlib

class VerifiedFileCopier(FileCopier):
    """File copier with integrity verification."""

    def _copy_files(self, source_files, target_dir):
        """Copy files with verification."""
        target_dir.mkdir(parents=True, exist_ok=True)

        verified_copies = []
        failed_copies = []

        for source_file in source_files:
            target_file = target_dir / source_file.name

            try:
                # Copy file
                shutil.copy2(source_file, target_file)

                # Verify integrity
                if self._verify_file_integrity(source_file, target_file):
                    verified_copies.append((source_file, target_file))
                else:
                    failed_copies.append(source_file)
                    target_file.unlink()  # Remove corrupted copy

            except Exception as e:
                print(f"Error copying {source_file}: {e}")
                failed_copies.append(source_file)

        if failed_copies:
            print(f"Warning: {len(failed_copies)} files failed verification")

        return verified_copies

    def _verify_file_integrity(self, source_file, target_file):
        """Verify file integrity using SHA-256."""
        def get_file_hash(file_path):
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()

        return get_file_hash(source_file) == get_file_hash(target_file)

# Usage
verified_copier = VerifiedFileCopier()
verified_copier.process(context)
```

## Error Handling

### File Operation Errors

```python
from rdetoolkit.processing.processors import FileCopier
import shutil

class RobustFileCopier(FileCopier):
    """File copier with comprehensive error handling."""

    def _copy_files(self, source_files, target_dir):
        """Copy files with detailed error handling."""
        target_dir.mkdir(parents=True, exist_ok=True)

        successful_copies = []
        failed_copies = []

        for source_file in source_files:
            target_file = target_dir / source_file.name

            try:
                # Check source file exists and is readable
                if not source_file.exists():
                    raise FileNotFoundError(f"Source file not found: {source_file}")

                if not source_file.is_file():
                    raise ValueError(f"Source is not a file: {source_file}")

                # Check target directory is writable
                if not target_dir.exists():
                    target_dir.mkdir(parents=True, exist_ok=True)

                # Perform copy with error handling
                shutil.copy2(source_file, target_file)
                successful_copies.append((source_file, target_file))

            except PermissionError as e:
                print(f"Permission denied copying {source_file}: {e}")
                failed_copies.append(source_file)
            except FileNotFoundError as e:
                print(f"File not found: {e}")
                failed_copies.append(source_file)
            except OSError as e:
                print(f"OS error copying {source_file}: {e}")
                failed_copies.append(source_file)
            except Exception as e:
                print(f"Unexpected error copying {source_file}: {e}")
                failed_copies.append(source_file)

        print(f"File copy results: {len(successful_copies)} successful, {len(failed_copies)} failed")
        return successful_copies

# Usage
robust_copier = RobustFileCopier()
robust_copier.process(context)
```

### Configuration Validation

```python
from rdetoolkit.processing.processors import FileCopier

class ValidatedFileCopier(FileCopier):
    """File copier with configuration validation."""

    def process(self, context: ProcessingContext) -> None:
        # Validate configuration
        config = context.srcpaths.config

        if not config.save_raw and not config.save_nonshared_raw:
            print("Warning: No file copying enabled (save_raw and save_nonshared_raw both False)")
            return

        # Validate source files exist
        missing_files = [f for f in context.resource_paths.rawfiles if not f.exists()]
        if missing_files:
            print(f"Warning: {len(missing_files)} source files not found")
            for f in missing_files:
                print(f"  Missing: {f}")

        # Validate output directories are accessible
        if config.save_raw:
            self._validate_output_directory(context.resource_paths.raw)
        if config.save_nonshared_raw:
            self._validate_output_directory(context.resource_paths.nonshared_raw)

        # Perform copying
        super().process(context)

    def _validate_output_directory(self, directory: Path):
        """Validate output directory is accessible."""
        try:
            directory.mkdir(parents=True, exist_ok=True)
            # Test write access
            test_file = directory / ".write_test"
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            raise PermissionError(f"Cannot write to directory {directory}: {e}")

# Usage
validated_copier = ValidatedFileCopier()
validated_copier.process(context)
```

## Performance Considerations

- **Large Files**: Use streaming operations for large file copying
- **Many Files**: Consider parallel processing for multiple files
- **Network Storage**: Handle network timeout and retry logic
- **Disk Space**: Check available space before copying
- **Memory Usage**: Avoid loading entire files into memory

## See Also

- [Processing Context](../context.md) - Context management and configuration
- [Pipeline Architecture](../pipeline.md) - Core pipeline classes
- [Invoice Processors](invoice.md) - Invoice initialization processors
- [Validation Processors](validation.md) - File validation processors
