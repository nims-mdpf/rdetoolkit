# AGENTS.md

Development rules for all agents working in this repository — including Claude Code,
Codex (via `codex` CLI), and any other AI-assisted tooling. Read this file in full
before writing any code or tests.

> **Claude Code workflow guidance** (agent orchestration, phase classification, Codex
> delegation and `/goal` usage) lives in **CLAUDE.md**. This file covers only the
> coding and testing rules that every agent must follow regardless of how it is
> invoked.

> **⚠️ Canonical design document**: v2 architecture is defined by
> **`local/develop/v2/Design.md`** (v2.1: eager execution + call-log recording,
> ADR-020/021/022 — no value lineage).
> The former plan (`Plan.md`) and the former design note (`20260210_raa_refactor_ja.md`)
> are **superseded**. If any instruction, memory, or training prior suggests
> implementing a Trace proxy, Build/Compile phases, or a pre-execution DAG —
> **that is the retired v1-of-v2 design. Do not implement it.**

---

## 1. Project Overview

RDEToolKit is a Python package for creating workflows of RDE (Research Data Express)
structured programs. It enables researchers to register, process, and visualize
experimental data in RDE format.

The project is a **Rust + Python hybrid library** using PyO3/Maturin. Performance-
critical v1 operations (image processing, encoding detection, file system ops) are
implemented in Rust and exposed to Python via PyO3 bindings.

**Current status:**
- **v1.x** — stable, maintenance mode. Do not break existing behaviour.
- **v2.x** — active development under `develop/v2`, **redesigned (2026-06)** around
  eager execution and call-log recording (v2.1). Canonical spec: `local/develop/v2/Design.md`.
  Phase instructions: `local/develop/v2/Phase{A..F}_prompts.md`.

**v2 execution model in one paragraph (memorize this):**
`@flow` functions are **plain Python executed eagerly** — `if`, loops, f-strings,
literal arguments, and default arguments all behave exactly as normal Python.
`@node` is a thin wrapper that registers a `NodeSpec` and records a runtime
`NodeCallRecord` when an active run exists. The DAG is **derived after the fact**
from call-log records as a Call Sequence (not a dataflow DAG, ADR-022), never
constructed before execution. The Runner owns the
RDE domain lifecycle (config → mode → validate → iterate tiles → flow call →
validate → `job.failed` / RunReport).

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
# Full test suite (v1 + v2) — the primary gate for everything
.venv/bin/tox -e py312-module

# v2 tests only
.venv/bin/tox -e py312-module -- tests/v2/ -v

# Specific test file
.venv/bin/tox -e py312-module -- tests/v2/core/ -v

# Linting / type checking
.venv/bin/tox -e py312-ruff
.venv/bin/tox -e py312-mypy

# Complexity check
.venv/bin/tox -e lizard

# Docs (error catalog pages are generated — never hand-edit)
python scripts/gen_error_docs.py --check
mkdocs serve

# Rust extension rebuild — ONLY needed if a v1 Rust file changed.
# v2.0 makes no Rust changes (dag.rs is frozen, see §4).
maturin develop
```

> Use `.venv/bin/tox` explicitly. A stale `tox` on PATH has caused silent
> environment mismatches in the past.

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
| `types.py` is append-only | Never modify existing v1 lines. v2 canonical types per Design §4.2. |
| `errors.py` is append-only | Single int-coded catalog per Design §9. Old `E001–E025` / `E_CYCLE` IDs are retired markers — never delete, never reuse. |
| `errors.pyi` is append-only | Stub files follow the same rule as their modules. Declarations must never silently disappear. |
| `core/result.py` must not be created | Use existing `result.py` (`Success`, `Failure`, `Result`) as-is. |
| Re-export pattern for direct refactors | When moving functions, keep `from rdetoolkit.<new> import <fn>  # noqa: F401` in the original module. |
| `@node` transparency | Decorated functions remain plain functions: direct calls pass args verbatim, exceptions propagate unwrapped when no run is active, `functools.wraps` metadata preserved. |
| `@flow` is a plain function | Direct invocation is a normal call. No trace mode, no proxies, ever. |
| No DI inside `@node` | Reserved types are injected at the **flow boundary only** (Design §4.3). Nodes receive everything via explicit arguments. |
| `OutputContext` construction | Only via `OutputContext.from_resource_paths()`. Directory creation belongs to the Runner (step 4a), never to the factory. |
| Error codes | Raise only `RdeError` subclasses carrying an int code present in `ERROR_CATALOG`. Never invent ad-hoc codes or string-prefixed schemes. |
| Schemas carry `schema_version` | Any change to Event / RunReport / NodeCallRecord JSON requires a version bump and a consumer-compat note. |
| v1 public API must not break | Any phase touching v1 files requires full `tox -e py312-module` GREEN before merge. |
| No `DeprecationWarning` on the v1 path | `run(custom_dataset_function=...)` stays warning-free in v2.0 (Design §11). |

