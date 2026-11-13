# Diagnostic Commands (JSON)

Three commands print the same versioned JSON envelope, so a script or a coding agent can check a project and read a failed run without parsing human-readable text. Without the JSON option each command prints text.

| Command | Checks | Exit codes |
| ------- | ------ | ---------- |
| `rdetoolkit nodes lint --json` | Registered nodes, flows, and processing skeletons | `0` clean; `3` any finding (warnings too) or a module that fails to import; `2` invalid command line |
| `rdetoolkit doctor --format json` | Project inputs, config, mode, invoice and metadata definitions; with `--ref`, a flow | `0` passed (warnings allowed); `1` a check failed; `3` `PROJECT_DIR` is not a directory or `--format` is unknown; `2` invalid command line |
| `rdetoolkit report diagnose <run_report.json> --json` | The failures recorded in a run report | `0` diagnosed (also when the run failed); `1` with `--fail-on-error`, the run recorded a failure; `3` the report is missing or not a supported run report; `2` invalid command line |

## The envelope

The [JSON Schema](diagnostics.schema.json) defines it. Every document has:

- `schema_version`: `"1"`. Check it; ignore keys you do not know within a supported version.
- `format`: `"rdetoolkit.diagnostics"`, and `producer`: `{"name": "rdetoolkit", "version": "<installed version>"}`. They say which tool and release wrote the document.
- `command`: `"nodes lint"`, `"doctor"`, or `"report diagnose"`.
- `status`: `"failed"` if any finding is an error, `"warning"` if any is a warning, otherwise `"passed"`. This is the diagnostic result; the exit code is decided per command as in the table above.
- `diagnostics`: findings sorted by `subject`, then `name`. Each has `code` (an integer from the error or warning catalog, or `null`), `severity` (`error`, `warning`, `info`), `name`, `message`, `remediation`, `subject`, and optionally `location`.
- `truncated`: `true` when a list was cut at the output cap (see [Limits](#limits)).
- `source` (`report diagnose` only, when the report could be read): the document diagnosed, `{"format": "rdetoolkit.run-report", "schema_version": "2"}`.

A finding with `code: null` has a documented `name` instead (for example `ModuleImportFailed`); no new error codes are allocated for these checks.

stdout carries exactly one UTF-8 JSON document. Output that imported project modules print goes to stderr.

## What is never printed

Messages are fixed text or catalog templates. Exception text, tracebacks, local variables, environment variables, argument previews (`repr`), invoice and input values, and config values are not copied into any field, because they can contain research data or credentials. A catalog template keeps its placeholders (`{reason}`, `{node_id}`): they are not filled from runtime values. There is no option that prints them; read the local files when you need them.

Identifiers are printed: node, flow, and call ids, module names, run ids, and paths relative to the project or report. They can still describe the project, so review the output before sharing it outside your organisation. None of the commands sends anything over the network.

## Limits

These rules bound what the JSON on stdout can contain:

- **Identifiers read from a file.** `report diagnose` prints a `node_id` or `call_id` from the report only if it is a string rdetoolkit could have written: a word character followed by word characters, `.`, `<`, `>`, `#` or `-`, at most 200 characters in all (`pkg.mod.func`, `mod.f.<locals>.g#3`). Any other value is printed as `null` and the field is listed in that failure's `redacted` array; the value itself is never echoed. A report whose `run_id` is not a plain file-name part is rejected (exit 3).
- **Paths.** Paths are relative POSIX paths: to `PROJECT_DIR` for `doctor`, and the fixed names `iterations/iteration_<index>.json` and `events_<run_id>.jsonl` next to the report for `report diagnose`. No command prints an absolute path or the name of an input file. `nodes lint` prints `module:qualname`, not file paths.
- **Input size.** `report diagnose` reads at most 16 MiB of the report (a larger one is rejected with exit 3) and skips an iteration detail or event log over 64 MiB with the flag `truncated`.
- **Output size.** `diagnostics`, `failures` and `evidence.iterations` keep at most their first 200 entries. `truncated` is then `true`; `status` and the exit code still count every finding.
- **What it covers.** Only the JSON document on stdout follows these rules. stderr (output of imported project modules, third-party warnings), `report show`, `report trace`, the run report and logs themselves, `job.failed`, and `repro export` archives carry raw text and paths.

Leaving free text out is how the envelope protects data: it does not try to recognise secrets in text. An identifier that is a credential (a node id chosen as a token, say) is printed like any other. Regular-expression or name-based masking, such as the [legacy traceback](structured_process/traceback.en.md) `SecretsSanitizer`, finds only what its patterns describe and is not anonymisation. Before you paste any of this output into an external agent, service or issue, read it and decide that it can leave your organisation; that decision is yours, and no rdetoolkit command makes it or sends anything for you.

## nodes lint

```shell
python3 -m rdetoolkit nodes lint --module modules.processing --json
```

Reports duplicate node ids (E2001), unstable node ids (E2005), duplicate reserved flow annotations (E2006), skeleton declaration errors (E2101–E2105), and skeleton slots that read instance state (W1101, severity `warning`). A parameter without a type annotation is `MissingTypeAnnotation`; a `--module` that cannot be imported is `ModuleImportFailed`. Both have `code: null`. `location.source` is the `module:qualname` of the function.

Lint imports the modules you pass, which runs their top-level code. It is not a sandbox and not a static analyzer; it never calls a node or flow body.

The text output and its exit codes are unchanged. In text mode a module that fails to import still prints the error on stderr and exits 3.

## doctor

```shell
python3 -m rdetoolkit doctor --format json
python3 -m rdetoolkit doctor container --format json --ref modules.processing:pipeline
```

`PROJECT_DIR` (default: the current directory) is resolved like `rdetoolkit run` resolves it: a nested `data/`, the `data/` directory itself, or an alias-flat layout. Doctor checks, in order:

1. `data/inputdata/`, `data/invoice/invoice.json` and `data/tasksupport/invoice.schema.json` exist (E4003 when missing, as the Runner reports it). A missing `tasksupport/metadata-def.json` is the warning `MetadataDefinitionMissing`: a run does not need it.
2. The effective config loads (`load_run_config`, E1002 on failure).
3. The JSON files parse; `metadata-def.json` and `invoice.schema.json` are valid definitions (E4002 / E4001). A schema with an external `$ref` is `ExternalSchemaReference`: doctor never downloads one.
4. `Runner.run(validate_only=True)` on a temporary copy of the config files and the `inputdata/`, `invoice/` and `tasksupport/` directories, with a stand-in flow. This resolves the mode and validates the invoice exactly as a run does. A configured mode that input files override is reported as W1001 (exit 0). The copy is deleted afterwards.
5. With `--ref pkg.mod:callable`: the module imports (`FlowImportFailed`), and the Runner can inject every parameter (E2003, E2006, or `FlowSignatureInvalid`). A flow with `prepare=` adds the warning `FlowPreparationSkipped`: doctor checked the files that exist now, and the mode after `prepare=` runs can differ.

Doctor never calls the flow or its `prepare=` hook, and writes nothing into the project: no `temp/`, logs, run report or `job.failed`, and the invoice is not rewritten. `--ref` imports the flow's module (its top-level code runs, with its output discarded and no `__pycache__` written). Copying the inputs costs time and disk space in proportion to `inputdata/`.

Besides the envelope, the JSON has `data_root` (relative to `PROJECT_DIR`), `mode` (`null` when the preflight did not run), `config` (`digest`, `on_iteration_error`, `repr_head`; no other values), and `checks` (`check_id`, `status`, `path` for every check, passed or not). Findings carry `check_id` and, when a file is involved, `location.path`.

## report diagnose

```shell
python3 -m rdetoolkit report diagnose data/logs/run_report_<run_id>.json --json
```

Failures come from the run report only. Each entry in `failures` has `iteration_index`, `node_id` and `call_id` (each `null` when not recorded, for example a failure before any node ran), `redacted` (the id fields replaced by `null` under [Limits](#limits), usually empty), `code`, `name`, `message`, `remediation`, and `source: "report"`. A v2 catalog code gets its catalog name and remediation; any other code, including a v1 `StructuredError` code, keeps its number under the name `ExecutionError`. These are observed calls from the call log, not inferred dependencies or a proven root cause.

`evidence` describes the files next to the report and never adds failures:

- `evidence.iterations[].iteration_detail`: `path` (`iterations/iteration_<index>.json`), `state`, `flags`. The detail files are reused by index on every run, so a detail is `verified` only when its `schema_version` is `"1"`, its `run_id` matches the report, and its `iteration_index` matches. Otherwise the state is `missing`, `corrupt`, `unverified` (a file written before details carried a version), `unsupported`, `mismatched` (another run's file), or `truncated`.
- `evidence.events`: `path` (`events_<run_id>.jsonl`), `flags`, `verified_records`. Records of another run or event version are not counted. A log without `run.completed` is `incomplete`; a W1002 record is `truncated`.

Every flag also appears as a warning finding named `SupportingEvidence<Flag>` (for example `SupportingEvidenceMismatched`). Keep the report next to its `iterations/` directory and event log when you move it. The [diagnosis schema](diagnostics-report.schema.json) describes the full document.

Since this release each `iterations/iteration_<index>.json` carries `schema_version: "1"` and `run_id` besides its existing fields. The run report (`schema_version: "2"`), event, and call-record formats are unchanged.

## See also

- [Command Line Interface](cli.en.md)
- [Error catalog](../rdetoolkit/error_catalog.md)
