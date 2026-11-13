"""Executable policy for the develop/v2 CI gate (Issue #748).

EP table (written before implementation):

| Partition | Expected | Test ID |
| --- | --- | --- |
| develop/v2 PR | dedicated, read-only, cancelling workflow | CI-001 |
| full-suite command | one complete run, existing selection, reports and gates | CI-002 |
| weakened command or condition | policy rejects the regression | CI-003 |
| quality and Rust jobs | real lint/type/check/clippy/test commands | CI-004 |
| old coverage workflows | v2 excluded and no repository-writing badge | CI-005 |
| installed wheel | clean environment and original compatibility tests | CI-006 |
| existing main matrix | five Python versions, three tox environments | CI-007 |
| each scoped module below 95, including branch-only deficit | actual subprocess fails | CI-008 |
| required-job status failures/missing jobs | final required check fails closed | CI-011 |
| report absent or empty | report validation fails | CI-012 |

BV table:

| Boundary | Expected | Test ID |
| --- | --- | --- |
| total coverage 79%, 80% | fail, pass | CI-009 |
| scoped coverage 94%, 95% | fail, pass | CI-008, CI-010 |
| full-suite gate has zero positional arguments | scoped checks cannot skip | CI-002 |

Flow semantics and RDE error codes are outside this workflow-only change.
"""

from __future__ import annotations

from pathlib import Path
from copy import deepcopy
import os
import json
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
REQUIRED_JOBS = ("full-suite", "quality", "rust", "wheel-install-gate", "changelog")
REPORTS = ("ci-results/test-nodeids.txt", "ci-results/junit.xml", "ci-results/coverage.xml", "ci-results/coverage.json", ".coverage")


def _workflow(name: str = "v2-ci.yml") -> dict[str, Any]:
    # BaseLoader constructs only strings/containers and preserves GitHub's `on` key.
    return yaml.load((ROOT / ".github/workflows" / name).read_text(encoding="utf-8"), Loader=yaml.BaseLoader)  # noqa: S506


def _commands(job: dict[str, Any]) -> list[list[str]]:
    commands = []
    for step in job["steps"]:
        for line in step.get("run", "").replace("\\\n", " ").splitlines():
            tokens = shlex.split(line, comments=True)
            if tokens:
                tokens[0] = Path(tokens[0]).name
                commands.append(tokens)
    return commands


def _full_suite_policy(job: dict[str, Any]) -> None:
    assert "if" not in job
    assert job.get("continue-on-error", "false") == "false"
    assert "matrix" not in job.get("strategy", {})
    commands = _commands(job)
    pytest_commands = [command for command in commands if command[:3] == ["python", "-m", "pytest"] and "--collect-only" not in command]
    assert len(pytest_commands) == 1
    command = pytest_commands[0]
    assert "tests/" in command
    assert not any(argument.startswith("tests/") and argument != "tests/" for argument in command)
    assert not any(token in command[3:] for token in ("-m", "-k", "-o", "--override-ini", "--ignore", "--ignore-glob", "||"))
    assert not any(token.startswith(("--ignore=", "--ignore-glob=", "--override-ini=")) for token in command)
    assert "--cov=rdetoolkit" in command
    assert "--cov-config=pyproject.toml" in command
    assert "--cov-fail-under=80" in command
    assert "--durations=30" in command
    assert any(token.startswith("--junitxml=") for token in command)
    assert any(token.startswith("--cov-report=xml") for token in command)
    assert any(token.startswith("--cov-report=json") for token in command)
    gate_commands = [command for command in commands if "scripts/check_phase_h_coverage.py" in command]
    assert gate_commands == [["python", "scripts/check_phase_h_coverage.py"]]
    for step in job["steps"]:
        if "python -m pytest" in step.get("run", "") or "scripts/check_phase_h_coverage.py" in step.get("run", ""):
            assert step.get("continue-on-error", "false") == "false"
            assert "if" not in step
        if "python -m pytest" in step.get("run", ""):
            assert {**job.get("env", {}), **step.get("env", {})}["HYPOTHESIS_PROFILE"] == "ci"


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
    assert set(workflow["jobs"]) == {"full-suite", "quality", "rust", "wheel-install-gate", "changelog", "required"}
    assert all(job.get("permissions", {"contents": "read"}) == {"contents": "read"} for job in workflow["jobs"].values())