### 3.3 Rust Coding Standards

v2.0 introduces **no new Rust code**. These rules apply to v1 maintenance only:

- Follow standard Rust idioms — code must be `clippy` clean.
- No `unwrap()` in library code — always return `PyResult<T>`.
- All `#[pyclass]` types must have a corresponding declaration in `_core.pyi`.
- Pass only primitive types across the Python ↔ Rust boundary.
- Rust unit tests go in `#[cfg(test)]` modules within each `.rs` file.
- After any Rust change, run `maturin develop` before running Python tests.

---

## 4. Rust / Python Language Boundary

### 4.1 Division of Responsibility (v2 — post ADR-020)

| Domain | Language | Status |
|--------|----------|--------|
| Image processing / thumbnails (`imageutil.rs`) | Rust | v1, unchanged |
| Encoding detection (`charset_detector.rs`) | Rust | v1, unchanged |
| File system operations (`fsops.rs`) | Rust | v1, unchanged |
| DAG structure / algorithms (`dag.rs`) | Rust | **FROZEN — internal, not on any v2.0 code path** |
| `@node` / `@flow` decorators, registries | Python | v2 |
| Call-log recording (CallLogRecorder, no lineage) | Python | v2 |
| Flow-boundary DI | Python | v2 |
| Runner lifecycle, tile iterators | Python | v2 |
| Call-sequence rendering (`report/graph_render.py`) | Python | v2 — pure Python, tens of nodes, no perf concern |
| Domain services, plugins, CLI (typer), DataFrames | Python | v2 |

### 4.2 dag.rs Freeze Rules

- `dag.rs` is **not deleted** but carries an `INTERNAL — not used in v2.0 critical
  path (ADR-020)` header and is **not registered** in the PyO3 module.
- ❌ Never import `RustDAG` from any v2 module. Graph work derives from the call log
  records in pure Python.
- ❌ Never "optimize" call-log/graph code by reviving `RustDAG` without an
  explicit new ADR superseding ADR-020.
- The compiled extension module is **`rdetoolkit._core`**. The type stub is
  **`src/rdetoolkit/_core.pyi`**. The former `core.pyi` was removed in Phase A —
  do not recreate it.

---

## 5. Documentation Guidelines

All public APIs require **Google Style** docstrings:

```python
def render_call_sequence(records: list[NodeCallRecord]) -> str:
    """Render the run's call sequence from call-log records.

    Records are ordered by their run-global ``seq`` (Design v2.1 §3.4);
    the output is a Call Sequence, not a dataflow DAG (ADR-022).

    Returns:
        Mermaid source for the per-tile call sequence.
    """
```

Additional rules:
- The error-code reference in docs is **generated** by `scripts/gen_error_docs.py`.
  Never hand-write or hand-edit error tables in docs.
- Code examples in user docs must be covered by doctest or an executed test.
- When citing the design, reference sections as `Design §N.M`.

---

## 6. Branch Strategy

### 6.1 Branch Naming

```bash
# v2 development (one branch per phase, letter-indexed)
git checkout -b v2/phase-<a|b|c|d|e|f> origin/develop/v2

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
git commit -m "feat(v2/phase-c): eager @node/@flow with registry (Design §3.1-3.3)"
git commit -m "test(v2/phase-c): PBT for provenance edge reconstruction invariants"
```

### 6.4 Worktree Rules

- **Create worktrees with `git gtr new <branch> --from <base>`** — never plain
  `git worktree add`. gtr's postcreate hooks provide, per worktree:
  `.venv` (uv, Python pinned), the symlink `local -> ~/github/rdetoolkit/local`,
  and a copy of `.claude/`.
- `local/develop/` therefore has exactly **one canonical copy** in the main repo
  (`~/github/rdetoolkit/local/develop/`), shared by every worktree via the
  symlink. Never create a real `local/` directory inside a worktree; if one
  exists (worktree made without gtr), sync its contents back to the main repo
  and replace it with the symlink.
- **`local/develop/` is never committed or pushed.** It is gitignored (`local/`);
  `git add -f local/...` is forbidden. Session artifacts (surveys, task files,
  decision records) stay under `local/develop/` as local-only documents.

