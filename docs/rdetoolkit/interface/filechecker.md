# File Checker Interfaces Module

The `rdetoolkit.interfaces.filechecker` module defines abstract base classes (interfaces) for file checking, input processing, compressed file parsing, and artifact compression operations. These interfaces provide standardized contracts for implementing various file processing components in RDE (Research Data Exchange) workflows, ensuring consistent behavior across different implementation classes.

## Overview

The file checker interfaces module provides foundational abstractions for:

- **Input File Processing**: Define standard operations for handling and processing input files
- **File Type Checking**: Establish contracts for different input file checkers and validators
- **Compressed File Operations**: Specify interfaces for parsing and extracting compressed file structures
- **Archive Creation**: Define standard operations for creating compressed artifact packages

## Interfaces

### IInputFileHelper

Abstract interface for input file helper operations, specifically designed for handling ZIP file operations among input files.

#### Abstract Methods (IInputFileChecker)

##### get_zipfiles(input_files)

Retrieve ZIP files from a list of input file paths.

```python
@abstractmethod
def get_zipfiles(input_files: list[Path]) -> ZipFilesPathList
```

**Parameters:**

- `input_files` (list[Path]): List of file paths to search for ZIP files

**Returns:**

- `ZipFilesPathList`: List of paths pointing to found ZIP files

**Raises:**

- `NotImplementedError`: Must be implemented by concrete classes

**Example Implementation:**

```python
from pathlib import Path
from rdetoolkit.interfaces.filechecker import IInputFileHelper

class BasicInputFileHelper(IInputFileHelper):
    def get_zipfiles(self, input_files: list[Path]) -> list[Path]:
        """Find all ZIP files in the input list."""
        return [f for f in input_files if f.suffix.lower() == ".zip"]

    def unpacked(self, zipfile: Path, target_dir: Path) -> list[Path]:
        """Extract ZIP file and return extracted files."""
        # Implementation details...
        pass
```

##### unpacked(zipfile, target_dir)

Unpack a ZIP file into a target directory and return paths to extracted files.

```python
@abstractmethod
def unpacked(zipfile: Path, target_dir: Path) -> UnZipFilesPathList
```

**Parameters:**

- `zipfile` (Path): Path to the ZIP file to be unpacked
- `target_dir` (Path): Directory where ZIP file contents will be extracted

**Returns:**

- `UnZipFilesPathList`: List of paths to the unpacked files

**Raises:**

- `NotImplementedError`: Must be implemented by concrete classes

### IInputFileChecker

Abstract interface for checking and parsing input files in RDE workflows. This interface defines the structure for classes that handle validation and extraction of information from source input files.

#### Abstract Properties

##### checker_type

Return the type identifier for the checker implementation.

```python
@property
@abstractmethod
def checker_type() -> str
```

**Returns:**

- `str`: String identifier representing the checker type

**Example Implementation:**

```python
class ExcelInvoiceChecker(IInputFileChecker):
    @property
    def checker_type(self) -> str:
        return "excel_invoice"
```

#### Abstract Methods

##### parse(src_input_path)

Parse the source input path and extract relevant file information.

```python
@abstractmethod
def parse(src_input_path: Path) -> tuple[RawFiles, Path | None]
```

**Parameters:**

- `src_input_path` (Path): Path to the source input file(s)

**Returns:**

- `tuple[RawFiles, Path | None]`: Tuple containing extracted raw file data and optional path to additional relevant data

**Raises:**

- `NotImplementedError`: Must be implemented by concrete classes

**Example Implementation:**

```python
from pathlib import Path
from rdetoolkit.interfaces.filechecker import IInputFileChecker

class CustomInputChecker(IInputFileChecker):
    @property
    def checker_type(self) -> str:
        return "custom"

    def parse(self, src_input_path: Path) -> tuple[list, Path | None]:
        """Parse input files and return raw files and metadata."""
        # Find all files in the input directory
        input_files = list(src_input_path.glob("*"))

        # Group files and extract metadata
        raw_files = [(f,) for f in input_files if f.suffix != ".meta"]
        metadata_file = next((f for f in input_files if f.suffix == ".meta"), None)

        return raw_files, metadata_file
```

