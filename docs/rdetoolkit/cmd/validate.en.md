# Validate Command

## Purpose

The `validate` command group provides CLI tools for validating RDE project files including invoice schemas, invoice data, metadata definitions, and metadata data. These commands help catch configuration errors early in the development workflow and integrate seamlessly with CI/CD pipelines.

## Key Features

### Validation Commands
- Validate invoice schema structure
- Validate invoice data against schema
- Validate metadata definition files
- Validate metadata data against definitions
- Batch validation of entire projects

### Output Formats
- **Text**: Human-readable validation results (default)
- **JSON**: Machine-readable output for CI/CD integration

### Exit Codes
- **0**: All validations passed successfully
- **1**: Validation failures detected
- **2**: Invalid command usage or arguments
- **3**: Internal errors or unexpected exceptions

---

## Commands

### validate invoice-schema

Validates the structure of an invoice schema file.

```bash
rdetoolkit validate invoice-schema <path>
```

**Arguments:**
- `path`: Path to the invoice schema JSON file

**Options:**
- `--format [text|json]`: Output format (default: text)
- `--quiet`: Only show errors, suppress informational messages

**Example:**
```bash
# Validate invoice schema with text output
rdetoolkit validate invoice-schema data/tasksupport/invoice.schema.json

# Validate with JSON output for CI
rdetoolkit validate invoice-schema data/tasksupport/invoice.schema.json --format json
```

---

### validate invoice

Validates invoice data against an invoice schema.

```bash
rdetoolkit validate invoice <invoice_path> --schema <schema_path>
```

**Arguments:**
- `invoice_path`: Path to the invoice JSON file to validate

**Options:**
- `--schema`: Path to the invoice schema file (required)
- `--format [text|json]`: Output format (default: text)
- `--quiet`: Only show errors, suppress informational messages

**Example:**
```bash
# Validate invoice against schema
rdetoolkit validate invoice data/invoice/invoice.json \
  --schema data/tasksupport/invoice.schema.json

# Validate with JSON output
rdetoolkit validate invoice data/invoice/invoice.json \
  --schema data/tasksupport/invoice.schema.json \
  --format json
```

---

### validate metadata-def

Validates the structure of a metadata definition file.

```bash
rdetoolkit validate metadata-def <path>
```

**Arguments:**
- `path`: Path to the metadata definition JSON file

**Options:**
- `--format [text|json]`: Output format (default: text)
- `--quiet`: Only show errors, suppress informational messages

**Example:**
```bash
# Validate metadata definition
rdetoolkit validate metadata-def data/tasksupport/metadata-def.json

# Validate with JSON output
rdetoolkit validate metadata-def data/tasksupport/metadata-def.json --format json
```

---

### validate metadata

Validates metadata data against a metadata definition schema.

```bash
rdetoolkit validate metadata <metadata_path> --schema <schema_path>
```

**Arguments:**
- `metadata_path`: Path to the metadata JSON file to validate

**Options:**
- `--schema`: Path to the metadata definition schema file (required)
- `--format [text|json]`: Output format (default: text)
- `--quiet`: Only show errors, suppress informational messages

**Example:**
```bash
# Validate metadata against definition
rdetoolkit validate metadata data/metadata.json \
  --schema data/tasksupport/metadata-def.json

# Validate with JSON output
rdetoolkit validate metadata data/metadata.json \
  --schema data/tasksupport/metadata-def.json \
  --format json
```

---

### validate all

Performs batch validation of all standard files in an RDE project directory.

```bash
rdetoolkit validate all [project_dir]
```

**Arguments:**
- `project_dir`: Path to the RDE project directory (default: current directory)

**Discovery Rules:**
The command automatically discovers and validates files in the standard RDE project layout:
- `data/tasksupport/invoice.schema.json` (invoice schema)
- `data/invoice/invoice.json` (invoice data)
- `data/tasksupport/metadata-def.json` (metadata definition)

