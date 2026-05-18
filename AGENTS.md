# AGENTS.md

Development rules for all agents working in this repository — including Claude Code,
Codex (via MCP), and any other AI-assisted tooling. Read this file in full before
writing any code or tests.

> **Claude Code workflow guidance** (agent orchestration, phase classification, MCP
> setup) lives in **CLAUDE.md**. This file covers only the coding and testing rules
> that every agent must follow regardless of how it is invoked.

---

## 1. Project Overview

RDEToolKit is a Python package for creating workflows of RDE (Research Data Express)
structured programs. It enables researchers to register, process, and visualize
experimental data in RDE format.

The project is a **Rust + Python hybrid library** using PyO3/Maturin. Performance-
critical operations (image processing, encoding detection, file system ops, and from
v2: DAG graph algorithms) are implemented in Rust and exposed to Python via PyO3
bindings.

**Current status:**
- **v1.x** — stable, maintenance mode. Do not break existing behaviour.
- **v2.x** — active development under `develop/v2`. Plan: `local/develop/v2/Plan.md`.

---

## 2. Development Environment Setup

```bash
cd <local rdetoolkit repo>
uv sync
source .venv/bin/activate
pre-commit install
```

### 2.1 Common Commands

```bash
# Build Rust extension + Python package (required after any Rust change)
maturin develop

# Full test suite (v1 + v2)
tox -e py312-module

# Specific test file
tox -e py312-module -- tests/v2/core/test_dag.py -v

# Linting / type checking
tox -e py312-ruff
tox -e py312-mypy

# Complexity check
tox -e lizard

# Docs
mkdocs serve
```

---

## 3. Code Formatting & Linters

Tools: **Ruff** (lint + format) and **mypy** (strict type checking).

### 3.1 Coding Standards

- **All comments and docstrings must be written in English.**
- Avoid redundant comments — explain *why*, not *what*.
- Use Unix-style line endings (LF) for all files.
- **Google Style docstrings** are mandatory on all public APIs.
- **Type annotations are required everywhere** — mypy strict mode is enforced.

### 3.2 v2-Specific Python Constraints

| Rule | Detail |
|------|--------|
| `types.py` is append-only | Never modify existing content. Add new types below existing definitions. |
| `errors.py` is append-only | Never modify existing content. Add new error codes below existing definitions. |
| `core/result.py` must not be created | Use existing `result.py` (`Success`, `Failure`, `Result`) as-is. |
| Re-export pattern for direct refactors | When moving functions to `utils/`, add `from rdetoolkit.utils.<module> import <fn>  # noqa: F401` to the original file. |
| `@node` transparency | Decorated functions must remain directly callable without the framework. |
| v1 public API must not break | Any phase touching v1 files requires `tox -e py312-module` to pass before merge. |

### 3.3 Rust Coding Standards

- Follow standard Rust idioms — code must be `clippy` clean.
- No `unwrap()` in library code — always return `PyResult<T>`.
- All `#[pyclass]` types must have a corresponding `.pyi` stub in `rdetoolkit-core/`.
- Rust → Python errors must be converted to `PyErr` via `PyResult<T>`.
- **Pass only primitive types across the Python ↔ Rust boundary**: `str`, `int`,
  `bool`, `list[str]`, `dict[str, str]`. Never pass Python objects (`NodeSpec`,
  `RunContext`, etc.) into Rust — keep those on the Python side.
- Rust unit tests go in `#[cfg(test)]` modules within each `.rs` file.
- After any Rust change, run `maturin develop` before running Python tests.

---

## 4. Rust / Python Language Boundary

### 4.1 Division of Responsibility

