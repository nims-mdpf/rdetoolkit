# CLI Workflow — Complete Reference

## Command Overview

| Command | Purpose |
|---------|---------|
| `rdetoolkit init` | Scaffold a new project |
| `rdetoolkit validate invoice-schema <path>` | Validate schema syntax |
| `rdetoolkit validate invoice <path> --schema <schema>` | Validate invoice against schema |
| `rdetoolkit validate metadata-def <path>` | Validate metadata definition |
| `rdetoolkit validate metadata <path> --schema <def>` | Validate metadata against definition |
| `rdetoolkit validate all [path]` | Run all validations at once |
| `python3 main.py` | Execute structured processing |

---

## Correct Execution Order

This order is critical. Skipping steps or running out of sequence causes confusing errors.

### Phase 1: Project Setup

```bash
# Create project skeleton
rdetoolkit init          # or: python3 -m rdetoolkit init

# Install additional dependencies if needed
pip install -r requirements.txt
```

### Phase 2: Template Editing (ORDER MATTERS)

Edit files in this exact sequence:

#### Step 1: Define the schema — `invoice.schema.json`

This JSON Schema defines what fields are allowed in `invoice.json`.
Define the schema BEFORE filling in invoice values.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "sample_name": {
      "type": "string",
      "description": "Name of the measured sample"
    },
    "measurement_date": {
      "type": "string",
      "format": "date"
    },
    "temperature_k": {
      "type": "number",
      "minimum": 0
    }
  },
  "required": ["sample_name"]
}
```

#### Step 2: Configure metadata definitions — `metadata-def.json`

Maps invoice fields to RDE metadata fields.

#### Step 3: Fill in invoice values — `invoice.json`

Now fill in actual values that conform to the schema defined in Step 1.

```json
{
  "sample_name": "NiO-001",
  "measurement_date": "2025-03-15",
  "temperature_k": 300
}
```

### Phase 3: Validation (ORDER MATTERS)

```bash
# 1. Validate the schema file itself (is it valid JSON Schema?)
rdetoolkit validate invoice-schema data/tasksupport/invoice.schema.json

# 2. Validate invoice against the schema (does invoice.json conform?)
rdetoolkit validate invoice data/invoice/invoice.json \
  --schema data/tasksupport/invoice.schema.json

# 3. Validate metadata definition file
rdetoolkit validate metadata-def data/tasksupport/metadata-def.json

# Or run all at once:
rdetoolkit validate all
```

#### Why order matters

- If `invoice.schema.json` has syntax errors, validating `invoice.json` against it
  will give misleading error messages
- If `invoice.json` doesn't match the schema, the structured processing will fail
  at runtime with unclear errors
- Validate bottom-up: schema → invoice → metadata-def → all

### Phase 4: Implement dataset function

Write your processing logic in `modules/`:

```python
# modules/my_processor.py
from rdetoolkit.models.rde2types import RdeDatasetPaths
from rdetoolkit.fileops import read_from_json_file

def dataset(paths: RdeDatasetPaths) -> None:
    # Your processing logic here
    ...
```

### Phase 5: Wire entry point and run

```python
# main.py
import rdetoolkit
from modules.my_processor import dataset

rdetoolkit.workflows.run(custom_dataset_function=dataset)
```

```bash
python3 main.py
```

---

## Validation Commands — Detail

### `rdetoolkit validate invoice-schema`

Checks that the schema file itself is valid JSON Schema.

```bash
rdetoolkit validate invoice-schema data/tasksupport/invoice.schema.json
```

Common errors:
- Invalid JSON syntax (missing commas, unmatched brackets)
- Invalid JSON Schema keywords
- Unsupported `$ref` references

### `rdetoolkit validate invoice`

Checks that invoice.json conforms to the schema.

```bash
rdetoolkit validate invoice data/invoice/invoice.json \
  --schema data/tasksupport/invoice.schema.json
```

Common errors:
- Missing required fields
- Type mismatches (string where number expected)
- Values outside defined ranges

### `rdetoolkit validate metadata-def`

Checks the metadata definition file structure.

```bash
rdetoolkit validate metadata-def data/tasksupport/metadata-def.json
```

### `rdetoolkit validate all`

Runs all validations in the correct order. Recommended for CI/CD.

```bash
# Default: validate current directory
rdetoolkit validate all

# Specify project path
rdetoolkit validate all /path/to/project

# JSON output for CI/CD pipelines
rdetoolkit validate all --format json
```

---

## CI/CD Integration

```yaml
# GitHub Actions example
- name: Validate RDE project
  run: |
    pip install rdetoolkit
    rdetoolkit validate all --format json
```

---

## Fixing Validation Errors

| Error | Likely cause | Fix |
|-------|-------------|-----|
| "Schema validation failed" on invoice-schema | Malformed JSON Schema | Check JSON syntax, use a JSON Schema validator |
| "Required property missing" on invoice | invoice.json missing a required field | Add the field defined in invoice.schema.json |
| "Type mismatch" on invoice | Wrong data type in invoice.json | Match the type specified in schema (string, number, etc.) |
| "Invalid metadata-def" | Structural issue in metadata-def.json | Check field mappings and required keys |
| Validation passes but runtime fails | Schema too permissive | Tighten schema constraints |
