# Type Definitions API

## Purpose

This module defines type definitions and type aliases used throughout RDEToolKit. It provides consistent type annotations, path types, and data structure definitions for type safety and code clarity.

## Key Features

### Type Definitions
- Path type definitions for file system operations
- Data structure type aliases
- Input/output type specifications

### Type Safety
- Consistent type annotations across the codebase
- Type checking support for development
- Clear interface definitions

---

::: src.rdetoolkit.models.rde2types

---

## Practical Usage

### Using Type Definitions

```python title="type_usage.py"
from rdetoolkit.models.rde2types import RdeFsPath, RdeInputDirPaths, RdeOutputResourcePath
from pathlib import Path

# Use path types
def process_data(input_path: RdeFsPath, output_path: RdeFsPath):
    """Process data with type-safe paths"""
    input_file = Path(input_path)
    output_file = Path(output_path)
    
    print(f"Processing: {input_file} -> {output_file}")

# Use with structured processing
def dataset_function(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    """Type-safe dataset processing function"""
    for src_path in srcpaths:
        print(f"Processing source: {src_path}")
    
    print(f"Output resources: {resource_paths}")
```
