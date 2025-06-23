# Configuration Module

The `rdetoolkit.config` module provides comprehensive configuration management functionality for RDE (Research Data Exchange) processing workflows. This module handles loading, parsing, and validation of configuration files in multiple formats, with automatic discovery and flexible configuration options.

## Overview

The config module offers robust configuration management capabilities:

- **Multiple Format Support**: Support for YAML, YML, and TOML configuration files
- **Automatic Discovery**: Intelligent configuration file discovery in directories
- **Validation**: Pydantic-based configuration validation with detailed error reporting
- **Priority Loading**: Configurable loading priority for different file types
- **Default Configurations**: Fallback to default configurations when files are missing
- **Project Integration**: Special support for pyproject.toml configuration sections
- **Path Flexibility**: Support for both string and Path object inputs

## Constants

- `CONFIG_FILE`: `["rdeconfig.yaml", "rdeconfig.yml"]` - Standard configuration filenames
- `PYPROJECT_CONFIG_FILES`: `["pyproject.toml"]` - Project configuration filenames
- `CONFIG_FILES`: Combined list of all supported configuration filenames

## Functions

### parse_config_file

Parse a configuration file and return a validated Config object.

```python
def parse_config_file(*, path: str | None = None) -> Config
```

**Parameters:**
- `path` (str | None): Path to the configuration file (optional)

**Returns:**
- `Config`: Parsed and validated configuration object

**Raises:**
- `FileNotFoundError`: If the specified configuration file does not exist

**File Loading Priority:**
1. If `path` is provided with `.toml` extension: Read as TOML file
2. If `path` is provided with `.yaml`/`.yml` extension: Read as YAML file
3. If `path` is None: Search for `pyproject.toml` in current working directory
4. If file not found or invalid: Return default Config object

**Supported Configuration Files:**
- `rdeconfig.yaml`
- `rdeconfig.yml`
- `pyproject.toml`

**Example:**

```python
from rdetoolkit.config import parse_config_file

# Parse specific configuration file
config = parse_config_file(path="config/rdeconfig.yaml")
print(f"Extended mode: {config.system.extended_mode}")

# Parse default pyproject.toml
default_config = parse_config_file()
print(f"Save raw: {config.system.save_raw}")

# Handle missing configuration gracefully
try:
    config = parse_config_file(path="nonexistent.yaml")
    # Returns default config instead of raising error
except FileNotFoundError:
    print("Configuration file not found")
```

### find_config_files

Find and return a list of configuration files in a specified directory.

```python
def find_config_files(target_dir_path: RdeFsPath) -> list[str]
```

**Parameters:**
- `target_dir_path` (RdeFsPath): Directory path to search for configuration files

**Returns:**
- `list[str]`: Sorted list of configuration file paths

**Sorting Priority:**
- Files are sorted by type: TOML files first, then YAML files
- Within each type, files are sorted alphabetically

**Example:**

```python
from rdetoolkit.config import find_config_files
from pathlib import Path

# Find configuration files in directory
config_dir = Path("data/tasksupport")
config_files = find_config_files(config_dir)

for config_file in config_files:
    print(f"Found config: {config_file}")

# Check if any configuration files exist
if config_files:
    print(f"Found {len(config_files)} configuration files")
else:
    print("No configuration files found")
```

### get_config

Retrieve configuration from a specified directory with fallback options.

```python
def get_config(target_dir_path: RdeFsPath) -> Config | None
```

**Parameters:**
- `target_dir_path` (RdeFsPath): Directory path to search for configuration

**Returns:**
- `Config | None`: First valid configuration found, or None if no valid configuration exists

**Raises:**
- `ValueError`: If configuration file exists but contains invalid data

**Search Strategy:**
1. Search for configuration files in the specified directory
2. Parse each found file until a valid configuration is found
3. If no valid configuration in directory, check for `pyproject.toml` in current working directory
4. Return the first valid configuration, or None if none found

**Example:**

```python
from rdetoolkit.config import get_config
from pathlib import Path

# Get configuration from tasksupport directory
config = get_config("data/tasksupport")

if config:
    print(f"Configuration loaded successfully")
    print(f"Extended mode: {config.system.extended_mode}")
    print(f"Save raw files: {config.system.save_raw}")
else:
    print("No valid configuration found")

# Handle validation errors
try:
    config = get_config("data/invalid_config")
except ValueError as e:
    print(f"Configuration validation failed: {e}")
```

