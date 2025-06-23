# RDE Logger Module

The `rdetoolkit.rdelogger` module provides specialized logging functionality for RDE (Research Data Exchange) structuring processes. This module offers lazy file handling, custom logging configurations, and decorators for comprehensive execution tracking.

## Overview

The rdelogger module provides robust logging capabilities tailored for RDE workflows:

- **Lazy File Handling**: Efficient file handler that creates log files only when needed
- **Custom Logger Configuration**: Specialized logger setup for RDE processes
- **Flexible Log Output**: Support for both file and console logging
- **Function Decorators**: Automatic logging of function execution start, end, and errors
- **Directory Management**: Automatic creation of log directories
- **Duplicate Prevention**: Smart handler management to avoid duplicate log entries

## Classes

### LazyFileHandler

A logging handler that lazily creates the actual FileHandler when needed, preventing unnecessary file creation when logging is configured but not used.

#### Constructor

```python
LazyFileHandler(filename: str, mode: str = "a", encoding: str = 'utf-8')
```

**Parameters:**
- `filename` (str): The path to the log file
- `mode` (str): The file opening mode (default: 'a' for append)
- `encoding` (str): The encoding to use for the file (default: 'utf-8')

#### Attributes

- `filename` (str): The path where the log file will be created
- `mode` (str): The file opening mode
- `encoding` (str): The file encoding
- `_handler` (logging.FileHandler | None): The underlying FileHandler instance, created on first use

#### Methods

##### _ensure_handler

Create the actual FileHandler if it hasn't been created yet.

```python
def _ensure_handler(self) -> None
```

**Returns:**
- `None`

**Functionality:**
- Creates necessary directories if they don't exist
- Initializes the FileHandler with specified filename, mode, and encoding
- Configures the handler with formatter and level settings from the parent handler

##### emit

Lazily create the actual FileHandler and delegate the emission of the log record.

```python
def emit(self, record: logging.LogRecord) -> None
```

**Parameters:**
- `record` (logging.LogRecord): The LogRecord instance containing all logging event information

**Returns:**
- `None`

**Example:**

```python
from rdetoolkit.rdelogger import LazyFileHandler
import logging

# Create a lazy file handler
handler = LazyFileHandler("data/logs/application.log", mode="a", encoding="utf-8")

# Setup logger with lazy handler
logger = logging.getLogger("example")
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

# Set formatter
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)

# The log file won't be created until the first log message
logger.info("This message will create the log file")  # File created here
logger.debug("Subsequent messages use the existing handler")
```

### CustomLog

A specialized class for creating custom loggers with user-defined log files and flexible output options.

#### Constructor

```python
CustomLog(name: str = "rdeuser")
```

**Parameters:**
- `name` (str): Logger name (default: "rdeuser")

#### Attributes

- `logger` (logging.Logger): The underlying logger instance

#### Methods

##### get_logger

Retrieve the configured logger instance with optional log output control.

```python
def get_logger(self, needlogs: bool = True) -> logging.Logger
```

**Parameters:**
- `needlogs` (bool): Whether logs should be written (default: True)

**Returns:**
- `logging.Logger`: The configured logger instance

**Functionality:**
- Creates log directory (`data/logs`) if it doesn't exist
- Sets up both console and file handlers when `needlogs=True`
- Uses NullHandler when `needlogs=False` to suppress output
- Prevents duplicate handler registration

##### _set_handler

Internal method to configure and add handlers to the logger.

```python
def _set_handler(self, handler: logging.Handler, verbose: bool) -> None
```

**Parameters:**
- `handler` (logging.Handler): The handler to configure and add
- `verbose` (bool): Whether to use verbose logging (DEBUG level vs INFO level)

**Returns:**
- `None`

**Example:**

```python
from rdetoolkit.rdelogger import CustomLog

# Create custom logger with logging enabled
custom_logger = CustomLog("my_module").get_logger(needlogs=True)
custom_logger.info("This will be logged to both console and file")
custom_logger.debug("Debug message will also be logged")

# Create custom logger with logging disabled
silent_logger = CustomLog("silent_module").get_logger(needlogs=False)
silent_logger.info("This message will be suppressed")

# Custom logger for specific module
class DataProcessor:
    def __init__(self):
        self.logger = CustomLog(f"{__name__}.DataProcessor").get_logger()

    def process_data(self, data):
        self.logger.info("Starting data processing")
        try:
            # Process data
            result = self._transform_data(data)
            self.logger.info(f"Successfully processed {len(result)} items")
            return result
        except Exception as e:
            self.logger.error(f"Data processing failed: {e}")
            raise

    def _transform_data(self, data):
        # Data transformation logic
        return [item.upper() for item in data if isinstance(item, str)]

# Usage
processor = DataProcessor()
result = processor.process_data(["hello", "world", 123, "test"])
```

