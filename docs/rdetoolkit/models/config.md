# Configuration Module

The `rdetoolkit.config` module provides comprehensive configuration management for RDE (Research Data Exchange) workflows using Pydantic models. This module defines system settings, processing mode configurations, and validation rules to ensure proper toolkit operation and data handling.

## Overview

The configuration module offers structured configuration management with:

- **System Settings**: Core RDEToolkit operational parameters and data handling options
- **Mode-Specific Settings**: Specialized configurations for different processing modes (MultiDataTile, etc.)
- **Validation Rules**: Built-in validation to ensure configuration consistency and correctness
- **Extensible Design**: Support for additional configuration sections through Pydantic's extra fields

## Classes

### SystemSettings

Core system configuration model that defines fundamental RDEToolkit operational parameters.

#### Constructor

```python
SystemSettings(
    extended_mode: str | None = None,
    save_raw: bool = False,
    save_nonshared_raw: bool = True,
    save_thumbnail_image: bool = False,
    magic_variable: bool = False
)
```

**Parameters:**
- `extended_mode` (str | None): Processing mode selection ('rdeformat', 'MultiDataTile', or None)
- `save_raw` (bool): Enable automatic saving of raw data to the raw directory
- `save_nonshared_raw` (bool): Enable saving of non-shared raw data
- `save_thumbnail_image` (bool): Enable automatic thumbnail generation from main images
- `magic_variable` (bool): Enable filename variable substitution with '${filename}' syntax

#### Attributes

- `extended_mode` (str | None): The current processing mode
- `save_raw` (bool): Raw data auto-save setting
- `save_nonshared_raw` (bool): Non-shared raw data save setting
- `save_thumbnail_image` (bool): Thumbnail auto-generation setting
- `magic_variable` (bool): Magic variable substitution setting

#### Validators

##### check_at_least_one_save_option_enabled()

Validates that at least one save option is enabled to prevent data loss.

```python
@model_validator(mode='after')
def check_at_least_one_save_option_enabled() -> SystemSettings
```

**Returns:**
- `SystemSettings`: The validated model instance

**Raises:**
- `ValueError`: If both 'save_raw' and 'save_nonshared_raw' are False

**Example:**
```python
from rdetoolkit.models.config import SystemSettings

# Valid configuration
valid_config = SystemSettings(
    extended_mode="MultiDataTile",
    save_raw=True,
    save_nonshared_raw=False
)

# Invalid configuration - will raise ValueError
try:
    invalid_config = SystemSettings(
        save_raw=False,
        save_nonshared_raw=False
    )
except ValueError as e:
    print(f"Configuration error: {e}")
```

### MultiDataTileSettings

Configuration model for MultiDataTile processing mode settings.

#### Constructor

```python
MultiDataTileSettings(ignore_errors: bool = False)
```

**Parameters:**
- `ignore_errors` (bool): Continue processing when errors are encountered instead of stopping

#### Attributes

- `ignore_errors` (bool): Error handling behavior for MultiDataTile processing

**Example:**
```python
from rdetoolkit.models.config import MultiDataTileSettings

# Configure MultiDataTile to continue on errors
mdt_settings = MultiDataTileSettings(ignore_errors=True)
print(f"Ignore errors: {mdt_settings.ignore_errors}")
```

### Config

Main configuration class that combines all settings sections with support for additional custom fields.

#### Constructor

```python
Config(
    system: SystemSettings = SystemSettings(),
    multidata_tile: MultiDataTileSettings | None = MultiDataTileSettings(),
    **kwargs
)
```

**Parameters:**
- `system` (SystemSettings): System-related settings
- `multidata_tile` (MultiDataTileSettings | None): MultiDataTile-specific settings
- `**kwargs`: Additional configuration fields (enabled by `extra="allow"`)

#### Attributes

- `system` (SystemSettings): Core system configuration
- `multidata_tile` (MultiDataTileSettings | None): MultiDataTile processing settings

**Example:**
```python
from rdetoolkit.models.config import Config, SystemSettings, MultiDataTileSettings

# Create comprehensive configuration
config = Config(
    system=SystemSettings(
        extended_mode="MultiDataTile",
        save_raw=True,
        magic_variable=True
    ),
    multidata_tile=MultiDataTileSettings(ignore_errors=False)
)
```

## Performance Notes

- Configuration loading is optimized for startup performance with lazy validation
- Pydantic models provide efficient serialization/deserialization
- Environment variablereading is cached by the OS
- JSON file parsing is fast for typical configuration sizes
- Model validation occurs once during creation, not on every access

## See Also

- [Workflows Module](workflows.md) - For configuration usage in processing workflows
- [System Overview](../overview.md) - For understanding RDEToolkit system architecture
- [Processing Modes](../processing_modes.md) - For details on extended_mode options
- [Pydantic Documentation](https://docs.pydantic.dev/) - For advanced model features and validation