**Options:**
- `--format [text|json]`: Output format (default: text)
- `--strict/--no-strict`: Treat warnings as failures (default: no-strict)
- `--quiet`: Only show errors and summary

**Example:**
```bash
# Validate all files in current directory
rdetoolkit validate all

# Validate all files in specific project
rdetoolkit validate all /path/to/project

# Strict validation with JSON output
rdetoolkit validate all --strict --format json

# Quiet mode (errors only)
rdetoolkit validate all --quiet
```

---

## Output Formats

### Text Output (Default)

Human-readable format suitable for terminal display:

```
✓ Invoice schema validation passed
✓ Invoice data validation passed
✓ Metadata definition validation passed

All validations passed (3/3)
```

**Error Example:**
```
✗ Invoice validation failed:
  - Missing required field: 'basic_info'
  - Invalid format for 'timestamp': expected ISO8601

1 validation failed, 2 passed (1/3)
```

### JSON Output

Machine-readable format suitable for CI/CD pipelines:

```json
{
  "results": [
    {
      "target": "data/tasksupport/invoice.schema.json",
      "type": "invoice-schema",
      "status": "passed",
      "errors": []
    },
    {
      "target": "data/invoice/invoice.json",
      "type": "invoice",
      "status": "failed",
      "errors": [
        {
          "message": "Missing required field: 'basic_info'",
          "path": "$.basic_info"
        },
        {
          "message": "Invalid format for 'timestamp': expected ISO8601",
          "path": "$.timestamp"
        }
      ]
    }
  ],
  "summary": {
    "total": 3,
    "passed": 2,
    "failed": 1
  }
}
```

---

## Use Cases

### 1. Basic Validation Workflow

Validate individual files during development:

```bash
# Step 1: Validate schema structure
rdetoolkit validate invoice-schema data/tasksupport/invoice.schema.json

# Step 2: Validate invoice data against schema
rdetoolkit validate invoice data/invoice/invoice.json \
  --schema data/tasksupport/invoice.schema.json

# Step 3: Validate metadata definition
rdetoolkit validate metadata-def data/tasksupport/metadata-def.json
```

### 2. CI/CD Integration

Integrate validation into continuous integration pipelines:

```yaml
# .github/workflows/validate.yml
name: Validate RDE Files

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install RDEToolKit
        run: pip install rdetoolkit
      - name: Validate all RDE files
        run: |
          rdetoolkit validate all --format json --strict > validation-results.json
          cat validation-results.json
```

**Exit Code Handling in CI:**
```bash
#!/bin/bash
# ci-validate.sh

rdetoolkit validate all --format json
EXIT_CODE=$?

case $EXIT_CODE in
  0)
    echo "✓ All validations passed"
    exit 0
    ;;
  1)
    echo "✗ Validation failures detected"
    exit 1
    ;;
  2)
    echo "✗ Invalid command usage"
    exit 2
    ;;
  3)
    echo "✗ Internal error occurred"
    exit 3
    ;;
esac
```

### 3. JSON Output Parsing

Parse JSON output for custom processing:

```python
# parse_validation.py
import json
import sys
import subprocess

result = subprocess.run(
    ["rdetoolkit", "validate", "all", "--format", "json"],
    capture_output=True,
    text=True
)

data = json.loads(result.stdout)

# Check for failures
if data["summary"]["failed"] > 0:
    print(f"Validation failures detected: {data['summary']['failed']}")

    # Print detailed errors
    for item in data["results"]:
        if item["status"] == "failed":
            print(f"\nFailed: {item['target']} ({item['type']})")
            for error in item["errors"]:
                print(f"  - {error['message']}")
                if "path" in error:
                    print(f"    Path: {error['path']}")

    sys.exit(1)

print(f"✓ All validations passed ({data['summary']['total']})")
sys.exit(0)
```

### 4. Pre-commit Hook

Add validation as a Git pre-commit hook:

