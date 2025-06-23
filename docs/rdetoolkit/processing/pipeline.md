# Pipeline Architecture

The `rdetoolkit.processing.pipeline` module provides the core pipeline architecture for sequential processing operations. It defines the base classes and interfaces for building modular, extensible processing workflows.

## Overview

The pipeline architecture enables:

- **Sequential Execution**: Processors execute in defined order
- **Shared Context**: All processors share the same processing context
- **Error Handling**: Comprehensive error handling and logging
- **Extensibility**: Easy addition of new processing steps
- **Status Reporting**: Detailed execution results and error reporting

## Classes

### Processor

Abstract base class for all processing operations. Each processor represents a single step in the processing pipeline.

```python
class Processor(ABC):
    """Abstract base class for processing operations."""
```

#### Methods

##### process

Execute the processing operation.

```python
@abstractmethod
def process(self, context: ProcessingContext) -> None
```

**Parameters:**
- `context` (ProcessingContext): The processing context containing all necessary information

**Raises:**
- Any exceptions that occur during processing should be allowed to propagate unless the processor is designed to handle specific error conditions

**Example:**
```python
class CustomProcessor(Processor):
    def process(self, context: ProcessingContext) -> None:
        # Access resources from context
        raw_files = context.resource_paths.rawfiles
        output_dir = context.resource_paths.struct

        # Perform processing operations
        for file in raw_files:
            process_file(file, output_dir)
```

##### get_name

Get the name of this processor for logging purposes.

```python
def get_name(self) -> str
```

**Returns:**
- `str`: The class name of the processor

**Example:**
```python
processor = CustomProcessor()
print(processor.get_name())  # "CustomProcessor"
```

### Pipeline

Pipeline for executing a sequence of processing operations. The pipeline executes processors in the order they were added, passing the same context to each processor.

```python
class Pipeline:
    """Pipeline for executing a sequence of processing operations."""
```

#### Constructor

```python
def __init__(self) -> None
```

Initialize an empty pipeline.

**Example:**
```python
pipeline = Pipeline()
```

#### Methods

##### add

Add a processor to the pipeline.

```python
def add(self, processor: Processor) -> Pipeline
```

**Parameters:**
- `processor` (Processor): The processor to add

**Returns:**
- `Pipeline`: Self for method chaining

**Example:**
```python
from rdetoolkit.processing.processors import FileCopier, DatasetRunner

pipeline = (Pipeline()
    .add(FileCopier())
    .add(DatasetRunner()))
```

##### execute

Execute all processors in the pipeline.

```python
def execute(self, context: ProcessingContext) -> WorkflowExecutionStatus
```

**Parameters:**
- `context` (ProcessingContext): The processing context

**Returns:**
- `WorkflowExecutionStatus`: Status indicating success or failure

**Raises:**
- Any exceptions from processors will propagate unless handled

**Example:**
```python
try:
    result = pipeline.execute(context)
    if result.status == "success":
        print(f"Pipeline completed: {result.title}")
    else:
        print(f"Pipeline failed: {result.error_message}")
except Exception as e:
    print(f"Pipeline execution error: {e}")
```

##### get_processor_count

Get the number of processors in this pipeline.

```python
def get_processor_count(self) -> int
```

**Returns:**
- `int`: Number of processors in the pipeline

**Example:**
```python
count = pipeline.get_processor_count()
print(f"Pipeline has {count} processors")
```

##### get_processor_names

Get the names of all processors in this pipeline.

```python
def get_processor_names(self) -> list[str]
```

**Returns:**
- `list[str]`: List of processor names

**Example:**
```python
names = pipeline.get_processor_names()
print(f"Processors: {', '.join(names)}")
```

## Usage Examples

### Creating a Custom Processor

```python
from rdetoolkit.processing.pipeline import Processor
from rdetoolkit.processing.context import ProcessingContext
import shutil

class FileBackupProcessor(Processor):
    """Processor that creates backups of raw files."""

    def process(self, context: ProcessingContext) -> None:
        backup_dir = context.resource_paths.raw.parent / "backup"
        backup_dir.mkdir(exist_ok=True)

        for raw_file in context.resource_paths.rawfiles:
            backup_path = backup_dir / raw_file.name
            shutil.copy2(raw_file, backup_path)

        print(f"Backed up {len(context.resource_paths.rawfiles)} files")
```

### Building a Custom Pipeline

```python
from rdetoolkit.processing import Pipeline
from rdetoolkit.processing.processors import (
    FileCopier, DatasetRunner, ThumbnailGenerator, InvoiceValidator
)

# Create custom pipeline
pipeline = (Pipeline()
    .add(FileBackupProcessor())  # Custom processor
    .add(FileCopier())           # Standard processor
    .add(DatasetRunner())        # Standard processor
    .add(ThumbnailGenerator())   # Standard processor
    .add(InvoiceValidator()))    # Standard processor

print(f"Pipeline has {pipeline.get_processor_count()} processors")
print(f"Processors: {pipeline.get_processor_names()}")
```

### Conditional Processing

```python
class ConditionalProcessor(Processor):
    """Processor that performs different operations based on context."""

    def process(self, context: ProcessingContext) -> None:
        config = context.srcpaths.config

        if context.is_excel_mode:
            self._process_excel_mode(context)
        elif context.is_smarttable_mode:
            self._process_smarttable_mode(context)
        else:
            self._process_standard_mode(context)

    def _process_excel_mode(self, context: ProcessingContext) -> None:
        excel_file = context.excel_invoice_file
        print(f"Processing Excel file: {excel_file}")
        # Excel-specific processing

    def _process_smarttable_mode(self, context: ProcessingContext) -> None:
        smarttable_file = context.smarttable_invoice_file
        print(f"Processing SmartTable file: {smarttable_file}")
        # SmartTable-specific processing

    def _process_standard_mode(self, context: ProcessingContext) -> None:
        print("Processing in standard mode")
        # Standard processing
```

