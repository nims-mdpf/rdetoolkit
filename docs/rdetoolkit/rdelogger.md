# RdeLogger API

## Purpose

This module handles collection and management of execution logs in RDEToolKit's structured processing. It provides functionality for detailed log recording, level control, and output destination management.

## Key Features

### Log Management
- Collection of structured processing execution logs
- Efficient log output through lazy file handlers
- Custom log configuration and decorators

### Output Control
- Switching between file output and console output
- Log handler management
- Detailed control of debug information

---

::: src.rdetoolkit.rdelogger.LazyFileHandler

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
from pathlib import Path

# Configure custom log
log_file = Path("logs/experiment.log")
log_file.parent.mkdir(parents=True, exist_ok=True)

custom_log = CustomLog()
logger = custom_log.get_logger("custom_logger", str(log_file))

# Record logs
logger.info("Started custom logging")
logger.info("Starting experimental data processing")

# Processing simulation
for i in range(5):
    logger.debug(f"Executing processing step {i+1}/5")
    
logger.info("Experimental data processing completed")
print(f"Recorded to log file: {log_file}")
```

### Using Log Decorator

```python title="log_decorator_usage.py"
from rdetoolkit.rdelogger import log_decorator, get_logger

# Configure logger
logger = get_logger("decorated_functions")

@log_decorator(logger)
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

@log_decorator(logger)
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
    
except Exception as e:
    logger.error(f"Error occurred during processing: {e}")
```

### Utilizing Lazy File Handler

```python title="lazy_file_handler.py"
from rdetoolkit.rdelogger import LazyFileHandler, get_logger
import logging
from pathlib import Path

def setup_lazy_logging(log_file_path: Path):
    """Log configuration using lazy file handler"""
    
    # Create lazy file handler
    lazy_handler = LazyFileHandler(str(log_file_path))
    lazy_handler.setLevel(logging.INFO)
    
    # Configure formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    lazy_handler.setFormatter(formatter)
    
    # Configure logger
    logger = get_logger("lazy_logger")
    logger.addHandler(lazy_handler)
    logger.setLevel(logging.INFO)
    
    return logger

# Usage example
log_path = Path("logs/lazy_experiment.log")
logger = setup_lazy_logging(log_path)

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