| Domain | Language | Reason |
|--------|----------|--------|
| DAG graph structure (nodes, edges, adjacency) | **Rust** | `petgraph` crate — type-safe, battle-tested graph algorithms |
| Topological sort | **Rust** | Pure algorithm; `petgraph::algo::toposort` |
| Cycle detection | **Rust** | DFS-based; correctness critical |
| DAG structural validation (unconnected nodes, duplicate IDs) | **Rust** | Structural checks benefit from Rust type guarantees |
| ExecutionPlan node ordering | **Rust** | Derived from topological sort |
| Image processing / thumbnail generation | **Rust** | v1 continuation (`imageutil.rs`) |
| Encoding detection | **Rust** | v1 continuation (`charset_detector.rs`) |
| File system operations | **Rust** | v1 continuation (`fsops.rs`) |
| `@node` / `@flow` decorators | **Python** | Requires `inspect.signature`, `functools.wraps`, metaprogramming |
| Trace proxy (`NodeProxy`, `OutputProxy`) | **Python** | Requires `__iter__`, `ast`/`dis`, Python object references |
| DI resolution | **Python** | Requires `typing.get_type_hints` introspection |
| Type checking in Compiler (strict/warn/off) | **Python** | Compares Python type annotations |
| Runner lifecycle | **Python** | Orchestration, exception handling, context management |
| Domain services (Config, Mode, Paths) | **Python** | pydantic, Python ecosystem |
| Plugin system | **Python** | `importlib.metadata.entry_points` |
| CLI | **Python** | typer — Python standard |
| DataFrame operations | **Python** | pandas/polars — Python data science ecosystem |

### 4.2 Python ↔ Rust Boundary Rules

```
Python layer (core/dag.py)            Rust layer (rdetoolkit-core/dag.rs)
┌───────────────────────────┐         ┌──────────────────────────────────┐
│ class DAG:                │         │ #[pyclass]                       │
│   def __init__(self):     │         │ struct RustDAG {                 │
│     self._rust = RustDAG()│         │   graph: DiGraph<String, ...>    │
│     self._specs: dict     │         │ }                                │
│                           │         │                                  │
│   def add_node(id, spec): │         │ #[pymethods]                     │
│     self._rust.add_node(id)         │ fn add_node(&mut self, id: &str) │
│     self._specs[id] = spec│         │ fn add_edge(&mut self, ...)      │
│                           │         │ fn topological_sort(&self)       │
│   def topological_sort(): │         │   -> PyResult<Vec<String>>       │
│     return self._rust     │         │ fn detect_cycle(&self)           │
│       .topological_sort() │         │   -> Option<Vec<String>>         │
│                           │         │ fn validate(&self)               │
│   # Python responsibilities:        │   -> Vec<HashMap<String,String>> │
│   # - NodeSpec management │         │                                  │
│   # - Type info storage   │         │ # Rust responsibilities:         │
│   # - Python obj refs     │         │ # - Graph structure              │
└───────────────────────────┘         │ # - Algorithms                   │
                                      │ # - Structural validation        │
                                      └──────────────────────────────────┘
```

**Key rules:**
1. Rust receives only node IDs (`str`) — never `NodeSpec` or Python objects.
2. Python `DAG` class wraps `RustDAG` and maintains the `NodeSpec` dict Python-side.
3. Rust errors are converted to Python exceptions via `PyResult`.
4. Keep `.pyi` stubs up to date whenever the Rust public API changes.

### 4.3 Rust Module Structure

```
rdetoolkit-core/
├── lib.rs                  # PyO3 module registration
├── charset_detector.rs     # [v1] Encoding detection
├── imageutil.rs            # [v1] Image processing
├── imageutil/
│   └── processing.rs
├── fsops.rs                # [v1] Directory operations
└── dag.rs                  # [v2 NEW] DAG + graph algorithms (petgraph backend)
```

### 4.4 Cargo.toml Dependencies

```toml
[dependencies]
# v1 (unchanged)
pyo3 = { version = "0.28.2", features = ["extension-module"] }
image = "0.25.9"
chardetng = "0.1.17"
encoding_rs = "0.8.35"
tempfile = "3.26.0"

# v2 additions
petgraph = "0.7"   # DAG data structure + graph algorithms
```

