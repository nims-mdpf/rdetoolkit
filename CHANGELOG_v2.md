# rdetoolkit v2 changelog

## Unreleased — Session I-REVIEW-B (PR #539 review response: contracts & tests)

Test-and-contract response to review findings F4, F5 and F7. No
`src/rdetoolkit` file changes in this session; the behavior described below
already existed and is now protected by tests that can fail.

### Added

- **Artifact content is part of parity.** The contract observation gained an
  `artifact_sha256` key covering every run-produced non-raw file —
  `meta/`, `structured/`, `thumbnail/`, `main_image/`, `other_image/`,
  `attachment/`, `temp/` and `job.failed` — and it is the fourth
  `observe.PARITY_KEYS` entry. Writing `b"broken"` into a correctly named
  `data/thumbnail/1.jpg` passed "full artifact parity" before; it is now
  detected by **every comparison against a live v1 oracle** (the mode
  compatibility, RDEFormat invoice-stage, SmartTable `save_table_file` and all
  six multi-tile policy cells). The cells that compare against the **frozen**
  corpus start enforcing it when the snapshots are re-frozen — see the
  maintainers' note below.
- **`TC-UM-*-CB-V2-{OK,USERERR,VALERR}` (15 cells).** The v1 dataset callback is
  executed through `Runner.run(RunRequest(target=LegacyCallbackTarget(...)))` —
  i.e. the unified Runner driving `LegacyCallbackInvoker` — and compared with
  the same frozen v1 observation as the existing `CB` cells, which stay as pins
  of the oracle. Plus a dynamic SmartTable row-material comparison against a
  live v1 run, a unified-signature cell, and a cell proving that the v1 `Config`
  object (not a mapping of the same switches) is what seeds the fail-fast
  policy.
- **Six multi-tile error-policy cells** replace the `pytest.fail()` seats.
  Each runs a three-tile family whose tile 1 raises `StructuredError(999)`.
  The `FAIL-FAST` cells and the MultiDataTile `CONTINUE-PARTIAL` cell are
  compared against a live v1 oracle on tree, raw, artifact content, invoices
  and `job.failed`; ExcelInvoice and SmartTable `CONTINUE-PARTIAL` are stated as
  a v2-only contract because v1 honors `ignore_errors` in MultiDataTile alone.
  Reserved xfail seats drop from 12 to 6 (SIGTERM 1 + callback observability 5).

### Changed

- Thumbnail and main-image **bytes** are now compared. The former exclusion
  assumed an image-library re-encode; both v1 `ThumbnailGenerator` and v2
  `ImageArtifactService` call `img2thumb.copy_images_to_thumbnail`, which is a
  `shutil.copy`, so the digests are environment-independent.
- Contract snapshot regeneration covers every mode again. Session H4 had
  narrowed write mode to the SmartTable subset for a PII re-freeze; the
  PII guarantee is enforced by the owner-value scan, not by that filter.
- `tests/v2/modes/canary_support.py` replaces the per-mode canary harness
  boilerplate (Session I-REVIEW-A debt 1).

### Fixed

- **Observation classification no longer depends on where a run lives.** Both
  digest walkers tested the absolute path for `raw`/`logs`/`inputdata`
  components, so a project checked out below a directory with one of those
  names was observed incorrectly — and silently, because v1 and v2 agreed on
  the same wrong answer. Classification now looks only below the data root.
  This is the ancestor-sensitivity class reported as R1 for RDEFormat.
  The 21 frozen `raw_sha256` observations are unchanged by the fix.

### Note for maintainers

The 21 snapshots under `tests/v2/contract/fixtures/expected/**` were re-frozen
on a clean tree in a separate commit (two-commit ritual, see
`merge_v1/contracts.md` §I-REVIEW-B); the only delta was the added
`artifact_sha256` key plus the provenance stamp. `observe.PENDING_FREEZE_KEYS`
is empty again, so every frozen cell -- not only the live-oracle cells --
now compares artifact contents. Keep the tuple empty unless a future session
adds another observation key; list the key there only between the generator
change and its re-freeze.

## Unreleased — Session I-REVIEW-A (PR #539 review response)

Core response to the two independent PR #539 reviews. Every item below is
backed by a regression test that reproduces the reviewers' counterexample.

### Fixed

- **One data root per run.** `Runner.run` resolves the data root once, before
  anything is created, and every consumer (config discovery, tile iteration,
  invoice service, callback adapter, validation, aggregator, finalizer) uses
  that answer. An alias-flat root no longer splits a single run between
  `<root>/invoice` and `<root>/data/raw`.
- **SmartTable callback material is run-private.** The process-global row-data
  dictionary is removed; the row a v1 callback receives now travels by value
  from tile preparation to the invoker, so a second Runner on the same root
  cannot erase it.
- **A stale `data/temp/invoice_org.json` is ignored.** The run-level
  `invoice_org` is decided once, by v1's own mode rule, instead of by the
  presence of a backup file; the structured export, `${invoice:...}` resolution
  and the callback's `invoice_org` all follow that decision.
