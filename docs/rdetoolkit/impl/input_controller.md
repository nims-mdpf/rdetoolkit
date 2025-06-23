# Input Controller Module

The `rdetoolkit.impl.input_controller` module provides comprehensive input file processing capabilities for RDE (Research Data Exchange) workflows. This module includes specialized checker classes for different input file formats and modes, enabling automatic detection and processing of various data structures including Excel invoices, ZIP archives, multi-file inputs, and SmartTable formats.

## Overview

The input controller module offers specialized file processing capabilities for different RDE input modes:

- **Invoice Processing**: Handle general invoice files with flexible input types
- **Excel Invoice Processing**: Process structured Excel invoice files with ZIP archive validation
- **RDE Format Processing**: Handle structured RDE format ZIP archives with numbered directories
- **Multi-File Processing**: Process multiple individual files simultaneously
- **SmartTable Processing**: Handle SmartTable files with automatic CSV generation and file mapping

## Classes

### InvoiceChecker

A basic checker class for processing invoice files with minimal validation requirements.

#### Constructor

```python
InvoiceChecker(unpacked_dir_basename: Path)
```

**Parameters:**
- `unpacked_dir_basename` (Path): Temporary directory for unpacked content

#### Attributes

- `out_dir_temp` (Path): Temporary directory for the unpacked content
- `checker_type` (str): Returns "invoice" as the type identifier

#### Methods

##### parse(src_dir_input)

Parse the source input directory and group files by type.

```python
def parse(src_dir_input: Path) -> tuple[RawFiles, Path | None]
```

**Parameters:**
- `src_dir_input` (Path): Source directory containing the input files

**Returns:**
- `tuple[RawFiles, Path | None]`: Tuple containing list of raw file tuples and None

**Example:**
```python
from pathlib import Path
from rdetoolkit.impl.input_controller import InvoiceChecker

# Create checker instance
checker = InvoiceChecker(Path("temp"))

# Parse input directory
raw_files, invoice_file = checker.parse(Path("input_data"))
print(f"Found {len(raw_files)} file groups")
```

### ExcelInvoiceChecker

A sophisticated checker class for processing Excel invoice files with ZIP archive validation and structured data extraction.

#### Constructor

```python
ExcelInvoiceChecker(unpacked_dir_basename: Path)
```

**Parameters:**
- `unpacked_dir_basename` (Path): Temporary directory for unpacked content

#### Attributes

- `out_dir_temp` (Path): Temporary directory for unpacked content
- `checker_type` (str): Returns "excel_invoice" as the type identifier

#### Methods

##### parse(src_dir_input)

Parse and validate Excel invoice files with optional ZIP archives.

```python
def parse(src_dir_input: Path) -> tuple[RawFiles, Path | None]
```

**Parameters:**
- `src_dir_input` (Path): Source directory containing the input files

**Returns:**
- `tuple[RawFiles, Path | None]`: Tuple containing list of raw file tuples and Excel invoice file path

**Raises:**
- `StructuredError`: If validation fails or file structure is inconsistent

**Example:**
```python
from pathlib import Path
from rdetoolkit.impl.input_controller import ExcelInvoiceChecker

# Create checker with temporary directory
checker = ExcelInvoiceChecker(Path("temp_extract"))

# Process Excel invoice with ZIP
try:
    raw_files, excel_file = checker.parse(Path("excel_invoice_data"))
    print(f"Excel invoice: {excel_file}")
    print(f"Raw file groups: {len(raw_files)}")
except StructuredError as e:
    print(f"Validation error: {e}")
```

##### get_index(paths, sort_items)

Get the index of a file path based on sorted items from Excel invoice.

```python
def get_index(paths: Path, sort_items: Sequence) -> int
```

**Parameters:**
- `paths` (Path): Directory path of the raw files
- `sort_items` (Sequence): List of files sorted in Excel invoice order

**Returns:**
- `int`: The index number or length of sort_items if not found

### RDEFormatChecker

A checker class for processing structured RDE format ZIP archives with numbered directory organization.

#### Constructor

```python
RDEFormatChecker(unpacked_dir_basename: Path)
```

**Parameters:**
- `unpacked_dir_basename` (Path): Temporary directory for unpacked content

#### Attributes

- `out_dir_temp` (Path): Temporary directory for unpacked content
- `checker_type` (str): Returns "rde_format" as the type identifier

