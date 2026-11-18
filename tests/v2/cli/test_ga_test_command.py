"""GA-14 (#694): the thin ``rdetoolkit test`` wrapper around pytest.

``rdetoolkit test ARGS...`` must behave exactly like ``python -m pytest
ARGS...``: same collection, markers, fixtures, output and exit code. The end
to end cases therefore run ``python -m rdetoolkit test`` in a subprocess on a
generated suite and compare with pytest's own contract.

EP table
========

| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-TEST-EP-001 | pass | passing suite | exit 0, pytest summary |
| TC-TEST-EP-002 | failed assertion | failing test | exit 1, pytest's rewritten assertion context kept |
| TC-TEST-EP-003 | no tests | empty directory | exit 5 (pytest's "no tests collected") |
| TC-TEST-EP-004 | ``-k`` | keyword selection | only the selected tests run |
| TC-TEST-EP-005 | ``-m`` / ``-x`` / ``-v`` / ``-q`` | marker, fail-fast, verbosity | forwarded unchanged |
| TC-TEST-EP-006 | parametrization | parametrized ids | listed by pytest |
| TC-TEST-EP-007 | rde_case | failing case | ``rdetoolkit: retained runs`` section with retained paths; absent on success |
| TC-TEST-EP-008 | cwd / paths | relative, absolute and OS-separator paths | resolved like pytest |
| TC-TEST-EP-009 | ``--`` | ``rdetoolkit test -- --help`` | pytest's own help |
| TC-TEST-EP-010 | parallel | two concurrent invocations using rde_runner | both pass in separate temp roots |
| TC-TEST-EP-011 | help | ``rdetoolkit test --help`` | thin-wrapper help with examples and exit codes |
| TC-TEST-EP-012 | equivalence | same args to ``python -m pytest`` | same exit code and test list |

BV / negative table
===================

| TC | Boundary | Input | Expected |
|----|----------|-------|----------|
| TC-TEST-BV-001 | missing pytest | pytest not importable | exit 2, installation hint, no traceback |
| TC-TEST-BV-002 | no pytest at all | blocked pytest import | ``import rdetoolkit``, the CLI app and ``--help`` still work |
| TC-TEST-BV-003 | packaging | pyproject | pytest only in the optional ``testing`` extra |
| TC-TEST-BV-004 | pytest usage error | unknown pytest option | pytest's exit 4 passed through |
| TC-TEST-BV-005 | interrupt | KeyboardInterrupt while pytest runs | exit 2 (pytest's "interrupted") |
| TC-TEST-BV-006 | command | argument forwarding | exactly ``[sys.executable, "-m", "pytest", *args]`` |
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli import test_cmd
from rdetoolkit.cli.app import app

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE = REPO_ROOT / "tests" / "v2" / "testing" / "fixtures" / "rde_case" / "sample"

_SUITE = '''
import pytest


def test_alpha():
    assert 1 + 1 == 2


def test_beta():
    assert 2 * 2 == 4


@pytest.mark.slow
def test_gamma_slow():
    pass


@pytest.mark.parametrize("value", [1, 2], ids=["one", "two"])
def test_param(value):
    assert value > 0
'''

_FAILING = '''
def test_first_failure():
    observed = {"temperature": 301}
    assert observed["temperature"] == 300


def test_second_failure():
    assert False
'''

_RDE_CASE = '''
from pathlib import Path

from rdetoolkit import flow
from rdetoolkit.testing import rde_case
from rdetoolkit.types import InputPaths, OutputContext

PROJECT = Path({project!r})


@flow(id="tests.ga694.writes")
def writes(paths: InputPaths, out: OutputContext) -> None:
    out.write_bytes("struct", "result.csv", b"time,value\\n0,1\\n")


@flow(id="tests.ga694.fails")
def fails(paths: InputPaths) -> None:
    raise ValueError("reader failed")


@rde_case(flow=writes, project=PROJECT, expect_files=("structured/result.csv",))
def test_passing_case(rde_run):
    pass


@rde_case(flow=fails, project=PROJECT)
def test_failing_case(rde_run):
    pass


def test_failing_runner(rde_runner):
    first = rde_runner.run(flow=writes, project=PROJECT)
    second = rde_runner.run(flow=fails, project=PROJECT)
    assert second.status == "success"
'''


def _write(root: Path, name: str, body: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def _ini(root: Path) -> None:
    # The generated suite is its own rootdir: no repository addopts (--mpl).
    _write(root, "pytest.ini", "[pytest]\nmarkers =\n    slow: slow tests\n")


def _cli(cwd: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "rdetoolkit", "test", "-p", "no:cacheprovider", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
        env={**os.environ, **(env or {})},
    )


def _pytest(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )


def _ran(stdout: str) -> list[str]:
    """Return the node ids pytest reported with -v, in order."""
    return [line.split(" ")[0] for line in stdout.splitlines() if " PASSED" in line or " FAILED" in line]


@pytest.fixture
def suite(tmp_path: Path) -> Path:
    """A generated pytest project with passing, marked and parametrized tests."""
    _ini(tmp_path)
    _write(tmp_path, "tests/test_suite.py", _SUITE)
    return tmp_path


# ------------------------------------------------------------------------ EP


def test_passing_suite__tc_test_ep_001(suite: Path) -> None:
    """TC-TEST-EP-001: a passing suite exits 0 with pytest's own summary."""
    # When
    completed = _cli(suite)
    # Then
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "5 passed" in completed.stdout


