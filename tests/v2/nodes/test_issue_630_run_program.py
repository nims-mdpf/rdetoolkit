"""Tests for the ``run_program`` builtin node (#630).

EP table
| Target | Partition | Expected | Test ID |
|---|---|---|---|
| ``run_program`` | exit 0 | ``CompletedProgram`` with command, code, output, duration | GA630-EP-1 |
| ``run_program`` | ``Path`` / ``str`` arguments, ``cwd`` | arguments as text, program runs in ``cwd`` | GA630-EP-2 |
| ``run_program`` | ``env`` | added to the inherited environment | GA630-EP-3 |
| ``run_program`` | non-zero exit | ``StructuredError`` code 1 with command, code and stderr tail | GA630-EP-4 |
| ``run_program`` | ``error_code`` / ``error_message`` | template code; message used verbatim | GA630-EP-5 |
| ``run_program`` | missing program / timeout | ``StructuredError`` naming the program / timeout | GA630-EP-6 |
| ``run_program`` | ``wine=True`` | ``wine`` prefix, ``Path`` arguments in Windows form | GA630-EP-7 |
| ``run_program`` | ``wine="auto"`` on Windows / elsewhere | no prefix / prefix | GA630-EP-8 |
| ``to_wine_path`` | absolute / relative / Windows host | ``Z:\\...`` / backslashes / unchanged | GA630-EP-9 |
| ``run_program`` | flow run, non-zero exit | RunReport, ``job.failed`` and failed call record carry the code | GA630-EP-10 |

BV table
| Target | Boundary | Expected | Test ID |
|---|---|---|---|
| ``run_program`` | empty argument list / a bare string | ``ValueError`` / ``TypeError`` before anything runs | GA630-BV-1 |
| ``run_program`` | stderr longer than the tail | only the last lines in the message | GA630-BV-2 |
"""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from rdetoolkit.exceptions import StructuredError

_PYTHON = sys.executable


def _script(code: str) -> list[str]:
    return [_PYTHON, "-c", code]


def test_success_returns_completed_program__ga630_ep_1() -> None:
    """GA630-EP-1: a zero exit returns the command, output and duration."""
    from rdetoolkit.nodes import CompletedProgram, run_program

    # Given: a converter writing to both streams
    args = _script("import sys; print('out'); print('err', file=sys.stderr)")
    # When: running it
    result = run_program(args)
    # Then: everything needed to reproduce and inspect the call is returned
    assert isinstance(result, CompletedProgram)
    assert result.args == tuple(args)
    assert result.returncode == 0
    assert result.stdout == "out\n"
    assert result.stderr == "err\n"
    assert result.duration >= 0


def test_path_arguments_and_cwd__ga630_ep_2(tmp_path: Path) -> None:
    """GA630-EP-2: ``Path`` arguments become text and ``cwd`` is the working directory."""
    from rdetoolkit.nodes import run_program

    # Given: a converter writing an output file named by a Path argument
    target = tmp_path / "structured" / "export.txt"
    target.parent.mkdir()
    code = "import os, sys; open(sys.argv[1], 'w').write(os.getcwd())"
    # When: running it with a Path argument and a working directory
    result = run_program([Path(_PYTHON), "-c", code, target], cwd=tmp_path)
    # Then: the argument reached the program as a path, and cwd applied
    assert result.args == (_PYTHON, "-c", code, str(target))
    assert Path(target.read_text(encoding="utf-8")).resolve() == tmp_path.resolve()


def test_env_extends_inherited_environment__ga630_ep_3(monkeypatch: pytest.MonkeyPatch) -> None:
    """GA630-EP-3: ``env`` entries are added to, not substituted for, the environment."""
    from rdetoolkit.nodes import run_program

    # Given: an inherited variable and an explicit one
    monkeypatch.setenv("GA630_INHERITED", "kept")
    code = "import os; print(os.environ['GA630_INHERITED'], os.environ['GA630_EXTRA'])"
    # When: running with env
    result = run_program(_script(code), env={"GA630_EXTRA": "added"})
    # Then: both are visible to the program
    assert result.stdout.split() == ["kept", "added"]


def test_nonzero_exit_raises_structured_error__ga630_ep_4() -> None:
    """GA630-EP-4: a non-zero exit is StructuredError code 1 with command and stderr tail."""
    from rdetoolkit.nodes import run_program

    # Given: a converter failing with a message on stderr
    args = _script("import sys; print('bad header', file=sys.stderr); sys.exit(3)")
    # When: running it
    with pytest.raises(StructuredError) as excinfo:
        run_program(args)
    # Then: the error names the exit code, the command and the stderr tail
    error = excinfo.value
    assert error.ecode == 1
    assert "exit code 3" in error.emsg
    assert _PYTHON in error.emsg
    assert "bad header" in error.emsg
    assert "\n" not in error.emsg


def test_template_error_code_and_message__ga630_ep_5() -> None:
    """GA630-EP-5: ``error_code`` sets the code and ``error_message`` is used verbatim."""
    from rdetoolkit.nodes import run_program

    # Given: a template that reports converter failures with its own code
    args = _script("import sys; sys.exit(2)")
    # When: the converter fails
    with pytest.raises(StructuredError) as excinfo:
        run_program(args, error_code=51, error_message="MPExport failed")
    # Then: job.failed would show the template's code and message
    assert excinfo.value.ecode == 51
    assert excinfo.value.emsg == "MPExport failed"
    assert excinfo.value.eobj.returncode == 2


