---
name: rdetoolkit-metadata
description: Implement or repair rdetoolkit v2 metadata definitions, typed constants, units, repeated variable rows, and invoice fields without changing general flow orchestration.
---

Use this Skill when the question concerns metadata or invoice contracts. Use
flow-authoring for orchestration, debugging for locating failures, and testing
for building fixtures.

1. Verify the installed version and discover the metadata node signatures.
2. Read the project's `metadata-def.json` and invoice schema. Use
   `build_meta(values, metadef_path, repeated=...)` and `save_meta(metadata, out)`
   for definition-driven conversion; definitions may also be a Mapping.
3. Read custom invoice values with `InvoiceData.get_custom_fields()`. Use public
   invoice nodes for schema-based custom field mapping. `metadata.basic` is not
   serialized into `metadata.json`; invoice output has a separate contract.
4. Execute the local fixture; inspect constants, units, sparse variable rows and
   invoice files. Fix the definition or measured values and rerun.

<!-- example: metadata-discovery -->
```console
python -m rdetoolkit nodes show rdetoolkit.nodes.meta.build_meta --json
python -m rdetoolkit nodes show rdetoolkit.nodes.meta.save_meta --json
```

The [executed recipe](references/metadata.md) saves constants, repeated values,
and a plot. Undefined keys and missing/`None` values are omitted. Do not infer
units or fill sparse repeated cells with invented measurements. Test actual
mode-specific output paths, especially divided tiles and invoice changes.

Use normal return values; `Result` is optional when a helper's contract needs it.
Use `rdetoolkit.nodes` and installed type stubs as the authority, with the
[public metadata guide](https://github.com/nims-mdpf/rdetoolkit/blob/develop/v2/docs/usage/metadata_definition_file.en.md).
Keep scientific data local unless the user explicitly authorizes sharing it.