### ICompressedFileStructParser

Abstract interface for parsing the structure of compressed files, focusing on understanding internal organization and extracting structural information.

#### Abstract Methods

##### read(zipfile, target_path)

Read and parse the structure of a compressed file.

```python
@abstractmethod
def read(zipfile: Path, target_path: Path) -> list[tuple[Path, ...]]
```

**Parameters:**

- `zipfile` (Path): Path to the compressed file to be read
- `target_path` (Path): Path where contents might be extracted or analyzed

**Returns:**

- `list[tuple[Path, ...]]`: List of tuples containing paths or relevant data extracted from the compressed file

**Raises:**

- `NotImplementedError`: Must be implemented by concrete classes

**Example Implementation:**

```python
from pathlib import Path
from rdetoolkit.interfaces.filechecker import ICompressedFileStructParser

class StandardStructParser(ICompressedFileStructParser):
    def read(self, zipfile: Path, target_path: Path) -> list[tuple[Path, ...]]:
        """Extract and analyze compressed file structure."""
        import zipfile

        # Extract files
        with zipfile.ZipFile(zipfile, 'r') as zip_ref:
            zip_ref.extractall(target_path)

        # Group files by directory structure
        extracted_files = list(target_path.rglob("*"))
        file_groups = []

        # Group files by their parent directory
        from collections import defaultdict
        dir_groups = defaultdict(list)

        for file_path in extracted_files:
            if file_path.is_file():
                dir_groups[file_path.parent].append(file_path)

        return [tuple(files) for files in dir_groups.values()]
```

### IArtifactPackageCompressor

Abstract interface for compressing artifacts into archive packages, providing standardized operations for creating compressed archives with exclusion patterns.

#### Abstract Properties

##### exclude_patterns

Get the list of exclusion patterns used during compression.

```python
@property
@abstractmethod
def exclude_patterns() -> list[str]
```

**Returns:**

- `list[str]`: List of exclusion patterns (typically regex patterns)

#### Abstract Methods

##### archive(output_zip)

Create an archive from source files with applied exclusion patterns.

```python
@abstractmethod
def archive(output_zip: str | Path) -> list[Path]
```

**Parameters:**

- `output_zip` (str | Path): Path to the output archive file

**Returns:**

- `list[Path]`: List of paths to files that were included in the archive

**Raises:**

- `NotImplementedError`: Must be implemented by concrete classes

**Example Implementation:**

```python
from pathlib import Path
import zipfile
import re
from rdetoolkit.interfaces.filechecker import IArtifactPackageCompressor

class BasicArchiveCompressor(IArtifactPackageCompressor):
    def __init__(self, source_dir: Path, patterns: list[str]):
        self.source_dir = source_dir
        self._exclude_patterns = patterns

    @property
    def exclude_patterns(self) -> list[str]:
        return self._exclude_patterns

    def archive(self, output_zip: str | Path) -> list[Path]:
        """Create ZIP archive with exclusion patterns."""
        output_path = Path(output_zip)
        included_files = []

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in self.source_dir.rglob("*"):
                if file_path.is_file() and not self._is_excluded(file_path):
                    rel_path = file_path.relative_to(self.source_dir)
                    zipf.write(file_path, rel_path)
                    included_files.append(rel_path)

        return included_files

    def _is_excluded(self, file_path: Path) -> bool:
        """Check if file matches exclusion patterns."""
        file_str = str(file_path)
        return any(re.search(pattern, file_str) for pattern in self._exclude_patterns)
```

## Complete Usage Examples

### Implementing a Custom Input File Checker

