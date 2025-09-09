# Error Handling Methods

## Purpose

This document explains how to handle errors that may occur during RDE structured processing. You will learn common error patterns and effective troubleshooting procedures.

## Prerequisites

- Understanding of basic RDEToolKit usage
- Basic knowledge of Python error handling
- Understanding of how to read log files

## Steps

### 1. Identify Error Types

First, identify the type of error that occurred:

```python title="Error Information Retrieval"
import traceback

def identify_error():
    try:
        # Execute structured processing
        result = workflows.run(custom_dataset_function)
    except Exception as e:
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        print(f"Detailed Traceback:")
        traceback.print_exc()
```

### 2. Resolve File-Related Errors

#### File Not Found Errors

```python title="File Existence Check"
import os

def check_file_exists(file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        # Suggest alternative file paths
        alternatives = [
            file_path.replace('.csv', '.xlsx'),
            os.path.join('data', os.path.basename(file_path))
        ]
        for alt in alternatives:
            if os.path.exists(alt):
                print(f"Alternative file found: {alt}")
                return alt
        return None
    return file_path
```

#### Permission Error Resolution

```shell title="Permission Fixes"
# Set directory permissions
chmod 755 data/
chmod 755 data/structured/
chmod 755 data/logs/

# Set file permissions
chmod 644 data/invoice/invoice.json
chmod 644 data/tasksupport/*.json
```

### 3. Resolve Configuration File Errors

#### JSON Format Validation

```python title="JSON Validation"
import json

def validate_json_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✅ {file_path} is valid JSON")
        return data
    except json.JSONDecodeError as e:
        print(f"❌ JSON format error in {file_path}:")
        print(f"   Line {e.lineno}, Column {e.colno}: {e.msg}")
        return None
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return None
```

#### Schema Validation Error Handling

```python title="Schema Validation"
def validate_against_schema(data, schema_path):
    try:
        with open(schema_path, 'r') as f:
            schema = json.load(f)
        
        # Check required fields
        if 'required' in schema:
            for field in schema['required']:
                if field not in data:
                    print(f"❌ Missing required field: {field}")
                    return False
        
        print("✅ Schema validation passed")
        return True
    except Exception as e:
        print(f"❌ Schema validation error: {e}")
        return False
```

### 4. Use RDEToolKit Error Handling Features

#### Using StructuredError

```python title="Structured Error Implementation"
from rdetoolkit.exceptions import StructuredError

def dataset_with_error_handling(srcpaths, resource_paths):
    try:
        # File reading process
        config = read_config_file("config.json")
    except FileNotFoundError as e:
        # Set RDE error information
        raise StructuredError(
            "Configuration file not found", 
            ecode=3, 
            eobj=e
        ) from e
    except json.JSONDecodeError as e:
        raise StructuredError(
            "Configuration file format is incorrect", 
            ecode=4, 
            eobj=e
        ) from e
    
    # Normal processing
    return process_data(config)
```

#### Using Error Decorator

```python title="Error Decorator"
from rdetoolkit.errors import catch_exception_with_message

@catch_exception_with_message(
    error_message="An unexpected error occurred", 
    error_code=100, 
    verbose=False
)
def dataset_with_decorator(srcpaths, resource_paths):
    # Processing logic
    return process_data()
```

### 5. Debug Using Logs

#### Detailed Log Configuration

```python title="Log Configuration"
import logging

def setup_detailed_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('debug.log'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    return logger

def debug_processing(srcpaths, resource_paths):
    logger = setup_detailed_logging()
    
    logger.info("Starting structured processing")
    logger.debug(f"Input paths: {srcpaths}")
    logger.debug(f"Output paths: {resource_paths}")
    
    try:
        # Execute processing
        result = your_processing_logic()
        logger.info("Processing completed successfully")
        return result
    except Exception as e:
        logger.error(f"Error occurred during processing: {e}")
        logger.debug("Detailed traceback:", exc_info=True)
        raise
```

## Verification

After resolving errors, verify the following:

### Check job.failed File

```python title="Error File Check"
def check_error_file():
    error_file = "job.failed"
    if os.path.exists(error_file):
        with open(error_file, 'r') as f:
            content = f.read()
        print(f"Error information:\n{content}")
        return False
    else:
        print("✅ No error file exists (normal completion)")
        return True
```

### Check Log Files

```shell title="Log Check Commands"
# Check latest log entries
tail -n 20 data/logs/rdesys.log

# Search for error messages
grep -i "error" data/logs/rdesys.log

# Search for warning messages
grep -i "warning" data/logs/rdesys.log
```

## Troubleshooting Checklist

### Pre-Execution Check

- [ ] All required files exist
- [ ] File permissions are properly set
- [ ] Required Python packages are installed
- [ ] Configuration file format is correct
- [ ] Input data format matches expected format

### Error Occurrence Check

- [ ] Read error messages in detail
- [ ] Check job.failed file
- [ ] Check log files
- [ ] Verify input data content
- [ ] Verify configuration file content
- [ ] Ensure sufficient disk space

### Post-Resolution Check

- [ ] Verify the same error doesn't recur
- [ ] Check that other functions are not affected
- [ ] Verify appropriate information is logged
- [ ] Confirm job.failed file is not generated

## Related Information

To learn more about error handling, refer to the following documents:

- Understand processing phases where errors occur in [Structured Processing Concepts](structured.en.md)
- Learn how to handle configuration-related errors in [Configuration Files](../config/config.en.md)
- Check data validation error handling in [Validation](../validation.en.md)
- Learn about LLM/AI-friendly stacktrace formatting in [Traceback System](traceback.en.md)
