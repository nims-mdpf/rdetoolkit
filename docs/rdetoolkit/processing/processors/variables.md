# Variable Processing Processor

The `rdetoolkit.processing.processors.variables` module provides a processor for applying magic variables to invoice files. This processor enables dynamic variable substitution in invoice files using data from raw files.

## Overview

The variable processor provides:

- **Magic Variable Substitution**: Replace placeholder variables in invoice files with actual values
- **Dynamic Content**: Generate dynamic content based on raw file data
- **Conditional Processing**: Apply variables only when enabled in configuration
- **File-Based Variables**: Extract variable values from raw files
- **Error Handling**: Comprehensive error handling for variable processing

## Classes

### VariableApplier

Applies magic variables to invoice files using data from raw files.

#### Constructor

```python
VariableApplier()
```

No parameters required. Inherits from `Processor` base class.

#### Methods

##### process(context)

Apply magic variables if enabled in configuration.

```python
def process(context: ProcessingContext) -> None
```

**Parameters:**
- `context` (ProcessingContext): Processing context containing configuration and file paths

**Returns:**
- `None`

**Raises:**
- `Exception`: If magic variable processing fails

**Example:**
```python
from rdetoolkit.processing.processors.variables import VariableApplier

applier = VariableApplier()
applier.process(context)  # Applies magic variables if enabled
```

**Required Context Attributes:**
- `context.srcpaths.config.system.magic_variable`: Boolean flag to enable/disable magic variables
- `context.invoice_dst_filepath`: Path to invoice file to process
- `context.resource_paths.rawfiles`: Tuple of raw file paths for variable extraction

**Processing Logic:**
1. Check if magic variables are enabled in configuration
2. Verify raw files are available for variable extraction
3. Apply magic variable replacement using the first raw file
4. Save updated invoice file with substituted variables

## Magic Variable System

### Variable Format

Magic variables in invoice files use the format:
```
${variable_name}
```

### Common Magic Variables

- `${filename}`: Original filename without extension
- `${filepath}`: Full path to the file
- `${filesize}`: File size in bytes
- `${timestamp}`: File modification timestamp
- `${index}`: Processing index
- `${date}`: Current date
- `${time}`: Current time

### Variable Substitution Process

1. **Invoice Loading**: Load invoice.json file
2. **Variable Detection**: Scan for magic variable patterns
3. **Value Extraction**: Extract values from raw files
4. **Substitution**: Replace variables with actual values
5. **Save**: Write updated invoice back to file

## Complete Usage Examples

### Basic Magic Variable Processing

```python
from rdetoolkit.processing.processors.variables import VariableApplier
from rdetoolkit.processing.context import ProcessingContext
from pathlib import Path

# Create variable applier
applier = VariableApplier()

# Create processing context with magic variables enabled
context = ProcessingContext(
    srcpaths=srcpaths,  # srcpaths.config.system.magic_variable = True
    invoice_dst_filepath=Path("output/invoice.json"),
    resource_paths=resource_paths,  # Contains rawfiles
    # ... other parameters
)

# Apply magic variables
try:
    applier.process(context)
    print("Magic variables applied successfully")
except Exception as e:
    print(f"Magic variable processing failed: {e}")
```

### Invoice Template with Magic Variables

```python
# Example invoice.json template with magic variables
invoice_template = {
    "basic": {
        "dataName": "${filename}",
        "description": "Data file: ${filepath}",
        "fileSize": "${filesize}",
        "createdDate": "${date}",
        "processedTime": "${time}"
    },
    "custom": {
        "originalFilename": "${filename}",
        "processingIndex": "${index}",
        "lastModified": "${timestamp}"
    },
    "sample": {
        "names": ["Sample from ${filename}"],
        "generalAttributes": [
            {
                "termId": "sourceFile",
                "value": "${filepath}"
            },
            {
                "termId": "fileSize",
                "value": "${filesize}"
            }
        ]
    }
}

# After processing, variables would be replaced with actual values:
processed_invoice = {
    "basic": {
        "dataName": "experiment_data",
        "description": "Data file: /data/raw/experiment_data.csv",
        "fileSize": "1024",
        "createdDate": "2024-01-01",
        "processedTime": "12:00:00"
    },
    "custom": {
        "originalFilename": "experiment_data",
        "processingIndex": "001",
        "lastModified": "2024-01-01T10:30:00"
    },
    "sample": {
        "names": ["Sample from experiment_data"],
        "generalAttributes": [
            {
                "termId": "sourceFile",
                "value": "/data/raw/experiment_data.csv"
            },
            {
                "termId": "fileSize",
                "value": "1024"
            }
        ]
    }
}
```