- **Configuration shipped in `data/tasksupport` is honored.** v2 discovery now
  falls back to `data/tasksupport/{rdeconfig.yaml,rdeconfig.yml,pyproject.toml}`,
  read through the v1 loader. A configuration discovered there also adopts v1's
  `fail_fast` error policy unless it sets `multidata_tile.ignore_errors`. All
  five real-canary families now reach full artifact parity through production
  discovery with no configuration overrides.
- **Mode-specific artifact order is preserved.** MultiDataTile and ExcelInvoice
  expand magic variables before the thumbnail and structured stages, as their v1
  pipelines do, so a tile whose magic expansion fails no longer leaves a
  `structured/invoice.json` v1 never wrote.
- **SmartTable EarlyExit validates before completing.** A pre-completed tile is
  validated before it is recorded, so a broken tile invoice or metadata aborts a
  fail-fast run without executing any user flow, exactly as v1 does.
- **RDEFormat classifies inputs relative to the data root.** A project stored
  below a directory named `raw`, `meta` or `structured` no longer misplaces its
  structured and metadata artifacts.
- **The public entry points follow the resolved data root.**
  `workflows.run(flow=...)` and `rdetoolkit run --validate-only` derived it from
  a hardcoded `<root>/data`. On an alias-flat project the flow entry therefore
  processed zero input files and still reported success, and `--validate-only`
  resolved the mode against a directory that does not exist. The v1
  `custom_dataset_function` path is unchanged.

### Changed

- `ModeHandler` is now the minimum protocol (`kind`, `create_tiles`). The two
  artifact capabilities are separate, runtime-checkable protocols,
  `RawCopyStrategyProvider` and `ArtifactStageProvider`, exported from
  `rdetoolkit.modes`. A handler implementing only the minimum is accepted by
  both the runtime and a type checker.
- `ModeHandler.invoice_stage_steps` (a `frozenset`) is replaced by
  `artifact_stage_order`, which returns an ordered tuple.
- `InvoiceService.apply_config(steps=...)` is replaced by
  `InvoiceService.apply_step(step, ...)`; the caller owns the order.
- `RawCopyStrategy.copy` takes a `data_root` argument.
- `runner.finalize.finalize` and `RunFinalizer` take `data_root` instead of
  `root`; `runner.iterator.iterate_tiles` takes `data_root` as its fourth
  argument and derives the tile invoice/tasksupport inputs from it.

## 2.0.0a1 — 2026-07-14

This alpha is the Phase F feature baseline. It keeps the current dual-entry
runtime as a canary and rollback point while unified-runner work continues;
the public v2 result model is `RunReport`.

The release is identified by the git tag `v2.0.0a1`, while the in-code version
remains `2.0.0` for now because the v1 ExcelInvoice template embeds a version
whose format contract accepts only stable `X.Y.Z`. Relaxing that contract will
ship in an independent PR to `main` before the first release candidate.

### Added

- Eager `@node` and `@flow` execution with runtime call-log recording and
  post-run call-sequence reports.
- RDE Runner lifecycle, five registration modes, validation, iteration error
  policies, Events, `RunReport`, `job.failed`, report/graph/repro commands, and
  testing fixtures.
- Fifteen canonical builtin nodes for input, structured output, metadata,
  images, and plots.
- `ProcessingTemplate`, required slots, template discovery, `templates`
  commands, and `init --processing-template` skeleton generation.
- Declarative plugin discovery for node sets, format handlers, and processing
  templates; `formats list` and `nodes list --plugin`.
- Dry-run-first `migrate check` / `migrate apply` and the level-3
  `rdetoolkit.testing.run_flow` helper.
- Generated error-catalog documentation, an executed progressive tutorial,
  and a provisional v1-to-v2 migration guide.

### Compatibility notes

- v2 flow executions return `RunReport`.
- `on_iteration_error` defaults to `continue`; select `fail_fast` explicitly
  when immediate termination is required.
- Runtime unification and final compatibility commitments are scheduled after
  this alpha and before the release candidate.

### Changed — migration protocol alignment

The unreleased pre-v2.1 protocol surface was replaced by the migration-only
contracts in Design Appendix M:

- Removed `DataValidator`, `NodeRunner`, and `FormatHandler`.
- Changed `FileReader.read` from `read(path: str) -> bytes` to the canonical
  `InputPaths -> tuple[Metadata, DataFrame]` contract.
- Changed `MetadataExtractor.extract` from a bytes/dict placeholder to the
  canonical `(DataFrame, InvoiceData) -> Metadata` contract.
- Added `DataProcessor`, `ResultWriter`, and `Visualizer`.

These protocols are migration aids only. New code should use processing
templates (Design §5.2) or plain node/flow functions (Design §3).

### Added — plugin discovery and migration application