def test_failed_assertion_keeps_pytest_context__tc_test_ep_002(tmp_path: Path) -> None:
    """TC-TEST-EP-002: a failure exits 1 and pytest's assertion introspection is shown unchanged."""
    # Given
    _ini(tmp_path)
    _write(tmp_path, "tests/test_failing.py", _FAILING)
    # When
    completed = _cli(tmp_path)
    # Then
    assert completed.returncode == 1, completed.stdout
    assert "assert 301 == 300" in completed.stdout
    assert "2 failed" in completed.stdout
    assert "rdetoolkit: retained runs" not in completed.stdout


def test_no_tests_collected__tc_test_ep_003(tmp_path: Path) -> None:
    """TC-TEST-EP-003: pytest's exit 5 is passed through."""
    # Given
    _ini(tmp_path)
    (tmp_path / "tests").mkdir()
    # When
    completed = _cli(tmp_path, "tests")
    # Then
    assert completed.returncode == 5, completed.stdout
    assert "no tests ran" in completed.stdout


def test_keyword_selection_is_forwarded__tc_test_ep_004(suite: Path) -> None:
    """TC-TEST-EP-004 (mutation check): -k changes the selected-test list exactly as in pytest."""
    # When
    selected = _cli(suite, "-v", "-k", "alpha or param")
    everything = _cli(suite, "-v")
    # Then
    assert selected.returncode == 0, selected.stdout
    assert _ran(selected.stdout) == [
        "tests/test_suite.py::test_alpha",
        "tests/test_suite.py::test_param[one]",
        "tests/test_suite.py::test_param[two]",
    ]
    assert _ran(selected.stdout) != _ran(everything.stdout)


def test_marker_failfast_and_verbosity__tc_test_ep_005(suite: Path) -> None:
    """TC-TEST-EP-005: -m, -x, -q and -v reach pytest unchanged."""
    # Given: a second module with two failures
    _write(suite, "tests/test_failing.py", _FAILING)
    # When
    marked = _cli(suite, "-v", "-m", "slow", "tests/test_suite.py")
    failfast = _cli(suite, "-x", "tests/test_failing.py")
    quiet = _cli(suite, "-q", "tests/test_suite.py")
    # Then
    assert _ran(marked.stdout) == ["tests/test_suite.py::test_gamma_slow"]
    assert failfast.returncode == 1
    assert "1 failed" in failfast.stdout
    assert "2 failed" not in failfast.stdout
    assert "5 passed" in quiet.stdout
    assert "test_suite.py::test_alpha PASSED" not in quiet.stdout


def test_parametrized_ids__tc_test_ep_006(suite: Path) -> None:
    """TC-TEST-EP-006: parametrization and its ids are pytest's."""
    # When
    completed = _cli(suite, "-v", "-k", "param")
    # Then
    assert _ran(completed.stdout) == ["tests/test_suite.py::test_param[one]", "tests/test_suite.py::test_param[two]"]


