# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Deprecated

- **Python 3.9 Support**: Python 3.9 support is now deprecated and will be removed in rdetoolkit v2.0. Users are encouraged to upgrade to Python 3.10 or later. A `DeprecationWarning` is now issued when rdetoolkit is imported under Python 3.9. (#360)
  - **Timeline**: Python 3.9 reaches End of Life in October 2025
  - **Action Required**: Plan to upgrade to Python 3.10+ before rdetoolkit v2.0 release
  - **Migration Path**: Python 3.10, 3.11, 3.12, and 3.13 are fully supported

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

[Unreleased]: https://github.com/nims-mdpf/rdetoolkit/compare/v1.5.2...HEAD
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
