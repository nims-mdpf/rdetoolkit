# API Reference

## Purpose

This section provides technical specifications for all features of RDEToolKit. It is a comprehensive reference including detailed functionality, parameters, return values, and usage examples for each module.

## API Documentation Structure

RDEToolKit's API documentation is structured using a hybrid approach:

- **Auto-generated parts**: Detailed technical specifications generated from docstrings in source code
- **Manually created parts**: Practical usage examples and inter-module collaboration methods

## Core Modules

### Workflow Management

- [workflows](../rdetoolkit/workflows.md) - Structured processing execution and workflow management
- [modeproc](../rdetoolkit/modeproc.md) - Mode processing

### Configuration and File Operations

- [config](../rdetoolkit/config.md) - Configuration file loading and management
- [fileops](../rdetoolkit/fileops.md) - RDE-related file operations

### Data Processing

- [invoicefile](../rdetoolkit/invoicefile.md) - Invoice file processing
- [validation](../rdetoolkit/validation.md) - Data validation
- [rde2util](../rdetoolkit/rde2util.md) - RDE-related utility functions

### Representative Image Operations

- [img2thumb](../rdetoolkit/img2thumb.md) - Image to thumbnail conversion

### Error Handling and Logging

- [rdelogger](../rdetoolkit/rdelogger.md) - Logging functionality
- [errors](../rdetoolkit/errors.md) - Error handling
- [exceptions](../rdetoolkit/exceptions.md) - Exception handling

## Data Models

### Configuration Models

- [models.config](../rdetoolkit/models/config.md) - Configuration data structure definitions

### RDE-related Models

- [models.rde2types](../rdetoolkit/models/rde2types.md) - RDE-related type definitions
- [models.invoice](../rdetoolkit/models/invoice_schema.md) - Invoice data structure
- [models.metadata](../rdetoolkit/models/metadata.md) - Metadata management

### Processing Result Models

- Processing result management functionality is integrated into each module

## Implementation Modules

### Controllers

- [impl.input_controller](../rdetoolkit/impl/input_controller.md) - Input mode management
- [impl.compressed_controller](../rdetoolkit/impl/compressed_controller.md) - Compressed file management

### Interfaces

- [interface.filechecker](../rdetoolkit/interface/filechecker.md) - File validation interface

### Command Line

- [CLI Commands](../usage/cli.ja.md) - Command line interface usage

## Usage Patterns

### Basic Usage

```python title="basic_usage.py"
import rdetoolkit
from rdetoolkit.models.rde2types import RdeDatasetPaths


def my_dataset_function(paths: RdeDatasetPaths) -> None:
    # Implement custom processing here
    pass


# Execute structured processing
result = rdetoolkit.workflows.run(custom_dataset_function=my_dataset_function)
```

> Legacy callbacks that accept `RdeInputDirPaths` and `RdeOutputResourcePath`
> as two separate arguments continue to work during the compatibility period.
> Accessors such as `paths.invoice`, `paths.invoice_org`, and
> `paths.metadata_def_json` mirror the most commonly used paths.

### Configuration File Usage

```python title="config_usage.py"
from rdetoolkit.config import parse_config_file

# Load configuration file
config = parse_config_file()

# Reference configuration values
extended_mode = config.system.extended_mode
save_raw = config.system.save_raw
```

### Error Handling

```python title="error_handling.py"
from rdetoolkit.exceptions import RdeToolkitError
from rdetoolkit import workflows

try:
    result = workflows.run(custom_dataset_function=my_function)
except RdeToolkitError as e:
    print(f"RDEToolKit error: {e}")
    print(f"Error code: {e.error_code}")
```

## API Version Information

| Version | Compatibility | Major Changes |
|---------|---------------|---------------|
| 1.0.x | Stable | Initial release |
| 1.1.x | Backward compatible | New features added |
| 1.2.x | Backward compatible | Performance improvements |

!!! note "API Stability"
    Backward compatibility is maintained within major versions. Breaking changes only occur during major version upgrades.

## Developer Information

### Type Hints

RDEToolKit supports complete type hints:

```python title="type_hints.py"
from typing import Optional
from rdetoolkit.models.rde2types import RdeDatasetPaths


def process_data(paths: RdeDatasetPaths, options: Optional[dict] = None) -> bool:
    # Type-safe implementation
    return True
```


## Next Steps

- Specific module details: Refer to the module links above
- Practical usage examples: [User Guide](../user-guide/index.en.md)
- Contributing to development: [Developer Guide](../development/index.en.md)