```python
from pathlib import Path
from typing import Optional
from rdetoolkit.interfaces.filechecker import IInputFileChecker
from rdetoolkit.models.rde2types import RawFiles

class DatasetInputChecker(IInputFileChecker):
    """Custom checker for dataset input files."""

    def __init__(self, temp_dir: Path):
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    @property
    def checker_type(self) -> str:
        return "dataset"

    def parse(self, src_input_path: Path) -> tuple[RawFiles, Optional[Path]]:
        """Parse dataset directory structure."""

        # Find data files and metadata
        data_files = []
        metadata_file = None

        for file_path in src_input_path.rglob("*"):
            if file_path.is_file():
                if file_path.name == "metadata.json":
                    metadata_file = file_path
                elif file_path.suffix.lower() in [".csv", ".tsv", ".xlsx"]:
                    data_files.append(file_path)

        # Group files by dataset (assuming directory structure)
        dataset_groups = {}
        for data_file in data_files:
            # Use parent directory as dataset identifier
            dataset_name = data_file.parent.name
            if dataset_name not in dataset_groups:
                dataset_groups[dataset_name] = []
            dataset_groups[dataset_name].append(data_file)

        # Convert to RawFiles format
        raw_files = [tuple(files) for files in dataset_groups.values()]

        return raw_files, metadata_file

# Usage
def process_dataset_input(input_dir: str, temp_dir: str):
    """Process dataset input using custom checker."""

    checker = DatasetInputChecker(Path(temp_dir))

    try:
        raw_files, metadata = checker.parse(Path(input_dir))

        print(f"Checker type: {checker.checker_type}")
        print(f"Dataset groups: {len(raw_files)}")
        print(f"Metadata file: {metadata.name if metadata else 'None'}")

        for i, group in enumerate(raw_files):
            print(f"  Group {i+1}: {len(group)} files")
            for file_path in group:
                print(f"    - {file_path.name}")

        return raw_files, metadata

    except Exception as e:
        print(f"Processing failed: {e}")
        raise

# Usage
raw_files, metadata = process_dataset_input("dataset_input", "temp")
```

### Implementing a Compressed File Structure Parser

```python
from pathlib import Path
import zipfile
import json
from rdetoolkit.interfaces.filechecker import ICompressedFileStructParser

class MetadataStructParser(ICompressedFileStructParser):
    """Parser that groups files based on metadata structure."""

    def __init__(self, metadata_config: dict):
        self.metadata_config = metadata_config

    def read(self, zipfile_path: Path, target_path: Path) -> list[tuple[Path, ...]]:
        """Extract and group files based on metadata structure."""

        # Extract ZIP file
        with zipfile.ZipFile(zipfile_path, 'r') as zip_ref:
            zip_ref.extractall(target_path)

        # Find metadata files
        metadata_files = list(target_path.glob("**/metadata.json"))

        if not metadata_files:
            # Fallback: group by directory
            return self._group_by_directory(target_path)

        # Group files based on metadata
        file_groups = []

        for metadata_file in metadata_files:
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)

                # Find related files based on metadata
                related_files = self._find_related_files(
                    metadata_file.parent, metadata
                )

                if related_files:
                    file_groups.append(tuple(related_files))

            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error reading metadata {metadata_file}: {e}")
                continue

        return file_groups

    def _group_by_directory(self, target_path: Path) -> list[tuple[Path, ...]]:
        """Fallback grouping by directory structure."""
        from collections import defaultdict

        dir_groups = defaultdict(list)

        for file_path in target_path.rglob("*"):
            if file_path.is_file():
                dir_groups[file_path.parent].append(file_path)

        return [tuple(files) for files in dir_groups.values()]

    def _find_related_files(self, base_dir: Path, metadata: dict) -> list[Path]:
        """Find files related to metadata entry."""
        related_files = []

        # Look for files mentioned in metadata
        if "files" in metadata:
            for file_info in metadata["files"]:
                if isinstance(file_info, dict) and "path" in file_info:
                    file_path = base_dir / file_info["path"]
                    if file_path.exists():
                        related_files.append(file_path)
                elif isinstance(file_info, str):
                    file_path = base_dir / file_info
                    if file_path.exists():
                        related_files.append(file_path)

        # Add metadata file itself
        metadata_file = base_dir / "metadata.json"
        if metadata_file.exists():
            related_files.append(metadata_file)

        return related_files

# Usage
def parse_structured_archive(archive_path: str, extract_dir: str):
    """Parse archive with metadata-based structure."""

    # Configuration for metadata parsing
    config = {
        "group_by_metadata": True,
        "required_fields": ["files", "dataset_id"]
    }

    parser = MetadataStructParser(config)

    try:
        file_groups = parser.read(Path(archive_path), Path(extract_dir))

        print(f"Extracted {len(file_groups)} file groups:")

        for i, group in enumerate(file_groups):
            print(f"  Group {i+1}: {len(group)} files")

            # Check for metadata in group
            metadata_files = [f for f in group if f.name == "metadata.json"]
            if metadata_files:
                print(f"    Metadata: {metadata_files[0]}")

            # List other files
            other_files = [f for f in group if f.name != "metadata.json"]
            for file_path in other_files:
                print(f"    Data: {file_path.name}")

        return file_groups

    except Exception as e:
        print(f"Parsing failed: {e}")
        raise

# Usage
groups = parse_structured_archive("structured_data.zip", "extracted")
```

