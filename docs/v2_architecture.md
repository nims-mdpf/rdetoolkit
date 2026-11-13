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
