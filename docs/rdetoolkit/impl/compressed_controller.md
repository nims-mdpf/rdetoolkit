# Compressed Controller Module

The `rdetoolkit.impl.compressed_controller` module provides comprehensive functionality for handling compressed files and creating archives. This module includes parsers for different compressed file structures, archive creation utilities, and encoding-aware extraction capabilities specifically designed for RDE (Research Data Exchange) workflows.

## Overview

The compressed controller module offers specialized archive management capabilities:

- **Compressed File Parsing**: Extract and validate contents from ZIP files with different structural modes
- **Archive Creation**: Create ZIP and TAR.GZ archives with customizable exclusion patterns
- **Encoding Handling**: Robust filename encoding detection and correction during extraction
- **Structure Validation**: Ensure extracted files match expected structures and avoid naming conflicts

## Classes

### CompressedFlatFileParser

Parser for compressed flat files that validates extracted contents against an Excel invoice structure.

#### Constructor

```python
CompressedFlatFileParser(xlsx_invoice: pd.DataFrame)
```

**Parameters:**
- `xlsx_invoice` (pd.DataFrame): DataFrame representing the expected structure or content description of the compressed files

#### Attributes

- `xlsx_invoice` (pd.DataFrame): The Excel invoice DataFrame used for validation

#### Methods

##### read(zipfile, target_path)

Extract ZIP file contents and validate against the Excel invoice structure.

```python
def read(zipfile: Path, target_path: Path) -> list[tuple[Path, ...]]
```

**Parameters:**
- `zipfile` (Path): Path to the compressed flat file to be read
- `target_path` (Path): Destination directory where the zipfile will be extracted

**Returns:**
- `list[tuple[Path, ...]]`: List of tuples containing file paths that matched the xlsx_invoice structure

**Example:**
```python
import pandas as pd
from pathlib import Path
from rdetoolkit.impl.compressed_controller import CompressedFlatFileParser

# Create invoice DataFrame
invoice_df = pd.DataFrame({'data_file_names/name': ['file1.txt', 'file2.csv']})

# Parse compressed flat file
parser = CompressedFlatFileParser(invoice_df)
matched_files = parser.read(
    zipfile=Path("data.zip"),
    target_path=Path("extracted")
)
```

### CompressedFolderParser

Parser for compressed folders that extracts contents and validates unique directory structures.

#### Constructor

```python
CompressedFolderParser(xlsx_invoice: pd.DataFrame)
```

**Parameters:**
- `xlsx_invoice` (pd.DataFrame): DataFrame representing the expected structure or content description of the compressed folder contents

#### Attributes

- `xlsx_invoice` (pd.DataFrame): The Excel invoice DataFrame used for validation

#### Methods

##### read(zipfile, target_path)

Extract ZIP file contents and return validated file paths based on unique directory names.

```python
def read(zipfile: Path, target_path: Path) -> list[tuple[Path, ...]]
```

**Parameters:**
- `zipfile` (Path): Path to the compressed folder to be read
- `target_path` (Path): Destination directory where the zipfile will be extracted

**Returns:**
- `list[tuple[Path, ...]]`: List of tuples containing file paths validated based on unique directory names

**Example:**
```python
from pathlib import Path
from rdetoolkit.impl.compressed_controller import CompressedFolderParser

# Parse compressed folder
parser = CompressedFolderParser(invoice_df)
folder_files = parser.read(
    zipfile=Path("folder_archive.zip"),
    target_path=Path("extracted_folders")
)
```

##### validation_uniq_fspath(target_path, exclude_names)

Check for unique directory names and detect case-sensitive duplicates.

```python
def validation_uniq_fspath(target_path: str | Path, exclude_names: list[str]) -> dict[str, list[Path]]
```

**Parameters:**
- `target_path` (str | Path): The directory path to scan
- `exclude_names` (list[str]): List of filenames to exclude from validation

**Returns:**
- `dict[str, list[Path]]`: Dictionary mapping unique directory names to lists of files

**Raises:**
- `StructuredError`: When duplicate directory names are detected (case-insensitive)

**Example:**
```python
# Validate unique folder structure
unique_folders = parser.validation_uniq_fspath(
    target_path="extracted_data",
    exclude_names=["invoice_org.json", ".DS_Store"]
)
```

### ZipArtifactPackageCompressor

Archive compressor for creating ZIP files with customizable exclusion patterns and case-insensitive duplicate detection.

#### Constructor

```python
ZipArtifactPackageCompressor(source_dir: str | Path, exclude_patterns: list[str])
```

