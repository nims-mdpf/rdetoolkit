# How to Create Configuration Files

## Purpose

This document explains how to create and configure configuration files (`rdeconfig.yaml`) for customizing RDEToolKit structured processing behavior. You will learn from basic settings to advanced configurations step by step.

## Prerequisites

- Understanding of basic RDEToolKit usage
- Basic knowledge of YAML file format
- Understanding of structured processing directory structure

## Steps

### 1. Place Configuration File

Place the configuration file in the correct location:

```shell title="Configuration File Location"
data/
└── tasksupport/
    └── rdeconfig.yaml  # Place here
```

### 2. Create Basic Configuration

Create a minimal configuration file:

```yaml title="Basic rdeconfig.yaml"
system:
  save_raw: true
  magic_variable: false
  save_thumbnail_image: true
  extended_mode: null
```

### 3. Configure Each Setting Item

#### save_raw Setting

Controls whether to copy input data to the `raw` directory:

```yaml title="save_raw Setting"
system:
  save_raw: true   # Copy input data to raw directory (recommended)
  save_raw: false  # Do not copy input data
```

!!! tip "Recommended Setting"
    We recommend `save_raw: true` to ensure data traceability.

#### magic_variable Setting

Controls the dynamic filename replacement feature:

```yaml title="magic_variable Setting"
system:
  magic_variable: true   # Enable ${filename} replacement
  magic_variable: false  # Disable replacement feature (default)
```

Usage example:
```json title="magic_variable Usage Example"
{
  "data_name": "${filename}",
  "output_file": "${filename}_processed.csv"
}
```

#### save_thumbnail_image Setting

Controls automatic thumbnail generation from main images:

```yaml title="save_thumbnail_image Setting"
system:
  save_thumbnail_image: true   # Auto-generate thumbnail images (recommended)
  save_thumbnail_image: false  # Do not generate thumbnail images
```

#### extended_mode Setting

Specifies extended processing modes:

```yaml title="extended_mode Setting"
system:
  extended_mode: null              # Standard invoice mode
  extended_mode: "MultiDataTile"   # Multi-data tile mode
  extended_mode: "rdeformat"       # RDE format mode
```

### 4. Add Extended Settings

#### Non-shared Data Save Setting

```yaml title="Non-shared Data Setting"
system:
  save_nonshared_raw: true   # Save to non-shared raw directory
  save_nonshared_raw: false  # Do not save to non-shared raw directory
```

#### MultiDataTile Error Handling Setting

```yaml title="MultiDataTile Error Handling"
multidata_tile:
  ignore_errors: true   # Continue processing even if errors occur
  ignore_errors: false  # Stop processing if errors occur (default)
```

#### Adding Custom Settings

```yaml title="Custom Settings"
custom:
  thumbnail_image_name: "inputdata/sample_image.png"
  processing_timeout: 300
  debug_mode: false
```

### 5. Create Complete Configuration Examples

#### Basic Configuration Example

```yaml title="Basic Configuration rdeconfig.yaml"
system:
  save_raw: true
  save_nonshared_raw: false
  magic_variable: false
  save_thumbnail_image: true
  extended_mode: null
```

#### Advanced Configuration Example

```yaml title="Advanced Configuration rdeconfig.yaml"
system:
  save_raw: true
  save_nonshared_raw: true
  magic_variable: true
  save_thumbnail_image: true
  extended_mode: "MultiDataTile"

multidata_tile:
  ignore_errors: false

custom:
  thumbnail_image_name: "inputdata/main_chart.png"
  processing_timeout: 600
  debug_mode: true
  output_format: "csv"
```

### 6. Reference Configuration Values in Structured Processing

Use the created configuration values within structured processing:

```python title="Configuration Value Reference"
def dataset(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    # Reference system settings
    extended_mode = srcpaths.config.system.extended_mode
    save_raw = srcpaths.config.system.save_raw
    magic_variable = srcpaths.config.system.magic_variable
    
    print(f"Extended mode: {extended_mode}")
    print(f"Save raw: {save_raw}")
    print(f"Magic variable: {magic_variable}")
    
    # Reference custom settings
    if "custom" in srcpaths.config:
        thumbnail_name = srcpaths.config["custom"].get("thumbnail_image_name")
        timeout = srcpaths.config["custom"].get("processing_timeout", 300)
        
        print(f"Thumbnail image: {thumbnail_name}")
        print(f"Timeout: {timeout} seconds")
```

## Verification

Verify that the configuration file was created correctly:

### Configuration File Validation

```python title="Configuration File Validation"
import yaml
from pathlib import Path

def validate_config(config_path):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        print("✅ Configuration file loaded successfully")
        
        # Check system settings
        if 'system' in config:
            system = config['system']
            print(f"save_raw: {system.get('save_raw', 'default value')}")
            print(f"extended_mode: {system.get('extended_mode', 'default value')}")
            print(f"magic_variable: {system.get('magic_variable', 'default value')}")
        
        return config
    except Exception as e:
        print(f"❌ Configuration file error: {e}")
        return None

# Usage example
config = validate_config("data/tasksupport/rdeconfig.yaml")
```

### Configuration Operation Verification

```shell title="Configuration Operation Verification"
# Run structured processing to test if settings are applied
cd container
python3 main.py
```

## Troubleshooting

### Common Problems and Solutions

| Problem | Cause | Solution |
|---------|-------|----------|
| YAML format error | Indentation or colon issues | Check indentation and spaces after colons |
| Settings not applied | Wrong file path or item names | Verify file path and setting item names |
| Character encoding error | File character code issues | Save file as UTF-8 |

### Configuration Priority

1. Environment variables
2. `rdeconfig.yaml` file
3. Default values

## Related Information

To learn more about configuration files, refer to the following documents:

- Check detailed settings for each mode in [Processing Modes](mode.en.md)
- Learn about dynamic replacement features in [Magic Variable](magic_variable.en.md)
- Understand processes affected by settings in [Structured Processing Concepts](../structured_process/structured.en.md)
