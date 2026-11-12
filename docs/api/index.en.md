# API Reference

## Purpose

This section provides technical specifications for all features of RDEToolKit. It is a comprehensive reference including detailed functionality, parameters, return values, and usage examples for each module.

## API Documentation Structure

RDEToolKit's API documentation is structured using a hybrid approach:

- **Auto-generated parts**: Detailed technical specifications generated from docstrings in source code
- **Manually created parts**: Practical usage examples and inter-module collaboration methods

## Top-level Imports

The names below form the supported top-level API: each one works as
`from rdetoolkit import <name>`, is included in `from rdetoolkit import *`, and is
typed in the shipped `__init__.pyi` stub. They are resolved lazily, so
`import rdetoolkit` alone does not import any submodule or heavy dependency.

```python title="top_level_imports.py"
from rdetoolkit import Failure, Result, Success, as_node, flow, node, workflows
```

<!-- top-level-api:start -->
| Name | Kind | Resolves to |
|------|------|-------------|
| `node` | v2 decorator | `rdetoolkit.core.node.node` |
| `flow` | v2 decorator | `rdetoolkit.core.flow.flow` |
| `as_node` | v2 adapter | `rdetoolkit.nodes.as_node` |
| `Result` | type alias | `rdetoolkit.result.Result` |
| `Success` | class | `rdetoolkit.result.Success` |
| `Failure` | class | `rdetoolkit.result.Failure` |
| `try_result` | decorator | `rdetoolkit.result.try_result` |
| `DirectoryOps` | class (Rust extension) | `rdetoolkit.core.DirectoryOps` |
| `ManagedDirectory` | class (Rust extension) | `rdetoolkit.core.ManagedDirectory` |
| `detect_encoding` | function (Rust extension) | `rdetoolkit.core.detect_encoding` |
| `resize_image_aspect_ratio` | function (Rust extension) | `rdetoolkit.core.resize_image_aspect_ratio` |
| `workflows` | module | `rdetoolkit.workflows` |
| `errors` | module | `rdetoolkit.errors` |
| `exceptions` | module | `rdetoolkit.exceptions` |
| `img2thumb` | module | `rdetoolkit.img2thumb` |
| `invoicefile` | module | `rdetoolkit.invoicefile` |
| `rde2util` | module | `rdetoolkit.rde2util` |
| `rdelogger` | module | `rdetoolkit.rdelogger` |
| `storage` | module | `rdetoolkit.storage` |
| `traceback` | module | `rdetoolkit.traceback` |
| `models` | module | `rdetoolkit.models` |
| `config` | module | `rdetoolkit.models.config` |
| `invoice` | module | `rdetoolkit.models.invoice` |
| `invoice_schema` | module | `rdetoolkit.models.invoice_schema` |
| `metadata` | module | `rdetoolkit.models.metadata` |
| `rde2types` | module | `rdetoolkit.models.rde2types` |
<!-- top-level-api:end -->

`__version__` is also exported. The legacy `get_agent_guide()` helper remains
importable for v1 compatibility but is not part of the supported v2 API and is
scheduled for removal. No pre-GA top-level export has been removed.

The top-level `config` attribute is the configuration *models* module
(`rdetoolkit.models.config`). The configuration *loader* functions live in the
`rdetoolkit.config` package; import them explicitly, as in
`from rdetoolkit.config import parse_config_file`.

## Core Modules

### Workflow Management

- [workflows](../rdetoolkit/workflows.md) - Structured processing execution and workflow management

### Configuration and File Operations

- [config](../rdetoolkit/config.md) - Configuration file loading and management
- [fileops](../rdetoolkit/fileops.md) - RDE-related file operations

### Data Processing

- [invoicefile](../rdetoolkit/invoicefile.md) - Invoice file processing
- [validation](../rdetoolkit/validation.md) - Data validation
- [rde2util](../rdetoolkit/rde2util.md) - RDE-related utility functions
- [csv2graph](../rdetoolkit/csv2graph.md) - CSV visualization and plotting pipeline

### Representative Image Operations

- [img2thumb](../rdetoolkit/img2thumb.md) - Image to thumbnail conversion

### Error Handling and Logging

- [result](result.en.md) - Type-safe error handling with Result pattern
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

- [CLI Commands](../usage/cli.en.md) - Command line interface usage

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
| 1.4.x | Backward compatible | CSV-to-graph API, config generator CLI, SmartTable metadata automation |

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
