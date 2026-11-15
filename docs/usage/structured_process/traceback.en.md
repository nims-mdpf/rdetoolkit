# Diagnostics and legacy traceback compatibility

For v2 troubleshooting, with or without a coding agent, start with
`rdetoolkit report diagnose data/logs/run_report_<run_id>.json --json`. This is
the one preferred diagnostic entry. Its versioned envelope reports the failed
iteration, node and call ids, catalog codes and remediation without copying
exception text, source lines, locals, environment values or input paths. See
[Diagnostic commands](../diagnostics.en.md) for the format and its limits.

RunReport files, events, call logs, `report show`, stderr and `job.failed` remain
local debugging artifacts and may contain confidential text. The safe view is a
new serialization boundary; it does not rewrite those compatibility outputs.
No rdetoolkit command sends diagnostics to an LLM, telemetry endpoint or issue tracker.
Review any output before sharing it externally.

## Compatibility inventory and decisions

The following v1 interfaces remain available in v2. No public symbols are
removed, moved into a new namespace or given runtime deprecation warnings.
Only the recommendation to use `<STACKTRACE>` as the primary agent format is
retired. Catalog remediation remains defined once, in `ERROR_CATALOG`.

| Interface / entry point | Decision | Retained behavior |
|---|---|---|
| `rdetoolkit.errors.handle_exception` | Keep, frozen v1 compatibility | Returns `StructuredError`; respects explicit `Config.traceback`, then environment, then the traditional Python-style fallback |
| `errors.handle_generic_error`, `handle_and_exit_on_structured_error`, `format_simplified_traceback` | Keep, frozen v1 compatibility | Existing stderr, wrapping and exit behavior; output may contain raw messages, paths and source |
| `rdetoolkit.traceback.formatter.CompactTraceFormatter` and `errors.CompactTraceFormatter` proxy | Keep, frozen v1 compatibility | `<STACKTRACE>` with `CFG v=1`, `E`, optional `T`, `F` and `RC` lines; no v2 remediation implementation |
| `rdetoolkit.traceback.masking.SecretsSanitizer` | Keep, frozen v1 compatibility | Name-based masking, custom patterns and representation/truncation behavior |
| `rdetoolkit.models.config.TracebackSettings`, `Config.traceback` | Keep, frozen v1 compatibility | `compact`, `python`, `duplex` formats and existing fields/defaults |
| `config.get_traceback_settings_from_env`, `errors.get_traceback_settings_from_env` | Keep, frozen v1 compatibility | Existing `TRACE_VERBOSE` / `TRACE_FORMAT` controls |
| `errors.pyi`, `traceback/{formatter,masking}.pyi`, `models/config.pyi`, `config/__init__.pyi` | Keep | Existing import names and signatures remain available |
| v1 callback `workflows.run(custom_dataset_function=...)` | Keep | Existing traceback configuration/priority; no new warnings |
| `<STACKTRACE>` as the recommended v2 agent interchange format, automatic LLM/bug-report examples | Retire guidance | Use `report diagnose --json`; review before intentional external disclosure |
| Public traceback APIs | Remove: none | Removal would need a separate compatibility decision and migration plan |

Imports of the formatter, sanitizer and configuration remain in the existing
modules. Only the v1 callback entry (`workflows.run(custom_dataset_function=...)`)
prints this traceback; the v2 flow entry does not. A project-root v2 `rdeconfig.yaml` rejects `traceback:`; existing
v1 configuration files retain it. See the [migration matrix](../../migration_v1_to_v2.en.md).

## Local debugging controls

Compact formatting is disabled by default. `TracebackSettings()` defaults to
`enabled=False`, `format="duplex"`, and `include_context=False`,
`include_locals=False`, `include_env=False`, with `max_locals_size=512` UTF-8 bytes
per represented local. Explicit configuration takes precedence over environment.

| Control | Meaning |
|---|---|
| `TRACE_VERBOSE` unset or empty | No environment settings; traditional traceback fallback remains |
| `TRACE_VERBOSE=off`, `false`, `disable`, `disabled` (case-insensitive) | Disable compact formatting; does **not** silence or anonymize Python traceback |
| `TRACE_VERBOSE=context,locals,env` | Opt into source, local values and runtime platform information respectively |
| `TRACE_FORMAT=compact`, `python`, `duplex` | Select output; default is `duplex` when enabled |

`include_env` adds Python and OS information, rather than an environment-variable
dump. Source and locals are separate opt-ins. Keeping both off does not remove
sensitive exception messages or filenames. Full Python verbose traceback retains
Python exception chaining (`__cause__`, `__context__`, `raise ... from None`).
The simplified call path and compact `RC` line are legacy summaries, not complete
root-cause analysis: `RC` uses a frame heuristic and the current exception text;
the simplified call path can still include context frames when Python suppresses
the displayed full chain. Inspect the local Python exception chain when needed.

## Disclosure limits

`SecretsSanitizer` matches variable **names** before representing their values.
It is not recursive anonymization: a nested credential under a neutral name can
remain visible. Raw exception messages, source lines, filenames and arbitrary
`repr` output are not made safe by these patterns. Custom regular expressions
and size caps reduce some exposure; they cannot prove that research data,
credentials or identifying details have been removed. Legacy per-value limits
also do not impose a total-output cap.

Keep detailed traceback and full reproduction ZIPs local unless you deliberately
review their contents. Prefer `report diagnose --json` and, when structural
file metadata is needed, `repro export --manifest-only`. Digests and size metadata
can still identify known files; a metadata-only bundle is not anonymous and is
not replayable. Never automatically attach either bundle to external services.

## Related documentation

- [Diagnostic commands](../diagnostics.en.md)
- [repro: Export and Re-run a Finished Run](../cli.en.md)
- [Configuration](../config/config.en.md)
- [Error handling](errorhandling.en.md)
