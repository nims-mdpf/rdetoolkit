# Issue #361 Overview: Configuration File Error Message Improvement

## Input Source
- **File**: `local/develop/issue_361.md`
- **Issue**: #361
- **Created**: 2026-01-26

## Overall Purpose
Improve error messages when configuration file loading fails (`rdeconfig.yaml` or `pyproject.toml`) to provide specific information about:
1. File paths involved in the failure
2. Specific failure reasons (file not found, parse error, schema validation error)
3. Line/column information for parse errors (when available)
4. Field-specific validation errors with explanations
5. Documentation links for all error messages

## Current Implementation Analysis

### Configuration Loading Flow
1. **Entry Points**:
   - `parse_config_file(path=None)` - Main parser for YAML/TOML files
   - `get_config(target_dir_path)` - Searches for config files in directory
   - `load_config(tasksupport_path, config=None)` - Top-level loader

2. **Error Handling Locations** (src/rdetoolkit/config.py):
   - Line 164-166: Generic ValidationError handling in `get_config()`
   - Line 174-176: Generic ValidationError handling for pyproject.toml
   - No specific handling for file not found, parse errors, or YAML syntax errors
   - Returns empty/default Config objects on failures instead of raising informative errors

3. **Current Issues**:
   - Generic error messages without file paths
   - No line/column information for YAML parse errors
   - ValidationError from pydantic not properly translated to user-friendly messages
   - No documentation links in error messages
   - Silent failures (returns default Config instead of raising errors)

## Task List

| Index | Title | Dependencies | Status | File Count |
|-------|-------|--------------|--------|------------|
| 01 | Create custom exception class for config errors | - | ✅ Complete | 2 files |
| 02 | Improve file not found error handling | 01 | ✅ Complete | 2 files |
| 03 | Add YAML/TOML parse error handling with line info | 01 | ✅ Complete | 2 files |
| 04 | Improve pydantic validation error messages | 01 | ✅ Complete | 2 files |
| 05 | Add comprehensive unit tests for error scenarios | 01-04 | ✅ Complete | 1 file |

## Task Decomposition Strategy

### File Count Guidelines Applied
- **Task 01**: 2 files (new exception class + stub file) - Small task
- **Task 02**: 2 files (config.py + test file) - Small task
- **Task 03**: 2 files (config.py + test file) - Small task
- **Task 04**: 2 files (config.py + test file) - Small task
- **Task 05**: 1 file (test file only) - Small task, consolidates all error scenarios

### Optimization Considerations
1. **Common Processing**:
   - Custom exception class (Task 01) is used by all subsequent tasks
   - Documentation URL constant defined once in Task 01
   - Error message formatting patterns established in Task 01

2. **Impact Scope**:
   - Primary file: `src/rdetoolkit/config.py`
   - New file: `src/rdetoolkit/exceptions/config.py` (or add to existing exceptions)
   - Test file: `tests/test_config.py` (extend existing)
   - Type stub files: `.pyi` files for type safety

3. **Information Sharing**:
   - All tasks share the custom exception class
   - Error message format follows consistent pattern
   - Documentation URL is centralized
   - Each task builds on previous error handling infrastructure

## Progress Log
- 2026-01-26: Overview document created, task decomposition complete
- 2026-01-26 15:30: **Task 01 Complete** - ConfigError exception class created
  - Added ConfigError class to `src/rdetoolkit/exceptions.py`
  - Added type stub to `src/rdetoolkit/exceptions.pyi`
  - All attributes implemented: message, file_path, error_type, line_number, column_number, field_name, doc_url
  - Error message formatting includes file path, location info, and documentation link
  - Passed mypy type checking and ruff linting
  - Functionality verified with manual tests
- 2026-01-26 16:00: **Task 02 Complete** - File not found error handling improved
  - Added file existence checks in `parse_config_file()` and `__read_pyproject_toml()`
  - Added directory existence check in `get_config()`
  - All checks raise ConfigError with detailed messages and documentation links
  - Added 3 unit tests for file/directory not found scenarios
  - All tests pass, mypy and ruff clean
- 2026-01-26 16:30: **Task 03 Complete** - YAML/TOML parse error handling with line info
  - Added YAMLError exception handling in `parse_config_file()` with line/column extraction
  - Added TOMLKitError exception handling in `__read_pyproject_toml()` with line extraction
  - I/O errors (OSError) handled separately from parse errors
  - All error messages include file path, error type, and line/column info when available
  - Added 3 unit tests: YAML syntax error, TOML syntax error, I/O error
  - All tests pass, mypy clean
  - Note: 2 ruff warnings (C901, PLR0912) for function complexity - pre-existing, not introduced by this task
- 2026-01-26 17:00: **Task 04 Complete** - Pydantic validation error messages improved
  - Added `_format_validation_error()` helper function to format ValidationError into ConfigError
  - Modified `parse_config_file()` to catch ValidationError and use helper for formatting
  - Modified `get_config()` to use helper for validation errors
  - Error messages now include field name, validation reason, provided value, and valid values for enums
  - Multiple validation errors are acknowledged in the message
  - Added 5 unit tests: invalid extended_mode, invalid field type, get_config validation, traceback format, multiple errors
  - All new tests pass (5/5), mypy clean, ruff EM102 errors fixed
  - Note: C901 and PLR0912 warnings remain (pre-existing complexity issues)
- 2026-01-26 18:00: **Task 05 Complete** - Comprehensive integration tests added
  - Added test design documentation at module level (docstring with test design references)
  - Added 5 equivalence partition tests: TC-EP-001, TC-EP-002, TC-EP-009, TC-EP-010, TC-EP-013
  - Added 7 boundary value tests: TC-BV-001 through TC-BV-007
  - Added coverage validation test documenting all error types
  - All tests follow Given/When/Then pattern
  - Tests verify: error type, file path, line/column info, field names, documentation URLs
  - Total test count: 54 tests in test_config.py (13 new tests added in Task 05)
  - All 54 tests pass successfully
  - Config module coverage: 80% (155 statements, 60 branches)
  - mypy and ruff checks pass with no new errors
  - Fixed TC-EP-013 test to prevent fallback to cwd's pyproject.toml using monkeypatch
- Task decomposition follows 1 commit = 1 task granularity
- Each task is independently executable with clear completion criteria
- Dependencies are minimal and clearly defined