- Added declarative discovery for plugin-provided nodes, format handlers, and
  processing templates, with provenance-aware inspection commands and
  warn-and-skip handling for broken third-party entry points.
- Added `formats list`, `nodes list --plugin`, and automatic plugin discovery
  for `templates list`; Runner lifecycle extension points remain intentionally
  unavailable (Design §5.3).
- Completed the level-3 `testing.run_flow` contract for function and template
  targets, including recursive fixture trees (Design §13).
- Added dry-run-first `migrate apply`, external-only output, explicit TODO
  markers for unresolved constructs, and a five-template corpus demonstrating
  the ADR-021 80% executable-conversion condition.

### Fixed — Phase F review remediation

- Made rich-rendered `init --help` assertions robust to ANSI styling and line
  wrapping in color-enabled CI environments.
- Prevented `init --processing-template` from overwriting generated files
  unless the user explicitly supplies `--force`.
- Restricted template execution to registered depth-2 concrete classes and
  registered inherited default hooks under each concrete class's node id.
- Derived plugin node/template provenance from loaded provider objects so
  discovery remains correct after pre-import.
- Read `migrate apply` inputs with their PEP 263 declared encoding and report
  malformed files without aborting sibling conversions.

### Added — Phase G unified-runner contracts

- Added the seven v1 artifact-behavior settings to strict `RdeConfig` with
  v1-identical defaults, including a dedicated `smarttable` section.
- Added immutable `FlowTarget`, `LegacyCallbackTarget`, and `RunRequest`
  boundary types plus entry-point normalization using catalog error 1001.
- Fixed the Phase H contracts for legacy config normalization and explicit
  `RunReport.to_legacy_statuses()` conversion against frozen v1 fixtures.

### Fixed — Phase G contract review remediation

- Made flat-layout ExcelInvoice backup root-relative and independent of the
  process working directory, with the same parsed JSON content as its source.
- Recreated Git-unrepresentable empty staging directories during oracle-case
  materialization and covered fresh-checkout behavior with a regression test.
- Strengthened all 16 frozen v1 observations with parsed invoice-backup content
  and complete normalized `job.failed` text.
- Normalized the order-dependent RDEFormat status-target subdirectory while
  retaining each deterministic `data/temp/NNNN` tile prefix.

### Changed — Phase H Runner lifecycle completion

- Completed source invoice pre-validation and the completed-tile output sweep
  by delegating to the existing `invoice_validate` and `metadata_validate`
  domain functions. Missing metadata remains an optional, v1-compatible skip.
- Defined output-validation failures as run-level failures: an invalid
  completed invoice now produces catalog code 4001 and `job.failed`; artifacts
  left by failed iterations are excluded from the sweep.
- Split execution planning, tile execution, flow invocation, and finalization
  into `RunPlanner`, `TileExecutor`, `FlowInvoker`, and `RunFinalizer` while
  preserving the six public `Runner` lifecycle step methods.
- Recorded the executing `git describe --always --dirty` revision in generated
  snapshots and added non-failing provenance warnings plus deterministic input
  drift checks; XLSX drift is compared semantically because workbook metadata
  bytes are nondeterministic.

### Changed — Phase H cleanup

- Removed the unused `RunAggregator.record_failure()` method; Runner failure
  paths already record canonical failed `ExecutionResult` instances.

### Added — Phase H request and configuration normalization

- Relocated the unchanged v1 `rdetoolkit.config` module into a compatible
  package and added strict v1/v2 `ConfigNormalizer` conversion.
- Added the total `RunReport.to_legacy_statuses()` compatibility conversion,
  including a defined status representation for failed runs where v1 exited
  without returning a value.
- Routed v2 flow execution through `RunRequest`, moved ProcessingTemplate
  conversion to request normalization, and kept the v1 callback branch intact.

### Added — Phase H common domain services and concurrent Runner support

- Added path-based `InvoiceService`, `RawArtifactService`,
  `ImageArtifactService`, `OutputLayoutResolver`, `InputValidator`, and
  deterministic `IterationFactory` services, consuming all seven canonical v1
  artifact settings without routing through legacy mode processors.
- Replaced cwd-relative invoice backup with one explicit-root implementation
  and replaced process-wide SmartTable cache clearing with targeted per-root
  invalidation owned by the Runner's invoice service.
- Added two-thread, distinct-root acceptance coverage across all five modes;
  output snapshots, invoice content, and primary RunReport fields match an
  isolated execution.
- Deferred live per-tile wiring of `RawArtifactService` and
  `ImageArtifactService` to Phase I I5/I6 so Phase H does not change existing
  output trees or frozen contracts.

### Fixed — Phase H PR #521 blocker remediation

- Made failed-run finalization resolve both project-root and already-flat
  `data` layouts before writing the absolute `job.failed` path, while retaining
  the unchanged v1 writer and file format.
- Replaced identity serialization in `RunReport.to_legacy_statuses()` with a
  total conversion from primary `RunAggregator` iteration results. Tile
  results now retain title, target, and stacktrace at the execution boundary.
