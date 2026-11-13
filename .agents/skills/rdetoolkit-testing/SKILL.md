---
name: rdetoolkit-testing
description: Build isolated deterministic rdetoolkit v2 fixtures and regression tests, execute public flows through the real Runner, and compare functional artifacts and failure behavior.
---

Use this Skill when constructing tests or proving a repair. Use debugging to
locate the cause of a currently observed failure and migration for v1 parity.

1. Verify the installed version and discover existing flows and processing
   skeletons.
2. Use public `rdetoolkit.testing` builders for input paths, invoice data and
   output contexts. `make_input_paths` creates directories and requested empty
   raw files; it does not write a valid invoice/schema for you.
3. Run `run_flow(flow, data_root=project)` on a complete temporary RDE tree to
   keep its outputs for assertions. `fixture_dir=` creates a synthetic temporary
   tree, deleted after the run; use it when inspecting only the report is enough.
4. Assert file contents, metadata units/repeated rows, invoice changes, image
   signatures where applicable, `report.status`, `exit_code`, and `job.failed`.
   Also exercise invalid inputs, repair, and rerun; successful imports are not
   sufficient. Keep fixtures synthetic and independent of internet/LLM access.

<!-- example: testing-discovery -->
```console
python -m rdetoolkit flows list --json
python -m rdetoolkit skeletons list --json
```

Lint the registered declarations as part of the regression suite. Pass
`--module` for project modules (importing them runs their code). With no
findings it prints `"status": "passed"` and exits 0; any finding exits 3.

<!-- example: testing-lint -->
```console
python -m rdetoolkit nodes lint --json
```

The [complete executed fixture](references/testing.md) creates local input and
runs the real Runner. Use different fixture roots for distinct processing modes
and success/failure cases; do not assume an invoice fixture covers SmartTable,
ExcelInvoice, multidatatile or rdeformat semantics. Compare the actual per-mode
output tree and contract. Do not construct `OutputContext` directly: use its
factory or `make_output_context` for direct node tests.

See the [public testing guide](https://github.com/nims-mdpf/rdetoolkit/blob/develop/v2/docs/tutorial_v2.md)
and installed `.pyi` declarations when selecting assertion helpers.