### Implementing a Custom Archive Compressor

```python
from pathlib import Path
import zipfile
import tarfile
import re
from typing import Union
from rdetoolkit.interfaces.filechecker import IArtifactPackageCompressor

class FlexibleArchiveCompressor(IArtifactPackageCompressor):
    """Flexible compressor supporting multiple archive formats."""

    def __init__(self, source_dir: Path, exclude_patterns: list[str],
                 format_type: str = "zip"):
        self.source_dir = source_dir
        self._exclude_patterns = exclude_patterns
        self.format_type = format_type.lower()

        # Compile regex patterns for efficiency
        self._compiled_patterns = [re.compile(pattern) for pattern in exclude_patterns]

    @property
    def exclude_patterns(self) -> list[str]:
        return self._exclude_patterns

    @exclude_patterns.setter
    def exclude_patterns(self, patterns: list[str]):
        self._exclude_patterns = patterns
        self._compiled_patterns = [re.compile(pattern) for pattern in patterns]

    def archive(self, output_path: Union[str, Path]) -> list[Path]:
        """Create archive in specified format."""

        output_path = Path(output_path)

        # Collect files to archive
        files_to_archive = self._collect_files()

        if self.format_type == "zip":
            return self._create_zip_archive(output_path, files_to_archive)
        elif self.format_type in ["tar.gz", "tgz"]:
            return self._create_tar_archive(output_path, files_to_archive)
        else:
            raise ValueError(f"Unsupported format: {self.format_type}")

    def _collect_files(self) -> list[tuple[Path, Path]]:
        """Collect files that should be included in archive."""
        files_to_archive = []

        for file_path in self.source_dir.rglob("*"):
            if file_path.is_file() and not self._is_excluded(file_path):
                relative_path = file_path.relative_to(self.source_dir)
                files_to_archive.append((file_path, relative_path))

        return files_to_archive

    def _create_zip_archive(self, output_path: Path,
                           files: list[tuple[Path, Path]]) -> list[Path]:
        """Create ZIP archive."""
        included_files = []

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for full_path, relative_path in files:
                zipf.write(full_path, relative_path)
                included_files.append(relative_path)

        return included_files

    def _create_tar_archive(self, output_path: Path,
                           files: list[tuple[Path, Path]]) -> list[Path]:
        """Create TAR.GZ archive."""
        included_files = []

        with tarfile.open(output_path, 'w:gz') as tar:
            for full_path, relative_path in files:
                tar.add(full_path, arcname=relative_path)
                included_files.append(relative_path)

        return included_files

    def _is_excluded(self, file_path: Path) -> bool:
        """Check if file should be excluded."""
        file_str = str(file_path)
        return any(pattern.search(file_str) for pattern in self._compiled_patterns)

    def add_exclusion_pattern(self, pattern: str):
        """Add a new exclusion pattern."""
        self._exclude_patterns.append(pattern)
        self._compiled_patterns.append(re.compile(pattern))

    def get_archive_stats(self) -> dict:
        """Get statistics about files that would be archived."""
        files_to_archive = self._collect_files()

        total_size = sum(f[0].stat().st_size for f in files_to_archive)
        file_types = {}

        for full_path, _ in files_to_archive:
            ext = full_path.suffix.lower() or "no_extension"
            file_types[ext] = file_types.get(ext, 0) + 1

        return {
            "total_files": len(files_to_archive),
            "total_size_bytes": total_size,
            "file_types": file_types,
            "exclude_patterns": self._exclude_patterns
        }

# Usage
def create_flexible_archive(source_dir: str, output_file: str,
                          archive_type: str = "zip"):
    """Create archive with flexible format support."""

    # Define exclusion patterns
    exclude_patterns = [
        r"\.git/",
        r"__pycache__/",
        r"\.pyc$",
        r"\.DS_Store$",
        r"\.log$",
        r"node_modules/",
        r"\.env$"
    ]

    # Create compressor
    compressor = FlexibleArchiveCompressor(
        source_dir=Path(source_dir),
        exclude_patterns=exclude_patterns,
        format_type=archive_type
    )

    # Get statistics before archiving
    stats = compressor.get_archive_stats()
    print(f"Archive Statistics:")
    print(f"  Files to archive: {stats['total_files']}")
    print(f"  Total size: {stats['total_size_bytes'] / 1024 / 1024:.2f} MB")
    print(f"  File types: {stats['file_types']}")

    # Create archive
    try:
        included_files = compressor.archive(output_file)

        print(f"✅ Archive created successfully:")
        print(f"  Output: {output_file}")
        print(f"  Format: {archive_type}")
        print(f"  Files included: {len(included_files)}")

        return included_files

    except Exception as e:
        print(f"❌ Archive creation failed: {e}")
        raise

# Usage examples
zip_files = create_flexible_archive("my_project", "backup.zip", "zip")
tar_files = create_flexible_archive("my_project", "backup.tar.gz", "tar.gz")
```

