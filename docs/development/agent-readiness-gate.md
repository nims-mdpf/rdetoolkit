# Coding-agent readiness gate

The coding-agent readiness gate (#676) checks that the whole
author → test → debug → fix loop works for a downstream user on every RDE
mode. It runs the public commands that the shipped Skills tell an agent to
run, against an installed wheel and a separately installed, version-matched
Skills pack. It makes no model call and needs no network access or
credentials. Output that an LLM writes is not evidence that the loop works.
Only this gate passing is.

- **Owner:** the rdetoolkit maintainers named by `.github/CODEOWNERS`. They
  review changes to the gate, its corpus and this page.
- **Code:** `tests/v2/acceptance/` (gate and corpus) and
  `scripts/agent_readiness_gate.py` (runner).
- **Blocking:** the `agent-readiness` job of `v2 CI` is one of the jobs that
  the required `test` check needs. A develop/v2 pull request cannot merge
  while the gate fails. The same runner also runs in every leg of `Build Test
  for Develop Branch PRs`: on pushes to develop/v2, and on the release pull
  request from develop/v2 to main for each supported platform and Python
  version (Linux, Windows and macOS × Python 3.10–3.14).

## Reproduce

```bash
maturin build --release --out dist
python -m venv /tmp/gate-venv
/tmp/gate-venv/bin/python -m pip install dist/rdetoolkit-*.whl pytest
python scripts/agent_readiness_gate.py --python /tmp/gate-venv/bin/python --work /tmp/agent-readiness
```

The runner builds the Skills pack with `scripts/skills_pack.py`. It installs
the pack into a new project with the installer bundled in the pack, run by the
interpreter under test, so the installer's exact-version check applies. It
then runs `tests/v2/acceptance` with that interpreter. The gate loads no
repository conftest and fails when the CLI imports rdetoolkit from the
checkout instead of the installed wheel. Every project, command output, run
report, event log and `job.failed` stays under `--work/pytest/`, and the JUnit
report is written to `--work/junit.xml`. When the gate fails in `v2 CI`, that
directory is uploaded as the `agent-readiness-evidence` artifact.

In the editable development suite (`tox -e py312-module`) the gate runs too.
There it builds and installs the pack from the checkout itself.

## What one mode's run covers

For each of `invoice`, `excelinvoice`, `multidatatile`, `rdeformat` and
`smarttable`, the gate builds a project with the public generators:
`new config --preset`, `new invoice`, and `new excelinvoice` with the
workbook filled in. It then runs, each command in its own process:

| Step | Command (exact Skill example where one exists) | Asserted |
|------|-----------------------------------------------|----------|
| discovery | `nodes lint --json` (`testing-lint`), `nodes lint --module processing --json`, `flows list --module processing --json`, the `authoring-discovery` commands | lint passed; `processing.pipeline` listed; JSON on stdout |
| preflight | `doctor --format json --ref processing:pipeline` (`authoring-doctor`) | passed, detected mode, `flow_executed: false`, nothing written |
| failing run | `run processing:pipeline` (`authoring-run`) on an input with one broken measurement | exit 1; stdout equals the saved run report; fail-fast stops at the broken tile; earlier tiles published; code 1 in the report and `job.failed`; the run's event log records the same failed call |
| diagnosis | `report diagnose failure-report.json --json` (`debugging-diagnose`) on a copy, then on the original, and `report explain --format json` | the same iteration, node, call id and code; iteration evidence `missing` for the copy and `verified` for the original |
| repair | archive `job.failed` (as the debugging Skill says), fix the input, rerun the same project | exit 0; each tile's `structured/`, `meta/metadata.json` (units, variable rows), invoice and raw copy; the injected `InputPaths`, `OutputContext` and `IterationInfo` of each tile |
| stale report | diagnose and explain the old report after the rerun | still the old run's failure; iteration details rewritten by the rerun are flagged `mismatched` and not used |
| privacy | a fake secret in the failing input, the error message and the environment | present in `job.failed` and the run report (negative control); absent from every doctor, lint, diagnose and explain JSON output, as are the environment variable name and the project path |
| contracts | all JSON output | stdout is exactly one document; envelopes validate against `docs/usage/diagnostics.schema.json` and `diagnostics-report.schema.json`; producer version is the installed runtime |
| new-code check | the project files and the four new-code Skills | no `custom_dataset_function`, `--legacy` or v1 path types |

Expected tile order, names and values come from the corpus definition in
`tests/v2/acceptance/corpus.py`. SmartTable runs its last row as tile 0, as
the frozen v1 contract does. Codes come from the user code's `ecode`, and
JSON shapes from the published schemas. The gate never compares one v2 run
with another as its oracle.

Single cases:

- **Partial exit semantics:** MultiDataTile under `on_iteration_error: continue`
  (via `run --config`) exits 2 with status `partial`, and
  `report diagnose --fail-on-error` exits 1.
- **Retained v1 compatibility:** `run --legacy legacy_dataset.py::dataset` on
  every mode gives the same structured, invoice and raw files and the same
  `job.failed` as the v2 flow, for a good and a bad input.
- **Migration parity:** the `migration-exercise` command of the installed
  `rdetoolkit-v1-migration` Skill runs outside the checkout. It requires the
  v1 entry, the converted flow and the artifact-node flow to agree. The frozen
  24-case mode parity replay (`migration-mode-parity`) needs the source
  checkout's v1 corpus and stays in `tests/v2/docs/test_agent_skills.py`.

## Not covered here

- **Agent clients discovering the Skills.** This needs a real Codex or Claude
  Code client and is recorded manually in
  [Agent Skills Verification](agent-skills-verification.md). Repeat that smoke
  for each release candidate. No CI job depends on a live model call.
- **Running a flow in-process and the full error matrix.** The GA
  debuggability matrix (`tests/v2/ga/`, [contract](../ga_debuggability_contract.md))
  and the frozen v1 contract tests cover these.
- **`rdetoolkit init`.** Its `container/main.py` still calls
  `rdetoolkit.workflows.run()` with no arguments, which is the v1 entry. That
  file is fixed by the v1 scaffold contract (`tests/test_cli.py`,
  `tests/v2/cli/fixtures/golden_init_bare`). The new-code workflow does not
  use it, and the gate builds its projects without `init`.