```bash
# .git/hooks/pre-commit
#!/bin/bash

echo "Running RDE validation..."

rdetoolkit validate all --quiet

if [ $? -ne 0 ]; then
    echo "❌ RDE validation failed. Commit aborted."
    echo "Run 'rdetoolkit validate all' for details."
    exit 1
fi

echo "✅ RDE validation passed"
exit 0
```

### 5. Batch Project Validation

Validate multiple projects in a batch:

```bash
#!/bin/bash
# validate-projects.sh

PROJECTS_DIR="./rde-projects"
FAILED_PROJECTS=()

for project in "$PROJECTS_DIR"/*; do
    if [ -d "$project" ]; then
        echo "Validating: $(basename "$project")"

        rdetoolkit validate all "$project" --quiet

        if [ $? -ne 0 ]; then
            FAILED_PROJECTS+=("$(basename "$project")")
        fi
    fi
done

if [ ${#FAILED_PROJECTS[@]} -eq 0 ]; then
    echo "✓ All projects validated successfully"
    exit 0
else
    echo "✗ Validation failed for projects:"
    printf '  - %s\n' "${FAILED_PROJECTS[@]}"
    exit 1
fi
```

---

## Common Error Messages

### Schema Validation Errors

**Invalid JSON syntax:**
```
✗ Invoice schema validation failed:
  - Invalid JSON: Unexpected token at line 15, column 3
  - Suggestion: Check for missing commas, brackets, or quotes
```

**Missing required schema fields:**
```
✗ Invoice schema validation failed:
  - Missing required field: '$schema'
  - Missing required field: 'properties'
```

### Data Validation Errors

**Schema mismatch:**
```
✗ Invoice validation failed:
  - Data does not conform to schema
  - Missing required property: 'basic_info'
  - Additional property not allowed: 'extra_field'
```

**Type mismatch:**
```
✗ Metadata validation failed:
  - Type mismatch at '$.timestamp': expected string, got integer
  - Type mismatch at '$.values': expected array, got object
```

### File Not Found Errors

```
✗ Validation failed:
  - File not found: data/invoice/invoice.json
  - Suggestion: Ensure the file exists and path is correct
```

---

## Best Practices

1. **Validate Early**: Run validation commands before committing changes
2. **Use in CI**: Integrate with CI/CD pipelines for automated validation
3. **JSON Format for Automation**: Use `--format json` for scripts and CI
4. **Quiet Mode in Scripts**: Use `--quiet` to reduce noise in automated workflows
5. **Strict Mode for Production**: Use `--strict` in production pipelines
6. **Version Control Schemas**: Keep schema files under version control
7. **Document Custom Schemas**: Add comments to schema files explaining validation rules

---

## Troubleshooting

### Validation Passes Locally but Fails in CI

**Possible causes:**
- Different file paths between environments
- Missing files not tracked in version control
- Line ending differences (CRLF vs LF)

**Solution:**
```bash
# Use absolute paths or project-relative paths
rdetoolkit validate all /path/to/project

# Ensure all required files are committed
git status

# Normalize line endings
git config core.autocrlf input
```

### JSON Output Not Parseable

**Possible causes:**
- Mixed output (logs + JSON)
- Unexpected error messages

**Solution:**
```bash
# Use quiet mode to suppress non-JSON output
rdetoolkit validate all --format json --quiet > results.json

# Redirect stderr separately
rdetoolkit validate all --format json 2>errors.log >results.json
```

### Exit Code Not as Expected

**Debugging:**
```bash
# Capture and display exit code
rdetoolkit validate all
echo "Exit code: $?"

# Run with verbose output
rdetoolkit validate all --format text

# Check for file permission issues
ls -la data/tasksupport/
```

---

## Related Commands

- `rdetoolkit init`: Initialize RDE project structure
- `rdetoolkit gen-excelinvoice`: Generate Excel invoice template
- `rdetoolkit archive`: Create deployment archive

---

## See Also

- [Validation Module API](../validation.md)
- [Invoice Schema Documentation](../models/invoice_schema.md)
- [Metadata Definition Documentation](../models/metadata.md)
- [Command API](./command.md)
