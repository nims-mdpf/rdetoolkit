# Configuration Models API

## Purpose

This module defines configuration models for RDEToolKit using Pydantic. It provides structured configuration management with type safety, validation, and automatic default value application for system settings and processing configurations.

## Key Features

### Configuration Data Models
- System settings management with type safety
- MultiDataTile settings for error handling
- Pydantic-based validation and serialization

### Type Safety and Validation
- Automatic type checking and conversion
- Field validation with descriptive error messages
- Default value management

---

::: src.rdetoolkit.models.config.SystemSettings

---

::: src.rdetoolkit.models.config.MultiDataTileSettings

---

::: src.rdetoolkit.models.config.Config

---

## Practical Usage

### Basic Configuration Creation

```python title="basic_config.py"
from rdetoolkit.models.config import Config, SystemSettings, MultiDataTileSettings

# Create system settings
system_settings = SystemSettings(
    extended_mode=True,
    save_raw=True,
    save_thumbnail_image=False
)

# Create MultiDataTile settings
multidatatile_settings = MultiDataTileSettings(
    ignore_errors=False
)

# Create complete configuration
config = Config(
    system=system_settings,
    multidatatile=multidatatile_settings
)

print(f"Extended mode: {config.system.extended_mode}")
print(f"Save raw files: {config.system.save_raw}")
print(f"Ignore errors: {config.multidatatile.ignore_errors}")
```

### Configuration from File

```python title="config_from_file.py"
from rdetoolkit.models.config import Config
from rdetoolkit.config import parse_config_file

# Load configuration from file
config = parse_config_file("config.yaml")

# Access configuration values
print(f"System configuration:")
print(f"  Extended mode: {config.system.extended_mode}")
print(f"  Save raw: {config.system.save_raw}")
print(f"  Save thumbnails: {config.system.save_thumbnail_image}")

print(f"MultiDataTile configuration:")
print(f"  Ignore errors: {config.multidatatile.ignore_errors}")
```

### Dynamic Configuration Management

```python title="dynamic_config.py"
from rdetoolkit.models.config import Config
import os

# Create configuration based on environment variables
config_data = {
    "system": {
        "extended_mode": os.getenv("RDE_EXTENDED_MODE", "false").lower() == "true",
        "save_raw": os.getenv("RDE_SAVE_RAW", "true").lower() == "true",
        "save_thumbnail_image": os.getenv("RDE_SAVE_THUMBNAILS", "false").lower() == "true"
    },
    "multidatatile": {
        "ignore_errors": os.getenv("RDE_IGNORE_ERRORS", "false").lower() == "true"
    }
}

# Create configuration object
config = Config(**config_data)

print("Configuration loaded from environment variables:")
print(f"Extended mode: {config.system.extended_mode}")
print(f"Save raw: {config.system.save_raw}")
print(f"Ignore errors: {config.multidatatile.ignore_errors}")
```