### Conditional Magic Variable Processing

```python
from rdetoolkit.processing.processors.variables import VariableApplier

def process_with_variable_check(context):
    """Process with magic variable configuration check."""

    # Check configuration
    if not context.srcpaths.config.system.magic_variable:
        print("Magic variables disabled, skipping processing")
        return

    # Check for raw files
    if not context.resource_paths.rawfiles:
        print("No raw files available for variable extraction")
        return

    # Apply magic variables
    applier = VariableApplier()
    try:
        applier.process(context)
        print("Magic variables processed successfully")
    except Exception as e:
        print(f"Magic variable processing failed: {e}")

# Usage
process_with_variable_check(context)
```

### Magic Variable Processing with Multiple Files

```python
from rdetoolkit.processing.processors.variables import VariableApplier
from pathlib import Path

def process_multiple_files(contexts):
    """Process magic variables for multiple files."""

    applier = VariableApplier()
    results = []

    for i, context in enumerate(contexts):
        try:
            print(f"Processing file {i+1}/{len(contexts)}")
            applier.process(context)
            results.append({
                "index": i,
                "status": "success",
                "file": str(context.invoice_dst_filepath)
            })
        except Exception as e:
            results.append({
                "index": i,
                "status": "failed",
                "file": str(context.invoice_dst_filepath),
                "error": str(e)
            })

    return results

# Create multiple contexts
contexts = [
    ProcessingContext(
        invoice_dst_filepath=Path(f"output/invoice_{i:03d}.json"),
        resource_paths=resource_paths,
        srcpaths=srcpaths
    )
    for i in range(10)
]

# Process all files
results = process_multiple_files(contexts)
print(f"Processed {len([r for r in results if r['status'] == 'success'])} files successfully")
```

### Custom Magic Variable Workflow

```python
from rdetoolkit.processing.processors.variables import VariableApplier
import json
from pathlib import Path

class MagicVariableWorkflow:
    """Custom workflow for magic variable processing."""

    def __init__(self, backup_dir: Path):
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def process_with_backup(self, context):
        """Process magic variables with backup creation."""

        # Create backup of original invoice
        backup_path = self._create_backup(context.invoice_dst_filepath)

        try:
            # Apply magic variables
            applier = VariableApplier()
            applier.process(context)

            print(f"Magic variables applied. Backup saved to: {backup_path}")
            return True

        except Exception as e:
            # Restore from backup on failure
            self._restore_backup(backup_path, context.invoice_dst_filepath)
            print(f"Magic variable processing failed, restored from backup: {e}")
            return False

    def _create_backup(self, invoice_path: Path) -> Path:
        """Create backup of invoice file."""
        if invoice_path.exists():
            backup_path = self.backup_dir / f"{invoice_path.stem}_backup.json"
            shutil.copy2(invoice_path, backup_path)
            return backup_path
        return None

    def _restore_backup(self, backup_path: Path, invoice_path: Path):
        """Restore invoice from backup."""
        if backup_path and backup_path.exists():
            shutil.copy2(backup_path, invoice_path)

# Usage
workflow = MagicVariableWorkflow(Path("backups"))
success = workflow.process_with_backup(context)
```

### Pre-Processing Variable Validation

```python
from rdetoolkit.processing.processors.variables import VariableApplier
import json
import re

def validate_magic_variables(invoice_path: Path, available_variables: set):
    """Validate magic variables in invoice before processing."""

    # Load invoice
    with open(invoice_path) as f:
        invoice_data = json.load(f)

    # Convert to string for pattern matching
    invoice_str = json.dumps(invoice_data)

    # Find all magic variables
    pattern = r'\$\{([^}]+)\}'
    found_variables = set(re.findall(pattern, invoice_str))

    # Check for undefined variables
    undefined_variables = found_variables - available_variables

    if undefined_variables:
        raise ValueError(f"Undefined magic variables: {undefined_variables}")

    return found_variables

# Define available variables
available_vars = {
    'filename', 'filepath', 'filesize', 'timestamp',
    'index', 'date', 'time'
}

# Validate before processing
try:
    used_vars = validate_magic_variables(context.invoice_dst_filepath, available_vars)
    print(f"Found valid magic variables: {used_vars}")

    # Process magic variables
    applier = VariableApplier()
    applier.process(context)

except ValueError as e:
    print(f"Validation failed: {e}")
```

## Integration with Processing Pipeline

### Pipeline Integration