**Parameters:**
- `source_dir` (str | Path): Source directory to be archived
- `exclude_patterns` (list[str]): List of regex patterns for files/directories to exclude

#### Attributes

- `source_dir` (Path): The source directory path
- `exclude_patterns` (list[str]): List of exclusion patterns (property with getter/setter)

#### Methods

##### archive(output_zip)

Create a ZIP archive from the source directory.

```python
def archive(output_zip: str | Path) -> list[Path]
```

**Parameters:**
- `output_zip` (str | Path): Path to the output ZIP file

**Returns:**
- `list[Path]`: List of top-level directories included in the archive

**Raises:**
- `StructuredError`: When case-insensitive duplicate paths are detected

**Example:**
```python
from pathlib import Path
from rdetoolkit.impl.compressed_controller import ZipArtifactPackageCompressor

# Create ZIP archive
compressor = ZipArtifactPackageCompressor(
    source_dir="project_files",
    exclude_patterns=[r"\.git", r"__pycache__", r"\.pyc$"]
)
included_dirs = compressor.archive("project_archive.zip")
```

### TarGzArtifactPackageCompressor

Archive compressor for creating TAR.GZ files with customizable exclusion patterns.

#### Constructor

```python
TarGzArtifactPackageCompressor(source_dir: str | Path, exclude_patterns: list[str])
```

**Parameters:**
- `source_dir` (str | Path): Source directory to be archived
- `exclude_patterns` (list[str]): List of regex patterns for files/directories to exclude

#### Attributes

- `source_dir` (Path): The source directory path
- `exclude_patterns` (list[str]): List of exclusion patterns (property with getter/setter)

#### Methods

##### archive(output_tar)

Create a TAR.GZ archive from the source directory.

```python
def archive(output_tar: str | Path) -> list[Path]
```

**Parameters:**
- `output_tar` (str | Path): Path to the output TAR.GZ file

**Returns:**
- `list[Path]`: List of top-level directories included in the archive

**Raises:**
- `StructuredError`: When case-insensitive duplicate paths are detected

**Example:**
```python
from rdetoolkit.impl.compressed_controller import TarGzArtifactPackageCompressor

# Create TAR.GZ archive
compressor = TarGzArtifactPackageCompressor(
    source_dir="project_files",
    exclude_patterns=[r"\.git", r"node_modules", r"\.log$"]
)
included_dirs = compressor.archive("project_archive.tar.gz")
```

## Functions

### parse_compressedfile_mode

Factory function to determine the appropriate parser based on Excel invoice structure.

```python
def parse_compressedfile_mode(xlsx_invoice: pd.DataFrame) -> ICompressedFileStructParser
```

**Parameters:**
- `xlsx_invoice` (pd.DataFrame): The invoice data in Excel format

**Returns:**
- `ICompressedFileStructParser`: Instance of either CompressedFlatFileParser or CompressedFolderParser

**Example:**
```python
import pandas as pd
from rdetoolkit.impl.compressed_controller import parse_compressedfile_mode

# Auto-detect parser type
invoice_df = pd.DataFrame({'data_file_names/name': ['file1.txt']})
parser = parse_compressedfile_mode(invoice_df)  # Returns CompressedFlatFileParser

folder_invoice_df = pd.DataFrame({'folder_structure': ['data']})
folder_parser = parse_compressedfile_mode(folder_invoice_df)  # Returns CompressedFolderParser
```

### get_artifact_archiver

Factory function to get the appropriate archiver based on the specified format.

```python
def get_artifact_archiver(fmt: str, source_dir: str | Path, exclude_patterns: list[str]) -> IArtifactPackageCompressor
```

**Parameters:**
- `fmt` (str): The format of the archive ('zip', 'tar.gz', 'targz', 'tgz')
- `source_dir` (str | Path): The source directory to be archived
- `exclude_patterns` (list[str]): List of patterns to exclude

**Returns:**
- `IArtifactPackageCompressor`: Instance of the appropriate archiver class

**Raises:**
- `ValueError`: If the format is not supported

**Example:**
```python
from rdetoolkit.impl.compressed_controller import get_artifact_archiver

# Get ZIP archiver
zip_archiver = get_artifact_archiver(
    fmt="zip",
    source_dir="my_project",
    exclude_patterns=[r"\.git", r"__pycache__"]
)

# Get TAR.GZ archiver
tar_archiver = get_artifact_archiver(
    fmt="tar.gz",
    source_dir="my_project",
    exclude_patterns=[r"\.git", r"__pycache__"]
)
```

## Complete Usage Examples