#### Methods

##### parse(src_dir_input)

Parse RDE format ZIP files and extract structured data.

```python
def parse(src_dir_input: Path) -> tuple[RawFiles, Path | None]
```

**Parameters:**
- `src_dir_input` (Path): Source directory containing the input files

**Returns:**
- `tuple[RawFiles, Path | None]`: Tuple containing list of raw file tuples grouped by directory numbers and None

**Raises:**
- `StructuredError`: If no ZIP file or multiple ZIP files are found

**Example:**
```python
from pathlib import Path
from rdetoolkit.impl.input_controller import RDEFormatChecker

# Create RDE format checker
checker = RDEFormatChecker(Path("rde_temp"))

# Process RDE format ZIP
try:
    raw_files, _ = checker.parse(Path("rde_archive"))
    print(f"RDE groups: {len(raw_files)}")
    for i, group in enumerate(raw_files):
        print(f"  Group {i}: {len(group)} files")
except StructuredError as e:
    print(f"RDE format error: {e}")
```

### MultiFileChecker

A checker class for processing multiple individual files without specific structural requirements.

#### Constructor

```python
MultiFileChecker(unpacked_dir_basename: Path)
```

**Parameters:**
- `unpacked_dir_basename` (Path): Temporary directory used for certain operations

#### Attributes

- `out_dir_temp` (Path): Temporary directory for operations
- `checker_type` (str): Returns "multifile" as the type identifier

#### Methods

##### parse(src_dir_input)

Parse multiple individual files from the input directory.

```python
def parse(src_dir_input: Path) -> tuple[RawFiles, Path | None]
```

**Parameters:**
- `src_dir_input` (Path): Source directory containing the input files

**Returns:**
- `tuple[RawFiles, Path | None]`: Tuple containing list of single-file tuples sorted by filename and None

**Example:**
```python
from pathlib import Path
from rdetoolkit.impl.input_controller import MultiFileChecker

# Create multi-file checker
checker = MultiFileChecker(Path("multi_temp"))

# Process multiple files
raw_files, _ = checker.parse(Path("multiple_files"))
print(f"Individual files: {len(raw_files)}")
for file_tuple in raw_files:
    print(f"  File: {file_tuple[0].name}")
```

### SmartTableChecker

A sophisticated checker class for processing SmartTable files with automatic CSV generation and file mapping capabilities.

#### Constructor

```python
SmartTableChecker(unpacked_dir_basename: Path)
```

**Parameters:**
- `unpacked_dir_basename` (Path): Temporary directory for unpacked content

#### Attributes

- `out_dir_temp` (Path): Temporary directory for unpacked content
- `checker_type` (str): Returns "smarttable" as the type identifier

#### Methods

##### parse(src_dir_input)

Parse SmartTable files and generate individual CSV files with file mappings.

```python
def parse(src_dir_input: Path) -> tuple[RawFiles, Path | None]
```

**Parameters:**
- `src_dir_input` (Path): Source directory containing the input files

**Returns:**
- `tuple[RawFiles, Path | None]`: Tuple containing list of CSV-file mapping tuples and SmartTable file path

**Raises:**
- `StructuredError`: If no SmartTable files found or multiple SmartTable files present

**Example:**
```python
from pathlib import Path
from rdetoolkit.impl.input_controller import SmartTableChecker

# Create SmartTable checker
checker = SmartTableChecker(Path("smarttable_temp"))

# Process SmartTable with related files
try:
    raw_files, smarttable_file = checker.parse(Path("smarttable_data"))
    print(f"SmartTable file: {smarttable_file}")

    for csv_file_tuple in raw_files:
        csv_file = csv_file_tuple[0]
        related_files = csv_file_tuple[1:]
        print(f"CSV: {csv_file.name} -> {len(related_files)} related files")

except StructuredError as e:
    print(f"SmartTable error: {e}")
```

## Complete Usage Examples

### Basic Input Processing Workflow