def test_full_suite_and_reports__ci_002() -> None:
    """CI-002: one complete run produces retained diagnostics and both gates."""
    # Given: the single canonical full-suite job.
    job = _workflow()["jobs"]["full-suite"]
    # When/Then: execution policy retains all tests and coverage gates.
    _full_suite_policy(job)
    setups = [step for step in job["steps"] if step.get("uses", "").startswith(("actions/setup-python@", "astral-sh/setup-uv@"))]
    assert any(step["with"].get("python-version") == "3.12" for step in setups)
    uploads = [step for step in job["steps"] if step.get("uses", "").startswith("actions/upload-artifact@")]
    assert uploads
    assert any("always()" in step.get("if", "") for step in uploads)
    paths = [path.strip().rstrip("/") for step in uploads for path in step["with"]["path"].splitlines()]
    command = next(command for command in _commands(job) if "--cov=rdetoolkit" in command)
    reports = [argument.split("=", 1)[1] for argument in command if argument.startswith("--junitxml=")]
    reports += [argument.split(":", 1)[1] for argument in command if argument.startswith(("--cov-report=xml:", "--cov-report=json:"))]
    assert len(reports) == 3
    assert all(any(report == path or report.startswith(path + "/") for path in paths) for report in reports)
    assert ".coverage" in paths
    assert any(step["with"].get("include-hidden-files") == "true" and step["with"].get("if-no-files-found") == "error" for step in uploads)


@pytest.mark.parametrize(
    ("original", "replacement"),
    [
        ("tests/", "tests/v2/"),
        ("--cov-fail-under=80", "--cov-fail-under=79"),
        ("--cov=rdetoolkit", "--cov=rdetoolkit.runner"),
        ("--cov-config=pyproject.toml", "--cov-config=/dev/null"),
        ("--durations=30", "--durations=0"),
        ("python -m pytest", "python -m pytest -m 'not graph_outputs'"),
        ("python -m pytest", "python -m pytest -o addopts=''"),
        ("python -m pytest", "python -m pytest --ignore=tests/v2"),
        ("scripts/check_phase_h_coverage.py", "scripts/check_phase_h_coverage.py tests/"),
        ("scripts/check_phase_h_coverage.py", "scripts/check_phase_h_coverage.py || true"),
    ],
)
def test_weakened_full_suite_is_rejected__ci_003(original: str, replacement: str) -> None:
    """CI-003: removing collection, measurement or enforcement is detectable."""
    # Given: a mutation of the real workflow command.
    job = deepcopy(_workflow()["jobs"]["full-suite"])
    changed = False
    for step in job["steps"]:
        if original in step.get("run", ""):
            step["run"] = step["run"].replace(original, replacement)
            changed = True
    assert changed
    # When/Then: the same policy oracle rejects the weakened command.
    with pytest.raises(AssertionError):
        _full_suite_policy(job)


@pytest.mark.parametrize("mutation", ["skip-job", "ignore-job-failure", "skip-step", "ignore-step-failure", "wrong-profile"])
def test_bypassed_full_suite_is_rejected__ci_003(mutation: str) -> None:
    """CI-003: conditions and failure suppression cannot turn gates green."""
    # Given: a bypass injected into the real job or its pytest step.
    job = deepcopy(_workflow()["jobs"]["full-suite"])
    step = next(step for step in job["steps"] if "python -m pytest" in step.get("run", ""))
    target = job if mutation.endswith("job") or mutation == "ignore-job-failure" else step
    if mutation.startswith("skip"):
        target["if"] = "false"
    elif mutation.startswith("ignore"):
        target["continue-on-error"] = "true"
    else:
        step.setdefault("env", {})["HYPOTHESIS_PROFILE"] = "dev"
    # When/Then: skipped or non-gating tests violate the same policy.
    with pytest.raises(AssertionError):
        _full_suite_policy(job)


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
    command = next(command for command in _commands(_workflow()["jobs"]["full-suite"]) if "--cov=rdetoolkit" in command)
    threshold = next(argument.split("=", 1)[1] for argument in command if argument.startswith("--cov-fail-under="))
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


@pytest.mark.parametrize(("report", "state"), [(None, "complete"), *[(report, state) for report in REPORTS for state in ("missing", "empty")]])
def test_incomplete_reports_fail_validation__ci_012(tmp_path: Path, report: str | None, state: str) -> None:
    """CI-012: artifact success cannot conceal missing or empty required reports."""
    # Given: the real validation shell and a complete or deliberately broken report set.
    job = _workflow()["jobs"]["full-suite"]
    step = next(step for step in job["steps"] if 'test -s "$report"' in step.get("run", ""))
    for name in REPORTS:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if name != report or state != "missing":
            path.write_text("" if name == report and state == "empty" else "report\n", encoding="utf-8")
    # When: GitHub's bash error handling executes the report validation step.
    result = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", step["run"]], cwd=tmp_path, capture_output=True, text=True, check=False)
    # Then: every missing or empty individual report fails before upload.
    assert (result.returncode == 0) is (report is None), result.stdout + result.stderr