### Basic Archive Creation

```python
from pathlib import Path
from rdetoolkit.impl.compressed_controller import get_artifact_archiver

def create_project_archive(project_dir: str, output_file: str, format_type: str = "zip"):
    """Create a project archive with standard exclusions."""

    # Standard exclusion patterns
    exclude_patterns = [
        r"\.git",           # Git repository
        r"__pycache__",     # Python cache
        r"\.pyc$",          # Python compiled files
        r"node_modules",    # Node.js modules
        r"\.env$",          # Environment files
        r"\.log$",          # Log files
        r"\.tmp$",          # Temporary files
        r"\.DS_Store$",     # macOS metadata
    ]

    try:
        # Get appropriate archiver
        archiver = get_artifact_archiver(
            fmt=format_type,
            source_dir=project_dir,
            exclude_patterns=exclude_patterns
        )

        # Create archive
        included_files = archiver.archive(output_file)

        print(f"✅ Archive created: {output_file}")
        print(f"📁 Files included: {len(included_files)}")

        return included_files

    except Exception as e:
        print(f"❌ Archive creation failed: {e}")
        raise

# Usage
included = create_project_archive(
    project_dir="my_python_project",
    output_file="backup.zip",
    format_type="zip"
)
```

### Advanced Archive with Custom Exclusions

```python
from pathlib import Path
from rdetoolkit.impl.compressed_controller import ZipArtifactPackageCompressor

class CustomArchiver:
    """Custom archiver with advanced exclusion logic."""

    def __init__(self, source_dir: str):
        self.source_dir = Path(source_dir)
        self.base_exclusions = [
            r"\.git",
            r"__pycache__",
            r"\.pyc$",
            r"\.pyo$",
        ]

    def create_source_archive(self, output_path: str) -> list[Path]:
        """Create archive with source code only."""

        source_exclusions = self.base_exclusions + [
            r"build",
            r"dist",
            r"\.egg-info",
            r"coverage",
            r"\.pytest_cache",
            r"\.mypy_cache",
        ]

        compressor = ZipArtifactPackageCompressor(
            source_dir=self.source_dir,
            exclude_patterns=source_exclusions
        )

        return compressor.archive(output_path)

    def create_deployment_archive(self, output_path: str) -> list[Path]:
        """Create archive for deployment (includes dependencies)."""

        deployment_exclusions = self.base_exclusions + [
            r"tests?",          # Test directories
            r"\.pytest_cache",
            r"\.coverage",
            r"docs?",           # Documentation
            r"examples?",       # Example files
            r"\.md$",           # Markdown files
        ]

        compressor = ZipArtifactPackageCompressor(
            source_dir=self.source_dir,
            exclude_patterns=deployment_exclusions
        )

        return compressor.archive(output_path)

    def create_full_backup(self, output_path: str) -> list[Path]:
        """Create complete backup archive."""

        minimal_exclusions = [
            r"\.git/objects",   # Exclude large git objects only
            r"__pycache__",
            r"\.pyc$",
        ]

        compressor = ZipArtifactPackageCompressor(
            source_dir=self.source_dir,
            exclude_patterns=minimal_exclusions
        )

        return compressor.archive(output_path)

# Usage
archiver = CustomArchiver("my_project")

# Create different types of archives
source_files = archiver.create_source_archive("source_code.zip")
deployment_files = archiver.create_deployment_archive("deployment.zip")
backup_files = archiver.create_full_backup("full_backup.zip")

print(f"Source archive: {len(source_files)} files")
print(f"Deployment archive: {len(deployment_files)} files")
print(f"Full backup: {len(backup_files)} files")
```

### Compressed File Extraction and Validation

```python
import pandas as pd
from pathlib import Path
from rdetoolkit.impl.compressed_controller import parse_compressedfile_mode

def extract_and_validate_archive(archive_path: str, invoice_file: str, extract_dir: str):
    """Extract archive and validate contents against invoice."""

    archive_path = Path(archive_path)
    extract_path = Path(extract_dir)

    # Ensure extraction directory exists
    extract_path.mkdir(parents=True, exist_ok=True)

    try:
        # Load invoice DataFrame
        invoice_df = pd.read_excel(invoice_file)

        # Get appropriate parser
        parser = parse_compressedfile_mode(invoice_df)

        # Extract and validate
        validated_files = parser.read(archive_path, extract_path)

        print(f"✅ Archive extracted successfully")
        print(f"📁 Extraction directory: {extract_path}")
        print(f"✔️  Validated file groups: {len(validated_files)}")

        # Display validated files
        for i, file_group in enumerate(validated_files):
            print(f"  Group {i+1}: {len(file_group)} files")
            for file_path in file_group:
                print(f"    - {file_path}")

        return validated_files

    except Exception as e:
        print(f"❌ Extraction/validation failed: {e}")
        raise

# Usage
validated = extract_and_validate_archive(
    archive_path="data_archive.zip",
    invoice_file="invoice.xlsx",
    extract_dir="extracted_data"
)
```