```python
from pathlib import Path
from rdetoolkit.impl.input_controller import (
    InvoiceChecker, ExcelInvoiceChecker, RDEFormatChecker,
    MultiFileChecker, SmartTableChecker
)

def detect_and_process_input(input_dir: str, temp_dir: str):
    """Automatically detect input type and process accordingly."""

    input_path = Path(input_dir)
    temp_path = Path(temp_dir)
    temp_path.mkdir(parents=True, exist_ok=True)

    # Get list of input files
    input_files = list(input_path.glob("*"))

    # Detect input type based on file patterns
    has_excel_invoice = any(
        f.suffix.lower() in [".xls", ".xlsx"] and f.stem.endswith("_excel_invoice")
        for f in input_files
    )

    has_smarttable = any(
        f.name.startswith("smarttable_") and f.suffix.lower() in [".xlsx", ".csv", ".tsv"]
        for f in input_files
    )

    has_zip = any(f.suffix.lower() == ".zip" for f in input_files)

    # Select appropriate checker
    if has_smarttable:
        checker = SmartTableChecker(temp_path)
        print("🔍 Detected: SmartTable format")
    elif has_excel_invoice:
        checker = ExcelInvoiceChecker(temp_path)
        print("🔍 Detected: Excel Invoice format")
    elif has_zip and len([f for f in input_files if f.suffix.lower() == ".zip"]) == 1:
        checker = RDEFormatChecker(temp_path)
        print("🔍 Detected: RDE Format")
    elif len(input_files) > 1:
        checker = MultiFileChecker(temp_path)
        print("🔍 Detected: Multi-file format")
    else:
        checker = InvoiceChecker(temp_path)
        print("🔍 Detected: General invoice format")

    # Process input
    try:
        raw_files, metadata_file = checker.parse(input_path)

        print(f"✅ Processing complete:")
        print(f"  Checker type: {checker.checker_type}")
        print(f"  File groups: {len(raw_files)}")
        print(f"  Metadata file: {metadata_file.name if metadata_file else 'None'}")

        return raw_files, metadata_file, checker.checker_type

    except Exception as e:
        print(f"❌ Processing failed: {e}")
        raise

# Usage
raw_files, metadata, input_type = detect_and_process_input(
    input_dir="input_data",
    temp_dir="temp_processing"
)
```

### Excel Invoice Processing with Validation

```python
from pathlib import Path
from rdetoolkit.impl.input_controller import ExcelInvoiceChecker
from rdetoolkit.exceptions import StructuredError

def process_excel_invoice_with_validation(input_dir: str, temp_dir: str):
    """Process Excel invoice with comprehensive validation."""

    input_path = Path(input_dir)
    temp_path = Path(temp_dir)

    # Pre-validation
    input_files = list(input_path.glob("*"))

    # Check for Excel invoice files
    excel_files = [
        f for f in input_files
        if f.suffix.lower() in [".xls", ".xlsx"] and f.stem.endswith("_excel_invoice")
    ]

    if not excel_files:
        raise ValueError("No Excel invoice files found")

    if len(excel_files) > 1:
        raise ValueError(f"Multiple Excel invoice files found: {[f.name for f in excel_files]}")

    # Check ZIP files
    zip_files = [f for f in input_files if f.suffix.lower() == ".zip"]

    if len(zip_files) > 1:
        raise ValueError(f"Multiple ZIP files found: {[f.name for f in zip_files]}")

    print(f"📄 Excel invoice: {excel_files[0].name}")
    if zip_files:
        print(f"📦 ZIP archive: {zip_files[0].name}")

    # Create checker and process
    checker = ExcelInvoiceChecker(temp_path)

    try:
        raw_files, excel_file = checker.parse(input_path)

        print(f"✅ Excel invoice processing complete:")
        print(f"  Raw file groups: {len(raw_files)}")
        print(f"  Files per group:")

        for i, group in enumerate(raw_files):
            print(f"    Group {i+1}: {len(group)} files")
            for file_path in group:
                print(f"      - {file_path.name}")

        return raw_files, excel_file

    except StructuredError as e:
        print(f"❌ Excel invoice validation failed: {e}")
        raise

# Usage
try:
    raw_files, excel_file = process_excel_invoice_with_validation(
        input_dir="excel_invoice_input",
        temp_dir="excel_temp"
    )
except Exception as e:
    print(f"Processing error: {e}")
```

### SmartTable Processing with File Mapping

