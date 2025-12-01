
# What Is the Magic Variable Feature?

## Purpose

This document explains the Magic Variable feature of RDEToolKit. You will understand how dynamic values such as file names and timestamps are automatically substituted, as well as how to configure the feature.

## Problem Statement and Background

In structuring processing, we faced the following issues:

- **Manual entry of file names**: File names had to be typed manually into the metadata.
- **Maintaining consistency**: It was difficult to enter the exact same file name correctly across multiple entries.
- **Efficiency concerns**: Processing large numbers of files significantly increased the amount of work time.
- **Managing dynamic values**: Handling dynamic values such as timestamps or calculated numbers became complex.

The Magic Variable feature was created to solve these problems.

## How to Use Magic Variables

When you include variables listed under **Supported Variables**, RDE structured processing automatically completes the dataset name according to the rules below. For local testing, set up Magic Variables inside `invoice.json` in advance (see the examples later).

![docs/img/magic_filename.svg]

### Supported Variables

| Variable Name                       | Description                                                                                      | Example                                               |
| ----------------------------------- | ------------------------------------------------------------------------------------------------ | ----------------------------------------------------- |
| `${filename}`                       | Raw file name including the extension                                                            | `sample.csv` → `sample.csv`                           |
| `${invoice:basic:<field>}`          | Value copied from the `basic` node of the source invoice (`invoice_org`)                         | `${invoice:basic:experimentId}` → `EXP-42`            |
| `${invoice:custom:<field>}`         | Value copied from the `custom` node of the source invoice                                        | `${invoice:custom:batchId}` → `BATCH-001`             |
| `${invoice:sample:names}`           | All non-empty entries under `sample.names` joined with `_`                                       | `["alpha", "", "beta"]` → `alpha_beta`                |
| `${metadata:constant:<field>}`      | Constant value from `metadata.json` (`paths.meta / metadata.json`)                               | `${metadata:constant:project_code}` → `PJT-001`       |

> **Note:** The `${metadata:variable:<field>}` pattern remains unsupported because runtime values can change between jobs.

### Invoice-Driven Variables

Invoice lookups always read from `invoice_org` so the template can refer to original user input. Missing fields raise an error, while empty strings are skipped with a warning (and underscores are collapsed to avoid `__`).

- `basic` fields cover properties such as `dataName`, `experimentId`, or `dateSubmitted`.
- `custom` fields are copied verbatim according to the schema you defined in `invoice.schema.json`.
- `sample.names` joins every non-empty string in the array. An empty array triggers an error to keep filenames meaningful.

### Metadata Constants

`${metadata:constant:<field>}` pulls values from `metadata.json` located at `RdeDatasetPaths.meta / metadata.json`. The constant must exist and include a `value`. Failing to resolve a constant (missing file or key) raises a `StructuredError` so the workflow cannot silently proceed with bad data.

## How to Set It Up

### 1. Enable in the Configuration File

Activate the Magic Variable feature in `rdeconfig.yaml`:

```yaml title="rdeconfig.yaml"
system:
  magic_variable: true
```

### 2. Use in JSON Files

Insert the variables inside `invoice.json` (or a SmartTable-generated invoice) by combining multiple sources:

```json title="invoice.json"
{
  "basic": {
    "experimentId": "EXP-42",
    "dataName": "${invoice:basic:experimentId}_${metadata:constant:project_code}_${invoice:sample:names}_${filename}"
  },
  "custom": {
    "project_code": "PRJ",
    "batch": "B-9"
  },
  "sample": {
    "names": ["alpha", "", "beta"]
  }
}
```

### 3. Verify the Processing Result

When the feature is enabled and `metadata.json` contains `{"constant": {"project_code": {"value": "PRJ01"}}}`, the substitution looks like this:

```json title="invoice after processing.json"
{
  "basic": {
    "experimentId": "EXP-42",
    "dataName": "EXP-42_PRJ01_alpha_beta_sample.csv"
  },
  "custom": {
    "project_code": "PRJ",
    "batch": "B-9"
  },
  "sample": {
    "names": ["alpha", "", "beta"]
  }
}
```

If a referenced field is missing the processor raises a `StructuredError`. Empty strings are skipped with a warning and surrounding underscores are collapsed automatically.

## Summary

Key benefits of the Magic Variable feature:

- **Automation**: Automatic substitution of file names and timestamps.
- **Consistency**: Guarantees consistent information across multiple entries.
- **Efficiency**: Greatly reduces manual entry work.
- **Context awareness**: Pulls identifiers from both the invoice (`basic`, `custom`, `sample.names`) and `metadata.json`.

## Next Steps

To make the most of the Magic Variable feature, refer to the following documents:

- Learn detailed configuration in the [Configuration File](config.en.md) documentation.
- Understand the processing flow in the [Structuring Processing Concept](../structured_process/structured.en.md) guide.
- Review metadata design in the [Metadata Definition File](../metadata_definition_file.en.md) documentation.
