# Description Processor

The `rdetoolkit.processing.processors.descriptions` module provides processing functionality for updating descriptions with feature information. This module contains processors specifically designed to enhance invoice descriptions with extracted features while maintaining robust error handling.

## Overview

The descriptions processor module focuses on:

- **Description Enhancement**: Updates invoice descriptions with feature information
- **Robust Error Handling**: Suppresses errors to ensure processing pipeline continuity
- **Feature Integration**: Integrates extracted features into invoice metadata
- **Pipeline Compatibility**: Implements the standard processor interface for pipeline integration

## Classes

### DescriptionUpdater

A processor that updates descriptions with feature information, providing robust error handling to prevent pipeline failures.

#### Constructor

```python
DescriptionUpdater()
```

The `DescriptionUpdater` class inherits from the base `Processor` class and requires no additional parameters for initialization.

#### Methods

##### process(context)

Update descriptions with features, ignoring any errors to ensure pipeline continuity.

```python
def process(context: ProcessingContext) -> None
```

**Parameters:**

- `context` (ProcessingContext): Processing context containing resource paths and configuration

**Returns:**

- `None`: This method does not return a value

**Error Handling:**

- Uses `contextlib.suppress(Exception)` to ignore any exceptions during processing
- Logs warnings for any unexpected errors
- Ensures pipeline continuation even if description updates fail

**Processing Flow:**

1. Logs the start of description update process
2. Calls `update_description_with_features()` with context information
3. Suppresses any exceptions that occur during processing
4. Logs completion status

**Example:**

```python
from rdetoolkit.processing.processors.descriptions import DescriptionUpdater
from rdetoolkit.processing.context import ProcessingContext

# Initialize the processor
processor = DescriptionUpdater()

# Process within a pipeline context
# (context is typically provided by the pipeline framework)
processor.process(context)
```

#### Base Class Integration

The `DescriptionUpdater` class inherits from `Processor`, providing:

- **Pipeline Compatibility**: Standard interface for use in processing pipelines
- **Context Management**: Access to processing context and resource paths
- **Error Handling**: Built-in error handling patterns
- **Logging Integration**: Consistent logging behavior across processors

## Processing Context Requirements

The `DescriptionUpdater` requires the following context attributes:

- `resource_paths`: Output resource paths for the current processing tile
- `invoice_dst_filepath`: Destination path for the invoice file
- `metadata_def_path`: Path to metadata definition file

## Integration with Invoice System

The description processor integrates with the invoice system through:

### update_description_with_features()

The processor delegates to `rdetoolkit.invoicefile.update_description_with_features()`:

```python
update_description_with_features(
    resource_paths,      # RdeOutputResourcePath
    invoice_dst_filepath, # Path to invoice destination
    metadata_def_path    # Path to metadata definitions
)
```

This function:

- Reads existing invoice data
- Extracts features from processed data
- Updates description fields with feature information
- Saves the enhanced invoice data

## Usage in Processing Pipelines

### Basic Pipeline Integration

```python
from rdetoolkit.processing.pipeline import Pipeline
from rdetoolkit.processing.processors.descriptions import DescriptionUpdater

# Create pipeline with description processor
pipeline = Pipeline([
    # ... other processors ...
    DescriptionUpdater(),
    # ... additional processors ...
])

# Execute pipeline
pipeline.execute(context)
```

### Custom Pipeline Configuration

```python
from rdetoolkit.processing.factories import ProcessorFactory
from rdetoolkit.processing.processors.descriptions import DescriptionUpdater

# Register description processor in factory
factory = ProcessorFactory()
factory.register("description_updater", DescriptionUpdater)

# Create processor through factory
processor = factory.create("description_updater")
```

### Conditional Processing

```python
from rdetoolkit.processing.processors.descriptions import DescriptionUpdater
from rdetoolkit.processing.context import ProcessingContext

class ConditionalDescriptionProcessor(DescriptionUpdater):
    """Description processor with conditional execution."""

    def process(self, context: ProcessingContext) -> None:
        """Process only if features are available."""

        # Check if feature extraction was successful
        if self._has_features(context):
            super().process(context)
        else:
            logger.info("Skipping description update - no features available")

    def _has_features(self, context: ProcessingContext) -> bool:
        """Check if features are available for processing."""
        # Implementation to check feature availability
        feature_file = context.resource_paths.meta / "features.json"
        return feature_file.exists()
```

## Error Handling and Resilience

### Exception Suppression

The processor uses `contextlib.suppress(Exception)` to handle errors gracefully:

```python
with contextlib.suppress(Exception):
    update_description_with_features(
        context.resource_paths,
        context.invoice_dst_filepath,
        context.metadata_def_path,
    )
```

**Benefits:**

- Prevents pipeline failures due to description update issues
- Maintains processing continuity for other pipeline stages
- Allows partial success in multi-stage processing

### Logging Strategy

The processor implements comprehensive logging:

```python
logger.debug("Updating descriptions with features")
# ... processing ...
logger.debug("Description update completed (errors suppressed)")
```