```python
from pathlib import Path
from rdetoolkit.impl.input_controller import SmartTableChecker

def process_smarttable_with_mapping(input_dir: str, temp_dir: str):
    """Process SmartTable files with detailed file mapping."""

    input_path = Path(input_dir)
    temp_path = Path(temp_dir)
    temp_path.mkdir(parents=True, exist_ok=True)

    # Validate SmartTable files
    smarttable_files = [
        f for f in input_path.glob("*")
        if f.name.startswith("smarttable_") and f.suffix.lower() in [".xlsx", ".csv", ".tsv"]
    ]

    if not smarttable_files:
        raise ValueError("No SmartTable files found (must start with 'smarttable_')")

    if len(smarttable_files) > 1:
        raise ValueError(f"Multiple SmartTable files: {[f.name for f in smarttable_files]}")

    print(f"📊 SmartTable file: {smarttable_files[0].name}")

    # Check for ZIP files
    zip_files = [f for f in input_path.glob("*.zip")]
    if zip_files:
        print(f"📦 ZIP files: {[f.name for f in zip_files]}")

    # Process with SmartTable checker
    checker = SmartTableChecker(temp_path)

    try:
        raw_files, smarttable_file = checker.parse(input_path)

        print(f"✅ SmartTable processing complete:")
        print(f"  Generated CSV files: {len(raw_files)}")
        print(f"  File mappings:")

        for i, file_tuple in enumerate(raw_files):
            csv_file = file_tuple[0]
            related_files = file_tuple[1:]

            print(f"    Row {i+1} -> {csv_file.name}")
            if related_files:
                print(f"      Related files: {len(related_files)}")
                for related_file in related_files:
                    print(f"        - {related_file.name}")
            else:
                print(f"      No related files")

        return raw_files, smarttable_file

    except Exception as e:
        print(f"❌ SmartTable processing failed: {e}")
        raise

# Usage
raw_files, smarttable = process_smarttable_with_mapping(
    input_dir="smarttable_input",
    temp_dir="smarttable_temp"
)
```

### Multi-Format Processing Pipeline

```python
from pathlib import Path
from typing import Dict, Any
from rdetoolkit.impl.input_controller import (
    InvoiceChecker, ExcelInvoiceChecker, RDEFormatChecker,
    MultiFileChecker, SmartTableChecker
)

class InputProcessingPipeline:
    """Comprehensive input processing pipeline for multiple formats."""

    def __init__(self, base_temp_dir: str):
        self.base_temp_dir = Path(base_temp_dir)
        self.base_temp_dir.mkdir(parents=True, exist_ok=True)

    def process_directory(self, input_dir: str) -> Dict[str, Any]:
        """Process a directory with automatic format detection."""

        input_path = Path(input_dir)
        temp_dir = self.base_temp_dir / f"temp_{input_path.name}"
        temp_dir.mkdir(exist_ok=True)

        result = {
            'input_dir': str(input_path),
            'input_type': None,
            'raw_files': None,
            'metadata_file': None,
            'success': False,
            'error': None,
            'stats': {}
        }

        try:
            # Detect format
            checker = self._detect_format(input_path, temp_dir)
            result['input_type'] = checker.checker_type

            # Process files
            raw_files, metadata_file = checker.parse(input_path)

            result['raw_files'] = raw_files
            result['metadata_file'] = metadata_file
            result['success'] = True

            # Calculate statistics
            result['stats'] = self._calculate_stats(raw_files)

            print(f"✅ {input_path.name}: {checker.checker_type} format, {len(raw_files)} groups")

        except Exception as e:
            result['error'] = str(e)
            print(f"❌ {input_path.name}: {e}")

        return result

    def _detect_format(self, input_path: Path, temp_dir: Path):
        """Detect input format and return appropriate checker."""

        input_files = list(input_path.glob("*"))

        # SmartTable detection
        if any(f.name.startswith("smarttable_") and f.suffix.lower() in [".xlsx", ".csv", ".tsv"] for f in input_files):
            return SmartTableChecker(temp_dir)

        # Excel Invoice detection
        if any(f.suffix.lower() in [".xls", ".xlsx"] and f.stem.endswith("_excel_invoice") for f in input_files):
            return ExcelInvoiceChecker(temp_dir)

        # RDE Format detection (single ZIP)
        zip_files = [f for f in input_files if f.suffix.lower() == ".zip"]
        if len(zip_files) == 1 and len(input_files) == 1:
            return RDEFormatChecker(temp_dir)

        # Multi-file detection
        if len(input_files) > 1:
            return MultiFileChecker(temp_dir)

        # Default to Invoice checker
        return InvoiceChecker(temp_dir)

    def _calculate_stats(self, raw_files) -> Dict[str, Any]:
        """Calculate statistics for processed files."""

        total_files = sum(len(group) for group in raw_files)
        group_sizes = [len(group) for group in raw_files]

        return {
            'total_groups': len(raw_files),
            'total_files': total_files,
            'avg_files_per_group': total_files / len(raw_files) if raw_files else 0,
            'min_group_size': min(group_sizes) if group_sizes else 0,
            'max_group_size': max(group_sizes) if group_sizes else 0
        }

    def process_multiple_directories(self, directories: list[str]) -> Dict[str, Any]:
        """Process multiple directories and return summary."""

        results = []

        for directory in directories:
            result = self.process_directory(directory)
            results.append(result)

        # Generate summary
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]

        format_counts = {}
        for result in successful:
            format_type = result['input_type']
            format_counts[format_type] = format_counts.get(format_type, 0) + 1

        summary = {
            'total_directories': len(directories),
            'successful': len(successful),
            'failed': len(failed),
            'format_distribution': format_counts,
            'results': results
        }

        print(f"\n📊 Processing Summary:")
        print(f"  Total directories: {summary['total_directories']}")
        print(f"  Successful: {summary['successful']}")
        print(f"  Failed: {summary['failed']}")
        print(f"  Format distribution: {summary['format_distribution']}")

        return summary

# Usage
pipeline = InputProcessingPipeline("temp_processing")

# Process single directory
result = pipeline.process_directory("sample_input")

# Process multiple directories
directories = ["excel_data", "smarttable_data", "rde_data", "multi_files"]
summary = pipeline.process_multiple_directories(directories)
```

