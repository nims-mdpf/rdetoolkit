# Runner

The Runner is the execution frame that takes on every procedure RDE structured processing
requires. Loading the configuration, determining the mode, validating the invoice and the
schema, creating the directories for each data tile, validating the artifacts, and writing
`job.failed` and the RunReport are all done by the Runner. Your flow is just a function that
is called once per data tile as one step of this procedure.

## Lifecycle

| Stage | Content |
|-------|---------|
| 1. Load the configuration | Searches for `rdeconfig.yaml` and similar files, and resolves the effective `RdeConfig` |
| 2. Determine the mode | Decides between invoice / ExcelInvoice / SmartTable / MultiDataTile / RDEFormat |
| 3. Pre-validation | Validates the invoice, `invoice.schema.json` and `metadata-def.json` |
| 4. Iterate over data tiles | For each tile, creates its directories, injects the reserved types and calls the flow |
| 5. Post-validation | Checks the consistency of the generated artifacts |
| 6. Finalization | Writes the RunReport and the event log, and writes `job.failed` on failure |

`rdetoolkit run --flow ... --validate-only` runs only stages 1 to 3 and does not call the flow.

## Entry points

| Entry point | Accepts | Return value / result |
|-------------|---------|-----------------------|
| `workflows.run(flow=...)` | A flow function or a subclass of `ProcessingTemplate` | `RunReport` |
| `rdetoolkit run --flow pkg.mod:attr` | Same as above (given as a string) | RunReport JSON and an exit code |
| `workflows.run(custom_dataset_function=...)` | A v1 callback function | The same JSON string as v1 |
| `rdetoolkit run module::attr` | A v1 callback function | Same as v1 |

Every entry point runs on the same Runner. Passing both `flow` and `custom_dataset_function`
raises `RdeConfigError` before anything runs (on the CLI, unless exactly one of `TARGET` and
`--flow` is given, the exit code is 3).

## Configuration search

If `config` is not passed, the Runner searches for a configuration file in this order.

1. `rdeconfig.yaml` at the project root
2. `pyproject.toml` at the project root (`[tool.rdetoolkit]`)
3. `tasksupport/rdeconfig.yaml`, `tasksupport/rdeconfig.yml` or `tasksupport/pyproject.toml` under the data root (interpreted as v1 format)

`workflows.run(flow=..., config=...)` accepts either an `RdeConfig` or a dict. A dict is merged
recursively on top of the configuration found by the search; an `RdeConfig` is treated as the
complete configuration. To check the search result before running, use
`rdetoolkit.runner.load_run_config()`. The v2 configuration rejects unknown keys, so a mistyped
key fails with `E1002` at load time.

## Modes and data tiles

| Mode | Unit of iteration | Number of tiles |
|------|-------------------|-----------------|
| invoice | One registration | 1 |
| ExcelInvoice | Each row of the Excel invoice | Number of rows |
| MultiDataTile | Each file in `inputdata/` | Number of files |
| SmartTable | Each row of the table | Number of rows |
| RDEFormat | Existing data in RDE format | 1 |

The mode is decided in the order "SmartTable file > ExcelInvoice file > configuration value".
If `system.extended_mode` in the configuration disagrees with what file detection found, the
warning `W1001 ModeOverriddenByFileDetection` is written to the RunReport and to standard error.

