# Processors

The `rdetoolkit.processing.processors` module provides individual processor implementations for the processing pipeline. Each processor handles a specific aspect of the data processing workflow.

## Overview

The processors module contains specialized processing components:

- **File Operations**: File copying and management
- **Invoice Processing**: Invoice initialization and validation
- **Data Processing**: Custom dataset execution and variable application
- **Image Processing**: Thumbnail generation
- **Validation**: Metadata and invoice validation
- **Content Updates**: Description and feature updates

## Processor Classes

### File Processing

- **[FileCopier](files.md#filecopier)**: Standard file copying for raw files
- **[RDEFormatFileCopier](files.md#rdeformatfilecopier)**: Specialized copying for RDEFormat mode
- **[SmartTableFileCopier](files.md#smarttablefilecopier)**: Specialized copying for SmartTable mode

### Invoice Processing

- **[StandardInvoiceInitializer](invoice.md#standardinvoiceinitializer)**: Standard invoice initialization
- **[ExcelInvoiceInitializer](invoice.md#excelinvoiceinitializer)**: Excel-based invoice initialization
- **[SmartTableInvoiceInitializer](invoice.md#smarttableinvoiceinitializer)**: SmartTable-based invoice initialization
- **[InvoiceInitializerFactory](invoice.md#invoiceinitializerfactory)**: Factory for creating appropriate initializers

### Data Processing

- **[DatasetRunner](datasets.md#datasetrunner)**: Executes custom dataset processing functions
- **[VariableApplier](variables.md#variableapplier)**: Applies magic variable replacement

### Content Processing

- **[DescriptionUpdater](descriptions.md#descriptionupdater)**: Updates descriptions with feature information
- **[ThumbnailGenerator](thumbnails.md#thumbnailgenerator)**: Generates thumbnail images

### Validation

- **[InvoiceValidator](validation.md#invoicevalidator)**: Validates invoice files against schema
- **[MetadataValidator](validation.md#metadatavalidator)**: Validates metadata files against schema

## Common Patterns

All processors follow these design patterns:

### Base Processor Interface

```python
from rdetoolkit.processing.pipeline import Processor
from rdetoolkit.processing.context import ProcessingContext

class ExampleProcessor(Processor):
    def process(self, context: ProcessingContext) -> None:
        # Processing logic here
        pass
```

### Configuration-Based Processing

```python
def process(self, context: ProcessingContext) -> None:
    config = context.srcpaths.config

    if not config.some_feature_enabled:
        return  # Skip processing if disabled

    # Perform processing
```

### Error Handling

```python
def process(self, context: ProcessingContext) -> None:
    try:
        # Main processing logic
        self._do_processing(context)
    except SpecificError:
        # Handle specific errors gracefully
        logger.warning("Specific error occurred, continuing...")
    except Exception as e:
        # Critical errors should propagate
        logger.error(f"Critical error in {self.get_name()}: {e}")
        raise
```

### Resource Management

```python
def process(self, context: ProcessingContext) -> None:
    # Access resources from context
    input_files = context.resource_paths.rawfiles
    output_dir = context.resource_paths.struct

    # Create output directory if needed
    output_dir.mkdir(parents=True, exist_ok=True)

    # Process files
    for file in input_files:
        self._process_file(file, output_dir)
```

## Usage Examples

### Basic Processor Usage

```python
from rdetoolkit.processing.processors import FileCopier, DatasetRunner

# Create processors
file_copier = FileCopier()
dataset_runner = DatasetRunner()

# Execute processors with context
file_copier.process(context)
dataset_runner.process(context)
```

### Pipeline Integration

```python
from rdetoolkit.processing import Pipeline
from rdetoolkit.processing.processors import (
    FileCopier, DatasetRunner, ThumbnailGenerator, InvoiceValidator
)

# Build pipeline with processors
pipeline = (Pipeline()
    .add(FileCopier())
    .add(DatasetRunner())
    .add(ThumbnailGenerator())
    .add(InvoiceValidator()))

# Execute pipeline
result = pipeline.execute(context)
```

### Custom Processor Implementation

```python
from rdetoolkit.processing.pipeline import Processor
from rdetoolkit.processing.context import ProcessingContext
import json

class MetadataProcessor(Processor):
    """Custom processor that creates metadata files."""

    def process(self, context: ProcessingContext) -> None:
        metadata = {
            "processing_mode": context.mode_name,
            "file_count": len(context.resource_paths.rawfiles),
            "timestamp": self._get_timestamp(),
        }

        metadata_file = context.metadata_path
        metadata_file.parent.mkdir(parents=True, exist_ok=True)

        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

    def _get_timestamp(self) -> str:
        from datetime import datetime
        return datetime.now().isoformat()

# Use custom processor
custom_processor = MetadataProcessor()
custom_processor.process(context)
```

### Conditional Processing

```python
from rdetoolkit.processing.processors import ThumbnailGenerator

class ConditionalThumbnailGenerator(ThumbnailGenerator):
    """Thumbnail generator with additional conditions."""

    def process(self, context: ProcessingContext) -> None:
        config = context.srcpaths.config

        # Check if thumbnails are enabled
        if not config.save_thumbnail_image:
            return

        # Check if we have image files
        image_files = [f for f in context.resource_paths.rawfiles
                      if f.suffix.lower() in ['.jpg', '.png', '.tiff']]

        if not image_files:
            return  # No images to process

        # Call parent implementation
        super().process(context)
```

### Processor Factory Pattern

```python
from typing import Dict, Type
from rdetoolkit.processing.pipeline import Processor

class ProcessorFactory:
    """Factory for creating processors based on configuration."""

    _processors: Dict[str, Type[Processor]] = {
        'files': FileCopier,
        'datasets': DatasetRunner,
        'thumbnails': ThumbnailGenerator,
        'validation': InvoiceValidator,
    }

    @classmethod
    def create_processor(cls, processor_type: str) -> Processor:
        processor_class = cls._processors.get(processor_type)
        if not processor_class:
            raise ValueError(f"Unknown processor type: {processor_type}")
        return processor_class()

    @classmethod
    def create_processors(cls, processor_types: list[str]) -> list[Processor]:
        return [cls.create_processor(ptype) for ptype in processor_types]

# Usage
processors = ProcessorFactory.create_processors(['files', 'datasets', 'validation'])
```

## Performance Considerations

### Memory Efficiency

```python
def process(self, context: ProcessingContext) -> None:
    # Process files one at a time instead of loading all into memory
    for raw_file in context.resource_paths.rawfiles:
        self._process_single_file(raw_file, context)
```

### I/O Optimization

```python
def process(self, context: ProcessingContext) -> None:
    # Batch I/O operations
    operations = self._prepare_operations(context)
    self._execute_batch_operations(operations)
```

### Error Recovery

```python
def process(self, context: ProcessingContext) -> None:
    failed_files = []

    for raw_file in context.resource_paths.rawfiles:
        try:
            self._process_file(raw_file, context)
        except Exception as e:
            failed_files.append((raw_file, str(e)))
            logger.warning(f"Failed to process {raw_file}: {e}")

    if failed_files:
        # Report failed files but don't stop processing
        logger.info(f"Completed with {len(failed_files)} failures")
```

## Testing Processors

### Unit Testing

```python
import unittest
from unittest.mock import Mock, patch
from rdetoolkit.processing.processors import FileCopier

class TestFileCopier(unittest.TestCase):
    def setUp(self):
        self.processor = FileCopier()
        self.context = Mock()
        # Setup mock context attributes

    def test_process_success(self):
        # Test successful processing
        self.processor.process(self.context)
        # Assert expected behavior

    def test_process_error_handling(self):
        # Test error handling
        with self.assertRaises(SpecificError):
            self.processor.process(self.context)
```

### Integration Testing

```python
from rdetoolkit.processing import Pipeline
from rdetoolkit.processing.processors import FileCopier, DatasetRunner

def test_processor_integration():
    # Create test context
    context = create_test_context()

    # Create pipeline with processors
    pipeline = Pipeline().add(FileCopier()).add(DatasetRunner())

    # Execute and verify results
    result = pipeline.execute(context)
    assert result.status == "success"
```

## See Also

- [File Processors](files.md) - File copying and management
- [Invoice Processors](invoice.md) - Invoice initialization and handling
- [Dataset Processors](datasets.md) - Custom dataset processing
- [Validation Processors](validation.md) - Data validation
- [Other Processors](variables.md) - Variable application and content updates