- Bumped `RunReport.schema_version` from `"1"` to `"2"` because the serialized
  iteration schema adds `title`, `target`, and `stacktrace`. Consumers that
  read only existing primary fields remain compatible; schema-aware consumers
  must accept version 2. `rdetoolkit report show` now reads the current schema
  constant instead of hardcoding an older version.
- Classified explicit v1 `Config` instances with `origin="v1"` and preserved
  catalogued `RdeConfigError(1002)` failures instead of exposing Pydantic
  `ValidationError` causes.
- Separated business-lifecycle failure handling from the exactly-once
  finalization boundary. Finalization I/O failures now surface as catalogued
  `RdeInternalError(5001)` and never trigger a second finalize attempt.
- Enabled branch coverage and added focused rejection, interruption, path,
  artifact-filter, directory-copy, copy-failure, and disabled-image tests for
  new Phase H modules.
- Corrected legacy status identities to the v1-observed four-digit tile index
  (`0000`, `0001`, ...), kept run-level UUIDs out of every compatibility
  status, and preserved those deterministic values during fixture freezing.
- Unified RunReport and `job.failed` placement through the four-tier data-root
  resolver: explicit `data`, existing nested `data`, marker-identified alias
  flat root, then a bare project root's future `data` child.
- Added CI enforcement for 95% branch coverage on the six reviewed Phase H
  modules at the end of the existing Python 3.12 module run. Focused tox
  invocations skip the scoped gates while retaining the global 80% policy.

### Changed — Phase I core mode seam

- Added the narrow `ModeHandler` planning protocol and mode registry. The
  planner delegates tile-plan creation to registered handlers while retaining
  its unchanged legacy iterator fallback until per-mode migration in I5/I6.
- Added optional, default-off per-tile `RawArtifactService` and
  `ImageArtifactService` injection to `TileExecutor`; injected services run
  only after completed tile execution, so existing output trees remain
  unchanged.
- Removed the test-only `backup_invoice_json_files` re-export from the planner
  and strengthened the ExcelInvoice backup guard at the direct
  `InvoiceService.backup` boundary.
- Kept RunReport data-root handling unchanged in this session because the
  I0.4 symmetry fix was already completed during Phase H review remediation.

### Added — Phase I walking skeleton (five modes, two entry points)

- Added thin `ModeHandler` implementations for invoice, ExcelInvoice,
  MultiDataTile, RDEFormat, and SmartTable, plus the explicit
  `modes.install.install_default_handlers()` registration the Runner performs
  while it is constructed. Registration is never an import side effect, so the
  planner fallback stays reachable. The handlers delegate to one shared tile
  builder, so the planned tiles are identical to the pre-handler Runner in
  every mode; mode-specific behavior arrives in I6.
- Added the minimal v1 callback adapter `compat/v1/callback.py`
  (`LegacyCallbackInvoker`, `to_legacy_dataset_paths`,
  `accepts_unified_argument`). It only converts arguments and calls the user
  callback, porting the v1 `DatasetRunner` signature rules including the
  guarded fallback for undecidable signatures. Call-log semantics for this
  entry point remain Session I8 work.
- Added the Runner-side `InvokerRegistry` that selects the flow or legacy
  adapter for a normalized target, and removed the placeholder `TypeError`
  that rejected `LegacyCallbackTarget` at the Runner entrance. `workflows.run`
  is unchanged: the public v1 entry point still uses the v1 code path.
- `Runner.iterate` now accepts a normalized execution target (a bare flow
  callable is still accepted and wrapped), and a callback-free legacy run
  reports the stable flow id `rdetoolkit.compat.v1.callback:none`.
- Added `modes.registry.clear()` so a caller can return to the
  pre-installation state without reaching into registry internals.

### Fixed — Phase I unified flow error translation

- Fixed the loss of raised error codes on the v2 Runner path. A
  `StructuredError` carries `emsg` / `ecode`, not `message` / `code`, so the
  tile, run-level, and finalize translators all silently rewrote it as 3001
  `NodeExecutionFailed`. Its `ecode` and `emsg` now reach `RunReport.error` and
  `job.failed` verbatim, restoring the v1 Tier 1 contract (Design §6.3).
  Catalog substitution still applies to everything else: a plain exception is
  3001, an `RdeError` keeps its own code, and an off-catalog code that is not a
  passthrough record is still replaced in `finalize`. No `RunReport.error`
  field was added, so `schema_version` remains `"2"`.
- Added `runner.finalize.structured_error_record()` as the single owner of that
  rule, used by the tile executor, the lifecycle failure path, and the
  `job.failed` writer. The passthrough covers every `StructuredError` a v2
  domain error has not already wrapped — framework-raised ones included, since
  v1 `catch_exception_with_message` publishes those verbatim as well — while
  validation stays 4001/4002/4003. At the tile boundary only
  `code`/`name`/`message`/`remediation` are replaced, so recorder context such
  as `call_id` still identifies the failing call.
