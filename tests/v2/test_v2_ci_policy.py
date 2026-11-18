"""Executable policy for the develop/v2 CI gate (Issue #748).

EP table (written before implementation):

| Partition | Expected | Test ID |
| --- | --- | --- |
| develop/v2 PR | dedicated, read-only, cancelling workflow | CI-001 |
| shard commands | isolated path shards, existing selection, per-shard reports | CI-002 |
| full-suite aggregate | partition proof, combined coverage, both gates | CI-002 |
| weakened command or condition | policy rejects the regression | CI-003 |
| quality and Rust jobs | real lint/type/check/clippy/test commands | CI-004 |
| old coverage workflows | v2 excluded and no repository-writing badge | CI-005 |
| installed wheel | clean environment and original compatibility tests | CI-006 |
| existing main matrix | five Python versions, three tox environments | CI-007 |
| each scoped module below 95, including branch-only deficit | actual subprocess fails | CI-008 |
| required-job status failures/missing jobs | final required check fails closed | CI-011 |
| report absent or empty | report validation fails | CI-012 |
| shard listings vs complete collection | missing, extra, duplicate, empty fail | CI-013 |
| shard matrix result | only success passes the aggregate | CI-014 |
| shard coverage data | gates apply to the combined data; absent shard fails | CI-015 |

BV table:

| Boundary | Expected | Test ID |
| --- | --- | --- |
| total coverage 79%, 80% | fail, pass | CI-009 |
| scoped coverage 94%, 95% | fail, pass | CI-008, CI-010 |
| full-suite gate has zero positional arguments | scoped checks cannot skip | CI-002 |
| ID drift, same function and count / changed count | pass / fail | CI-013 |

Flow semantics and RDE error codes are outside this workflow-only change.
"""

from __future__ import annotations

from pathlib import Path
from copy import deepcopy
import os
import json
import re
import shlex
import subprocess
import sys
from typing import Any

