# Invoice Processors

The invoice processors handle invoice initialization for different processing modes including standard, Excel-based, and SmartTable-based invoice creation.

## Classes

### StandardInvoiceInitializer

Handles invoice initialization for RDEFormat, MultiFile, and Invoice modes by copying the original invoice to the destination.

```python
class StandardInvoiceInitializer(Processor):
    """Standard invoice initializer for RDEFormat, MultiFile, and Invoice modes."""
```

#### Methods

##### process

Execute standard invoice initialization by copying the original invoice.

```python
def process(self, context: ProcessingContext) -> None
```

**Parameters:**
- `context` (ProcessingContext): Processing context containing invoice paths

**Behavior:**
- Copies invoice from `invoice_org` to destination `invoice.json`
- Creates destination directory if it doesn't exist
- Handles file copying errors gracefully

**Example:**
```python
from rdetoolkit.processing.processors import StandardInvoiceInitializer

initializer = StandardInvoiceInitializer()
initializer.process(context)
```

### ExcelInvoiceInitializer

Handles invoice initialization for ExcelInvoice mode by creating invoice from Excel file data.

```python
class ExcelInvoiceInitializer(Processor):
    """Invoice initializer for ExcelInvoice mode."""
```

#### Methods

##### process

Execute Excel invoice initialization by parsing Excel data and creating invoice.

```python
def process(self, context: ProcessingContext) -> None
```

**Parameters:**
- `context` (ProcessingContext): Processing context with Excel file information

**Raises:**
- `ValueError`: If context is not configured for Excel mode or if Excel index is invalid

**Behavior:**
- Validates context is in Excel mode
- Parses Excel index from context
- Creates invoice using Excel invoice processing functions
- Handles Excel processing errors

**Example:**
```python
from rdetoolkit.processing.processors import ExcelInvoiceInitializer

# Context must be configured for Excel mode
excel_initializer = ExcelInvoiceInitializer()
excel_initializer.process(context)  # context.is_excel_mode must be True
```

### SmartTableInvoiceInitializer

Handles invoice initialization for SmartTable mode by generating invoice from CSV data with complex field mapping.

```python
class SmartTableInvoiceInitializer(Processor):
    """Invoice initializer for SmartTable mode."""
```

#### Methods

##### process

Execute SmartTable invoice initialization by parsing CSV data and creating invoice.

```python
def process(self, context: ProcessingContext) -> None
```

**Parameters:**
- `context` (ProcessingContext): Processing context with SmartTable file information

**Raises:**
- `ValueError`: If context is not configured for SmartTable mode
- `FileNotFoundError`: If SmartTable CSV file is not found
- `Exception`: If CSV parsing or invoice creation fails

**Behavior:**
- Validates context is in SmartTable mode
- Reads and parses SmartTable CSV file
- Maps CSV columns to invoice structure using complex field mapping
- Processes general and specific attributes
- Ensures required invoice fields are present
- Creates final invoice JSON file

**Field Mapping:**
- Supports nested field mapping (e.g., `"basic.dataName"`)
- Handles array fields and complex data structures
- Provides fallback values for missing fields

**Example:**
```python
from rdetoolkit.processing.processors import SmartTableInvoiceInitializer

# Context must be configured for SmartTable mode
smarttable_initializer = SmartTableInvoiceInitializer()
smarttable_initializer.process(context)  # context.is_smarttable_mode must be True
```

### InvoiceInitializerFactory

Factory class for creating appropriate invoice initializers based on processing mode.

```python
class InvoiceInitializerFactory:
    """Factory for creating invoice initializers based on mode."""
```

#### Class Methods

##### create

Create an appropriate invoice initializer for the specified mode.

```python
@classmethod
def create(cls, mode: str) -> Processor
```

**Parameters:**
- `mode` (str): Processing mode name

**Returns:**
- `Processor`: Appropriate invoice initializer for the mode

**Raises:**
- `ValueError`: If mode is not supported

**Supported Modes:**
- `"rdeformat"`: Returns `StandardInvoiceInitializer`
- `"multidatatile"`: Returns `StandardInvoiceInitializer`
- `"invoice"`: Returns `StandardInvoiceInitializer`
- `"excelinvoice"`: Returns `ExcelInvoiceInitializer`
- `"smarttableinvoice"`: Returns `SmartTableInvoiceInitializer`

