---
name: rdetoolkit-flow-authoring
description: Write or extend a new rdetoolkit v2 structured-processing flow, choose existing nodes or processing skeletons, and run it against local project inputs.
---

Use this Skill for new processing logic. For metadata schemas, failures, fixtures,
or existing v1 code, select the corresponding rdetoolkit Skill instead.

1. Verify the installed rdetoolkit version matches this Skills pack. Discover
   nodes, flows and processing skeletons before inventing APIs. Load project
   declarations with `--module package.module` where needed; use
   `show <id> --json` for the signature of an id returned by `list`.
2. Implement a plain eager Python `@flow`, with reusable `@node` functions.
   Import reserved types from `rdetoolkit.types`. Injection occurs only at the
   flow boundary; pass node arguments explicitly. Helpers can return ordinary
   values; do not wrap every helper in `Result`.
3. Before the first run, `rdetoolkit doctor --format json --ref processing:pipeline`
   checks inputs, config, mode and the flow's injectable parameters without
   calling the flow. Then execute using `workflows.run(flow=pipeline)` from a
   complete local RDE project (or `rdetoolkit run processing:pipeline` after
   saving the example as `processing.py`). For production entry scripts use
   `exit_on_failure=True`.
4. Inspect the returned `RunReport`, actual files and invoice; fix the smallest
   demonstrated failure and rerun with the same local fixture.

Execution is eager: branches, loops, literals, defaults and f-strings retain
Python semantics. The recorded call sequence describes observed calls after
execution. Never construct a pre-run DAG or infer node value lineage.
The Runner owns configuration, mode resolution, validation, tile iteration,
output directories, `job.failed` and the report. It does not inject into nodes.

<!-- example: authoring-discovery -->
```console
python -m rdetoolkit nodes list --json
python -m rdetoolkit flows list --json
python -m rdetoolkit skeletons list --json
```

Use the [executable flow recipe](references/flow.md) for fixture assumptions and
public artifact functions. Consult the installed `.pyi` declarations and the
[public v2 tutorial](https://github.com/nims-mdpf/rdetoolkit/blob/develop/v2/docs/tutorial_v2.md)
for authoritative signatures. Do not download instructions during a normal run.
