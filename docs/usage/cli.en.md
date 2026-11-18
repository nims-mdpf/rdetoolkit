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
| Validate | `validate invoice`, `validate invoice-schema`, `validate metadata`, `validate metadata-def`, `validate all`, `doctor` | Validate RDE schema and data files; check that a project can run |
| Run | `run`, `test` | Run structured processing (v2 flow, or a v1 dataset function with `--legacy`); run the project's pytest tests |
| Inspect | `report show`, `report trace`, `report diagnose`, `report explain`, `nodes list/show/lint`, `flows list/show`, `skeletons list/show`, `formats list` | Read run reports and list registered components |
| Package | `package`, `repro export`, `repro import`, `repro inspect`, `repro to-pytest` | Create the submission archive, export, inspect and re-import a run, and turn an archived run into a regression test |
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
python3 -m rdetoolkit validate all ./rde-project --strict --require-files
if [ $? -ne 0 ]; then
    echo "Validation failed"
    exit 1
fi
```

Finding no standard file exits `0` by default. `--require-files` makes it a validation failure (exit `1`, error type `no_target_files`) that lists the searched directories, so CI cannot pass after validating nothing; `--strict` makes warnings fail. Use both in CI.

!!! tip "Detailed Documentation"
    For comprehensive validation documentation including CI/CD integration examples, see [Validation Features](validation.en.md).

### doctor: Check That a Project Can Run

Checks the inputs, config, mode, invoice and metadata definitions of a project with the Runner's own validate-only preflight, run on a temporary copy of the inputs. `--ref pkg.mod:callable` also imports a flow and checks that the Runner can inject its parameters. `--module NAME` (repeatable) imports a project module and adds the `rdetoolkit nodes lint` findings (check `nodes.lint`, for example E2001 for a duplicate node id). Doctor never calls the flow or its `prepare=` hook and writes nothing into the project. Modules are imported only when `--ref` or `--module` names them.

These are static checks only: the flow is not executed, so a passing doctor does not prove that processing succeeds. The text output says so on its second line, and the JSON has `"flow_executed": false`.

```bash title="Preflight a project, with a flow, as JSON"
python3 -m rdetoolkit doctor --format json --ref modules.processing:pipeline
```

```bash title="CI form: fail on warnings, lint the project's nodes"
python3 -m rdetoolkit doctor --strict --module modules.processing
```

Missing required inputs (`inputdata/`, `invoice/invoice.json`, `tasksupport/invoice.schema.json`) always fail. An `inputdata/` without any file is the warning `NoInputFiles` (check `inputs.files`): an invoice-only registration is valid, but nothing would be processed. `--strict` makes every warning fail, which matches `validate all --strict --require-files`. The JSON also reports `"strict"`.

Exit codes: `0` passed (warnings allowed without `--strict`), `1` a check failed or a warning was reported under `--strict`, `2` invalid command line, `3` `PROJECT_DIR` is not a directory or `--format` is not `text`/`json`. The JSON format and every check are described in [Diagnostic Commands (JSON)](diagnostics.en.md).

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
| --validate-only | Check the config, mode, and invoice without calling the flow (v2 flows only). In ExcelInvoice / SmartTable mode only the invoice files and the schema are checked, because the rows complete the invoice. Writes no outputs |
| --explain | With `--validate-only`: explain the current input snapshot instead of validating through a run. Prints the selected mode and its reasons, the tile plan, artifact stages, the config source, a magic variable preview, a graph input preview and warnings. The flow module is not imported, `prepare=` and the flow are not called, and nothing is written |
| --format | `text` (default) or `json`, with `--explain` only. JSON follows the checked-in schema `rdetoolkit/static/registration-explain.schema.json` (`schema_version` `"1"`) and is printed with sorted keys, so repeated runs on the same inputs give identical bytes. A failure prints one `{"status": "failed", "error": ...}` envelope on stdout and exits 1 |

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

```bash title="Explain the registration plan as JSON without running the flow"
python3 -m rdetoolkit run modules.processing:pipeline --validate-only --explain --format json
```

The `graph_preview` section reports, for every `.csv` and `.tsv` input of every tile, how the Graph Engine's builtin table detection would read it: `detected` with the selected reader (`standard`, `noheader`, `transpose`, `meta_block`), `ambiguous` with every candidate, its confidence and evidence, or `unreadable` for an empty or unreadable file. It also gives the encoding, delimiter, column count and data-row count. Column names and cell values are never printed. Inputs inside an archive that is extracted only at run time (SmartTable, ExcelInvoice, RDEFormat) are `skipped`, and the section is `deferred` when nothing else is tabular. Reader plugins, the flow's own plot settings and rendering are not checked, so name the reader with `csv_format=<id>` or `--csv-format <id>` when a file is `ambiguous`.

### test: Run the Project's pytest Tests

`rdetoolkit test [PATH] [PYTEST_ARGS]...` runs `python -m pytest` with the same interpreter in the current directory, forwards every argument unchanged, and exits with pytest's exit code. A failing test that used the `rde_runner` or `rde_run` fixture also gets an `rdetoolkit: retained runs` section listing each retained data root, run report, diagnostics sidecar and `job.failed`. Plain `pytest` is fully equivalent and remains the recommended command in CI. pytest is not installed with rdetoolkit: `pip install "rdetoolkit[testing]"`. See [Testing structured processing](testing.en.md#rdetoolkit-test).

```bash title="Run the project's tests, stopping at the first failure"
python3 -m rdetoolkit test tests/ -k xrd -x
```

Put `--` first to pass an option rdetoolkit would otherwise read itself: `rdetoolkit test -- --help`.

Exit codes are pytest's: `0` all collected tests passed, `1` some tests failed, `2` pytest is not installed (an installation hint is printed) or the run was interrupted, `3` pytest internal error, `4` pytest rejected the command line, `5` no tests were collected.

### report show / report trace / report diagnose / report explain: Inspect Run Reports

Reads the run report (`run_report_<run_id>.json`) that `rdetoolkit run` writes to `data/logs/`.

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit report show <run_report.json>
    python3 -m rdetoolkit report trace <run_report.json> [--format json|mermaid|html]
    python3 -m rdetoolkit report diagnose <run_report.json> [--json] [--fail-on-error]
    python3 -m rdetoolkit report explain <run_report.json> [--format text|json] [--iteration N] [--full-traceback]
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit report show <run_report.json>
    py -m rdetoolkit report trace <run_report.json> [--format json|mermaid|html]
    py -m rdetoolkit report diagnose <run_report.json> [--json] [--fail-on-error]
    py -m rdetoolkit report explain <run_report.json> [--format text|json] [--iteration N] [--full-traceback]
    ```

