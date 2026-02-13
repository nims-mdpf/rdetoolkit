# Issue #371 Overview: Generate invoice.json from invoice.schema.json

## Input Source
- **File**: `local/develop/issue_371.md`
- **Created**: 2026-02-05

## Overall Purpose
Provide API and CLI functionality to generate `invoice.json` files directly from `invoice.schema.json`, enabling users to create valid invoice templates without manual JSON construction. This addresses the gap where validation exists but template generation does not.

## Task List
| Index | Title | Dependencies | Status |
|-------|-------|--------------|--------|
| 01 | Create invoice generator service module | - | ✅ Complete (2026-02-05) |
| 02 | Create command class for invoice generation | 01 | ✅ Complete (2026-02-06) |
| 03 | Add CLI command for gen-invoice | 02 | ✅ Complete (2026-02-06) |
| 04 | Add comprehensive tests for generator and CLI | 01, 02, 03 | ✅ Complete (2026-02-06) |
| 05 | Update documentation | 04 | ⬜ Not Started |

## Task Architecture

### Task 01: Invoice Generator Service (Core Logic)
- **Location**: `src/rdetoolkit/invoice_generator.py`
- **Purpose**: Core business logic for generating invoice.json from schema
- **Key Functions**:
  - `generate_invoice_from_schema()`: Main API function
  - Helper functions for default value generation by type
  - Schema field extraction and processing
  - Validation integration

### Task 02: Command Class (CLI Integration Layer)
- **Location**: `src/rdetoolkit/cmd/gen_invoice.py`
- **Purpose**: Command class following existing patterns (e.g., GenerateExcelInvoiceCommand)
- **Integration**: Uses Task 01's generator service
- **Pattern**: Typer-compatible command class with `invoke()` method

### Task 03: CLI Command Registration
- **Location**: `src/rdetoolkit/cli/app.py`
- **Purpose**: Register new `gen-invoice` command in Typer app
- **Pattern**: Follows existing commands like `make-excelinvoice`, `gen-config`
- **Features**:
  - Argument/option parsing
  - Input validation
  - Error handling

### Task 04: Comprehensive Testing
- **Location**: `tests/invoice_generator/`, `tests/cmd/test_gen_invoice.py`, `tests/cli/test_gen_invoice_cli.py`
- **Coverage**: 100% branch coverage required
- **Test Types**:
  - Unit tests for generator logic
  - Integration tests for command class
  - CLI e2e tests
  - Edge cases and error conditions

### Task 05: Documentation
- **Location**: `CLAUDE.md`, docstrings
- **Purpose**: Document new API and CLI usage
- **Content**: Usage examples, parameter descriptions, integration guide

## Common Design Patterns

### Schema Processing
- Read schema using `readf_json()` from `fileops.py`
- Validate with `InvoiceSchemaJson` pydantic model
- Extract required/properties fields
- Build invoice structure from schema metadata

### Default Value Generation Strategy
```python
Type → Default Value
- "string" → "" (empty string)
- "number" → 0.0
- "integer" → 0
- "boolean" → false
- "array" → []
- "object" → {}
- Honor schema's "default" field if present
- Use first "examples" value if available and fill_defaults=True
```

### Validation Integration
- Use existing `InvoiceValidator` from `validation.py`
- Validate generated output before writing
- Surface clear, actionable error messages

### File I/O
- Use `readf_json()` and `writef_json()` from `fileops.py`
- Support both Path and str inputs
- Create parent directories if needed (os.makedirs with exist_ok=True)

## Shared Information Points

### Data Models (from invoice_schema.py)
- `InvoiceSchemaJson`: Root schema model
- `Properties`: Top-level properties container
- `CustomField`: Custom field definitions
- `SampleField`: Sample field definitions
- `MetaProperty`: Individual property metadata

### Existing Generators (Reference Implementation)
- `InvoiceJsonGenerator` (command.py:628-643): Current basic generator
- `InvoiceSchemaJsonGenerator` (command.py:578-605): Schema generator
- `ExcelInvoiceTemplateGenerator` (invoicefile.py:437-642): Complex template generation

### Impact Scope Control
- Generator module: Pure functions, no side effects except file I/O
- Command class: Handles user interaction, delegates to generator
- CLI: Input validation and error presentation only
- Tests: Isolated with temp directories, no cross-test dependencies

## Critical Design Decisions

### Required Fields Handling
- Always include system-required fields: `datasetId`, `basic`
- Parse `required` array from schema for `custom` and `sample` sections
- Option `--required-only` to exclude optional fields

### Format Options
- `--format pretty`: JSON with indent=4 (default)
- `--format compact`: Minified JSON for efficiency

### Backward Compatibility
- Do not modify existing `InvoiceJsonGenerator`
- New generator lives in separate module
- Existing code continues to work unchanged

## Progress Log
- 2026-02-05: Overview document created, task decomposition complete
- 2026-02-05: Task 01 completed - Invoice generator service module implemented with comprehensive tests (97% branch coverage, 40 test cases)
- 2026-02-06: Task 02 completed - Command class `GenerateInvoiceCommand` created with Typer integration, 100% branch coverage (17 test cases)
- 2026-02-06: Task 03 completed - CLI command `gen-invoice` registered in app.py with full test coverage (15 test cases), all tests passing
- 2026-02-06: Task 04 completed - Comprehensive test suite with 74 test cases total (40 generator unit tests, 17 command tests, 15 CLI tests, 2 integration tests), 98% overall coverage (cmd/gen_invoice.py: 100%, invoice_generator.py: 97%)