- Contracted the v1-to-v2 error mapping for all five modes as
  `tests/v2/contract/flow_error_table.py` and contracts.md §I6-0. Validation
  failures keep the v2 catalog codes (4001 for every mode's invalid source
  invoice) rather than v1's mode-specific 999 / 1, because v2 validates the
  source invoice before the flow runs. The ten TC-UM FLOW-USERERR /
  FLOW-VALERR seats now assert that table instead of being placeholders;
  twelve Phase J seats (policy, SIGTERM, callback observability) stay xfail.

### Changed — Phase I artifact publication is wired

- The Runner now injects `RawArtifactService` and `ImageArtifactService` into
  its tile executor by default, so `save_raw`, `save_nonshared_raw`, and
  `save_thumbnail_image` finally take effect on the v2 path. The services read
  those settings themselves, so configuration — not construction — decides
  whether a completed tile publishes anything. Failed tiles publish nothing,
  and a caller-supplied executor is never overridden.

### Added — Phase I output-tree parity foundation (Session I6-1)

- Every tile now owns the same **twelve** directories as v1, adding `temp/` and
  `invoice_patch/`. `TileOutputPaths` carries them and the iterator creates
  them; `OutputContext` still exposes ten fields, so the directories are a
  contract while the public output API is unchanged (Design §6.3 addendum).
- The tile executor gained an artifact stage split around the flow, matching
  every v1 pipeline: the raw/nonshared copy runs **before** the flow (v1's
  FileCopier precedes DatasetRunner), while thumbnail,
  `structured/invoice.json`, magic variable and the feature description update
  run after it and only for completed tiles. Each step keeps its v1 config
  gate. `InvoiceService.apply_config` — previously never called — is now the
  production path for the last three, and it receives the whole v1
  `RdeDatasetPaths` bundle so `${invoice:...}` and `${metadata:...}` resolve
  the way v1's VariableApplier resolves them.
- A tile whose flow fails therefore keeps the raw copies v1 would have made,
  which is what the frozen `usererr` observations record.
- The run-level invoice backup now happens after the input checker has parsed,
  as in v1 (`backup_invoice_json_files` runs after `check_files`). With the
  unpack root at `data/temp`, backing up earlier made the RDEFormat checker
  ingest `data/temp/invoice_org.json` as raw data.
- The structured invoice copy now takes the run-level `invoice_org`, matching
  v1's `StructuredInvoiceSaver`. Copying the tile invoice would have published
  magic-variable substitutions that v1 never writes to `structured/`.
- Artifact stages run outside the flow invocation and are attributed
  separately: raw/nonshared and thumbnail failures are the new **3005
  `ArtifactPublicationFailed`**, invoice-stage failures are the new **3006
  `InvoiceArtifactFailed`**, and a `StructuredError` raised by the invoice
  stage keeps its v1 `ecode`/`emsg` (Session I6-0 passthrough). None of them is
  reported as 3001 `NodeExecutionFailed`, because the flow already succeeded.
  A failed post-invoke stage keeps the tile's call log and stack trace.
- `ModeHandler` gained two optional seams, `raw_copy_strategy(plan)` and
  `invoice_stage_steps(plan)`. All five built-in handlers return `None` from
  both; Session I6-A uses them for the RDEFormat copy semantics and for the
  fact that v1's RDEFormat pipeline runs neither StructuredInvoiceSaver nor
  VariableApplier.
- Installing the built-in mode handlers no longer overwrites a handler the
  caller registered before constructing a Runner.
- The tile iterator forwards the effective configuration to the legacy input
  checkers, so `smarttable.save_table_file` is reachable on the v2 path. The
  default (`False`) reproduces the previous tile layout exactly.
- v1 callbacks now receive real `temp`, `invoice_patch`, `smarttable_rowfile`
  and `smarttable_row_data` values (Session I5 left all four `None`), and
  `invoice_org` is resolved run-level so divided tiles stop looking for a
  backup inside `divided/NNNN/temp/`.
- `tests/v2/contract/observe.py` observes a v2 run through the frozen
  `_generate` walkers, and the `invoice`, `multidatatile`, `excelinvoice` and
  `smarttable` FLOW-OK matrix cells now compare the complete artifact
  observation — output tree (excluding the contents of `data/logs/`),
  `raw_sha256`, and written invoices — with the frozen v1 snapshot. Only
  `rdeformat` keeps the narrower comparison, until Session I6-A ports the
  RDEFormat copy semantics.

### Added — Phase H real-canary compatibility protection

- Added permanent import and minimal-behavior coverage for the maintained v1
  Tier 1 public API, including an explicit compatibility pin for
  `rdetoolkit.core.detect_encoding`.
- Imported representative real inputs for invoice, ExcelInvoice,
  MultiDataTile, RDEFormat, and SmartTable without copying canary program code
  or dependency environments.
