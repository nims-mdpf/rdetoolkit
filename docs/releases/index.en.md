# Changelog

## Version Index

| Version | Release Date | Key Changes | Details |
| ------- | ------------ | ----------- | ------- |
| v1.5.2  | 2026-01-27   | CLI validate exit codes / metadata-def validation fix / Config error messages / Python 3.9 deprecation / PBT infrastructure | [v1.5.2](#v152-2026-01-27) |
| v1.5.1  | 2026-01-21   | SmartTable row data direct access / Variable array feature support in description | [v1.5.1](#v151-2026-01-21) |
| v1.5.0  | 2026-01-09   | Result type / Typer CLI + validate / Timestamped logs / Lazy imports / Python 3.14 | [v1.5.0](#v150-2026-01-09) |
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

## v1.5.2 (2026-01-27)

!!! info "References"
    - Key issues: [#358](https://github.com/nims-mdpf/rdetoolkit/issues/358), [#359](https://github.com/nims-mdpf/rdetoolkit/issues/359), [#360](https://github.com/nims-mdpf/rdetoolkit/issues/360), [#361](https://github.com/nims-mdpf/rdetoolkit/issues/361), [#362](https://github.com/nims-mdpf/rdetoolkit/issues/362), [#370](https://github.com/nims-mdpf/rdetoolkit/issues/370), [#372](https://github.com/nims-mdpf/rdetoolkit/issues/372), [#373](https://github.com/nims-mdpf/rdetoolkit/issues/373), [#381](https://github.com/nims-mdpf/rdetoolkit/issues/381), [#382](https://github.com/nims-mdpf/rdetoolkit/issues/382)

#### Highlights
- Standardized CLI `validate` command exit codes (0/1/2) for CI/CD pipeline integration
- Fixed `metadata-def.json` validation to use correct Pydantic model (`MetadataDefinitionValidator`)
- Improved configuration error messages with detailed context (file path, line/column info, documentation links)
- Added Python 3.9 deprecation warning with v2.0 removal timeline
- Introduced Hypothesis Property-Based Testing (PBT) infrastructure with 75 tests across 5 modules

---

### CLI Validate Exit Code Standardization (Issue #362, #381)

#### Enhancements
- **Standardized Exit Codes**: Implemented consistent exit codes for CI/CD integration:
  - Exit code 0: All validations passed (success)
  - Exit code 1: Validation failures (data/schema issues)
  - Exit code 2: Usage/configuration errors (invalid arguments, missing files)
- **Bug Fix**: Fixed `typer.Exit` being incorrectly caught by generic `except Exception` handler, which caused spurious "Internal error during validation:" messages
- **CLI Help Update**: Added exit code documentation to all validate subcommand docstrings
- **User Documentation**: Added CI/CD integration examples for GitHub Actions, GitLab CI, and shell scripts

#### Usage Examples

```bash
# CI/CD pipeline example
rdetoolkit validate --all ./data

if [ $? -eq 0 ]; then
    echo "Validation passed"
elif [ $? -eq 1 ]; then
    echo "Validation failed - check output for details"
    exit 1
elif [ $? -eq 2 ]; then
    echo "Command error - check arguments"
    exit 2
fi
```

---

### Metadata Definition Validation Fix (Issue #382)

#### Enhancements
- **New Pydantic Models**: Added `MetadataDefEntry` and `MetadataDefinition` models for proper `metadata-def.json` schema validation
  - Required fields: `name.ja`, `name.en`, `schema.type`
  - Optional fields: `unit`, `description`, `uri`, `mode`, `order`, `originalName`
  - `extra="allow"` to ignore undefined fields (e.g., `variable`)
- **New Validator**: Added `MetadataDefinitionValidator` class for metadata definition file validation
- **CLI Fix**: Updated `MetadataDefCommand` to use `MetadataDefinitionValidator` instead of the incorrect `MetadataValidator`

---

### Configuration Error Message Improvements (Issue #361)

#### Enhancements
- **ConfigError Exception**: New custom exception class with comprehensive error information:
  - File path that failed to load
  - Line/column information for parse errors (when available)
  - Field name and validation reason for schema errors
  - Documentation link for resolution guidance
- **File Not Found**: Clear error messages with `gen-config` command guidance
- **Parse Errors**: YAML/TOML syntax errors now include line/column information
- **Validation Errors**: Pydantic validation errors show specific field names and valid values

#### Example Error Messages

```python
# File not found
ConfigError: Configuration file not found: '/path/to/rdeconfig.yaml'.
Create a configuration file or use 'rdetoolkit gen-config' to generate one.
See: https://nims-mdpf.github.io/rdetoolkit/usage/config/config/

# Parse error with line info
ConfigError: Failed to parse '/path/to/rdeconfig.yaml': invalid YAML syntax at line 15.

# Schema validation error
ConfigError: Invalid configuration in '/path/to/rdeconfig.yaml':
'extended_mode' must be one of ['MultiDataTile', 'RDEFormat'].
```

---

### Python 3.9 Deprecation Warning (Issue #360)

#### Enhancements
- **DeprecationWarning**: Added warning when rdetoolkit is imported under Python 3.9
- **Clear Timeline**: Warning message indicates support removal in v2.0
- **Session-Safe**: Warning appears only once per session to avoid noise
- **Documentation**: Updated README, CHANGELOG, and installation docs (English/Japanese) with deprecation notices

#### Warning Message

```
DeprecationWarning: Python 3.9 support is deprecated and will be removed in rdetoolkit v2.0.
Please upgrade to Python 3.10 or later.
```

---

### Property-Based Testing Infrastructure (Issue #372)

#### Enhancements
- **Hypothesis Library**: Added `hypothesis>=6.102.0` to dev dependencies
- **Test Directory**: Created `tests/property/` with shared strategies and profile configuration
- **75 PBT Tests** across 5 modules:
  - `graph.normalizers` (14 tests): Column normalization and validation
  - `graph.textutils` (20 tests): Filename sanitization, text transformations
  - `graph.io.path_validator` (13 tests): Path safety validation
  - `rde2util.castval` (15 tests): Type casting and error handling
  - `validation` (10 tests): Invoice validation invariants
- **CI Integration**: Added `HYPOTHESIS_PROFILE: ci` environment variable for optimized CI execution
- **Tox Integration**: Added `passenv = HYPOTHESIS_PROFILE` to all tox environments

#### Running PBT Tests

```bash
# Run all tests (example-based + property-based)
tox -e py312-module

# Run only property-based tests
pytest tests/property/ -v -m property

# Run with CI profile (faster, fewer examples)
HYPOTHESIS_PROFILE=ci pytest tests/property/ -v -m property
```

---

### Workflow Documentation Alignment (Issue #370)

#### Enhancements
- **Docstring Update**: Aligned `workflows.run` Note section with actual implementation
- **Mode Selection**: Documented real mode precedence and allowed `extended_mode` values
- **New Tests**: Added EP/BV tables and unit tests for `_process_mode` covering priority order and failure handling

---

### Documentation Fixes (Issue #358, #359)

#### Fixes
- **Badge URLs**: Updated README badges (release, license, issue tracking, workflow) from `nims-dpfc` to `nims-mdpf` organization
- **Typo Fix**: Corrected `display_messsage` to `display_message` in README and Japanese documentation

---

### Dependency Fix (Issue #373)

#### Fixes
- **pytz Dependency**: Added `pytz>=2024.1` to runtime dependencies to fix CI failures
  - Root cause: pandas 2.2 removed its pytz dependency, but `archive.py` and tests still import pytz directly
  - Resolution: Explicit pytz dependency in `pyproject.toml` and regenerated lock files

---

### Migration / Compatibility

#### CLI Validate Exit Codes
- **Exit code change**: Internal errors now return exit code 2 (was 3) for consistency
- **CI scripts**: Update any scripts checking for exit code 3 to check for exit code 2

#### Metadata Definition Validation
- **Backward Compatible**: Existing valid `metadata-def.json` files will now validate correctly
- **Error messages**: More accurate error messages for invalid metadata definitions

#### Python 3.9
- **Deprecation only**: Python 3.9 continues to work but shows deprecation warning
- **Action required**: Plan upgrade to Python 3.10+ before rdetoolkit v2.0

#### Configuration Errors
- **Backward Compatible**: ConfigError is a new exception type; existing error handling continues to work
- **Enhanced debugging**: More informative error messages for configuration issues

---

#### Known Issues
- None reported at this time.

---

## v1.5.1 (2026-01-21)

!!! info "References"
    - Key issues: [#207](https://github.com/nims-mdpf/rdetoolkit/issues/207), [#210](https://github.com/nims-mdpf/rdetoolkit/issues/210)

#### Highlights
- Added `smarttable_row_data` property to `RdeDatasetPaths` for direct row data access in SmartTable mode, eliminating the need for users to manually read and parse CSV files
- Feature-flagged items from `variable` array in `metadata.json` are now transcribed to description in array format (`[A,B,C]`)
- Added `feature_description` configuration flag to enable/disable automatic feature transcription to description

---

### SmartTable Row Data Direct Access (Issue #207)

#### Enhancements
- **New Attribute**: Added `smarttable_row_data: dict[str, Any] | None` to `RdeOutputResourcePath` dataclass
- **New Property**: Added `smarttable_row_data` property to `RdeDatasetPaths` for user callback access
- **Processor Update**: Modified `SmartTableInvoiceInitializer` to parse CSV and store row data in context
- **Type Stubs**: Updated `.pyi` files for IDE autocomplete support
- **Comprehensive Tests**: Added unit tests and integration tests covering new and legacy signatures

#### Usage Examples

**Before (existing method still works):**
```python
def custom_dataset(paths: RdeDatasetPaths):
    csv_path = paths.smarttable_rowfile
    if csv_path:
        df = pd.read_csv(csv_path)
        sample_name = df.iloc[0]["sample/name"]
```

**After (new improved API):**
```python
def custom_dataset(paths: RdeDatasetPaths):
    row_data = paths.smarttable_row_data  # dict[str, Any] | None
    if row_data:
        sample_name = row_data.get("sample/name")
```

---

### Variable Array Feature Support in Description (Issue #210)

#### Enhancements
- **New Helper Function**: `__collect_values_from_variable` collects all values for a specified key from the `variable` array
- **New Helper Function**: `__format_description_entry` centralizes formatting logic (DRY principle)
- **Extended Function**: `update_description_with_features` now supports variable array lookup
  - `constant` values take priority over `variable` values (backward compatible)
  - Multiple values formatted as `[A,B,C]`, single value remains unchanged
- **New Config Flag**: Added `feature_description` boolean to `SystemSettings`
  - Default: `True` (backward compatible)
  - Controls automatic feature transcription to description
  - Configurable via `rdeconfig.yaml` or `pyproject.toml`

#### Configuration Examples

**rdeconfig.yaml:**
```yaml
system:
  feature_description: false  # Disable auto-transfer to description
```

**pyproject.toml:**
```toml
[tool.rdetoolkit.system]
feature_description = false
```

---

### Migration / Compatibility

#### SmartTable Row Data Access
- **Backward Compatible**: Existing `smarttable_rowfile` path access continues to work
- **Gradual Migration**: Both old (file path) and new (dict) approaches can coexist
- **Non-SmartTable Modes**: `smarttable_row_data` returns `None` in non-SmartTable modes

#### Variable Array Feature Support
- **Backward Compatible**: Existing constant-only feature behavior unchanged
- **Priority Rules**: `constant` values always take precedence over `variable` values
- **Config Default**: `feature_description` defaults to `True`, preserving existing behavior
- **Opt-out Available**: Set `feature_description: false` to disable automatic transcription

---

#### Known Issues
- None reported at this time.

---

## v1.5.0 (2026-01-09)

!!! info "References"
    - Key issues: [#3](https://github.com/nims-mdpf/rdetoolkit/issues/3), [#247](https://github.com/nims-mdpf/rdetoolkit/issues/247), [#249](https://github.com/nims-mdpf/rdetoolkit/issues/249), [#262](https://github.com/nims-mdpf/rdetoolkit/issues/262), [#301](https://github.com/nims-mdpf/rdetoolkit/issues/301), [#323](https://github.com/nims-mdpf/rdetoolkit/issues/323), [#324](https://github.com/nims-mdpf/rdetoolkit/issues/324), [#325](https://github.com/nims-mdpf/rdetoolkit/issues/325), [#326](https://github.com/nims-mdpf/rdetoolkit/issues/326), [#327](https://github.com/nims-mdpf/rdetoolkit/issues/327), [#328](https://github.com/nims-mdpf/rdetoolkit/issues/328), [#329](https://github.com/nims-mdpf/rdetoolkit/issues/329), [#330](https://github.com/nims-mdpf/rdetoolkit/issues/330), [#333](https://github.com/nims-mdpf/rdetoolkit/issues/333), [#334](https://github.com/nims-mdpf/rdetoolkit/issues/334), [#335](https://github.com/nims-mdpf/rdetoolkit/issues/335), [#336](https://github.com/nims-mdpf/rdetoolkit/issues/336), [#337](https://github.com/nims-mdpf/rdetoolkit/issues/337), [#338](https://github.com/nims-mdpf/rdetoolkit/issues/338), [#341](https://github.com/nims-mdpf/rdetoolkit/issues/341)

#### Highlights
- Introduced Result type pattern (`Result[T, E]`) for explicit, type-safe error handling without exceptions
- System logs now use timestamped filenames (`rdesys_YYYYMMDD_HHMMSS.log`) instead of static `rdesys.log`, enabling per-run log management and preventing log collision in concurrent or successive executions
- CLI modernized with Typer, adding `validate` subcommands, `rdetoolkit run`, and init template path options while preserving `python -m rdetoolkit` compatibility
- Lazy imports across core, workflow, CLI, and graph stacks reduce startup overhead and defer heavy dependencies until needed
- Added optional structured `invoice.json` export, expanded Magic Variables, and official Python 3.14 support

---

### Result Type Pattern (Issue #334)

#### Enhancements
- **New Result Module** (`rdetoolkit.result`):
  - `Success[T]`: Immutable frozen dataclass for successful results with value
  - `Failure[E]`: Immutable frozen dataclass for failed results with error
  - `Result[T, E]`: Type alias for `Success[T] | Failure[E]`
  - `try_result` decorator: Converts exception-based functions to Result-returning functions
  - Full generic type support with `TypeVar` and `ParamSpec` for type safety
  - Functional methods: `is_success()`, `map()`, `unwrap()`
- **Result-based Workflow Functions**:
  - `check_files_result()`: File classification with explicit Result type
  - Returns `Result[tuple[RawFiles, Path | None, Path | None], StructuredError]`
- **Result-based Mode Processing Functions**:
  - `invoice_mode_process_result()`: Invoice processing with Result type
  - Returns `Result[WorkflowExecutionStatus, Exception]`
- **Type Stubs**: Complete `.pyi` files for IDE autocomplete and type checking
- **Documentation**: Comprehensive API docs in English and Japanese (`docs/api/result.en.md`, `docs/api/result.ja.md`)
- **Public API**: Result types exported from `rdetoolkit.__init__.py` for easy import
- **100% Test Coverage**: 40 comprehensive unit tests for Result module

#### Usage Examples

**Result-based error handling:**
```python
from rdetoolkit.workflows import check_files_result

result = check_files_result(srcpaths, mode="invoice")
if result.is_success():
    raw_files, excel_path, smarttable_path = result.unwrap()
    # Process files
else:
    error = result.error
    print(f"Error {error.ecode}: {error.emsg}")
```

**Traditional exception-based (still works):**
```python
from rdetoolkit.workflows import check_files

try:
    raw_files, excel_path, smarttable_path = check_files(srcpaths, mode="invoice")
except StructuredError as e:
    print(f"Error {e.ecode}: {e.emsg}")
```

---

### Timestamped Log Filenames (Issue #341)

#### Enhancements
- Added `generate_log_timestamp()` utility function to create filesystem-safe timestamp strings
- Modified `workflows.run()` to generate unique timestamped log files for each workflow execution
- Fixed P2 bug: Handler accumulation when `run()` called multiple times in the same process
  - Root cause: Logger singleton retained old LazyFileHandlers with different filenames
  - Solution: Clear existing LazyFileHandlers before adding new ones
  - Impact: Ensures 1 execution = 1 log file, preventing log cross-contamination
- Replaced custom `LazyFileHandler` with standard `logging.FileHandler(delay=True)` for better maintainability
- Updated all documentation to reference the new timestamped log filename pattern

#### Benefits
- **Per-run isolation**: Each workflow execution creates a separate log file, preventing log mixing
- **Concurrent execution**: No log collision when running multiple workflows simultaneously
- **Easy comparison**: Compare logs from different runs without manual separation
- **Simplified auditing**: Collect and archive logs per execution for debugging and compliance
- **Better maintainability**: Standard library FileHandler is well-tested and widely understood

---

### CLI Modernization and Validation (Issues #247, #262, #337, #338)

#### Enhancements
- Migrated CLI to Typer with lazy imports; preserved `python -m rdetoolkit` invocation and command names (`init`, `version`, `gen-config`, `make-excelinvoice`, `artifact`, `csv2graph`)
- Added `rdetoolkit run <module_or_file::attr>` to load a function dynamically, reject classes/callables, and ensure the function accepts two positional arguments
- Added `rdetoolkit validate` commands (`invoice-schema`, `invoice`, `metadata-def`, `metadata`, `all`) with `--format text|json`, `--quiet`, `--strict/--no-strict`, and CI-friendly exit codes (0/1/2/3)
- Added init template path options (`--entry-point`, `--modules`, `--tasksupport`, `--inputdata`, `--other`) and persist them to `pyproject.toml` / `rdeconfig.yaml`

#### Init Template Path Options Details (Issue #262)

Added template path options to `rdetoolkit init` command, enabling project initialization from custom templates.

**Use Cases**:

- Initialize with commonly used utility files pre-placed in `modules/` folder
- Customize `main.py` to preferred format
- Include frequently used config files as templates
- Specify custom object-oriented script templates

**Added Options**:

- `--entry-point`: Place entry point (.py file) in container/ directory
- `--modules`: Place modules in container/modules/ directory (folder specification includes subdirectories)
- `--tasksupport`: Place config files in tasksupport/ directory (folder specification includes subdirectories)
- `--inputdata`: Place input data in container/data/inputdata/ directory (folder specification includes subdirectories)
- `--other`: Place other files in container/ directory (folder specification includes subdirectories)

**Config Persistence**:

- CLI-specified paths are automatically saved to `pyproject.toml` or `rdeconfig.yaml(yml)`
- Auto-generates `pyproject.toml` if no config file exists
- Overwrites existing settings when present

**Safety Measures**:

- Self-copy (same path) detection and skip
- Invalid path and empty string validation with error reporting

**Config File Example** (`pyproject.toml`):
```toml
[tool.rdetoolkit.init]
entry_point = "path/to/your/template/main.py"
modules = "path/to/your/template/modules/"
tasksupport = "path/to/your/template/config/"
inputdata = "path/to/your/template/inputdata/"
other = [
    "path/to/your/template/file1.txt",
    "path/to/your/template/dir2/"
]
```

**Config File Example** (`rdeconfig.yaml`):
```yaml
init:
  entry_point: "path/to/your/template/main.py"
  modules: "path/to/your/template/modules/"
  tasksupport: "path/to/your/template/config/"
  inputdata: "path/to/your/template/inputdata/"
  other:
    - "path/to/your/template/file1.txt"
    - "path/to/your/template/dir2/"
```

---

### Startup Performance Improvements (Issues #323-330)

#### Enhancements
- Implemented lazy exports in `rdetoolkit` and `rdetoolkit.graph` to avoid importing heavy submodules until needed
- Deferred heavy dependencies in invoice/validation/encoding, core utilities, workflows, CLI commands, and graph renderers
- Updated Ruff per-file ignores to allow intentional `PLC0415` in lazy-import modules

---

### Type Safety and Refactors (Issues #333, #335, #336)

#### Enhancements
- Replaced `models.rde2types` aliases with NewType definitions and validated path classes; added `FileGroup` / `ProcessedFileGroup` for safer file grouping
- Broadened read-only inputs to `Mapping` and mutable inputs to `MutableMapping`, including `Validator.validate()` accepting `Mapping` and normalizing to `dict`
- Replaced if/elif chains with dispatch tables for `rde2util.castval`, invoice sheet processing, and archive format selection, preserving behavior with new tests

---

### Workflow and Config Enhancements (Issues #3, #301)

#### Enhancements
- Added `system.save_invoice_to_structured` (default `false`) and `StructuredInvoiceSaver` to optionally copy `invoice.json` into the `structured` directory after thumbnail generation
- Expanded Magic Variable patterns: `${invoice:basic:*}`, `${invoice:custom:*}`, `${invoice:sample:names:*}`, `${metadata:constant:*}`, with warnings on skipped values and strict validation for missing fields

---

### Tooling and Platform Support (Issue #249)

#### Enhancements
- Added official Python 3.14 support across classifiers, tox environments, and CI build/test matrices

---

### Migration / Compatibility

#### Result Type Pattern
- **Backward Compatible**: All original exception-based functions remain unchanged
- **Gradual Migration**: Both patterns (exception-based and Result-based) can coexist
- **Delegation Pattern**: Original functions delegate to `*_result()` versions internally
- **Type Safety**: Use `isinstance(result, Failure)` for type-safe error checking
- **Error Preservation**: All error information (StructuredError attributes, Exception details) preserved in Failure

#### Timestamped Log Filenames
- **Log file naming change**: System logs are now written to `data/logs/rdesys_YYYYMMDD_HHMMSS.log` instead of `data/logs/rdesys.log`
- **Finding logs**: Use wildcard patterns to find logs: `ls -t data/logs/rdesys_*.log | head -1` for the latest log
- **Scripts and tools**: Update any scripts or monitoring tools that directly reference `rdesys.log` to use pattern matching with `rdesys_*.log`
- **Log collection**: Automated log collection systems should be updated to handle multiple timestamped files instead of a single static file
- **Old log files**: Existing `rdesys.log` files from previous versions will remain in place and are not automatically removed
- **No configuration needed**: The new behavior is automatic; no configuration changes are required

#### CLI (Typer Migration and New Commands)
- **Invocation unchanged**: `python -m rdetoolkit ...` continues to work; command names and options are preserved
- **Dependency update**: Click is removed in favor of Typer; avoid importing Click-specific objects from `rdetoolkit.cli`
- **Validation commands**: New `rdetoolkit validate` subcommands return exit codes 0/1/2/3 for CI automation

#### Init Template Paths
- **Config persistence**: Template paths are stored in `pyproject.toml` / `rdeconfig.yaml` when provided; existing configs remain valid

#### Structured Invoice Export
- **Opt-in behavior**: `system.save_invoice_to_structured` defaults to `false`; enabling it creates `structured/invoice.json` after thumbnail generation

#### Magic Variables
- **Expanded patterns**: `${invoice:basic:*}`, `${invoice:custom:*}`, `${invoice:sample:names:*}`, `${metadata:constant:*}` are now supported
- **Error handling**: Missing required fields raise errors; empty segments are skipped with warnings to avoid double underscores

#### Mapping Type Hints
- **Type-only change**: `Mapping` / `MutableMapping` widen input types without changing runtime behavior
- **Validation inputs**: `Validator.validate(obj=...)` now copies mappings into a `dict` at the boundary

#### Python 3.14 Support
- **Compatibility**: Python 3.14 is now a supported runtime with CI and packaging updates

---

#### Known Issues
- Only `invoice_mode_process` has Result-based version; other mode processors will be migrated in future releases

---

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
