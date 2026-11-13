---
name: rdetoolkit-debugging
description: Locate an actual failed rdetoolkit v2 iteration or node, inspect RunReport and local artifacts, repair a demonstrated failure, and rerun the same fixture.
---

Use this Skill for an observed execution failure. General flow authoring,
metadata design and test fixture construction belong to their own Skills.

1. Verify the installed version and reproduce using the same local inputs,
   configuration and mode. Keep a separate copy of inputs before running.
2. Execute `workflows.run(flow=...)` and inspect its `RunReport`: `status`,
   `exit_code`, `mode`, `iterations`, and `error`. Inspect failed iterations'
   `node_calls`, including `node_id`, `call_id`, `status` and errors. A failure
   during setup may have no iteration or node at all; do not invent one.
3. Read the matching `data/logs/run_report_<run_id>.json` and `job.failed`
   locally. `rdetoolkit report diagnose <report-path> --json` lists each
   recorded failure with its iteration, `node_id`, `call_id`, catalog code and
   remediation, and flags iteration details or event logs from another run;
   `rdetoolkit report show <report-path>` prints a short summary. Match the
   `run_id` to the run being investigated; do not use the newest filename as
   proof of provenance. Error descriptions come from the installed error
   catalog and API docs, not a second table in this Skill.
4. Fix the smallest demonstrated cause, rerun the same fixture, and compare
   the actual artifact and report. See the [failure/repair recipe](references/debugging.md).

A call log records observed execution, without value lineage. It is not a
pre-execution DAG. Event logs are supplementary diagnostics; they do not replace
the primary run results. `report diagnose` reports observed failures; it does
not establish a root cause or print error messages, so read those locally.

Keep invoice values, raw text, filenames, stack traces, environment values,
reports and reproduction archives local. Review and redact before explicitly
authorized external sharing; do not upload research data to an LLM by default.
Only the JSON on stdout of `report diagnose --json` (and of `doctor` and
`nodes lint`) leaves out messages and values; its ids, digests and stderr
still need the user's review before they leave the machine. Do not use the
legacy `<STACKTRACE>`/`TRACE_*` output as an agent format; its name-based
masking is not anonymization. A full `repro export` zip holds the raw inputs,
invoice and config: never attach or recommend sharing it without the user's
deliberate data review. `repro export --manifest-only` holds digests and
diagnostics only and cannot be replayed. Nothing here uploads automatically.
The [public error reference](https://github.com/nims-mdpf/rdetoolkit/blob/develop/v2/docs/rdetoolkit/error_catalog.md)
and installed CLI help remain authoritative.