- Added a repository-independent assembly helper for Phase K v1↔v2 canary
  comparisons. MultiDataTile combines the shared schema and metadata support
  with its mode-specific `rdeconfig.yaml` overlay.
- Added a deterministic canary-import sanitization boundary. ExcelInvoice user
  names become `RDE,User01` through `RDE,User04`; user IDs and invoice owner IDs
  become synthetic 56-digit values ending in `1` through `4`; sample owner IDs
  use the non-colliding value ending in `5`. The sanitizer edits OOXML members
  surgically to retain formulas and cached values, removes personal workbook
  metadata, and is byte-idempotent after the first import.
- Froze five additional OK-only v1 observations under `expected/canary` through
  the canonical normalization and provenance path. The G1 SmartTable input and
  affected observations use the same synthetic owner-ID policy; this is the
  sole intentional update to the original 16 synthetic G1 observations.

#### Existing-test UPDATE table

| Test seat | Previous expectation | Strengthened expectation and reason |
| --- | --- | --- |
| `test_finalize.py` TC-FIN-006 | v1 writer received only code/message | writer must also receive the resolved absolute root-owned filename (F1) |
| `test_legacy_statuses_contract.py` TC-EP-G2-301..315 | expected legacy payload was injected into `RunReport.iterations` | independent frozen invoices/output inventory produce real `ExecutionResult` → `RunAggregator` output before exact legacy comparison (F2; removes tautology) |
| `test_aggregator.py` TC-AGG-001 | five-field iteration summary | summary explicitly retains compatibility title/target/stacktrace (F2 schema 2) |
| `test_iteration_streaming.py` TC-D2R-F5 | five-field canonical summary | serialized iteration schema 2 includes the three explicit compatibility inputs (F2) |
| `test_execute.py` TC-EXEC-001 | six-field `ExecutionResult` | execution result explicitly carries title/target/stacktrace while they are available (F2) |
| `test_run_report.py` TC-EP-001/002 | schema version 1 | schema version 2 is asserted after the serialized iteration change (F2) |
| `test_run_flow.py` TC-E2E-004 | schema version 1 | end-to-end report asserts schema version 2 (F2) |
| `test_event_schema.py` TC-EVENT-022 helper/assertion | schema version 1 | schema-aware serialization seat asserts version 2 (F2) |
| `test_config_loader.py` TC-CFG-005/006 | raw Pydantic `ValidationError` | public `RdeConfigError` with integer code 1002 (F4 contract strengthening) |
| `test_rdeconfig_v1_keys.py` TC-EP-G2-005 | direct model `ValidationError` | public loader rejects every strict-section unknown key with `RdeConfigError(1002)` (F4) |
| `test_cli_report.py` TC-CLI-REPORT-EP-003 fixture | version-1 report was current | version-2 report is current and must not emit an unknown-schema warning (F2 consumer compatibility) |
| `test_legacy_statuses_contract.py` TC-EP-G2-301..315 | run-level placeholder could mask tile identity | fixed run UUID is deliberately distinct; frozen four-digit tile IDs must match and never expose the UUID (A/E) |
| `test_legacy_statuses_contract.py` TC-EP/BV-HR2-AE-001 | no production-path multi-tile identity regression | real `Runner.run` with two tiles yields `0000` and `0001` while retaining its separate UUID (A/E) |
| `test_fixture_generator.py` TC-HR2-E-001 | every `run_id` key normalized to one placeholder | deterministic legacy tile IDs survive normalization and regeneration (E) |
| `test_finalize.py` TC-EP/BV-HR2-B-001 | report path covered project roots only | flat `data` root writes directly to `logs` and never creates `data/data` (B) |
| `test_paths.py` TC-EP/BV-HR2-B-002/003 | project/flat fallback was ambiguous for bare and alias roots | four resolver priorities cover explicit, nested, marker-flat, and bare-project layouts (B) |
| `test_coverage_policy.py` TC-EP/BV-HR2-C-001/002 | branch measurement enabled without scoped enforcement | existing Python 3.12 CI run enforces six independent 95% module gates and preserves focused tox use (C) |

### Added — Phase I RDEFormat copy semantics and canary parity (Session I6-A)

- `modes/rdeformat.py` now owns RDEFormat raw publication through
  `RdeFormatRawCopyStrategy`, installed on the Session I6-1
  `ModeHandler.raw_copy_strategy` seam. It reproduces v1's
  `RDEFormatFileCopier`: each raw input is copied to the tile directory named
  by the **first** matching path component, in v1's own order (`raw`,
  `main_image`, `other_image`, `meta`, `structured`, `logs`, `nonshared_raw`),
  with no `save_raw` / `save_nonshared_raw` gate and no SmartTable filtering.
  An input naming no component is copied nowhere, and an input is never
  mirrored into a second directory — both differences from the generic
  `RawArtifactService`. Directory creation stays owned by the Runner, so a
  missing destination raises catalogued `RdeExecutionError` 3001 instead of
  being papered over.