import coverage
import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
MODULES = (
    "domain/artifacts.py",
    "report/run_report.py",
    "runner/executor.py",
    "runner/invoker.py",
    "runner/planner.py",
    "runner/finalize.py",
)
REQUIRED_JOBS = ("pytest-shard", "full-suite", "quality", "rust", "wheel-install-gate", "changelog")
REMAINDER = next(
    entry["paths"]
    for entry in yaml.load((ROOT / ".github/workflows/v2-ci.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)["jobs"]["pytest-shard"]["strategy"]["matrix"]["include"]  # noqa: S506
    if entry["paths"].startswith("tests ")
)
FORBIDDEN_SELECTION = ("-m", "-k", "-o", "--override-ini", "--deselect", "-x", "--exitfirst", "--lf", "--last-failed", "||")


def _workflow(name: str = "v2-ci.yml") -> dict[str, Any]:
    # BaseLoader constructs only strings/containers and preserves GitHub's `on` key.
    return yaml.load((ROOT / ".github/workflows" / name).read_text(encoding="utf-8"), Loader=yaml.BaseLoader)  # noqa: S506


def _collapse(run: str) -> str:
    """Make each ``${{ expression }}`` one ``${{expression}}`` token for splitting."""
    return re.sub(r"\$\{\{\s*(.*?)\s*\}\}", lambda match: "${{" + match.group(1).replace(" ", "") + "}}", run)


def _commands(job: dict[str, Any]) -> list[list[str]]:
    commands = []
    for step in job["steps"]:
        for line in _collapse(step.get("run", "")).replace("\\\n", " ").splitlines():
            tokens = shlex.split(line, comments=True)
            if tokens:
                tokens[0] = Path(tokens[0]).name
                commands.append(tokens)
    return commands


def _shards(job: dict[str, Any]) -> dict[str, list[str]]:
    return {entry["shard"]: shlex.split(entry["paths"]) for entry in job["strategy"]["matrix"]["include"]}


def _gate_steps(job: dict[str, Any], *needles: str) -> list[dict[str, Any]]:
    return [step for step in job["steps"] if any(needle in step.get("run", "") for needle in needles)]


def _shard_policy(job: dict[str, Any]) -> None:
    """The shards are isolated runners whose path selectors cover tests/ exactly once."""
    assert "if" not in job
    assert job.get("continue-on-error", "false") == "false"
    assert set(job["strategy"]["matrix"]) == {"include"}
    shards = _shards(job)
    assert len(shards) >= 2
    # One shard is tests/ minus every directory the other shards select; the
    # others select existing, disjoint directories only.
    rest = [name for name, paths in shards.items() if paths[0] == "tests"]
    assert len(rest) == 1
    directories = [path for name, paths in shards.items() if name != rest[0] for path in paths]
    assert all(path.startswith("tests/") and (ROOT / path).is_dir() for path in directories)
    assert len(set(directories)) == len(directories)
    assert not any(other.startswith(path + "/") for path in directories for other in directories)
    assert all(paths for paths in shards.values())
    assert sorted(shards[rest[0]][1:]) == sorted(f"--ignore={path}" for path in directories)
    assert job["env"]["COVERAGE_FILE"] == "${{ github.workspace }}/ci-results/.coverage.${{ matrix.shard }}"
    assert job["env"]["HYPOTHESIS_PROFILE"] == "ci"
    commands = _commands(job)
    pytest_commands = [command for command in commands if command[:3] == ["python", "-m", "pytest"] and "--collect-only" not in command]
    collect_commands = [command for command in commands if command[:3] == ["python", "-m", "pytest"] and "--collect-only" in command]
    assert len(pytest_commands) == 1
    assert len(collect_commands) == 1
    for command in (*pytest_commands, *collect_commands):
        assert command[3 + ("--collect-only" in command) * 2 :][:1] == ["${{matrix.paths}}"]
        assert not any(token in command[3:] for token in FORBIDDEN_SELECTION)
        assert not any(token.startswith(("tests", "--ignore", "--deselect", "--override-ini", "-p")) for token in command[3:])
    command = pytest_commands[0]
    assert "--cov=rdetoolkit" in command
    assert "--cov-config=pyproject.toml" in command
    assert "--durations=30" in command
    assert "--junitxml=ci-results/junit-${{matrix.shard}}.xml" in command
    assert "ci-results/nodeids-${{matrix.shard}}.txt" in collect_commands[0]
    # v1 CLI tests spawn `python`/`rdetoolkit` from PATH, so the venv must be on it first.
    runs = [step.get("run", "") for step in job["steps"]]
    path_steps = [index for index, run in enumerate(runs) if '"$PWD/.venv/bin" >> "$GITHUB_PATH"' in run]
    assert path_steps
    assert path_steps[0] < next(index for index, run in enumerate(runs) if "python -m pytest" in run)
    for step in _gate_steps(job, "python -m pytest", 'test -s "$report"'):
        assert step.get("continue-on-error", "false") == "false"
        assert "if" not in step
        assert "HYPOTHESIS_PROFILE" not in step.get("env", {})
        assert "COVERAGE_FILE" not in step.get("env", {})
    uploads = [step for step in job["steps"] if step.get("uses", "").startswith("actions/upload-artifact@")]
    assert len(uploads) == 1
    assert "always()" in uploads[0]["if"]
    assert uploads[0]["with"]["name"] == "v2-shard-${{ matrix.shard }}"
    assert uploads[0]["with"]["path"].strip() == "ci-results/"
    assert uploads[0]["with"]["include-hidden-files"] == "true"
    assert uploads[0]["with"]["if-no-files-found"] == "error"


def _aggregate_policy(job: dict[str, Any], shard_names: list[str]) -> None:
    """The aggregate proves the partition and applies both gates to combined data."""
    assert job["name"] == "Code Coverage with pytest"
    assert job["needs"] == ["pytest-shard"]
    assert "always()" in job["if"]
    assert job.get("continue-on-error", "false") == "false"
    first = job["steps"][0]
    assert first["env"] == {"SHARDS": "${{ needs.pytest-shard.result }}"}
    assert first["run"].strip() == 'test "$SHARDS" = success'
    commands = _commands(job)
    collect = [command for command in commands if command[:3] == ["python", "-m", "pytest"]]
    assert collect == [["python", "-m", "pytest", "--collect-only", "-q", "tests/", ">", "ci-results/test-nodeids.txt"]]
    listings = [f"shards/nodeids-{name}.txt" for name in shard_names]
    assert [command for command in commands if "scripts/check_test_partition.py" in command] == [
        ["python", "scripts/check_test_partition.py", "ci-results/test-nodeids.txt", *listings],
    ]
    combine = [command for command in commands if command[3:4] == ["combine"]]
    assert len(combine) == 1
    assert sorted(token for token in combine[0] if token.startswith("shards/")) == sorted(f"shards/.coverage.{name}" for name in shard_names)
    report = [command for command in commands if command[:4] == ["python", "-m", "coverage", "report"]]
    assert len(report) == 1
    assert "--fail-under=80" in report[0]
    assert not any(token.startswith(("--include", "--omit")) for token in report[0])
    assert [command for command in commands if "scripts/check_phase_h_coverage.py" in command] == [["python", "scripts/check_phase_h_coverage.py"]]
    assert "--rcfile=pyproject.toml" in combine[0]
    assert "--rcfile=pyproject.toml" in report[0]
    gates = _gate_steps(job, 'test "$SHARDS"', "check_test_partition.py", "coverage combine", "coverage report", "check_phase_h_coverage.py", 'test -s "$report"')
    assert len(gates) == 6
    for step in gates:
        assert step.get("continue-on-error", "false") == "false"
        assert "if" not in step
    downloads = [step for step in job["steps"] if step.get("uses", "").startswith("actions/download-artifact@")]
    assert len(downloads) == 1
    assert downloads[0]["with"] == {"pattern": "v2-shard-*", "path": "shards", "merge-multiple": "true"}


def _full_suite_policy(workflow: dict[str, Any]) -> None:
    jobs = workflow["jobs"]
    _shard_policy(jobs["pytest-shard"])
    _aggregate_policy(jobs["full-suite"], list(_shards(jobs["pytest-shard"])))


def _synthetic_coverage(directory: Path, counts: dict[str, int]) -> None:
    """Write independently controlled coverage inputs without importing the package."""
    data = coverage.CoverageData(basename=str(directory / ".coverage"))
    for module, count in counts.items():
        source = directory / "rdetoolkit" / module
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("\n".join(f"value_{line} = {line}" for line in range(1, 101)) + "\n", encoding="utf-8")
        data.add_arcs({str(source): [(-1, 1), *((line, line + 1) for line in range(1, count)), (count, -1)]})
    data.write()


def _run_coverage(directory: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=directory,
        env={**os.environ, "COVERAGE_FILE": str(directory / ".coverage"), "COVERAGE_RCFILE": str(ROOT / "pyproject.toml")},
        capture_output=True,
        text=True,
        check=False,
    )


def test_dedicated_v2_pr_gate__ci_001() -> None:
    """CI-001: the dedicated gate is restricted to v2 pull requests."""
    # Given: the dedicated workflow configuration.
    # When: parsing YAML using string scalars (GitHub's 'on' is not a boolean).
    workflow = _workflow()
    # Then: it targets v2 PRs, cancels stale runs and cannot write repository contents.
    assert workflow["on"] == {"pull_request": {"branches": ["develop/v2"]}}
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"]["cancel-in-progress"] == "true"
    assert "pull_request.number" in workflow["concurrency"]["group"]
    assert set(workflow["jobs"]) == {*REQUIRED_JOBS, "required"}
    assert all(job.get("permissions", {"contents": "read"}) == {"contents": "read"} for job in workflow["jobs"].values())


def test_full_suite_and_reports__ci_002() -> None:
    """CI-002: isolated shards and one aggregate keep the complete suite and both gates."""
    # Given: the shard matrix and the aggregate job of the real workflow.
    workflow = _workflow()
    # When/Then: selection, measurement, partition proof and gates satisfy the policy.
    _full_suite_policy(workflow)
    for job in (workflow["jobs"]["pytest-shard"], workflow["jobs"]["full-suite"]):
        setups = [step for step in job["steps"] if step.get("uses", "").startswith(("actions/setup-python@", "astral-sh/setup-uv@"))]
        assert any(step["with"].get("python-version") == "3.12" for step in setups)
    uploads = [step for step in workflow["jobs"]["full-suite"]["steps"] if step.get("uses", "").startswith("actions/upload-artifact@")]
    assert len(uploads) == 1
    assert "always()" in uploads[0]["if"]
    paths = [path.strip().rstrip("/") for path in uploads[0]["with"]["path"].splitlines()]
    assert set(paths) == {"ci-results", "shards", ".coverage"}
    assert uploads[0]["with"]["include-hidden-files"] == "true"
    assert uploads[0]["with"]["if-no-files-found"] == "error"


def _mutate(workflow: dict[str, Any], job_name: str, original: str, replacement: str) -> None:
    job = workflow["jobs"][job_name]
    changed = False
    for step in job["steps"]:
        if original in step.get("run", ""):
            step["run"] = step["run"].replace(original, replacement)
            changed = True
    for entry in job.get("strategy", {}).get("matrix", {}).get("include", []):
        if entry["paths"] == original:
            entry["paths"] = replacement
            changed = True
    assert changed


@pytest.mark.parametrize(
    ("job_name", "original", "replacement"),
    [
        ("pytest-shard", REMAINDER, REMAINDER + " --ignore=tests/v2/core"),
        ("pytest-shard", REMAINDER, REMAINDER.replace(" --ignore=tests/property", "")),
        ("pytest-shard", REMAINDER, "tests"),
        ("pytest-shard", REMAINDER, "tests/v2/core"),
        ("pytest-shard", "tests/v2/graph tests/v2/runner", "tests/v2/graph"),
        ("pytest-shard", "tests/v2/graph tests/v2/runner", "tests/v2/graph tests/v2/runner tests/v2/cli"),
        ("pytest-shard", "tests/v2/graph tests/v2/runner", "tests/v2/graph tests/v2/runner/missing"),
        ("pytest-shard", "tests/v2/graph tests/v2/runner", "tests/v2 tests/v2/runner"),
        ("pytest-shard", "--cov=rdetoolkit", "--cov=rdetoolkit.runner"),
        ("pytest-shard", "--cov-config=pyproject.toml", "--cov-config=/dev/null"),
        ("pytest-shard", "--durations=30", "--durations=0"),
        ("pytest-shard", "python -m pytest ${{ matrix.paths }} --durations", "python -m pytest ${{ matrix.paths }} -m 'not graph_outputs' --durations"),
        ("pytest-shard", "python -m pytest ${{ matrix.paths }} --durations", "python -m pytest ${{ matrix.paths }} -o addopts='' --durations"),
        ("pytest-shard", "python -m pytest ${{ matrix.paths }} --durations", "python -m pytest ${{ matrix.paths }} -k 'not slow' --durations"),
        ("pytest-shard", "python -m pytest ${{ matrix.paths }} --durations", "python -m pytest ${{ matrix.paths }} -x --durations"),
        ("pytest-shard", "--collect-only -q ${{ matrix.paths }}", "--collect-only -q tests/v2"),
        ("full-suite", 'test "$SHARDS" = success', 'test "$SHARDS" = success || true'),
        ("full-suite", "--collect-only -q tests/", "--collect-only -q tests/v2"),
        ("full-suite", " shards/nodeids-remainder.txt", ""),
        ("full-suite", " shards/.coverage.remainder", ""),
        ("full-suite", "--fail-under=80", "--fail-under=79"),
        ("full-suite", "--fail-under=80", "--fail-under=80 --include=*/runner/*"),
        ("full-suite", "scripts/check_phase_h_coverage.py", "scripts/check_phase_h_coverage.py tests/"),
        ("full-suite", "scripts/check_phase_h_coverage.py", "scripts/check_phase_h_coverage.py || true"),
    ],
)
def test_weakened_full_suite_is_rejected__ci_003(job_name: str, original: str, replacement: str) -> None:
    """CI-003: removing collection, measurement, partition proof or enforcement is detectable."""
    # Given: a mutation of the real workflow command or shard selector.
    workflow = deepcopy(_workflow())
    _mutate(workflow, job_name, original, replacement)
    # When/Then: the same policy oracle rejects the weakened workflow.
    with pytest.raises(AssertionError):
        _full_suite_policy(workflow)


@pytest.mark.parametrize("job_name", ["pytest-shard", "full-suite"])
@pytest.mark.parametrize("mutation", ["skip-job", "ignore-job-failure", "skip-step", "ignore-step-failure", "wrong-profile", "drop-always"])
def test_bypassed_full_suite_is_rejected__ci_003(job_name: str, mutation: str) -> None:
    """CI-003: conditions and failure suppression cannot turn gates green."""
    # Given: a bypass injected into a real job or its gating step.
    workflow = deepcopy(_workflow())
    job = workflow["jobs"][job_name]
    needle = "python -m pytest" if job_name == "pytest-shard" else "check_phase_h_coverage.py"
    step = next(step for step in job["steps"] if needle in step.get("run", ""))
    if mutation == "skip-job":
        job["if"] = "false"
    elif mutation == "ignore-job-failure":
        job["continue-on-error"] = "true"
    elif mutation == "skip-step":
        step["if"] = "false"
    elif mutation == "ignore-step-failure":
        step["continue-on-error"] = "true"
    elif mutation == "wrong-profile":
        if job_name == "pytest-shard":
            step.setdefault("env", {})["HYPOTHESIS_PROFILE"] = "dev"
        else:
            job["needs"] = []
    elif job_name == "pytest-shard":
        job["strategy"]["matrix"]["include"].pop()
    else:
        job["if"] = "success()"
    # When/Then: skipped or non-gating tests violate the same policy.
    with pytest.raises(AssertionError):
        _full_suite_policy(workflow)


def test_quality_and_rust_are_real_checks__ci_004() -> None:
    """CI-004: Rust check names are backed by compiler, lint and unit tests."""
    # Given: the dedicated jobs and historical branch-protection Rust check.
    jobs = _workflow()["jobs"]
    main_rust = _workflow("main.yml")["jobs"]["test_rs"]
    # When/Then: quality uses canonical tools and Rust actually runs all gates.
    quality = _commands(jobs["quality"])
    assert any(command[:2] == ["ruff", "check"] for command in quality)
    assert any(command[0] == "mypy" for command in quality)
    for job in (jobs["rust"], main_rust):
        commands = _commands(job)
        for operation in ("check", "clippy", "test"):
            assert any(command[:2] == ["cargo", operation] for command in commands)
        assert any(command[:2] == ["cargo", "test"] and "--features" in command and "test" in command[2:] for command in commands)
        assert all("||" not in command for command in commands if command[0] == "cargo")
    assert main_rust["name"] == "Test on ${{ matrix.os }}"
    assert set(main_rust["strategy"]["matrix"]["os"]) == {"ubuntu-latest", "windows-latest", "macos-latest"}
    assert main_rust["strategy"]["matrix"].get("python-version", ["3.12"]) == ["3.12"]


@pytest.mark.parametrize("name", ["coverage_pr_reports.yml", "coverage_badge.yml"])
def test_legacy_coverage_excludes_v2_and_cannot_push__ci_005(name: str) -> None:
    """CI-005: legacy branch coverage remains without duplicate v2 work or commits."""
    # Given: one of the historical coverage workflows.
    workflow = _workflow(name)
    # When/Then: existing target branches remain and v2 is excluded last.
    assert workflow["on"]["pull_request"]["branches"] == ["develop-*", "develop/**", "!develop/v2"]
    assert workflow["permissions"] == {"contents": "read"}
    for job in workflow["jobs"].values():
        assert job.get("permissions", {}).get("contents", "read") == "read"
        assert not any(command[:2] in (["git", "push"], ["git", "commit"]) for command in _commands(job))
    if name == "coverage_badge.yml":
        assert any(step.get("uses", "").startswith("actions/upload-artifact@") for job in workflow["jobs"].values() for step in job["steps"])


def test_installed_wheel_gate_preserves_tests__ci_006() -> None:
    """CI-006: the dedicated gate retains the established clean wheel validation."""
    # Given: both workflows' installed-wheel jobs.
    old = _workflow("main.yml")["jobs"]["wheel-install-gate"]
    new = _workflow()["jobs"]["wheel-install-gate"]
    # When/Then: commands retain the clean venv, import assertion and exact test list.
    assert _commands(new) == _commands(old)


def test_existing_python_matrix_is_preserved__ci_007() -> None:
    """CI-007: this change does not silently reduce existing compatibility coverage."""
    # Given: the historical primary Python CI matrix.
    job = _workflow("main.yml")["jobs"]["test"]
    # When/Then: every original version and tox seat remains.
    assert job["strategy"]["matrix"] == {
        "python-version": ["3.10", "3.11", "3.12", "3.13", "3.14"],
        "tox-env": ["module", "ruff", "mypy"],
    }


@pytest.mark.parametrize("module", MODULES)
def test_each_scoped_gate_rejects_94_percent__ci_008(tmp_path: Path, module: str) -> None:
    """CI-008: every module fails independently even when the global gate passes."""
    # Given: one module at 94%, the other five at 100%, with branch-mode data.
    _synthetic_coverage(tmp_path, {name: 94 if name == module else 100 for name in MODULES})
    # When: running the real global and scoped coverage subprocesses.
    global_result = _run_coverage(tmp_path, "-m", "coverage", "report", "--fail-under=80")
    result = _run_coverage(tmp_path, str(ROOT / "scripts/check_phase_h_coverage.py"))
    # Then: averaging cannot conceal any individual scoped coverage regression.
    assert global_result.returncode == 0, global_result.stdout + global_result.stderr
    assert result.returncode == 2, result.stdout + result.stderr
    assert module in result.stdout.replace("\\", "/")
    assert "fail-under=95" in result.stdout


@pytest.mark.parametrize("module", MODULES)
def test_branch_deficit_fails_despite_full_line_coverage__ci_008(tmp_path: Path, module: str) -> None:
    """CI-008: complete line coverage cannot conceal untested branch outcomes."""
    # Given: every line covered, but one module's ten false branches unexecuted.
    _synthetic_coverage(tmp_path, dict.fromkeys(MODULES, 100))
    source = tmp_path / "rdetoolkit" / module
    source.write_text(
        "".join(f"if choice:\n    value_{index} = {index}\n" for index in range(10))
        + "".join(f"value_{index} = {index}\n" for index in range(10, 90)),
        encoding="utf-8",
    )
    measurement = coverage.Coverage(data_file=str(tmp_path / ".coverage"), config_file=str(ROOT / "pyproject.toml"))
    measurement.load()
    assert measurement.analysis2(str(source))[3] == []
    # When: the real scoped gate consumes branch data (100 lines, 10/20 branches).
    result = _run_coverage(tmp_path, str(ROOT / "scripts/check_phase_h_coverage.py"))
    # Then: the process fails even though no source line is missing.
    assert result.returncode == 2, result.stdout + result.stderr
    assert "fail-under=95" in result.stdout
    assert module in result.stdout.replace("\\", "/")


@pytest.mark.parametrize(("percent", "exit_code"), [(79, 2), (80, 0)])
def test_global_coverage_boundary__ci_009(tmp_path: Path, percent: int, exit_code: int) -> None:
    """CI-009: the configured threshold fails below 80 and accepts exactly 80."""
    # Given: controlled coverage and the threshold extracted from the actual command.
    _synthetic_coverage(tmp_path, {MODULES[0]: percent})
    command = next(command for command in _commands(_workflow()["jobs"]["full-suite"]) if command[:4] == ["python", "-m", "coverage", "report"])
    threshold = next(argument.split("=", 1)[1] for argument in command if argument.startswith("--fail-under="))
    # When: coverage evaluates the same numerical gate against actual data.
    result = _run_coverage(tmp_path, "-m", "coverage", "report", f"--fail-under={threshold}")
    # Then: crossing the boundary changes the process result.
    assert result.returncode == exit_code, result.stdout + result.stderr


def test_all_scoped_gates_accept_95_percent__ci_010(tmp_path: Path) -> None:
    """CI-010: the minimum passing value is accepted by every real scoped gate."""
    # Given: all six independently measured modules exactly at 95%.
    _synthetic_coverage(tmp_path, dict.fromkeys(MODULES, 95))
    # When: executing the unchanged gate script without positional arguments.
    result = _run_coverage(tmp_path, str(ROOT / "scripts/check_phase_h_coverage.py"))
    # Then: each module is reported and the complete gate succeeds.
    assert result.returncode == 0, result.stdout + result.stderr
    assert all(module in result.stdout.replace("\\", "/") for module in MODULES)


@pytest.mark.parametrize(
    ("job_name", "status"),
    [(None, "success"), *[(name, status) for name in REQUIRED_JOBS for status in ("failure", "cancelled", "skipped", "missing")], ("unexpected", "success")],
)
def test_required_gate_fails_closed__ci_011(job_name: str | None, status: str) -> None:
    """CI-011: execute the final gate with failed, skipped and absent dependencies."""
    # Given: real gate code and one changed dependency result, or all successful jobs.
    job = _workflow()["jobs"]["required"]
    assert job["name"] == "test"
    assert "always()" in job["if"]
    assert set(job["needs"]) == set(REQUIRED_JOBS)
    step = job["steps"][0]
    assert step["env"]["RESULTS"] == "${{ toJSON(needs) }}"
    source = step["run"].split("\n", 1)[1].rsplit("\nPY", 1)[0]
    results = {name: {"result": "success"} for name in REQUIRED_JOBS}
    if status == "missing":
        results.pop(job_name)
    elif job_name is not None:
        results[job_name] = {"result": status}
    # When: running the workflow's actual Python gate in a separate process.
    result = subprocess.run([sys.executable, "-c", source], env={**os.environ, "RESULTS": json.dumps(results)}, capture_output=True, text=True, check=False)
    # Then: success requires every expected dependency, with no silent skips.
    assert (result.returncode == 0) is (job_name is None), result.stdout + result.stderr


def _reports(job: dict[str, Any]) -> list[str]:
    step = next(step for step in job["steps"] if 'test -s "$report"' in step.get("run", ""))
    loop = _collapse(step["run"]).replace("\\\n", " ").split(" in ", 1)[1].split(";", 1)[0]
    return loop.split()


@pytest.mark.parametrize("job_name", ["pytest-shard", "full-suite"])
def test_report_validation_lists_every_report__ci_012(job_name: str) -> None:
    """CI-012: the validated report set covers every shard's listing, JUnit and coverage."""
    # Given: the report validation step of a real job.
    workflow = _workflow()
    shards = list(_shards(workflow["jobs"]["pytest-shard"]))
    # When: reading the validated paths.
    reports = _reports(workflow["jobs"][job_name])
    # Then: no required report is absent from the validation.
    if job_name == "pytest-shard":
        assert reports == [f"ci-results/{name}" for name in ("nodeids-${{matrix.shard}}.txt", "junit-${{matrix.shard}}.xml", ".coverage.${{matrix.shard}}")]
    else:
        expected = {"ci-results/test-nodeids.txt", "ci-results/coverage.xml", "ci-results/coverage.json", ".coverage"}
        expected |= {f"shards/{kind}-{name}.{ext}" for name in shards for kind, ext in (("nodeids", "txt"), ("junit", "xml"))}
        assert set(reports) == expected


@pytest.mark.parametrize("state", ["complete", "missing", "empty"])
def test_incomplete_reports_fail_validation__ci_012(tmp_path: Path, state: str) -> None:
    """CI-012: artifact success cannot conceal missing or empty required reports."""
    # Given: the real validation shell and a complete or deliberately broken report set.
    job = _workflow()["jobs"]["full-suite"]
    step = next(step for step in job["steps"] if 'test -s "$report"' in step.get("run", ""))
    reports = _reports(job)
    for report in reports:
        path = tmp_path / report
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("report\n", encoding="utf-8")
    for report in reports if state != "complete" else []:
        # When: one report at a time is broken, GitHub's bash error handling runs the step.
        if state == "missing":
            (tmp_path / report).unlink()
        else:
            (tmp_path / report).write_text("", encoding="utf-8")
        result = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", step["run"]], cwd=tmp_path, capture_output=True, text=True, check=False)
        # Then: every missing or empty individual report fails before upload.
        assert result.returncode != 0, report
        (tmp_path / report).write_text("report\n", encoding="utf-8")
    result = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", step["run"]], cwd=tmp_path, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def _listing(path: Path, nodeids: list[str]) -> Path:
    path.write_text("".join(f"{nodeid}\n" for nodeid in nodeids) + f"\n{len(nodeids)} tests collected in 1.00s\n", encoding="utf-8")
    return path


FULL = ["tests/test_a.py::test_one", "tests/v2/test_b.py::test_two[x]", "tests/v2/test_b.py::test_two[\\x1f\\x8b\\x01]", "tests/v2/test_c.py::TestC::test_three"]


@pytest.mark.parametrize(
    ("root", "v2", "passes"),
    [
        (FULL[:1], FULL[1:], True),
        (FULL[:1], FULL[1:3], False),
        (FULL[:1], [*FULL[1:], "tests/v2/test_d.py::test_new"], False),
        (FULL[:2], FULL[1:], False),
        ([], FULL, False),
        (FULL[:1], [*FULL[1:], FULL[3]], False),
        (FULL[:1], [FULL[1], "tests/v2/test_b.py::test_two[\\x1f\\x8b\\x02]", FULL[3]], True),
        (FULL[:1], [FULL[1], FULL[3]], False),
        (FULL[:1], [FULL[1], "tests/v2/test_b.py::test_two[\\x1f\\x8b\\x02]", "tests/v2/test_b.py::test_two[\\x1f\\x8b\\x03]", FULL[3]], False),
    ],
    ids=["exact", "missing", "extra", "duplicate", "empty-shard", "repeated", "id-drift", "drift-missing", "drift-extra"],
)
def test_partition_check__ci_013(tmp_path: Path, root: list[str], v2: list[str], passes: bool) -> None:
    """CI-013: the real partition script fails on any missing, extra or duplicate case."""
    # Given: a complete listing and two shard listings in pytest's -q format.
    full = _listing(tmp_path / "full.txt", FULL)
    shards = [_listing(tmp_path / "nodeids-tests-root.txt", root), _listing(tmp_path / "nodeids-tests-v2.txt", v2)]
    # When: executing the script exactly as the aggregate job does.
    result = subprocess.run([sys.executable, str(ROOT / "scripts/check_test_partition.py"), str(full), *map(str, shards)], capture_output=True, text=True, check=False)
    # Then: only an exact partition, up to same-function ID drift, passes.
    assert (result.returncode == 0) is passes, result.stdout + result.stderr


@pytest.mark.parametrize(("status", "passes"), [("success", True), ("failure", False), ("cancelled", False), ("skipped", False), ("", False)])
def test_aggregate_requires_every_shard__ci_014(status: str, passes: bool) -> None:
    """CI-014: a failed, cancelled, skipped or absent shard result fails the aggregate."""
    # Given: the aggregate's real first step and a matrix result.
    step = _workflow()["jobs"]["full-suite"]["steps"][0]
    # When: GitHub's bash runs it with the result GitHub would substitute.
    result = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", step["run"]], env={**os.environ, "SHARDS": status}, capture_output=True, text=True, check=False)
    # Then: only an all-successful matrix continues.
    assert (result.returncode == 0) is passes


def _combine_commands(job: dict[str, Any]) -> str:
    step = next(step for step in job["steps"] if "coverage combine" in step.get("run", ""))
    report = next(step for step in job["steps"] if "coverage report" in step.get("run", ""))
    return (step["run"] + report["run"]).replace(".venv/bin/python", shlex.quote(sys.executable)).replace("pyproject.toml", shlex.quote(str(ROOT / "pyproject.toml")))


@pytest.mark.parametrize(("last", "passes"), [(20, True), (19, False), (None, False)], ids=["combined-80", "combined-79", "absent-shard"])
def test_gates_apply_to_combined_coverage__ci_015(tmp_path: Path, last: int | None, passes: bool) -> None:
    """CI-015: no shard alone reaches 80%, the combined data decides, and an absent shard fails."""
    # Given: four shards that each cover a disjoint 20-line part of the same 100-line module.
    source = tmp_path / "rdetoolkit" / MODULES[0]
    source.parent.mkdir(parents=True)
    source.write_text("\n".join(f"value_{line} = {line}" for line in range(1, 101)) + "\n", encoding="utf-8")
    (tmp_path / "shards").mkdir()
    (tmp_path / "ci-results").mkdir()
    names = list(_shards(_workflow()["jobs"]["pytest-shard"]))
    assert len(names) == 4
    for index, name in enumerate(names):
        count = last if index == len(names) - 1 else 20
        if count is not None:
            data = coverage.CoverageData(basename=str(tmp_path / "shards" / f".coverage.{name}"))
            lines = range(1 + 20 * index, 1 + 20 * index + count)
            data.add_arcs({str(source): [(-1, lines[0]), *zip(lines, lines[1:], strict=False), (lines[-1], -1)]})
            data.write()
    # When: running the aggregate's real combine and overall-gate commands.
    env = {key: value for key, value in os.environ.items() if not key.startswith("COVERAGE_")}
    result = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", _combine_commands(_workflow()["jobs"]["full-suite"])], cwd=tmp_path, env=env, capture_output=True, text=True, check=False)
    # Then: the overall gate judges the union; a missing shard cannot pass.
    assert (result.returncode == 0) is passes, result.stdout + result.stderr
    if passes:
        assert (tmp_path / "ci-results" / "coverage.json").stat().st_size > 0
