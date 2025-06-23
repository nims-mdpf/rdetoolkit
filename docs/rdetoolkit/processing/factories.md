# Pipeline Factory

The `rdetoolkit.processing.factories` module provides factory classes and builders for creating predefined processing pipelines. It implements the Factory and Builder design patterns to automate pipeline construction for different processing modes.

## Overview

The factory module provides:

- **Automated Pipeline Creation**: Pre-configured pipelines for different modes
- **Builder Pattern**: Flexible pipeline construction
- **Mode Enumeration**: Standardized processing mode definitions
- **Backward Compatibility**: Support for legacy method names
- **Extensibility**: Easy addition of new modes and pipelines

## Classes and Enums

### ProcessingMode

Enumeration of supported processing modes.

```python
class ProcessingMode(Enum):
    """Enumeration of supported processing modes."""
    RDEFORMAT = "rdeformat"
    MULTIDATATILE = "multidatatile"
    EXCELINVOICE = "excelinvoice"
    INVOICE = "invoice"
    SMARTTABLEINVOICE = "smarttableinvoice"
```

**Supported Modes:**
- **RDEFORMAT**: Processes RDE format files with structured data
- **MULTIDATATILE**: Handles multiple data files in flat structure
- **EXCELINVOICE**: Processes Excel-based invoice data
- **INVOICE**: Standard invoice processing
- **SMARTTABLEINVOICE**: Processes SmartTable-generated data

### PipelineBuilder

Abstract base class for pipeline builders.

```python
class PipelineBuilder(ABC):
    """Abstract base class for pipeline builders."""
```

#### Methods

##### build

Build and return a configured pipeline.

```python
@abstractmethod
def build(self) -> Pipeline
```

**Returns:**
- `Pipeline`: Configured pipeline for the specific mode

### Concrete Builder Classes

#### RDEFormatPipelineBuilder

Builder for RDEFormat mode pipelines.

```python
def build(self) -> Pipeline
```

**Pipeline Configuration:**
1. `StandardInvoiceInitializer` - Initialize invoice from original
2. `RDEFormatFileCopier` - Copy files by directory structure
3. `DatasetRunner` - Execute custom dataset processing
4. `ThumbnailGenerator` - Generate thumbnail images
5. `DescriptionUpdater` - Update descriptions with features
6. `MetadataValidator` - Validate metadata files
7. `InvoiceValidator` - Validate invoice files

#### MultiFilePipelineBuilder

Builder for MultiFile mode pipelines.

```python
def build(self) -> Pipeline
```

**Pipeline Configuration:**
1. `StandardInvoiceInitializer` - Initialize invoice from original
2. `FileCopier` - Copy raw files to output directories
3. `DatasetRunner` - Execute custom dataset processing
4. `VariableApplier` - Apply magic variables to invoice
5. `ThumbnailGenerator` - Generate thumbnail images
6. `DescriptionUpdater` - Update descriptions with features
7. `MetadataValidator` - Validate metadata files
8. `InvoiceValidator` - Validate invoice files

#### ExcelInvoicePipelineBuilder

Builder for ExcelInvoice mode pipelines.

```python
def build(self) -> Pipeline
```

**Pipeline Configuration:**
1. `ExcelInvoiceInitializer` - Initialize invoice from Excel data
2. `FileCopier` - Copy raw files to output directories
3. `DatasetRunner` - Execute custom dataset processing
4. `VariableApplier` - Apply magic variables to invoice
5. `ThumbnailGenerator` - Generate thumbnail images
6. `DescriptionUpdater` - Update descriptions with features
7. `MetadataValidator` - Validate metadata files
8. `InvoiceValidator` - Validate invoice files

#### InvoicePipelineBuilder

Builder for Invoice mode pipelines.

```python
def build(self) -> Pipeline
```

**Pipeline Configuration:**
1. `FileCopier` - Copy raw files to output directories
2. `DatasetRunner` - Execute custom dataset processing
3. `ThumbnailGenerator` - Generate thumbnail images
4. `VariableApplier` - Apply magic variables to invoice
5. `DescriptionUpdater` - Update descriptions with features
6. `MetadataValidator` - Validate metadata files
7. `InvoiceValidator` - Validate invoice files

#### SmartTableInvoicePipelineBuilder

Builder for SmartTableInvoice mode pipelines.

```python
def build(self) -> Pipeline
```

**Pipeline Configuration:**
1. `SmartTableInvoiceInitializer` - Initialize invoice from SmartTable data
2. `SmartTableFileCopier` - Copy files excluding SmartTable CSVs
3. `DatasetRunner` - Execute custom dataset processing
4. `ThumbnailGenerator` - Generate thumbnail images
5. `VariableApplier` - Apply magic variables to invoice
6. `DescriptionUpdater` - Update descriptions with features
7. `MetadataValidator` - Validate metadata files
8. `InvoiceValidator` - Validate invoice files

### PipelineFactory

Factory for creating predefined processing pipelines with Pythonic design.

```python
class PipelineFactory:
    """Factory for creating predefined processing pipelines."""
```

#### Class Methods

##### create_pipeline

Create a pipeline for the specified mode.