**Example:**
```python
from rdetoolkit.processing.processors import InvoiceInitializerFactory

# Create initializer for specific mode
initializer = InvoiceInitializerFactory.create("excelinvoice")
initializer.process(context)

# Dynamic mode selection
mode = context.mode_name.lower()
initializer = InvoiceInitializerFactory.create(mode)
initializer.process(context)
```

##### get_supported_modes

Get list of supported processing modes.

```python
@classmethod
def get_supported_modes(cls) -> list[str]
```

**Returns:**
- `list[str]`: List of supported mode names

**Example:**
```python
modes = InvoiceInitializerFactory.get_supported_modes()
print(f"Supported modes: {', '.join(modes)}")
```

## Usage Examples

### Basic Invoice Initialization

```python
from rdetoolkit.processing.processors import StandardInvoiceInitializer

# Standard invoice processing
standard_init = StandardInvoiceInitializer()
standard_init.process(context)

# Check if invoice was created
if context.invoice_dst_filepath.exists():
    print(f"Invoice created at: {context.invoice_dst_filepath}")
```

### Mode-Based Invoice Initialization

```python
from rdetoolkit.processing.processors import InvoiceInitializerFactory

def initialize_invoice_by_mode(context: ProcessingContext):
    """Initialize invoice using appropriate initializer for the mode."""

    try:
        # Create appropriate initializer
        initializer = InvoiceInitializerFactory.create(context.mode_name.lower())

        print(f"Using {initializer.get_name()} for {context.mode_name} mode")

        # Execute initialization
        initializer.process(context)

        print(f"Invoice initialized successfully")

    except ValueError as e:
        print(f"Unsupported mode: {e}")
    except Exception as e:
        print(f"Invoice initialization failed: {e}")
        raise

# Usage
initialize_invoice_by_mode(context)
```

### Excel Invoice Processing

```python
from rdetoolkit.processing.processors import ExcelInvoiceInitializer
from rdetoolkit.processing.context import ProcessingContext

def process_excel_invoice(context: ProcessingContext):
    """Process Excel invoice with validation."""

    # Validate context for Excel processing
    if not context.is_excel_mode:
        raise ValueError("Context not configured for Excel mode")

    # Check Excel file exists
    excel_file = context.excel_invoice_file
    if not excel_file.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_file}")

    # Initialize Excel invoice
    excel_init = ExcelInvoiceInitializer()
    excel_init.process(context)

    print(f"Excel invoice processed from: {excel_file}")

# Usage with Excel context
excel_context = ProcessingContext(
    index="1",
    srcpaths=srcpaths,
    resource_paths=resource_paths,
    datasets_function=None,
    mode_name="ExcelInvoice",
    excel_file=Path("data/inputdata/dataset_excel_invoice.xlsx"),
    excel_index=1
)

process_excel_invoice(excel_context)
```

### SmartTable Invoice Processing

```python
from rdetoolkit.processing.processors import SmartTableInvoiceInitializer
from rdetoolkit.processing.context import ProcessingContext

def process_smarttable_invoice(context: ProcessingContext):
    """Process SmartTable invoice with validation."""

    # Validate context for SmartTable processing
    if not context.is_smarttable_mode:
        raise ValueError("Context not configured for SmartTable mode")

    # Check SmartTable file exists
    smarttable_file = context.smarttable_invoice_file
    if not smarttable_file.exists():
        raise FileNotFoundError(f"SmartTable file not found: {smarttable_file}")

    # Initialize SmartTable invoice
    smarttable_init = SmartTableInvoiceInitializer()
    smarttable_init.process(context)

    print(f"SmartTable invoice processed from: {smarttable_file}")

# Usage with SmartTable context
smarttable_context = ProcessingContext(
    index="1",
    srcpaths=srcpaths,
    resource_paths=resource_paths,
    datasets_function=None,
    mode_name="SmartTableInvoice",
    smarttable_file=Path("data/inputdata/smarttable_data.csv")
)

process_smarttable_invoice(smarttable_context)
```

### Custom Invoice Initializer