### Batch Archive Processing

```python
from pathlib import Path
from rdetoolkit.impl.compressed_controller import get_artifact_archiver

def batch_archive_directories(base_dir: str, output_dir: str, format_type: str = "zip"):
    """Create archives for multiple directories."""

    base_path = Path(base_dir)
    output_path = Path(output_dir)

    # Ensure output directory exists
    output_path.mkdir(parents=True, exist_ok=True)

    # Find all subdirectories
    subdirs = [d for d in base_path.iterdir() if d.is_dir()]

    if not subdirs:
        print(f"No subdirectories found in {base_path}")
        return

    print(f"Found {len(subdirs)} directories to archive")

    # Standard exclusions
    exclude_patterns = [
        r"\.git", r"__pycache__", r"\.pyc$",
        r"node_modules", r"\.DS_Store$"
    ]

    results = []

    for subdir in subdirs:
        archive_name = f"{subdir.name}_archive.{format_type}"
        archive_path = output_path / archive_name

        print(f"📦 Archiving: {subdir.name}")

        try:
            # Get archiver
            archiver = get_artifact_archiver(
                fmt=format_type,
                source_dir=subdir,
                exclude_patterns=exclude_patterns
            )

            # Create archive
            included_files = archiver.archive(archive_path)

            results.append({
                'directory': subdir.name,
                'archive': archive_path,
                'files_count': len(included_files),
                'success': True,
                'error': None
            })

            print(f"  ✅ Success: {len(included_files)} files")

        except Exception as e:
            results.append({
                'directory': subdir.name,
                'archive': None,
                'files_count': 0,
                'success': False,
                'error': str(e)
            })

            print(f"  ❌ Failed: {e}")

    # Summary
    successful = sum(1 for r in results if r['success'])
    total_files = sum(r['files_count'] for r in results)

    print(f"\n📊 Batch archiving complete:")
    print(f"  ✅ Successful: {successful}/{len(subdirs)}")
    print(f"  📁 Total files archived: {total_files}")

    return results

# Usage
results = batch_archive_directories(
    base_dir="projects",
    output_dir="archives",
    format_type="zip"
)
```

### Encoding-Aware Archive Extraction

```python
import pandas as pd
from pathlib import Path
from rdetoolkit.impl.compressed_controller import CompressedFlatFileParser

def extract_international_archive(archive_path: str, extract_dir: str):
    """Extract archive with international filenames."""

    # Create a simple invoice for validation
    invoice_df = pd.DataFrame({
        'data_file_names/name': ['*']  # Accept all files
    })

    parser = CompressedFlatFileParser(invoice_df)

    try:
        # The parser handles encoding detection automatically
        validated_files = parser.read(
            zipfile=Path(archive_path),
            target_path=Path(extract_dir)
        )

        print(f"✅ Archive with international filenames extracted")
        print(f"📁 Files extracted: {len(validated_files)}")

        # Display files with their detected encoding
        for file_group in validated_files:
            for file_path in file_group:
                print(f"  📄 {file_path}")

                # Check if filename contains non-ASCII characters
                try:
                    file_path.name.encode('ascii')
                    print(f"    ✓ ASCII filename")
                except UnicodeEncodeError:
                    print(f"    🌐 International filename detected")

        return validated_files

    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        raise

# Usage
international_files = extract_international_archive(
    archive_path="国際的なファイル.zip",  # Archive with Japanese filename
    extract_dir="extracted_international"
)
```

## Error Handling

### Common Exceptions

The compressed controller module may raise the following exceptions:

#### StructuredError
Raised when structural validation fails or duplicate paths are detected:

```python
from rdetoolkit.impl.compressed_controller import ZipArtifactPackageCompressor
from rdetoolkit.exceptions import StructuredError

try:
    compressor = ZipArtifactPackageCompressor(
        source_dir="project_with_duplicates",
        exclude_patterns=[]
    )
    compressor.archive("output.zip")
except StructuredError as e:
    print(f"Structural error: {e}")
    # Handle case-insensitive duplicate paths
```

#### ValueError
Raised when unsupported archive formats are specified:

