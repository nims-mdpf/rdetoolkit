# CLI Reference

A list of every rdetoolkit command and option. Commands can be run either as `rdetoolkit` or as
`python -m rdetoolkit`. Each command shows the same content with `--help`.

For details on the commands carried over from v1 (`init`, `gen-invoice` and so on), see
[Command Line Interface](../usage/cli.md); for `csv2graph`, see [Visualizing CSV as Graphs](../usage/structured_process/csv2graph.md).

## Exit codes

The v2 commands (`run`, `nodes`, `flows`, `templates`, `formats`, `graph`, `report`, `repro`, `migrate`)
share the same exit codes (`validate` uses its own exit codes; see below).

| Code | Meaning |
|------|---------|
| 0 | Success (`success` for `run`) |
| 1 | The run failed (`failed` for `run`) |
| 2 | Only some data tiles failed (`partial` for `run`) |
| 3 | Usage error (missing or conflicting arguments, a flow or node that cannot be resolved, and `nodes lint` violations) |

The exit code of `run` is independent of the error code written to `job.failed`.

## Running structured processing

### `rdetoolkit run`

Runs structured processing. Specify **exactly one** of a v1 callback function (`TARGET`) or a v2
flow (`--flow`). Specifying both, or neither, gives exit code 3.

| Argument / option | Default | Description |
|-------------------|---------|-------------|
| `TARGET` | — | A v1 callback function, in the form `module_or_file::attr` |
| `--flow` | — | A v2 flow or `ProcessingTemplate` subclass, in the form `pkg.mod:attr` |
| `--validate-only` | Off | Performs only configuration, mode and pre-validation, without calling the flow |
| `--config` | — | A YAML file that overrides the configuration. Applied recursively on top of the configuration found by the search |

When run with `--flow`, it writes the RunReport JSON to standard output and also saves it to
`data/logs/run_report_<run_id>.json`. The current directory is added to the import path, so you
can name modules in the project as they are.

<!-- illustration: cli-run -->
```bash
$ rdetoolkit run --flow modules.flow:pipeline
$ rdetoolkit run --flow modules.processing:MyProcessing --validate-only
$ rdetoolkit run --flow modules.flow:pipeline --config overrides.yaml
$ rdetoolkit run main.py::dataset
```

## Inspecting nodes, flows and templates

`--module` names a module to import before the inspection, and can be given more than once. Use
it when you want the listing to include the nodes and flows of your project.

### `rdetoolkit nodes list`

Lists the IDs of the registered nodes. Built-in nodes are always included.

| Option | Default | Description |
|--------|---------|-------------|
| `--json` | Off | Writes machine-readable JSON |
| `--plugin` | Off | Shows only the nodes registered by plugins |
| `--module` | — | A module to import before listing (can be given more than once) |

### `rdetoolkit nodes describe`

Shows a node's NodeSpec (argument and return types, default values, tags, version, and definition
location).

| Argument / option | Default | Description |
|-------------------|---------|-------------|
| `NODE_ID` | — | The node ID |
| `--json` | Off | Writes machine-readable JSON |
| `--module` | — | A module to import before showing (can be given more than once) |

### `rdetoolkit nodes lint`

Statically checks the registrations of nodes, flows and templates. It reports missing type
annotations, unstable node IDs (`E2005`), duplicate reserved-type annotations (`E2006`), misuse of
templates and similar problems, and returns exit code 3 if there are any violations.

| Option | Default | Description |
|--------|---------|-------------|
| `--module` | — | A module to import before checking (can be given more than once) |

### `rdetoolkit flows list`

Lists the IDs of the registered flows.

| Option | Default | Description |
|--------|---------|-------------|
| `--json` | Off | Writes machine-readable JSON |
| `--module` | — | A module to import before listing (can be given more than once) |

### `rdetoolkit flows describe`

Shows a flow's registration information.

