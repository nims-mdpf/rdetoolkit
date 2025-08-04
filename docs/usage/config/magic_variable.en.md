# What is Magic Variable

## Purpose

This document explains the Magic Variable feature in RDEToolKit. You will understand the mechanism and usage methods for automatically replacing dynamic values such as filenames and timestamps.

## Challenges and Background

Structured processing faced the following challenges:

- **Manual Filename Input**: Need to manually input filenames for data names
- **Consistency Assurance**: Inconsistencies when writing the same filename in multiple places
- **Dynamic Value Management**: Automatic generation of dynamic values like timestamps
- **Work Efficiency**: Automation of repetitive tasks

The Magic Variable feature was developed to solve these challenges.

## Key Concepts

### Dynamic Replacement Mechanism

```mermaid
flowchart LR
    A[JSON File] --> B[${variable_name} description]
    C[Actual Filename] --> D[Variable Value]
    B --> E[Magic Variable Processing]
    D --> E
    E --> F[Replaced JSON File]
```

### Supported Variables

| Variable Name | Description | Example |
|---------------|-------------|---------|
| `${filename}` | Input filename (without extension) | `experiment_data` |
| `${timestamp}` | Current timestamp | `2023-01-01T12:00:00Z` |

### Application Scope

- **Target Mode**: Invoice mode only
- **Target Files**: JSON files (invoice.json, metadata.json, etc.)
- **Replacement Timing**: During structured processing execution

## Configuration Method

### 1. Enable Magic Variable

Enable Magic Variable in the configuration file:

```yaml title="rdeconfig.yaml"
system:
    magic_variable: true
```

### 2. Use Variables in JSON Files

#### Usage Example in invoice.json

```json title="invoice.json"
{
    "basic": {
        "dataName": "${filename}",
        "description": "Data processing result from ${filename}"
    },
    "custom": {
        "original_file": "${filename}",
        "processing_date": "${timestamp}"
    }
}
```

#### Usage Example in metadata.json

```json title="metadata.json"
{
    "source_file": "${filename}",
    "processing_timestamp": "${timestamp}",
    "output_filename": "${filename}_result.csv"
}
```

### 3. Verify Replacement Results

For input file `experiment_data.csv`:

```json title="Replaced invoice.json"
{
    "basic": {
        "dataName": "experiment_data",
        "description": "Data processing result from experiment_data"
    },
    "custom": {
        "original_file": "experiment_data",
        "processing_date": "2023-01-01T12:00:00Z"
    }
}
```

## Practical Usage Examples

### Dynamic Filename Generation

```python title="Utilization in Structured Processing"
def dataset(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    # Processing when Magic Variable is enabled
    
    # Generate metadata (using Magic Variable)
    metadata = {
        "source": "${filename}",
        "processed_at": "${timestamp}",
        "output": "${filename}_processed.csv",
        "version": "1.0"
    }
    
    # Save as metadata.json
    metadata_file = Path(resource_paths.meta) / "metadata.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
```

### Conditional Magic Variable Usage

```python title="Usage with Configuration Check"
def dataset(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    # Check Magic Variable setting
    magic_enabled = srcpaths.config.system.magic_variable
    
    if magic_enabled:
        # Use Magic Variable
        data_name = "${filename}"
        timestamp = "${timestamp}"
    else:
        # Use fixed values
        data_name = "default_data"
        timestamp = "2023-01-01T00:00:00Z"
    
    metadata = {
        "data_name": data_name,
        "created_at": timestamp
    }
```

## Troubleshooting

### When Magic Variable Doesn't Work

#### Configuration Check Checklist

```python title="Configuration Check Script"
def check_magic_variable_settings(srcpaths):
    # Check Magic Variable setting
    magic_enabled = srcpaths.config.system.magic_variable
    print(f"Magic Variable enabled: {magic_enabled}")
    
    # Check input files
    input_files = list(srcpaths.inputdata.glob("*"))
    for file in input_files:
        print(f"Input file: {file.name}")
        print(f"Filename (without extension): {file.stem}")
```

### Common Problems and Solutions

| Problem | Cause | Solution |
|---------|-------|----------|
| Variables not replaced | Magic Variable disabled | Set `magic_variable: true` in configuration file |
| Doesn't work in non-invoice modes | Mode limitation | Execute in invoice mode |
| Variable names not recognized | Description error | Check `${filename}`, `${timestamp}` description |

### Debugging Method

```python title="Debug Code"
def debug_magic_variable(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath):
    # Check configuration values
    config = srcpaths.config
    print(f"Magic Variable setting: {config.system.magic_variable}")
    
    # Check input files
    input_files = list(srcpaths.inputdata.glob("*"))
    print(f"Number of input files: {len(input_files)}")
    
    for file in input_files:
        print(f"Filename: {file.name}")
        print(f"Stem: {file.stem}")
    
    # Test metadata
    test_metadata = {
        "test_filename": "${filename}",
        "test_timestamp": "${timestamp}"
    }
    
    print(f"Test metadata: {test_metadata}")
```

## Summary

Key features of the Magic Variable function:

- **Automatic Replacement**: Automatic replacement of filenames and timestamps
- **Consistency Assurance**: Unification of the same values in multiple places
- **Work Efficiency**: Reduction of manual input tasks
- **Dynamic Response**: Generation of dynamic values at runtime

## Next Steps

To utilize the Magic Variable feature, refer to the following documents:

- Learn Magic Variable configuration methods in [Configuration Files](config.en.md)
- Check invoice mode details in [Data Registration Modes](mode.en.md)
- Understand processing flows in [Structured Processing Concepts](../structured_process/structured.en.md)