### Advanced RDE Format Processing

```python
from pathlib import Path
from collections import defaultdict
from rdetoolkit.impl.input_controller import RDEFormatChecker

def analyze_rde_structure(input_dir: str, temp_dir: str):
    """Analyze RDE format structure in detail."""

    input_path = Path(input_dir)
    temp_path = Path(temp_dir)
    temp_path.mkdir(parents=True, exist_ok=True)

    # Validate RDE format
    zip_files = list(input_path.glob("*.zip"))

    if len(zip_files) != 1:
        raise ValueError(f"RDE format requires exactly one ZIP file, found {len(zip_files)}")

    zip_file = zip_files[0]
    print(f"📦 RDE ZIP file: {zip_file.name}")

    # Process with RDE checker
    checker = RDEFormatChecker(temp_path)

    try:
        raw_files, _ = checker.parse(input_path)

        print(f"✅ RDE format analysis:")
        print(f"  Directory groups: {len(raw_files)}")

        # Analyze structure
        structure_info = defaultdict(list)
        total_files = 0

        for i, group in enumerate(raw_files):
            group_info = {
                'group_index': i,
                'file_count': len(group),
                'file_types': defaultdict(int),
                'directories': set(),
                'files': []
            }

            for file_path in group:
                total_files += 1
                group_info['files'].append(file_path)
                group_info['file_types'][file_path.suffix.lower()] += 1
                group_info['directories'].add(str(file_path.parent))

            structure_info[i] = group_info

            print(f"  Group {i}:")
            print(f"    Files: {group_info['file_count']}")
            print(f"    Types: {dict(group_info['file_types'])}")
            print(f"    Directories: {len(group_info['directories'])}")

        print(f"  Total files: {total_files}")

        return raw_files, structure_info

    except Exception as e:
        print(f"❌ RDE analysis failed: {e}")
        raise

# Usage
raw_files, structure = analyze_rde_structure(
    input_dir="rde_archive_input",
    temp_dir="rde_analysis_temp"
)
```

## Performance Notes

- File pattern detection uses efficient glob operations for fast directory scanning
- ZIP extraction performance depends on archive size and compression ratio
- SmartTable CSV generation is optimized for memory efficiency with row-by-row processing
- Temporary directory operations use system temp space for optimal I/O performance
- File grouping operations use efficient sorting algorithms based on path structures
- Memory usage scales linearly with the number of files and their metadata

## See Also

- [Compressed Controller](compressed_controller.md) - For ZIP archive processing
- [Invoice File Module](invoicefile.md) - For Excel invoice and SmartTable operations
- [Interface Definitions](interfaces/filechecker.md) - For checker interface specifications
- [Exceptions Module](exceptions.md) - For custom exception types
- [RDE Types Models](models/rde2types.md) - For type definitions used in input processing