### 4.5 RustDAG Type Stub (core.pyi addition)

```python
# Additions to rdetoolkit-core/core.pyi for v2
class RustDAG:
    def __init__(self) -> None: ...
    def add_node(self, node_id: str) -> None: ...
    def add_edge(
        self,
        from_id: str,
        to_id: str,
        from_port: str,
        to_port: str,
    ) -> None: ...
    def node_ids(self) -> list[str]: ...
    def edge_list(self) -> list[tuple[str, str, str, str]]: ...
    def topological_sort(self) -> list[str]: ...     # raises RdeGraphError on cycle
    def detect_cycle(self) -> list[str] | None: ...  # None if acyclic
    def predecessors(self, node_id: str) -> list[str]: ...
    def successors(self, node_id: str) -> list[str]: ...
    def validate(self) -> list[dict[str, str]]: ...  # list of validation errors
    def node_count(self) -> int: ...
    def edge_count(self) -> int: ...
```

---

## 5. Documentation Guidelines

All public APIs require **Google Style** docstrings:

```python
def topological_sort(self) -> list[str]:
    """Return nodes in topological order.

    Delegates to RustDAG for O(V+E) performance via petgraph.

    Returns:
        List of node IDs in dependency order (sources first).

    Raises:
        RdeGraphError: If the DAG contains a cycle.
    """
```

---

## 6. Branch Strategy

### 6.1 Branch Naming

```bash
# v2 development (one branch per phase)
git checkout -b v2/phase-<N> origin/develop/v2

# v1 maintenance / issue-based
git checkout -b develop/v<x.y.z>/<prefix>/<short-descriptor> origin/develop/v<x.y.z>
```

### 6.2 Branch Prefixes

| Prefix | Purpose |
|--------|---------|
| `feature/` | New feature |
| `bugfix/` / `fix/` | Bug fix |
| `hotfix/` | Critical urgent fix |
| `release/` | Release preparation |
| `chore/` | Refactoring / maintenance |
| `refactor/` | Code refactoring |
| `test/` | Test-only changes |
| `docs/` | Documentation |
| `ci/` | CI/CD configuration |
| `perf/` | Performance improvements |
| `experiment/` | Proof-of-concept |

### 6.3 Commit Message Format

```bash
# Issue-based (v1 maintenance)
git commit -m "#<issue-number> <brief description in English>"

# Phase-based (v2 development)
git commit -m "feat(v2/phase-1): implement RustDAG with petgraph backend"
git commit -m "feat(v2/phase-1): add @node decorator and NodeSpec"
git commit -m "test(v2/phase-1): PBT for DAG topological sort invariants"
```

### 6.4 Pull Request Rules

- **Never target `main` directly.** PRs must target `develop/v<x.y.z>` or `develop/v2`.
- All CI checks must pass before requesting review.
- Phases with Rust changes: include `maturin develop && tox -e py312-module` output.
- Direct Refactor phases (2.2, 3.17, 4.x, 5.2, 5.5): confirm v1 tests are GREEN.

---

## 7. Testing

### 7.1 Test Commands

```bash
# After any Rust change — always rebuild first
maturin develop && tox -e py312-module

# v2 tests only
tox -e py312-module -- tests/v2/ -v

# Single file
tox -e py312-module -- tests/v2/core/test_dag.py -v

# Property-based tests only
pytest tests/v2/ -m property -v

# CI Hypothesis profile
HYPOTHESIS_PROFILE=ci pytest tests/v2/ -m property -v
```

### 7.2 Test Directory Structure

```
tests/
├── (v1 tests — never modify)
└── v2/
    ├── core/       # @node, @flow, DAG (Python wrapper + RustDAG), Compiler, Executor
    ├── domain/     # Config, Mode, Paths, Invoice, Validation
    ├── runner/     # Runner, Iterator, Compat bridge
    ├── report/     # Events, RunReport
    ├── nodes/      # Built-in @node wrappers
    ├── plugin/     # Plugin system
    ├── testing/    # Test helpers
    ├── cli/        # CLI commands
    ├── property/   # PBT-only tests (@pytest.mark.property)
    └── integration/# E2E tests (@pytest.mark.integration)
```

