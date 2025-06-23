# Generate Excel Invoice Module

The `rdetoolkit.cmd.gen_excelinvoice` module provides functionality for generating Excel invoice templates from JSON schema files. This module is designed to create standardized Excel files that conform to RDE (Research Data Exchange) invoice specifications, supporting both file and folder processing modes.

## Overview

The generate Excel invoice module offers specialized template generation capabilities:

- **Excel Template Generation**: Create Excel invoice templates from JSON schema definitions
- **Schema Validation**: Validate invoice schemas before template generation
- **Mode Support**: Support for both file and folder processing modes
- **Error Handling**: Comprehensive error handling with user-friendly messages

## Classes

### GenerateExcelInvoiceCommand

A command class that generates Excel invoice templates based on JSON schema files with support for different processing modes.

#### Constructor

```python
GenerateExcelInvoiceCommand(invoice_schema_file: pathlib.Path, output_path: pathlib.Path, mode: Literal["file", "folder"])
```

**Parameters:**
- `invoice_schema_file` (pathlib.Path): Path to the JSON schema file that defines the invoice structure
- `output_path` (pathlib.Path): Path where the generated Excel template will be saved
- `mode` (Literal["file", "folder"]): Processing mode - either "file" for single file processing or "folder" for batch processing

#### Attributes

- `invoice_schema_file` (pathlib.Path): The source schema file path
- `output_path` (pathlib.Path): The target output file path
- `mode` (Literal["file", "folder"]): The processing mode

#### Methods

##### invoke()

Execute the Excel invoice template generation process.

```python
def invoke() -> None
```

**Raises:**
- `click.Abort`: If validation fails, schema file is not found, or generation encounters errors
- `FileNotFoundError`: If the schema file does not exist
- `InvoiceSchemaValidationError`: If the schema validation fails
- `Exception`: For any unexpected errors during generation

**Example:**
```python
import pathlib
from rdetoolkit.cmd.gen_excelinvoice import GenerateExcelInvoiceCommand

# Generate Excel invoice template
schema_file = pathlib.Path("schemas/invoice.schema.json")
output_file = pathlib.Path("templates/my_invoice_excel_invoice.xlsx")

command = GenerateExcelInvoiceCommand(
    invoice_schema_file=schema_file,
    output_path=output_file,
    mode="file"
)
command.invoke()
```

#### File Naming Conventions

The generated Excel files must follow specific naming conventions:

- **Required Suffix**: All output files must end with `_excel_invoice.xlsx`
- **Example Valid Names**:
  - `project_excel_invoice.xlsx`
  - `2024_data_excel_invoice.xlsx`
  - `research_template_excel_invoice.xlsx`

## Complete Usage Examples

### Basic Excel Invoice Generation

```python
import pathlib
from rdetoolkit.cmd.gen_excelinvoice import GenerateExcelInvoiceCommand

def generate_basic_invoice_template():
    """Generate a basic Excel invoice template."""

    # Define paths
    schema_path = pathlib.Path("data/invoice.schema.json")
    output_path = pathlib.Path("output/basic_excel_invoice.xlsx")

    # Create command instance
    command = GenerateExcelInvoiceCommand(
        invoice_schema_file=schema_path,
        output_path=output_path,
        mode="file"
    )

    try:
        command.invoke()
        print(f"✅ Template generated successfully: {output_path}")
    except Exception as e:
        print(f"❌ Generation failed: {e}")

# Usage
generate_basic_invoice_template()
```

### Batch Template Generation

```python
import pathlib
from rdetoolkit.cmd.gen_excelinvoice import GenerateExcelInvoiceCommand

def generate_multiple_templates(schemas_dir: str, output_dir: str):
    """Generate Excel templates for multiple schema files."""

    schemas_path = pathlib.Path(schemas_dir)
    output_path = pathlib.Path(output_dir)

    # Ensure output directory exists
    output_path.mkdir(parents=True, exist_ok=True)

    # Find all schema files
    schema_files = list(schemas_path.glob("*.schema.json"))

    if not schema_files:
        print(f"No schema files found in {schemas_path}")
        return

    print(f"Found {len(schema_files)} schema files")

    for schema_file in schema_files:
        # Generate output filename
        template_name = schema_file.stem.replace('.schema', '_excel_invoice.xlsx')
        output_file = output_path / template_name

        print(f"Processing: {schema_file.name}")

        try:
            command = GenerateExcelInvoiceCommand(
                invoice_schema_file=schema_file,
                output_path=output_file,
                mode="file"  # Use "folder" mode for batch processing if supported
            )
            command.invoke()
            print(f"  ✅ Generated: {output_file.name}")

        except Exception as e:
            print(f"  ❌ Failed: {e}")

# Usage
generate_multiple_templates("schemas", "templates")
```

