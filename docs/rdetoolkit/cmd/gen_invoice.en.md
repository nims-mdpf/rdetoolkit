# Invoice Generator API

## Purpose

This module defines the command for generating `invoice.json` from `invoice.schema.json`. It automatically generates invoice files based on schema definitions and validates them using InvoiceValidator.

## Key Features

### Invoice Generation
- Automatic invoice.json generation from invoice.schema.json
- Automatic default value assignment (schema default → examples → type-based)
- Option to generate required fields only
- Automatic validation after generation

### Output Options
- Pretty/Compact JSON formatting
- Custom output path specification
- Default value population control

---

::: src.rdetoolkit.cmd.gen_invoice.GenerateInvoiceCommand

---

## Practical Usage

### Basic Command Execution

```python title="basic_invoice_generation.py"
from rdetoolkit.cmd.gen_invoice import GenerateInvoiceCommand
from pathlib import Path

# Create invoice generation command
command = GenerateInvoiceCommand(
    schema_path=Path("tasksupport/invoice.schema.json"),
    output_path=Path("invoice/invoice.json"),
)

# Execute command
try:
    command.invoke()
    print("✓ Invoice generation completed")
except Exception as e:
    print(f"✗ Invoice generation error: {e}")
```

### Generation with Custom Options

```python title="custom_invoice_generation.py"
from rdetoolkit.cmd.gen_invoice import GenerateInvoiceCommand
from pathlib import Path

# Generate with required fields only, compact format
command = GenerateInvoiceCommand(
    schema_path=Path("tasksupport/invoice.schema.json"),
    output_path=Path("invoice/invoice.json"),
    fill_defaults=False,      # Don't fill default values
    required_only=True,       # Required fields only
    output_format="compact",  # Compact JSON
)

try:
    command.invoke()
    print("✓ Minimal invoice.json generated")
except Exception as e:
    print(f"✗ Generation error: {e}")
```

### Batch Processing Usage

```python title="batch_invoice_generation.py"
from rdetoolkit.cmd.gen_invoice import GenerateInvoiceCommand
from pathlib import Path

# Generate invoices from multiple schemas
schemas = [
    ("project_a/invoice.schema.json", "project_a/invoice.json"),
    ("project_b/invoice.schema.json", "project_b/invoice.json"),
    ("project_c/invoice.schema.json", "project_c/invoice.json"),
]

results = {"success": [], "failed": []}

for schema_path, output_path in schemas:
    try:
        command = GenerateInvoiceCommand(
            schema_path=Path(schema_path),
            output_path=Path(output_path),
        )
        command.invoke()
        results["success"].append(output_path)
        print(f"✓ {output_path}")
    except Exception as e:
        results["failed"].append((output_path, str(e)))
        print(f"✗ {output_path}: {e}")

print(f"\nSuccess: {len(results['success'])}, Failed: {len(results['failed'])}")
```

## CLI Usage

When using directly from the command line:

```bash
# Basic usage
rdetoolkit gen-invoice tasksupport/invoice.schema.json

# Specify output path
rdetoolkit gen-invoice tasksupport/invoice.schema.json -o invoice/invoice.json

# Generate required fields only
rdetoolkit gen-invoice tasksupport/invoice.schema.json --required-only

# Don't fill default values
rdetoolkit gen-invoice tasksupport/invoice.schema.json --no-fill-defaults

# Output in compact format
rdetoolkit gen-invoice tasksupport/invoice.schema.json --format compact
```

## Default Value Strategy

Default values are determined in the following priority order:

1. Schema `default` field
2. First item from schema `examples` array
3. Type-based default values:
   - string → `""`
   - number → `0.0`
   - integer → `0`
   - boolean → `false`
   - array → `[]`
   - object → `{}`
