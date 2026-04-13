# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.6.3] - 2026-04-13

### Fixed

#### SmartTable New Sample Registration sampleId Fix (#470)

Fixed a bug where `sampleId` was set to an empty string `""` instead of `None` during new sample registration in SmartTable mode. The empty string caused a server-side error "存在しない試料IDが指定されました" (non-existent sample ID specified). Now `_clear_sample_for_new_registration()` sets `sampleId` to `None`, which correctly triggers new sample creation.

#### Support Uppercase Image Extensions in Thumbnail Copy (#473)

Fixed a bug where image files with uppercase extensions (`.JPG`, `.JPEG`, `.PNG`) were not copied to the thumbnail folder. On case-sensitive file systems (Linux/Docker), `glob` pattern matching only found lowercase extensions. Added `.tif`/`.tiff` support and switched to a single directory scan that normalizes file suffixes to lowercase for case-insensitive extension matching, improving both correctness and efficiency.

#### SmartTable Missing File Reference Error Improvement (#462)

Improved error messages when SmartTable `inputdata` column references files that do not exist in the uploaded zip. Previously, a generic "ERROR: failed in data processing" was shown. Now raises `StructuredError` with the specific SmartTable row number, column name, and file basename. Full details of all missing references are logged for multi-file diagnosis.

### Added

#### Agent Guide for AI Coding Assistants (#380)

Added embedded documentation to enable AI coding agents (Claude Code, GitHub Copilot, Codex) to effectively use rdetoolkit without requiring users to write detailed instruction files.

**New Features:**

- **`get_agent_guide()` API function**: Programmatic access to agent documentation
  - `get_agent_guide()`: Returns summary guide (~2KB, 1500-2000 tokens)
  - `get_agent_guide(detailed=True)`: Returns detailed guide (~5KB, 3000-4000 tokens)
  - Available at package level: `rdetoolkit.get_agent_guide()`

- **`agent-guide` CLI command**: Command-line access to documentation
  - `rdetoolkit agent-guide`: Display summary guide
  - `rdetoolkit agent-guide --detailed`: Display detailed guide with advanced patterns
  - `rdetoolkit agent-guide --help`: Show command usage

- **Comprehensive agent documentation**:
  - `_agent/AGENTS.md`: Summary guide with quick reference
  - `_agent/guide.md`: Detailed guide with architecture, advanced patterns, and testing guidance
  - Includes practical examples, error handling patterns, and processor development guide

- **Agent Skills for AI coding assistants** (`.agents/SKILL.md`):
  - Contextual development guidance auto-discovered by Claude Code
  - Covers encoding-safe file I/O, 5 processing modes, CLI workflow, configuration specs
  - Reference files for preferred APIs, mode selection, CLI workflow, and configuration
  - Complements the programmatic Agent Guide (`_agent/`) with development-session guidance

**Enhanced Documentation:**

- Enhanced `workflows.run()` docstring with comprehensive examples and usage patterns
- Enhanced `RdeInputDirPaths` and `RdeOutputResourcePath` docstrings with practical examples
- Added module-level documentation for `rde2types.py`

**Package Distribution:**

- Guide files (`_agent/*.md`) included in wheel distribution
- Accessible after package installation in any environment

**Benefits:**

- Reduces user burden of writing detailed agent instructions
- Provides consistent, maintained documentation for AI assistants
- Enables better code generation and assistance from AI tools
- Improves discoverability through multiple access paths (API, CLI, docstrings)

**Usage Examples:**

```python
# Programmatic access
import rdetoolkit
guide = rdetoolkit.get_agent_guide()
detailed_guide = rdetoolkit.get_agent_guide(detailed=True)
```

```bash
# CLI access
rdetoolkit agent-guide
rdetoolkit agent-guide --detailed
```

**Testing:**

- Comprehensive test coverage for `get_agent_guide()` API
- Comprehensive test coverage for `agent-guide` CLI command
- Package distribution tests verify guide files included in wheel
- 100% branch coverage for new code

## [1.6.0] - 2026-01-30

### Breaking Changes