### 6.5 Pull Request Rules

- **Never target `main` directly.** PRs must target `develop/v<x.y.z>` or `develop/v2`.
  (Sole exception: the Phase A "B5 settlement" PR that restores/hardens v1 tests
  goes to `main` via the normal human-review process.)
- All CI checks must pass before requesting review.
- Phase merges into `develop/v2` use `--no-ff` and require the full suite GREEN —
  this is a **CI-enforced phase gate**, not an honor-system checklist.
- Direct-Refactor work (anything touching v1 files): confirm v1 tests GREEN and
  paste the tail of the tox output into the PR description.

### 6.6 Release / Tagging Rules

> Background: on 2026-07 a `v2.0.0a1` tag was pushed while `pyproject.toml`
> still said `2.0.0`, so an unintended **2.0.0** was published to PyPI (now
> yanked). PyPI file names can never be reused, so the version number `2.0.0`
> is permanently burned. These rules exist to make that impossible to repeat.

- **Version sources that must always agree** (canonical PEP 440 form, e.g.
  `2.0.0a1` — never `2.0.0.a1`):
  1. `pyproject.toml` `[project].version` (maturin stamps the wheel/sdist with this)
  2. `src/rdetoolkit/__init__.py` `__version__`
  3. the git tag (`v` + version, e.g. `v2.0.0a1`)
- **A version bump is a normal committed change**: update both source files in
  one commit *before* tagging; the tag points at that commit.
- **Before pushing any tag**, run and paste the output of:
  `python scripts/check_version_consistency.py --tag v<version>`
- CI enforces the same check: the `check-version` job in
  `.github/workflows/pypi-release.yml` gates every build, and the release jobs
  additionally verify that the built artifact file names match the tag. Never
  bypass, weaken, or `continue-on-error` these gates.
- **Only the human operator creates and pushes tags.** Agents (Claude, Codex)
  must never run `git tag` or `git push --tags`; they stop and report the
  verified version state instead.
- Never re-point (delete + recreate) a tag that has already produced a PyPI
  upload; pick the next free version instead.

---

## 7. Testing

### 7.1 Test Commands

```bash
# Full suite (v1 + v2) — required GREEN at every session end
.venv/bin/tox -e py312-module

# v2 only / single file
.venv/bin/tox -e py312-module -- tests/v2/ -v
.venv/bin/tox -e py312-module -- tests/v2/golden/ -v

# Property-based tests only
pytest tests/v2/ -m property -v
HYPOTHESIS_PROFILE=ci pytest tests/v2/ -m property -v
```

### 7.2 Test Directory Structure

```
tests/
├── (v1 tests — never modify)
└── v2/
    ├── core/       # @node, @flow (eager), registry, provenance, injection
    ├── domain/     # Config, Mode, Paths, Invoice, Validation
    ├── runner/     # Lifecycle, iterators, error policy, aggregator, finalize
    ├── report/     # Events, RunReport, graph rendering
    ├── nodes/      # Built-in nodes
    ├── plugin/     # Plugin discovery
    ├── testing/    # Public test helpers
    ├── cli/        # CLI commands
    ├── golden/     # v1↔v2 directory-tree parity (Design §6.4)
    ├── e2e/        # run(flow=...) end-to-end
    ├── property/   # PBT-only tests (@pytest.mark.property)
    └── fixtures/   # Shared fixtures incl. dummy plugin package
```

**All v2 tests go under `tests/v2/`. Never touch `tests/` root files.**

### 7.3 TDD Cycle (Mandatory for v2)

```
RED      → Write failing tests against the public Python API
GREEN    → Implement the minimal change
REFACTOR → Improve design while keeping tests green
PBT      → Add Hypothesis property tests for invariants (provenance, iterators)
```

Red-phase confirmation is mandatory before any implementation:
```bash
.venv/bin/tox -e py312-module -- tests/v2/<new_test>.py -v 2>&1 | tail -20
# Must show FAILED or ImportError before you write implementation code
```

### 7.4 Mandatory Test Requirements

1. **Write EP/BV tables before writing tests.**
2. Each table row maps to at least one test case.
3. Failing (negative) cases ≥ passing (positive) cases.
4. Required viewpoints:
   - Normal (happy path)
   - Abnormal / error paths (error **code** and exception type asserted)
   - Boundary values (0 tiles, 1 tile, empty inputs, duplicate node ids)
   - Eager-semantics regressions (the legacy-B2 family: `if`/loop/f-string/
     literal-arg/default-arg/container patterns must behave as plain Python)
   - Contract parity (golden directory trees, `job.failed` format)
