# Issue #364 Overview: Refactor invoicefile.py for SRP Compliance

## Input Source
- **File**: `local/develop/issue_364.md`
- **Created**: 2026-02-05

## Overall Purpose

Refactor the monolithic `src/rdetoolkit/invoicefile.py` (1702 lines) into a modular package structure while maintaining **complete backward compatibility** of all public imports. The file currently violates the Single Responsibility Principle (SRP) by bundling multiple concerns: invoice file handling, Excel processing, template generation, magic variable resolution, rule-based replacement, and SmartTable processing.

## Key Constraints

1. **Backward Compatibility**: All existing import paths must continue to work unchanged:
   - `from rdetoolkit.invoicefile import <any_public_name>`
2. **No Functional Changes**: Pure structural refactoring only
3. **Test Coverage**: Maintain 100% branch coverage
4. **Type Safety**: Pass strict mypy checks
5. **Code Quality**: Pass ruff checks and Google Style docstring requirements

## Current External Import Dependencies

From **src/** (production code):
- `backup_invoice_json_files`
- `InvoiceFile`
- `apply_magic_variable`
- `ExcelInvoiceFile`
- `update_description_with_features`
- `check_exist_rawfiles`
- `SmartTableFile`
- `apply_default_filename_mapping_rule`

From **tests/**:
- All above + internal functions: `_identify_sheet_type`, `_SHEET_PROCESSORS`, `_process_invoice_sheet`, `_process_general_term_sheet`, `_process_specific_term_sheet`
- `ExcelInvoiceTemplateGenerator`

## Proposed Module Structure

Create package: `src/rdetoolkit/invoicefile/`

| Module | Responsibility | Public Exports | Lines Est. |
|--------|---------------|----------------|------------|
| `_helpers.py` | Lazy import helpers, shared constants | STATIC_DIR, EX_GENERALTERM, EX_SPECIFICTERM, MAGIC_VARIABLE_PATTERN, logger, _ensure_* functions | ~70 |
| `_sheet_processing.py` | Excel sheet type identification and processing | SheetType, _identify_sheet_type, _process_invoice_sheet, _process_general_term_sheet, _process_specific_term_sheet, _SHEET_PROCESSORS, check_exist_rawfiles, check_exist_rawfiles_for_folder | ~180 |
| `_invoice.py` | JSON invoice file CRUD operations | InvoiceFile, _assign_invoice_val, overwrite_invoicefile_for_dpfterm | ~180 |
| `_template.py` | Template generation for Excel invoices | TemplateGenerator, ExcelInvoiceTemplateGenerator | ~250 |
| `_excelinvoice.py` | Excel invoice file handling | ExcelInvoiceFile, read_excelinvoice (deprecated) | ~280 |
| `_description.py` | Description field updates with metadata | update_description_with_features, __collect_values_from_variable, __serch_key_from_constant_variable_obj, __format_description_entry | ~120 |
| `_rule_replacer.py` | Rule-based filename mapping | RuleBasedReplacer, apply_default_filename_mapping_rule | ~170 |
| `_magic_variable.py` | Magic variable expansion | MagicVariableResolver, apply_magic_variable, _load_metadata | ~200 |
| `_smarttable.py` | SmartTable file handling | SmartTableFile | ~180 |
| `__init__.py` | Backward compatibility re-exports | ALL public API | ~50 |

## Task List

| Index | Title | Dependencies | Status | Files |
|-------|-------|--------------|--------|-------|
| 01 | Create package structure and helpers module | - | ✅ Complete | 2 |
| 02 | Extract sheet processing functions | 01 | ✅ Complete | 3 |
| 03 | Extract InvoiceFile class | 01 | ✅ Complete | 3 |
| 04 | Extract template generation classes | 01, 02 | ✅ Complete | 3 |
| 05 | Extract ExcelInvoiceFile class | 01, 02, 04 | ✅ Complete | 3 |
| 06 | Extract description update functions | 01 | ✅ Complete | 3 |
| 07 | Extract rule replacer classes | 01 | ✅ Complete | 3 |
| 08 | Extract magic variable resolution | 01, 06 | ✅ Complete | 3 |
| 09 | Extract SmartTableFile class | 01 | ✅ Complete | 3 |
| 10 | Create backward compatibility layer | 02-09 | ⬜ Not Started | 2 |
| 11 | Remove original invoicefile.py | 10 | ⬜ Not Started | 1 |

## Overall Design Notes

### Dependency Graph
```
_helpers.py (foundation)
    ├── _sheet_processing.py
    ├── _invoice.py
    ├── _template.py (uses _sheet_processing via constants)
    ├── _description.py
    ├── _rule_replacer.py
    ├── _magic_variable.py (uses _description indirectly)
    └── _smarttable.py

_excelinvoice.py (uses _sheet_processing, _template)

__init__.py (imports all modules for re-export)
```

### Common Processing Strategy

Each task follows this pattern:
1. Create new module file with extracted code
2. Update imports to reference new module locations
3. Add module to `__init__.py` re-exports
4. Run tests to verify backward compatibility
5. Verify type hints and linting pass

### Testing Strategy

- Existing tests in `tests/test_invoicefile.py` should pass **unchanged**
- Tests that import internal functions (`_identify_sheet_type`, etc.) will still work via `__init__.py` re-exports
- No new tests required (pure refactoring)
- Each task must end with all tests passing

### Risk Mitigation

- **Circular Dependencies**: Extract in dependency order (helpers first, composition last)
- **Import Errors**: `__init__.py` will re-export everything, maintaining original namespace
- **Test Breakage**: Each commit verified with full test suite
- **Type Errors**: All modules maintain existing type annotations

## Progress Log

- 2026-02-05: Overview document created, task decomposition complete
- 2026-02-05: Task 01 completed - Created package structure and _helpers.py with all helper functions and constants extracted
- 2026-02-06: Task 02 completed - Extracted sheet processing functions to _sheet_processing.py
- 2026-02-06: Task 03 completed - Extracted InvoiceFile class to _invoice.py
- 2026-02-06: Task 04 completed - Extracted template generation to _template.py
- 2026-02-06: Task 05 completed - Extracted ExcelInvoiceFile class to _excelinvoice.py with all stub files created
- 2026-02-06: Task 06 completed - Extracted description update functions to _description.py
- 2026-02-06: Task 07 completed - Extracted rule replacer to _rule_replacer.py
- 2026-02-06: Task 08 completed - Extracted magic variable resolution to _magic_variable.py
- 2026-02-06: Task 09 completed - Extracted SmartTableFile class to _smarttable.py