## Functions

### get_logger

Create and configure a logger using Python's built-in logging module with RDE-specific optimizations.

```python
def get_logger(name: str, *, file_path: RdeFsPath | None = None, level: int = logging.DEBUG) -> logging.Logger
```

**Parameters:**
- `name` (str): The name of the logger (typically the module name, e.g., `__name__`)
- `file_path` (RdeFsPath | None): The file path where log messages will be written (optional)
- `level` (int): The logging level (default: `logging.DEBUG`)

**Returns:**
- `logging.Logger`: A configured logger instance

**Features:**
- Lazy file handler creation using `LazyFileHandler`
- Automatic directory creation for log files
- Duplicate handler prevention
- Standardized log formatting
- Flexible log level configuration

**Example:**

```python
from rdetoolkit.rdelogger import get_logger
import logging

# Create a logger with default DEBUG level
logger = get_logger(__name__, file_path="data/logs/rdesys.log")
logger.debug('This is a debug message.')
logger.info('This is an info message.')
logger.warning('This is a warning message.')
logger.error('This is an error message.')

# Create a logger with custom logging level (INFO)
logger_info = get_logger(__name__, file_path="data/logs/rdesys.log", level=logging.INFO)
logger_info.debug('This debug message will not appear')  # Below INFO level
logger_info.info('This info message will appear')

# Create a console-only logger (no file output)
console_logger = get_logger(__name__, file_path=None, level=logging.WARNING)
console_logger.warning('This will only appear on console')

# Module-specific logger
class WorkflowManager:
    def __init__(self):
        self.logger = get_logger(f"{__name__}.WorkflowManager",
                                file_path="data/logs/workflow.log")

    def execute_workflow(self, workflow_config):
        self.logger.info(f"Starting workflow: {workflow_config.get('name', 'unnamed')}")

        try:
            # Execute workflow steps
            for step in workflow_config.get('steps', []):
                self.logger.debug(f"Executing step: {step}")
                self._execute_step(step)

            self.logger.info("Workflow completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Workflow failed: {e}")
            return False

    def _execute_step(self, step):
        # Step execution logic
        pass

# Usage
manager = WorkflowManager()
config = {"name": "data_processing", "steps": ["validate", "transform", "save"]}
success = manager.execute_workflow(config)
```

### log_decorator

A decorator function that automatically logs the start and end of decorated functions, including error handling.

```python
def log_decorator() -> Callable
```

**Returns:**
- `Callable`: The decorator function

**Functionality:**
- Logs function start with function name
- Logs function completion
- Logs errors if exceptions occur
- Re-raises exceptions after logging
- Uses CustomLog for consistent formatting

**Example:**

```python
from rdetoolkit.rdelogger import log_decorator

@log_decorator()
def process_dataset(dataset_path: str) -> dict:
    """Process a dataset and return statistics."""
    print(f"Processing dataset: {dataset_path}")

    # Simulate processing
    import time
    time.sleep(1)

    # Return results
    return {"processed": True, "records": 1000}

@log_decorator()
def risky_operation() -> str:
    """Function that might raise an exception."""
    import random
    if random.random() < 0.5:
        raise ValueError("Random error occurred")
    return "Success"

# Usage examples
try:
    result = process_dataset("/data/sample.csv")
    print(f"Processing result: {result}")
except Exception as e:
    print(f"Processing failed: {e}")

# Example with error handling
for i in range(3):
    try:
        result = risky_operation()
        print(f"Attempt {i+1}: {result}")
        break
    except ValueError as e:
        print(f"Attempt {i+1} failed: {e}")

# Advanced usage with class methods
class DataAnalyzer:
    def __init__(self, name: str):
        self.name = name

    @log_decorator()
    def analyze_data(self, data: list) -> dict:
        """Analyze data and return statistics."""
        if not data:
            raise ValueError("Empty data provided")

        return {
            "count": len(data),
            "mean": sum(data) / len(data),
            "min": min(data),
            "max": max(data)
        }

    @log_decorator()
    def generate_report(self, analysis: dict) -> str:
        """Generate a formatted report."""
        return f"Analysis Report for {self.name}:\n" + \
               f"Count: {analysis['count']}\n" + \
               f"Mean: {analysis['mean']:.2f}\n" + \
               f"Range: {analysis['min']} - {analysis['max']}"

# Usage
analyzer = DataAnalyzer("Sample Dataset")
try:
    data = [1, 2, 3, 4, 5, 10, 15, 20]
    analysis = analyzer.analyze_data(data)
    report = analyzer.generate_report(analysis)
    print(report)
except Exception as e:
    print(f"Analysis failed: {e}")
```

