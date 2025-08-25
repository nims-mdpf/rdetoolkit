# Excel Invoice Generator API

## Purpose

This module defines Excel invoice template generation processing in RDEToolKit. It provides functionality for template creation, saving, validation, and customization.

## Key Features

### Template Generation
- Automatic Excel invoice template generation
- Customizable template structure
- Multilingual header generation

### Command Execution
- Template generation via command line
- Configuration file-based generation
- Batch processing support

---

::: src.rdetoolkit.cmd.gen_excelinvoice.GenerateExcelInvoiceCommand

---

## Practical Usage

### Basic Command Execution

```python title="basic_excel_invoice_generation.py"
from rdetoolkit.cmd.gen_excelinvoice import GenerateExcelInvoiceCommand

# Create Excel invoice generation command
command = GenerateExcelInvoiceCommand()

# Execute command
try:
    result = command.invoke()
    print(f"✓ Excel invoice template generation completed: {result}")
except Exception as e:
    print(f"✗ Excel invoice generation error: {e}")
```

### Generation with Custom Configuration

```python title="custom_excel_invoice_generation.py"
from rdetoolkit.cmd.gen_excelinvoice import GenerateExcelInvoiceCommand
from pathlib import Path
import json

# Create custom configuration file
custom_config = {
    "template_name": "Material Science Experiment Invoice",
    "output_path": "templates/material_science_invoice.xlsx",
    "basic_fields": [
        {"name": "dataName", "label": "Data Name", "required": True},
        {"name": "researcher", "label": "Researcher", "required": True},
        {"name": "institution", "label": "Institution", "required": True},
        {"name": "experiment_date", "label": "Experiment Date", "required": True}
    ],
    "general_attributes": [
        {"name": "temperature", "unit": "℃", "description": "Measurement temperature"},
        {"name": "pressure", "unit": "hPa", "description": "Atmospheric pressure"},
        {"name": "humidity", "unit": "%", "description": "Humidity"}
    ],
    "specific_attributes": [
        {"name": "material_type", "description": "Material type"},
        {"name": "sample_size", "unit": "mm", "description": "Sample size"},
        {"name": "surface_treatment", "description": "Surface treatment"}
    ],
    "styling": {
        "header_color": "#4472C4",
        "font_name": "Arial",
        "font_size": 11
    }
}

# Save configuration file
config_path = Path("config/custom_invoice_config.json")
config_path.parent.mkdir(parents=True, exist_ok=True)

with open(config_path, 'w', encoding='utf-8') as f:
    json.dump(custom_config, f, ensure_ascii=False, indent=2)

# Execute command with custom configuration
command = GenerateExcelInvoiceCommand()

try:
    result = command.invoke(config_file=str(config_path))
    print(f"✓ Custom Excel invoice generation completed: {result}")
    
    output_file = Path(custom_config["output_path"])
    if output_file.exists():
        print(f"✓ File generation confirmed: {output_file}")
        print(f"File size: {output_file.stat().st_size:,} bytes")
    
except Exception as e:
    print(f"✗ Custom Excel invoice generation error: {e}")
```