### load_config

Load configuration for RDE Toolkit with optional override.

```python
def load_config(tasksupport_path: RdeFsPath, *, config: Config | None = None) -> Config
```

**Parameters:**
- `tasksupport_path` (RdeFsPath): Path to the tasksupport directory
- `config` (Config | None): Optional existing configuration object to use instead

**Returns:**
- `Config`: Loaded configuration object (never None)

**Behavior:**
- If `config` parameter is provided, returns that configuration
- Otherwise, attempts to load configuration from `tasksupport_path`
- If no configuration is found, returns default Config object
- Guarantees non-None return value

**Example:**

```python
from rdetoolkit.config import load_config
from rdetoolkit.models.config import Config, SystemSettings

# Load configuration from tasksupport directory
config = load_config("data/tasksupport")

# Load with custom configuration override
custom_config = Config(
    system=SystemSettings(extended_mode="rdeformat", save_raw=True)
)
config = load_config("data/tasksupport", config=custom_config)

# Always returns a valid configuration
print(f"Extended mode: {config.system.extended_mode}")
```

### Utility Functions

#### is_toml

Check if a filename has a TOML extension.

```python
def is_toml(filename: str) -> bool
```

**Parameters:**
- `filename` (str): Filename to check

**Returns:**
- `bool`: True if filename ends with `.toml`, False otherwise

#### is_yaml

Check if a filename has a YAML extension.

```python
def is_yaml(filename: str) -> bool
```

**Parameters:**
- `filename` (str): Filename to check

**Returns:**
- `bool`: True if filename ends with `.yaml` or `.yml`, False otherwise

#### get_pyproject_toml

Get the pyproject.toml file path from the current working directory.

```python
def get_pyproject_toml() -> Path | None
```

**Returns:**
- `Path | None`: Path to pyproject.toml if it exists, None otherwise

**Example:**

```python
from rdetoolkit.config import is_toml, is_yaml, get_pyproject_toml

# Check file types
print(is_toml("config.toml"))        # True
print(is_yaml("config.yaml"))       # True
print(is_yaml("config.yml"))        # True
print(is_toml("config.json"))       # False

# Get pyproject.toml path
pyproject_path = get_pyproject_toml()
if pyproject_path:
    print(f"Found pyproject.toml at: {pyproject_path}")
else:
    print("No pyproject.toml found in current directory")
```

## Configuration File Formats

### YAML Configuration (rdeconfig.yaml/rdeconfig.yml)

```yaml
system:
  extended_mode: "rdeformat"
  save_raw: true
  save_main_image: false
  save_thumbnail_image: true
  save_nonshared_raw: false
  magic_variable: true

multidata_tile:
  ignore_errors: false
```

### TOML Configuration (pyproject.toml)

```toml
[tool.rdetoolkit.system]
extended_mode = "multidatatile"
save_raw = true
save_main_image = false
save_thumbnail_image = true
save_nonshared_raw = false
magic_variable = true

[tool.rdetoolkit.multidata_tile]
ignore_errors = false
```

## Configuration Loading Examples

### Basic Configuration Loading

```python
from rdetoolkit.config import load_config, parse_config_file

# Load from tasksupport directory
config = load_config("data/tasksupport")

# Parse specific file
config = parse_config_file(path="config/custom.yaml")

# Use configuration
if config.system.extended_mode == "rdeformat":
    print("Using RDE format mode")

if config.system.save_raw:
    print("Raw files will be saved")
```

### Configuration Discovery and Validation

```python
from rdetoolkit.config import find_config_files, get_config
from pathlib import Path

def setup_configuration(config_dir: str):
    """Setup configuration with discovery and validation."""

    # Find available configuration files
    config_files = find_config_files(config_dir)
    print(f"Available configurations: {config_files}")

    # Load configuration with validation
    try:
        config = get_config(config_dir)
        if config:
            print("✓ Configuration loaded successfully")
            return config
        else:
            print("⚠ No configuration found, using defaults")
            from rdetoolkit.models.config import Config
            return Config()

    except ValueError as e:
        print(f"✗ Configuration validation failed: {e}")
        return None

# Usage
config = setup_configuration("data/tasksupport")
if config:
    print(f"Extended mode: {config.system.extended_mode}")
```

### Configuration Priority and Fallback