## Complete Usage Examples

### Comprehensive Logging Setup

```python
from rdetoolkit.rdelogger import get_logger, CustomLog, log_decorator
from pathlib import Path
import logging
from typing import Dict, List, Any

class RDEProcessingPipeline:
    """Example pipeline with comprehensive logging setup."""

    def __init__(self, pipeline_name: str, log_level: int = logging.INFO):
        self.pipeline_name = pipeline_name

        # Setup multiple loggers for different purposes
        self.main_logger = get_logger(
            f"{__name__}.{self.__class__.__name__}",
            file_path=f"data/logs/{pipeline_name}_main.log",
            level=log_level
        )

        self.error_logger = get_logger(
            f"{__name__}.{self.__class__.__name__}.errors",
            file_path=f"data/logs/{pipeline_name}_errors.log",
            level=logging.ERROR
        )

        self.debug_logger = get_logger(
            f"{__name__}.{self.__class__.__name__}.debug",
            file_path=f"data/logs/{pipeline_name}_debug.log",
            level=logging.DEBUG
        )

        # Custom user logger for operational messages
        self.user_logger = CustomLog(f"{pipeline_name}_user").get_logger()

    @log_decorator()
    def initialize_pipeline(self) -> bool:
        """Initialize the processing pipeline."""
        self.main_logger.info(f"Initializing pipeline: {self.pipeline_name}")

        try:
            # Initialize components
            self._setup_directories()
            self._validate_configuration()

            self.main_logger.info("Pipeline initialization completed successfully")
            self.user_logger.info(f"Pipeline '{self.pipeline_name}' is ready for processing")
            return True

        except Exception as e:
            self.error_logger.error(f"Pipeline initialization failed: {e}")
            self.user_logger.error(f"Failed to initialize pipeline '{self.pipeline_name}': {e}")
            return False

    def _setup_directories(self):
        """Setup required directories."""
        directories = ["data/input", "data/output", "data/temp", "data/logs"]
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            self.debug_logger.debug(f"Created/verified directory: {directory}")

    def _validate_configuration(self):
        """Validate pipeline configuration."""
        # Configuration validation logic
        self.debug_logger.debug("Configuration validation completed")

    @log_decorator()
    def process_batch(self, input_files: List[str]) -> Dict[str, Any]:
        """Process a batch of input files."""
        self.main_logger.info(f"Starting batch processing of {len(input_files)} files")

        results = {
            "processed": 0,
            "failed": 0,
            "details": []
        }

        for file_path in input_files:
            try:
                self.debug_logger.debug(f"Processing file: {file_path}")
                result = self._process_single_file(file_path)

                results["processed"] += 1
                results["details"].append({
                    "file": file_path,
                    "status": "success",
                    "result": result
                })

                self.main_logger.info(f"Successfully processed: {file_path}")

            except Exception as e:
                results["failed"] += 1
                results["details"].append({
                    "file": file_path,
                    "status": "failed",
                    "error": str(e)
                })

                self.error_logger.error(f"Failed to process {file_path}: {e}")
                self.main_logger.warning(f"Skipping failed file: {file_path}")

        # Summary logging
        self.main_logger.info(f"Batch processing completed: {results['processed']} successful, {results['failed']} failed")
        self.user_logger.info(f"Batch processing summary: {results['processed']}/{len(input_files)} files processed successfully")

        return results

    def _process_single_file(self, file_path: str) -> Dict[str, Any]:
        """Process a single file."""
        # File processing logic
        import time
        time.sleep(0.1)  # Simulate processing time

        return {
            "processed_at": "2024-01-01T00:00:00Z",
            "size": 1024,
            "records": 100
        }

    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get processing statistics from log files."""
        self.debug_logger.debug("Collecting processing statistics")

        stats = {
            "pipeline_name": self.pipeline_name,
            "log_files": [],
            "total_size": 0
        }

        # Collect log file information
        log_dir = Path("data/logs")
        for log_file in log_dir.glob(f"{self.pipeline_name}_*.log"):
            if log_file.exists():
                size = log_file.stat().st_size
                stats["log_files"].append({
                    "name": log_file.name,
                    "size": size,
                    "path": str(log_file)
                })
                stats["total_size"] += size

        self.main_logger.info(f"Statistics collected: {len(stats['log_files'])} log files, total size: {stats['total_size']} bytes")
        return stats

# Usage example
def main():
    """Example usage of comprehensive logging setup."""

    # Create pipeline with INFO level logging
    pipeline = RDEProcessingPipeline("sample_processing", logging.INFO)

    # Initialize pipeline
    if not pipeline.initialize_pipeline():
        print("Failed to initialize pipeline")
        return False

    # Process sample files
    sample_files = [
        "data/input/file1.csv",
        "data/input/file2.json",
        "data/input/file3.txt"
    ]

    # Execute batch processing
    results = pipeline.process_batch(sample_files)

    # Get and display statistics
    stats = pipeline.get_processing_statistics()
    print(f"Processing completed. Statistics: {stats}")

    return results["failed"] == 0

if __name__ == "__main__":
    success = main()
    print(f"Pipeline execution {'succeeded' if success else 'failed'}")
```

