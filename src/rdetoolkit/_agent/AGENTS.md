# rdetoolkit - Summary Guide for AI Coding Assistants

## Overview

RDEToolKit is a Python package for creating workflows of RDE (Research Data Express) structured programs. It enables researchers to register, process, and visualize experimental data in RDE format through a hybrid Python/Rust architecture. This guide provides quick reference for AI coding agents to effectively use the library.

## Processing Modes

rdetoolkit supports four processing modes (evaluated in order):

1. **invoice**: Standard JSON invoice mode
2. **excelinvoice**: Excel-based invoice mode
3. **MultiDataTile**: Multiple data tiles per dataset (extended_mode)
4. **SmartTable**: Smart table processing with early exit support (extended_mode)

Mode selection is controlled via `Config.system.extended_mode`.

## Quick Start

```python
from rdetoolkit.workflows import run

# Basic usage with custom processing function
def custom_dataset(srcpaths, resource_paths):
    # Process input data from srcpaths
    # Save outputs to resource_paths
    pass

result = run(custom_dataset_function=custom_dataset)
```

## Expected Directory Structure

```
project/
├── tasksupport/
│   ├── config.toml           # Configuration file
│   ├── invoice.schema.json   # Invoice schema
│   └── invoice.json          # Invoice data (or .xlsx for excelinvoice)
├── container/
│   └── data/
│       ├── inputdata/        # Input data files (CSV, images, etc.)
│       └── invoice/          # Output resources
└── process.py                # Your processing script
```

## Custom Processing Function Signature

```python
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath

def custom_dataset(
    srcpaths: RdeInputDirPaths,      # Input paths (container/data/inputdata)
    resource_paths: RdeOutputResourcePath  # Output paths (container/data/invoice)
) -> None:
    """Process input data and save outputs.

    Args:
        srcpaths: RdeInputDirPaths object with .inputdata, .invoice, .tasksupport, .config
        resource_paths: RdeOutputResourcePath object with .struct, .main_image, .other_image,
            .meta, .raw, .nonshared_raw, .rawfiles, .thumbnail, .logs, .invoice
    """
    # Your processing logic here
    pass
```

## Key Modules

- **workflows**: Main workflow orchestration (`run()` function)
- **models.config**: Configuration schema (`Config`, `SystemSettings`)
- **models.rde2types**: Type definitions (`RdeInputDirPaths`, `RdeOutputResourcePath`)
- **invoice_generator**: Generate invoice.json from schema
- **processing**: Processor-based pipeline architecture
- **graph**: CSV to graph conversion utilities

## Common Errors

### 1. Missing Configuration File
```
Error: Config file not found: tasksupport/config.toml
Solution: Create config.toml or use default configuration
```

### 2. Invalid Directory Structure
```
Error: Required directory not found: container/data/inputdata
Solution: Ensure proper directory structure as shown above
```

### 3. Custom Function Signature Mismatch
```
Error: custom_dataset_function must accept (RdeInputDirPaths, RdeOutputResourcePath)
Solution: Match the function signature exactly as shown
```

## Configuration Example

```toml
[system]
extended_mode = "MultiDataTile"  # or "SmartTable", "", etc.
save_raw = false
save_thumbnail_image = true
```

## CLI Commands

```bash
# Initialize project template
rdetoolkit init <project_name>

# Generate invoice.json from schema
rdetoolkit gen-invoice tasksupport/invoice.schema.json

# Generate Excel invoice from schema
rdetoolkit gen-excelinvoice tasksupport/invoice.schema.json

# Validate project structure
rdetoolkit validate <project_dir>
```

## For More Details

Use `get_agent_guide(detailed=True)` or `rdetoolkit agent-guide --detailed` for comprehensive documentation including:
- Architecture details
- Advanced processing patterns
- Error handling patterns
- Testing patterns
- Configuration reference
