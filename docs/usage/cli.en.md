# Command Line Interface

## Overview

RDEToolKit provides a comprehensive command-line interface to support the development and execution of RDE structured processing. It supports the entire development workflow from project initialization to Excel invoice generation and archive creation.

## Prerequisites

- Python 3.9 or higher
- rdetoolkit package installation

## Available Commands

### init: Create Startup Project

Creates a startup project for RDE structured processing.

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit init
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit init
    ```

The following directories and files will be generated:

```shell
container
├── data
│   ├── inputdata
│   ├── invoice
│   │   └── invoice.json
│   └── tasksupport
│       ├── invoice.schema.json
│       └── metadata-def.json
├── main.py
├── modules
└── requirements.txt
```

Description of each file:

- **requirements.txt**: Add Python packages you want to use for structured program construction. Run `pip install` as needed.
- **modules**: Store programs you want to use for structured processing.
- **main.py**: Define startup processing for structured programs
- **data/inputdata**: Place data files to be processed by structured processing.
- **data/invoice**: Required for local execution, even if empty.
- **data/tasksupport**: Place files that support structured processing.

!!! tip "File Overwriting"
    Existing files will be skipped from overwriting or generation.

### make-excelinvoice: Generate Excel Invoice

Generates an Excel invoice from `invoice.schema.json`.

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit make-excelinvoice <invoice.schema.json path> -o <save file path> -m <file or folder>
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit make-excelinvoice <invoice.schema.json path> -o <save file path> -m <file or folder>
    ```

#### Options

| Option       | Description                                                                                                      | Required |
| ------------ | ---------------------------------------------------------------------------------------------------------------- | -------- |
| -o(--output) | Output file path. The file path should end with `_excel_invoice.xlsx`.                                          | ○        |
| -m           | Mode selection. Choose registration mode. You can select file mode `file` or folder mode `folder`.              | -        |

!!! tip "Default Output"
    If `-o` is not specified, it will be created as `template_excel_invoice.xlsx` in the execution directory.

### gen-config: Generate rdeconfig.yaml Templates

Creates an `rdeconfig.yaml` file based on predefined templates or an interactive questionnaire.

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit gen-config [OUTPUT_DIR] --template <template> [--overwrite] [--lang <ja|en>]
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit gen-config [OUTPUT_DIR] --template <template> [--overwrite] [--lang <ja|en>]
    ```

Available templates:

- `minimal` (default): System and traceback keys only.
- `full`: Includes `multidata_tile` defaults.
- `multitile`: Enables `extended_mode: "MultiDataTile"`.
- `rdeformat`: Enables `extended_mode: "rdeformat"`.
- `smarttable`: Adds SmartTable settings with `save_table_file: true`.
- `interactive`: Guides you through each option. Use `--lang ja` for Japanese prompts.

#### Options

| Option          | Description                                                                                   | Required |
| --------------- | --------------------------------------------------------------------------------------------- | -------- |
| OUTPUT_DIR      | Directory to place `rdeconfig.yaml`. Defaults to the current directory.                       | -        |
| --template      | Template name (`minimal`, `full`, `multitile`, `rdeformat`, `smarttable`, `interactive`).     | -        |
| --overwrite     | Force overwrite of an existing `rdeconfig.yaml` without confirmation. Omit to be prompted.    | -        |
| --lang          | Prompt language (`en` or `ja`). Applicable only when `--template interactive` is selected.    | -        |

!!! tip "Interactive Mode"
    When `--template interactive` is used, the command asks about system, MultiDataTile, SmartTable, and traceback
    settings. Responses are written back into the generated `rdeconfig.yaml` so teams start with validated defaults.

### version: Version Check

Check the version of rdetoolkit.

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit version
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit version
    ```

### artifact: Create RDE Submission Archive

Creates an archive (.zip) for submission to RDE. Compresses the specified source directory and excludes files or directories that match exclusion patterns.

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit artifact --source-dir <source directory> --output-archive <output archive file> --exclude <exclusion pattern>
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit artifact --source-dir <source directory> --output-archive <output archive file> --exclude <exclusion pattern>
    ```

#### Options

| Option               | Description                                                                                      | Required |
| -------------------- | ------------------------------------------------------------------------------------------------ | -------- |
| -s(--source-dir)     | Source directory to compress and scan                                                           | ○        |
| -o(--output-archive) | Output archive file (e.g., rde_template.zip)                                                    | -        |
| -e(--exclude)        | Directory names to exclude. By default, 'venv' and 'site-packages' are excluded                | -        |

#### Execution Report

When an archive is created, the following execution report is generated:

- Existence check of Dockerfile and requirements.txt
- List of included directories and files
- Code scan results (security risk detection)
- External communication check results

Sample execution report:

```markdown
# Execution Report

**Execution Date:** 2025-04-08 02:58:44

- **Dockerfile:** [Exists]: 🐳　container/Dockerfile
- **Requirements:** [Exists]: 🐍 container/requirements.txt

## Included Directories

- container/requirements.txt
- container/Dockerfile
- container/vuln.py
- container/external.py

## Code Scan Results

### container/vuln.py

**Description**: Usage of eval() poses the risk of arbitrary code execution.

```python
def insecure():
    value = eval("1+2")
    print(value)
```

## External Communication Check Results

### **container/external.py**

```python
1:
2: import requests
3: def fetch():
4:     response = requests.get("https://example.com")
5:     return response.text
```

!!! tip "Option Details"
    - If `--output-archive` is not specified, an archive will be created with a default filename.
    - The `--exclude` option can be specified multiple times (e.g., `--exclude venv --exclude .git`).

## Next Steps

- Understand [Structured Processing Concepts](../user-guide/structured-processing.en.md)
- Learn how to create [Configuration Files](../user-guide/config.en.md)
- Check detailed features in [API Reference](../api/index.en.md)
