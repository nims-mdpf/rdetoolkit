# FileOps API

## Purpose

This module provides a unified interface for file operations in RDEToolKit. It enables reading and writing of various file formats such as JSON, YAML, TOML, and CSV through a concise and consistent API.

## Key Features

### File Reading
- Reading JSON, YAML, TOML, and CSV files
- Automatic encoding detection and processing
- Error handling and exception processing

### File Writing
- File output in various formats
- Saving in appropriate formats
- Character encoding management

---

::: src.rdetoolkit.fileops.readf_json

---

::: src.rdetoolkit.fileops.writef_json

---

## Practical Usage

### JSON File Operations

```python title="json_operations.py"
from rdetoolkit.fileops import readf_json, writef_json
from pathlib import Path

# Read JSON file
config_path = Path("config/settings.json")
config_data = readf_json(config_path)
print(f"Configuration data: {config_data}")

# Write JSON file
output_data = {
    "experiment_id": "EXP001",
    "parameters": {
        "temperature": 25.0,
        "pressure": 1013.25,
        "humidity": 60
    },
    "results": [1.2, 3.4, 5.6, 7.8]
}

output_path = Path("results/experiment_001.json")
writef_json(output_data, output_path)
print(f"Results saved to {output_path}")
```

### File Operations with Error Handling

```python title="safe_file_operations.py"
from rdetoolkit.fileops import readf_json, writef_json
from pathlib import Path
import json

def safe_read_json(file_path: Path):
    """Safe JSON reading"""
    try:
        data = readf_json(file_path)
        print(f"✓ JSON read successful: {file_path}")
        return data
    except FileNotFoundError:
        print(f"✗ File not found: {file_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"✗ JSON format error: {e}")
        return None

def safe_write_json(data, file_path: Path):
    """Safe JSON writing"""
    try:
        # Create directory
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        writef_json(data, file_path)
        print(f"✓ JSON write successful: {file_path}")
        return True
    except Exception as e:
        print(f"✗ JSON write error: {e}")
        return False

# Usage example
config_data = safe_read_json(Path("config/experiment.json"))
if config_data:
    # Update data
    config_data["last_updated"] = "2024-01-01T10:00:00Z"
    safe_write_json(config_data, Path("config/experiment_updated.json"))
```