@pytest.mark.parametrize(
    ("args", "timeout", "expected"),
    [
        (["ga630-no-such-program"], None, "ga630-no-such-program"),
        (_script("import time; time.sleep(30)"), 0.5, "timed out after 0.5s"),
    ],
    ids=["missing", "timeout"],
)
def test_missing_program_and_timeout__ga630_ep_6(args: list[str], timeout: float | None, expected: str) -> None:
    """GA630-EP-6: a missing program and a timeout are StructuredError, not OSError / TimeoutExpired."""
    from rdetoolkit.nodes import run_program

    # Given: a program that cannot start, or one that does not finish in time
    # When: running it
    with pytest.raises(StructuredError) as excinfo:
        run_program(args, timeout=timeout, error_code=52)
    # Then: the template code applies and the message says what happened
    assert excinfo.value.ecode == 52
    assert expected in excinfo.value.emsg


@pytest.fixture
def fake_wine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Replace the wine launcher with a script that prints the arguments it receives."""
    launcher = tmp_path / "fake-wine"
    launcher.write_text(f"#!{_PYTHON}\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\n", encoding="utf-8")
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setattr("rdetoolkit.nodes.external._WINE", str(launcher))
    return launcher


@pytest.mark.skipif(os.name == "nt", reason="the fake launcher is a POSIX script")
def test_wine_prefix_and_windows_paths__ga630_ep_7(fake_wine: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA630-EP-7: ``wine=True`` prefixes the launcher and converts Path arguments only."""
    import json

    from rdetoolkit.nodes import run_program

    # Given: a Windows converter on a POSIX host
    monkeypatch.setattr("rdetoolkit.nodes.external._on_windows", lambda: False)
    args = [Path("/opt/phi/MPExport.exe"), "-Filename:raw.spe", Path("/data/structured")]
    # When: running it under wine
    result = run_program(args, wine=True)
    # Then: the launcher received Windows paths; text arguments are untouched
    expected = ["Z:\\opt\\phi\\MPExport.exe", "-Filename:raw.spe", "Z:\\data\\structured"]
    assert json.loads(result.stdout) == expected
    assert result.args == (str(fake_wine), *expected)


@pytest.mark.parametrize(("windows", "prefixed"), [(True, False), (False, True)], ids=["windows", "posix"])
def test_wine_auto__ga630_ep_8(fake_wine: Path, monkeypatch: pytest.MonkeyPatch, windows: bool, prefixed: bool) -> None:
    """GA630-EP-8: ``wine="auto"`` uses the launcher only outside Windows."""
    from rdetoolkit.nodes.external import _command

    # Given: the host platform
    monkeypatch.setattr("rdetoolkit.nodes.external._on_windows", lambda: windows)
    # When: building the command for a Path program
    command = _command([Path("/opt/conv.exe"), "-x"], wine="auto")
    # Then: only a non-Windows host gets the launcher and converted paths
    if prefixed:
        assert command == (str(fake_wine), "Z:\\opt\\conv.exe", "-x")
    else:
        assert command == (str(Path("/opt/conv.exe")), "-x")


@pytest.mark.parametrize(
    ("windows", "path", "expected"),
    [
        (False, Path("/home/rde/data/structured"), "Z:\\home\\rde\\data\\structured"),
        (False, Path("data/logs"), "data\\logs"),
        (True, Path("data/logs"), str(Path("data/logs"))),
    ],
    ids=["absolute", "relative", "windows-host"],
)
def test_to_wine_path__ga630_ep_9(monkeypatch: pytest.MonkeyPatch, windows: bool, path: Path, expected: str) -> None:
    """GA630-EP-9: paths embedded in option strings use the same conversion."""
    from rdetoolkit.nodes import to_wine_path

    # Given: the host platform
    monkeypatch.setattr("rdetoolkit.nodes.external._on_windows", lambda: windows)
    # When / Then: the path is written as the Windows program sees it
    assert to_wine_path(path) == expected


def test_flow_failure_reaches_report_and_job_failed__ga630_ep_10(tmp_path: Path) -> None:
    """GA630-EP-10: inside a flow the converter failure is the template's error, not 3001."""
    from rdetoolkit.core.flow import flow
    from rdetoolkit.nodes import run_program
    from rdetoolkit.testing import run_flow

    # Given: a flow running a failing converter with a template error code
    @flow
    def convert() -> None:
        run_program(_script("import sys; sys.exit(4)"), error_code=61, error_message="converter failed")

    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "raw.spe").write_bytes(b"\x00")
    # When: running it through the Runner
    report = run_flow(convert, fixture)
    # Then: the report and the call log carry the template's error
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == 61
    assert report.error["message"] == "converter failed"
    calls = report.iterations[0]["node_calls"]
    assert [call["status"] for call in calls] == ["failed"]
    assert calls[0]["node_id"].endswith("run_program")


@pytest.mark.parametrize(("args", "error"), [([], ValueError), ("convert.exe", TypeError)], ids=["empty", "string"])
def test_invalid_argument_lists__ga630_bv_1(args: object, error: type[Exception]) -> None:
    """GA630-BV-1: an empty list or a bare string is rejected before anything runs."""
    from rdetoolkit.nodes import run_program

    # Given / When / Then: no process is started for an unusable command
    with pytest.raises(error):
        run_program(args)  # type: ignore[arg-type]


def test_stderr_tail_is_bounded__ga630_bv_2() -> None:
    """GA630-BV-2: only the last stderr lines appear in the message."""
    from rdetoolkit.nodes import run_program

    # Given: a converter writing many stderr lines before failing
    code = "import sys\nfor i in range(100): print(f'line{i:03d}', file=sys.stderr)\nsys.exit(1)"
    # When: running it
    with pytest.raises(StructuredError) as excinfo:
        run_program(_script(code))
    # Then: the last line is reported and the first is not
    assert "line099" in excinfo.value.emsg
    assert "line000" not in excinfo.value.emsg
    assert excinfo.value.eobj.stderr.count("\n") == 100