### Advanced Logging with Context Management

```python
from rdetoolkit.rdelogger import get_logger, CustomLog
import logging
import contextlib
from typing import Generator, Any
import time
import json

class LoggingContext:
    """Context manager for structured logging with automatic cleanup."""

    def __init__(self, operation_name: str, log_level: int = logging.INFO):
        self.operation_name = operation_name
        self.log_level = log_level
        self.start_time = None
        self.logger = None
        self.context_data = {}

    def __enter__(self):
        self.start_time = time.time()
        self.logger = get_logger(
            f"context.{self.operation_name}",
            file_path=f"data/logs/context_{self.operation_name}.log",
            level=self.log_level
        )

        self.logger.info(f"=== Starting operation: {self.operation_name} ===")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time

        if exc_type is None:
            self.logger.info(f"=== Operation completed successfully: {self.operation_name} (Duration: {duration:.2f}s) ===")
        else:
            self.logger.error(f"=== Operation failed: {self.operation_name} (Duration: {duration:.2f}s) ===")
            self.logger.error(f"Exception: {exc_type.__name__}: {exc_val}")

        # Log context data if available
        if self.context_data:
            self.logger.info(f"Context data: {json.dumps(self.context_data, default=str)}")

    def add_context(self, key: str, value: Any):
        """Add context information to be logged."""
        self.context_data[key] = value
        self.logger.debug(f"Added context: {key} = {value}")

    def log_progress(self, message: str, **kwargs):
        """Log progress information with optional context."""
        if kwargs:
            self.context_data.update(kwargs)
        self.logger.info(f"Progress: {message}")

@contextlib.contextmanager
def logging_operation(operation_name: str, log_level: int = logging.INFO) -> Generator[LoggingContext, None, None]:
    """Context manager factory for logging operations."""
    context = LoggingContext(operation_name, log_level)
    with context:
        yield context

# Example usage with context managers
def process_data_with_context():
    """Example of using logging context managers."""

    with logging_operation("data_validation", logging.DEBUG) as ctx:
        ctx.add_context("input_files", 5)
        ctx.add_context("validation_rules", ["format", "schema", "completeness"])

        # Simulate validation process
        for i in range(5):
            ctx.log_progress(f"Validating file {i+1}/5", current_file=f"file_{i+1}.csv")
            time.sleep(0.1)

        ctx.add_context("validation_result", "all_passed")

    with logging_operation("data_transformation") as ctx:
        ctx.add_context("transformation_type", "normalize_and_aggregate")

        # Simulate transformation
        ctx.log_progress("Starting data normalization")
        time.sleep(0.2)

        ctx.log_progress("Performing aggregation")
        time.sleep(0.2)

        ctx.add_context("output_records", 1500)

    # Example with error handling
    with logging_operation("error_prone_operation") as ctx:
        ctx.add_context("operation_type", "risky_calculation")

        try:
            # Simulate an operation that might fail
            import random
            if random.random() < 0.3:
                raise ValueError("Simulated calculation error")

            ctx.log_progress("Calculation completed successfully")
            ctx.add_context("calculation_result", 42.7)

        except ValueError as e:
            ctx.add_context("error_details", str(e))
            # Error will be automatically logged by context manager
            raise

# Function-level logging with multiple loggers
class MultiLoggerProcessor:
    """Processor with multiple specialized loggers."""

    def __init__(self):
        # Different loggers for different purposes
        self.audit_logger = get_logger(
            "audit",
            file_path="data/logs/audit.log",
            level=logging.INFO
        )

        self.performance_logger = get_logger(
            "performance",
            file_path="data/logs/performance.log",
            level=logging.DEBUG
        )

        self.business_logger = CustomLog("business_events").get_logger()

    def process_transaction(self, transaction_id: str, amount: float):
        """Process a transaction with multi-level logging."""
        start_time = time.time()

        # Audit logging
        self.audit_logger.info(f"Transaction started: {transaction_id}, amount: {amount}")

        try:
            # Business logic simulation
            self.business_logger.info(f"Processing payment transaction: ${amount:.2f}")

            # Performance monitoring
            processing_start = time.time()
            time.sleep(0.1)  # Simulate processing
            processing_time = time.time() - processing_start

            self.performance_logger.debug(f"Transaction {transaction_id} processing time: {processing_time:.3f}s")

            # Success logging
            total_time = time.time() - start_time
            self.audit_logger.info(f"Transaction completed: {transaction_id}, total_time: {total_time:.3f}s")
            self.business_logger.info(f"Payment processed successfully: ${amount:.2f}")

            return {"status": "success", "transaction_id": transaction_id, "processing_time": total_time}

        except Exception as e:
            # Error logging across all loggers
            self.audit_logger.error(f"Transaction failed: {transaction_id}, error: {e}")
            self.business_logger.error(f"Payment processing failed: ${amount:.2f} - {e}")
            raise

# Usage examples
def demonstrate_advanced_logging():
    """Demonstrate advanced logging features."""

    print("=== Context Manager Logging ===")
    process_data_with_context()

    print("\n=== Multi-Logger Processing ===")
    processor = MultiLoggerProcessor()

    transactions = [
        ("TXN001", 99.99),
        ("TXN002", 1500.00),
        ("TXN003", 25.50)
    ]

    for txn_id, amount in transactions:
        try:
            result = processor.process_transaction(txn_id, amount)
            print(f"Transaction result: {result}")
        except Exception as e:
            print(f"Transaction {txn_id} failed: {e}")

if __name__ == "__main__":
    demonstrate_advanced_logging()
```