```python
from rdetoolkit.processing.processors import StandardInvoiceInitializer
import json
from datetime import datetime

class TimestampedInvoiceInitializer(StandardInvoiceInitializer):
    """Invoice initializer that adds timestamp to invoice data."""

    def process(self, context: ProcessingContext) -> None:
        # First, copy the original invoice
        super().process(context)

        # Then add timestamp
        self._add_timestamp(context)

    def _add_timestamp(self, context: ProcessingContext):
        """Add processing timestamp to invoice."""
        invoice_file = context.invoice_dst_filepath

        if not invoice_file.exists():
            return

        try:
            # Read existing invoice
            with open(invoice_file, 'r', encoding='utf-8') as f:
                invoice_data = json.load(f)

            # Add timestamp
            if 'processing' not in invoice_data:
                invoice_data['processing'] = {}

            invoice_data['processing']['timestamp'] = datetime.now().isoformat()
            invoice_data['processing']['mode'] = context.mode_name

            # Write back
            with open(invoice_file, 'w', encoding='utf-8') as f:
                json.dump(invoice_data, f, indent=2, ensure_ascii=False)

            print(f"Added timestamp to invoice: {invoice_file}")

        except Exception as e:
            print(f"Warning: Could not add timestamp to invoice: {e}")

# Usage
timestamped_init = TimestampedInvoiceInitializer()
timestamped_init.process(context)
```

### Parallel Invoice Processing

```python
from rdetoolkit.processing.processors import InvoiceInitializerFactory
import concurrent.futures

def process_multiple_invoices(contexts: list[ProcessingContext]):
    """Process multiple invoices in parallel."""

    def process_single_invoice(context):
        try:
            initializer = InvoiceInitializerFactory.create(context.mode_name.lower())
            initializer.process(context)
            return context.index, "success", None
        except Exception as e:
            return context.index, "failed", str(e)

    # Process invoices in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(process_single_invoice, ctx) for ctx in contexts]

        results = []
        for future in concurrent.futures.as_completed(futures):
            index, status, error = future.result()
            results.append((index, status, error))

            if status == "success":
                print(f"✓ Invoice {index} processed successfully")
            else:
                print(f"✗ Invoice {index} failed: {error}")

    # Summary
    successful = sum(1 for _, status, _ in results if status == "success")
    failed = len(results) - successful
    print(f"Processing complete: {successful} successful, {failed} failed")

    return results

# Usage
contexts = [context1, context2, context3]  # List of processing contexts
results = process_multiple_invoices(contexts)
```

## Error Handling

### Mode Validation

```python
from rdetoolkit.processing.processors import InvoiceInitializerFactory

def safe_invoice_initialization(context: ProcessingContext):
    """Safely initialize invoice with comprehensive error handling."""

    try:
        # Validate mode
        supported_modes = InvoiceInitializerFactory.get_supported_modes()
        mode = context.mode_name.lower()

        if mode not in supported_modes:
            raise ValueError(f"Unsupported mode: {mode}. Supported: {supported_modes}")

        # Validate context configuration
        if mode == "excelinvoice" and not context.is_excel_mode:
            raise ValueError("Context not properly configured for Excel mode")

        if mode == "smarttableinvoice" and not context.is_smarttable_mode:
            raise ValueError("Context not properly configured for SmartTable mode")

        # Create and execute initializer
        initializer = InvoiceInitializerFactory.create(mode)
        initializer.process(context)

        # Validate result
        if not context.invoice_dst_filepath.exists():
            raise RuntimeError("Invoice file was not created")

        print(f"✓ Invoice initialization successful for {mode} mode")
        return True

    except ValueError as e:
        print(f"✗ Configuration error: {e}")
        return False
    except FileNotFoundError as e:
        print(f"✗ File not found: {e}")
        return False
    except RuntimeError as e:
        print(f"✗ Processing error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

# Usage
success = safe_invoice_initialization(context)
```

### Excel Processing Errors