def test_rde_case_failure_lists_retained_runs__tc_test_ep_007(tmp_path: Path) -> None:
    """TC-TEST-EP-007: failing RDE tests point at their retained runs; passing ones do not."""
    # Given
    _ini(tmp_path)
    _write(tmp_path, "tests/test_rde.py", _RDE_CASE.format(project=str(FIXTURE)))
    # When
    completed = _cli(tmp_path, "--basetemp", str(tmp_path / "bt"))
    # Then: pytest's failure context first, then the retained runs per failing test
    assert completed.returncode == 1, completed.stdout
    assert "1 passed" in completed.stdout
    assert "2 failed" in completed.stdout
    assert "RDE run status was 'failed', expected 'success'" in completed.stdout
    assert completed.stdout.count("rdetoolkit: retained runs") == 2
    failing_case = completed.stdout.split("test_failing_case", 2)[2]
    assert "run 1: status 'failed' (flow 'tests.ga694.fails'" in failing_case
    assert f"data root: {tmp_path / 'bt'}" in failing_case
    assert "job.failed:" in failing_case
    runner_section = completed.stdout.split("rdetoolkit: retained runs")[-1]
    assert "run 1: status 'success' (flow 'tests.ga694.writes'" in runner_section
    assert "run 2: status 'failed' (flow 'tests.ga694.fails'" in runner_section
    assert "test_passing_case" not in "".join(completed.stdout.split("rdetoolkit: retained runs")[1:2])


def test_paths_and_cwd__tc_test_ep_008(suite: Path) -> None:
    """TC-TEST-EP-008: relative (OS separator), absolute and nested-cwd paths behave as in pytest."""
    # Given
    relative = os.path.join("tests", "test_suite.py")
    absolute = str(suite / "tests" / "test_suite.py")
    # When
    from_root = _cli(suite, "-q", relative)
    from_absolute = _cli(suite / "tests", "-q", absolute)
    from_inside = _cli(suite / "tests", "-q", "test_suite.py::test_alpha")
    # Then
    assert "5 passed" in from_root.stdout
    assert "5 passed" in from_absolute.stdout
    assert "1 passed" in from_inside.stdout


def test_double_dash_forwards_options__tc_test_ep_009(suite: Path) -> None:
    """TC-TEST-EP-009: after '--' even --help goes to pytest."""
    # When
    completed = _cli(suite, "--", "--help")
    # Then
    assert completed.returncode == 0
    assert "usage:" in completed.stdout
    assert "--rde-update-snapshots" in completed.stdout