### Error Handling in Processors

```python
class RobustProcessor(Processor):
    """Processor with comprehensive error handling."""

    def process(self, context: ProcessingContext) -> None:
        try:
            self._do_processing(context)
        except FileNotFoundError as e:
            # Handle specific errors gracefully
            print(f"Warning: File not found, skipping: {e}")
        except Exception as e:
            # Log error and re-raise for pipeline to handle
            print(f"Error in {self.get_name()}: {e}")
            raise

    def _do_processing(self, context: ProcessingContext) -> None:
        # Actual processing logic
        pass
```

### Pipeline Execution with Status Handling

```python
def execute_pipeline_with_monitoring(pipeline: Pipeline, context: ProcessingContext):
    """Execute pipeline with detailed status monitoring."""

    print(f"Starting pipeline with {pipeline.get_processor_count()} processors")
    print(f"Processors: {', '.join(pipeline.get_processor_names())}")

    try:
        result = pipeline.execute(context)

        if result.status == "success":
            print(f"✓ Pipeline completed successfully")
            print(f"  Title: {result.title}")
            print(f"  Mode: {result.mode}")
            print(f"  Target: {result.target}")
        else:
            print(f"✗ Pipeline failed")
            print(f"  Error Code: {result.error_code}")
            print(f"  Error Message: {result.error_message}")
            if result.stacktrace:
                print(f"  Stack Trace: {result.stacktrace}")

        return result

    except Exception as e:
        print(f"✗ Pipeline execution failed with exception: {e}")
        raise

# Usage
pipeline = Pipeline().add(FileCopier()).add(DatasetRunner())
result = execute_pipeline_with_monitoring(pipeline, context)
```

### Parallel Processing Design

```python
class ParallelFileProcessor(Processor):
    """Processor designed for parallel execution."""

    def process(self, context: ProcessingContext) -> None:
        import concurrent.futures

        raw_files = context.resource_paths.rawfiles
        output_dir = context.resource_paths.struct

        # Process files in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(self._process_single_file, file, output_dir)
                for file in raw_files
            ]

            # Wait for all tasks to complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"Error processing file: {e}")
                    raise

    def _process_single_file(self, file_path, output_dir):
        """Process a single file (thread-safe)."""
        # File processing logic here
        pass
```

## Design Patterns

### Template Method Pattern

```python
class TemplateProcessor(Processor):
    """Template processor with customizable steps."""

    def process(self, context: ProcessingContext) -> None:
        self._pre_process(context)
        self._main_process(context)
        self._post_process(context)

    def _pre_process(self, context: ProcessingContext) -> None:
        """Override in subclasses for pre-processing."""
        pass

    def _main_process(self, context: ProcessingContext) -> None:
        """Override in subclasses for main processing."""
        raise NotImplementedError

    def _post_process(self, context: ProcessingContext) -> None:
        """Override in subclasses for post-processing."""
        pass
```

### Strategy Pattern

```python
class StrategyProcessor(Processor):
    """Processor using strategy pattern for different operations."""

    def __init__(self, strategy_name: str):
        self._strategy_name = strategy_name
        self._strategies = {
            "compress": self._compress_strategy,
            "encrypt": self._encrypt_strategy,
            "archive": self._archive_strategy,
        }

    def process(self, context: ProcessingContext) -> None:
        strategy = self._strategies.get(self._strategy_name)
        if not strategy:
            raise ValueError(f"Unknown strategy: {self._strategy_name}")

        strategy(context)

    def _compress_strategy(self, context: ProcessingContext) -> None:
        # Compression logic
        pass

    def _encrypt_strategy(self, context: ProcessingContext) -> None:
        # Encryption logic
        pass

    def _archive_strategy(self, context: ProcessingContext) -> None:
        # Archiving logic
        pass
```

## Error Handling

### Pipeline Error Handling

The pipeline provides comprehensive error handling:

1. **Processor Errors**: Caught and converted to StructuredError
2. **Status Creation**: Automatic creation of success/failure status
3. **Logging**: Detailed logging of all operations
4. **Exception Propagation**: Controlled exception handling

### Custom Error Handling

```python
class ErrorHandlingProcessor(Processor):
    """Processor with custom error handling strategies."""

    def process(self, context: ProcessingContext) -> None:
        try:
            self._risky_operation(context)
        except FileNotFoundError:
            # Graceful degradation
            self._fallback_operation(context)
        except PermissionError as e:
            # Critical error - re-raise
            raise StructuredError(
                emsg=f"Permission denied: {e}",
                ecode=403,
                eobj=e
            )
        except Exception as e:
            # Log and re-raise
            logger.error(f"Unexpected error in {self.get_name()}: {e}")
            raise
```

## Performance Considerations

- **Stateless Design**: Processors should be stateless for thread safety
- **Resource Management**: Proper cleanup of resources in processors
- **Memory Usage**: Avoid loading large files entirely into memory
- **I/O Operations**: Use async operations for I/O-heavy processors
- **Caching**: Cache expensive operations where appropriate

## See Also

- [Processing Context](context.md) - Context management and state
- [Pipeline Factory](factories.md) - Automated pipeline creation
- [Processors](processors/index.md) - Individual processor implementations
- [Models](../models/result.md) - Status and result data structures