```python
from rdetoolkit.config import load_config
from rdetoolkit.models.config import Config, SystemSettings, MultiDataTileSettings

def load_configuration_with_fallback(primary_path: str, fallback_path: str = None):
    """Load configuration with fallback options."""

    # Try primary configuration
    try:
        config = load_config(primary_path)
        if config.system.extended_mode or config.system.save_raw:
            print(f"✓ Loaded configuration from: {primary_path}")
            return config
    except Exception as e:
        print(f"⚠ Primary configuration failed: {e}")

    # Try fallback configuration
    if fallback_path:
        try:
            config = load_config(fallback_path)
            print(f"✓ Loaded fallback configuration from: {fallback_path}")
            return config
        except Exception as e:
            print(f"⚠ Fallback configuration failed: {e}")

    # Use programmatic default
    print("Using programmatic default configuration")
    return Config(
        system=SystemSettings(
            extended_mode="invoice",
            save_raw=True,
            magic_variable=True
        ),
        multidata_tile=MultiDataTileSettings(
            ignore_errors=False
        )
    )

# Usage
config = load_configuration_with_fallback(
    primary_path="data/tasksupport",
    fallback_path="config"
)
```

## Error Handling

### Configuration Validation Errors

```python
from rdetoolkit.config import get_config
from pydantic import ValidationError

def safe_config_loading(config_path: str):
    """Safely load configuration with comprehensive error handling."""

    try:
        config = get_config(config_path)
        if config is None:
            print("No configuration found")
            return None

        # Validate specific settings
        if config.system.extended_mode not in ["invoice", "rdeformat", "multidatatile"]:
            print(f"Warning: Unknown extended_mode: {config.system.extended_mode}")

        return config

    except ValueError as e:
        print(f"Configuration validation error: {e}")
        return None
    except FileNotFoundError as e:
        print(f"Configuration file not found: {e}")
        return None
    except Exception as e:
        print(f"Unexpected configuration error: {e}")
        return None

# Usage
config = safe_config_loading("data/tasksupport")
if config:
    print("Configuration loaded successfully")
else:
    print("Using default configuration")
```

### File Format Detection and Handling

```python
from rdetoolkit.config import is_toml, is_yaml, parse_config_file

def load_config_by_type(config_file: str):
    """Load configuration with format-specific handling."""

    if is_toml(config_file):
        print(f"Loading TOML configuration: {config_file}")
        try:
            return parse_config_file(path=config_file)
        except Exception as e:
            print(f"TOML parsing failed: {e}")
            return None

    elif is_yaml(config_file):
        print(f"Loading YAML configuration: {config_file}")
        try:
            return parse_config_file(path=config_file)
        except Exception as e:
            print(f"YAML parsing failed: {e}")
            return None

    else:
        print(f"Unsupported configuration format: {config_file}")
        return None

# Usage
config_files = ["config.toml", "config.yaml", "config.json"]
for config_file in config_files:
    config = load_config_by_type(config_file)
    if config:
        print(f"Successfully loaded: {config_file}")
        break
```

## Best Practices

### Configuration Management

```python
# Always use load_config for guaranteed non-None results
config = load_config("data/tasksupport")

# Use get_config when you need to handle None results
config = get_config("data/tasksupport")
if config is None:
    # Handle missing configuration
    pass

# Validate configuration after loading
if config.system.extended_mode not in ["invoice", "rdeformat", "multidatatile"]:
    raise ValueError(f"Invalid extended_mode: {config.system.extended_mode}")
```

### Environment-Specific Configuration

```python
def load_environment_config(environment: str = "production"):
    """Load configuration based on environment."""

    config_paths = {
        "development": "config/dev",
        "testing": "config/test",
        "production": "data/tasksupport"
    }

    config_path = config_paths.get(environment, "data/tasksupport")
    return load_config(config_path)

# Usage
import os
env = os.getenv("RDE_ENVIRONMENT", "production")
config = load_environment_config(env)
```

## See Also

- [Models - Config](models/config.md) - For Config, SystemSettings, and MultiDataTileSettings data structures
- [Models - RDE2 Types](models/rde2types.md) - For RdeFsPath type definitions
- [Workflows](workflows.md) - For configuration usage in workflow processing
- [Usage - Configuration](../usage/config/config.md) - For practical configuration examples and patterns
- [Usage - Mode](../usage/config/mode.md) - For configuration mode usage examples
