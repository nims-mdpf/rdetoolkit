# Exceptions Module

The `rdetoolkit.exceptions` module provides a comprehensive set of custom exception classes for RDE (Research Data Exchange) processing workflows. These exceptions enable precise error handling, detailed error reporting, and structured error management across all RDE operations.

## Overview

The exceptions module offers specialized exception types for different RDE components and operations:

- **Structured Error Handling**: Base exception with detailed error information including codes and context
- **Mode-Specific Exceptions**: Specialized exceptions for different processing modes (Invoice, Excel, MultiDataTile, RDE Format)
- **Validation Exceptions**: Dedicated exceptions for schema and metadata validation errors
- **Data Retrieval Exceptions**: Specialized exceptions for data access and search operations
- **Enhanced Error Context**: Support for error codes, additional objects, and traceback information
- **Consistent Error Messaging**: Standardized error message formatting across all exception types

## Exception Classes

### StructuredError

A comprehensive base exception class providing structured error information with detailed context.

#### Constructor

```python
StructuredError(
    emsg: str = "",
    ecode: int = 1,
    eobj: Any | None = None,
    traceback_info: str | None = None
) -> None
```

**Parameters:**
- `emsg` (str): The error message describing what went wrong
- `ecode` (int): Numeric error code for programmatic error identification (default: 1)
- `eobj` (Any | None): Additional error object providing context (optional)
- `traceback_info` (str | None): Additional traceback information (optional)

**Attributes:**
- `emsg` (str): The error message
- `ecode` (int): The error code
- `eobj` (Any | None): Additional error object
- `traceback_info` (str | None): Traceback information

**Use Cases:**
- General RDE processing errors
- File operation failures
- Configuration errors
- Data processing failures
- Base class for more specific exceptions

**Example:**

```python
from rdetoolkit.exceptions import StructuredError
import traceback

# Basic usage
try:
    # Some operation that might fail
    if not file_exists:
        raise StructuredError("Required file not found", ecode=404)
except StructuredError as e:
    print(f"Error {e.ecode}: {e.emsg}")

# Enhanced usage with context object
def process_data_file(file_path: str, config: dict) -> dict:
    """Process data file with structured error handling."""
    try:
        # Validate file
        if not Path(file_path).exists():
            raise StructuredError(
                emsg=f"Data file not found: {file_path}",
                ecode=404,
                eobj={"file_path": file_path, "config": config}
            )

        # Validate configuration
        required_keys = ["input_format", "output_format", "validation_rules"]
        missing_keys = [key for key in required_keys if key not in config]
        if missing_keys:
            raise StructuredError(
                emsg=f"Missing required configuration keys: {missing_keys}",
                ecode=400,
                eobj={"missing_keys": missing_keys, "provided_config": config}
            )

        # Process file (example)
        return {"status": "success", "processed_file": file_path}

    except Exception as e:
        # Wrap unexpected errors
        raise StructuredError(
            emsg=f"Unexpected error during file processing: {str(e)}",
            ecode=500,
            eobj={"original_exception": e, "file_path": file_path},
            traceback_info=traceback.format_exc()
        ) from e

# Usage with comprehensive error handling
def robust_file_processor():
    """Demonstrate robust file processing with StructuredError."""

    files_to_process = [
        ("data/valid_file.json", {"input_format": "json", "output_format": "csv", "validation_rules": ["schema"]}),
        ("data/missing_file.json", {"input_format": "json", "output_format": "csv"}),
        ("data/another_file.json", {"input_format": "json", "output_format": "csv", "validation_rules": ["schema"]})
    ]

    results = []

    for file_path, config in files_to_process:
        try:
            result = process_data_file(file_path, config)
            results.append({"file": file_path, "status": "success", "result": result})
            print(f"✓ Successfully processed: {file_path}")

        except StructuredError as e:
            error_info = {
                "file": file_path,
                "status": "error",
                "error_code": e.ecode,
                "error_message": e.emsg,
                "error_context": e.eobj
            }
            results.append(error_info)

            print(f"✗ Error processing {file_path}:")
            print(f"  Code: {e.ecode}")
            print(f"  Message: {e.emsg}")
            if e.eobj:
                print(f"  Context: {e.eobj}")
            if e.traceback_info:
                print(f"  Traceback: {e.traceback_info}")

    return results

# Advanced error context usage
class DataProcessor:
    """Example class demonstrating StructuredError usage."""

    def __init__(self, processor_id: str):
        self.processor_id = processor_id
        self.processed_count = 0
        self.error_count = 0

    def process_item(self, item: dict) -> dict:
        """Process a single item with detailed error context."""
        try:
            # Validate item structure
            required_fields = ["id", "type", "data"]
            for field in required_fields:
                if field not in item:
                    raise StructuredError(
                        emsg=f"Missing required field: {field}",
                        ecode=400,
                        eobj={
                            "processor_id": self.processor_id,
                            "item": item,
                            "required_fields": required_fields,
                            "processed_count": self.processed_count
                        }
                    )

            # Process based on type
            if item["type"] == "numeric":
                result = self._process_numeric(item["data"])
            elif item["type"] == "text":
                result = self._process_text(item["data"])
            else:
                raise StructuredError(
                    emsg=f"Unknown item type: {item['type']}",
                    ecode=422,
                    eobj={
                        "processor_id": self.processor_id,
                        "item_id": item.get("id"),
                        "unknown_type": item["type"],
                        "supported_types": ["numeric", "text"]
                    }
                )

            self.processed_count += 1
            return {"id": item["id"], "status": "processed", "result": result}

        except StructuredError:
            self.error_count += 1
            raise
        except Exception as e:
            self.error_count += 1
            raise StructuredError(
                emsg=f"Unexpected processing error: {str(e)}",
                ecode=500,
                eobj={
                    "processor_id": self.processor_id,
                    "item": item,
                    "original_exception": str(e),
                    "processed_count": self.processed_count,
                    "error_count": self.error_count
                }
            ) from e

    def _process_numeric(self, data: any) -> float:
        """Process numeric data."""
        try:
            return float(data) * 2  # Example processing
        except (ValueError, TypeError) as e:
            raise StructuredError(
                emsg=f"Invalid numeric data: {data}",
                ecode=422,
                eobj={"data": data, "data_type": type(data).__name__}
            ) from e

    def _process_text(self, data: any) -> str:
        """Process text data."""
        try:
            return str(data).upper()  # Example processing
        except Exception as e:
            raise StructuredError(
                emsg=f"Text processing failed: {str(e)}",
                ecode=422,
                eobj={"data": data, "data_type": type(data).__name__}
            ) from e

# Usage example
processor = DataProcessor("PROC_001")
test_items = [
    {"id": "1", "type": "numeric", "data": "42.5"},
    {"id": "2", "type": "text", "data": "hello world"},
    {"id": "3", "type": "unknown", "data": "test"},  # Will cause error
    {"id": "4", "data": "missing type"},  # Will cause error
    {"id": "5", "type": "numeric", "data": "invalid"}  # Will cause error
]

for item in test_items:
    try:
        result = processor.process_item(item)
        print(f"✓ {result}")
    except StructuredError as e:
        print(f"✗ Item {item.get('id', 'unknown')}: {e.emsg} (Code: {e.ecode})")
```

