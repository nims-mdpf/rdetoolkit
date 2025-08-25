# Config Models API

## Purpose

This module defines configuration data structures for RDEToolKit. It provides configuration models that control the behavior of the entire application, including system settings and MultiDataTile settings.

## Key Features

### Configuration Data Models
- System-wide configuration management
- Detailed settings for MultiDataTile mode
- Type-safe configuration value management

### Data Validation
- Pydantic-based type safety
- Configuration value validity verification
- Automatic application of default values

---

::: src.rdetoolkit.models.config.Config

---

::: src.rdetoolkit.models.config.SystemSettings

---

::: src.rdetoolkit.models.config.MultiDataTileSettings

---

## Practical Usage

### Basic Configuration Creation

```python title="basic_config.py"
from rdetoolkit.models.config import Config, SystemSettings, MultiDataTileSettings

# Create system settings
system_settings = SystemSettings(
    save_raw=True,
    save_thumbnail_image=True,
    extended_mode="MultiDataTile"
)

# Create MultiDataTile settings
multidatatile_settings = MultiDataTileSettings(
    tile_size=256,
    overlap_ratio=0.1,
    compression_level=6
)

# Create integrated configuration
config = Config(
    system=system_settings,
    multidatatile=multidatatile_settings
)

print(f"Configuration created: {config}")
```

### Loading from Configuration File

```python title="config_from_file.py"
from rdetoolkit.models.config import Config
from rdetoolkit.config import parse_config_file
import json

# Load from configuration file
config = parse_config_file()

# Reference configuration values
print(f"Save raw data: {config.system.save_raw}")
print(f"Save thumbnail: {config.system.save_thumbnail_image}")
print(f"Extended mode: {config.system.extended_mode}")

# Reference MultiDataTile settings
if hasattr(config, 'multidatatile') and config.multidatatile:
    print(f"Tile size: {config.multidatatile.tile_size}")
    print(f"Overlap ratio: {config.multidatatile.overlap_ratio}")

# Update configuration
config.system.save_raw = False
if config.multidatatile:
    config.multidatatile.tile_size = 512

# Save updated configuration
config_dict = config.dict()
with open("config/updated_config.json", "w") as f:
    json.dump(config_dict, f, indent=2)
```

### Creating Custom Configuration

```python title="custom_config.py"
from rdetoolkit.models.config import Config, SystemSettings, MultiDataTileSettings
from pathlib import Path

# Custom system settings
custom_system = SystemSettings(
    save_raw=True,
    save_thumbnail_image=False,
    extended_mode="MultiDataTile",
    output_dir=Path("custom_output"),
    temp_dir=Path("custom_temp")
)

# Custom MultiDataTile settings
custom_multidatatile = MultiDataTileSettings(
    tile_size=1024,
    overlap_ratio=0.2,
    compression_level=9,
    enable_caching=True,
    max_memory_usage="2GB"
)

# Integrated configuration
custom_config = Config(
    system=custom_system,
    multidatatile=custom_multidatatile
)

# Configuration validation
try:
    validated_config = Config.parse_obj(custom_config.dict())
    print("Configuration validation successful")
    
    # Display configuration values
    print(f"System settings: {validated_config.system}")
    print(f"MultiDataTile settings: {validated_config.multidatatile}")
    
except Exception as e:
    print(f"Configuration validation error: {e}")
```

### Dynamic Configuration Management

```python title="dynamic_config.py"
from rdetoolkit.models.config import Config, SystemSettings, MultiDataTileSettings
import os

def create_environment_based_config():
    """Create dynamic configuration based on environment"""
    
    # Get configuration values from environment variables
    save_raw = os.getenv("RDE_SAVE_RAW", "true").lower() == "true"
    extended_mode = os.getenv("RDE_EXTENDED_MODE", "MultiDataTile")
    tile_size = int(os.getenv("RDE_TILE_SIZE", "256"))
    
    # System settings
    system_settings = SystemSettings(
        save_raw=save_raw,
        save_thumbnail_image=True,
        extended_mode=extended_mode
    )
    
    # MultiDataTile settings (only if extended mode is MultiDataTile)
    multidatatile_settings = None
    if extended_mode == "MultiDataTile":
        multidatatile_settings = MultiDataTileSettings(
            tile_size=tile_size,
            overlap_ratio=float(os.getenv("RDE_OVERLAP_RATIO", "0.1")),
            compression_level=int(os.getenv("RDE_COMPRESSION", "6"))
        )
    
    # Create configuration
    config = Config(
        system=system_settings,
        multidatatile=multidatatile_settings
    )
    
    return config

# Usage example
env_config = create_environment_based_config()
print(f"Environment-based configuration: {env_config}")

# Configuration validity check
if env_config.system.extended_mode == "MultiDataTile":
    if env_config.multidatatile:
        print(f"MultiDataTile mode enabled: tile_size={env_config.multidatatile.tile_size}")
    else:
        print("Warning: MultiDataTile mode but configuration not found")
```
