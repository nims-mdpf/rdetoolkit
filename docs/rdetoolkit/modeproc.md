# ModeProc API

## Purpose

This module defines processing for various input modes in RDEToolKit's structured processing. It provides dedicated processing flows for Invoice, ExcelInvoice, RDEFormat, and MultiFile modes.

## Key Features

### Input Mode Processing
- **Invoice Mode**: Processing using JSON format invoice files
- **Excel Invoice Mode**: Processing using Excel format invoice files
- **RDEFormat Mode**: Processing in RDE standard format
- **MultiFile Mode**: Batch processing of multiple files

### File Operations
- Copying input files to raw data directory
- Generation and placement of thumbnail images
- Metadata validation and updates

---

::: src.rdetoolkit.modeproc.invoice_mode_process

---

::: src.rdetoolkit.modeproc.excel_invoice_mode_process

---

::: src.rdetoolkit.modeproc.rdeformat_mode_process

---

::: src.rdetoolkit.modeproc.copy_input_to_rawfile_for_rdeformat

---

::: src.rdetoolkit.modeproc.multifile_mode_process

---

::: src.rdetoolkit.modeproc.copy_input_to_rawfile

---

::: src.rdetoolkit.modeproc.selected_input_checker

---

## Practical Usage

### RDEFormat Mode Processing

```python title="rdeformat_processing.py"
from rdetoolkit.modeproc import rdeformat_mode_process
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath

def custom_dataset_function(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    """Custom dataset processing function"""
    # Set metadata
    metadata = {
        "processing_mode": "rdeformat",
        "timestamp": "2024-01-01T10:00:00Z"
    }
    
    # Create metadata file
    import json
    with open(resource_paths.meta / "metadata.json", "w") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

# Execute RDEFormat mode processing
result = rdeformat_mode_process(
    index="001",
    srcpaths=srcpaths,
    resource_paths=resource_paths,
    datasets_process_function=custom_dataset_function
)

print(f"Processing result: {result.status}")
print(f"Execution ID: {result.run_id}")
```

### Invoice Mode Processing

```python title="invoice_processing.py"
from rdetoolkit.modeproc import invoice_mode_process
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath

# Execute Invoice mode processing
result = invoice_mode_process(
    index="002",
    srcpaths=srcpaths,
    resource_paths=resource_paths,
    datasets_process_function=custom_dataset_function
)

if result.status == "success":
    print(f"Invoice processing completed successfully: {result.title}")
else:
    print(f"Processing error: {result.error_message}")
```

### Excel Invoice Mode Processing

```python title="excel_invoice_processing.py"
from rdetoolkit.modeproc import excel_invoice_mode_process
from pathlib import Path

# Specify Excel invoice file
excel_invoice_path = Path("data/invoice/invoice.xlsx")

# Execute Excel Invoice mode processing
result = excel_invoice_mode_process(
    index="003",
    srcpaths=srcpaths,
    resource_paths=resource_paths,
    datasets_process_function=custom_dataset_function,
    excel_invoice_file=excel_invoice_path
)

print(f"Excel Invoice processing result: {result.status}")
```

### MultiFile Mode Processing

```python title="multifile_processing.py"
from rdetoolkit.modeproc import multifile_mode_process

# Batch processing of multiple files
result = multifile_mode_process(
    index="004",
    srcpaths=srcpaths,
    resource_paths=resource_paths,
    datasets_process_function=custom_dataset_function
)

print(f"MultiFile processing result: {result.status}")
print(f"Processing target: {result.target}")
```

### Using Input Checker

```python title="input_checker.py"
from rdetoolkit.modeproc import selected_input_checker
from rdetoolkit.models.rde2types import RdeInputDirPaths

# Check appropriateness of input files
srcpaths = RdeInputDirPaths(
    inputdata=Path("data/input"),
    invoice=Path("data/invoice"),
    tasksupport=Path("data/tasksupport")
)

checker_result = selected_input_checker(srcpaths, mode="Invoice")
if checker_result:
    print("Input files are appropriate")
else:
    print("There are issues with input files")
```
