# What is RDEFormat Mode?

## Purpose

RDEFormat Mode is a mode for registering RDE-format data into RDE to integrate RDE with external systems. When another system outputs data in the RDE format, you can use RDEFormat Mode to register that output directly into RDE as is.

![rdeformat](../../img/rdeformat.svg)

## Features

- You can register the specified RDE registration data format (.zip) as is.

## When to Use

- When you want to register RDE-format data from another system into RDE
- When you want to set up a dataset for mock/testing purposes and register data

## Configuration

Configure the `rdeconfig.yml` settings file as follows:

```yaml
system:
  extended_mode: "rdeformat"
```

## Folders That Are Extracted

The folders included in the zip that will be extracted are as follows:

- raw
- main_image
- other_image
- meta
- structured
- nonshared_raw

## Input File

Compress the directory structure supported by the RDE structuring process into a zip file.

```bash
input.zip
├── main_image
│   └── sample1.png
├── meta
│   └── metadata.json
├── nonshared_raw
├── other_image
│   └── other_sampling.png
├── raw
│   └── sample1.raw
└── structured
    └── sample1.csv
```

## Directory Layout

Place the Excel file and the zip file in the `inputdata` directory.

```bash
data/
├── inputdata/
│   ├── input.zip
├── invoice/
└── tasksupport/
    └── rdeconfig.yml
```

After execution, the contents of `input.zip` are registered as is, as shown below. Data split under the `divided` directory is also supported.

```bash
data/
├── inputdata/
│   ├── file1.rasx
│   └── file2.rasx
├── invoice/
├── tasksupport/
├── main_image
│   └── sample1.png
├── meta
│   └── metadata.json
├── nonshared_raw
├── other_image
│   └── other_sampling.png
├── raw
│   └── sample1.raw
└── structured
    └── sample1.csv
```

## Common Errors and Questions

### Can I implement a structuring process using RDEFormat Mode?

Although RDEFormat Mode is intended to register RDE-format data as is, it is also possible to implement a structuring process. As with Invoice Mode, if you define the structuring process, the predefined processing can be executed at the time of registration.

### Can RDEFormat Mode overwrite `invoice.json`?

No. RDEFormat Mode cannot perform overwrites including `invoice.json`. Because RDEFormat Mode registers RDE-format data as is, `invoice.json` is automatically generated at registration time.

The folders that are extracted are as follows:

- raw
- main_image
- other_image
- meta
- structured
- nonshared_raw
