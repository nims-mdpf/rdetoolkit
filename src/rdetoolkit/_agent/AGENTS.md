# rdetoolkit - Summary Guide for AI Coding Assistants

Use the public v2 API for new structured programs. The v1 callback entry is the
frozen compatibility path for existing programs.

## v2 entry and execution

A `@flow` is eager Python: branches, loops, f-strings, literals and defaults keep
normal semantics. A `@node` registers a reusable function and records calls
inside a run; direct calls remain ordinary functions. The Runner owns config,
mode detection, validation, tile iteration, artifacts, job.failed and RunReport.
The graph is a recorded call sequence, without value lineage or a prebuilt DAG.

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

Run `rdetoolkit run --flow modules.processing:pipeline` from the project root,
or call `workflows.run(flow=pipeline)` after importing `rdetoolkit.workflows`.
For production main.py, use `workflows.run(flow=pipeline, exit_on_failure=True)`.
The default library call returns RunReport; its public exit_code is 0 for success,
1 for failed and 2 for partial. The CLI uses the same mapping and 3 for usage errors.

## Reserved types and output

Import reserved types from `rdetoolkit.types`: `InputPaths`, `OutputContext`,
`RdeConfig`, `InvoiceData`, `IterationInfo`. Injection uses annotations at the
flow boundary only, with arbitrary parameter names. Nodes take explicit args.
InputPaths exposes relative input paths, rawfiles and run-level invoice_org.
SmartTable row CSVs use smarttable_rawfile and are excluded from rawfiles.
InvoiceData.get_custom_fields() reads raw["custom"]; mode is the resolved mode.

Use `rdetoolkit.nodes` for saving: save_csv, save_json, save_text, save_invoice,
save_meta, plot_lines and save_figure. `build_meta(values, metadef_path)` applies
metadata definition types, units, variable rows and ordering before save_meta.
Metadata.units and Metadata.variable preserve units and repeated cells. Construct
OutputContext through its factory or test builders; the Runner creates dirs.

## Templates and tests

Use `ProcessingTemplate` for a reusable domain skeleton. Implement its required
slots; keep the final __flow__ skeleton intact. Templates use the same Runner.
Inspect `rdetoolkit nodes list` and `rdetoolkit templates list` before rebuilding
existing functionality. Use `rdetoolkit.testing` builders make_input_paths,
make_output_context and make_invoice, or run_flow for Runner integration.

## Input and compatibility

The standard tree has data/inputdata, data/invoice/invoice.json, and
 data/tasksupport/{invoice.schema.json,metadata-def.json}. Modes include invoice,
excelinvoice, multidatatile, smarttable and rdeformat. File detection takes
precedence over configured modes. RdeConfig is strict; user settings use custom.
Flow iteration defaults to continue. Existing programs may keep
`workflows.run(custom_dataset_function=...)` and v1 path types; that entry keeps
its legacy JSON return and exit behavior. Migrate new implementations to flows
and compare artifacts, including metadata units and variable values.

Use `get_agent_guide(detailed=True)` or `rdetoolkit agent-guide --detailed` for
signature, error handling, configuration and migration details.