5. **Given/When/Then comments** in every test.
6. **Branch coverage ≥ 95 % for new v2 code** (single canonical figure — the old
   95 %/100 % contradiction is resolved at 95 %, Design §13).

### 7.5 Test Templates

**(A) EP Table**

| API | Partition | Rationale | Expected | Test ID |
|-----|-----------|-----------|---------|---------|
| `@node` direct call | plain args | transparency | returns value verbatim | `TC-EP-001` |
| node registry | duplicate id | invalid | raises `RdeRegistryError` (E2001) | `TC-EP-002` |
| flow DI | reserved name, wrong type | invalid | raises `RdeRegistryError` (E2004) | `TC-EP-003` |

**(B) BV Table**

| API | Boundary | Rationale | Expected | Test ID |
|-----|----------|-----------|---------|---------|
| iterator | 0 input files (multidatatile) | empty | 0 tiles, status success | `TC-BV-001` |
| provenance | same node called twice | minimal repeat | distinct `call_id` `#1`,`#2` | `TC-BV-002` |

**(C) pytest style**

```python
class TestNodeTransparency:
    def test_direct_call_passes_args_verbatim__tc_ep_001(self) -> None:
        """TC-EP-001: @node function behaves as a plain function when called directly."""
        # Given: a decorated node and no active run
        # When: calling it directly with a literal argument
        result = normalize(make_df(), threshold=0.3)
        # Then: the value is returned verbatim and nothing was recorded
        assert isinstance(result, pd.DataFrame)
```

### 7.6 Property-Based Testing (PBT)

| Component | Invariants |
|-----------|-----------|
| Provenance edge reconstruction | producer call precedes consumer call; reconstructed graph is acyclic; each call_id unique |
| Provenance determinism | same flow + same input ⇒ identical call_id sequence and edge set |
| `runner/iterator.py` | tile count matches mode semantics; no tile skipped or duplicated |
| Error policy | `continue` ⇒ status ∈ {success, partial, failed} consistent with per-tile results; `fail_fast` ⇒ stops at first failure |
| `utils/` transformations | idempotence, round-trip, length preservation |

**Generate branching and merging flow shapes** — not only linear chains — when
testing provenance (the chain-only bias was a known audit finding).

Hypothesis profiles (registered in `tests/v2/conftest.py`):

| Profile | `max_examples` | Deadline |
|---------|---------------|---------|
| `dev` (default) | 100 | none |
| `ci` | 50 | 5000 ms |

### 7.7 PR Checklist

- [ ] EP and BV tables provided, linked to Test IDs
- [ ] All table rows implemented as tests
- [ ] Failing cases ≥ passing cases
- [ ] Given/When/Then comments in every test
- [ ] Error code (int) and exception type verified for every error path
- [ ] Eager-semantics regression cases covered where flow behaviour is touched
- [ ] Branch coverage ≥ 95 % for new code
- [ ] PBT added where applicable (§7.6)
- [ ] v1 tests GREEN: full `tox -e py312-module` output tail attached
- [ ] No new dependency on `rdetoolkit._core` from v2 modules

---

## 8. v2 Implementation Rules

### 8.1 Module Placement

| Code belongs in | When |
|----------------|------|
| `src/rdetoolkit/core/` | `@node`, `@flow`, `registry.py`, `provenance.py`, `injection.py`, `context.py` |
| `src/rdetoolkit/domain/` | Config, Mode, Paths, Validation (v1-faithful ports) |
| `src/rdetoolkit/runner/` | `lifecycle.py`, `config_loader.py`, `mode_resolver.py`, `paths.py`, `iterator.py`, `execute.py`, `aggregator.py`, `finalize.py` |
| `src/rdetoolkit/report/` | Events, RunReport, `graph_render.py` |
| `src/rdetoolkit/nodes/` | Built-in nodes (io / structured / meta / image / plot) |
| `src/rdetoolkit/protocols/` | Canonical Protocols (Design §5.2) + `as_node` |
| `src/rdetoolkit/plugin/` | Plugin discovery via entry_points |
| `src/rdetoolkit/testing/` | Public test helpers (`run_flow`) |
| `src/rdetoolkit/cli/` | typer CLI |
| `tests/v2/` | All new v2 tests |

### 8.2 Forbidden Actions

- ❌ Implement a Trace proxy, `NodeProxy`/`OutputProxy`, Build/Compile phase, or any
  pre-execution DAG construction — **retired design (ADR-020)**