**All v2 tests go under `tests/v2/`. Never touch `tests/` root files.**

### 7.3 TDD Cycle (Mandatory for v2)

```
RED    → Write failing Python tests (targeting Rust binding or Python API)
GREEN  → Implement: Rust first (maturin develop), then Python wrapper
REFACTOR → Improve design while keeping tests green
PBT    → Add Hypothesis property tests for algorithmic invariants
```

Red phase for Rust-backed components targets the Python binding:
```python
# Fails because RustDAG does not exist yet — correct Red state
from rdetoolkit.core.dag import DAG, RdeGraphError

def test_dag_self_loop_raises() -> None:
    dag = DAG()
    dag.add_node("a", spec=None)
    with pytest.raises(RdeGraphError):
        dag.add_edge("a", "a", from_port="out", to_port="in")
```

### 7.4 Mandatory Test Requirements

1. **Write EP/BV tables before writing tests.**
2. Each table row maps to at least one test case.
3. Failing (negative) cases ≥ passing (positive) cases.
4. Required viewpoints:
   - Normal (happy path)
   - Abnormal / error paths
   - Boundary values (empty graph, single node, max edges)
   - Rust ↔ Python error conversion (for Rust-backed components)
   - Exception type and message verification
5. **Given/When/Then comments** in every test.
6. **Python branch coverage 100%**; Rust logic tested in `#[cfg(test)]` blocks.

### 7.5 Test Templates

**(A) EP Table**

| API | Partition | Rationale | Expected | Test ID |
|-----|-----------|-----------|---------|---------|
| `DAG.add_edge` | valid distinct nodes | normal | edge recorded | `TC-EP-001` |
| `DAG.add_edge` | self-loop | structurally invalid | raises `RdeGraphError` | `TC-EP-002` |
| `DAG.topological_sort` | DAG with cycle | invalid state | raises `RdeGraphError` | `TC-EP-003` |

**(B) BV Table**

| API | Boundary | Rationale | Expected | Test ID |
|-----|----------|-----------|---------|---------|
| `DAG.topological_sort` | 0 nodes | empty | `[]` | `TC-BV-001` |
| `DAG.topological_sort` | 1 node, 0 edges | minimal | `[node]` | `TC-BV-002` |

**(C) pytest style**

```python
class TestDag:
    def test_add_edge_valid_records_edge__tc_ep_001(self) -> None:
        """TC-EP-001: Valid edge is recorded in the DAG."""
        # Given: empty DAG with two nodes
        dag = DAG()
        dag.add_node("a", spec=None)
        dag.add_node("b", spec=None)
        # When: adding a valid edge
        dag.add_edge("a", "b", from_port="out", to_port="in")
        # Then: successor relationship established
        assert "b" in dag.successors("a")

    def test_add_edge_self_loop_raises__tc_ep_002(self) -> None:
        """TC-EP-002: Self-loop raises RdeGraphError (Rust cycle detection)."""
        # Given: DAG with one node
        dag = DAG()
        dag.add_node("a", spec=None)
        # When / Then: self-loop rejected
        with pytest.raises(RdeGraphError, match="cycle"):
            dag.add_edge("a", "a", from_port="out", to_port="in")
```

### 7.6 Property-Based Testing (PBT)

| Component | Invariants |
|-----------|-----------|
| `RustDAG` — topological sort | Each node appears exactly once; A before B when A→B exists |
| `RustDAG` — cycle detection | Detected iff cycle exists; never fires on acyclic graphs |
| `core/compiler.py` | Valid DAG → no compile errors; invalid → always errors |
| `core/context.py` — DI resolution | Resolved inputs satisfy declared types |
| `runner/iterator.py` | Tile count matches; no tile skipped or duplicated |
| `utils/` — data transformation | Idempotence, round-trip, length preservation |

