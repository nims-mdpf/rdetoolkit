---
name: rdetoolkit-v1-migration
description: Migrate an existing rdetoolkit v1 callback or handler to a v2 eager flow while preserving mode-specific artifacts and explicitly reviewing intentional compatibility differences.
---

This is the migration-only Skill. Do not use its legacy source as a pattern for
new projects; use rdetoolkit-flow-authoring for new code. This Skill provides the
workflow shell; complex mode-specific migration requires the public migration
guide and project-specific parity fixtures.

1. Verify the installed version, select a complete local v1 input fixture and
   preserve an untouched copy. Record configuration, mode, status, `job.failed`,
   invoice, metadata, structured files and image outputs from the v1 run.
2. Run `migrate check` and preview `migrate apply`. Review all findings manually;
   conversion is structural and cannot prove scientific parity. The commands
   below use [legacy.py](references/legacy.py), copied byte-for-byte from the
   repository's real `case01_init` migration corpus, not a guessed signature.
3. Write conversion into a new external directory. Review the generated eager
   `@flow`, imports, `InputPaths`/`OutputContext`, and explicit node arguments.
   Existing `custom_dataset_function` and v1 path types belong only to frozen
   compatibility. For a temporary class bridge, inspect the installed `as_node`
   signature; do not force `Result` around every handler result.
4. Run v1 and v2 on separate copies of the same local inputs. Compare actual
   mode-specific artifact trees, JSON values/units/variable rows, image size and
   errors. Keep every intentional difference explicit, with an independent
   expected output. Fix and rerun before switching a production entrypoint.

Copy `references/legacy.py` to `legacy.py` in an empty temporary directory before
executing this example. `migrated/` must not exist; preview writes no output.

<!-- example: migration-commands -->
```console
python -m rdetoolkit migrate check legacy.py
python -m rdetoolkit migrate apply legacy.py -o migrated
python -m rdetoolkit migrate apply legacy.py -o migrated --no-dry-run
```

The fixture reads a UTF-8 `*.txt` input and writes `structured/structured.txt`.
CI executes its actual legacy callback, runs these exact conversion commands,
executes the generated flow through the Runner, and compares artifact bytes.
This single invoice-mode example does not certify parity for the other modes.

Use the [public migration guide](https://github.com/nims-mdpf/rdetoolkit/blob/develop/v2/docs/migration_v1_to_v2.en.md)
for compatibility decisions, including missing metadata values and image bounds.
V2 is eager execution plus observed call records: do not restore a pre-run DAG
or node value lineage during conversion. Keep fixtures and reports local.