```python
@classmethod
def create_pipeline(cls, mode: str | ProcessingMode) -> Pipeline
```

**Parameters:**
- `mode` (str | ProcessingMode): Processing mode (string or ProcessingMode enum)

**Returns:**
- `Pipeline`: Pipeline configured for the specified mode

**Raises:**
- `ValueError`: If mode is not supported

**Example:**
```python
from rdetoolkit.processing.factories import PipelineFactory

# Using string mode
pipeline = PipelineFactory.create_pipeline("invoice")

# Using enum mode
from rdetoolkit.processing.factories import ProcessingMode
pipeline = PipelineFactory.create_pipeline(ProcessingMode.INVOICE)
```

##### get_supported_modes

Get list of supported mode names.

```python
@classmethod
def get_supported_modes(cls) -> list[str]
```

**Returns:**
- `list[str]`: List of supported mode strings

**Example:**
```python
modes = PipelineFactory.get_supported_modes()
print(f"Supported modes: {', '.join(modes)}")
# Output: Supported modes: rdeformat, multidatatile, excelinvoice, invoice, smarttableinvoice
```

#### Static Methods (Backward Compatibility)

##### create_rdeformat_pipeline

Create a pipeline for RDEFormat mode processing.

```python
@staticmethod
def create_rdeformat_pipeline() -> Pipeline
```

**Returns:**
- `Pipeline`: Pipeline configured for RDEFormat mode

##### create_multifile_pipeline

Create a pipeline for MultiFile mode processing.

```python
@staticmethod
def create_multifile_pipeline() -> Pipeline
```

**Returns:**
- `Pipeline`: Pipeline configured for MultiFile mode

##### create_excel_pipeline

Create a pipeline for ExcelInvoice mode processing.

```python
@staticmethod
def create_excel_pipeline() -> Pipeline
```

**Returns:**
- `Pipeline`: Pipeline configured for ExcelInvoice mode

##### create_invoice_pipeline

Create a pipeline for Invoice mode processing.

```python
@staticmethod
def create_invoice_pipeline() -> Pipeline
```

**Returns:**
- `Pipeline`: Pipeline configured for Invoice mode

##### create_smarttable_invoice_pipeline

Create a pipeline for SmartTableInvoice mode processing.

```python
@staticmethod
def create_smarttable_invoice_pipeline() -> Pipeline
```

**Returns:**
- `Pipeline`: Pipeline configured for SmartTableInvoice mode

## Usage Examples

### Basic Pipeline Creation

```python
from rdetoolkit.processing.factories import PipelineFactory

# Create pipelines for different modes
invoice_pipeline = PipelineFactory.create_pipeline("invoice")
excel_pipeline = PipelineFactory.create_pipeline("excelinvoice")
smarttable_pipeline = PipelineFactory.create_pipeline("smarttableinvoice")

# Execute pipeline
result = invoice_pipeline.execute(context)
```

### Dynamic Mode Selection

```python
from rdetoolkit.processing.factories import PipelineFactory

def create_pipeline_for_mode(mode_name: str):
    """Create pipeline based on mode name with validation."""

    supported_modes = PipelineFactory.get_supported_modes()

    if mode_name.lower() not in supported_modes:
        raise ValueError(f"Unsupported mode: {mode_name}. Supported: {supported_modes}")

    return PipelineFactory.create_pipeline(mode_name.lower())

# Usage
try:
    pipeline = create_pipeline_for_mode("Invoice")
    print(f"Created pipeline with {pipeline.get_processor_count()} processors")
except ValueError as e:
    print(f"Error: {e}")
```

### Mode-Based Processing

```python
from rdetoolkit.processing.factories import PipelineFactory, ProcessingMode

def process_data_by_mode(context, mode_name: str):
    """Process data using the appropriate pipeline for the mode."""

    # Convert string to enum for validation
    try:
        mode = ProcessingMode(mode_name.lower())
    except ValueError:
        supported = [m.value for m in ProcessingMode]
        raise ValueError(f"Unsupported mode: {mode_name}. Supported: {supported}")

    # Create and execute pipeline
    pipeline = PipelineFactory.create_pipeline(mode)

    print(f"Processing in {mode.value} mode")
    print(f"Pipeline processors: {pipeline.get_processor_names()}")

    result = pipeline.execute(context)
    return result

# Usage
result = process_data_by_mode(context, "invoice")
```

### Custom Builder Implementation

```python
from rdetoolkit.processing.factories import PipelineBuilder
from rdetoolkit.processing import Pipeline
from rdetoolkit.processing.processors import *

class CustomPipelineBuilder(PipelineBuilder):
    """Custom builder for specialized processing."""

    def build(self) -> Pipeline:
        """Build custom pipeline with specific processors."""
        return (self._create_base_pipeline()
                .add(FileCopier())
                .add(CustomDataProcessor())  # Custom processor
                .add(DatasetRunner())
                .add(ThumbnailGenerator())
                .add(InvoiceValidator()))

# Use custom builder
builder = CustomPipelineBuilder()
custom_pipeline = builder.build()
```

### Pipeline Inspection

