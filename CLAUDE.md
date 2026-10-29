# CLAUDE.md

This file provides Claude Code-specific guidance when working with code in this repository.

> **📋 Development Rules**: For comprehensive development rules (testing methodology,
> code style, language boundary, branch strategy, environment setup), see
> **[AGENTS.md](./AGENTS.md)**. This file focuses on Claude Code-specific guidance,
> architecture, agent usage patterns, and Codex delegation (including `/goal`).

> **⚠️ Canonical design**: `local/develop/v2/Design.md` (**v2.2, 2026-07-15** — eager
> execution + call-log recording; R1–R10 revisions, ADR-020/021/022). `Plan.md`,
> the 2026-02 note, and v2.0 (retired to Design_v2.0_20260622.md) are superseded.
> **Never implement Trace proxies, Build/Compile phases, or pre-execution DAGs** —
> if you remember those from this repo, that is the retired design.

## Quick Reference

- **Testing Requirements** → [AGENTS.md §7](./AGENTS.md#7-testing)
- **Language Boundary / dag.rs freeze** → [AGENTS.md §4](./AGENTS.md#4-rust--python-language-boundary)
- **Code Style & Standards** → [AGENTS.md §3](./AGENTS.md#3-code-formatting--linters)
- **Branch Strategy** → [AGENTS.md §6](./AGENTS.md#6-branch-strategy)
- **Forbidden Actions** → [AGENTS.md §8.2](./AGENTS.md#82-forbidden-actions)

---

## Project Overview

RDEToolKit is a Python package for creating workflows of RDE (Research Data Express)
structured programs. The project is a **Rust + Python hybrid library** using
PyO3/Maturin (Rust is v1-only; v2.0 adds no Rust).

### Current Development Status

- **v1.x** — stable, maintenance mode. Bug fixes and minor improvements only.
- **v2.x** — active development, **redesigned 2026-06**.
  - Canonical spec: `local/develop/v2/Design.md`
  - Phase instructions: `local/develop/v2/Phase{A..F}_prompts.md`
  - Branch: `develop/v2`, work on `v2/phase-<a..f>`

---

## Architecture

### v2 Execution Model (eager + call log, v2.1)

```
Layer 4:  CLI / Entry Points      rdetoolkit run / nodes / flows / graph / report / repro / migrate
Layer 3:  Runner (Orchestration)  config → mode → validate → iterate tiles → flow call → validate → finalize
Layer 2:  Domain Services         config / mode / validation / paths / invoice
Layer 1:  Node Registry + Call Log     @node / @flow / NodeSpec / NodeCallRecord / flow-boundary DI (type-based)
Layer 0:  Shared Kernel           types / errors (int catalog) / events (schema_version) / models
```

Key invariants (Design §1):
1. `@flow` runs as **plain Python** — no trace, no compile, no proxies.
2. `@node` = registration + runtime recording + opt-in type check. Directly callable.
3. Recording is a **call log** (no value lineage, ADR-022); `rdetoolkit graph`
   renders a Call Sequence, not a dataflow DAG.
4. The Runner owns all RDE ceremony incl. the `job.failed` contract and directory
   contract (golden-tested against v1).
5. **(revised 2026-07-15, ADR-023)** the v1 *contract* is inviolable — entry
   point `run(custom_dataset_function=...)`, artifact contracts (directory
   tree, invoice, job.failed, exit codes), and Tier-1 public API (rde2types,
   rde2util, invoicefile, errors/exceptions) are guaranteed by frozen contract
   fixtures. The v1 *implementation* (workflows loop / modeproc dispatch /
   pipeline) is being unified into the single Runner across Phase G–K
   (`local/develop/v2/merge_v1/Plan.md`); old orchestration is deleted before
   v2.0 GA. Bridges (triple implementation) remain forbidden.

### Rust Core Modules

| Module | Responsibility | Status |
|--------|---------------|--------|
| `imageutil.rs` | Image processing, thumbnails | v1 (unchanged) |
| `charset_detector.rs` | Encoding detection | v1 (unchanged) |
| `fsops.rs` | File system ops | v1 (unchanged) |
| `dag.rs` | (former v2 DAG engine) | **FROZEN — internal, unregistered, never imported from v2** |

Extension module: `rdetoolkit._core` (stub: `src/rdetoolkit/_core.pyi`).
`maturin develop` is only needed when a v1 Rust file changes.

### v1.x Architecture (Stable — Do Not Break)

1. **Workflow Pipeline** (`workflows.py`, `processing/pipeline.py`) —
   `run(custom_dataset_function=...)`, linear Processor pipeline,
   modes: invoice / excelinvoice / extended (MultiDataTile, SmartTable)
2. **Data Models** (`models/`) — Config (pydantic), invoice schema, paths
3. **CLI** (`cli/`) — init, gen-invoice, make-excelinvoice, archive

---

## Working with Claude Code Agents

### Agent Roster

#### Orchestration
- **task-decomposer** — Reads `local/develop/v2/Phase{X}_prompts.md`, classifies
  session type, dispatches the correct pipeline. **Entry point for all v2 work.**
- **task-executor** — Executes decomposed tasks via Claude (non-Codex tasks).

#### Implementation
- **codex-worker** — Delegates to Codex through agmsg with a per-session goal
  contract (see "Codex via agmsg" below). Runs messaging inside a subagent context
  so the main conversation is not flooded.
- **/codex-delegate Skill** (`.claude/skills/codex-delegate/SKILL.md`) — Equivalent
  entry point for main-context delegation. Shares prompt + goal conventions.
- **python-expert** — Complex architectural decisions when delegation isn't appropriate.

#### Quality & Testing
- **tdd-enforcer** — Writes failing test files before implementation
  (`standard` mode for new modules, `v1-reuse` mode when v1 files are touched).
- **quality-checker** — Runs ruff, mypy, full tox suite after each codex round.
  Also verifies the **goal evidence** (see below) before a goal may be completed.

#### Analysis / Refactoring / Git
- **root-cause-analyst**, **performance-engineer**, **refactoring-expert**,
  **system-architect**, **pr-generator** — unchanged roles.

---

## Development Workflows

### v2 Development Workflow (Primary)

Input: `local/develop/v2/Phase{A..F}_prompts.md` (each references Design.md sections)

```
task-decomposer
  └─ Reads PhaseX_prompts.md, classifies each session, generates task files

Session Classification:
  Cleanup / settlement      → Pipeline S  (serial, human checkpoints)   … A3
  New-with-v1-ref           → Pipeline B  (tdd-enforcer → codex-worker via agmsg) … A2, B*, C*, D*, F*
  Direct Refactor (v1 hit)  → Pipeline C  (v1-reuse baseline → codex-worker via agmsg, serialized) … A1, D2, E*

Pipeline B:  tdd-enforcer (standard) → codex-worker (agmsg + goal contract) → quality-checker
Pipeline C:  tdd-enforcer (v1-reuse: confirm v1 GREEN baseline)
               → codex-worker (agmsg + goal contract, serialized — never parallel with other v1-touching work)
               → quality-checker → full tox (mandatory)
Pipeline S:  Claude-led, step-by-step with human confirmation between A3.1/A3.2/A3.3.
             Deletion-heavy work is NOT delegated to Codex.
```

**Parallelization rule** (unchanged in spirit): group sessions with no v1 impact
into one parallel round; serialize anything that touches v1 files. quality-checker
runs between rounds.

| Phase | Sessions | v1 impact | Default rounds |
|-------|----------|-----------|----------------|
| A | A1, A2, A3 | A1 (errors.pyi), A3 (cleanup) | A1 → A2 → A3 all serial (contracts build on each other) |
| B | B1, B2 | none | B1 → B2 serial (B2 needs B1) |
| C | C1, C2 | none | C1 → C2 serial |
| D | D1, D2 | D2 (workflows.py) | D1 → D2 serial |
| E | E1, E2 | both (cli/) | E1 → E2 serial |
| F | F1, F2 | none | F1 → F2 serial (F2 docs need F1 nodes) |

> Phases themselves are strictly sequential (A → B → C → D → E → F): each phase
> gate requires full suite GREEN and `--no-ff` merge to `develop/v2`.

**Phase branch rule:** Always work on `v2/phase-<letter>`. Never commit to
`develop/v2` directly.

### v1 Maintenance / Bug / Refactoring / PR workflows — unchanged

```
v1 issue:  task-decomposer-v1 (issue mode) → task-executor × N → quality-checker
bug:       root-cause-analyst → python-expert → tdd-enforcer (regression) → quality-checker
refactor:  system-architect → task-decomposer-v1 → refactoring-expert → quality-checker
PR:        quality-checker (final) → pr-generator
```

---

## Key Files and Their Purposes

### v1.x (Do Not Break)
- `workflows.py` — `run(custom_dataset_function=...)` (D2 adds dispatch only)
- `processing/pipeline.py`, `models/config.py`, `result.py`, `rde2util.py`, `fileops.py`

### v2.x (In Development)
- `local/develop/v2/Design.md` — **canonical architecture spec**
- `local/develop/v2/Phase{A..F}_prompts.md` — session instructions
- `local/develop/v2/goals/` — per-phase `/goal` templates (see below)
- `src/rdetoolkit/core/` — node / flow / registry / calllog / injection / context
- `src/rdetoolkit/runner/` — lifecycle / paths / iterator / execute / aggregator / finalize
- `src/rdetoolkit/report/`, `nodes/`, `protocols/`, `plugin/`, `testing/`, `cli/`
- `tests/v2/` — all v2 tests (never touch `tests/` root)

---

## Testing

See [AGENTS.md §7](./AGENTS.md#7-testing). Summary:

```bash
.venv/bin/tox -e py312-module                      # full suite — the phase gate
.venv/bin/tox -e py312-module -- tests/v2/ -v      # v2 only
.venv/bin/tox -e py312-module -- tests/v2/golden/ -v   # v1↔v2 parity
pytest tests/v2/ -m property -v                    # PBT
```

---

## Codex via agmsg

v2 implementation is delegated to Codex through **agmsg**, not by calling
`codex exec` directly from Claude Code. Claude Code owns orchestration,
task/goal authoring, and verification. Codex receives a self-contained task
message, works in its own session, and reports back through agmsg.

**Every delegated session still carries a goal contract**, but the contract is
sent as a `[GOAL CONTRACT]` block in the agmsg message. The important part is
the completion contract: outcome, verification surface, constraints, boundaries,
iteration policy, and blocked-stop condition.

### Why agmsg here

Claude Code and Codex do not share context. agmsg gives the two sessions an
explicit message channel with history, named agents, and clear handoff points.
This keeps Codex work auditable without flooding the main Claude conversation,
and it avoids relying on fragile `codex exec --last` session selection.

### Requirements & configuration

- agmsg is installed by APM: `fujibee/agmsg#v1.1.2`.
- `sqlite3` is available.
- Claude Code is joined to an agmsg team for this repository.
- Codex workers are started or contacted through agmsg scripts only.
- Do not read or edit agmsg DB/team files directly.

Recommended `.claude/settings.local.json` permissions include:

```json
{
  "permissions": {
    "allow": [
      "Bash(~/.agents/skills/agmsg/scripts/whoami.sh *)",
      "Bash(~/.agents/skills/agmsg/scripts/join.sh *)",
      "Bash(~/.agents/skills/agmsg/scripts/spawn.sh *)",
      "Bash(~/.agents/skills/agmsg/scripts/send.sh *)",
      "Bash(~/.agents/skills/agmsg/scripts/inbox.sh *)",
      "Bash(~/.agents/skills/agmsg/scripts/history.sh *)",
      "Bash(~/.agents/skills/agmsg/scripts/team.sh *)",
      "Bash(~/.agents/skills/agmsg/scripts/delivery.sh *)"
    ]
  }
}
```

### agmsg invocation pattern

```bash
# 1. Confirm Claude Code identity for this project.
~/.agents/skills/agmsg/scripts/whoami.sh "$PWD" claude-code

# 2. If needed, join a team. There is no register.sh.
~/.agents/skills/agmsg/scripts/join.sh <team> <claude_agent_name> claude-code "$PWD"

# 3. Start a Codex worker for one delegated session.
~/.agents/skills/agmsg/scripts/spawn.sh codex codex-c2 --project "$PWD" --team <team>

# 4. Send the goal contract and task prompt.
~/.agents/skills/agmsg/scripts/send.sh <team> <claude_agent_name> codex-c2 "<payload>"

# 5. Read replies.
~/.agents/skills/agmsg/scripts/inbox.sh <team> <claude_agent_name>
~/.agents/skills/agmsg/scripts/history.sh <team> <claude_agent_name>
```

- One delegated session = one Codex agent/thread = one goal contract.
- Name workers predictably: `codex-a1`, `codex-c2`, `codex-d1`, etc.
- Follow-ups are `send.sh` messages to the explicit Codex agent.
- Never use ambiguous "last session" semantics when multiple Codex agents exist.
- Codex may claim completion only when it has run the required verification
  commands and reported output tails. quality-checker still re-verifies locally.

### Goal lifecycle in our workflow

```
compose [GOAL CONTRACT]
  → agmsg send to named Codex agent
  → Codex work + agmsg progress replies
  → evidence check (Codex must report verification output)
  → STOP — Codex reports; quality-checker independently re-runs tox/ruff/mypy
  → human checklist from PhaseX_prompts.md → human commits
  → despawn or leave the Codex worker idle for explicit reuse
```

Codex's claim is never trusted without local verification. Pause/resume/clear
authority stays with Claude Code and the human operator.

### Writing goals — the six required elements

Every goal must contain: **Outcome / Verification surface / Constraints /
Boundaries / Iteration policy / Blocked stop condition.** A goal missing the
blocked-stop condition is rejected — that clause is what stops Codex from
"fixing" a RED v1 test by editing it.

### Shared goal skeleton (all phases)

Stored at `local/develop/v2/goals/_skeleton.goal.md`; phase files below fill the
`{...}` slots:

```
/goal Complete rdetoolkit v2 Session {SESSION} exactly as specified in
local/develop/v2/Phase{P}_prompts.md (§Session {SESSION}), with Design.md as the
overriding spec. DONE means: {OUTCOME}, verified by {VERIFICATION} — all of:
`.venv/bin/tox -e py312-module` fully GREEN (v1+v2), `.venv/bin/tox -e py312-ruff`
and `.venv/bin/tox -e py312-mypy` clean, run in this thread with output shown.
Constraints that must hold at every step: never modify files under tests/ root;
types.py, errors.py, errors.pyi are append-only; never implement Trace/Compile/
pre-execution DAG machinery (ADR-020); never import rdetoolkit._core from v2
modules; do not git commit; {EXTRA_CONSTRAINTS}. Boundaries: create/edit only
{TARGET_FILES}; read anything. Iteration policy: strict TDD — write or run the
failing test first, confirm RED, make the smallest change, re-run, and after each
cycle state what changed and the next experiment. Blocked stop condition: if a
tests/-root (v1) test goes RED, if the session spec conflicts with Design.md, if
an append-only rule would have to be broken to proceed, or if the same failure
survives 3 distinct fix attempts — STOP immediately, do not work around it, and
report: attempted paths, evidence (test output), the exact blocker, and the
decision/input you need.
```

### Per-phase goal parameters (`local/develop/v2/goals/phase-{a..f}.goal.md`)

**Phase A — contracts & settlement**
- OUTCOME: error catalog unified to int codes with hierarchy (A1) / canonical
  reserved types `{paths,out,config,invoice,iteration}` and versioned Event-
  RunReport schemas (A2) / trace machinery deleted, B5 revert + B6 stub cleanup
  done (A3)
- VERIFICATION adds: `git diff HEAD -- src/rdetoolkit/errors.py(.pyi) | grep '^-'`
  empty; `python scripts/gen_error_docs.py --check`; A3: `git diff main -- tests/`
  empty, `core.pyi` absent, `_core.pyi` present
- EXTRA_CONSTRAINTS: A3 deletions limited to the explicit file list in the
  session prompt; `dag.rs` content untouched except the freeze header
- Note: **A3 is preferably NOT delegated** (Pipeline S). If delegated anyway, the
  goal's boundaries clause lists every deletable path explicitly.

**Phase B — runner skeleton & platform contracts**
- OUTCOME: lifecycle steps 1–6 ordered and tested; W1001 emitted on mode
  override; tile path resolution incl. `divided/`; `job.failed` written only by
  finalize in v1 format with catalog int codes
- VERIFICATION adds: `tox ... -- tests/v2/golden/ -v` GREEN — directory-tree
  parity with the v1 code path on ≥3 modes, where the expected tree is **generated
  by running v1**, never hand-written
- EXTRA_CONSTRAINTS: `domain/mode.py` priority order unchanged;
  `write_job_errorlog_file` called, not reimplemented

**Phase C — eager node/flow & call log (v2.1: see PhaseC_prompts.md + review/phase_c_kickoff.md)**
- OUTCOME: `@node`/`@flow` fully transparent plain functions; registry with
  E2001/E2005; CallLogRecorder with per-call `call_id`, run-global `seq`,
  `parent_flow` (call log ONLY — no lineage/edges, ADR-022); flow-boundary DI
  by type annotation with E2003/E2006 (E2002 retired, name-based DI forbidden);
  opt-in type check with zero cost when off; rdetoolkit.testing pytest plugin
- VERIFICATION adds: `tests/v2/core/test_eager_semantics.py` GREEN (the legacy-B2
  regression suite: if/loop/f-string/literal/default-arg/container/repeat-call);
  determinism test GREEN; PBT with branching+merging shapes GREEN
- EXTRA_CONSTRAINTS: no DI inside `@node`; no `sys.setprofile`-style global hooks

**Phase D — iteration & end-to-end**
- OUTCOME: 5 mode iterators with correct tile semantics; error policy
  continue/fail_fast with success/partial/failed; RunAggregator independent of
  EventSink; `workflows.run` dispatch with v1 path byte-identical
- VERIFICATION adds: `tests/v2/e2e/ -v` GREEN on ≥3 modes (tree parity + report
  schema + job.failed artifact); `git diff` shows zero changes to v1 processing
  files other than the dispatch block in `workflows.py`
- EXTRA_CONSTRAINTS: no `Executor` class; no DeprecationWarning on the v1 path

**Phase E — CLI**
- OUTCOME: run/--validate-only, nodes list|describe|lint, flows, graph (3
  formats from the call log, output titled "Call Sequence" — not a dataflow
  DAG), report show, repro export→import→run round-trip,
  migrate check; exit codes 0/1/2/3 uniform
- VERIFICATION adds: `rdetoolkit --help` still lists init/gen-invoice/
  make-excelinvoice/archive; parametrized exit-code test GREEN; v1 CLI tests GREEN
- EXTRA_CONSTRAINTS: typer; do not implement `plan`/`debug-node`; only
  `cli/main.py` registration may touch existing CLI files; graph rendering in
  pure Python (no `_core`)

**Phase F — builtin nodes, protocols, plugins, docs**
- OUTCOME: builtin node set registered & listed; canonical Protocols replace old
  ones (removals logged in CHANGELOG_v2.md); `as_node` proves v1 handler-class
  migration; plugin discovery with NO lifecycle hooks; migration guide + docs
  with executed examples; traceability.md covers every Design §14 row
- VERIFICATION adds: `mkdocs build --strict`; `gen_error_docs.py --check`;
  doctest/executed-example tests GREEN; `rdetoolkit nodes list` shows builtins
- EXTRA_CONSTRAINTS: builtin nodes get no framework privileges; v1
  rde2util/Meta read-only (port, don't modify)

### Goal anti-patterns (reject these)

- `/goal Implement Phase C` — no verification surface, no constraints.
- Any goal whose completion can be satisfied by **weakening a test** — the
  constraints clause must make tests/ root and acceptance tests immutable.
- One goal spanning multiple sessions or phases — thread evidence gets stale and
  budget accounting becomes meaningless.

### Codex Task Payload Template

```
[GOAL CONTRACT]
Complete rdetoolkit v2 Session {SESSION} exactly as specified in
local/develop/v2/Phase{P}_prompts.md (§Session {SESSION}), with
local/develop/v2/Design.md as the overriding spec.

DONE means: {OUTCOME}
Verified by: {VERIFICATION}
Constraints: never modify files under tests/ root; types.py, errors.py,
errors.pyi are append-only; never implement Trace/Compile/pre-execution-DAG
machinery; never import rdetoolkit._core from v2 modules; do not git commit;
{EXTRA_CONSTRAINTS}.
Boundaries: create/edit only {TARGET_FILES}; read anything.
Iteration policy: strict TDD — confirm RED first, smallest change to GREEN,
then refactor while keeping tests green.
Blocked stop condition: {BLOCKED_STOP_CONDITION}

[CONTEXT]
- Python 3.12, strict mypy, ruff; test runner: .venv/bin/tox -e py312-module
- Canonical spec: local/develop/v2/Design.md (§ refs in the task)
- Rules: AGENTS.md (read in full; §8.2 Forbidden Actions especially)
- Execution model: eager + call log (v2.1). NO trace, NO compile, NO RustDAG,
  NO value lineage (ADR-022), NO name-based DI.

[TASK]
<paste the Session block from PhaseX_prompts.md verbatim>

[REPORTING]
Reply through agmsg after each TDD cycle: what changed, test output tail, next step.
On completion: paste the verification command outputs required by the goal contract.
On blocker: follow the Goal's blocked stop condition exactly.
```

### Delegation criteria

**Delegate to Codex via agmsg (with goal contract):** all session implementation in Phases A1, A2,
B–F; large test-suite authoring; mechanical refactors.
**Keep in Claude:** Phase A3 settlement (deletion-heavy), architecture decisions,
Design.md edits, goal authoring/review, anything requiring judgment about
*whether* a spec is right rather than *how* to satisfy it.

### Choosing between subagent and Skill

- Parallel dispatch / long sessions → `codex-worker` subagent, which uses agmsg.
- Single ad-hoc delegation → `/codex-delegate <task-file>` in main context, which uses agmsg.
Both use the same payload structure and named Codex-agent pattern.

---

## Common Development Patterns

### v2 @node / @flow (eager)

```python
from rdetoolkit import node, flow

@node(tags=["io"], version="1.0.0")
def read_csv(paths: InputPaths) -> tuple[Metadata, pd.DataFrame]:
    """Read CSV from input paths."""
    ...

@flow
def xrd_pipeline(paths: InputPaths, out: OutputContext, config: RdeConfig) -> None:
    meta, df = read_csv(paths)
    if config.custom.get("normalize", True):   # plain Python — by design
        df = normalize(df, threshold=0.3)
    save_csv(df, out, "structured.csv")
    save_meta(meta, out)
```

### Protocol adapter / Result / Re-export

```python
read_xrd = as_node(RigakuReader(), method="read")
from rdetoolkit.result import Success, Failure, Result      # v1, use as-is
from rdetoolkit.utils.encoding import detect_encoding  # noqa: F401  (re-export)
```

### rdeconfig.yaml v2 sections (Design §4.4, §7.2, §3.2)

```yaml
provenance:
  repr_head: on                # on (default) | off — call-log repr capture (R2)
  repr_head_len: 80
execution:
  type_check: off              # off (default) | warn | strict
  on_iteration_error: continue # fail_fast | continue (default)
# NOTE: a former `plugin.preferred_handler` example was removed 2026-07-15 —
# it never existed in Design.md v2.1+ (plugin config wiring is out of scope;
# discovery/display only, see session_f3.md Conflict #2).
# v1 sections preserved unchanged
system:
  extended_mode: null
  save_raw: true
  save_thumbnail_image: true
```

(Former `compile:` section is retired with the compile phase.)

---

## Dependencies

- **Core**: pandas, polars, pydantic, jsonschema, openpyxl, PyYAML, typer
- **v2 Python additions**: hypothesis (PBT)
- **Rust**: v1 crates only; `petgraph` remains in Cargo.toml for the frozen
  `dag.rs` but is not on any v2.0 path
- **Build**: maturin / **Dev**: pytest, ruff, mypy, tox, mkdocs, hypothesis

---

## Additional Resources

- Documentation: https://nims-mdpf.github.io/rdetoolkit/
- v2 Design: `local/develop/v2/Design.md` / Phase prompts: `Phase{A..F}_prompts.md`
- Goal templates: `local/develop/v2/goals/`
- Contributing Guide: `CONTRIBUTING.md`

---

## Local Rules

- Think in English, respond in Japanese.
- Never modify v1 test files (`tests/` root) — v2 tests go to `tests/v2/` only.
- Full `tox -e py312-module` GREEN is the gate for every session end and every
  phase merge — no exceptions.
- Never implement retired-design machinery (Trace/Compile/RustDAG-in-v2) even if
  asked by an outdated document; raise the conflict instead.
- One Codex agent/thread = one session = one goal contract. Goal contracts must
  include all six elements; contracts without a blocked-stop condition are rejected.
- The human commits. Agents stop and paste results.
- Worktrees are created with `git gtr new <branch> --from <base>` (never plain
  `git worktree add`). gtr symlinks `local -> ~/github/rdetoolkit/local` and
  copies `.claude/`, so `local/develop/` docs have a single canonical copy in
  the main repo shared by all worktrees (see AGENTS.md §6.4).
- `local/develop/` is never committed or pushed (`git add -f local/...` is
  forbidden). Session artifacts stay there as local-only documents.
- **Release/tagging is human-only** (AGENTS.md §6.6). Agents never run `git tag`
  or push tags. Before any tag, `pyproject.toml` version, `__version__` in
  `src/rdetoolkit/__init__.py`, and the tag must all be identical canonical
  PEP 440 (`python scripts/check_version_consistency.py --tag vX.Y.Z` must pass);
  CI's `check-version` gate enforces this and must never be weakened. Full
  procedure: `local/develop/v2/release_flow.md`. Note: PyPI version `2.0.0` is
  permanently burned (2026-07 incident, yanked) — GA cannot be `2.0.0`.
