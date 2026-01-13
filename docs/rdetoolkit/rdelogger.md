# RdeLogger API

## Purpose

This module handles collection and management of execution logs in RDEToolKit's structured processing. It provides functionality for detailed log recording, level control, and output destination management.

## Key Features

### Log Management
- Collection of structured processing execution logs
- Efficient log output with delayed file creation
- Custom log configuration and decorators

### Output Control
- Switching between file output and console output
- Log handler management
- Detailed control of debug information

---

::: src.rdetoolkit.rdelogger.get_logger

---

::: src.rdetoolkit.rdelogger.CustomLog

---

::: src.rdetoolkit.rdelogger.log_decorator

---

## Practical Usage

### Basic Log Configuration

```python title="basic_logging.py"
from rdetoolkit.rdelogger import get_logger, CustomLog
from pathlib import Path

# Get basic logger
logger = get_logger("experiment_001")

# Output logs
logger.info("Starting experiment")
logger.debug("Debug information: Parameter verification")
logger.warning("Warning: Temperature exceeds threshold")
logger.error("Error: Data file not found")

print("Log configuration completed")
```

### Custom Log Configuration

```python title="custom_logging.py"
from rdetoolkit.rdelogger import CustomLog

# Configure user log (writes to data/logs/rdeuser.log)
logger = CustomLog().get_logger()

# Record logs
logger.info("Started user logging")
logger.info("Starting experimental data processing")

# Processing simulation
for i in range(5):
    logger.debug(f"Executing processing step {i+1}/5")
    
logger.info("Experimental data processing completed")
print("Recorded to log file: data/logs/rdeuser.log")
```

### Using Log Decorator

```python title="log_decorator_usage.py"
from rdetoolkit.rdelogger import CustomLog, log_decorator

# Configure logger for error reporting
logger = CustomLog().get_logger()

@log_decorator()
def process_data(data_file):
    """Data processing function (with log decorator)"""
    if not data_file.exists():
        raise FileNotFoundError(f"File not found: {data_file}")
    
    # Data processing simulation
    with open(data_file, 'r') as f:
        content = f.read()
        if not content:
            raise ValueError("File is empty")
    
    return {"status": "success", "size": len(content)}

@log_decorator()
def analyze_results(results):
    """Result analysis function (with log decorator)"""
    if not results:
        raise ValueError("Result data is empty")
    
    analysis = {
        "count": len(results),
        "average": sum(results) / len(results),
        "max": max(results),
        "min": min(results)
    }
    
    return analysis

# Usage example
from pathlib import Path

try:
    # Execute data processing (logs are automatically recorded)
    result = process_data(Path("data/sample.txt"))
    print(f"Processing result: {result}")
    
    # Execute result analysis (logs are automatically recorded)
    test_results = [1.2, 3.4, 5.6, 7.8, 9.0]
    analysis = analyze_results(test_results)
    print(f"Analysis result: {analysis}")
    
except Exception as exc:
    logger.error(f"Error occurred during processing: {exc}")
```

### Delayed file creation with `get_logger`

```python title="delayed_file_creation.py"
from rdetoolkit.rdelogger import get_logger
from pathlib import Path

# Usage example
log_path = Path("logs/lazy_experiment.log")
logger = get_logger("lazy_logger", file_path=log_path)

# Record logs (file is not created until actually written to)
logger.info("Started lazy log system")
logger.info("Starting experimental data processing")

# Process large amount of logs
for i in range(100):
    if i % 10 == 0:
        logger.info(f"Processing progress: {i}/100")
    logger.debug(f"Detailed log: Step {i}")

logger.info("Experiment completed")
print(f"Lazy log file: {log_path}")
```
