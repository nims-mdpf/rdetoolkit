# v2 architecture reference for contributors

This checked-in summary is the accessible architecture reference for a clean
checkout. It records the implemented v2 model; private design and phase notes
are optional historical context, never prerequisites for contributing. Public
API details come from installed CLI introspection, type stubs and the
[executed tutorial](tutorial_v2.md).

## 1. Execution and responsibility boundaries

`@flow` executes eager, ordinary Python. Branches, loops, literal/default
arguments and helper calls retain Python semantics. `@node` registers a
specification and records an observed call during an active run; direct calls
remain ordinary function calls. There is no trace proxy or build/compile phase.
Do not restore a pre-execution DAG (ADR-020).

The Runner owns config loading, mode resolution, input validation, output
directories, tile iteration, flow invocation, output validation and finalization.
Modes are invoice, excelinvoice, rdeformat, multidatatile and smarttable.
Nodes receive explicit arguments. Reserved types are injected only at the flow
boundary, based on annotations from `rdetoolkit.types`.

## 2. Observation and reporting

The call log describes observed call sequence, with per-call identities and
run-global ordering. It does not track value lineage or infer dataflow edges
(ADR-022). Graph output renders that observed call sequence after execution.
RunReport aggregates primary execution results; it is not reconstructed from
an event sink. Events and reports carry explicit schema versions.

## 3. Public authoring surface

Use `flow`, `node`, `workflows.run(flow=...)`, reserved types and artifact nodes
from `rdetoolkit.nodes`. Prefer `build_meta` / `save_meta` for metadata when
appropriate. `Result` is an available compatibility tool, not a wrapper required
around every Python helper. The `nodes`, `flows` and `skeletons` list/show CLI
commands (each with `--json`) and installed type stubs expose the actual
version's API.

## 4. Compatibility and artifacts

The warning-free v1 callback entry point and its input/output contracts remain
supported. Frozen fixtures protect invoice, metadata, output tree, `job.failed`
and exit behavior. The v1 public contract takes precedence over implementation
reorganization (ADR-023). Pre-GA removals that are not part of that contract,
such as the package-embedded agent guide, are listed in the
[migration guide](migration_v1_to_v2.en.md). No new processing code should
default to the legacy callback API.

## 5. Language and state boundaries

Python owns v2 decorators, registries, injection, Runner, reporting, plugins and
CLI. Rust remains responsible for existing image, encoding and filesystem
operations; `dag.rs` stays frozen and unregistered. Do not import `RustDAG` or
the private extension from v2 modules. Run state must be isolated between runs.
Use catalogued integer errors; preserve existing append-only type/error APIs.

## 6. Verification and distribution

Use public test builders with isolated temporary inputs and real Runner
execution. Test outputs, failure artifacts and mode semantics, not just imports.
`tests/v2/golden/` protects compatibility; contributor gates are in
[AGENTS.md](https://github.com/nims-mdpf/rdetoolkit/blob/develop/v2/AGENTS.md). Deterministic tests require no live LLM or private data.
Canonical downstream Skills live in `.agents/skills/`, ship as a separate
version-matched release asset, and never belong to wheel/sdist package data.

## 7. Registration mode intent and read-only explanation

V2 flows preserve explicit registration intent. The canonical mode names are
`invoice`, `multidatatile`, `smarttable`, `excelinvoice`, and `rdeformat`.
The exact aliases `Invoice`, `MultiDataTile`, `SmartTableInvoice`,
`ExcelInvoice`, and `RDEFormat` normalize to those names at the flow boundary. Unknown names and
other case variants fail configuration validation with the valid vocabulary.
An omitted or null `system.extended_mode` enables automatic selection. An
explicit `invoice` requests Invoice grouping even when its effective setting
matches the default. Normalization, config digests, and reproduction archives
retain this distinction.

Configuration loading and reproduction preserve the exact `RDEFormat`
spelling until the execution target is known. The callback contract interprets
it as Invoice, whereas `rdeformat` selects RDEFormat; their config digests must
differ. Aliases whose meanings agree under both contracts can normalize during
loading. A v2 flow converts `RDEFormat` to `rdeformat` before mode selection.

A single special input can select SmartTable or ExcelInvoice automatically.
Multiple ordinary files remain one Invoice tile unless MultiDataTile is
requested. V2 rejects conflicting explicit settings and mixed or duplicate
special inputs before registration. A `ModeDecision` retains the requested
mode, chosen mode, candidates, filename evidence, and stable reason codes.
Evidence contains filenames and format indicators, never cell contents.

The callback compatibility target preserves the historical
SmartTable, ExcelInvoice, configured-mode priority and W1001 warning.
The execution target selects this policy, independently of the config's file
format. This intentional separation prevents a v2 flow from silently changing
a user's requested registration boundaries while retaining v1 behavior.

`rdetoolkit run --validate-only --explain` inspects the current input snapshot.
It does not invoke preparation or flow functions, create output directories,
or publish events, reports, or registration artifacts. JSON explanation uses
a versioned schema and includes mode reasons, tile membership, ordering,
output paths, stage plans, config source, and applicable diagnostics.
Preparation can change inputs, so a later run describes the prepared snapshot.
`--validate-only` alone retains its existing preparation and report behavior.

Mode handlers own artifact stage order. Invoice and SmartTable run thumbnail,
structured, magic, and description. MultiDataTile and ExcelInvoice run magic,
thumbnail, structured, and description. RDEFormat runs thumbnail and description.
Planning validates stage identifiers and duplicates before invoking the flow.
Unavailable runtime Magic or Graph previews must be reported explicitly;
configuration inspection does not validate data that a flow has not produced.

V2 RDEFormat preview and execution group tiles by numeric directory and retain
archive-member order within each group. The callback route retains its legacy
filesystem ordering. MultiDataTile `filesystem` ordering explicitly reports
that its order is not reproducible; name ordering remains deterministic.

ExcelInvoice folder grouping retains the legacy parent-before-child traversal
before applying workbook order. When a parent and its nested folder both have
files, each keeps the invoice from its corresponding workbook row.
Workbook identifiers only sort folder groups. The sorted groups are then
assigned to rows by position, so unmatched and duplicate identifiers fall back
to folder order. The migration guide gives the full rule (#760).

RDEFormat report `datatile_id` and `target` keep their first-input derivation.
V2 now takes that first input from archive order, so their values can differ
from the callback's filesystem-first values. Tile indices and artifact output
paths retain their existing contracts. Invalid v2 special layouts can now fail
with a planning error before extraction or missing-invoice validation; the
callback keeps its historical error priority and partial artifacts.