### Mode-Specific Exception Classes

#### InvoiceModeError

Exception for errors in standard invoice processing mode.

```python
InvoiceModeError(
    emsg: str = "",
    ecode: int = 100,
    eobj: Any | None = None,
    traceback_info: str | None = None
) -> None
```

**Default Error Code:** 100

**Example:**

```python
from rdetoolkit.exceptions import InvoiceModeError

def process_invoice_file(invoice_path: str) -> dict:
    """Process invoice file with mode-specific error handling."""
    try:
        # Invoice processing logic
        if not invoice_path.endswith('.json'):
            raise InvoiceModeError(
                emsg="Invalid invoice file format. Expected .json file.",
                ecode=101,
                eobj={"file_path": invoice_path, "expected_format": ".json"}
            )

        # More processing...
        return {"status": "processed"}

    except Exception as e:
        raise InvoiceModeError(
            emsg=f"Invoice processing failed: {str(e)}",
            ecode=102,
            eobj={"file_path": invoice_path, "original_error": str(e)}
        ) from e
```

#### ExcelInvoiceModeError

Exception for errors in Excel invoice processing mode.

```python
ExcelInvoiceModeError(
    emsg: str = "",
    ecode: int = 101,
    eobj: Any | None = None,
    traceback_info: str | None = None
) -> None
```

**Default Error Code:** 101

**Example:**

```python
from rdetoolkit.exceptions import ExcelInvoiceModeError

def process_excel_invoice(excel_path: str) -> dict:
    """Process Excel invoice with specific error handling."""
    try:
        if not excel_path.endswith(('.xlsx', '.xls')):
            raise ExcelInvoiceModeError(
                emsg="Invalid Excel file format",
                ecode=111,
                eobj={"file_path": excel_path, "supported_formats": [".xlsx", ".xls"]}
            )

        # Excel processing logic...
        return {"status": "processed"}

    except Exception as e:
        raise ExcelInvoiceModeError(
            emsg=f"Excel invoice processing failed: {str(e)}",
            ecode=112,
            eobj={"file_path": excel_path}
        ) from e
```

#### MultiDataTileModeError

Exception for errors in multi-data tile processing mode.

```python
MultiDataTileModeError(
    emsg: str = "",
    ecode: int = 102,
    eobj: Any | None = None,
    traceback_info: str | None = None
) -> None
```

**Default Error Code:** 102

**Example:**

