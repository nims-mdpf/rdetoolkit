# Compressed Controller API

## Purpose

This module defines compressed file processing in RDEToolKit. It provides functionality for compressed file extraction, validation, information retrieval, and temporary file management.

## Key Features

### Compressed File Processing
- Support for various compression formats including ZIP, TAR, GZ
- Compressed file extraction and validation
- Proper handling of Japanese file names

### File Management
- Temporary directory management
- Organization of extracted files
- Cleanup processing

---

::: src.rdetoolkit.impl.compressed_controller.CompressedFlatFileParser

---

::: src.rdetoolkit.impl.compressed_controller.CompressedFolderParser

---

::: src.rdetoolkit.impl.compressed_controller.parse_compressedfile_mode

---

## Practical Usage

### Basic Compressed File Processing

```python title="basic_compressed_processing.py"
from rdetoolkit.impl.compressed_controller import CompressedFlatFileParser, CompressedFolderParser
from pathlib import Path

# Use flat file parser
flat_parser = CompressedFlatFileParser()

# Read compressed file
archive_path = Path("data/input/experiment_data.zip")
if archive_path.exists():
    try:
        # Read file
        parsed_data = flat_parser.read(archive_path)
        print(f"✓ Compressed file analysis completed: {parsed_data}")

        # Extract files
        unpacked_files = flat_parser._unpacked(archive_path)
        print(f"Number of extracted files: {len(unpacked_files)}")

        for file_path in unpacked_files:
            print(f"  - {file_path}")

    except Exception as e:
        print(f"✗ Compressed file processing error: {e}")
```

### Folder Structure Compressed File Processing

```python title="folder_compressed_processing.py"
from rdetoolkit.impl.compressed_controller import CompressedFolderParser
from pathlib import Path

# Use folder parser
folder_parser = CompressedFolderParser()

# Process compressed folder
archive_path = Path("data/input/experiment_folder.zip")
if archive_path.exists():
    try:
        # Read folder structure
        folder_data = folder_parser.read(archive_path)
        print(f"✓ Folder structure analysis completed: {folder_data}")

        # Validate unique paths
        validation_result = folder_parser.validation_uniq_fspath(folder_data)
        if validation_result:
            print("✓ File path uniqueness validation successful")
        else:
            print("✗ File path uniqueness validation failed")

        # Extract files
        unpacked_files = folder_parser._unpacked(archive_path)
        print(f"Number of extracted files: {len(unpacked_files)}")

    except Exception as e:
        print(f"✗ Folder compressed file processing error: {e}")
```

### Compressed File Mode Analysis

```python title="compressed_mode_analysis.py"
from rdetoolkit.impl.compressed_controller import parse_compressedfile_mode
from pathlib import Path

# Mode analysis for multiple compressed files
archive_files = [
    Path("data/input/flat_data.zip"),
    Path("data/input/folder_structure.zip"),
    Path("data/input/mixed_content.tar.gz")
]

for archive_path in archive_files:
    if archive_path.exists():
        try:
            # Analyze compressed file mode
            mode_result = parse_compressedfile_mode(archive_path)
            print(f"File: {archive_path.name}")
            print(f"Mode: {mode_result}")
            print(f"---")

        except Exception as e:
            print(f"✗ Mode analysis error {archive_path.name}: {e}")
```