## Error Handling

### Exception Handling in Logging

The rdelogger module handles various error conditions gracefully:

```python
from rdetoolkit.rdelogger import get_logger, LazyFileHandler
import logging
import os

def robust_logging_setup():
    """Example of robust logging setup with error handling."""

    try:
        # Attempt to create logger with file output
        logger = get_logger(__name__, file_path="data/logs/application.log")
        logger.info("Logger created successfully")
        return logger

    except PermissionError:
        # Fall back to console-only logging
        print("Warning: Cannot write to log file, using console logging")
        logger = get_logger(__name__, file_path=None)
        logger.warning("Log file creation failed, using console output only")
        return logger

    except Exception as e:
        # Ultimate fallback
        print(f"Error setting up logging: {e}")
        logger = logging.getLogger(__name__)
        logger.addHandler(logging.StreamHandler())
        return logger

# Handling logging errors in decorators
from rdetoolkit.rdelogger import log_decorator

def safe_log_decorator():
    """A safer version of log_decorator with error handling."""

    def _safe_log_decorator(func):
        def wrapper(*args, **kwargs):
            try:
                logger = get_logger(func.__module__)
                logger.info(f"{func.__name__:15} --> Start")

                try:
                    result = func(*args, **kwargs)
                    logger.info(f"{func.__name__:15} <-- End (Success)")
                    return result
                except Exception as func_error:
                    logger.error(f"{func.__name__:15} !!! Error: {func_error}")
                    raise

            except Exception as log_error:
                # If logging fails, still execute the function
                print(f"Logging error for {func.__name__}: {log_error}")
                return func(*args, **kwargs)

        return wrapper
    return _safe_log_decorator

# Usage with error handling
@safe_log_decorator()
def potentially_failing_function():
    """Function that might fail."""
    import random
    if random.random() < 0.5:
        raise ValueError("Random failure")
    return "Success"
```