### Interface-Based Plugin System

```python
from pathlib import Path
from typing import Type, Dict
from rdetoolkit.interfaces.filechecker import IInputFileChecker

class CheckerRegistry:
    """Registry for managing different input file checkers."""

    def __init__(self):
        self._checkers: Dict[str, Type[IInputFileChecker]] = {}

    def register_checker(self, checker_class: Type[IInputFileChecker]):
        """Register a new checker class."""
        # Create temporary instance to get type
        temp_instance = checker_class(Path("temp"))
        checker_type = temp_instance.checker_type

        self._checkers[checker_type] = checker_class
        print(f"Registered checker: {checker_type}")

    def get_checker(self, checker_type: str, temp_dir: Path) -> IInputFileChecker:
        """Get checker instance by type."""
        if checker_type not in self._checkers:
            raise ValueError(f"Unknown checker type: {checker_type}")

        return self._checkers[checker_type](temp_dir)

    def list_checkers(self) -> list[str]:
        """List all registered checker types."""
        return list(self._checkers.keys())

    def auto_detect_checker(self, input_dir: Path, temp_dir: Path) -> IInputFileChecker:
        """Auto-detect appropriate checker based on input files."""

        input_files = list(input_dir.glob("*"))

        # Simple heuristics for auto-detection
        if any(f.name.startswith("smarttable_") for f in input_files):
            return self.get_checker("smarttable", temp_dir)
        elif any(f.stem.endswith("_excel_invoice") for f in input_files):
            return self.get_checker("excel_invoice", temp_dir)
        elif len([f for f in input_files if f.suffix == ".zip"]) == 1:
            return self.get_checker("rde_format", temp_dir)
        elif len(input_files) > 1:
            return self.get_checker("multifile", temp_dir)
        else:
            return self.get_checker("invoice", temp_dir)

# Example usage
def setup_checker_system():
    """Set up a plugin-based checker system."""

    registry = CheckerRegistry()

    # Register built-in checkers (would normally import from actual modules)
    # registry.register_checker(ExcelInvoiceChecker)
    # registry.register_checker(SmartTableChecker)
    # registry.register_checker(RDEFormatChecker)

    # Register custom checkers
    registry.register_checker(DatasetInputChecker)

    return registry

def process_with_auto_detection(input_dir: str, temp_dir: str):
    """Process input with automatic checker detection."""

    registry = setup_checker_system()

    input_path = Path(input_dir)
    temp_path = Path(temp_dir)
    temp_path.mkdir(parents=True, exist_ok=True)

    # Auto-detect appropriate checker
    checker = registry.auto_detect_checker(input_path, temp_path)

    print(f"Auto-detected checker: {checker.checker_type}")

    # Process input
    raw_files, metadata = checker.parse(input_path)

    print(f"Processing results:")
    print(f"  File groups: {len(raw_files)}")
    print(f"  Metadata: {metadata.name if metadata else 'None'}")

    return raw_files, metadata

# Usage
raw_files, metadata = process_with_auto_detection("input_data", "temp")
```