```python
from rdetoolkit.processing.factories import PipelineFactory

def inspect_pipeline(mode: str):
    """Inspect pipeline configuration for a given mode."""

    pipeline = PipelineFactory.create_pipeline(mode)

    print(f"Pipeline for {mode} mode:")
    print(f"  Processor count: {pipeline.get_processor_count()}")
    print(f"  Processors:")

    for i, name in enumerate(pipeline.get_processor_names(), 1):
        print(f"    {i}. {name}")

# Inspect all supported modes
for mode in PipelineFactory.get_supported_modes():
    inspect_pipeline(mode)
    print()
```

### Backward Compatibility Usage

```python
from rdetoolkit.processing.factories import PipelineFactory

# Legacy method calls (backward compatibility)
rde_pipeline = PipelineFactory.create_rdeformat_pipeline()
multi_pipeline = PipelineFactory.create_multifile_pipeline()
excel_pipeline = PipelineFactory.create_excel_pipeline()
invoice_pipeline = PipelineFactory.create_invoice_pipeline()
smarttable_pipeline = PipelineFactory.create_smarttable_invoice_pipeline()

# Modern method calls (recommended)
rde_pipeline = PipelineFactory.create_pipeline("rdeformat")
multi_pipeline = PipelineFactory.create_pipeline("multidatatile")
excel_pipeline = PipelineFactory.create_pipeline("excelinvoice")
invoice_pipeline = PipelineFactory.create_pipeline("invoice")
smarttable_pipeline = PipelineFactory.create_pipeline("smarttableinvoice")
```

### Error Handling

```python
from rdetoolkit.processing.factories import PipelineFactory

def safe_pipeline_creation(mode: str):
    """Safely create pipeline with comprehensive error handling."""

    try:
        # Validate mode
        supported_modes = PipelineFactory.get_supported_modes()
        if mode.lower() not in supported_modes:
            print(f"Error: '{mode}' is not supported")
            print(f"Supported modes: {', '.join(supported_modes)}")
            return None

        # Create pipeline
        pipeline = PipelineFactory.create_pipeline(mode)

        print(f"✓ Successfully created {mode} pipeline")
        print(f"  Processors: {', '.join(pipeline.get_processor_names())}")

        return pipeline

    except ValueError as e:
        print(f"✗ Value error: {e}")
        return None
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return None

# Usage
pipeline = safe_pipeline_creation("invoice")
if pipeline:
    result = pipeline.execute(context)
```

## Extending the Factory

### Adding New Modes

```python
from rdetoolkit.processing.factories import PipelineBuilder, PipelineFactory
from rdetoolkit.processing import Pipeline
from enum import Enum

# 1. Extend ProcessingMode enum
class ExtendedProcessingMode(Enum):
    RDEFORMAT = "rdeformat"
    MULTIDATATILE = "multidatatile"
    EXCELINVOICE = "excelinvoice"
    INVOICE = "invoice"
    SMARTTABLEINVOICE = "smarttableinvoice"
    CUSTOM_MODE = "custommode"  # New mode

# 2. Create custom builder
class CustomModePipelineBuilder(PipelineBuilder):
    def build(self) -> Pipeline:
        return (self._create_base_pipeline()
                .add(CustomProcessor())
                .add(DatasetRunner())
                .add(InvoiceValidator()))

# 3. Extend factory (would require modifying the original class)
# This is an example of how you might extend the factory
class ExtendedPipelineFactory(PipelineFactory):
    _builders = {
        **PipelineFactory._builders,
        ExtendedProcessingMode.CUSTOM_MODE: CustomModePipelineBuilder,
    }
```

### Custom Factory Pattern

```python
from typing import Dict, Type
from rdetoolkit.processing.factories import PipelineBuilder
from rdetoolkit.processing import Pipeline

class CustomPipelineFactory:
    """Custom factory for application-specific pipelines."""

    def __init__(self):
        self._builders: Dict[str, Type[PipelineBuilder]] = {}

    def register_builder(self, mode: str, builder_class: Type[PipelineBuilder]):
        """Register a new builder for a mode."""
        self._builders[mode.lower()] = builder_class

    def create_pipeline(self, mode: str) -> Pipeline:
        """Create pipeline for the specified mode."""
        builder_class = self._builders.get(mode.lower())
        if not builder_class:
            raise ValueError(f"No builder registered for mode: {mode}")

        builder = builder_class()
        return builder.build()

    def get_supported_modes(self) -> list[str]:
        """Get list of supported modes."""
        return list(self._builders.keys())

# Usage
factory = CustomPipelineFactory()
factory.register_builder("custom", CustomModePipelineBuilder)
pipeline = factory.create_pipeline("custom")
```

## Performance Considerations

- **Lazy Instantiation**: Builders create processors only when needed
- **Memory Efficiency**: Pipelines are lightweight objects
- **Caching**: Consider caching pipelines for repeated use
- **Thread Safety**: Factory methods are thread-safe

## See Also

- [Pipeline Architecture](pipeline.md) - Core pipeline and processor classes
- [Processing Context](context.md) - Context management and state
- [Processors](processors/index.md) - Individual processor implementations
- [Processing Module](index.md) - Main processing module overview