### Best Practices for Error Handling

1. **Graceful Degradation**:
   ```python
   def setup_logging_with_fallback(preferred_path: str):
       """Setup logging with multiple fallback options."""
       fallback_paths = [
           preferred_path,
           "logs/fallback.log",
           "/tmp/application.log",
           None  # Console only
       ]

       for path in fallback_paths:
           try:
               logger = get_logger(__name__, file_path=path)
               if path:
                   logger.info(f"Logging initialized with file: {path}")
               else:
                   logger.info("Logging initialized (console only)")
               return logger
           except Exception as e:
               if path is None:
                   # Last resort - basic console logging
                   logger = logging.getLogger(__name__)
                   logger.addHandler(logging.StreamHandler())
                   logger.error(f"All logging setup attempts failed: {e}")
                   return logger
               continue
   ```

2. **Resource Cleanup**:
   ```python
   import atexit

   def setup_logging_with_cleanup():
       """Setup logging with proper cleanup registration."""
       logger = get_logger(__name__, file_path="data/logs/app.log")

       def cleanup_logging():
           """Cleanup function for logging resources."""
           for handler in logger.handlers:
               if hasattr(handler, 'close'):
                   handler.close()

       # Register cleanup function
       atexit.register(cleanup_logging)
       return logger
   ```

## Performance Notes

### Optimization Features

1. **Lazy File Creation**: LazyFileHandler only creates files when log messages are actually emitted
2. **Handler Deduplication**: Automatic prevention of duplicate handlers to avoid redundant processing
3. **Efficient Formatting**: Standardized formatters reduce overhead
4. **Level-based Filtering**: Messages below the configured level are filtered early

### Performance Best Practices

```python
# Efficient logging patterns
def efficient_logging_example():
    """Demonstrate efficient logging patterns."""

    logger = get_logger(__name__, file_path="data/logs/efficient.log", level=logging.INFO)

    # Good: Use appropriate log levels
    logger.debug("Detailed debug info")  # Won't be processed if level is INFO
    logger.info("Important information")  # Will be processed

    # Good: Use lazy evaluation for expensive operations
    def expensive_calculation():
        import time
        time.sleep(1)
        return "expensive_result"

    # Only call expensive_calculation if DEBUG level is enabled
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Debug info: {expensive_calculation()}")

    # Good: Use string formatting in log calls
    user_id = 12345
    action = "login"
    logger.info("User %s performed action: %s", user_id, action)

    # Avoid: String concatenation before log call
    # logger.info("User " + str(user_id) + " performed action: " + action)  # Always executes

# Batch logging for high-volume scenarios
class BatchLogger:
    """Logger that batches messages for high-volume scenarios."""

    def __init__(self, batch_size: int = 100):
        self.logger = get_logger(__name__, file_path="data/logs/batch.log")
        self.batch_size = batch_size
        self.message_buffer = []

    def add_message(self, level: int, message: str):
        """Add message to buffer."""
        self.message_buffer.append((level, message))

        if len(self.message_buffer) >= self.batch_size:
            self.flush()

    def flush(self):
        """Flush all buffered messages."""
        for level, message in self.message_buffer:
            self.logger.log(level, message)
        self.message_buffer.clear()

    def __del__(self):
        """Ensure messages are flushed on destruction."""
        if self.message_buffer:
            self.flush()
```

## See Also

- [Core Module](core.md) - For directory management and file operations
- [Workflows Module](workflows.md) - For workflow execution logging
- [Mode Processing](modeproc.md) - For processing mode logging
- [Models - RDE2 Types](models/rde2types.md) - For RdeFsPath type definitions
- [Error Handling](errors.md) - For error management utilities
- [Usage - CLI](../usage/cli.md) - For command-line logging examples
- [Usage - Structured Process](../usage/structured_process/structured.md) - For process logging
- [Usage - Error Handling](../usage/structured_process/errorhandling.md) - For error logging strategies
