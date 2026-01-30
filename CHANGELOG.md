# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.6.0] - 2026-01-30

### Breaking Changes

- **Python 3.9 support dropped**: Minimum Python version is now 3.10 (#351)
  - Python 3.9 reached end-of-life on October 31, 2025
  - Users on Python 3.9 should use rdetoolkit v1.5.x or earlier
  - `pip install rdetoolkit` on Python 3.9 will automatically resolve to the last compatible version (v1.5.2)

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
   Note: This will limit you to rdetoolkit v1.5.2 and earlier, which will not receive new features or bug fixes.

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