## Interface Implementation Guidelines

### Best Practices for Interface Implementation

1. **Consistent Error Handling**:

   ```python
   class MyChecker(IInputFileChecker):
       def parse(self, src_input_path: Path) -> tuple[RawFiles, Path | None]:
           try:
               # Implementation logic
               pass
           except FileNotFoundError as e:
               raise ValueError(f"Input path not found: {src_input_path}") from e
           except Exception as e:
               raise RuntimeError(f"Parsing failed: {e}") from e
   ```

2. **Type Safety**:

   ```python
   from typing import TYPE_CHECKING
   if TYPE_CHECKING:
       from rdetoolkit.models.rde2types import RawFiles

   class TypeSafeChecker(IInputFileChecker):
       def parse(self, src_input_path: Path) -> tuple['RawFiles', Path | None]:
           # Implementation with proper type hints
           pass
   ```

3. **Resource Management**:

   ```python
   class ResourceManagedChecker(IInputFileChecker):
       def __init__(self, temp_dir: Path):
           self.temp_dir = temp_dir
           self._cleanup_files: list[Path] = []

       def parse(self, src_input_path: Path) -> tuple[RawFiles, Path | None]:
           try:
               # Processing logic
               pass
           finally:
               self._cleanup_temp_files()

       def _cleanup_temp_files(self):
           for file_path in self._cleanup_files:
               if file_path.exists():
                   file_path.unlink()
   ```

4. **Documentation and Validation**:

   ```python
   class WellDocumentedChecker(IInputFileChecker):
       """A well-documented checker implementation.

       This checker handles XYZ format files and provides
       ABC functionality for DEF workflows.
       """

       @property
       def checker_type(self) -> str:
           return "well_documented"

       def parse(self, src_input_path: Path) -> tuple[RawFiles, Path | None]:
           """Parse input files with validation.

           Args:
               src_input_path: Directory containing input files

           Returns:
               Tuple of (raw_files, metadata_file)

           Raises:
               ValueError: If input validation fails
               FileNotFoundError: If required files are missing
           """
           self._validate_input(src_input_path)
           # Implementation logic...

       def _validate_input(self, input_path: Path):
           """Validate input directory and files."""
           if not input_path.exists():
               raise FileNotFoundError(f"Input directory not found: {input_path}")

           if not input_path.is_dir():
               raise ValueError(f"Input path must be a directory: {input_path}")
   ```

## See Also

- [Input Controller Implementation](impl/input_controller.md) - For concrete implementations of these interfaces
- [Compressed Controller Implementation](impl/compressed_controller.md) - For compressed file parser and compressor implementations
- [RDE Types Models](models/rde2types.md) - For type definitions used in interface contracts
- [Exceptions Module](exceptions.md) - For custom exception types used in implementations