A flow does not need to be aware of the iteration. If it needs the tile number or similar,
declare an argument of type `IterationInfo` and it is injected
([Flows](flow.md#reserved-types-and-dependency-injection)).

## Failure handling and exit codes

`execution.on_iteration_error` selects what happens when a tile fails.

| Value | Behavior | Default for |
|-------|----------|-------------|
| `continue` | Continues processing the remaining tiles | The flow entry points |
| `fail_fast` | Stops at the first failure | The v1 callback entry points |

The state of the whole run and the CLI exit codes are as follows.

| State | Meaning | Exit code | `job.failed` |
|-------|---------|-----------|--------------|
| `success` | All tiles succeeded | 0 | Not written |
| `partial` | Some tiles failed (only with `continue`) | 2 | Not written |
| `failed` | The run failed | 1 | Written |
| (argument error) | Incorrect CLI usage, or the flow cannot be resolved | 3 | — |

When tiles fail, the number of failed tiles is written to standard error (for example,
`1 iteration(s) failed`). Which tiles failed is shown in `iterations[*].status` of the RunReport.

<!-- test: runner-error-policy -->
```python
from rdetoolkit import flow, node, workflows
from rdetoolkit.types import InputPaths


@node(id="docs.runner.check")
def check(paths: InputPaths) -> None:
    if any(path.name == "bad.txt" for path in paths.rawfiles):
        raise ValueError("bad input")


@flow(id="docs.runner.per_file")
def per_file(paths: InputPaths) -> None:
    check(paths)


mode = {"system": {"extended_mode": "MultiDataTile"}}
report = workflows.run(flow=per_file, config=mode)
assert (report.status, report.exit_code) == ("partial", 2)
assert [tile["status"] for tile in report.iterations] == ["failed", "completed"]

report = workflows.run(flow=per_file, config={**mode, "execution": {"on_iteration_error": "fail_fast"}})
assert (report.status, report.exit_code) == ("failed", 1)
assert report.error["code"] == 3001
```

Run this example in a project created by `rdetoolkit init`, with `bad.txt` and `good.txt`
placed in `inputdata/`. In MultiDataTile mode, tiles are created in file-name order.

## `job.failed`

When a run ends as `failed`, the Runner writes `data/job.failed` in the same format as v1.

<!-- illustration: runner-job-failed -->
```text
ErrorCode=3001
ErrorMessage=Node execution failed for call docs.runner.check#1: bad input Remediation: ...
```

- Errors that rdetoolkit detects use the codes of the [error catalog](../rdetoolkit/error_catalog.md)
  (1xxx configuration, 2xxx registration and declaration, 3xxx runtime, 4xxx validation,
  5xxx internal errors). Every error in the catalog has a remediation (`remediation`), which is
  included in the message.
- For a v1 `StructuredError(emsg, ecode)` raised by user code, its code and message are written
  to `job.failed` unchanged.

## RunReport and the call log

For each run, the Runner writes the following files to `data/logs/`.

| File | Content |
|------|---------|
| `run_report_<run_id>.json` | The RunReport (state, mode, configuration digest, per-tile call records, warnings, errors) |
| `events_<run_id>.jsonl` | Events such as `run.started` / `iteration.completed` / `node.failed` |
| `iterations/iteration_<n>.json` | The result of each tile |

<!-- illustration: runner-report -->
```json
{
  "schema_version": "2",
  "run_id": "550956f7318c414eb15a5f9175309f22",
  "status": "success",
  "flow_id": "quickstart.pipeline",
  "mode": "invoice",
  "config_digest": "sha256:...",
  "iterations": [
    {
      "index": 0,
      "status": "completed",
      "node_calls": [
        {"call_id": "quickstart.normalize#2", "node_id": "quickstart.normalize", "seq": 2, "status": "completed", "duration_ms": 1.45}
      ],
      "error": null
    }
  ],
  "warnings": [],
  "error": null
}
```

The RunReport is used by `rdetoolkit report show` (summary), `rdetoolkit graph` (Call Sequence)
and `rdetoolkit repro export` (an archive of the RunReport, inputs and configuration).
If you need the same JSON as the v1 return value, use `report.to_legacy_statuses()`.

## What the Runner does not provide

rdetoolkit v2 is a batch harness for RDE structured processing, not a general-purpose workflow
engine. It does not provide scheduling, parallel execution of nodes, resuming from the middle
of a run, or result caching. To redo the processing, run it again.

## Related pages

- [Flows](flow.md) — the functions the Runner calls, and dependency injection
- [CLI reference](../reference/cli.md) — `run` / `report` / `graph` / `repro`
- [ADR-023](../adr/0023-single-runner-contract-compat.md) — v1 compatibility and the single Runner
