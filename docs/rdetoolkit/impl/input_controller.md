# Input Controller API

## Purpose

This module defines file operation processing corresponding to various input modes in RDEToolKit. It provides functionality for input mode determination, file validation, and processing control.

## Key Features

### Input Mode Management
- Automatic determination of mode from input file patterns
- Support for Invoice, ExcelInvoice, RDEFormat, and MultiFile modes
- Input file validation and preprocessing

### File Operation Control
- Acquisition and classification of input files
- File format validation
- Control of processing workflow

---

::: src.rdetoolkit.impl.input_controller.InvoiceChecker

---

::: src.rdetoolkit.impl.input_controller.ExcelInvoiceChecker

---

::: src.rdetoolkit.impl.input_controller.RDEFormatChecker

---

::: src.rdetoolkit.impl.input_controller.MultiFileChecker

---

## Practical Usage

### Invoice Mode Processing

```python title="invoice_mode_processing.py"
from rdetoolkit.impl.input_controller import InvoiceChecker
from rdetoolkit.models.rde2types import RdeInputDirPaths
from pathlib import Path

# Configure input paths
input_paths = RdeInputDirPaths(
    inputdata=Path("data/input"),
    invoice=Path("data/invoice"),
    tasksupport=Path("data/tasksupport")
)

# Create an Invoice checker
invoice_checker = InvoiceChecker(input_paths)

try:
    # Parse the Invoice file
    parsed_data = invoice_checker.parse()
    print(f"✓ Invoice parsing successful: {parsed_data}")

    # Get file groups
    file_groups = invoice_checker._get_group_by_files()
    print(f"Number of file groups: {len(file_groups)}")

    for i, group in enumerate(file_groups):
        print(f"Group {i+1}: {group}")

except Exception as e:
    print(f"✗ Invoice processing error: {e}")
```

### ExcelInvoice Mode Processing

```python title="excel_invoice_mode_processing.py"
from rdetoolkit.impl.input_controller import ExcelInvoiceChecker
from rdetoolkit.models.rde2types import RdeInputDirPaths
from pathlib import Path

# Configure input paths
input_paths = RdeInputDirPaths(
    inputdata=Path("data/input"),
    invoice=Path("data/invoice"),
    tasksupport=Path("data/tasksupport")
)

# Create an ExcelInvoice checker
excel_checker = ExcelInvoiceChecker(input_paths)

try:
    # Read the Excel invoice
    excel_data = excel_checker.read()
    print("✓ Excel invoice read successfully")

    # Get index
    index = excel_checker.get_index()
    print(f"Index: {index}")

    # Get raw data files
    rawfiles = excel_checker._get_rawfiles()
    print(f"Number of raw data files: {len(rawfiles)}")

    # Validate files
    validation_result = excel_checker._validate_files()
    if validation_result:
        print("✓ File validation successful")
    else:
        print("✗ File validation failed")

        # Detect invalid files
        invalid_zips = excel_checker._detect_invalid_zipfiles()
        invalid_excels = excel_checker._detect_invalid_excel_invoice_files()
        invalid_others = excel_checker._detect_invalid_other_files()

        if invalid_zips:
            print(f"Invalid ZIP files: {invalid_zips}")
        if invalid_excels:
            print(f"Invalid Excel files: {invalid_excels}")
        if invalid_others:
            print(f"Other invalid files: {invalid_others}")

except Exception as e:
    print(f"✗ ExcelInvoice processing error: {e}")
```

### RDEFormat Mode Processing

```python title="rde_format_mode_processing.py"
from rdetoolkit.impl.input_controller import RDEFormatChecker
from rdetoolkit.models.rde2types import RdeInputDirPaths
from pathlib import Path

# Configure input paths
input_paths = RdeInputDirPaths(
    inputdata=Path("data/input"),
    invoice=Path("data/invoice"),
    tasksupport=Path("data/tasksupport")
)

# Create an RDEFormat checker
rde_checker = RDEFormatChecker(input_paths)

try:
    # Parse the RDE format
    parsed_data = rde_checker.parse()
    print(f"✓ RDE format parsing successful: {parsed_data}")

    # Get ZIP files
    zipfiles = rde_checker._get_zipfiles()
    print(f"Number of ZIP files: {len(zipfiles)}")

    # Unpack files
    unpacked_files = rde_checker._unpacked()
    print(f"Number of unpacked files: {len(unpacked_files)}")

    # Get raw data files
    rawfiles = rde_checker._get_rawfiles()
    print(f"Number of raw data files: {len(rawfiles)}")

    for rawfile in rawfiles:
        print(f"  - {rawfile}")

except Exception as e:
    print(f"✗ RDEFormat processing error: {e}")
```