```python
from hypothesis import given, strategies as st
import pytest

@pytest.mark.property
class TestRustDagProperties:
    @given(
        node_ids=st.lists(
            st.text(min_size=1, max_size=8, alphabet="abcdefghij"),
            min_size=0, max_size=15, unique=True,
        )
    )
    def test_topological_sort_contains_each_node_exactly_once(
        self, node_ids: list[str]
    ) -> None:
        """Property: sort contains each node exactly once (no edges = always acyclic)."""
        dag = DAG()
        for nid in node_ids:
            dag.add_node(nid, spec=None)
        order = dag.topological_sort()
        assert sorted(order) == sorted(node_ids)
        assert len(order) == len(set(order))
```

Hypothesis profiles:

| Profile | `max_examples` | Deadline |
|---------|---------------|---------|
| `dev` (default) | 100 | none |
| `ci` | 50 | 5000 ms |

### 7.7 PR Checklist

- [ ] EP and BV tables provided, linked to Test IDs
- [ ] All table rows implemented as tests
- [ ] Failing cases ≥ passing cases
- [ ] Given/When/Then comments in every test
- [ ] Rust boundary error conversion tested (Rust-backed components)
- [ ] Exception type and message verified
- [ ] Python branch coverage = 100% for new code
- [ ] Rust `#[cfg(test)]` unit tests present for new Rust functions
- [ ] PBT added where applicable (§7.6)
- [ ] `maturin develop` succeeds (Rust changes only)
- [ ] v1 tests GREEN: `tox -e py312-module` (Direct Refactor phases only)

---

## 8. v2 Implementation Rules

### 8.1 Module Placement

| Code belongs in | When |
|----------------|------|
| `rdetoolkit-core/dag.rs` | DAG graph structure, topological sort, cycle detection, structural validation |
| `src/rdetoolkit/core/` | `@node`, `@flow`, Python DAG wrapper, Compiler, Executor, Context |
| `src/rdetoolkit/domain/` | Config, Mode, Paths, Validation |
| `src/rdetoolkit/runner/` | Runner lifecycle, DataTile iterators, compat bridge |
| `src/rdetoolkit/report/` | EventSink, RunReport |
| `src/rdetoolkit/nodes/` | Built-in `@node` wrappers |
| `src/rdetoolkit/utils/` | Utilities from `rde2util.py`, `fileops.py` |
| `src/rdetoolkit/plugin/` | Plugin discovery and registry |
| `src/rdetoolkit/testing/` | Public test helpers |
| `tests/v2/` | All new v2 tests |

### 8.2 Forbidden Actions

- ❌ Create `src/rdetoolkit/core/result.py` — use existing `result.py`
- ❌ Modify existing lines in `types.py` or `errors.py` — append only
- ❌ Touch any file under `tests/` root — v1 tests are read-only
- ❌ Commit directly to `develop/v2` — always use `v2/phase-N`
- ❌ Merge a Direct Refactor phase without `tox -e py312-module` confirmation
- ❌ Pass Python objects (`NodeSpec`, `RunContext`, etc.) across the Rust boundary
- ❌ Use `unwrap()` in Rust library code — always use `PyResult<T>`
- ❌ Forget to update `.pyi` stubs after changing the Rust public API

### 8.3 Required Implementation Patterns

