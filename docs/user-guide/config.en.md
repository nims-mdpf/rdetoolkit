# How to Use Configuration Files

## Purpose

This guide explains how to create and use configuration files that control the behavior of RDEToolKit. By properly configuring configuration files, you can select processing modes, control file saving, and define custom settings.

## Prerequisites

Before using configuration files, ensure the following:

- RDEToolKit is installed
- Project directory has been created
- Basic knowledge of YAML or TOML format

## Steps

### 1. Create Configuration File

RDEToolKit automatically searches for configuration files in the following locations and file names:

#### Supported File Names and Locations

| File Name | Location | Format |
|-----------|----------|--------|
| `rdeconfig.yaml` | `tasksupport/` or project root | YAML |
| `rdeconfig.yml` | `tasksupport/` or project root | YAML |
| `pyproject.toml` | project root | TOML |

!!! tip "Recommended Placement"
    We recommend placing project-specific settings in `tasksupport/rdeconfig.yaml` and development environment-wide settings in `pyproject.toml`.

### 2. Define Basic Settings

#### Processing Mode Configuration

=== "YAML Format"
    ```yaml title="tasksupport/rdeconfig.yaml"
    system:
      # Extended mode specification
      extended_mode: 'MultiDataTile'  # or 'rdeformat'
      
      # File saving settings
      save_raw: true
      save_nonshared_raw: true
      
      # Feature enable/disable
      magic_variable: true
      save_thumbnail_image: true
    ```

=== "TOML Format"
    ```toml title="pyproject.toml"
    [tool.rdetoolkit.system]
    extended_mode = 'MultiDataTile'
    save_raw = true
    save_nonshared_raw = true
    magic_variable = true
    save_thumbnail_image = true
    ```

#### Configuration Item Details

| Setting Item | Type | Default Value | Description |
|--------------|------|---------------|-------------|
| `extended_mode` | string | none | Extended mode ('MultiDataTile' or 'rdeformat') |
| `save_raw` | boolean | false | Save input files to `raw` directory |
| `save_nonshared_raw` | boolean | true | Save input files to `nonshared_raw` directory |
| `magic_variable` | boolean | false | Enable Magic Variable functionality |
| `save_thumbnail_image` | boolean | false | Automatic thumbnail image generation |

### 3. Processing Mode-Specific Settings

#### Invoice Mode (Default)

```yaml title="tasksupport/rdeconfig.yaml"
system:
  magic_variable: true
  save_thumbnail_image: true
```

#### Multi Data Tile Mode

```yaml title="tasksupport/rdeconfig.yaml"
system:
  extended_mode: 'MultiDataTile'
  
multidata_tile:
  ignore_errors: true  # Continue processing on errors
```

#### RDE Format Mode

```yaml title="tasksupport/rdeconfig.yaml"
system:
  extended_mode: 'rdeformat'
  save_raw: false
  save_nonshared_raw: false
```

### 4. Add Custom Settings

Define custom configuration values that can be referenced within structured processing:

=== "YAML Format"
    ```yaml title="tasksupport/rdeconfig.yaml"
    custom:
      # Image processing settings
      thumbnail_image_name: "inputdata/sample_image.png"
      image_quality: 85
      max_image_size: 1920
      
      # Data processing settings
      analysis_parameters:
        threshold: 0.5
        iterations: 100
      
      # Output settings
      output_format: "csv"
      include_metadata: true
    ```

=== "TOML Format"
    ```toml title="pyproject.toml"
    [tool.rdetoolkit.custom]
    thumbnail_image_name = "inputdata/sample_image.png"
    image_quality = 85
    max_image_size = 1920
    output_format = "csv"
    include_metadata = true
    
    [tool.rdetoolkit.custom.analysis_parameters]
    threshold = 0.5
    iterations = 100
    ```

### 5. Reference Settings in Structured Processing

How to use created configuration values within structured processing functions:

```python title="modules/process.py"
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath

def dataset(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    # Reference system settings
    extended_mode = srcpaths.config.system.extended_mode
    save_raw = srcpaths.config.system.save_raw
    magic_variable = srcpaths.config.system.magic_variable
    
    print(f"Processing mode: {extended_mode}")
    print(f"Save raw: {save_raw}")
    print(f"Magic Variable: {magic_variable}")
    
    # Reference custom settings
    if hasattr(srcpaths.config, 'custom'):
        custom_config = srcpaths.config.custom
        
        # Get image settings
        thumbnail_name = custom_config.get('thumbnail_image_name')
        image_quality = custom_config.get('image_quality', 75)
        
        # Get analysis parameters
        analysis_params = custom_config.get('analysis_parameters', {})
        threshold = analysis_params.get('threshold', 0.5)
        
        print(f"Thumbnail image: {thumbnail_name}")
        print(f"Image quality: {image_quality}")
        print(f"Threshold: {threshold}")
```

## Verification

### Verify Configuration File Loading

How to verify that settings are loaded correctly:

```python title="test_config.py"
from rdetoolkit.config import parse_config_file

# Test configuration file loading
config = parse_config_file()

print("=== Configuration Check ===")
print(f"Extended mode: {config.system.extended_mode}")
print(f"Save raw: {config.system.save_raw}")
print(f"Magic Variable: {config.system.magic_variable}")

if hasattr(config, 'custom'):
    print(f"Custom settings: {config.custom}")
```

### Configuration Priority

Priority when multiple configuration files exist:

1. `tasksupport/rdeconfig.yaml`
2. `tasksupport/rdeconfig.yml`
3. `./rdeconfig.yaml`
4. `./rdeconfig.yml`
5. `./pyproject.toml`

!!! warning "Configuration Conflicts"
    When the same configuration item is defined in multiple files, the setting from the higher priority file is used.

## Troubleshooting

### Common Issues and Solutions

#### YAML Syntax Error

```
ERROR: YAML parsing failed
```

**Solution**: Check YAML syntax
```yaml
# Correct example
system:
  extended_mode: 'MultiDataTile'
  save_raw: true

# Incorrect example (indentation error)
system:
extended_mode: 'MultiDataTile'
save_raw: true
```

#### Configuration Values Not Applied

**Check items**:
1. File name spelling mistakes
2. File placement location
3. YAML/TOML syntax errors
4. Incorrect configuration item names

#### Cannot Access Custom Settings

```python title="safe_config_access.py"
def safe_get_custom_config(config, key, default=None):
    """Safely get custom configuration"""
    if hasattr(config, 'custom') and key in config.custom:
        return config.custom[key]
    return default

# Usage example
thumbnail_name = safe_get_custom_config(
    srcpaths.config, 
    'thumbnail_image_name', 
    'default_thumbnail.png'
)
```

## Related Information

For detailed configuration file specifications:

- [Magic Variables](#magic-variables) - Dynamic metadata replacement functionality (see Magic Variables section above)
- [API Reference](../api/index.en.md) - Configuration-related API specifications