### Advanced Template Generation with Validation

```python
import pathlib
import json
from rdetoolkit.cmd.gen_excelinvoice import GenerateExcelInvoiceCommand

def generate_validated_template(schema_file: str, output_file: str):
    """Generate Excel template with pre-validation."""

    schema_path = pathlib.Path(schema_file)
    output_path = pathlib.Path(output_file)

    # Validate file naming convention
    if not output_path.name.endswith('_excel_invoice.xlsx'):
        print("❌ Error: Output filename must end with '_excel_invoice.xlsx'")
        return False

    # Validate schema file exists and is valid JSON
    if not schema_path.exists():
        print(f"❌ Error: Schema file not found: {schema_path}")
        return False

    try:
        # Test if schema is valid JSON
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_data = json.load(f)

        # Check for required schema properties
        required_keys = ['type', 'properties']
        missing_keys = [key for key in required_keys if key not in schema_data]

        if missing_keys:
            print(f"❌ Error: Schema missing required keys: {missing_keys}")
            return False

        print(f"✅ Schema validation passed")

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate template
        command = GenerateExcelInvoiceCommand(
            invoice_schema_file=schema_path,
            output_path=output_path,
            mode="file"
        )
        command.invoke()

        print(f"✅ Template generated successfully: {output_path}")
        return True

    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in schema file: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: Template generation failed: {e}")
        return False

# Usage
success = generate_validated_template(
    "schemas/project.schema.json",
    "templates/project_excel_invoice.xlsx"
)
```

### Integration with Project Workflow

```python
import pathlib
from typing import List, Tuple
from rdetoolkit.cmd.gen_excelinvoice import GenerateExcelInvoiceCommand

class ExcelInvoiceTemplateManager:
    """Manager class for Excel invoice template operations."""

    def __init__(self, schemas_dir: str, templates_dir: str):
        self.schemas_dir = pathlib.Path(schemas_dir)
        self.templates_dir = pathlib.Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)

    def generate_all_templates(self) -> List[Tuple[str, bool, str]]:
        """Generate templates for all schema files.

        Returns:
            List of tuples: (schema_name, success, message)
        """
        results = []
        schema_files = list(self.schemas_dir.glob("*.schema.json"))

        for schema_file in schema_files:
            result = self._generate_single_template(schema_file)
            results.append(result)

        return results

    def _generate_single_template(self, schema_file: pathlib.Path) -> Tuple[str, bool, str]:
        """Generate template for a single schema file."""

        # Generate output filename
        template_name = schema_file.stem.replace('.schema', '_excel_invoice.xlsx')
        output_file = self.templates_dir / template_name

        try:
            command = GenerateExcelInvoiceCommand(
                invoice_schema_file=schema_file,
                output_path=output_file,
                mode="file"
            )
            command.invoke()
            return (schema_file.name, True, f"Generated: {output_file.name}")

        except Exception as e:
            return (schema_file.name, False, f"Error: {str(e)}")

    def update_templates(self, force_update: bool = False) -> None:
        """Update existing templates if schema files are newer."""

        schema_files = list(self.schemas_dir.glob("*.schema.json"))

        for schema_file in schema_files:
            template_name = schema_file.stem.replace('.schema', '_excel_invoice.xlsx')
            template_file = self.templates_dir / template_name

            # Check if update is needed
            if not force_update and template_file.exists():
                schema_mtime = schema_file.stat().st_mtime
                template_mtime = template_file.stat().st_mtime

                if schema_mtime <= template_mtime:
                    print(f"⏭️  Skipping {schema_file.name} (template is up to date)")
                    continue

            print(f"🔄 Updating template for {schema_file.name}")
            schema_name, success, message = self._generate_single_template(schema_file)

            if success:
                print(f"  ✅ {message}")
            else:
                print(f"  ❌ {message}")

    def list_templates(self) -> List[pathlib.Path]:
        """List all generated Excel invoice templates."""
        return list(self.templates_dir.glob("*_excel_invoice.xlsx"))

    def cleanup_orphaned_templates(self) -> List[str]:
        """Remove templates that no longer have corresponding schema files."""

        # Get all schema base names
        schema_names = {f.stem.replace('.schema', '') for f in self.schemas_dir.glob("*.schema.json")}

        # Find orphaned templates
        orphaned = []
        for template in self.list_templates():
            template_base = template.stem.replace('_excel_invoice', '')
            if template_base not in schema_names:
                template.unlink()
                orphaned.append(template.name)

        return orphaned

# Usage example
def manage_project_templates():
    """Complete template management workflow."""

    manager = ExcelInvoiceTemplateManager("schemas", "templates")

    # Generate all templates
    print("🚀 Generating Excel invoice templates...")
    results = manager.generate_all_templates()

    # Report results
    successful = sum(1 for _, success, _ in results if success)
    total = len(results)
    print(f"\n📊 Generation complete: {successful}/{total} successful")

    for schema_name, success, message in results:
        status = "✅" if success else "❌"
        print(f"{status} {schema_name}: {message}")

    # List generated templates
    templates = manager.list_templates()
    print(f"\n📁 Generated templates ({len(templates)}):")
    for template in templates:
        print(f"  - {template.name}")

# Usage
manage_project_templates()
```