**Log Levels:**

- `DEBUG`: Normal processing flow information
- `WARNING`: Unexpected errors that are handled gracefully
- `INFO`: Significant processing milestones

### Error Recovery Patterns

```python
class RobustDescriptionUpdater(DescriptionUpdater):
    """Enhanced description processor with error recovery."""

    def process(self, context: ProcessingContext) -> None:
        """Process with multiple error recovery strategies."""

        try:
            # Attempt primary processing
            super().process(context)

        except MemoryError:
            # Handle memory-specific issues
            logger.warning("Memory error during description update")
            self._cleanup_memory(context)

        except FileNotFoundError:
            # Handle missing file issues
            logger.warning("Required files missing for description update")
            self._create_default_description(context)

    def _cleanup_memory(self, context: ProcessingContext) -> None:
        """Clean up memory and retry with reduced processing."""
        # Implementation for memory cleanup
        pass

    def _create_default_description(self, context: ProcessingContext) -> None:
        """Create default description when features are unavailable."""
        # Implementation for default description creation
        pass
```

## Complete Usage Examples

### Basic Description Processing

```python
from rdetoolkit.processing.processors.descriptions import DescriptionUpdater
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.models.rde2types import RdeOutputResourcePath
from pathlib import Path

# Setup processing context
resource_paths = RdeOutputResourcePath(
    raw=Path("data/divided/0001/raw"),
    struct=Path("data/divided/0001/structured"),
    meta=Path("data/divided/0001/meta"),
    invoice=Path("data/divided/0001/invoice"),
    # ... other paths ...
)

context = ProcessingContext(
    resource_paths=resource_paths,
    invoice_dst_filepath=Path("data/divided/0001/invoice/invoice.json"),
    metadata_def_path=Path("data/tasksupport/metadata_def.json")
)

# Process descriptions
processor = DescriptionUpdater()
processor.process(context)
print("Description processing completed")
```

### Pipeline Integration with Multiple Processors

```python
from rdetoolkit.processing.pipeline import Pipeline
from rdetoolkit.processing.processors.descriptions import DescriptionUpdater
from rdetoolkit.processing.processors.files import FileProcessor
from rdetoolkit.processing.processors.validation import ValidationProcessor

# Create comprehensive processing pipeline
pipeline = Pipeline([
    FileProcessor(),           # Process raw files
    DescriptionUpdater(),      # Update descriptions
    ValidationProcessor(),     # Validate results
])

# Execute complete pipeline
try:
    pipeline.execute(context)
    print("Pipeline execution completed successfully")
except Exception as e:
    print(f"Pipeline execution failed: {e}")
```

### Custom Description Enhancement

```python
from rdetoolkit.processing.processors.descriptions import DescriptionUpdater
from rdetoolkit.processing.context import ProcessingContext
import json

class EnhancedDescriptionUpdater(DescriptionUpdater):
    """Enhanced description processor with additional features."""

    def process(self, context: ProcessingContext) -> None:
        """Enhanced processing with custom feature extraction."""

        # Pre-processing: extract custom features
        self._extract_custom_features(context)

        # Standard description processing
        super().process(context)

        # Post-processing: add metadata
        self._add_processing_metadata(context)

    def _extract_custom_features(self, context: ProcessingContext) -> None:
        """Extract custom features before description update."""

        custom_features = {
            "processing_timestamp": "2024-01-01T12:00:00Z",
            "feature_version": "1.0.0",
            "custom_tags": ["enhanced", "processed"]
        }

        # Save custom features
        feature_file = context.resource_paths.meta / "custom_features.json"
        with feature_file.open("w") as f:
            json.dump(custom_features, f, indent=2)

    def _add_processing_metadata(self, context: ProcessingContext) -> None:
        """Add processing metadata after description update."""

        metadata = {
            "description_updated": True,
            "processor_version": "2.0.0",
            "processing_notes": "Enhanced description processing completed"
        }

        # Save processing metadata
        metadata_file = context.resource_paths.meta / "processing_metadata.json"
        with metadata_file.open("w") as f:
            json.dump(metadata, f, indent=2)

# Usage
enhanced_processor = EnhancedDescriptionUpdater()
enhanced_processor.process(context)
```

## Performance Considerations

- **Error Suppression**: Minimal performance impact from exception handling
- **Memory Usage**: Low memory footprint for description processing
- **I/O Operations**: Optimized file operations for invoice updates
- **Pipeline Integration**: Efficient integration with other processors

## Best Practices

1. **Always Use in Pipelines**: Integrate with other processors for complete workflows
2. **Monitor Logs**: Check debug logs for processing status and any suppressed errors
3. **Validate Context**: Ensure required context attributes are available
4. **Handle Dependencies**: Ensure prerequisite processors have executed successfully

## See Also

- [Processing Pipeline](../../pipeline.md) - For pipeline framework documentation
- [Processing Context](../../context.md) - For context management details
- [Invoice Module](../../../invoicefile.md) - For invoice processing functions
- [Processor Base Class](../../pipeline.md#processor) - For base processor interface