- The same handler narrows `invoice_stage_steps` to the thumbnail and
  description steps, because v1's RDEFormat pipeline
  (`processing/factories.py::RDEFormatPipelineBuilder`) contains neither
  `StructuredInvoiceSaver` nor `VariableApplier`. Of the three invoice steps
  `InvoiceService.apply_config` understands, only `description` is selected.
  RDEFormat is now the single built-in handler that overrides either seam;
  the other four still resolve to the generic service and the full invoice
  stage (this supersedes the I6-1 note that all five return `None`).
- `TC-UM-RDF-FLOW-OK` joined `_FULL_PARITY_MODES`, so **all five** matrix
  FLOW-OK cells now compare the complete frozen artifact observation — output
  tree (excluding the contents of `data/logs/`), `raw_sha256`, and written
  invoices — instead of tile counts and invoice values alone.
- New `TC-UM-*-CANARY-FLOW-OK` matrix cells run the eager v2 Runner against the
  imported real RDE canary material and compare the same full parity view with
  `expected/canary/<mode>/ok.json`. Session I6-A enables `invoice` and
  `rdeformat`; the cell body is mode-agnostic, so a mode is added by one entry
  in `_CANARY_FLOW_MODES`. Because a v2 flow entry does not discover
  `data/tasksupport/rdeconfig.yaml`, each cell hands the frozen
  `case.effective_config` to the Runner as explicit overrides, projected by the
  production `ConfigNormalizer` (`origin="v1"`) so the harness cannot invent a
  mapping of its own.
- The RDEFormat canary is the only case in either family that produces
  thumbnails: it proves `data/temp/main_image/1.jpg` reaching
  `data/main_image/1.jpg` through the new strategy and then
  `data/thumbnail/1.jpg` through the config-gated image stage. The generic
  service would have collapsed both `1.jpg` inputs into `data/raw/` and
  produced no thumbnail at all.

#### Existing-test UPDATE table

