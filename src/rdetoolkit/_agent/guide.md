# rdetoolkit - Detailed Guide

Use public v2 flows and nodes for new RDE programs. Existing programs keep the
v1 frozen compatibility entry.

## Execution model and entry points

The Python Runner owns the lifecycle. Rust primitives live in `rdetoolkit._core`;
user v2 flows do not import it. There is no trace proxy, build/compile stage,
pre-execution DAG, value-lineage inference or node scheduling.

`@flow` executes eagerly with ordinary Python control flow, defaults and values.
`@node` registers a function and records calls during active runs. Pass values
explicitly between nodes; direct calls support ordinary unit tests. Recorded
graphs describe call order after execution.

Use `workflows.run(flow=pipeline)` from Python or
`rdetoolkit run modules.processing:pipeline` from the CLI. The Runner loads
config, detects mode, validates inputs, iterates tiles, calls the flow once per
tile, validates outputs, then writes job.failed and a RunReport. The Python flow
entry returns that report by default. In production main.py, use
`workflows.run(flow=pipeline, exit_on_failure=True)` to exit after finalization
with 1 for failed and 2 for partial. Alternatively use `raise SystemExit(report.exit_code)`.
The public report.exit_code and CLI share success 0, failed 1 and partial 2;
CLI usage errors use 3. The default programmatic call keeps returning its report.

## Executable v2 example

This example writes a normalized text artifact for each current-tile input.

<!-- test: agent-guide-v2 -->
```python
from rdetoolkit import flow, node
from rdetoolkit.nodes import read_text, save_text
from rdetoolkit.types import InputPaths, OutputContext


@node
def normalize_text(text: str) -> str:
    """Normalize a text measurement for structured output."""
    return text.strip() + "\n"


@flow
def pipeline(paths: InputPaths, out: OutputContext) -> None:
    """Write normalized input text for the current tile."""
    for index, source in enumerate(paths.rawfiles):
        save_text(normalize_text(read_text(source)), out, f"structured-{index}.txt")
```

## Flow boundary types

Import the five reserved types from `rdetoolkit.types`. Injection matches the
annotation, not its parameter name, and happens only at the flow boundary.

- InputPaths: inputdata, invoice, tasksupport, raw, rawfiles,
  smarttable_rawfile and invoice_org. Paths supplied to flows are cwd-relative;
  the Runner retains its single resolved root internally. rawfiles contains only
  user inputs. SmartTable row CSVs are carried separately by smarttable_rawfile.
- OutputContext: struct, meta, main_image, other_image, thumbnail, attachment,
  nonshared_raw, raw, invoice and logs. Construct it with from_resource_paths()
  or test builders. The Runner creates directories; builtin nodes save artifacts.
  path_for() and write_bytes() are low-level helpers.
- RdeConfig: strict v2 configuration; custom contains user-defined settings.
  Unknown configuration fields are rejected rather than silently ignored.
- InvoiceData: raw parsed invoice, optional schema, and resolved mode.
  get_custom_fields() reads raw["custom"]; get_field() reads a top-level field.
- IterationInfo: index, total and mode for the current tile. Use this to identify
  tile boundaries instead of manually managing divided directories.

invoice_org is the run-level source selected before tile invocation. ExcelInvoice,
MultiDataTile and RDEFormat use data/temp/invoice_org.json; invoice and SmartTable
use data/invoice/invoice.json. Write edited invoices to the current out.invoice
using save_invoice(), without overwriting another tile's source or output.

## Artifact nodes and metadata

Import helpers from `rdetoolkit.nodes`. read_text and read_json share v1 encoding
rules, including Shift-JIS to CP932. read_excel supports sheet/header/row/column
selection and pandas options; read_excel_fills gives row fill colours.
save_csv supports float_format, header and index. save_json and save_text accept
an output kind. save_invoice and save_meta keep v1 four-space JSON. save_figure
leaves figure ownership with callers. plot_lines accepts x/y columns or pairs,
labels, grid, title, scale, legend, size, DPI and kind; it always closes
internally created figures. bbox_inches=None matches v1 fig.savefig(path).

Use build_meta(values, metadef_path, repeated=...) to construct Metadata from
metadata-def.json. It filters unknown keys, casts schema types/formats, resolves
literal units and $Key references, orders keys by the definition, and assembles
variable rows. Scalar values with variable definitions form a single row;
repeated accepts columns of values. save_meta() writes constant and variable
sections with units. Metadata.custom contains constant values, Metadata.units
contains their units, and Metadata.variable contains rows of value/unit cells.
parse_invoice_meta() applies those rules to invoice.raw["custom"]. User flows need
no v1 Meta import or object adapter.

## Templates and testing

ProcessingTemplate provides a wired flow skeleton. Implement required slots and
preserve the final __flow__. Slot signatures are checked at class definition.
Pass values explicitly instead of hiding state in self. Templates share the
Runner, call log and CLI. Inspect skeletons list/show and nodes list/show.

`rdetoolkit.testing` provides make_input_paths, make_output_context, make_invoice,
run_flow and assert_output_tree. make_invoice puts bare measurement overrides in
custom and accepts explicit invoice sections. run_flow(flow, data_root=root)
runs a real RDE tree in place. Test nodes directly, then test a
real Runner with complete mode fixtures. Compare invoice/metadata content,
units, variable rows, structured files, images, divided layout and job.failed.

## Configuration, modes and errors

The standard root has data/inputdata, data/invoice/invoice.json and
data/tasksupport/{invoice.schema.json,metadata-def.json}. Supply config to
workflows.run or CLI --config. Check normalized RdeConfig.custom when migrating.
Modes are invoice, excelinvoice, multidatatile, smarttable and rdeformat. Input
SmartTable files have priority, followed by Excel invoice files and configured
modes; MultiDataTile uses extended_mode="MultiDataTile" and RDEFormat uses
extended_mode="rdeformat". Each mode controls tile counts and output layout.

Flow on_iteration_error defaults to continue; fail_fast stops at the first
failed tile. Read report.status, iterations, warnings and error. Framework
errors use the integer ERROR_CATALOG and its remediation. StructuredError(msg,
code) preserves a user-supplied error code. @flow(error_code=7,
error_message="Cannot process input: {error}") maps ordinary body failures through
the Runner, while a StructuredError raised in the body keeps its own code and
message; direct calls still raise the original exception, and KeyboardInterrupt
or SystemExit are not mapped. Empty Excel forms use input error 4004 on the flow
entry; the compatibility callback entry retains 999. Input preparation before
mode detection remains explicit code before run(); a flow prepare hook is not
available in this release.

## v1 compatibility and migration

Existing programs keep workflows.run(custom_dataset_function=callback), Config,
RdeInputDirPaths, RdeOutputResourcePath and RdeDatasetPaths. The callback accepts
the unified path object or legacy pair; its JSON return and exit rules remain.
Do not import removed orchestration modules or copy the old processing loop.

Use migrate check, review migrate apply output, and test successful and failing
real inputs. Keep existing programs on their compatibility entry until artifact
parity is demonstrated. Consult the migration guide for intentional differences
and rollback, and the generated error catalog for codes and remediation.