```python
from rdetoolkit.exceptions import MultiDataTileModeError

def process_multi_data_tiles(tile_configs: list) -> dict:
    """Process multiple data tiles with error handling."""
    try:
        if not tile_configs:
            raise MultiDataTileModeError(
                emsg="No data tile configurations provided",
                ecode=121,
                eobj={"provided_configs": tile_configs}
            )

        # Multi-tile processing logic...
        return {"tiles_processed": len(tile_configs)}

    except Exception as e:
        raise MultiDataTileModeError(
            emsg=f"Multi-data tile processing failed: {str(e)}",
            ecode=122,
            eobj={"tile_count": len(tile_configs) if tile_configs else 0}
        ) from e
```

#### RdeFormatModeError

Exception for errors in RDE format processing mode.

```python
RdeFormatModeError(
    emsg: str = "",
    ecode: int = 103,
    eobj: Any | None = None,
    traceback_info: str | None = None
) -> None
```

**Default Error Code:** 103

**Example:**

```python
from rdetoolkit.exceptions import RdeFormatModeError

def process_rde_format(format_spec: dict) -> dict:
    """Process RDE format with specific error handling."""
    try:
        required_fields = ["version", "schema", "data"]
        missing_fields = [field for field in required_fields if field not in format_spec]

        if missing_fields:
            raise RdeFormatModeError(
                emsg=f"Missing required RDE format fields: {missing_fields}",
                ecode=131,
                eobj={"missing_fields": missing_fields, "provided_spec": format_spec}
            )

        # RDE format processing logic...
        return {"status": "processed"}

    except Exception as e:
        raise RdeFormatModeError(
            emsg=f"RDE format processing failed: {str(e)}",
            ecode=132,
            eobj={"format_spec": format_spec}
        ) from e
```

### Validation Exception Classes

#### InvoiceSchemaValidationError

Exception for invoice schema validation failures.

```python
InvoiceSchemaValidationError(message: str = "Validation error") -> None
```

**Example:**

```python
from rdetoolkit.exceptions import InvoiceSchemaValidationError

def validate_invoice_schema(invoice_data: dict, schema: dict) -> bool:
    """Validate invoice against schema."""
    try:
        # Schema validation logic
        if "basic" not in invoice_data:
            raise InvoiceSchemaValidationError(
                "Missing required 'basic' section in invoice"
            )

        if "title" not in invoice_data["basic"]:
            raise InvoiceSchemaValidationError(
                "Missing required field 'title' in basic section"
            )

        return True

    except Exception as e:
        raise InvoiceSchemaValidationError(
            f"Schema validation failed: {str(e)}"
        ) from e
```

#### MetadataValidationError

Exception for metadata validation failures.

```python
MetadataValidationError(message: str = "Validation error") -> None
```

**Example:**

```python
from rdetoolkit.exceptions import MetadataValidationError

def validate_metadata(metadata: dict) -> bool:
    """Validate metadata structure."""
    try:
        required_sections = ["constant", "variable"]
        for section in required_sections:
            if section not in metadata:
                raise MetadataValidationError(
                    f"Missing required metadata section: {section}"
                )

        return True

    except Exception as e:
        raise MetadataValidationError(
            f"Metadata validation failed: {str(e)}"
        ) from e
```

### Data Retrieval Exception Classes

#### DataRetrievalError

Exception for data access and retrieval failures.

```python
DataRetrievalError(message: str = "Data retrieval error") -> None
```

#### NoResultsFoundError

Exception when search operations return no results.

```python
NoResultsFoundError(message: str = "No results found") -> None
```

#### InvalidSearchParametersError

Exception for invalid search parameters or terms.

```python
InvalidSearchParametersError(message: str = "Invalid search term") -> None
```

**Example:**

```python
from rdetoolkit.exceptions import (
    DataRetrievalError,
    NoResultsFoundError,
    InvalidSearchParametersError
)

def search_data(query: str, filters: dict) -> list:
    """Search data with comprehensive error handling."""

    # Validate search parameters
    if not query or len(query.strip()) < 2:
        raise InvalidSearchParametersError(
            f"Search query too short: '{query}'. Minimum 2 characters required."
        )

    try:
        # Simulate data retrieval
        results = []  # Would contain actual search results

        if not results:
            raise NoResultsFoundError(
                f"No results found for query: '{query}' with filters: {filters}"
            )

        return results

    except Exception as e:
        raise DataRetrievalError(
            f"Failed to retrieve data for query '{query}': {str(e)}"
        ) from e
```

## See Also

- [Core Module](core.md) - For core functionality that may raise these exceptions
- [Validation](validation.md) - For validation functions that raise validation exceptions
- [Workflows](workflows.md) - For workflow processing that uses structured error handling
- [File Operations](fileops.md) - For file operations that may raise StructuredError
- [Invoice File](invoicefile.md) - For invoice processing that uses mode-specific exceptions
- [RDE Logger](rdelogger.md) - For logging integration with exception handling
- [Usage - Error Handling](../usage/structured_process/errorhandling.md) - For practical error handling examples