### Command-Line Integration Example

```python
import argparse
import pathlib
import sys
from rdetoolkit.cmd.gen_excelinvoice import GenerateExcelInvoiceCommand

def main():
    """Command-line interface for Excel invoice generation."""

    parser = argparse.ArgumentParser(
        description="Generate Excel invoice templates from JSON schemas"
    )
    parser.add_argument(
        "schema_file",
        type=pathlib.Path,
        help="Path to the invoice schema JSON file"
    )
    parser.add_argument(
        "output_file",
        type=pathlib.Path,
        help="Path for the generated Excel template (must end with '_excel_invoice.xlsx')"
    )
    parser.add_argument(
        "--mode",
        choices=["file", "folder"],
        default="file",
        help="Processing mode (default: file)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output file"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.schema_file.exists():
        print(f"❌ Error: Schema file not found: {args.schema_file}")
        sys.exit(1)

    if not args.output_file.name.endswith('_excel_invoice.xlsx'):
        print("❌ Error: Output filename must end with '_excel_invoice.xlsx'")
        sys.exit(1)

    if args.output_file.exists() and not args.force:
        print(f"❌ Error: Output file exists: {args.output_file}")
        print("Use --force to overwrite")
        sys.exit(1)

    # Generate template
    try:
        command = GenerateExcelInvoiceCommand(
            invoice_schema_file=args.schema_file,
            output_path=args.output_file,
            mode=args.mode
        )
        command.invoke()

    except KeyboardInterrupt:
        print("\n⚠️  Generation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

## Error Handling

### Common Exceptions

The Excel invoice generation module may raise the following exceptions:

#### click.Abort
Raised when command execution is aborted due to validation or processing errors:

```python
from rdetoolkit.cmd.gen_excelinvoice import GenerateExcelInvoiceCommand
import pathlib

try:
    command = GenerateExcelInvoiceCommand(
        invoice_schema_file=pathlib.Path("schema.json"),
        output_path=pathlib.Path("invalid_name.xlsx"),  # Missing required suffix
        mode="file"
    )
    command.invoke()
except click.Abort:
    print("Command execution was aborted")
    # Check console output for specific error details
```

#### FileNotFoundError
Raised when the schema file cannot be found:

```python
import pathlib
from rdetoolkit.cmd.gen_excelinvoice import GenerateExcelInvoiceCommand

schema_path = pathlib.Path("nonexistent_schema.json")

# Always check file existence before processing
if not schema_path.exists():
    print(f"Schema file not found: {schema_path}")
else:
    command = GenerateExcelInvoiceCommand(
        invoice_schema_file=schema_path,
        output_path=pathlib.Path("output_excel_invoice.xlsx"),
        mode="file"
    )
    command.invoke()
```

#### InvoiceSchemaValidationError
Raised when the schema file is invalid or doesn't conform to expected format:

```python
from rdetoolkit.cmd.gen_excelinvoice import GenerateExcelInvoiceCommand
from rdetoolkit.exceptions import InvoiceSchemaValidationError
import pathlib