```python
from rdetoolkit.impl.compressed_controller import get_artifact_archiver

try:
    archiver = get_artifact_archiver(
        fmt="unsupported_format",
        source_dir="project",
        exclude_patterns=[]
    )
except ValueError as e:
    print(f"Unsupported format: {e}")
    # Use supported formats: 'zip', 'tar.gz', 'targz', 'tgz'
```

#### UnicodeDecodeError
May be raised during filename encoding detection:

```python
from rdetoolkit.impl.compressed_controller import CompressedFlatFileParser

try:
    parser = CompressedFlatFileParser(invoice_df)
    parser.read(archive_path, extract_path)
except UnicodeDecodeError as e:
    print(f"Encoding error: {e}")
    # The parser attempts automatic encoding detection
```

### Best Practices

1. **Validate paths before archiving**:
   ```python
   def validate_source_directory(source_dir: Path) -> bool:
       """Validate source directory before archiving."""
       if not source_dir.exists():
           print(f"Source directory does not exist: {source_dir}")
           return False

       if not source_dir.is_dir():
           print(f"Source path is not a directory: {source_dir}")
           return False

       # Check for files to archive
       files = list(source_dir.rglob("*"))
       if not files:
           print(f"No files found in source directory: {source_dir}")
           return False

       return True
   ```

2. **Handle exclusion patterns carefully**:
   ```python
   def create_safe_exclusions(custom_patterns: list[str]) -> list[str]:
       """Create safe exclusion patterns with validation."""
       import re

       safe_patterns = []
       for pattern in custom_patterns:
           try:
               # Test if pattern is valid regex
               re.compile(pattern)
               safe_patterns.append(pattern)
           except re.error as e:
               print(f"Invalid regex pattern '{pattern}': {e}")

       return safe_patterns
   ```

3. **Monitor disk space and permissions**:
   ```python
   import shutil

   def check_archive_requirements(source_dir: Path, output_path: Path) -> bool:
       """Check system requirements for archiving."""

       # Estimate source size
       total_size = sum(
           f.stat().st_size for f in source_dir.rglob("*") if f.is_file()
       )

       # Check available disk space (with 20% buffer)
       free_space = shutil.disk_usage(output_path.parent).free
       required_space = int(total_size * 1.2)  # Compression may not reduce size much

       if free_space < required_space:
           print(f"Insufficient disk space. Required: {required_space}, Available: {free_space}")
           return False

       # Check write permissions
       try:
           test_file = output_path.parent / ".test_write"
           test_file.touch()
           test_file.unlink()
       except (OSError, PermissionError):
           print(f"No write permission for: {output_path.parent}")
           return False

       return True
   ```

4. **Implement progress tracking for large archives**:
   ```python
   import os
   from typing import Callable

   class ProgressTrackingArchiver:
       """Archiver with progress tracking capabilities."""

       def __init__(self, source_dir: Path, exclude_patterns: list[str]):
           self.source_dir = source_dir
           self.exclude_patterns = exclude_patterns
           self.progress_callback: Callable[[int, int], None] | None = None

       def set_progress_callback(self, callback: Callable[[int, int], None]):
           """Set callback for progress updates."""
           self.progress_callback = callback

       def archive_with_progress(self, output_path: Path) -> list[Path]:
           """Create archive with progress tracking."""

           # Count total files first
           total_files = 0
           for root, dirs, files in os.walk(self.source_dir):
               total_files += len([f for f in files if not self._is_excluded(os.path.join(root, f))])

           # Create archive with progress
           processed_files = 0

           compressor = ZipArtifactPackageCompressor(
               self.source_dir, self.exclude_patterns
           )

           # This would need to be integrated into the actual archiver
           # For demonstration purposes
           if self.progress_callback:
               self.progress_callback(processed_files, total_files)

           return compressor.archive(output_path)
   ```

## Performance Notes

- Archive creation performance scales with the number of files and their total size
- Exclusion pattern matching uses compiled regex for optimal performance
- Encoding detection during extraction may add overhead for files with international names
- Memory usage is minimized by streaming file operations
- TAR.GZ compression typically provides better compression ratios than ZIP but may be slower
- Case-insensitive duplicate detection requires additional processing but prevents extraction issues

## See Also

- [Interface Definitions](interfaces/filechecker.md) - For compressor and parser interfaces
- [Invoice File Module](invoicefile.md) - For file validation functionality
- [Exceptions Module](exceptions.md) - For custom exception types
- [RDE Logger](rdelogger.md) - For logging functionality
