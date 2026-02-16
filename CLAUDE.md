# CLAUDE.md

This file provides Claude Code-specific guidance when working with code in this repository.

> **📋 Development Rules**: For comprehensive development rules (testing methodology, code style, branch strategy, environment setup), see **[AGENTS.md](./AGENTS.md)**. This file focuses on Claude Code-specific guidance, architecture, and agent usage patterns.

## Quick Reference

- **Testing Requirements** → [AGENTS.md Section 6](./AGENTS.md#6-testing)
- **Code Style & Standards** → [AGENTS.md Section 3](./AGENTS.md#3-code-formatting--linters)
- **Branch Strategy** → [AGENTS.md Section 5](./AGENTS.md#5-branch-strategy)
- **Environment Setup** → [AGENTS.md Section 2](./AGENTS.md#2-development-environment-setup)

## Project Overview

RDEToolKit is a Python package for creating workflows of RDE (Research Data Express) structured programs. It enables researchers to register, process, and visualize experimental data in RDE format. The project has a **hybrid architecture** combining Python (frontend/workflow) and Rust (performance-critical operations).

## Architecture

### Hybrid Language Structure

- **Python Layer** (`src/rdetoolkit/`): Main API, workflow orchestration, data models
- **Rust Core** (`rdetoolkit-core/`): Performance-critical operations via PyO3 bindings
  - Image processing and thumbnail generation
  - Character set detection
  - File system operations

The Rust code is compiled into a Python extension module (`core.cpython-*.so`) via Maturin.

### Key Architectural Components

1. **Workflow Pipeline** (`workflows.py`, `processing/pipeline.py`):
   - Entry point: `rdetoolkit.workflows.run(custom_dataset_function=...)`
   - Processor-based architecture with pluggable components
   - Supports three execution modes: invoice, excelinvoice, and extended_mode (MultiDataTile/SmartTable)

2. **Processing System** (`processing/`):
   - `Pipeline`: Coordinates processor execution
   - `Processor`: Base class for all processing steps
   - Processors in `processing/processors/`: validation, files, invoice, thumbnails, descriptions, variables, datasets

3. **Data Models** (`models/`):
   - `Config`: System configuration with pydantic validation
   - `invoice.py`/`invoice_schema.py`: RDE invoice schema models
   - `RdeInputDirPaths`/`RdeOutputResourcePath`: Path management

4. **CLI Commands** (`cli.py`, `cmd/`):
   - `init`: Generate RDE project template
   - `gen-invoice`: Generate invoice.json from invoice.schema.json
   - `gen-excelinvoice`: Generate Excel invoice from schema
   - `archive`: Create deployment artifacts

## Working with Claude Code Agents

This project leverages specialized Claude Code agents for various development tasks. These agents are invoked automatically based on context, or can be explicitly requested.

### Recommended Agents for RDEToolKit Development

#### Code Quality & Testing
- **quality-checker**: Validates code quality (ruff, mypy, pytest). Automatically runs after code changes.
  - Use when: After implementing features, before commits
  - Example: Validates type hints, linting rules, runs test suite

- **tdd-enforcer**: Ensures test-first development approach
  - Use when: Implementing new features, adding processors
  - Example: Creates test cases before implementation for new processors

- **python-expert**: Production-ready Python code following SOLID principles
  - Use when: Complex Python implementations, architectural decisions
  - Example: Implementing new processor classes, data model refactoring

#### Task Management
- **task-decomposer**: Breaks down complex features into atomic tasks
  - Use when: Large features, multi-component changes, PRD implementation
  - Example: Breaking down "Add new execution mode" into specific tasks

- **task-executor**: Executes decomposed tasks systematically
  - Use when: Following task-decomposer output, systematic implementation
  - Example: Executing tasks one by one with progress tracking

#### Analysis & Debugging
- **root-cause-analyst**: Systematically investigates bugs and failures
  - Use when: Test failures, unexpected behavior, performance issues
  - Example: Analyzing why thumbnail generation fails for specific image types

- **performance-engineer**: Optimizes system performance through measurement
  - Use when: Performance bottlenecks, slow operations, memory issues
  - Example: Optimizing Rust-Python data transfer, reducing memory usage

#### Refactoring & Architecture
- **refactoring-expert**: Improves code quality and reduces technical debt
  - Use when: Code cleanup, pattern improvements, architecture improvements
  - Example: Refactoring processor architecture for better extensibility

- **system-architect**: Designs scalable system architecture
  - Use when: New major features, architectural decisions, system design
  - Example: Designing multi-backend support (S3, local filesystem)

#### Git & Documentation
- **pr-generator**: Creates comprehensive pull requests with descriptions
  - Use when: Feature completion, ready to create PR
  - Example: Generates PR description from commit history and changes

### Agent Usage Patterns

#### Issue-Based Development Workflow (Recommended)

This is the standard workflow for RDEToolKit development when working on GitHub issues:

**Step 1: Task Decomposition**
```
Use task-decomposer to break down the issue into atomic tasks.
Input: local/develop/issue_<issue番号>.md
Output: Decomposed tasks in task files
```

**Step 2: Parallel Task Execution with Quality Gates**
For each decomposed task, execute in parallel:
```
1. task-executor: Execute one task
2. quality-checker: Validate code quality after task completion
   ↓ (passes) → Continue to next task
   ↓ (fails) → Fix issues → Re-run quality-checker
```

**Complete Workflow Command Pattern**
```
Sub-agentのtask-decomposerでタスク分解して。タスクは、local/develop/issue_<issue番号>.mdです。
その後、分解したタスクを並列で、以下のsub-agentを使ってタスクの実行をしてください：
  - task-executorで1タスク実行
  - task-executorが完了したらquality-checkerで品質チェック
```

**Benefits of This Workflow**
- Incremental quality assurance (each task is validated before proceeding)
- Parallel execution where tasks are independent
- Systematic progress tracking with quality gates
- Early detection of issues (fail fast)

#### Feature Development Workflow
```
1. task-decomposer: Break down feature into tasks
2. tdd-enforcer: Define test cases for each task
3. task-executor: Implement tasks one by one
4. quality-checker: Validate code quality after each task
5. pr-generator: Create PR when feature is complete
```

#### Bug Investigation Workflow
```
1. root-cause-analyst: Systematically investigate the issue
2. python-expert: Implement fix following best practices
3. tdd-enforcer: Add regression tests
4. quality-checker: Validate fix and tests
```

#### Refactoring Workflow
```
1. system-architect: Plan refactoring approach
2. task-decomposer: Break into safe incremental steps
3. refactoring-expert: Execute refactoring
4. quality-checker: Ensure no regressions
```

### Project-Specific Agent Guidance

For RDEToolKit development, agents should be aware of:
- **Hybrid architecture**: Both Python and Rust code need consideration
- **Processor pattern**: New processors must follow `Processor` base class contract
- **Type safety**: Strict mypy enforcement, all code must be fully typed
- **Test coverage**: All new code requires comprehensive tests
- **Documentation**: Google Style docstrings are mandatory
- **Pre-commit hooks**: Code must pass ruff, mypy, and other checks

## Key Files and Their Purposes

- **`workflows.py`**: Main workflow orchestration (`run()` function)
- **`processing/pipeline.py`**: Processor execution pipeline
- **`processing/processors/`**: Individual processing steps (validation, thumbnails, etc.)
- **`models/config.py`**: Configuration schema with `SystemSettings`, `MultiDataTileSettings`, `SmartTableSettings`
- **`invoicefile.py`**: Invoice JSON file handling
- **`fileops.py`**: File operations and utilities
- **`rde2util.py`**: RDE format utilities
- **`static/`**: Static resources (invoice schema, CSV templates)

## Invoice Generation from Schema

RDEToolKit provides both API and CLI methods to generate `invoice.json` files directly from `invoice.schema.json` definitions.

### API Usage

```python
from pathlib import Path
from rdetoolkit.invoice_generator import generate_invoice_from_schema

# Generate with all fields and defaults, write to file
invoice_data = generate_invoice_from_schema(
    schema_path="tasksupport/invoice.schema.json",
    output_path="invoice/invoice.json",
    fill_defaults=True,
    required_only=False,
)

# Generate required fields only, return dict without file
invoice_data = generate_invoice_from_schema(
    schema_path="tasksupport/invoice.schema.json",
    fill_defaults=False,
    required_only=True,
)
```

### CLI Usage

```bash
# Basic usage - generates invoice.json in current directory
rdetoolkit gen-invoice tasksupport/invoice.schema.json

# Specify output path
rdetoolkit gen-invoice tasksupport/invoice.schema.json -o container/data/invoice/invoice.json

# Generate required fields only
rdetoolkit gen-invoice tasksupport/invoice.schema.json --required-only

# Generate without default values
rdetoolkit gen-invoice tasksupport/invoice.schema.json --no-fill-defaults

# Generate with compact formatting
rdetoolkit gen-invoice tasksupport/invoice.schema.json --format compact
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --output` | Output path for invoice.json | ./invoice.json |
| `--fill-defaults/--no-fill-defaults` | Populate type-based default values | True |
| `--required-only` | Include only required fields | False |
| `--format [pretty\|compact]` | Output JSON format | pretty |

### Default Value Strategy

When `fill_defaults=True`, values are determined in this priority:
1. Schema `default` field
2. First item from schema `examples`
3. Type-based defaults: string→"", number→0.0, integer→0, boolean→false

## RDE Execution Modes

The toolkit supports three modes (evaluated in order: extended_mode → excelinvoice → invoice):

1. **invoice**: Standard JSON invoice mode
2. **excelinvoice**: Excel-based invoice mode
3. **extended_mode**: Advanced modes
   - `MultiDataTile`: Multiple data tiles per dataset
   - `SmartTable`: Smart table processing with early exit support

Mode selection is controlled via `Config.system.extended_mode`.

## Common Development Patterns

### Adding a New Processor

1. Create processor class in `processing/processors/` inheriting from `Processor`
2. Implement `process(context: ProcessingContext) -> None` method
3. Register in `processing/factories.py` if needed
4. Add tests in `tests/processing/`

### Custom Dataset Function

User-defined processing functions follow this signature:

```python
def custom_dataset(
    srcpaths: RdeInputDirPaths,
    resource_paths: RdeOutputResourcePath
) -> None:
    # Process input data from srcpaths
    # Save outputs to resource_paths
    pass
```

### Configuration Management

Configuration is loaded from `tasksupport/config.toml` or programmatically:

```python
from rdetoolkit.models.config import Config, SystemSettings

config = Config(
    system=SystemSettings(
        extended_mode="MultiDataTile",
        save_raw=False,
        save_thumbnail_image=True
    )
)
```

## Rust Development Notes

- Rust code in `rdetoolkit-core/` uses PyO3 for Python bindings
- Build backend: Maturin (configured in `pyproject.toml`)
- Rust tests for PyO3 extensions must run through Python, not `cargo test`
- Key Rust modules:
  - `imageutil/`: Image processing and thumbnails
  - `charset_detector.rs`: Character encoding detection
  - `fsops.rs`: File system operations

## Dependencies

- **Core**: pandas, polars, pydantic, jsonschema, openpyxl, PyYAML
- **Optional**: minio (for S3-compatible storage)
- **Build**: maturin (Rust/Python bridge), build
- **Dev**: pytest, ruff, mypy, tox, mkdocs, hypothesis (property-based testing)

## Property-Based Testing (PBT)

### Overview

RDEToolKit uses the Hypothesis library for Property-Based Testing. PBT automatically tests boundary values and data combinations, discovering bugs that example-based tests might miss. PBT tests complement traditional example-based tests to achieve comprehensive coverage.

### When to Use PBT

- **Data transformation/normalization functions**: `graph.normalizers`, `rde2util.castval`
- **String processing**: `graph.textutils`
- **Validation logic**: `validation`, `graph.io.path_validator`
- **Invariant testing**: Properties that should always hold regardless of input

### PBT Test Location

- **Directory**: `tests/property/`
- **Marker**: All PBT tests must use `@pytest.mark.property`
- **Naming**: `test_<module>_*.py` (e.g., `test_graph_normalizers.py`)

### Writing PBT Tests

1. **Define Hypothesis strategies** in `tests/property/strategies.py` or test module
2. **Use `@given` decorator** with appropriate strategies
3. **Test properties (invariants)**, not specific examples:
   - Idempotence: `f(f(x)) == f(x)`
   - Round-trip: `decode(encode(x)) == x`
   - Preservation: output preserves certain properties of input
   - Consistency: same input always produces same output
4. **Use `assume()`** to filter invalid inputs
5. **Follow Given/When/Then** comment structure

### Example

```python
from hypothesis import given, strategies as st
import pytest

@pytest.mark.property
class TestNormalizeProperties:
    @given(data=st.lists(st.floats(allow_nan=False)))
    def test_normalize_preserves_length(self, data):
        """Property: Normalization preserves data length."""
        # Given: List of floats
        # When: Normalizing data
        result = normalize(data)
        # Then: Length is preserved
        assert len(result) == len(data)
```

### Hypothesis Settings

- **Dev profile** (default): `max_examples=100`, no deadline
- **CI profile**: `max_examples=50`, `deadline=5000ms`
- **Switch profile**: `HYPOTHESIS_PROFILE=ci pytest ...`

### Coverage Requirements

- PBT tests **must not reduce** existing 100% branch coverage
- PBT tests are **complementary** to example-based tests
- Both test types run together in CI

### Running PBT Tests

```bash
# Run all tests (example-based + property-based)
tox -e py312-module

# Run only property-based tests
pytest tests/property/ -v -m property

# Run with CI profile (faster, fewer examples)
HYPOTHESIS_PROFILE=ci pytest tests/property/ -v -m property
```

### Agent Guidance

When implementing new data processing functions:

1. Write example-based tests first (EP/BV tables)
2. Add PBT tests for invariants and edge cases
3. Ensure both test types pass
4. Verify coverage remains 100%

## Additional Resources

- Documentation: https://nims-mdpf.github.io/rdetoolkit/
- Issues: https://github.com/nims-dpfc/rdetoolkit/issues
- Contributing Guide: CONTRIBUTING.md

## Local Rule

- Think in English, respond in Japanese.