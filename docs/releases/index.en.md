# Changelog

## Version Index

| Version | Release Date | Key Changes | Details |
| ------- | ------------ | ----------- | ------- |
| v1.4.3  | 2025-12-25   | SmartTable data integrity fixes / csv2graph HTML destination + legend/log-scale tweaks | [v1.4.3](#v143-2025-12-25) |
| v1.4.2  | 2025-12-18   | Invoice overwrite validation / Excel invoice consolidation / csv2graph auto single-series / MultiDataTile empty input | [v1.4.2](#v142-2025-12-18) |
| v1.4.1  | 2025-11-05   | SmartTable rowfile accessor / legacy fallback warnings | [v1.4.1](#v141-2025-11-05) |
| v1.4.0  | 2025-10-24   | SmartTable `metadata.json` auto-generation / LLM-friendly traceback / CSV visualization utility / `gen-config` | [v1.4.0](#v140-2025-10-24) |
| v1.3.4  | 2025-08-21   | Stable SmartTable validation | [v1.3.4](#v134-2025-08-21) |
| v1.3.3  | 2025-07-29   | Fixed `ValidationError` handling / Added `sampleWhenRestructured` schema | [v1.3.3](#v133-2025-07-29) |
| v1.3.2  | 2025-07-22   | Strengthened SmartTable required-field validation | [v1.3.2](#v132-2025-07-22) |
| v1.3.1  | 2025-07-14   | Excel invoice empty-sheet fix / Stricter `extended_mode` validation | [v1.3.1](#v131-2025-07-14) |
| v1.2.0  | 2025-04-14   | MinIO integration / Archive generation / Report tooling | [v1.2.0](#v120-2025-04-14) |

# Release Details

## v1.4.3 (2025-12-25)

!!! info "References"
    - Key issues: [#292](https://github.com/nims-mdpf/rdetoolkit/issues/292), [#310](https://github.com/nims-mdpf/rdetoolkit/issues/310), [#311](https://github.com/nims-mdpf/rdetoolkit/issues/311), [#302](https://github.com/nims-mdpf/rdetoolkit/issues/302), [#304](https://github.com/nims-mdpf/rdetoolkit/issues/304)

#### Highlights
- SmartTable split processing now preserves `sample.ownerId`, respects boolean columns, and prevents empty cells from inheriting values from previous rows, restoring per-row data integrity.
- csv2graph defaults HTML artifacts to the CSV directory (structured) and adds `html_output_dir` for overrides, while aligning Plotly/Matplotlib legend text and log-scale tick formatting for consistent outputs.

#### Enhancements
- Cache the base invoice once in SmartTable processing and pass deep copies per row so divided invoices retain `sample.ownerId`.
- Detect empty SmartTable cells and clear mapped basic/custom/sample fields instead of reusing prior-row values.
- Cast `"TRUE"` / `"FALSE"` (case-insensitive) according to schema boolean types so Excel-derived strings convert correctly during SmartTable writes.
- Added `html_output_dir` / `--html-output-dir` to csv2graph, defaulting HTML saves to the CSV directory, and refreshed English/Japanese docs and samples.
- Standardized Plotly legend labels to series names (trimmed before `:`) and enforced decade-only log ticks with 10^ notation across Plotly and Matplotlib.
- Added EP/BV-backed regression tests for SmartTable ownerId inheritance, empty-cell clearing, boolean casting, csv2graph HTML destinations, and renderer legend/log formatting.

#### Fixes
- Resolved loss of `sample.ownerId` on SmartTable rows after the first split.
- Prevented empty SmartTable cells from carrying forward prior-row values into basic/description and sample/composition/description fields.
- Fixed boolean casting that treated `"FALSE"` as truthy; schema-driven conversion now produces correct booleans.
- Corrected csv2graph HTML placement when `output_dir` pointed to `other_image`, defaulting HTML to the CSV/structured directory unless overridden.
- Normalized Plotly legends that previously showed full headers (e.g., `total:intensity`) and removed 2/5 minor log ticks while enforcing exponential labels.

#### Migration / Compatibility
- csv2graph now saves HTML alongside the CSV by default (typically `data/structured`). Use `html_output_dir` (API) or `--html-output-dir` (CLI) to target a different directory.
- SmartTable no longer reuses prior-row values for empty cells; provide explicit values on each row where inheritance was previously relied upon.
- String booleans `"TRUE"` / `"FALSE"` are force-cast to real booleans. Review workflows that accidentally depended on non-empty strings always evaluating to `True`.
- No other compatibility changes.

#### Known Issues
- None reported at this time.

---

## v1.4.2 (2025-12-18)

!!! info "References"
    - Key issues: [#30](https://github.com/nims-mdpf/rdetoolkit/issues/30), [#36](https://github.com/nims-mdpf/rdetoolkit/issues/36), [#246](https://github.com/nims-mdpf/rdetoolkit/issues/246), [#293](https://github.com/nims-mdpf/rdetoolkit/issues/293)

#### Highlights
- `InvoiceFile.overwrite()` now accepts dictionaries, validates them through `InvoiceValidator`, and can fall back to the existing `invoice_path`.
- Excel invoice reading is centralized inside `ExcelInvoiceFile`, with `read_excelinvoice()` acting as a warning-backed compatibility wrapper slated for v1.5.0 removal.
- `csv2graph` detects when a single series is requested and suppresses per-series plots unless the CLI flag explicitly demands them, keeping CLI and API defaults in sync.
- MultiDataTile pipelines continue to run—and therefore validate datasets—even when the input directory only contains Excel invoices or is empty.

#### Enhancements
- Updated `InvoiceFile.overwrite()` to accept mapping objects, apply schema validation through `InvoiceValidator`, and default the destination path to the instance’s `invoice_path`; refreshed docstrings and `docs/rdetoolkit/invoicefile.md` to describe the new API.
- Converted `read_excelinvoice()` into a wrapper that emits a deprecation warning and delegates to `ExcelInvoiceFile.read()`, updated `src/rdetoolkit/impl/input_controller.py` to use the class API directly, and clarified docstrings/type hints so `df_general` / `df_specific` may be `None`.
- Adjusted `Csv2GraphCommand` so `no_individual` is typed as `bool | None`, added CLI plumbing that inspects `ctx.get_parameter_source()` to detect explicit user input, and documented the overlay-only default in `docs/rdetoolkit/csv2graph.md`.
- Added `assert_optional_frame_equal` and new regression tests that cover csv2graph CLI/API flows plus MultiFileChecker behaviors for Excel-only, empty, single-file, and multi-file directories.

#### Fixes
- Auto-detecting single-series requests avoids generating empty per-series artifacts and aligns CLI defaults with the Python API.
- `_process_invoice_sheet()`, `_process_general_term_sheet()`, and `_process_specific_term_sheet()` now correctly return `pd.DataFrame` objects, avoiding attribute errors in callers that expect frame operations.
- `MultiFileChecker.parse()` returns `[()]` when no payload files are detected so MultiDataTile validation runs even on empty input directories, matching Invoice mode semantics.

#### Migration / Compatibility
- Code calling `InvoiceFile.overwrite()` can now supply dictionaries directly; omit the destination argument to write to the instance path, and expect schema validation errors when invalid structures are provided.
- `read_excelinvoice()` is officially deprecated and scheduled for removal in v1.5.0—migrate to `ExcelInvoiceFile().read()` or `ExcelInvoiceFile.read()` helpers.
- `csv2graph` now generates only the overlay/summary graph when `--no-individual` is not specified and there is one (or zero) value columns; pass `--no-individual=false` to force legacy per-series output or `--no-individual` to always skip them.
- MultiDataTile runs on empty directories no longer short-circuit; expect validation failures to surface when required payload files are absent.

#### Known Issues
- None reported at this time.

---

## v1.4.1 (2025-11-05)

!!! info "References"
    - Key issues: [#204](https://github.com/nims-mdpf/rdetoolkit/issues/204), [#272](https://github.com/nims-mdpf/rdetoolkit/issues/272), [#273](https://github.com/nims-mdpf/rdetoolkit/issues/273), [#278](https://github.com/nims-mdpf/rdetoolkit/issues/278)

#### Highlights
- Dedicated SmartTable row CSV accessors replace ad-hoc `rawfiles[0]` lookups without breaking existing callbacks.
- MultiDataTile workflows now guarantee a returned status and surface the failing mode instead of producing silent job artifacts.
- CSV parsing tolerates metadata comments and empty data windows, removing spurious parser exceptions.
- Graph helpers (`csv2graph`, `plot_from_dataframe`) are now exported directly via `rdetoolkit.graph` for simpler imports.

#### Enhancements
- Introduced the `smarttable_rowfile` field on `RdeOutputResourcePath` and exposed it via `ProcessingContext.smarttable_rowfile` and `RdeDatasetPaths`.
- SmartTable processors populate the new field automatically; when fallbacks hit `rawfiles[0]` a `FutureWarning` is emitted to prompt migration while preserving backward compatibility.
- Refreshed developer guidance so SmartTable callbacks expect the dedicated row-file accessor.
- Re-exported `csv2graph` and `plot_from_dataframe` from `rdetoolkit.graph`, aligning documentation and samples with the simplified import path.

#### Fixes
- Ensured MultiDataTile mode always returns a `WorkflowExecutionStatus` and raises a `StructuredError` that names the failing mode if the pipeline fails to report back.
- Updated `CSVParser._parse_meta_block()` and `_parse_no_header()` to ignore `#`-prefixed metadata rows and return an empty `DataFrame` when no data remains, eliminating `ParserError` / `EmptyDataError`.

#### Migration / Compatibility
- Existing callbacks using `resource_paths.rawfiles[0]` continue to work, but now emit a `FutureWarning`; migrate to `smarttable_rowfile` to silence it.
- The `rawfiles` tuple itself remains the primary list of user-supplied files—only the assumption that its first entry is always the SmartTable row CSV is being phased out.
- No configuration changes are required for CSV ingestion; the parser improvements are backward compatible.
- Prefer `from rdetoolkit.graph import csv2graph, plot_from_dataframe`; the previous `rdetoolkit.graph.api` path remains available for now.

#### Known Issues
- None reported at this time.

---

## v1.4.0 (2025-10-24)

!!! info "References"
    - Key issues: [#144](https://github.com/nims-mdpf/rdetoolkit/issues/144), [#188](https://github.com/nims-mdpf/rdetoolkit/issues/188), [#197](https://github.com/nims-mdpf/rdetoolkit/issues/197), [#205](https://github.com/nims-mdpf/rdetoolkit/issues/205), [#236](https://github.com/nims-mdpf/rdetoolkit/issues/236)

#### Highlights
- SmartTableInvoice automatically writes `meta/` columns to `metadata.json`
- Compact AI/LLM-friendly traceback output (duplex mode)
- CSV visualization utility `csv2graph`
- Configuration scaffold generator `gen-config`

#### Enhancements
- Added the `csv2graph` API with multi-format CSV support, direction filters, Plotly HTML export, and 220+ tests.
- Added the `gen-config` CLI with template presets, bilingual interactive mode, and `--overwrite` safeguards.
- SmartTableInvoice now maps `meta/` prefixed columns—converted via `metadata-def.json`—into the `constant` section of `metadata.json`, preserving existing values and skipping if definitions are missing.
- Introduced selectable traceback formats (`compact`, `python`, `duplex`) with sensitive-data masking and local-variable truncation.
- Consolidated RDE dataset callbacks around a single `RdeDatasetPaths` argument while emitting deprecation warnings for legacy signatures.

#### Fixes
- Resolved a MultiDataTile issue where `StructuredError` failed to stop execution when `ignore_errors=True`.
- Cleaned up SmartTable error handling and annotations for more predictable failure behavior.

#### Migration / Compatibility
- Legacy two-argument callbacks continue to work but should migrate to the single-argument `RdeDatasetPaths` form.
- Projects using SmartTable `meta/` columns should ensure `metadata-def.json` is present for automatic mapping.
- Traceback format configuration is optional; defaults remain unchanged.

#### Known Issues
- None reported at this time.

---

## v1.3.4 (2025-08-21)

!!! info "References"
    - Key issue: [#217](https://github.com/nims-mdpf/rdetoolkit/issues/217) (SmartTable/Invoice validation reliability)

#### Highlights
- Stabilized SmartTable/Invoice validation flow.

#### Enhancements
- Reworked validation and initialization to block stray fields and improve exception messaging.

#### Fixes
- Addressed SmartTableInvoice validation edge cases causing improper exception propagation or typing mismatches.

#### Migration / Compatibility
- No breaking changes.

#### Known Issues
- None reported at this time.

---

## v1.3.3 (2025-07-29)

!!! info "References"
    - Key issue: [#201](https://github.com/nims-mdpf/rdetoolkit/issues/201)

#### Highlights
- Fixed `ValidationError` construction and stabilized Invoice processing.
- Added `sampleWhenRestructured` schema for copy-restructure workflows.

#### Enhancements
- Introduced the `sampleWhenRestructured` pattern so copy-restructured `invoice.json` files requiring only `sampleId` validate correctly.
- Expanded coverage across all sample-validation patterns to preserve backward compatibility.

#### Fixes
- Replaced the faulty `ValidationError.__new__()` usage with `SchemaValidationError` during `_validate_required_fields_only` checks.
- Clarified optional fields for `InvoiceSchemaJson` and `Properties`, fixing CI/CD mypy failures.

#### Migration / Compatibility
- No configuration changes required; existing `invoice.json` files remain compatible.

#### Known Issues
- None reported at this time.

---

## v1.3.2 (2025-07-22)

!!! info "References"
    - Key issue: [#193](https://github.com/nims-mdpf/rdetoolkit/issues/193)

#### Highlights
- Strengthened required-field validation for SmartTableInvoice.

#### Enhancements
- Added schema enforcement to restrict `invoice.json` to required fields, preventing unnecessary defaults.
- Ensured validation runs even when pipelines terminate early.

#### Fixes
- Tidied exception handling and annotations within SmartTable validation.

#### Migration / Compatibility
- Backward compatible, though workflows adding extraneous `invoice.json` fields should remove them.

#### Known Issues
- None reported at this time.

---

## v1.3.1 (2025-07-14)

!!! info "References"
    - Key issues: [#144](https://github.com/nims-mdpf/rdetoolkit/issues/144), [#161](https://github.com/nims-mdpf/rdetoolkit/issues/161), [#163](https://github.com/nims-mdpf/rdetoolkit/issues/163), [#168](https://github.com/nims-mdpf/rdetoolkit/issues/168), [#169](https://github.com/nims-mdpf/rdetoolkit/issues/169), [#173](https://github.com/nims-mdpf/rdetoolkit/issues/173), [#174](https://github.com/nims-mdpf/rdetoolkit/issues/174), [#177](https://github.com/nims-mdpf/rdetoolkit/issues/177), [#185](https://github.com/nims-mdpf/rdetoolkit/issues/185)

#### Highlights
- Fixed empty-sheet exports in Excel invoice templates.
- Enforced stricter validation for `extended_mode`.

#### Enhancements
- Added `serialization_alias` to `invoice_schema.py`, ensuring `$schema` and `$id` serialize correctly in `invoice.schema.json`.
- Restricted `extended_mode` in `models/config.py` to approved values and broadened tests for `save_raw` / `save_nonshared_raw` behavior.
- Introduced `save_table_file` and `SkipRemainingProcessorsError` to SmartTable for finer pipeline control.
- Updated `models/rde2types.py` typing and suppressed future DataFrame warnings.
- Refreshed Rust string formatting, `build.rs`, and CI workflows for reliability.

#### Fixes
- Added raw-directory existence checks to prevent copy failures.
- Ensured `generalTerm` / `specificTerm` sheets appear even when attributes are empty and corrected variable naming errors.
- Specified `orient` in `FixedHeaders` to silence future warnings.

#### Migration / Compatibility
- Invalid `extended_mode` values now raise errors; normalize configuration accordingly.
- Review SmartTable defaults if relying on prior `save_table_file` behavior.
- `tqdm` dependency removal may require adjustments in external tooling.

#### Known Issues
- None reported at this time.

---

## v1.2.0 (2025-04-14)

!!! info "References"
    - Key issue: [#157](https://github.com/nims-mdpf/rdetoolkit/issues/157)

#### Highlights
- Introduced MinIO storage integration.
- Delivered artifact archiving and report-generation workflows.

#### Enhancements
- Implemented the `MinIOStorage` class for object storage access.
- Added commands for archive creation (ZIP / tar.gz) and report generation.
- Expanded documentation covering object-storage usage and reporting APIs.

#### Fixes
- Updated dependencies and modernized CI configurations.

#### Migration / Compatibility
- Fully backward compatible; enable optional dependencies when using MinIO.

#### Known Issues
- None reported at this time.
