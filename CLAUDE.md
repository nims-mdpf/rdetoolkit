# CLAUDE.md

This file provides Claude Code-specific guidance when working with code in this repository.

> **📋 Development Rules**: For comprehensive development rules (testing methodology,
> code style, Rust/Python boundary, branch strategy, environment setup), see
> **[AGENTS.md](./AGENTS.md)**. This file focuses on Claude Code-specific guidance,
> architecture, and agent usage patterns.

## Quick Reference

- **Testing Requirements** → [AGENTS.md §7](./AGENTS.md#7-testing)
- **Rust / Python Boundary** → [AGENTS.md §4](./AGENTS.md#4-rust--python-language-boundary)
- **Code Style & Standards** → [AGENTS.md §3](./AGENTS.md#3-code-formatting--linters)
- **Branch Strategy** → [AGENTS.md §6](./AGENTS.md#6-branch-strategy)
- **Environment Setup** → [AGENTS.md §2](./AGENTS.md#2-development-environment-setup)

---

## Project Overview

RDEToolKit is a Python package for creating workflows of RDE (Research Data Express)
structured programs. The project is a **Rust + Python hybrid library** using
PyO3/Maturin.

### Current Development Status

- **v1.x** — stable, maintenance mode. Bug fixes and minor improvements only.
- **v2.x** — active development. Plan: `local/develop/v2/Plan.md`. Branch: `develop/v2`.

---

## Architecture

### Hybrid Language Structure

- **Python Layer** (`src/rdetoolkit/`): API, workflow orchestration, data models,
  metaprogramming (`@node`, `@flow`, Trace proxy, DI resolution)
- **Rust Core** (`rdetoolkit-core/`): Performance-critical and algorithmically precise
  operations via PyO3 bindings

### Rust Core Modules

| Module | Responsibility | Status |
|--------|---------------|--------|
| `imageutil.rs` | Image processing, thumbnail generation | v1 (unchanged) |
| `charset_detector.rs` | Character encoding detection | v1 (unchanged) |
| `fsops.rs` | File system / directory operations | v1 (unchanged) |
| `dag.rs` | DAG graph structure, topological sort, cycle detection, structural validation | **v2 NEW** |

The Rust code is compiled into `core.cpython-*.so` via Maturin.
**Run `maturin develop` after any Rust change before running Python tests.**

### v1.x Architecture (Stable)

1. **Workflow Pipeline** (`workflows.py`, `processing/pipeline.py`):
   - Entry point: `rdetoolkit.workflows.run(custom_dataset_function=...)`
   - Linear Processor-based architecture
   - Modes: invoice, excelinvoice, extended_mode (MultiDataTile / SmartTable)

2. **Processing System** (`processing/`):
   - `Pipeline`: Coordinates processor execution
   - `Processor`: Base class for all processing steps
   - Processors: validation, files, invoice, thumbnails, descriptions, variables, datasets

3. **Data Models** (`models/`): Config (pydantic), invoice schema, path management

4. **CLI** (`cli.py`, `cmd/`): init, gen-invoice, gen-excelinvoice, archive

### v2.x Architecture (In Development)

v2 is a **paradigm shift** from v1's linear Pipeline to a DAG-based, agent-centric
design. The Rust/Python split is intentional: Rust owns graph algorithms, Python owns
metaprogramming and orchestration.

```
src/rdetoolkit/
├── core/          # @node(Python), @flow(Python), DAG wrapper(Python+Rust), Compiler, Executor
├── protocols/     # Structural protocol definitions                 [NEW - Python]
├── domain/        # Config, Mode, Paths, Invoice, Validation        [NEW + REFACTOR - Python]
├── runner/        # Runner lifecycle, DataTile iterators            [NEW - Python]
├── report/        # EventSink, RunReport                           [NEW - Python]
├── nodes/         # Built-in @node wrappers around v1 processors   [NEW - Python]
├── utils/         # Utilities from rde2util/fileops                [REFACTOR - Python]
├── plugin/        # Plugin system via entry_points                 [NEW - Python]
├── testing/       # Public test helpers                            [NEW - Python]
├── cli/           # Extended CLI with v2 subcommands               [EXTEND - Python]
├── types.py       # Extended with InputPaths, OutputContext         [APPEND-ONLY]
├── errors.py      # Extended with RdeError hierarchy               [APPEND-ONLY]
├── result.py      # Used as-is (Success, Failure, Result)          [UNCHANGED]
└── workflows.py   # v1/v2 coexistence entry point                 [MODIFY]

rdetoolkit-core/
├── dag.rs         # RustDAG (#[pyclass]), petgraph backend         [NEW - Rust]
└── (v1 modules unchanged)
```

**Key v2 Design Decisions:**
- DAG graph structure and algorithms live in **Rust** (`dag.rs`, `petgraph` crate)
- `@node`, `@flow`, Trace proxy, DI resolution stay in **Python** (metaprogramming)
- Only primitive types cross the Python ↔ Rust boundary (`str`, `list[str]`, etc.)
- `NodeSpec` and other Python objects are managed Python-side; Rust sees only node IDs
- `@node` only attaches `__node_spec__` — decorated functions remain directly callable
- `core/result.py` is NOT created — existing `result.py` is used as-is
- `types.py` and `errors.py` are append-only

---

## Working with Claude Code Agents

### Agent Roster

#### Orchestration
- **task-decomposer** — Reads `local/develop/v2/Plan.md`, classifies phase type,
  dispatches the correct pipeline. **Entry point for all v2 development.**
- **task-executor** — Executes decomposed tasks via Claude (non-Codex tasks).

#### Implementation
- **codex-worker** — Delegates to Codex (gpt-5.4 xhigh) via the `codex` CLI
  (`codex exec --full-auto`). Used for all substantial implementation in v2 —
  including Rust code in `dag.rs`. Runs Codex I/O inside a subagent context so
  the main conversation is not flooded with tool output.
- **/codex-delegate Skill** (`.claude/skills/codex-delegate/SKILL.md`) —
  Equivalent entry point for main-context (non-subagent) delegation. Shares the
  same prompt conventions as codex-worker.
- **python-expert** — Complex architectural decisions when Codex delegation is not
  appropriate.

#### Quality & Testing
- **tdd-enforcer** — Writes failing test files before implementation. Two modes:
  - `standard`: new test files for New-with-v1-ref phases
  - `v1-reuse`: baseline confirmation + compat tests for Direct Refactor phases
  - **Not called for Phase 1.x (Pure New) — task-decomposer passes Plan.md `TEST:`
    rows directly to codex-worker**
- **quality-checker** — Runs ruff, mypy, full tox suite. Called after each
  codex-worker round.

#### Analysis & Debugging
- **root-cause-analyst** — Systematic investigation of bugs and test failures.
- **performance-engineer** — Performance measurement; especially relevant for
  Python ↔ Rust boundary overhead analysis.

#### Refactoring & Architecture
- **refactoring-expert** — Code quality, technical debt.
- **system-architect** — New major features, architectural decisions.

#### Git & Documentation
- **pr-generator** — Creates PRs after feature completion.

---

## Development Workflows

### v2 Development Workflow (Primary)

Input: `local/develop/v2/Plan.md`

```
task-decomposer
  └─ Reads Plan.md, classifies phase type, generates task files
  └─ Determines Rust vs Python scope per task

Phase Classification:
  Pure New Concept     → Pipeline A  (Phase 1.x core/ + dag.rs)
  New-with-v1-ref      → Pipeline B  (Phase 2.1/2.3/3.x/5.x)
  Direct Refactor      → Pipeline C  (Phase 2.2/3.17/4.x/5.2/5.5)

Pipeline A — direct-to-codex (Phase 1.x):
  codex-worker × N (parallel)
    Rust tasks:   implement dag.rs with petgraph, maturin develop
    Python tasks: @node, @flow, DAG wrapper, Compiler, Executor
    → quality-checker (maturin develop && tox -e py312-module)

Pipeline B — tdd-enforcer → codex (New-with-v1-ref):
  tdd-enforcer × N (parallel, standard mode)
    → codex-worker × N (parallel, Test Manifest as target)
      → quality-checker

Pipeline C — v1-reuse → codex (Direct Refactor):
  tdd-enforcer (v1-reuse mode: confirm v1 GREEN baseline)
    → codex-worker (move logic + re-export, keep v1 GREEN)
      → quality-checker
      → tox -e py312-module (VERIFY — mandatory before phase merge)
```

**Trigger command example (single phase, intra-phase parallel):**
```
Use task-decomposer to read local/develop/v2/Plan.md and implement Phase 1.3.
Note: Phase 1.3 includes both Rust (dag.rs with petgraph) and Python (@flow, Trace proxy).
Dispatch Rust and Python tasks to parallel codex-worker agents.
```

**Multi-subphase parallel dispatch (Phase 2 etc.):**

Phase 2 consists of three subphases (2.1 / 2.2 / 2.3) described in
`local/develop/v2/Phase2_prompts_check.md`. File targets do not overlap, but
subphase 2.2 is a Direct Refactor that touches v1 code, so tox runs can be
contaminated if it is parallelised with the others. Default pattern:

| Round | Dispatched in parallel | Pipeline | Rationale |
|-------|-----------------------|----------|-----------|
| R1 | Session 6 (Phase 2.1) + Session 8 (Phase 2.3) | B + B | Both New-with-v1-ref, no v1 impact, file-independent |
| R2 | Session 7 (Phase 2.2) alone | C | Direct Refactor — v1 tests must stay GREEN; serialise |

Apply the same pattern to any multi-subphase phase: group "New-with-v1-ref"
subphases into one parallel round, and serialise "Direct Refactor" subphases
between rounds. `quality-checker` runs between rounds.

Trigger example:
```
Use task-decomposer to read local/develop/v2/Phase2_prompts_check.md and
dispatch Phase 2 in two rounds:
  Round 1 (parallel): codex-worker for Session 6 (2.1) + codex-worker for Session 8 (2.3)
  Round 2 (serial):   codex-worker for Session 7 (2.2, Direct Refactor)
quality-checker between rounds.
```

**Phase branch rule:** Always work on `v2/phase-N`. Never commit to `develop/v2` directly.

---

### v1 Maintenance Workflow

Input: `local/develop/issue_<N>.md`

```
task-decomposer (issue mode)
  └─ task-executor × N (parallel)
       └─ quality-checker
```

### Bug Investigation Workflow

```
root-cause-analyst → python-expert → tdd-enforcer (regression) → quality-checker
```

### Refactoring Workflow

```
system-architect → task-decomposer → refactoring-expert → quality-checker
```

### PR Creation

```
quality-checker (final) → pr-generator
```

---

## v2 Phase Classification Reference

| Phase | Name | Type | Pipeline | v1 Impact | Rust? |
|-------|------|------|----------|-----------|-------|
| 1.1 | types/errors | Pure New | A | none | No |
| 1.2 | @node API | Pure New | A | none | No |
| 1.3 | @flow + DAG | Pure New | A | none | **Yes (dag.rs)** |
| 1.4 | Compiler | Pure New | A | none | **Yes (RustDAG.validate)** |
| 1.5 | Executor + Context | Pure New | A | none | No |
| 2.1 | Observability | New-with-v1-ref | B | none | No |
| **2.2** | **Config/Mode/Paths** | **Direct Refactor** | **C** | **modeproc.py, validation.py** | No |
| 2.3 | Protocols | New-with-v1-ref | B | none | No |
| 3.1–3.16 | Runner + Iterator | New-with-v1-ref | B | none | No |
| **3.17** | **workflows.py** | **Direct Refactor** | **C** | **workflows.py** | No |
| **4.x** | **CLI** | **Direct Refactor** | **C** | **cli/*** | No |
| 5.1 | Built-in nodes | New-with-v1-ref | B | none | No |
| **5.2** | **Utils migration** | **Direct Refactor** | **C** | **rde2util.py, fileops.py** | No |
| 5.3 | Plugin system | New-with-v1-ref | B | none | No |
| 5.4 | Testing helpers | New-with-v1-ref | B | none | No |
| **5.5** | **Public API** | **Direct Refactor** | **C** | **__init__.py, workflows.py** | No |
| 6 | Docs / Release | — | manual | none | No |

**Direct Refactor phases: `tox -e py312-module` must be GREEN before merging.**
**Phases with Rust: `maturin develop` must succeed before running any Python tests.**

---

## Key Files and Their Purposes

### v1.x (Do Not Break)
- `workflows.py` — `run(custom_dataset_function=...)`
- `processing/pipeline.py` — Processor execution pipeline
- `models/config.py` — Config schema (used as-is in v2)
- `result.py` — `Result`, `Success`, `Failure` — used as-is in v2, do not replace
- `rde2util.py` — Utilities (moved to `utils/` in Phase 5.2, re-exported here)
- `fileops.py` — File ops (moved to `utils/fileops.py` in Phase 5.2, re-exported here)

### v2.x (In Development)
- `local/develop/v2/Plan.md` — Master implementation plan
- `rdetoolkit-core/dag.rs` — Rust DAG engine (petgraph backend)
- `src/rdetoolkit/core/` — DAG engine Python layer
- `src/rdetoolkit/runner/` — Runner lifecycle
- `tests/v2/` — All v2 tests (never touch `tests/` v1 files)

---

## Testing

See [AGENTS.md §7](./AGENTS.md#7-testing) for full detail. Summary:

```bash
# After Rust changes (always rebuild first)
maturin develop && tox -e py312-module

# v2 only
tox -e py312-module -- tests/v2/ -v

# PBT only
pytest tests/v2/ -m property -v
```

Test directory for v2: `tests/v2/` — never modify `tests/` root.

---

## Codex CLI Integration

v2 development delegates Codex (gpt-5.4 xhigh) execution via the `codex` CLI —
including Rust code in `dag.rs`. **MCP is no longer used** (the former
`mcp__codex__codex` / `mcp__codex__codex-reply` tools are replaced by
`codex exec` + `codex exec resume`).

### Two entry points (same prompt convention)

| Entry | When | Context |
|-------|------|---------|
| `codex-worker` subagent | task-decomposer pipeline / parallel N-wide dispatch | Subagent (isolates Codex I/O from main conversation) |
| `/codex-delegate` Skill | Ad-hoc manual delegation | Main conversation |

### Configuration

No MCP server required. The `codex` CLI must be on PATH
(`which codex` — `codex-cli` 0.122.0+).

`.claude/settings.local.json`:
```json
{
  "permissions": {
    "allow": ["Bash(codex --version)", "Bash(codex exec *)"]
  }
}
```

### Invocation (shared by both entry points)

Single-turn — replaces `mcp__codex__codex`:
```bash
codex exec --full-auto -m "gpt-5.4 xhigh" -C "$PWD" \
  -o /tmp/codex-last.md "<structured prompt>"
```

Multi-turn follow-up — replaces `mcp__codex__codex-reply`:
```bash
codex exec resume --last -m "gpt-5.4 xhigh" "<next prompt>"
```

- `--full-auto` ≡ `--sandbox workspace-write` without approval prompts
  (matches the old MCP `sandbox: workspace-write, approval-policy: never`).
- Never use `--dangerously-bypass-approvals-and-sandbox`.
- `-o <file>` captures the agent's final message for verification.

### Codex Prompt Template (v2)

```
[ROLE] You are implementing <FEATURE> for rdetoolkit v2 (Rust+Python hybrid library).

[CONTEXT]
- Python 3.12, strict mypy, ruff
- Rust: PyO3 0.28.2, petgraph 0.7 (for DAG tasks)
- Test runner: tox -e py312-module (after maturin develop for Rust tasks)
- Reference: local/develop/v2/Plan.md §8 (design decisions)
- Reference: AGENTS.md §4 (Rust/Python boundary rules)

[TASK]
<NUMBERED STEPS FROM PLAN.md OR TEST MANIFEST>

[CONSTRAINTS — RUST TASKS]
- Only primitive types cross Python ↔ Rust boundary (str, list[str], dict[str,str])
- NodeSpec and Python objects stay Python-side; Rust sees only node IDs
- No unwrap() — always PyResult<T>
- Update core.pyi stubs after any public API change
- Run maturin develop before Python tests

[CONSTRAINTS — PYTHON TASKS]
- Do not modify existing content in types.py / errors.py (append-only)
- Do not create core/result.py — use existing result.py
- Google Style docstrings, type annotations everywhere (mypy strict)
- Do not modify files outside: <TARGET FILES>
```

### Codex Delegation Criteria

**Always delegate to Codex (codex-worker subagent or /codex-delegate Skill):**
- All v2 implementation tasks from Plan.md (Python and Rust)
- `dag.rs` Rust implementation (petgraph backend)
- 10+ file refactors, boilerplate generation

**Keep in Claude:**
- Architecture decisions requiring iteration
- PyO3 boundary design review
- Security review, small changes < 20 lines

### Choosing between subagent and Skill

- **Parallel N-wide dispatch (e.g., task-decomposer → codex-worker × 4)**:
  use the `codex-worker` subagent — Codex output stays in the subagent's
  context so the main conversation does not hit token limits.
- **Single ad-hoc delegation from the main conversation**:
  invoke `/codex-delegate <task-file>` — simpler, no subagent overhead.

---

## Common Development Patterns

### v2 @node

```python
from rdetoolkit.core.node import node

@node(tags=["io"], version="1.0.0")
def read_csv(paths: InputPaths) -> tuple[Metadata, pd.DataFrame]:
    """Read CSV from input paths."""
    ...
```

### v2 @flow

```python
from rdetoolkit.core.flow import flow

@flow
def xrd_pipeline(paths: InputPaths) -> None:
    meta, df = read_csv(paths)
    normalized = normalize(meta, df)
    write_metadata(normalized)
```

### Python DAG Wrapper (delegates to Rust)

```python
from rdetoolkit._core import RustDAG

class DAG:
    def __init__(self) -> None:
        self._rust = RustDAG()           # Rust graph engine
        self._specs: dict = {}            # Python metadata

    def add_node(self, node_id: str, spec) -> None:
        self._rust.add_node(node_id)      # only str crosses boundary
        self._specs[node_id] = spec       # Python obj stays Python-side

    def topological_sort(self) -> list[str]:
        return self._rust.topological_sort()  # petgraph O(V+E)
```

### Re-export Pattern (Direct Refactor)

```python
# rde2util.py after Phase 5.2
from rdetoolkit.utils.encoding import detect_encoding  # noqa: F401
```

### Result Type (v1, use as-is)

```python
from rdetoolkit.result import Success, Failure, Result
```

---

## Key Design Decisions (from Plan.md §8)

### Trace Proxy (Plan.md §8.1)

`@flow` switches to **Trace mode** during the Build phase. Each `@node` call returns
a `NodeProxy` instead of executing:

```python
class NodeProxy:
    """Placeholder returned during DAG tracing. Supports tuple unpack."""
    def __init__(self, node_spec: NodeSpec, output_names: tuple[str, ...]) -> None:
        self.node_spec = node_spec
        self.output_names = output_names

    def __iter__(self):
        # Enables:  meta, df = read_csv(paths)
        for name in self.output_names:
            yield OutputProxy(self.node_spec.id, name)
```

When a `NodeProxy` appears as an argument to the next `@node` call, it is recorded
as an edge in `RustDAG.add_edge()`. **This is the highest implementation risk in v2.**
TDD must define the edge-recording contract before implementation begins.

Variable name extraction requires `ast` module or bytecode (`dis`) analysis of the
`@flow` body — this must be settled during Phase 1.3 TDD.

### DI Resolution Priority (Plan.md §8.2)

```
Priority 1: DAG edge result (upstream @node output)
Priority 2: Runner reserved types (InputPaths, OutputContext, RunContext, ...)
Priority 3: UnconnectedInputError
```

### rdeconfig.yaml v2 Additions (Plan.md §8.5)

```yaml
# v2 new sections
policy:
  node_enforcement: recommend  # off | recommend | strict

compile:
  type_check: strict           # strict | warn | off
  warnings_as_errors: false

execution:
  on_iteration_error: continue # fail_fast | continue

plugin:
  preferred_handler:
    ".ras": "rdetoolkit_xrd.readers:RigakuReader"

# v1 existing sections — preserved unchanged
system:
  extended_mode: null
  save_raw: true
  save_thumbnail_image: true
```

---

## Rust Development Notes

- Rust code in `rdetoolkit-core/` uses PyO3 for Python bindings
- Build backend: Maturin (`pyproject.toml`)
- v2 adds `dag.rs` using `petgraph = "0.7"` for DAG algorithms
- Rust unit tests: `#[cfg(test)]` inside `.rs` files (not via `cargo test` for PyO3)
- Python-level tests call the binding via `from rdetoolkit._core import RustDAG`
- **Always `maturin develop` before `tox -e py312-module` when Rust changed**

---

## Dependencies

- **Core**: pandas, polars, pydantic, jsonschema, openpyxl, PyYAML
- **v2 Python additions**: hypothesis (PBT)
- **v2 Rust additions**: petgraph = "0.7"
- **Optional**: minio (S3), plotly
- **Build**: maturin (Rust/Python bridge)
- **Dev**: pytest, ruff, mypy, tox, mkdocs, hypothesis

---

## Additional Resources

- Documentation: https://nims-mdpf.github.io/rdetoolkit/
- v2 Milestone: https://github.com/nims-dpfc/rdetoolkit/milestone/18 (#435–#454)
- v2 Plan: `local/develop/v2/Plan.md`
- Contributing Guide: `CONTRIBUTING.md`

---

## Local Rules

- Think in English, respond in Japanese.
- Never modify v1 test files (`tests/` root) — v2 tests go to `tests/v2/` only.
- Direct Refactor phases: `tox -e py312-module` must pass before branch merge.
- Rust phases: `maturin develop` must succeed before any Python tests.
- `core/result.py` must never be created — use existing `result.py`.
- Only primitive types cross the Rust boundary — Python objects stay Python-side.