- **Python 3.9 support dropped**: Minimum Python version is now 3.10 (#351)
  - Python 3.9 reached end-of-life on October 31, 2025
  - Users on Python 3.9 should use rdetoolkit v1.5.x or earlier
  - `pip install rdetoolkit` on Python 3.9 will automatically resolve to the last version compatible with Python 3.9 (currently v1.5.3)

### Changed

- Updated `requires-python` to `>=3.10` in package metadata
- Removed Python 3.9 from CI/CD pipelines and test matrices (GitHub Actions, tox)
- Removed Python 3.9 classifier from PyPI metadata
- Cleaned up Python 3.9 compatibility code and version branches
  - Removed `sys.version_info` checks in `__init__.py`, `result.py`, `command.py`
  - Simplified dataclass definitions to use `slots=True` directly
  - Optimized typing imports to use Python 3.10+ built-ins (`Never`, `ParamSpec`, `TypeAlias`)
- Updated documentation to reflect Python 3.10+ requirement (installation, usage, development)
- Regenerated lock files (`uv.lock`, `requirements*.lock`) for Python 3.10+ dependencies

### Migration Guide

If you are using Python 3.9:

1. **Option 1 (Recommended)**: Upgrade to Python 3.10 or higher
   - Python 3.10, 3.11, 3.12, 3.13, and 3.14 are fully supported
   - See [Python Downloads](https://www.python.org/downloads/) for installation

2. **Option 2**: Pin rdetoolkit to the last 3.9-compatible version:
   ```bash
   pip install "rdetoolkit<1.6.0"
   ```
   Note: This will limit you to the last version compatible with Python 3.9 (currently v1.5.3) and earlier, which will not receive new features or bug fixes.

For more information on Python version support lifecycle, see: https://endoflife.date/python

## [1.5.2] - 2026-01-26

### Changed

- Bumped version to 1.5.2

## [1.5.1] - 2026-01-21

For detailed release notes, see [docs/releases/index.en.md](docs/releases/index.en.md#v151-2026-01-21).

### Added

- SmartTable row data direct access via `smarttable_row_data` property
- Variable array feature support in description with configurable `feature_description` flag

### Fixed

- Multiple SmartTable and variable processing improvements

## [1.5.0] - 2026-01-09

For detailed release notes, see [docs/releases/index.en.md](docs/releases/index.en.md#v150-2026-01-09).

### Added

- Result type pattern for explicit error handling
- Timestamped log filenames for better isolation
- CLI modernization with Typer and validation commands
- Python 3.14 official support

### Changed

- Lazy imports for improved startup performance
- Type safety improvements with NewType and dispatch tables

## [1.4.3] - 2025-12-25

For detailed release notes, see [docs/releases/index.en.md](docs/releases/index.en.md#v143-2025-12-25).

### Fixed

- SmartTable data integrity issues
- CSV2graph HTML output and legend formatting

## [1.4.2] - 2025-12-18

For detailed release notes, see [docs/releases/index.en.md](docs/releases/index.en.md#v142-2025-12-18).

### Added

- Invoice overwrite validation
- Excel invoice consolidation

### Fixed

- CSV2graph single-series handling
- MultiDataTile empty input processing

## [1.4.1] - 2025-11-05

For detailed release notes, see [docs/releases/index.en.md](docs/releases/index.en.md#v141-2025-11-05).

### Added

- SmartTable rowfile accessor

### Fixed

- Legacy fallback warnings
- MultiDataTile status reporting

## [1.4.0] - 2025-10-24

For detailed release notes, see [docs/releases/index.en.md](docs/releases/index.en.md#v140-2025-10-24).

### Added

- SmartTable automatic metadata.json generation
- CSV visualization utility (csv2graph)
- Configuration scaffold generator (gen-config)
- LLM-friendly traceback format

## [1.3.4] - 2025-08-21

For detailed release notes, see [docs/releases/index.en.md](docs/releases/index.en.md#v134-2025-08-21).

### Fixed

- SmartTable validation stability

## [1.3.3] - 2025-07-29

For detailed release notes, see [docs/releases/index.en.md](docs/releases/index.en.md#v133-2025-07-29).

### Added

- sampleWhenRestructured schema support

### Fixed

- ValidationError handling

## [1.3.2] - 2025-07-22

For detailed release notes, see [docs/releases/index.en.md](docs/releases/index.en.md#v132-2025-07-22).

### Changed

- Strengthened SmartTable required-field validation

## [1.3.1] - 2025-07-14

For detailed release notes, see [docs/releases/index.en.md](docs/releases/index.en.md#v131-2025-07-14).

### Fixed

- Excel invoice empty-sheet handling
- extended_mode validation strictness

## [1.2.0] - 2025-04-14

For detailed release notes, see [docs/releases/index.en.md](docs/releases/index.en.md#v120-2025-04-14).

### Added

- MinIO integration for object storage
- Archive generation utilities
- Report tooling

[Unreleased]: https://github.com/nims-mdpf/rdetoolkit/compare/v1.6.0...HEAD
[1.6.0]: https://github.com/nims-mdpf/rdetoolkit/compare/v1.5.2...v1.6.0
[1.5.2]: https://github.com/nims-mdpf/rdetoolkit/compare/v1.5.1...v1.5.2
[1.5.1]: https://github.com/nims-mdpf/rdetoolkit/compare/v1.5.0...v1.5.1
[1.5.0]: https://github.com/nims-mdpf/rdetoolkit/compare/v1.4.3...v1.5.0
[1.4.3]: https://github.com/nims-mdpf/rdetoolkit/compare/v1.4.2...v1.4.3
[1.4.2]: https://github.com/nims-mdpf/rdetoolkit/compare/v1.4.1...v1.4.2
[1.4.1]: https://github.com/nims-mdpf/rdetoolkit/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/nims-mdpf/rdetoolkit/compare/v1.3.4...v1.4.0
[1.3.4]: https://github.com/nims-mdpf/rdetoolkit/compare/v1.3.3...v1.3.4
[1.3.3]: https://github.com/nims-mdpf/rdetoolkit/compare/v1.3.2...v1.3.3
[1.3.2]: https://github.com/nims-mdpf/rdetoolkit/compare/v1.3.1...v1.3.2
[1.3.1]: https://github.com/nims-mdpf/rdetoolkit/compare/v1.2.0...v1.3.1
[1.2.0]: https://github.com/nims-mdpf/rdetoolkit/releases/tag/v1.2.0