| Test seat | Previous expectation | Strengthened expectation and reason |
| --- | --- | --- |
| `test_artifact_seam_i6_1.py` TC-I6-1-EP-031 | all five built-in handlers return `None` from `raw_copy_strategy` | the four non-RDEFormat handlers return `None` **and** RDEFormat returns an `RdeFormatRawCopyStrategy` — pins which single mode owns the seam instead of asserting nobody uses it (I6-A ruling #1) |
| `test_unified_matrix.py` `_FULL_PARITY_MODES` / TC-UM-RDF-FLOW-OK | rdeformat compared tile count and invoice values only | rdeformat compares the complete frozen artifact observation, like the other four modes |

### Added — Phase I ExcelInvoice / MultiDataTile compatibility pins (Session I6-B)

- The real-canary FLOW cells for `excelinvoice` and `multidatatile` are now
  compared against `expected/canary/<mode>/ok.json` with the same full parity
  view the FLOW-OK cells use (`TC-UM-XLS-CANARY-FLOW-OK`,
  `TC-UM-MDT-CANARY-FLOW-OK`, plus the mode-owned
  `tests/v2/modes/test_{excelinvoice,multidatatile}_canary_i6_b.py`). The
  canary's effective configuration is handed to the Runner as overrides,
  projected by the production `ConfigNormalizer` with `origin="v1"`, because v2
  discovery still ignores `data/tasksupport/rdeconfig.yaml`.
- Added mode-specific compatibility coverage that runs v1 itself as a dynamic
  oracle (the same isolated worker that froze the static fixtures) instead of
  restating expectations: ExcelInvoice archive-less runs, single-group
  broadcast, one-group-per-row, group/row count mismatch, intermittent blank
  rows, and the two ways a second workbook can reach `inputdata`;
  MultiDataTile empty-`inputdata` fallback, `divided/000N` numbering, and
  ExcelInvoice file detection outranking a configured `extended_mode`.
- Pinned the ExcelInvoice workbook-identity contract observationally: v2
  re-discovers the workbook by extension from `rawfiles + inputdata`, and a
  v1-valid run can never present a competing candidate — a second
  `*_excel_invoice.xlsx` and a stray `.xlsx` are both rejected by v1 before
  selection, and an `.xlsx` arriving through the raw archive does not displace
  the `inputdata` workbook.
- Pinned the `multidata_tile.ignore_errors` <-> `execution.on_iteration_error`
  projection in both directions. The default's correctness stays open for
  Session I7 and the multi-tile policy seats stay Phase J xfails.
- No ExcelInvoice or MultiDataTile production code changed: both handlers keep
  the generic raw-copy strategy and the full invoice stage, and full parity
  holds with the Session I6-1 wiring alone.

### Added — Phase I SmartTable invoice builder and run-owned base invoice (Session I6-C)

- `modes/smarttable.py` now owns `SmartTableInvoiceBuilder`, a port of the v1
  SmartTable invoice initializer (`processing/processors/invoice.py`). The v2
  path no longer constructs a throwaway `ProcessingContext` /
  `RdeOutputResourcePath` bundle to reach a v1 processor: the merge rules
  (`basic/`, typed `custom/`, `sample/names` new-sample clearing, general and
  specific attributes, empty-cell clearing, `sample.ownerId` inheritance),
  the strict SmartTable casting rules and the `meta/` to `metadata.json`
  emission are v2 code, pinned against the v1 processor used as a test-side
  oracle (`tests/v2/modes/test_smarttable_invoice_builder_i6_c.py`, 20 merge and
  rejection scenarios plus the real canary end to end).
- The base invoice is now **run-owned**. v1 kept it in a class attribute keyed
  by the resolved source path — necessary because SmartTable tile 0 writes its
  merged invoice back over `data/invoice/invoice.json`, so later tiles must not
  re-read it — and the Runner had to evict that key at every run boundary. The
  snapshot now lives on the run's `InvoiceService`, so two runs over one root
  never share or evict each other's base invoice, and a service reused for a
  second run always re-reads the source. `SmartTableInvoiceInitializer` and its
  `_BASE_INVOICE_CACHE` are no longer referenced anywhere under
  `domain/`, `modes/`, `runner/` or `compat/`; the v1 processor and v1's own
  process-wide clear in `workflows.py` are untouched.
- `TC-UM-SMT-CANARY-FLOW-OK` joined `_CANARY_FLOW_MODES`: the imported
  battery-electrolyte SmartTable canary now reproduces the frozen v1
  observation exactly through the v2 flow entry, which is the end-to-end proof
  that the ported builder writes v1's `invoice.json` for real input.

#### Added — `smarttable.save_table_file=True` (v1 EarlyExit parity)

- `TilePlan` gained one optional, mode-owned field, `precompleted` (default
  `False`, so every existing tile is unchanged). When a mode sets it,
  `TileExecutor` publishes the tile's raw inputs and then records the iteration
  as `completed` with an empty call log — **without invoking the flow** and
  without the post-invoke invoice stage. `Runner.post_validate` still validates
  the tile, which is v1's order: `SmartTableEarlyExitProcessor` validates before
  it raises `SkipRemainingProcessorsError`. `modes/protocol.py` is unchanged.
- `SmartTableModeHandler` marks the tile whose raw input is the original
  `inputdata/smarttable_*.{xlsx,csv,tsv}` and installs an EarlyExit
  `prepare_invoice` that writes `basic.dataName = <table filename>`. The table
  copy into `raw/` + `nonshared_raw/` needs no mode-specific strategy: with
  `save_table_file` on, the generic `RawArtifactService` already keeps the
  original table and honours `save_raw` / `save_nonshared_raw`, exactly like
  v1's EarlyExit copy.
- Contract: with N rows and `save_table_file=True`, `report.iterations` has
  N + 1 entries and the flow is invoked N times, matching the v1 tile count and
  `callback_count`. Verified by running **v1 itself** in an isolated worker
  (`tests/v2/modes/test_smarttable_early_exit_i6_c.py`) and comparing
  `output_tree` (logs excluded), `raw_sha256` and `invoices`;
  `fixtures/expected/**` and `_generate.py` are untouched.

#### Existing-test UPDATE table

| Test seat | Previous expectation | Strengthened expectation and reason |
| --- | --- | --- |
| `test_smarttable_cache_isolation.py` TC-G0-CACHE-001 | probe called `build_smarttable_tile_invoice` directly and reset the v1 class cache through a fixture | probe drives `InvoiceService.prepare_tile` (the production call site) with no v1 import, and additionally asserts that **one Runner reused for two runs** reloads a changed base invoice — the property the removed process-wide eviction used to provide |
| `test_unified_matrix.py` `_CANARY_FLOW_MODES` | smarttable had no canary FLOW cell | smarttable compares the full frozen canary observation (output tree, raw digests, invoices) |

### Fixed — Phase I I6-A audit follow-up (tests only)

- The RDEFormat invoice-stage narrowing had no behavioral test: `structured`
  and `magic` are double-gated by `save_invoice_to_structured` and
  `magic_variable`, and every frozen observation was generated with both
  `False`, so removing the override changed no frozen artifact and only the two
  self-referential seam asserts noticed. `test_rdeformat_invoice_stage_i6_a.py`
  now runs v1 itself as a **dynamic oracle** with both switches `True` and
  `basic.dataName` seeded as `${filename}`, and compares it with a v2 Runner run
  over the same input (output tree minus `data/logs/`, `raw_sha256`, invoices).
  Two explicit negatives pin the consequences — no `structured/invoice.json` in
  any tile, and the `${filename}` literal surviving in every written invoice —
  and a fourth cell asserts the same two facts about the **v1 oracle run
  itself**, so the expectation is v1's and not a v2 self-portrait. Restoring
  `invoice_stage_steps -> None` turns three of the four RED. The committed
  fixture inputs are untouched: the case is materialized into a temporary root
  by the shared `_generate` assembly and patched there.
