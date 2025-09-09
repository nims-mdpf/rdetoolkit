
# What Is the Magic Variable Feature?

## Purpose

This document explains the Magic Variable feature of RDEToolKit. You will understand how dynamic values such as file names and timestamps are automatically substituted, as well as how to configure the feature.

## Problem Statement and Background

In structured processing, we faced the following issues:

- **Manual entry of file names**: File names had to be typed manually into the metadata.
- **Maintaining consistency**: It was difficult to enter the exact same file name correctly across multiple entries.
- **Efficiency concerns**: Processing large numbers of files significantly increased the amount of work time.
- **Managing dynamic values**: Handling dynamic values such as timestamps or calculated numbers became complex.

The Magic Variable feature was created to solve these problems.

## Core Concept

### How Magic Variables Work

```mermaid
flowchart LR
    A[JSON file] --> B[${filename}]
    C[Actual file name] --> D[sample.csv]
    B --> E[Substitution process]
    D --> E
    E --> F[sample.csv]
```

### Supported Variables

| Variable Name | Description                     | Example                 |
| ------------- | ------------------------------- | ----------------------- |
| `${filename}` | File name without the extension | `sample.csv` → `sample` |

## How to Set It Up

### 1. Enable in the Configuration File

Activate the Magic Variable feature in `rdeconfig.yaml`:

```yaml title="rdeconfig.yaml"
system:
  magic_variable: true
```

### 2. Use in JSON Files

Insert the variable in metadata files or any other JSON files:

```json title="metadata.json"
{
  "data_name": "${filename}"
}
```

### 3. Verify the Processing Result

When the Magic Variable feature is enabled, the substitution will look like this:

```json title="metadata after processing.json"
{
  "data_name": "sample.csv"
}
```

## Summary

Key benefits of the Magic Variable feature:

- **Automation**: Automatic substitution of file names and timestamps.
- **Consistency**: Guarantees consistent information across multiple entries.
- **Efficiency**: Greatly reduces manual entry work.
- **Dynamic values**: Enables dynamic generation of timestamps and dates.

## Next Steps

To make the most of the Magic Variable feature, refer to the following documents:

- Learn detailed configuration in the [Configuration File](config.ja.md) documentation.
- Understand the processing flow in the [Structured Processing Concept](../structured_process/structured.ja.md) guide.
- Review metadata design in the [Metadata Definition File](../metadata_definition_file.ja.md) documentation.