```python
from rdetoolkit.processing.pipeline import ProcessingPipeline
from rdetoolkit.processing.processors.variables import VariableApplier

# Create processing pipeline
pipeline = ProcessingPipeline()

# Add processors in order
# pipeline.add_processor(InvoiceInitializer())
# pipeline.add_processor(FileProcessor())

# Add variable applier after invoice creation
pipeline.add_processor(VariableApplier())

# Add validation processors after variable processing
# pipeline.add_processor(InvoiceValidator())

# Execute pipeline
pipeline.process(context)
```

### Conditional Pipeline Processing

```python
from rdetoolkit.processing.processors.variables import VariableApplier

def create_conditional_pipeline(config):
    """Create pipeline with conditional magic variable processing."""

    pipeline = ProcessingPipeline()

    # Add standard processors
    pipeline.add_processor(StandardProcessor())

    # Add variable applier only if enabled
    if config.system.magic_variable:
        pipeline.add_processor(VariableApplier())

    # Add validation
    pipeline.add_processor(ValidationProcessor())

    return pipeline

# Usage
pipeline = create_conditional_pipeline(config)
pipeline.process(context)
```

## Error Handling

### Common Exceptions

#### Configuration Errors
```python
try:
    applier.process(context)
except AttributeError as e:
    print(f"Configuration error: {e}")
    # Handle missing configuration attributes
```

#### File Processing Errors
```python
try:
    applier.process(context)
except FileNotFoundError as e:
    print(f"File not found: {e}")
    # Handle missing invoice or raw files
```

#### Variable Processing Errors
```python
try:
    applier.process(context)
except Exception as e:
    print(f"Variable processing error: {e}")
    # Handle variable substitution failures
```

### Best Practices

1. **Always check configuration** before processing:
   ```python
   if context.srcpaths.config.system.magic_variable:
       applier.process(context)
   else:
       logger.debug("Magic variables disabled")
   ```

2. **Verify raw files exist**:
   ```python
   if context.resource_paths.rawfiles:
       applier.process(context)
   else:
       logger.warning("No raw files available for variable extraction")
   ```

3. **Handle processing failures gracefully**:
   ```python
   try:
       applier.process(context)
   except Exception as e:
       logger.error(f"Magic variable processing failed: {e}")
       # Decide whether to continue or abort processing
   ```

4. **Log variable processing results**:
   ```python
   logger.debug("Starting magic variable processing")
   try:
       result = apply_magic_variable(
           context.invoice_dst_filepath,
           context.resource_paths.rawfiles[0],
           save_filepath=context.invoice_dst_filepath
       )
       if result:
           logger.info("Magic variables applied successfully")
       else:
           logger.info("No magic variables found for replacement")
   except Exception as e:
       logger.error(f"Magic variable processing failed: {e}")
   ```

## Configuration Dependencies

### System Configuration

Magic variable processing depends on system configuration:

```yaml
system:
  magic_variable: true  # Enable magic variable processing
```

### Required Files

- **Invoice File**: Must exist at `context.invoice_dst_filepath`
- **Raw Files**: At least one file in `context.resource_paths.rawfiles`
- **Configuration**: Valid system configuration with magic_variable setting

## Performance Notes

- Magic variable processing is performed in-memory for optimal performance
- File I/O operations are minimized by processing all variables in one pass
- Variable substitution uses efficient string replacement algorithms
- Logging is optimized to minimize performance impact on processing
- The processor gracefully skips processing when disabled, adding minimal overhead

## Use Cases

### Common Use Cases

1. **Dynamic File Naming**: Include original filenames in processed data
2. **Metadata Enrichment**: Add file metadata to invoice data
3. **Audit Trails**: Include processing timestamps and file information
4. **Data Lineage**: Track source files in processed data
5. **Custom Identifiers**: Generate unique identifiers based on file properties

### Example Use Cases

```python
# Dynamic naming example
invoice_template = {
    "basic": {
        "dataName": "processed_${filename}",
        "description": "Processed data from ${filename} on ${date}"
    }
}

# Metadata enrichment example
invoice_template = {
    "custom": {
        "sourceFile": "${filepath}",
        "originalSize": "${filesize}",
        "processedTimestamp": "${timestamp}"
    }
}
```

## See Also

- [Processing Context](../context.md) - For understanding processing context structure
- [Pipeline Documentation](../pipeline.md) - For processor pipeline integration
- [Invoice File Operations](../../invoicefile.md) - For invoice file utilities
- [Configuration Guide](../../config.md) - For system configuration options
