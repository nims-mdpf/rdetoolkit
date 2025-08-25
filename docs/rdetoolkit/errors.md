# Errors API

## Purpose

This module handles error handling and exception management in RDEToolKit. It provides functionality for custom exception classes, error message management, exception capture and processing.

## Key Features

### Exception Management
- Exception capture and appropriate handling
- Simplified traceback display
- Dedicated handling for structured errors

### Error Handling
- Standardization of error messages
- Creation of job error log files
- Generic error processing functionality

---

::: src.rdetoolkit.errors.catch_exception_with_message

---

::: src.rdetoolkit.errors.format_simplified_traceback

---

::: src.rdetoolkit.errors.handle_exception

---

::: src.rdetoolkit.errors.handle_and_exit_on_structured_error

---

::: src.rdetoolkit.errors.handle_generic_error

---

::: src.rdetoolkit.errors.write_job_errorlog_file

---

## Practical Usage

### Using Exception Capture Decorator

```python title="exception_decorator.py"
from rdetoolkit.errors import catch_exception_with_message
from pathlib import Path

@catch_exception_with_message("Error occurred during data processing")
def process_data(data_file):
    """Data processing function (with error handling)"""
    if not data_file.exists():
        raise FileNotFoundError(f"File not found: {data_file}")
    
    # Data processing simulation
    with open(data_file, 'r') as f:
        content = f.read()
        if not content:
            raise ValueError("File is empty")
    
    return {"status": "success", "size": len(content)}

# Usage example
try:
    result = process_data(Path("data/sample.txt"))
    print(f"Processing result: {result}")
except Exception as e:
    print(f"Error: {e}")
```

### Using Simplified Traceback

```python title="simplified_traceback.py"
from rdetoolkit.errors import format_simplified_traceback
import traceback

def problematic_function():
    """Problematic function"""
    raise ValueError("Some error occurred")

def calling_function():
    """Calling function"""
    problematic_function()

try:
    calling_function()
except Exception as e:
    # Standard traceback
    print("=== Standard Traceback ===")
    traceback.print_exc()
    
    # Simplified traceback
    print("\n=== Simplified Traceback ===")
    simplified_tb = format_simplified_traceback()
    print(simplified_tb)
```

### Structured Error Handling

```python title="structured_error_handling.py"
from rdetoolkit.errors import handle_and_exit_on_structured_error, handle_exception
from rdetoolkit.exceptions import StructuredError

def risky_operation():
    """Risky operation"""
    # Raise structured error
    raise StructuredError("Error occurred in structured processing")

# Dedicated handling for structured errors
try:
    risky_operation()
except StructuredError as e:
    handle_and_exit_on_structured_error(e)
except Exception as e:
    handle_exception(e, "Unexpected error occurred")
```

### Creating Error Log Files

```python title="error_logging.py"
from rdetoolkit.errors import write_job_errorlog_file, handle_generic_error
from pathlib import Path
import traceback

def run_job_with_error_logging(job_id: str):
    """Job execution with error logging"""
    
    try:
        # Execute job (may cause errors)
        print(f"Starting job {job_id}")
        
        # Intentionally cause error
        if job_id == "error_job":
            raise RuntimeError("Error occurred during job execution")
        
        print(f"Job {job_id} completed successfully")
        return {"status": "success", "job_id": job_id}
        
    except Exception as e:
        # Create error log file
        error_log_path = Path(f"logs/job_{job_id}_error.log")
        error_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        write_job_errorlog_file(str(error_log_path), str(e), traceback.format_exc())
        
        # Generic error handling
        handle_generic_error(e, f"Error occurred in job {job_id}")
        
        return {"status": "error", "job_id": job_id, "error_log": str(error_log_path)}

# Usage example
jobs = ["normal_job", "error_job", "another_job"]

for job in jobs:
    print(f"\n--- Executing {job} ---")
    result = run_job_with_error_logging(job)
    print(f"Result: {result}")
```

### Comprehensive Error Handling System

```python title="comprehensive_error_handling.py"
from rdetoolkit.errors import (
    catch_exception_with_message, 
    handle_exception, 
    format_simplified_traceback,
    write_job_errorlog_file
)
from pathlib import Path
import logging

class ErrorHandlingSystem:
    """Comprehensive error handling system"""
    
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure logger
        self.logger = logging.getLogger("error_system")
        self.logger.setLevel(logging.INFO)
        
        # Add file handler
        handler = logging.FileHandler(self.log_dir / "system.log")
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    @catch_exception_with_message("Error occurred during system processing")
    def safe_execute(self, func, *args, **kwargs):
        """Safe function execution"""
        try:
            self.logger.info(f"Starting execution of function {func.__name__}")
            result = func(*args, **kwargs)
            self.logger.info(f"Function {func.__name__} completed successfully")
            return result
        except Exception as e:
            # Detailed error logging
            error_log_path = self.log_dir / f"error_{func.__name__}.log"
            simplified_tb = format_simplified_traceback()
            write_job_errorlog_file(str(error_log_path), str(e), simplified_tb)
            
            # Error handling
            handle_exception(e, f"Error occurred in function {func.__name__}")
            
            return {"status": "error", "function": func.__name__, "error": str(e)}

# Usage example
def sample_function(value):
    """Sample function"""
    if value < 0:
        raise ValueError("Negative values are not allowed")
    return value * 2

def another_function(data):
    """Another sample function"""
    if not data:
        raise RuntimeError("Data is empty")
    return len(data)

# Use error handling system
error_system = ErrorHandlingSystem(Path("logs/error_system"))

# Normal case
result1 = error_system.safe_execute(sample_function, 5)
print(f"Result 1: {result1}")

# Error case
result2 = error_system.safe_execute(sample_function, -1)
print(f"Result 2: {result2}")

result3 = error_system.safe_execute(another_function, [])
print(f"Result 3: {result3}")
```
