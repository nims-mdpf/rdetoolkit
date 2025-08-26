# What Is Invoice Mode

## Purpose

This is the most basic processing mode for RDE data registration. It refers to the mode in which you use the RDE invoice (the web-based registration screen) to register data one item at a time.

![invoice_mode](../../img/invoice_mode.svg)

### Features

- Register one experimental result as one dataset
- Simple configuration and operation
- Ideal for beginners

## When to Use

- Registering one-off experimental data

## Configuration Example

When using Invoice Mode, no changes to configuration files are required.

## Directory Structure

The directory structure before and after running the structuring process is as follows.

```bash
data
├── inputdata
│   └── 20250101_myexp.dat
├── invoice
│   └── invoice.json
└── tasksupport
    ├── invoice.schema.json
    ├── metadata-def.json
    └── rdeconfig.yml
```

After execution, the directory is as follows.

> The files shown are example outputs. They may vary depending on the definition of the structuring process.

```bash
data
├── attachment
├── inputdata
│   └── 20250101_myexp.dat
├── invoice
│   └── invoice.json
├── invoice_patch
├── logs
│   └── rdesys.log
├── main_image
│   └── 20250101.png
├── meta
├── nonshared_raw
├── other_image
│   └── 20250101_log_scale.png
├── raw
│   └── 20250101_myexp.dat
├── structured
│   └── 20250101_myexp.csv
├── tasksupport
│   ├── default_value.csv
│   ├── invoice.schema.json
│   ├── metadata-def.json
│   └── rdeconfig.yml
├── temp
└── thumbnail
```
