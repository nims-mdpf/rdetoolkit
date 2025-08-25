# Config API

## Purpose

This module handles loading, parsing, and managing configuration files for RDEToolKit. It supports YAML and TOML format configuration files and provides configuration information that controls the behavior of the entire system.

## Key Features

### Configuration File Parsing
- Automatic detection and loading of YAML and TOML format configuration files
- Configuration file search and discovery
- Configuration information extraction from pyproject.toml

### Configuration Management
- Generation of structured configuration objects
- Application of default configuration values
- Configuration validation and error handling

---

::: src.rdetoolkit.config.parse_config_file

---

::: src.rdetoolkit.config.find_config_files

---

::: src.rdetoolkit.config.get_config

---

::: src.rdetoolkit.config.load_config

---

::: src.rdetoolkit.config.is_toml

---

::: src.rdetoolkit.config.is_yaml

---

::: src.rdetoolkit.config.get_pyproject_toml

---

## Practical Usage

### Basic Configuration File Loading

```python title="basic_config.py"
from rdetoolkit.config import parse_config_file, load_config
from pathlib import Path

# Parse configuration file
config = parse_config_file()
print(f"System settings: {config.system}")
print(f"Extended mode: {config.system.extended_mode}")
print(f"Save raw data: {config.system.save_raw}")

# Load configuration from specific directory
project_dir = Path("/path/to/project")
config = load_config(project_dir)
```

### Configuration File Search and Detection

```python title="config_detection.py"
from rdetoolkit.config import find_config_files, is_yaml, is_toml
from pathlib import Path

# Search for configuration files
config_dir = Path("./config")
config_files = find_config_files(config_dir)
print(f"Found configuration files: {config_files}")

# Detect file format
for config_file in config_files:
    if is_yaml(config_file):
        print(f"{config_file} is a YAML file")
    elif is_toml(config_file):
        print(f"{config_file} is a TOML file")
```

### Configuration Retrieval from pyproject.toml

```python title="pyproject_config.py"
from rdetoolkit.config import get_pyproject_toml
from pathlib import Path

# Load pyproject.toml
project_root = Path(".")
pyproject_data = get_pyproject_toml(project_root)

if pyproject_data:
    print(f"Project name: {pyproject_data.get('project', {}).get('name')}")
    print(f"Version: {pyproject_data.get('project', {}).get('version')}")
```
