# Excel Invoice Generation API

## Purpose

This module provides Excel invoice generation functionality for RDEToolKit. It handles the creation of Excel-formatted invoice files from structured data, with support for templates and customization.

## Key Features

### Excel Invoice Generation
- Excel file generation from structured data
- Template-based invoice creation
- Customizable formatting and layout

### Data Integration
- Integration with invoice data models
- Support for multiple data sources
- Validation and error handling

---

::: src.rdetoolkit.cmd.gen_excelinvoice

---

## Practical Usage

### Basic Excel Invoice Generation

```python title="excel_invoice_generation.py"
from rdetoolkit.cmd.gen_excelinvoice import generate_excel_invoice
from pathlib import Path

# Generate Excel invoice
input_data = {
    "basic": {
        "dataName": "Experiment Data 001",
        "description": "Temperature measurement experiment"
    },
    "sample": {
        "generalAttributes": [],
        "specificAttributes": []
    }
}

output_path = Path("data/output/invoice.xlsx")
result = generate_excel_invoice(input_data, output_path)

print(f"Excel invoice generation result: {result}")
```
