# Changelog

## Version Index

| Version | Release Date | Key Changes | Details |
| ------- | ------------ | ----------- | ------- |
| v1.4.0  | 2025-10-24   | SmartTable `metadata.json` auto-generation / LLM-friendly traceback / CSV visualization utility / `gen-config` | [v1.4.0](#v140-2025-10-24) |
| v1.3.4  | 2025-08-21   | Stable SmartTable validation | [v1.3.4](#v134-2025-08-21) |
| v1.3.3  | 2025-07-29   | Fixed `ValidationError` handling / Added `sampleWhenRestructured` schema | [v1.3.3](#v133-2025-07-29) |
| v1.3.2  | 2025-07-22   | Strengthened SmartTable required-field validation | [v1.3.2](#v132-2025-07-22) |
| v1.3.1  | 2025-07-14   | Excel invoice empty-sheet fix / Stricter `extended_mode` validation | [v1.3.1](#v131-2025-07-14) |
| v1.2.0  | 2025-04-14   | MinIO integration / Archive generation / Report tooling | [v1.2.0](#v120-2025-04-14) |

# Release Details

## v1.4.0 (2025-10-24)

!!! info "References"
    - `local/develop/release_v140.md`
    - `local/develop/PR_v140.md`
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
    - `local/develop/PR_v134.md` (equivalent)
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
    - `local/develop/Release_v133.md`
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
    - `local/develop/PR_v132.md` (equivalent)
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
    - `local/develop/Release_v131.md`
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
    - `local/develop/PR_v120.md`
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