- ❌ Import or use `RustDAG` / `rdetoolkit._core` from any v2 module
- ❌ Create `src/rdetoolkit/core/result.py` — use existing `result.py`
- ❌ Modify existing lines in `types.py`, `errors.py`, or `errors.pyi` — append only
- ❌ Touch any file under `tests/` root — v1 tests are read-only
  (sole exception: the Phase A B5 settlement reverting them to `main`)
- ❌ Commit directly to `develop/v2` — always use `v2/phase-<letter>`
- ❌ Merge any phase without full `tox -e py312-module` GREEN
- ❌ Inject reserved types inside `@node` — flow boundary only
- ❌ Construct `OutputContext` directly — factory only
- ❌ Emit `DeprecationWarning` from the v1 `custom_dataset_function` path
- ❌ Raise errors without an `ERROR_CATALOG` int code
- ❌ Hand-edit generated error docs, or copy the error table into prose docs
- ❌ Build `RunReport` from `EventSink` output — aggregate from primary results
  (Design §8.2)

### 8.3 Required Implementation Patterns

**Eager `@node` (plain function + registration + recording hook):**
```python
from rdetoolkit import node

@node(tags=["io"], version="1.0.0")
def read_csv(paths: InputPaths) -> tuple[Metadata, pd.DataFrame]:
    """Read CSV from input paths."""
    ...
# read_csv(make_paths())  ← works directly; recorded only inside an active run
```

**Eager `@flow` (plain Python — all syntax allowed):**
```python
from rdetoolkit import flow

@flow
def pipeline(paths: InputPaths, out: OutputContext, config: RdeConfig) -> None:
    meta, df = read_csv(paths)
    if config.custom.get("normalize", True):     # plain if — fine
        df = normalize(df, threshold=0.3)        # literal arg — fine
    for col in df.columns:                       # plain loop — fine
        plot_lines(df[col], out, name=f"{col}.png")
    save_csv(df, out, "structured.csv")
```

**Reserved-type injection happens once, at the flow boundary (Runner side):**
```python
kwargs = resolve_flow_params(flow_fn, run_context)   # E2003/E2004 on mismatch
flow_fn(**kwargs)                                    # eager call — that's it
```

**Protocol adapter:**
```python
from rdetoolkit import as_node
read_xrd = as_node(RigakuReader(), method="read")    # id: "module.RigakuReader.read"
```

**Re-export pattern (Direct Refactor) / Result type:** unchanged from v1 rules —
keep `# noqa: F401` re-exports in original modules; use `rdetoolkit.result` as-is.

### 8.4 v1 Safety Rules

| Scenario | Required action before merge |
|----------|------------------------------|
| New v2 dirs only | `tox -e py312-module -- tests/v2/` GREEN, then full suite at phase gate |
| Any existing v1 `.py` touched | Full `tox -e py312-module` (all GREEN) in the same session |
| `tests/` root affected (Phase A B5 only) | Restore to `main` content; failures are reported, never silenced |

Phases with v1 impact: **A1/A3 (errors.pyi, stub cleanup), D2 (workflows.py
dispatch), E1/E2 (cli/main.py registration)**. Everything else must leave v1
files byte-identical.

---

## 9. Complexity Limits

Enforced by `tox -e lizard`:

| File | Max cyclomatic complexity |
|------|--------------------------|
| `workflows.py` | 16 |
| `__main__.py` | 10 |
| All other Python files | 10 |

Keep v2 modules well under 10. Split any function exceeding 7.

---

## Notes for AI Agents

- Read this file in full before writing any code.
- **The single source of truth for v2 architecture is `local/develop/v2/Design.md`.**
  When a task prompt, an old document, or your prior knowledge of this repository
  conflicts with Design.md, Design.md wins. Stop and report the conflict instead of
  guessing.
- **Codex**: you do not share context with Claude Code. All information must come
  from the task prompt (including any active `/goal`), this file, Design.md, and
  files you read from the workspace.
- **If your thread has an active Goal** (set via `/goal`): completion is
  evidence-based. Do not declare the goal complete unless the verification commands
  named in the goal have actually been run in this thread and their output is GREEN.
  If you hit the blocked condition defined in the goal, stop and report exactly:
  what was attempted, the evidence gathered, the blocker, and the input needed.
- Never git commit unless the task prompt explicitly says to — session prompts end
  with "stop and paste results"; the human commits after the manual checklist.
- Never skip Red-phase confirmation when implementing TDD tasks.
- Always run the verification command from your task prompt before reporting
  completion, and paste its tail output verbatim.