- `report show` prints the run id, status, iteration count, one `failed` line per failed node call, and the error message when set.
- `report trace` renders the Call Sequence recorded in the report: every node call in the order it ran (call ids, parent flow, status, argument previews). It is a call log and does not draw data dependencies. `--format` selects `json` (default), `mermaid` (a sequence diagram), or `html` (a standalone page). The rendering goes to stdout; redirect it to save a file.
- `report diagnose` lists each recorded failure with its iteration, node id, call id, catalog code, and remediation, and checks which `iterations/` details and event log next to the report belong to the same run. It never prints exception text or argument previews. `--json` prints the [diagnostics envelope](diagnostics.en.md); it exits `0` when the report was diagnosed, even for a failed run, and `1` with `--fail-on-error` when the run recorded a failure.
- `report explain` says why one run failed: phase, tile, node, exception, source location and remediation. It reads the [failure diagnostics file](diagnostics.en.md#failure-diagnostics-file) `diagnostics_<run_id>.json` next to the report; without it (an older run, a report copied alone) the explanation uses the report only and says the diagnostics are unavailable. A successful run is given no cause. `--iteration N` explains only tile `N`; `--full-traceback` adds every recorded frame (file, line, function). The text output shows the recorded exception messages; `--format json` prints the [diagnostics envelope](diagnostics.en.md#report-explain) and copies no runtime text. Nothing is written.

```bash title="Save the Call Sequence as an HTML page"
python3 -m rdetoolkit report trace data/logs/run_report_<id>.json --format html > trace.html
```

```bash title="Explain a failed run as JSON"
python3 -m rdetoolkit report explain data/logs/run_report_<id>.json --format json
```

Exit codes: `0` success (for `report explain`, also when the run itself failed), `1` `report diagnose --fail-on-error` found a recorded failure, `2` invalid command line, `3` the report file is missing or invalid (or, for `report trace` and `report explain`, an unknown `--format`; for `report explain`, an `--iteration` that is not in the report).

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

Options added in v2:

| Option | Description |
| ------ | ----------- |
| `--csv-format auto` | Detect the format, encoding and delimiter from a read-only sample (at most 64 KiB and 50 rows). An unclear file is an error naming the candidates and their evidence, never a guess. `--csv-format` also accepts `meta_block` and the id of a reader installed through the `rdetoolkit.graph.readers` entry points; the default stays `standard` |
| `--detect` | Print what `--csv-format auto` would do (selected reader, evidence, column names, row count) and exit with `0` without plotting |
| `--xmin`, `--xmax`, `--ymin`, `--ymax` | Set one side of an axis range; the other side stays automatic. Combining one of them with `--xlim`/`--ylim` on the same axis is a usage error (exit code `2`), as are invalid bounds (non-finite, equal, or `<= 0` on a log axis) |

Requests that cannot be honoured (an invalid `--mode`, `--mode individual` with `--no-individual`, invalid axis limits) fail before any file is written. For the Python API behind this command, see [Graph Engine](structured_process/graph_engine.en.md).

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

`nodes lint --json` prints the findings in the [diagnostics envelope](diagnostics.en.md) instead of text, with the same exit codes.

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

`repro export` archives a run report, the run's input directories (`data/inputdata`, `data/invoice`, `data/tasksupport`), and its effective `rdeconfig.yaml` into one zip. `repro import` unpacks such a zip into a new or empty directory, ready for `rdetoolkit run`. `repro inspect` shows what an archive records for reproduction, and what it does not, without extracting it.

There are two kinds of archive:

- **Full archive** (the default) for local reproduction. It holds every input file, the invoice, the raw run report and the effective config, which may include unpublished research data, personal data or credentials. Before writing it, `repro export` prints to stderr how many files and bytes each directory contributes, with a warning. Nothing is uploaded; review the archive before you share it, and do not attach it to an external agent or issue by default. Its `repro_manifest.json` (`schema_version` `"3"`, `format: "rdetoolkit.repro-manifest"`, `archive_kind: "full"`, `replayable: true`) lists every member (`files`: `path`, `byte_count`, `sha256`, sorted by path), including the report and `rdeconfig.yaml`. Each digest is taken from the bytes as they are written into the zip.
- **Metadata only** (`--manifest-only`). The zip holds one `repro_manifest.json` (`schema_version` `"3"`, `archive_kind: "manifest-only"`, `replayable: false`): file counts and bytes per directory, each file's size and SHA-256 digest under a numeric `file_id` (no file names), the report's `config_digest`, the provenance below, and the [`report diagnose` envelope](diagnostics.en.md). It contains no input bytes, invoice or config values, or report text, and `repro import` refuses it. A digest still identifies a file to anyone who has the same file, so this is not anonymisation.

Both kinds record `provenance`, captured when `repro export` runs. A run report does not record its interpreter, so these values describe the environment that exported the run, which may differ from the one that ran it. Each attribute has a `status`: `known`, `unavailable` (with a `reason`), or `not_included`.

| Attribute | Recorded |
| --- | --- |
| `rdetoolkit` | `version` |
| `python` | `implementation`, `version` |
| `platform` | `system`, `release`, `machine` |
| `git` | `commit` and `dirty` (tracked files differ from the commit) when the project directory is in a git checkout. Git runs locally with prompts, optional locks and `core.fsmonitor` disabled; if git is missing, fails, or takes too long, the attribute is `unavailable` and the export continues. |
| `lockfile` | `name` and `sha256` of the first regular file among `uv.lock`, `poetry.lock`, `pdm.lock`, `Pipfile.lock`, `pylock.toml` at the project root. The lockfile itself is not archived; a link is ignored. |
| `source_code` | Always `not_included`: repro never archives your flow's source code. Check it out separately, at the recorded commit when one is known. |

No host name, user name, absolute path, git remote or branch name is recorded.

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit repro export <run_report.json> -o <archive.zip> [--config <overrides.yaml>]
    python3 -m rdetoolkit repro export <run_report.json> -o <metadata.zip> --manifest-only
    python3 -m rdetoolkit repro inspect <archive.zip> [--format json]
    python3 -m rdetoolkit repro import <archive.zip> <target dir>
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit repro export <run_report.json> -o <archive.zip> [--config <overrides.yaml>]
    py -m rdetoolkit repro export <run_report.json> -o <metadata.zip> --manifest-only
    py -m rdetoolkit repro inspect <archive.zip> [--format json]
    py -m rdetoolkit repro import <archive.zip> <target dir>
    ```

- `--config` is required when the run used `rdetoolkit run --config`: the config is archived only if it reproduces the report's `config_digest`. The digest is SHA-256 over the effective config's key-sorted JSON, not over the YAML file, so the archived `rdeconfig.yaml` may be written differently and still match.
- `repro export` never replaces an existing `-o` file. It refuses inputs that are symbolic links or special files (copy the data into the project instead) and an unreadable directory, rather than following or skipping them. A report whose name does not start with `run_report_` is stored as `data/logs/run_report_export.json`.
- `repro import` never overwrites: a non-empty target directory, or a target that is a symbolic link, is refused. It accepts only the export layout (`data/{inputdata,invoice,tasksupport}/…`, one `data/logs/run_report_*.json`, `rdeconfig.yaml`, and a full `repro_manifest.json` with `schema_version` `"3"` or `"1"`), and refuses before extracting anything: absolute or `..` paths, empty path parts, backslashes, control characters (including a NUL that would shorten a name), links, devices and other special entries, encrypted entries, compression other than stored or deflate, two names that differ only in case or Unicode normalisation, a file used as a directory, more than 100,000 entries, more than 16 GiB uncompressed, a path over 1,024 characters or 64 levels, a manifest over 64 MiB, and an archive that expands more than 1,100:1 (beyond what deflate can do, so only overlapping or forged entries). On Windows it also refuses `:`, names ending in `.` or a space, and device names such as `CON` or `AUX`. The same limits apply when exporting, so a refused export never yields an archive that import would reject.
- For a `"3"` manifest, import first requires the file members and the manifest's `files` list to name the same files with the same sizes, then checks each member's SHA-256 while extracting it. A member that is missing, unlisted, resized or changed is refused with its name, before the target appears.
- The archive is extracted into a hidden staging directory next to the target, then the archived config is reloaded and must give the same `config_digest` as the manifest and the report. Only then is the staging directory renamed to the target; on any failure it is deleted and the target is left as it was. Matching digests show that the parts belong together, not who made the archive or that its data or config can be trusted: review them before running your flow on them.
- An archive written before this version (`schema_version` `"1"`) is still imported. It has no per-file checksums (its members are checked only against the zip CRCs) and no provenance, and import says so on stderr: `Provenance unavailable: …`. To get both, export the run again with the current rdetoolkit.
- `repro inspect` applies the same member checks as import, then reads (never writes) every member of a full `"3"` archive and compares it with the manifest. It prints three groups: the verified inputs, the known provenance, and what is unknown or unavailable (always including `source_code`). `--format json` emits the [diagnostics envelope](diagnostics.en.md) with `command: "repro inspect"`, `archive`, `inputs` (`status` `verified`, `mismatch`, `unverifiable` for `"1"`, or `not_included` for metadata-only), and `provenance` (`captured_at`, `known`, `unavailable`). Its findings have `code: null`: `ReproChecksumMismatch` (error, per member), `ReproProvenanceUnavailable` (warning, per attribute), `ReproInputsUnverifiable` (warning), `ReproInputsNotIncluded` and `ReproSourceNotIncluded` (info). Values read from the manifest are shown only if they are short printable text in the expected form; anything else is reported as unreadable.
- None of this makes a rerun deterministic. Matching config and file digests mean you have the same inputs and configuration. A different interpreter, dependency set, operating system or flow source can still change the result, and the provenance only tells you which of these the archive could record.

Exit codes: `0` success, `2` invalid command line, `3` unreadable report or zip, a missing or unsafe input, an existing output, a config that does not reproduce the digest, a non-empty target, a member that differs from the manifest (import and inspect), or an archive member, manifest or digest that import does not accept. `repro inspect` exits `0` when provenance is merely unavailable.

#### repro to-pytest: Turn an Archived Run into a Regression Test

`repro to-pytest` writes an editable pytest module that declares the archived run as an [`rde_case`](testing.en.md#from-a-repro-archive), so a fixed failure stays covered.

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit repro to-pytest <archive.zip> --ref <pkg.mod:flow> -o <tests/test_x.py> --project <imported dir>
    python3 -m rdetoolkit repro to-pytest <archive.zip> --ref <pkg.mod:flow> -o <tests/test_x.py> --stage-inputs <new dir>
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit repro to-pytest <archive.zip> --ref <pkg.mod:flow> -o <tests\test_x.py> --project <imported dir>
    py -m rdetoolkit repro to-pytest <archive.zip> --ref <pkg.mod:flow> -o <tests\test_x.py> --stage-inputs <new dir>
    ```

- `--ref pkg.mod:callable` is required: the flow is never guessed from the archived `flow_id`. Every part must be a Python identifier. The module is imported from the working directory, as `rdetoolkit run` does, which runs its top-level code; the flow itself is never called, and no bytecode cache is written.
- Only a full archive is accepted. It is checked like `repro inspect`: unsafe member names are refused, and a member that differs from `repro_manifest.json` stops the command. A `--manifest-only` archive is refused because it holds neither the inputs nor the report.
- Choose where the case's inputs come from, exactly once:
    - `--project DIR`: an existing project, typically made with `repro import`. Its `data/{inputdata,invoice,tasksupport}` files must equal the archived ones (same names and SHA-256) and its effective config must reproduce the archived `config_digest`; otherwise the differences are listed and nothing is written. This needs a `schema_version` `"3"` archive.
    - `--stage-inputs DIR`: extract the archive into the new or empty `DIR` with the same checks as `repro import`, and use it. This copies the raw research inputs, invoice and config into `DIR`, possibly inside your test folder: use it only when that data may be stored there, and keep the directory out of version control otherwise. It also works for a `"1"` archive (no per-file checksums; the generated file says so).
- The generated test expects `"success"`, the behaviour after the fix. The archived status is quoted in a comment but never becomes the expectation unless you pass `--expect-status success|partial|failed` after confirming the outcome; with `failed` or `partial` the archived error code is added as `expect_error_code`. Before the fix, the generated test therefore fails.
- The project path is written relative to the generated file. The archive contributes only its run id (in the test name), its status and error code, and the provenance as `#` comments (an environment difference, such as another rdetoolkit or Python version, is also printed as a warning). Report messages, `flow_id`, config values and input file names are never copied.
- An existing `-o` file is replaced only with `--force` (in one rename); a link or directory is always refused, and the file must end in `.py`.

Exit codes: `0` success, `2` invalid command line (including neither or both of `--project` and `--stage-inputs`, or an unknown `--expect-status`), `3` an unreadable, unsafe, metadata-only or modified archive, an invalid or unimportable `--ref`, a project that differs from the archive, a non-empty `--stage-inputs` directory, or an output that exists or cannot be written.

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