| Argument / option | Default | Description |
|-------------------|---------|-------------|
| `FLOW_ID` | — | The flow ID |
| `--json` | Off | Writes machine-readable JSON |
| `--module` | — | A module to import before showing (can be given more than once) |

### `rdetoolkit templates list`

Lists the registered template skeleton classes. If `--module` is not given, it searches the
`*.py` files in the current directory and everything under `modules/` for modules that declare a
skeleton, and also loads the installed plugins.

| Option | Default | Description |
|--------|---------|-------------|
| `--json` | Off | Writes machine-readable JSON |
| `--module` | — | A module to import before listing (can be given more than once) |

### `rdetoolkit templates describe`

Shows a template's slots, hooks and domain types.

| Argument / option | Default | Description |
|-------------------|---------|-------------|
| `TEMPLATE_ID` | — | The template ID or class name |
| `--json` | Off | Writes machine-readable JSON |
| `--module` | — | A module to import before showing (can be given more than once) |

### `rdetoolkit formats list`

Lists the file formats declared by the installed plugins.

| Option | Default | Description |
|--------|---------|-------------|
| `--json` | Off | Writes machine-readable JSON |

## Run records

### `rdetoolkit report show`

Shows the RunReport status, the number of data tiles, and the failed calls and their errors.

| Argument | Description |
|----------|-------------|
| `RUN_REPORT` | Path to `run_report_<run_id>.json` |

### `rdetoolkit graph`

Writes the order of node calls recorded in a RunReport (the Call Sequence). It is not a data
flow diagram.

| Argument / option | Default | Description |
|-------------------|---------|-------------|
| `RUN_REPORT` | — | Path to `run_report_<run_id>.json` |
| `--format` | `json` | One of `json`, `mermaid` or `html` |

### `rdetoolkit repro export`

Packs a RunReport, the inputs of that run, and the configuration actually used into one zip.

| Argument / option | Default | Description |
|-------------------|---------|-------------|
| `RUN_REPORT` | — | Path to `run_report_<run_id>.json` |
| `--output` | — (required) | The zip file to write |
| `--config` | — | The override YAML used in that run (same format as `run --config`) |

If the configuration does not match the RunReport's `config_digest`, it exits with code 3 without
creating the archive.

### `rdetoolkit repro import`

Extracts a `repro export` archive under a new directory and reconstructs the inputs.

| Argument | Description |
|----------|-------------|
| `ARCHIVE_PATH` | A zip created by `repro export` |
| `TARGET` | The directory to extract into |

## Migration

### `rdetoolkit migrate check`

Reports the places that need migration from v1 to v2 in one Python file, or in every Python file
under a directory.

| Argument | Default | Description |
|----------|---------|-------------|
| `PATH` | The current directory | The file or directory to check |

### `rdetoolkit migrate apply`

Converts v1 callbacks into v2 flows. It does not modify the input files. By default it only shows
the conversion result, and writes files only when `--no-dry-run` is given.

| Argument / option | Default | Description |
|-------------------|---------|-------------|
| `PATH` | The current directory | The file or directory to convert |
| `--out` | — | The directory to write to (a location separate from the input) |
| `--dry-run` / `--no-dry-run` | `--dry-run` | Whether to only preview, or to write |

For the detailed procedure, see [Migrating from v1 to v2](../migration_v1_to_v2.md).

## Creating projects and RDE files

### `rdetoolkit init`

Creates a project skeleton for structured processing. Without options it creates the same
skeleton as v1.

| Option | Default | Description |
|--------|---------|-------------|
| `--processing-template` | — | The name of a registered template. Creates a user class with the slots as TODOs, a sample test and `main.py` |
| `--module` | — | A module that provides the template (can be given more than once) |
| `--force` | Off | Overwrites files that `--processing-template` would create if they already exist |
| `--template` | — | A skeleton configuration file (`pyproject.toml` / `rdeconfig.yaml`) or a directory that contains one |
| `--entry-point` | — | A file to copy to `container/main.py` |
| `--modules` | — | A file or directory to copy to `container/modules/` |
| `--tasksupport` | — | A file or directory to copy to `tasksupport/` |
| `--inputdata` | — | A directory to copy to `inputdata/` |
| `--other` | — | Additional files to copy to `container/` (can be given more than once) |