try:
    command = GenerateExcelInvoiceCommand(
        invoice_schema_file=pathlib.Path("invalid_schema.json"),
        output_path=pathlib.Path("template_excel_invoice.xlsx"),
        mode="file"
    )
    command.invoke()
except InvoiceSchemaValidationError as e:
    print(f"Schema validation failed: {e}")
    print("Please check your schema file format and content")
```

### Best Practices

1. **Validate file paths before processing**:
   ```python
   def validate_paths(schema_file: pathlib.Path, output_file: pathlib.Path) -> bool:
       """Validate input and output paths."""

       # Check schema file
       if not schema_file.exists():
           print(f"Schema file not found: {schema_file}")
           return False

       if not schema_file.suffix == '.json':
           print(f"Schema file must be JSON: {schema_file}")
           return False

       # Check output file naming
       if not output_file.name.endswith('_excel_invoice.xlsx'):
           print(f"Output file must end with '_excel_invoice.xlsx': {output_file}")
           return False

       # Check output directory
       output_file.parent.mkdir(parents=True, exist_ok=True)

       return True
   ```

2. **Handle schema validation gracefully**:
   ```python
   import json

   def validate_schema_content(schema_file: pathlib.Path) -> bool:
       """Validate schema file content before processing."""
       try:
           with open(schema_file, 'r', encoding='utf-8') as f:
               schema = json.load(f)

           # Check required fields
           if 'type' not in schema:
               print("Schema missing 'type' field")
               return False

           if 'properties' not in schema:
               print("Schema missing 'properties' field")
               return False

           return True

       except json.JSONDecodeError as e:
           print(f"Invalid JSON in schema file: {e}")
           return False
       except Exception as e:
           print(f"Error reading schema file: {e}")
           return False
   ```

3. **Implement retry logic for transient failures**:
   ```python
   import time

   def generate_with_retry(command: GenerateExcelInvoiceCommand, max_retries: int = 3):
       """Generate template with retry logic."""

       for attempt in range(max_retries):
           try:
               command.invoke()
               return True
           except Exception as e:
               if attempt < max_retries - 1:
                   print(f"Attempt {attempt + 1} failed: {e}")
                   print(f"Retrying in {2 ** attempt} seconds...")
                   time.sleep(2 ** attempt)
               else:
                   print(f"All {max_retries} attempts failed")
                   raise

       return False
   ```

4. **Monitor file permissions and disk space**:
   ```python
   import shutil

   def check_system_requirements(output_path: pathlib.Path) -> bool:
       """Check system requirements before generation."""

       # Check disk space (minimum 10MB)
       free_space = shutil.disk_usage(output_path.parent).free
       if free_space < 10 * 1024 * 1024:
           print("Insufficient disk space (need at least 10MB)")
           return False

       # Check write permissions
       try:
           test_file = output_path.parent / ".test_write"
           test_file.touch()
           test_file.unlink()
       except (OSError, PermissionError):
           print(f"No write permission for directory: {output_path.parent}")
           return False

       return True
   ```

## Performance Notes

- Template generation is typically fast for standard schemas (< 1 second)
- Large schemas with many properties may take longer to process
- File I/O operations are optimized for typical Excel file sizes
- Memory usage scales with schema complexity and number of properties
- Network file systems may impact performance; use local storage when possible

## Integration with Other Modules

### Invoice File Integration

The module uses the ExcelInvoiceFile class for template generation:

```python
from rdetoolkit.invoicefile import ExcelInvoiceFile

# Used internally for actual Excel file generation
ExcelInvoiceFile.generate_template(schema_file, output_path, mode)
```

### Exception Handling Integration

Uses custom exceptions for better error reporting:

```python
from rdetoolkit.exceptions import InvoiceSchemaValidationError

# Provides specific error types for schema validation issues
```

### Logging Integration

Integrates with the RDE logging system:

```python
from rdetoolkit.rdelogger import get_logger

# Used for detailed error logging and debugging
logger = get_logger(__name__)
```

## See Also

- [Invoice File Module](invoicefile.md) - For Excel invoice file operations
- [Exceptions Module](exceptions.md) - For custom exception types
- [RDE Logger](rdelogger.md) - For logging functionality
- [Command Module](command.md) - For other command-line utilities
