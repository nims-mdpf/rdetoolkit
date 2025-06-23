# Processing Module

The `rdetoolkit.processing` module provides a modern, pipeline-based architecture for data processing operations in the RDE toolkit. This module replaces the traditional mode-based processing approach with a more flexible and extensible pipeline system.

## Overview

The processing module introduces a clean separation of concerns through:

- **Pipeline Architecture**: Sequential execution of processing steps
- **Processor Components**: Individual, reusable processing units
- **Context Management**: Centralized state and resource management
- **Factory Pattern**: Automated pipeline construction for different modes
- **Extensibility**: Easy addition of new processors and pipelines

## Architecture Components

### Core Classes

- **Pipeline**: Orchestrates the execution of multiple processors
- **Processor**: Abstract base class for all processing operations
- **ProcessingContext**: Encapsulates all processing state and resources
- **PipelineFactory**: Creates pre-configured pipelines for different modes

### Supported Processing Modes

1. **RDEFormat Mode**: Processes RDE format files with structured data
2. **MultiDataTile Mode**: Handles multiple data files in flat structure
3. **ExcelInvoice Mode**: Processes Excel-based invoice data
4. **Invoice Mode**: Standard invoice processing
5. **SmartTableInvoice Mode**: Processes SmartTable-generated data

## Quick Start

### Basic Usage

```python
from rdetoolkit.processing import PipelineFactory, ProcessingContext
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath

# Create processing context
context = ProcessingContext(
    index="0",
    srcpaths=input_paths,
    resource_paths=output_paths,
    datasets_function=None,
    mode_name="Invoice"
)

# Create and execute pipeline
pipeline = PipelineFactory.create_pipeline("invoice")
result = pipeline.execute(context)
```

### Custom Pipeline Creation

```python
from rdetoolkit.processing import Pipeline
from rdetoolkit.processing.processors import FileCopier, DatasetRunner, ThumbnailGenerator

# Build custom pipeline
pipeline = (Pipeline()
    .add(FileCopier())
    .add(DatasetRunner())
    .add(ThumbnailGenerator()))

# Execute pipeline
result = pipeline.execute(context)
```

## Module Structure

```
processing/
├── __init__.py          # Main module exports
├── context.py           # Processing context management
├── factories.py         # Pipeline factory and builders
├── pipeline.py          # Core pipeline and processor classes
└── processors/          # Individual processor implementations
    ├── __init__.py      # Processor exports
    ├── datasets.py      # Custom dataset processing
    ├── descriptions.py  # Description updates
    ├── files.py         # File operations
    ├── invoice.py       # Invoice initialization
    ├── thumbnails.py    # Thumbnail generation
    ├── validation.py    # Data validation
    └── variables.py     # Variable replacement
```

## Key Features

### Pipeline Execution

- **Sequential Processing**: Processors execute in order
- **Context Sharing**: All processors share the same context
- **Error Handling**: Comprehensive error handling and logging
- **Status Reporting**: Detailed execution status and results

### Processor Design

- **Stateless**: Processors maintain no internal state
- **Idempotent**: Can be safely re-executed
- **Configurable**: Behavior controlled by context configuration
- **Extensible**: Easy to add new processing capabilities

### Factory Pattern

- **Mode-based Creation**: Automatic pipeline setup for different modes
- **Backward Compatibility**: Support for legacy mode names
- **Extensible**: Easy addition of new processing modes

## Error Handling

The processing module provides comprehensive error handling:

```python
try:
    result = pipeline.execute(context)
    if result.status == "success":
        print("Processing completed successfully")
    else:
        print(f"Processing failed: {result.error_message}")
except Exception as e:
    print(f"Pipeline execution failed: {e}")
```

## Performance Considerations

- **Memory Efficient**: Streaming processing where possible
- **Parallel Processing**: Processor design supports parallel execution
- **Resource Management**: Proper cleanup and resource management
- **Logging**: Comprehensive logging for debugging and monitoring

## Migration from Legacy Code

The processing module is designed to be backward compatible with existing mode-based processing:

```python
# Legacy approach
from rdetoolkit.modeproc import invoice_mode_process

# New approach
from rdetoolkit.processing import PipelineFactory

pipeline = PipelineFactory.create_pipeline("invoice")
result = pipeline.execute(context)
```

## See Also

- [Context Management](context.md) - Processing context and state management
- [Pipeline Architecture](pipeline.md) - Core pipeline and processor classes
- [Factory Pattern](factories.md) - Pipeline creation and builders
- [Processors](processors/index.md) - Individual processor implementations