### `rdetoolkit version`

Shows the rdetoolkit version.

### `rdetoolkit gen-config`

Creates an `rdeconfig.yaml` skeleton.

| Argument / option | Default | Description |
|-------------------|---------|-------------|
| `OUTPUT_DIR` | The current directory | The output directory |
| `--template` | `minimal` | The kind of skeleton |
| `--overwrite` | Off | Replaces an existing `rdeconfig.yaml` |
| `--lang` | `en` | The language used by the interactive skeleton |

### `rdetoolkit gen-invoice`

Creates `invoice.json` from `invoice.schema.json`.

| Argument / option | Default | Description |
|-------------------|---------|-------------|
| `SCHEMA_PATH` | — | Path to `invoice.schema.json` |
| `--output` / `-o` | `./invoice.json` | The output destination |
| `--fill-defaults` / `--no-fill-defaults` | On | Fills in default values according to type |
| `--required-only` | Off | Writes only the required fields |
| `--format` | `pretty` | `pretty` or `compact` |

### `rdetoolkit make-excelinvoice`

Creates an ExcelInvoice from `invoice.schema.json`.

| Argument / option | Default | Description |
|-------------------|---------|-------------|
| `INVOICE_SCHEMA_JSON_PATH` | — | Path to `invoice.schema.json` |
| `--output` / `-o` | `./template_excel_invoice.xlsx` | The output destination |
| `--mode` / `-m` | `file` | The registration mode: `file` or `folder` |

### `rdetoolkit validate invoice-schema`

Validates the structure and content of `invoice.schema.json` (argument `SCHEMA_PATH`).

### `rdetoolkit validate metadata-def`

Validates the structure of `metadata-def.json` (argument `METADATA_DEF_PATH`).

### `rdetoolkit validate invoice`

Validates `invoice.json` (argument `INVOICE_PATH`) against `invoice.schema.json`. Specify the
schema with `--schema` / `-s` (required).

### `rdetoolkit validate metadata`

Validates `metadata.json` (argument `METADATA_PATH`) against a metadata definition. Specify the
definition file with `--schema` / `-s` (required).

### `rdetoolkit validate all`

Finds the standard RDE files in a project and validates all of them. The argument `PROJECT_DIR`
defaults to the current directory.

Every `validate` subcommand has the following options in common.

| Option | Default | Description |
|--------|---------|-------------|
| `--format` / `-f` | `text` | `text` (for people) or `json` (machine-readable) |
| `--strict` / `--no-strict` | Off | Treats warnings as failures too |
| `--quiet` / `-q` | Off | Shows only errors (`text` only) |

Unlike the v2 commands, the exit codes of `validate` are 0 = validation succeeded, 1 = validation
errors, and 2 = usage error (wrong arguments or a missing file).

### `rdetoolkit artifact`

Creates the archive (zip) to submit to RDE, and writes the results of inspecting the source code
as a report.

| Option | Default | Description |
|--------|---------|-------------|
| `--source-dir` / `-s` | — (required) | The directory to archive and inspect |
| `--output-archive` / `-o` | — | The zip file to write |
| `--exclude` / `-e` | `venv`, `site-packages` | Directory names to exclude |

### `rdetoolkit csv2graph`

Creates graphs from CSV files. For its options, see [Visualizing CSV as Graphs](../usage/structured_process/csv2graph.md).

### `rdetoolkit agent-guide`

Shows a guide for AI coding assistants. With `--detailed` it shows a version that includes
detailed patterns and an API reference.

## Shell completion

`--install-completion` sets up completion for the current shell, and `--show-completion` prints
the completion script.
