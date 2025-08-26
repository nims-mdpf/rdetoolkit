# What Is MultiDataTile Mode?

## Purpose

MultiDataTile mode is a registration mode for submitting multiple data items. It is positioned as an extension of RDE’s standard Invoice mode, allowing registration directly from the RDE invoice (the web-based registration screen) without using Excel files, etc.

There is also an ExcelInvoice mode for registering multiple data items; this mode allows you to register multiple data items at once under the same invoice (e.g., data sharing the same sample information).

![multidatatile\_mode](../../img/multidatatile_mode.svg)

## Features

- With a single setting, you can batch-register data from the invoice (web).
- Suited for registering data that share identical experimental conditions or sample information.

## Use Cases

- When you want to register data with the same experimental conditions or sample information in one batch.

## How to Configure

Set the following in the `rdeconfig.yml` configuration file:

```yaml
system:
  extended_mode: "MultiDataTile"
```

## Directory Structure

Place the Excel files and zip archives in the `inputdata` directory.

```bash
data/
├── inputdata/
│   ├── file1.rasx
│   └── file2.rasx
├── invoice/
└── tasksupport/
    └── rdeconfig.yml
```

After execution, the split data will be stored under the `divided` directory as shown below.

```bash
data/
├── inputdata/
│   ├── file1.rasx
│   └── file2.rasx
├── invoice/
├── tasksupport/
├── divided/
│   ├── 0001/
│   │   ├── structured/
│   │   ├── meta/
│   │   └── raw/
│   └── 0002/
│       ├── structured/
│       ├── meta/
│       └── raw/
└── logs/
```

## Common Errors and Questions

### I want to register multiple data items in a single tile

When using MultiDataTile mode, it is difficult to register multiple data items into a single tile. As a workaround, you can bundle the files you wish to register for each tile into a zip file, and register each zip within a separate structuring process.