**Rust PyO3 class skeleton (dag.rs):**
```rust
use petgraph::algo::toposort;
use petgraph::graph::DiGraph;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

/// Edge metadata stored in the petgraph DiGraph.
/// Represents the port-level connection between two nodes.
/// Never exposed to Python directly — queried via edge_list().
struct EdgeInfo {
    from_port: String,
    to_port: String,
}

#[pyclass]
pub struct RustDAG {
    graph: DiGraph<String, EdgeInfo>,
    node_index: std::collections::HashMap<String, petgraph::graph::NodeIndex>,
}

#[pymethods]
impl RustDAG {
    #[new]
    pub fn new() -> Self { ... }

    pub fn add_edge(
        &mut self,
        from_id: &str,
        to_id: &str,
        from_port: &str,
        to_port: &str,
    ) -> PyResult<()> {
        // Immediately check for cycle after adding edge
        let from_idx = self.node_index.get(from_id).ok_or_else(|| ...)?;
        let to_idx   = self.node_index.get(to_id).ok_or_else(|| ...)?;
        self.graph.add_edge(*from_idx, *to_idx, EdgeInfo {
            from_port: from_port.to_string(),
            to_port:   to_port.to_string(),
        });
        if toposort(&self.graph, None).is_err() {
            // Remove the edge we just added and raise CycleError
            self.graph.remove_edge(...);
            return Err(PyValueError::new_err("DAG contains a cycle"));
        }
        Ok(())
    }

    pub fn topological_sort(&self) -> PyResult<Vec<String>> {
        toposort(&self.graph, None)
            .map(|order| order.iter().map(|i| self.graph[*i].clone()).collect())
            .map_err(|_| PyValueError::new_err("DAG contains a cycle"))
    }

    /// Returns list of (from_id, to_id, from_port, to_port) tuples.
    pub fn edge_list(&self) -> Vec<(String, String, String, String)> { ... }
}
```

**Python DAG wrapper (core/dag.py):**
```python
from rdetoolkit._core import RustDAG
from rdetoolkit.core.node import NodeSpec

class DAG:
    """Python DAG wrapper. Delegates graph ops to RustDAG; manages NodeSpec Python-side."""

    def __init__(self) -> None:
        self._rust = RustDAG()
        self._specs: dict[str, NodeSpec | None] = {}

    def add_node(self, node_id: str, spec: NodeSpec | None) -> None:
        self._rust.add_node(node_id)   # only str crosses the boundary
        self._specs[node_id] = spec    # Python object stays Python-side

    def topological_sort(self) -> list[str]:
        return self._rust.topological_sort()
```

**Re-export pattern (Direct Refactor):**
```python
# rde2util.py — after Phase 5.2
from rdetoolkit.utils.encoding import detect_encoding, convert_encoding  # noqa: F401
from rdetoolkit.utils.cast import cast_metadata_value  # noqa: F401
```

**Result type — use existing:**
```python
from rdetoolkit.result import Success, Failure, Result
```

### 8.4 v1 Safety Rules

| Scenario | Required action before merge |
|----------|------------------------------|
| Rust-only changes (new `dag.rs`) | `maturin develop && tox -e py312-module -- tests/v2/` |
| New Python dirs only | `tox -e py312-module -- tests/v2/` |
| Any existing v1 `.py` touched | `maturin develop && tox -e py312-module` (full suite, all GREEN) |

Phases with v1 impact: **2.2, 3.17, 4.x, 5.2, 5.5**

---

## 9. Complexity Limits

Enforced by `tox -e lizard`:

| File | Max cyclomatic complexity |
|------|--------------------------|
| `workflows.py` | 16 |
| `__main__.py` | 10 |
| All other Python files | 10 |

Keep v2 modules well under 10. Split any function exceeding 7.
Rust functions: no enforced limit, but prefer small focused functions.

---

## Notes for AI Agents

- Read this file in full before writing any code.
- **Codex**: you do not share context with Claude Code. All information must come from
  the task prompt, this file, and files you read from the workspace.
- For tasks touching `dag.rs` or any Rust file: run `maturin develop` to rebuild the
  extension before running Python tests. Tests will fail with stale bindings otherwise.
- For Rust-backed components, write Python-level tests calling the binding. Rust
  internals are tested in `#[cfg(test)]` blocks — not from Python.
- Never pass Python objects across the Rust boundary — only primitives.
- Always run the verification command from your task prompt before reporting completion.
- Never skip Red phase confirmation when implementing TDD tasks.