### MultiFile Mode Processing

```python title="multifile_mode_processing.py"
from rdetoolkit.impl.input_controller import MultiFileChecker
from rdetoolkit.models.rde2types import RdeInputDirPaths
from pathlib import Path

# Configure input paths
input_paths = RdeInputDirPaths(
    inputdata=Path("data/input"),
    invoice=Path("data/invoice"),
    tasksupport=Path("data/tasksupport")
)

# Create a MultiFile checker
multifile_checker = MultiFileChecker(input_paths)

try:
    # Parse the MultiFile input
    parsed_data = multifile_checker.parse()
    print(f"✓ MultiFile parsing successful: {parsed_data}")

    # Get file groups
    file_groups = multifile_checker._get_group_by_files()
    print(f"Number of file groups: {len(file_groups)}")

    for i, group in enumerate(file_groups):
        print(f"Group {i+1}: {len(group)} files")
        for file_path in group:
            print(f"  - {file_path}")

    # Unpack files (if there are compressed files)
    unpacked_files = multifile_checker._unpacked()
    if unpacked_files:
        print(f"Number of unpacked files: {len(unpacked_files)}")
        for unpacked_file in unpacked_files:
            print(f"  - {unpacked_file}")

except Exception as e:
    print(f"✗ MultiFile processing error: {e}")
```

### Integrated Input Control System

```python title="integrated_input_control.py"
from rdetoolkit.impl.input_controller import (
    InvoiceChecker, ExcelInvoiceChecker,
    RDEFormatChecker, MultiFileChecker
)
from rdetoolkit.models.rde2types import RdeInputDirPaths
from pathlib import Path

class InputModeController:
    """Integrated input mode control system"""

    def __init__(self, input_paths: RdeInputDirPaths):
        self.input_paths = input_paths
        self.checkers = {
            "Invoice": InvoiceChecker(input_paths),
            "ExcelInvoice": ExcelInvoiceChecker(input_paths),
            "RDEFormat": RDEFormatChecker(input_paths),
            "MultiFile": MultiFileChecker(input_paths)
        }

    def detect_input_mode(self) -> str:
        """Automatic detection of input mode"""

        # Check for Excel invoice files
        excel_files = list(self.input_paths.invoice.glob("*.xlsx"))
        if excel_files:
            return "ExcelInvoice"

        # Check for JSON invoice files
        json_files = list(self.input_paths.invoice.glob("*.json"))
        if json_files:
            return "Invoice"

        # Check for ZIP files
        zip_files = list(self.input_paths.inputdata.glob("*.zip"))
        if zip_files:
            return "RDEFormat"

        # Default to MultiFile
        return "MultiFile"

    def process_input(self) -> dict:
        """Execute processing based on detected input mode"""

        detected_mode = self.detect_input_mode()
        print(f"Detected input mode: {detected_mode}")

        try:
            checker = self.checkers[detected_mode]

            if detected_mode == "ExcelInvoice":
                data = checker.read()
                index = checker.get_index()
                rawfiles = checker._get_rawfiles()

                return {
                    "mode": detected_mode,
                    "status": "success",
                    "data": data,
                    "index": index,
                    "rawfiles": rawfiles
                }

            else:
                parsed_data = checker.parse()
                file_groups = checker._get_group_by_files() if hasattr(checker, '_get_group_by_files') else []

                return {
                    "mode": detected_mode,
                    "status": "success",
                    "data": parsed_data,
                    "file_groups": file_groups
                }

        except Exception as e:
            return {
                "mode": detected_mode,
                "status": "error",
                "error": str(e)
            }

# Example usage
input_paths = RdeInputDirPaths(
    inputdata=Path("data/input"),
    invoice=Path("data/invoice"),
    tasksupport=Path("data/tasksupport")
)

controller = InputModeController(input_paths)
result = controller.process_input()

print(f"Result: {result}")
if result["status"] == "success":
    print(f"✓ Successfully processed in {result['mode']} mode")
else:
    print(f"✗ Error in {result['mode']} mode: {result['error']}")
```