def test_parallel_invocations__tc_test_ep_010(tmp_path: Path) -> None:
    """TC-TEST-EP-010: concurrent runs use separate pytest temp roots and never collide."""
    # Given: two suites staging the same project with rde_runner
    body = '''
        from pathlib import Path
        from rdetoolkit import flow
        from rdetoolkit.types import InputPaths

        @flow(id="tests.ga694.parallel")
        def pipeline(paths: InputPaths) -> None:
            pass

        def test_run(rde_runner):
            run = rde_runner.run(flow=pipeline, project=Path({project!r}))
            run.assert_success()
            print("DATA_ROOT", run.data_root)
    '''
    suites = []
    for name in ("one", "two"):
        root = tmp_path / name
        _ini(root)
        _write(root, "tests/test_parallel.py", body.format(project=str(FIXTURE)))
        suites.append(root)
    # When: both start before either finishes
    processes = [
        subprocess.Popen(  # noqa: S603
            [sys.executable, "-m", "rdetoolkit", "test", "-p", "no:cacheprovider", "-s", "--basetemp", str(root / "bt")],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for root in suites
    ]
    outputs = [process.communicate(timeout=300)[0] for process in processes]
    # Then
    assert [process.returncode for process in processes] == [0, 0], outputs
    # With -s the print lands on pytest's progress line, after the file name.
    roots = [line.split("DATA_ROOT ", 1)[1].split(" ")[0] for output in outputs for line in output.splitlines() if "DATA_ROOT " in line]
    assert len(set(roots)) == 2
    assert all(Path(root).is_relative_to(suite / "bt") for root, suite in zip(roots, suites, strict=True))


def test_help__tc_test_ep_011() -> None:
    """TC-TEST-EP-011: the help explains the thin wrapper and the pytest equivalence."""
    # When
    result = CliRunner().invoke(app, ["test", "--help"], env={"COLUMNS": "200", "NO_COLOR": "1"})
    # Then
    assert result.exit_code == 0
    assert "python -m pytest" in result.output
    assert "rdetoolkit[testing]" in result.output
    assert "Exit codes" in result.output


def test_same_result_as_pytest__tc_test_ep_012(suite: Path) -> None:
    """TC-TEST-EP-012: rdetoolkit test ARGS and python -m pytest ARGS agree."""
    # Given
    _write(suite, "tests/test_failing.py", _FAILING)
    args = ("-v", "-k", "not second")
    # When
    wrapped, direct = _cli(suite, *args), _pytest(suite, *args)
    # Then
    assert wrapped.returncode == direct.returncode == 1
    assert _ran(wrapped.stdout) == _ran(direct.stdout)


# ------------------------------------------------------------------------ BV


def test_missing_pytest_is_a_usage_error__tc_test_bv_001(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-TEST-BV-001: without pytest the command explains how to install it."""
    # Given
    monkeypatch.setattr(test_cmd, "pytest_available", lambda: False)
    calls: list[object] = []
    monkeypatch.setattr(test_cmd.subprocess, "run", lambda *a, **k: calls.append(a))
    # When
    result = CliRunner().invoke(app, ["test", "tests"])
    # Then
    assert result.exit_code == 2
    assert "pytest is not installed" in result.stderr
    assert 'pip install "rdetoolkit[testing]"' in result.stderr
    assert "Traceback" not in result.output
    assert calls == []


_NO_PYTEST = r'''
import importlib.abc
import sys


class _BlockPytest(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname in {"pytest", "_pytest"} or fullname.startswith(("pytest.", "_pytest.")):
            raise ModuleNotFoundError(f"No module named {fullname!r}", name=fullname)
        return None


sys.meta_path.insert(0, _BlockPytest())
for name in [name for name in sys.modules if name.startswith(("pytest", "_pytest"))]:
    del sys.modules[name]

import rdetoolkit
from rdetoolkit.cli import test_cmd
from rdetoolkit.cli.app import app

assert test_cmd.pytest_available() is False
assert "pytest" not in sys.modules
app(sys.argv[1:])
'''


@pytest.mark.parametrize(
    ("argv", "code", "fragment", "stream"),
    [
        pytest.param(["test", "-k", "x"], 2, 'pip install "rdetoolkit[testing]"', "stderr", id="test"),
        pytest.param(["--help"], 0, "Run the project's pytest tests", "stdout", id="root-help"),
        pytest.param(["run", "--help"], 0, "REF", "stdout", id="run-help"),
    ],
)
def test_cli_without_pytest__tc_test_bv_002(tmp_path: Path, argv: list[str], code: int, fragment: str, stream: str) -> None:
    """TC-TEST-BV-001/002: the package and the CLI work where pytest is not installed."""
    # Given
    script = tmp_path / "no_pytest.py"
    script.write_text(_NO_PYTEST, encoding="utf-8")
    # When
    completed = subprocess.run(  # noqa: S603
        [sys.executable, str(script), *argv],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
        env={**os.environ, "COLUMNS": "200", "NO_COLOR": "1"},
    )
    # Then
    assert completed.returncode == code, completed.stdout + completed.stderr
    assert fragment in getattr(completed, stream)
    assert "Traceback" not in completed.stderr


def test_pytest_is_only_an_optional_extra__tc_test_bv_003() -> None:
    """TC-TEST-BV-003: a normal installation does not pull in pytest."""
    # Given
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    # Then
    assert not [dep for dep in project["dependencies"] if dep.lower().startswith("pytest")]
    assert [dep for dep in project["optional-dependencies"]["testing"] if dep.startswith("pytest")] == ["pytest>=7.4.0"]


def test_pytest_usage_error_passes_through__tc_test_bv_004(suite: Path) -> None:
    """TC-TEST-BV-004: pytest's own usage error (exit 4) is not rewritten."""
    # When
    completed = _cli(suite, "--no-such-pytest-option")
    # Then
    assert completed.returncode == 4
    assert "--no-such-pytest-option" in completed.stderr


def test_interrupt_exits_like_pytest__tc_test_bv_005(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-TEST-BV-005: Ctrl-C during the run exits 2, pytest's 'interrupted'."""
    # Given
    def interrupted(*args: object, **kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(test_cmd.subprocess, "run", interrupted)
    # When
    result = CliRunner().invoke(app, ["test"])
    # Then
    assert result.exit_code == 2


def test_arguments_are_forwarded_verbatim__tc_test_bv_006(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-TEST-BV-006: the command is python -m pytest with the arguments in order."""
    # Given
    seen: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(command)
        assert kwargs == {"check": False}
        return subprocess.CompletedProcess(command, 3)

    monkeypatch.setattr(test_cmd.subprocess, "run", fake_run)
    argv = ["tests/unit", "-k", "a and not b", "-m", "slow", "-x", "-vv", "--maxfail=2", "-p", "no:cacheprovider", "path with space/test_x.py"]
    # When
    result = CliRunner().invoke(app, ["test", *argv])
    # Then
    assert result.exit_code == 3
    assert seen == [[sys.executable, "-m", "pytest", *argv]]
    assert test_cmd.pytest_command(["a"]) == [sys.executable, "-m", "pytest", "a"]
