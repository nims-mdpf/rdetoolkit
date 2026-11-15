# Command Line Interface

## Overview

RDEToolKit provides a command-line interface that covers the whole development workflow of an RDE structured program: creating the project, generating configuration and invoice files, validating them, running the processing, inspecting the results, and packaging the submission archive.

Commands follow the form `rdetoolkit <noun> <verb>` (for example `rdetoolkit new config` or `rdetoolkit report show`). A typical project runs `init` → `new config` → `validate all` → `run` → `package`.

!!! tip "Every command documents itself"
    Every command's `--help` lists its inputs, outputs and side effects, examples, and exit codes. Run `rdetoolkit --help` for the grouped command list and `rdetoolkit <command> --help` (for example `rdetoolkit new config --help`) for the details of one command. This page summarizes them; `--help` is the authoritative reference for your installed version.

## Prerequisites

- Python 3.10 or higher
- rdetoolkit package installation

## Command Overview

`rdetoolkit --help` groups the commands into the following panels:

| Panel | Commands | Purpose |
| ----- | -------- | ------- |
| Scaffold | `init` | Create the project scaffold |
| Generate | `new config`, `new invoice`, `new excelinvoice`, `new processing`, `plot` | Generate project files and graphs |
| Validate | `validate invoice`, `validate invoice-schema`, `validate metadata`, `validate metadata-def`, `validate all` | Validate RDE schema and data files |
| Run | `run` | Run structured processing (v2 flow, or a v1 dataset function with `--legacy`) |
| Inspect | `report show`, `report trace`, `nodes list/show/lint`, `flows list/show`, `skeletons list/show`, `formats list` | Read run reports and list registered components |
| Package | `package`, `repro export`, `repro import` | Create the submission archive, export and re-import a run |
| Migrate | `migrate check`, `migrate apply` | Find and convert v1 code and CLI calls for v2 |
| Info | `version` | Show the installed version |
| Deprecated (removed in v2.1) | v1 command names | Kept as aliases that print a warning; see [Renamed commands in v2.0](#renamed-commands-in-v20) |

## Available Commands

### init: Create a Startup Project

Creates a startup project for RDE structured processing in the current directory.

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit init [PATH options]
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit init [PATH options]
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
├── requirements.txt
└── Dockerfile
```

`init` also creates `input/` (`inputdata/`, `invoice/invoice.json`) and `template/tasksupport/` next to `container/`.

Description of each file:

- **requirements.txt**: Add Python packages you want to use for structured program construction. Run `pip install` as needed.
- **modules**: Store programs you want to use for structured processing.
- **main.py**: Define startup processing for structured programs
- **data/inputdata**: Place data files to be processed by structured processing.
- **data/invoice**: Required for local execution, even if empty.
- **data/tasksupport**: Place files that support structured processing.

!!! tip "File Overwriting"
    Existing files are kept (printed as `Skip: ... already exists.`); nothing is overwritten.

!!! note "Processing code from a skeleton"
    To generate `processing.py`, `main.py`, and a sample test from a registered processing skeleton, use [`new processing`](#new-processing-generate-processing-code-from-a-skeleton).

#### Template-based Initialization

Pass `--template <path>` to reuse your own boilerplate. The path can point to either:

- A directory that contains `pyproject.toml` or `rdeconfig.yaml`/`rdeconfig.yml`
- A direct path to one of the files above

When `--template .` is used, the command searches for `pyproject.toml` in the current directory first.
The configuration file must define template paths under `[tool.rdetoolkit.init]` (pyproject) or an `init` block (rdeconfig):

```toml
[tool.rdetoolkit.init]
entry_point = "tpl/main.py"
modules = "tpl/modules"
tasksupport = "tpl/tasksupport"
inputdata = "tpl/inputdata"
```

Key meaning:

- `entry_point`: File copied to `container/main.py`.
- `modules`: File or directory copied under `container/modules/`.
- `tasksupport`: File or directory mirrored to both `container/data/tasksupport/` and `template/tasksupport/`.
- `inputdata`: Directory copied into `container/data/inputdata/` and `input/inputdata/`.

Relative paths are resolved from the configuration file location, so template repositories stay portable.

#### Specify template paths directly with PATH options

If you prefer not to store personal paths in config files, pass PATH options directly (can be combined). CLI-specified paths override values from config files; existing `pyproject.toml` / `rdeconfig.yaml(yml)` will be updated, or a new `pyproject.toml` will be created when missing.

| Option          | Destination and role                                                                        |
| --------------- | ------------------------------------------------------------------------------------------- |
| `--entry-point` | Copied as `container/main.py` (file only)                                                   |
| `--modules`     | Copied under `container/modules/` (file or directory)                                       |
| `--tasksupport` | Copied to both `container/data/tasksupport/` and `template/tasksupport/` (file or directory) |
| `--inputdata`   | Copied to `container/data/inputdata/` and `input/inputdata/` (directory recommended)        |
| `--other` (repeatable) | Copies arbitrary files or directories under `container/`                             |

Relative paths are saved from the current working directory. CLI-specified paths override values from config files.

##### Sample output with PATH options

Example run with templates under `tpl/`:

```shell
python3 -m rdetoolkit init \
  --entry-point tpl/custom_main.py \
  --modules tpl/modules \
  --tasksupport tpl/tasksupport \
  --inputdata tpl/inputdata \
  --other tpl/extra.txt --other tpl/extras
```

Output (paths vary by environment):

```
Ready to develop a structured program for RDE.
Created from template: /private/tmp/rdt-init-check/container/main.py
Created: /private/tmp/rdt-init-check/container/requirements.txt
Created: /private/tmp/rdt-init-check/container/Dockerfile
Populated /private/tmp/rdt-init-check/container/modules from template directory: /private/tmp/rdt-init-check/tpl/modules
Created: /private/tmp/rdt-init-check/container/data/invoice/invoice.json
Populated /private/tmp/rdt-init-check/container/data/tasksupport from template directory: /private/tmp/rdt-init-check/tpl/tasksupport
Populated /private/tmp/rdt-init-check/template/tasksupport from template directory: /private/tmp/rdt-init-check/tpl/tasksupport
Populated /private/tmp/rdt-init-check/container/data/inputdata from template directory: /private/tmp/rdt-init-check/tpl/inputdata
Populated /private/tmp/rdt-init-check/input/inputdata from template directory: /private/tmp/rdt-init-check/tpl/inputdata
Copied template file /private/tmp/rdt-init-check/tpl/extra.txt into /private/tmp/rdt-init-check/container
Populated /private/tmp/rdt-init-check/container/extras from template directory: /private/tmp/rdt-init-check/tpl/extras
Created: /private/tmp/rdt-init-check/input/invoice/invoice.json
```

After the run, `[tool.rdetoolkit.init]` (or `init` in `rdeconfig.yaml`) is written with the provided paths, stored as relative paths when possible.

### new config: Generate rdeconfig.yaml

Creates an `rdeconfig.yaml` file from a preset or an interactive questionnaire.

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit new config [-o <output dir>] [--preset <preset>] [--force] [--lang <en|ja>]
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit new config [-o <output dir>] [--preset <preset>] [--force] [--lang <en|ja>]
    ```

Available presets:

- `minimal` (default): System and traceback keys only.
- `full`: Includes `multidata_tile` defaults.
- `multitile`: Enables `extended_mode: "MultiDataTile"`.
- `rdeformat`: Enables `extended_mode: "rdeformat"`.
- `smarttable`: Adds SmartTable settings with `save_table_file: false`.
- `interactive`: Guides you through each option. Use `--lang ja` for Japanese prompts.

#### Options

| Option          | Description                                                                                   | Required |
| --------------- | --------------------------------------------------------------------------------------------- | -------- |
| -o(--output)    | Directory that receives `rdeconfig.yaml`. Defaults to the current directory; created if needed. | -        |
| --preset        | Preset name (`minimal`, `full`, `multitile`, `rdeformat`, `smarttable`, `interactive`). Default: `minimal` | -        |
| --force         | Replace an existing `rdeconfig.yaml` without asking. Omit to be prompted.                      | -        |
| --lang          | Prompt language (`en` or `ja`). Applicable only with `--preset interactive`. Default: `en`     | -        |

#### Usage Examples

```bash title="Default (minimal) preset in the current directory"
python3 -m rdetoolkit new config
```

```bash title="MultiDataTile preset into the tasksupport directory"
python3 -m rdetoolkit new config --preset multitile -o container/data/tasksupport
```

```bash title="Interactive questionnaire in Japanese, replacing an existing file"
python3 -m rdetoolkit new config --preset interactive --lang ja --force
```

!!! tip "Interactive Mode"
    When `--preset interactive` is used, the command asks about system, MultiDataTile, SmartTable, and traceback
    settings. Responses are written back into the generated `rdeconfig.yaml` so teams start with validated defaults.

Exit codes: `0` success, `1` writing failed or you declined to overwrite, `2` invalid command line.

### new invoice: Generate invoice.json

Automatically generates `invoice.json` from `invoice.schema.json`. Sets default values based on schema definitions and performs automatic validation after generation.

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit new invoice <invoice.schema.json path> [OPTIONS]
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit new invoice <invoice.schema.json path> [OPTIONS]
    ```

#### Options

| Option | Description | Required |
| ------ | ----------- | -------- |
| -o(--output) | Output file path. Creates `invoice.json` in current directory if omitted. Parent directories are created and an existing file is overwritten | - |
| --fill-defaults/--no-fill-defaults | Whether to fill default values (default: enabled) | - |
| --required-only | Include only required fields | - |
| --format | Output format (`pretty` or `compact`). Default: `pretty` | - |

#### Usage Examples

```bash title="Basic usage"
python3 -m rdetoolkit new invoice tasksupport/invoice.schema.json
```

```bash title="Specify output path"
python3 -m rdetoolkit new invoice tasksupport/invoice.schema.json -o container/data/invoice/invoice.json
```

```bash title="Required fields only, compact format"
python3 -m rdetoolkit new invoice tasksupport/invoice.schema.json --required-only --format compact
```

#### Default Value Priority

1. Schema `default` field
2. First value from schema `examples` array
3. Type-based defaults: string→`""`, number→`0.0`, integer→`0`, boolean→`false`

!!! tip "Detailed API Documentation"
    For programmatic usage, see [Invoice Generator API](../rdetoolkit/cmd/gen_invoice.en.md).

Exit codes: `0` success, `1` the schema could not be read or the invoice could not be written, `2` invalid command line.

### new excelinvoice: Generate an ExcelInvoice

Generates an Excel invoice (`*_excel_invoice.xlsx`) from `invoice.schema.json`.

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit new excelinvoice <invoice.schema.json path> -o <save file path> -m <file or folder>
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit new excelinvoice <invoice.schema.json path> -o <save file path> -m <file or folder>
    ```

#### Options

| Option       | Description                                                                                                      | Required |
| ------------ | ---------------------------------------------------------------------------------------------------------------- | -------- |
| -o(--output) | Output file path. The file name must end with `_excel_invoice.xlsx`. An existing file is overwritten.           | -        |
| -m(--mode)   | Registration mode: file mode `file` (default, one row per file) or folder mode `folder` (one row per folder).   | -        |

!!! tip "Default Output"
    If `-o` is not specified, it will be created as `template_excel_invoice.xlsx` in the execution directory.

Exit codes: `0` success, `1` the schema is invalid, the file name is wrong, or writing failed, `2` invalid command line.

### new processing: Generate Processing Code from a Skeleton

Generates `processing.py`, `main.py`, and a sample test (`tests/test_processing.py`) from a registered processing skeleton (a `ProcessingTemplate` subclass). Implement the generated TODO slots, then run the result with [`run`](#run-run-structured-processing).

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit new processing <skeleton> [--module <module>] [-o <output dir>] [--force]
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit new processing <skeleton> [--module <module>] [-o <output dir>] [--force]
    ```

| Option / Argument | Description | Required |
| ----------------- | ----------- | -------- |
| SKELETON | A skeleton id or unambiguous class name as printed by `rdetoolkit skeletons list` | ○ |
| --module | Import a module that declares skeletons before the lookup (repeatable). Without it, skeletons are found in `*.py` files of the current directory, its `modules/` package, and installed plugins | - |
| -o(--output) | Directory that receives the generated files. Default: the current directory | - |
| --force | Overwrite existing generated files. Without it, the command refuses (exit code `3`) when any of them exists | - |

```bash title="Generate code for a skeleton declared in modules/skeletons.py"
python3 -m rdetoolkit new processing XrdTemplate --module modules.skeletons
```

Exit codes: `0` success, `2` invalid command line, `3` unknown skeleton, module import failure, or an output file already exists.

### validate: Validate RDE Files

Validate RDE-related files with standardized exit codes for CI/CD integration.

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit validate <subcommand> [OPTIONS]
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit validate <subcommand> [OPTIONS]
    ```

#### Available Subcommands

| Subcommand | Description |
|------------|-------------|
| `invoice-schema` | Validate invoice schema JSON structure |
| `metadata-def` | Validate metadata definition JSON structure |
| `invoice` | Validate invoice.json against its schema |
| `metadata` | Validate metadata.json against metadata-def.json |
| `all` | Discover and validate all standard RDE files in a project |

#### Exit Codes

All validate subcommands return standardized exit codes:

| Exit Code | Status | Description |
|-----------|--------|-------------|
| 0 | Success | All validations passed |
| 1 | Validation Failure | Data or schema errors found (or warnings with `--strict`) |
| 2 | Usage Error | Invalid arguments or missing files |

#### Usage Examples

```bash title="Validate invoice schema"
python3 -m rdetoolkit validate invoice-schema tasksupport/invoice.schema.json
```

```bash title="Validate all files in a project"
python3 -m rdetoolkit validate all ./rde-project
```

```bash title="CI/CD integration example"
python3 -m rdetoolkit validate all ./rde-project
if [ $? -ne 0 ]; then
    echo "Validation failed"
    exit 1
fi
```

!!! tip "Detailed Documentation"
    For comprehensive validation documentation including CI/CD integration examples, see [Validation Features](validation.en.md).

### run: Run Structured Processing

Runs structured processing from the project root. The Runner reads `data/inputdata`, `data/invoice`, and `data/tasksupport`, finds `rdeconfig.yaml`, and processes every tile.

=== "Unix/macOS"

    ```shell
    # v2 flow (a flow function or a ProcessingTemplate subclass)
    python3 -m rdetoolkit run <pkg.mod:callable> [--config <overrides.yaml>] [--validate-only]
    # v1 dataset function def f(srcpaths, resource_paths)
    python3 -m rdetoolkit run --legacy <module_or_file::attr>
    ```

=== "Windows"

    ```powershell
    # v2 flow (a flow function or a ProcessingTemplate subclass)
    py -m rdetoolkit run <pkg.mod:callable> [--config <overrides.yaml>] [--validate-only]
    # v1 dataset function def f(srcpaths, resource_paths)
    py -m rdetoolkit run --legacy <module_or_file::attr>
    ```

| Option / Argument | Description |
| ----------------- | ----------- |
| REF | `pkg.mod:callable` for a v2 flow (the current directory is importable), or `module_or_file::attr` with `--legacy` |
| --legacy | Run a v1 dataset function, as passed to `workflows.run(custom_dataset_function=...)` |
| --config | YAML overrides merged over the discovered `rdeconfig.yaml` (v2 flows only) |
| --validate-only | Check the config, mode, and invoice without calling the flow (v2 flows only). Writes no outputs |

Outputs: the RDE output tree under `data/` (`structured/`, `meta/`, `raw/`, images, `logs/`, and `job.failed` on failure). A v2 run prints the run report JSON and saves it as `data/logs/run_report_<run_id>.json`; a v1 run prints the legacy status JSON.

```bash title="Run a v2 flow"
python3 -m rdetoolkit run modules.processing:pipeline
```

```bash title="Run a v1 dataset function"
python3 -m rdetoolkit run --legacy main.py::dataset
```

!!! note "The v1 form without --legacy"
    In v2.0.x a `module_or_file::attr` reference without `--legacy` still runs as a v1 dataset function (without a warning, to keep the output unchanged). `--legacy` becomes required in v2.1, so add it now.

| Exit Code | Description |
|-----------|-------------|
| 0 | Every tile succeeded (or `--validate-only` passed) |
| 1 | The run failed (or validation failed) |
| 2 | Partial: some tiles failed (also used by the parser for an unknown option) |
| 3 | Invalid REF, unresolvable flow, unreadable `--config`, or options that do not apply to `--legacy` |

### report show / report trace: Inspect Run Reports

Reads the run report (`run_report_<run_id>.json`) that `rdetoolkit run` writes to `data/logs/`.

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit report show <run_report.json>
    python3 -m rdetoolkit report trace <run_report.json> [--format json|mermaid|html]
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit report show <run_report.json>
    py -m rdetoolkit report trace <run_report.json> [--format json|mermaid|html]
    ```

- `report show` prints the run id, status, iteration count, one `failed` line per failed node call, and the error message when set.
- `report trace` renders the Call Sequence recorded in the report: every node call in the order it ran (call ids, parent flow, status, argument previews). It is a call log and does not draw data dependencies. `--format` selects `json` (default), `mermaid` (a sequence diagram), or `html` (a standalone page). The rendering goes to stdout; redirect it to save a file.

```bash title="Save the Call Sequence as an HTML page"
python3 -m rdetoolkit report trace data/logs/run_report_<id>.json --format html > trace.html
```

Exit codes: `0` success, `2` invalid command line, `3` the report file is missing or invalid (or, for `report trace`, an unknown `--format`).

### plot: Draw Graphs from CSV

Draws graphs (PNG, optionally interactive HTML) from a CSV file. The options are the same as the Python `csv2graph()` API; see [Visualizing CSV as Graphs](structured_process/csv2graph.en.md) and the [Sample Gallery](structured_process/csv2graph_samples.en.md) for every option.

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit plot <csv path> [OPTIONS]
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit plot <csv path> [OPTIONS]
    ```

```bash title="Overlay and per-series PNGs into data/other_image"
python3 -m rdetoolkit plot sample.csv -o data/other_image --title 'XRD pattern'
```

Exit codes: `0` success, `1` the CSV could not be read or plotted, `2` invalid command line.

### nodes / flows / skeletons / formats: List Registered Components

These commands list what is registered in the current environment. Pass `--module <module>` (repeatable) to import a project module first, and `--json` for machine-readable output.

| Command | Description |
| ------- | ----------- |
| `rdetoolkit nodes list` | List registered node ids (`--plugin` lists only nodes from discovered plugins) |
| `rdetoolkit nodes show <node id>` | Show one node: id, version, tags, and input/output schema |
| `rdetoolkit nodes lint` | Check registered nodes and flows for problems that break runs or reproducibility (duplicate or unstable ids, missing type annotations, and so on) |
| `rdetoolkit flows list` | List registered flow ids |
| `rdetoolkit flows show <flow id>` | Show one flow: id, version, and signature |
| `rdetoolkit skeletons list` | List registered processing skeletons (`ProcessingTemplate` subclasses) |
| `rdetoolkit skeletons show <skeleton>` | Show one skeleton: its id, slots, and slot signatures |
| `rdetoolkit formats list` | List file format handlers that installed plugins declare |

```bash title="List the nodes of a project module"
python3 -m rdetoolkit nodes list --module modules.processing
```

Exit codes: `0` success, `2` invalid command line, `3` unknown id, a module that fails to import, or (for `nodes lint`) lint violations.

### package: Create RDE Submission Archive

Creates an archive (.zip) for submission to RDE. Compresses the specified source directory and excludes directories that match exclusion patterns.

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit package --source-dir <source directory> --output <output archive file> --exclude <exclusion pattern>
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit package --source-dir <source directory> --output <output archive file> --exclude <exclusion pattern>
    ```

#### Options

| Option               | Description                                                                                      | Required |
| -------------------- | ------------------------------------------------------------------------------------------------ | -------- |
| -s(--source-dir)     | Source directory to compress and scan (usually `container/`)                                     | ○        |
| -o(--output)         | Output archive file (e.g., rde_submission.zip). The name must end with `.zip`; an existing file is replaced | -        |
| -e(--exclude)        | Directory names to exclude (repeatable). By default, `.*`, `venv`, `.venv`, and `site-packages` are excluded | -        |

#### Execution Report

When an archive is created, an execution report is written next to the zip (same name, `.md`):

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
    - If `-o/--output` is not specified, the archive is created next to the source directory as `<YYYYMMDD>_<id>_rde_artifact.zip`.
    - The `--exclude` option can be specified multiple times (e.g., `--exclude venv --exclude .git`).

Exit codes: `0` success, `1` the output name is not `.zip`, or archiving or the report failed, `2` invalid command line.

### repro: Export and Re-run a Finished Run

`repro export` archives a run report, the run's input directories (`data/inputdata`, `data/invoice`, `data/tasksupport`), and its effective `rdeconfig.yaml` into one zip. `repro import` unpacks such a zip into a new or empty directory, ready for `rdetoolkit run`.

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit repro export <run_report.json> -o <archive.zip> [--config <overrides.yaml>]
    python3 -m rdetoolkit repro import <archive.zip> <target dir>
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit repro export <run_report.json> -o <archive.zip> [--config <overrides.yaml>]
    py -m rdetoolkit repro import <archive.zip> <target dir>
    ```

- `--config` is required when the run used `rdetoolkit run --config`: the config is archived only if it reproduces the report's `config_digest`.
- `repro import` never overwrites: a non-empty target directory is refused.

Exit codes: `0` success, `2` invalid command line, `3` unreadable report or zip, a missing input directory, a config that does not reproduce the digest, a non-empty target, or an unsafe member path.

### migrate: Find and Convert v1 Code

- `migrate check [PATH]` reports the lines that need v2 migration, one `path:line: finding` per line, and never changes files. Python files are scanned for `custom_dataset_function=` entry calls, `RdeOutputResourcePath` references, v1 handler-shaped classes, and CLI command names renamed in v2.0. Shell, CI, and container files (`*.sh`, `*.yml`, `*.yaml`, `*.toml`, `*.cfg`, `Makefile`, `Dockerfile`) are scanned for renamed CLI commands only.
- `migrate apply [PATH]` converts v1 `custom_dataset_function` callbacks into v2 flows. It previews the converted sources by default (`--dry-run`); with `--no-dry-run` it writes the converted copy to `-o/--output DIR` (default: `<PATH>_migrated` next to the input). The input is never edited.

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit migrate check [PATH]
    python3 -m rdetoolkit migrate apply [PATH] [--no-dry-run] [-o <output dir>]
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit migrate check [PATH]
    py -m rdetoolkit migrate apply [PATH] [--no-dry-run] [-o <output dir>]
    ```

```bash title="Write the converted copy of container/ to container_v2/"
python3 -m rdetoolkit migrate apply container --no-dry-run -o container_v2
```

Exit codes: `0` success, `2` invalid command line (for `migrate apply`, also a missing input path), `3` the path does not exist (`migrate check`), or no Python files were found or the output directory exists or is inside the input (`migrate apply`).

See [Migrating from v1 to v2](../migration_v1_to_v2.en.md) for the migration procedure.

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

## Renamed commands in v2.0

v2.0 reorganized the CLI into `rdetoolkit <noun> <verb>` commands. Commands from v1 keep working in v2.0.x as deprecated aliases that print a warning, and are removed in v2.1. Names that existed only in v2 release candidates were removed without an alias. `rdetoolkit migrate check` reports the old names in your scripts, CI, and container files.

| Old | New | Origin |
|---|---|---|
| `gen-config [OUTPUT_DIR] [--template X] [--overwrite]` | `new config [-o DIR] [--preset X] [--force]` | v1 — deprecated alias kept in v2.0.x, prints a warning, removed in v2.1 |
| `gen-invoice` | `new invoice` | v1 — deprecated alias |
| `make-excelinvoice` | `new excelinvoice` | v1 — deprecated alias |
| `csv2graph` | `plot` | v1 — deprecated alias |
| `artifact --output-archive` | `package -o/--output` | v1 — deprecated alias |
| `run TARGET` (`module::attr`) | `run --legacy TARGET` | v1 — the `::` form without `--legacy` still runs (no warning, for output compatibility); `--legacy` becomes required in v2.1 |
| `init --processing-template X` | `new processing X` | v2 rc only — removed, no alias |
| `run --flow X` | `run X` | v2 rc only — removed |
| `graph REPORT` | `report trace REPORT` | v2 rc only — removed |
| `templates list/describe` | `skeletons list/show` | v2 rc only — removed |
| `nodes describe`, `flows describe` | `nodes show`, `flows show` | v2 rc only — removed |
| `migrate apply --out DIR` | `migrate apply -o/--output DIR` | v2 rc only — removed |

## Shell Completion

Shell completion functionality is available to help complete command and option names. Press the Tab key to display candidate suggestions.

### Supported Shells

- Bash
- Zsh
- Fish
- PowerShell

### Installation

Use the `--install-completion` option to install completion for your current shell:

```bash
python -m rdetoolkit --install-completion
```

After execution, restart your shell to enable the completion feature.

```bash
# Restart shell
exec $SHELL
```

### Manual Installation

To review the completion script before installing manually, use the `--show-completion` option:

```bash
python -m rdetoolkit --show-completion
```

Add the displayed script to your shell configuration file.

#### For Bash

```bash
python -m rdetoolkit --show-completion >> ~/.bashrc
source ~/.bashrc
```

#### For Zsh

```bash
python -m rdetoolkit --show-completion >> ~/.zshrc
source ~/.zshrc
```

### Usage Examples

After installing the completion feature, press the Tab key to display candidates.

```bash
# Command name completion
python -m rdetoolkit <Tab>
# → init, new, plot, validate, run, report, package, etc. will be displayed

# Subcommand completion
python -m rdetoolkit new <Tab>
# → config, invoice, excelinvoice, processing will be displayed

# Option name completion
python -m rdetoolkit new config --<Tab>
# → --output, --preset, --force, --lang, etc. will be displayed

# Option values: --preset takes a preset name (no candidates are offered)
python -m rdetoolkit new config --preset <Tab>
# → type minimal, full, multitile, rdeformat, smarttable, or interactive
```

### Uninstallation

To remove the completion feature, delete the corresponding lines from your shell configuration file.

For Bash, remove lines similar to the following from `~/.bashrc`; for Zsh, from `~/.zshrc`:

```bash
eval "$(_RDETOOLKIT_COMPLETE=bash_source python -m rdetoolkit)"
```

Restart your shell after removal.

## Next Steps

- Understand [Structuring Processing Concepts](../user-guide/structured-processing.en.md)
- Learn how to create [Configuration Files](../user-guide/config.en.md)
- Check detailed features in [API Reference](../api/index.en.md)
