---
name: rdetoolkit-v1-migration
description: Migrate an existing rdetoolkit v1 callback or handler to a v2 eager flow through check, preview, explicit apply, artifact comparison and an accept-or-revert decision, keeping legacy compatibility when equivalence is unproven.
---

This is the migration-only Skill. Do not use its legacy source as a pattern for
new projects; use rdetoolkit-flow-authoring for new code. Everything here runs
locally: no external LLM service, API key or generated code index is needed.
A successful source rewrite is not a migration; only matching artifacts and
outcomes on representative inputs are.

## 1. Record the v1 baseline

Record the source revision, installed version, configuration, mode and input
checksums. Run the unchanged program on **copies** of real RDE inputs and keep
the whole `data/` tree and exit status: invoice, metadata, structured files,
images, raw copies and `job.failed`. Include an invalid input for every mode
the program supports and, for multiple tiles, a later-tile failure under each
error policy it uses. Keep data local.

Choose the target explicitly. **Compatibility on v2** keeps
`workflows.run(custom_dataset_function=...)` and the v1 path types; it stays
supported and is a valid stopping point. **Native v2** converts the callback to
a plain eager `@flow`, then adds `@node` boundaries and artifact nodes only as
the comparisons below keep passing. Never remove the compatibility API to
finish a migration.

## 2. Check, preview, then apply

Run `migrate check` and preview `migrate apply`; preview writes nothing. Write
only after the project owner opts in, to a new directory outside the source
(the CLI refuses existing or nested destinations and never edits the input).
The commands below use [legacy.py](references/legacy.py), copied byte-for-byte
from the repository's real `case01_init` migration corpus, not a guessed
signature. Copy it to `legacy.py` in an empty temporary directory first;
`migrated/` must not exist.

<!-- example: migration-commands -->
```console
python -m rdetoolkit migrate check legacy.py
python -m rdetoolkit migrate apply legacy.py -o migrated
python -m rdetoolkit migrate apply legacy.py -o migrated --no-dry-run
```

The fixture reads a UTF-8 `*.txt` input and writes `structured/structured.txt`;
CI runs it through the v1 entry and through the generated flow and compares the
bytes. Exit 0 means the converter ran, not that the result is correct. Read every
finding and every `TODO(rdetoolkit-migrate)` marker before running the output.
Stop for manual review when the callback is imported, selected dynamically
(`globals`, `getattr`, a dispatch table), bound to an instance, a lambda,
wrapped or aliased; when a handler receives a whole legacy bundle; when an
attribute has no mapped v2 home; or when the entry call carries extra logic.
Never let the converter or an agent rewrite user `StructuredError` codes,
messages, data contracts or nontrivial custom logic without a passing
comparison that proves equivalence.

## 3. Review the converted flow

The converter renames the callback to `pipeline(paths: InputPaths, out:
OutputContext)` and removes the old entry call. The Runner injects reserved
types (`InputPaths`, `OutputContext`, `InvoiceData`, `IterationInfo`,
`RdeConfig`) at the flow boundary only; nodes take explicit arguments. `if`,
loops and ordinary Python stay valid: there is no build phase, trace proxy or
pre-run DAG to restore. `resource_paths.rawfiles` becomes `paths.rawfiles`;
`srcpaths.config` and `resource_paths.smarttable_row_data` need a deliberate
redesign, not a rename. For a temporary class bridge, inspect the installed
`as_node` signature; do not force `Result` around every handler result.
The v1 entry stops at the first failing tile (unless
`multidata_tile.ignore_errors` is set); a v2 flow defaults to
`execution.on_iteration_error: continue`. Set `fail_fast` in `rdeconfig.yaml`
unless the owner chooses the new partial-run behavior.

The [artifact-node example](examples/native_flow.py) shows the next step for
the [legacy callback](examples/legacy_callback.py): `save_meta` keeps units and
variable rows, `save_text` writes the structured file, and `save_main_image`
copies image bytes. Keep filenames, serialization and directory kinds;
re-encoding an image or reformatting a CSV is a data-contract change.

## 4. Run and compare

Run the candidate on a **fresh copy** of the same data root with
`rdetoolkit.testing.run_flow(pipeline, data_root=...)`, or with
`rdetoolkit run`. The `run_flow(fixture_dir=...)` shortcut uses a synthetic invoice and
deletes its tree, so it cannot prove parity. Compare outcome semantics
explicitly: `RunReport.status` and `exit_code` (0 success, 1 failed, 2 partial),
each iteration's status and error code, name and message. Ignore `call_id`,
timestamps and run IDs. The v1 entry exits 1 on failure; a partial v2 run is not
an acceptable result unless the owner decides so.

Then compare the two preserved data roots, here the v1 tree in `v1/data` and
the candidate in `v2/data`. Run the scripts from the checkout or project root;
Skills installed for Claude live under `.claude/skills/` instead of `.agents/skills/`.

<!-- example: migration-compare -->
```console
python .agents/skills/rdetoolkit-v1-migration/scripts/compare_artifacts.py v1/data v2/data
```

It prints JSON and exits 0 for parity, 1 with the differing paths, 2 for
unusable evidence (missing `invoice/invoice.json`, a symlink, malformed or
non-finite JSON). `invoice/invoice.json` and `meta/metadata.json`, at the root
or under `divided/NNNN/`, are compared as JSON values, keeping scalar types
(`1`, `1.0` and `true` differ), units and variable-row order; formatting may
differ. Every other file is compared byte for byte, including structured
files, images, raw copies and `job.failed`, and empty directories count. The
only exclusion is the contents of the Runner's `logs/` and `divided/NNNN/logs/`;
the directories themselves are still compared. Never widen the exclusion or
regenerate the baseline to make a comparison pass.

The worked example runs this whole procedure on the shipped
[legacy callback](examples/legacy_callback.py): it converts it with the
commands above, runs the original through the v1 entry and both the converted
and the artifact-node flow through `run_flow`, on a valid and a failing input,
and compares artifacts and outcomes. The work directory must not exist.

<!-- example: migration-exercise -->
```console
python .agents/skills/rdetoolkit-v1-migration/scripts/exercise_migration.py --work-dir migration-exercise
```

In a source checkout, the toolkit's own five-mode gate replays the frozen v1
contract corpus against the v2 Runner (see
[mode parity](references/mode-parity.md) for the cases and per-mode review
points). It fails unless all 24 selected cases pass; a skip or xfail is a
failure. It proves the toolkit, not an arbitrary user program.

<!-- example: migration-mode-parity -->
```console
python .agents/skills/rdetoolkit-v1-migration/scripts/check_mode_parity.py
```

## 5. Accept or revert

Keep a local record: versions, checksums, source and output paths, the write
opt-in, findings and their resolution, commands and statuses, reports, and
every artifact difference with its reviewed reason. Accept only when every
representative input and mode policy compares equal, or each difference has an
independently reviewed expected output. Otherwise keep running the unchanged
v1 source (or the compatibility checkpoint) and preserve the failing candidate
for diagnosis; reverting means selecting the baseline, never deleting files.

Use the [public migration guide](https://github.com/nims-mdpf/rdetoolkit/blob/develop/v2/docs/migration_v1_to_v2.en.md)
for compatibility decisions, including missing metadata values and image bounds.
