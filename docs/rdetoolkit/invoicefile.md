# InvoiceFile API

## Purpose

This module handles processing of invoice files (invoice.json) and Excel invoice files in RDEToolKit. It provides functionality for data file management, metadata extraction, and file path operations.

## Key Features

### Invoice File Management
- Loading and manipulation of JSON format invoice files
- Processing of Excel format invoice files
- Path management and listing of raw data files

### Data Processing
- Application and replacement of magic variables
- Updating descriptions with feature information
- File existence verification and validation
- Rule-based replacement processing

---

::: src.rdetoolkit.invoicefile.read_excelinvoice

---

::: src.rdetoolkit.invoicefile.check_exist_rawfiles

---

::: src.rdetoolkit.invoicefile._assign_invoice_val

---

::: src.rdetoolkit.invoicefile.overwrite_invoicefile_for_dpfterm

---

::: src.rdetoolkit.invoicefile.InvoiceFile

---

::: src.rdetoolkit.invoicefile.ExcelInvoiceFile

---

::: src.rdetoolkit.invoicefile.ExcelInvoiceTemplateGenerator

---

::: src.rdetoolkit.invoicefile.backup_invoice_json_files

---

::: src.rdetoolkit.invoicefile.update_description_with_features

---

::: src.rdetoolkit.invoicefile.RuleBasedReplacer

---

::: src.rdetoolkit.invoicefile.apply_default_filename_mapping_rule

---

::: src.rdetoolkit.invoicefile.apply_magic_variable

---

## Practical Usage

### Basic Invoice File Operations

```python title="basic_invoice.py"
from rdetoolkit.invoicefile import InvoiceFile
from pathlib import Path

# Load invoice file
invoice_path = Path("data/invoice/invoice.json")
invoice = InvoiceFile(invoice_path)

# Read invoice data
invoice_data = invoice.read()
print(f"Data name: {invoice_data.get('basic', {}).get('dataName')}")

# Overwrite invoice file
updated_data = invoice_data.copy()
updated_data['basic']['description'] = "Updated description"
invoice.overwrite(updated_data)
```

### Excel Invoice File Processing

```python title="excel_invoice.py"
from rdetoolkit.invoicefile import ExcelInvoiceFile, read_excelinvoice
from pathlib import Path

# Load Excel invoice file
excel_path = Path("data/invoice/invoice.xlsx")
excel_invoice = ExcelInvoiceFile(excel_path)

# Read data
excel_data = excel_invoice.read()
print(f"Loaded data: {excel_data}")

# Generate template
template_data = excel_invoice.generate_template()
excel_invoice.save(template_data, Path("data/invoice/template.xlsx"))

# Read as dataframes
dataframes = read_excelinvoice(excel_path)
print(f"Number of sheets: {len(dataframes)}")
```

### File Existence Verification and Validation

```python title="file_validation.py"
from rdetoolkit.invoicefile import check_exist_rawfiles
from pathlib import Path

# Check existence of raw data files
rawfiles_dir = Path("data/rawfiles")
file_list = ["data1.csv", "data2.txt", "image.png"]

missing_files = check_exist_rawfiles(rawfiles_dir, file_list)
if missing_files:
    print(f"Missing files: {missing_files}")
else:
    print("All files exist")
```

### Magic Variables and Rule-Based Replacement

```python title="magic_variables_and_rules.py"
from rdetoolkit.invoicefile import apply_magic_variable, RuleBasedReplacer
from rdetoolkit.models.rde2types import RdeOutputResourcePath
from pathlib import Path

# Apply magic variables
resource_paths = RdeOutputResourcePath(
    rawfiles=Path("data/rawfiles"),
    thumbnail=Path("data/thumbnail"),
    meta=Path("data/meta"),
    invoice=Path("data/invoice")
)

invoice_path = resource_paths.invoice / "invoice.json"
apply_magic_variable(resource_paths, invoice_path)

# Use rule-based replacer
replacer = RuleBasedReplacer()
replacer.load_rules(Path("config/replacement_rules.json"))

# Apply replacement rules
apply_rules_obj = replacer.get_apply_rules_obj()
replacer.set_rule("temperature", "Temperature")
replacer.write_rule(Path("config/updated_rules.json"))
```