```python
from rdetoolkit.processing.processors import ExcelInvoiceInitializer

class RobustExcelInvoiceInitializer(ExcelInvoiceInitializer):
    """Excel invoice initializer with enhanced error handling."""

    def process(self, context: ProcessingContext) -> None:
        try:
            # Validate Excel context
            self._validate_excel_context(context)

            # Validate Excel file
            self._validate_excel_file(context)

            # Process Excel invoice
            super().process(context)

        except ValueError as e:
            print(f"Excel validation error: {e}")
            raise
        except FileNotFoundError as e:
            print(f"Excel file error: {e}")
            raise
        except Exception as e:
            print(f"Excel processing error: {e}")
            # Try to create a minimal invoice as fallback
            self._create_fallback_invoice(context)

    def _validate_excel_context(self, context: ProcessingContext):
        """Validate context for Excel processing."""
        if not context.is_excel_mode:
            raise ValueError("Context not configured for Excel mode")

        if context.excel_index is None:
            raise ValueError("Excel index not set")

    def _validate_excel_file(self, context: ProcessingContext):
        """Validate Excel file exists and is readable."""
        excel_file = context.excel_invoice_file

        if not excel_file.exists():
            raise FileNotFoundError(f"Excel file not found: {excel_file}")

        if not excel_file.is_file():
            raise ValueError(f"Excel path is not a file: {excel_file}")

        # Check file extension
        if excel_file.suffix.lower() not in ['.xlsx', '.xls']:
            raise ValueError(f"Invalid Excel file extension: {excel_file.suffix}")

    def _create_fallback_invoice(self, context: ProcessingContext):
        """Create minimal invoice as fallback."""
        fallback_data = {
            "basic": {
                "dataName": f"Fallback Invoice {context.index}",
                "experimentDate": datetime.now().strftime("%Y-%m-%d"),
            },
            "custom": {},
            "processing": {
                "mode": "excelinvoice_fallback",
                "error": "Failed to process Excel file, using fallback"
            }
        }

        # Write fallback invoice
        invoice_file = context.invoice_dst_filepath
        invoice_file.parent.mkdir(parents=True, exist_ok=True)

        with open(invoice_file, 'w', encoding='utf-8') as f:
            json.dump(fallback_data, f, indent=2, ensure_ascii=False)

        print(f"Created fallback invoice: {invoice_file}")

# Usage
robust_excel_init = RobustExcelInvoiceInitializer()
robust_excel_init.process(context)
```

## SmartTable Field Mapping

### Custom Field Mapping

```python
from rdetoolkit.processing.processors import SmartTableInvoiceInitializer
import json

class CustomSmartTableInitializer(SmartTableInvoiceInitializer):
    """SmartTable initializer with custom field mapping."""

    def __init__(self, custom_mapping=None):
        self.custom_mapping = custom_mapping or {}

    def _process_mapping_key(self, row_data, mapping_key, invoice_data):
        """Process mapping with custom rules."""

        # Check for custom mapping first
        if mapping_key in self.custom_mapping:
            custom_processor = self.custom_mapping[mapping_key]
            return custom_processor(row_data, invoice_data)

        # Fall back to default processing
        return super()._process_mapping_key(row_data, mapping_key, invoice_data)

# Define custom field processors
def process_temperature_field(row_data, invoice_data):
    """Custom processor for temperature fields."""
    temp_celsius = row_data.get('temperature_c')
    if temp_celsius:
        # Convert to Kelvin and store both
        temp_kelvin = float(temp_celsius) + 273.15
        return {
            'temperature': {
                'celsius': float(temp_celsius),
                'kelvin': temp_kelvin,
                'unit': 'C'
            }
        }
    return {}

def process_sample_info(row_data, invoice_data):
    """Custom processor for sample information."""
    return {
        'sample': {
            'id': row_data.get('sample_id', ''),
            'name': row_data.get('sample_name', ''),
            'batch': row_data.get('batch_number', ''),
            'prepared_date': row_data.get('prep_date', '')
        }
    }

# Usage with custom mapping
custom_mapping = {
    'temperature': process_temperature_field,
    'sample_info': process_sample_info,
}

custom_init = CustomSmartTableInitializer(custom_mapping)
custom_init.process(context)
```

## Performance Considerations

- **Large Excel Files**: Consider memory usage when processing large Excel files
- **CSV Parsing**: Use efficient CSV parsing for large SmartTable files
- **File I/O**: Minimize file read/write operations
- **Error Recovery**: Implement fallback strategies for critical processing
- **Validation**: Validate data early to prevent downstream errors

## See Also

- [Processing Context](../context.md) - Context management and mode configuration
- [Pipeline Architecture](../pipeline.md) - Core pipeline classes
- [File Processors](files.md) - File copying and management
- [Validation Processors](validation.md) - Invoice and metadata validation
