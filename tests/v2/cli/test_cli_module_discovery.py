"""Project-module discovery tests for node and flow inspection commands.

EP table:
    TC-E-REVIEW-F2-001 | valid repeated modules | definitions imported before list | both ids shown
    TC-E-REVIEW-F2-002 | valid module | describe/lint enumeration | imported definition available
    TC-E-REVIEW-F2-003 | missing module | import failure | exit 3 with exception text

BV table:
    TC-E-REVIEW-F2-004 | no --module options | additive default | existing registry behavior remains
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app


def _write_module(directory: Path, name: str, suffix: str) -> None:
    (directory / f"{name}.py").write_text(
        "from rdetoolkit import flow, node\n"
        "from rdetoolkit.types import InputPaths\n"
        f"@node(id='review.node.{suffix}')\n"
        f"def node_{suffix}(paths: InputPaths) -> None:\n    return None\n"
        f"@flow(id='review.flow.{suffix}')\n"
        f"def flow_{suffix}(paths: InputPaths) -> None:\n    return None\n",
        encoding="utf-8",
    )


@pytest.fixture
def project_modules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, str]:
    _write_module(tmp_path, "review_project_one", "one")
    _write_module(tmp_path, "review_project_two", "two")
    monkeypatch.syspath_prepend(str(tmp_path))
    return "review_project_one", "review_project_two"


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (["nodes", "list"], "review.node.one"),
        (["nodes", "describe", "review.node.one"], "review.node.one"),
        (["flows", "list"], "review.flow.one"),
        (["flows", "describe", "review.flow.one"], "review.flow.one"),
    ],
)
def test_command_imports_project_module_before_enumeration__tc_e_review_f2_002(
    project_modules: tuple[str, str],
    command: list[str],
    expected: str,
) -> None:
    """TC-E-REVIEW-F2-002: each inspection command loads requested modules."""
    # Given: an importable project module containing stable node and flow definitions
    module, _ = project_modules
    # When: the command receives the project module explicitly
    result = CliRunner().invoke(app, [*command, "--module", module])
    # Then: import occurs before registry enumeration
    assert result.exit_code == 0, result.output
    assert expected in result.output


def test_lint_imports_project_module_before_enumeration__tc_e_review_f2_002(
    project_modules: tuple[str, str],
    tmp_path: Path,
) -> None:
    """TC-E-REVIEW-F2-002: lint loads a project module in a clean registry."""
    # Given: an importable project module and a fresh interpreter registry
    module, _ = project_modules
    script = (
        "import sys\n"
        "from typer.testing import CliRunner\n"
        "from rdetoolkit.cli.app import app\n"
        f"result = CliRunner().invoke(app, ['nodes', 'lint', '--module', '{module}'])\n"
        "sys.stdout.write(result.output)\n"
        "raise SystemExit(result.exit_code)\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(tmp_path), env.get("PYTHONPATH", "")))
    # When: lint imports the module before enumerating in that fresh process
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=30,
    )
    # Then: the imported stable definitions produce a clean result
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 violations" in result.stdout


@pytest.mark.parametrize(
    "command",
    [
        ["nodes", "list"],
        ["nodes", "describe", "missing"],
        ["nodes", "lint"],
        ["flows", "list"],
        ["flows", "describe", "missing"],
    ],
)
def test_module_import_failure_is_usage_error__tc_e_review_f2_003(command: list[str]) -> None:
    """TC-E-REVIEW-F2-003: import errors preserve their text and exit with 3."""
    # Given: a dotted module name that cannot be imported
    missing = "review_project_module_that_does_not_exist"
    # When: module loading is requested by an inspection command
    result = CliRunner().invoke(app, [*command, "--module", missing])
    # Then: the import failure is reported as a usage error before enumeration
    assert result.exit_code == 3
    assert missing in result.output


def test_list_accepts_repeated_modules__tc_e_review_f2_001(project_modules: tuple[str, str]) -> None:
    """TC-E-REVIEW-F2-001: --module is repeatable and imports every value."""
    # Given: two project modules that register distinct definitions
    first, second = project_modules
    # When: both modules are supplied to one command
    result = CliRunner().invoke(
        app,
        ["nodes", "list", "--module", first, "--module", second],
    )
    # Then: definitions from both modules are enumerated
    assert result.exit_code == 0, result.output
    assert "review.node.one" in result.output
    assert "review.node.two" in result.output


def test_module_option_defaults_to_empty__tc_e_review_f2_004() -> None:
    """TC-E-REVIEW-F2-004: omitting --module keeps in-process enumeration valid."""
    # Given: no requested project module
    # When: listing flows with the additive option omitted
    result = CliRunner().invoke(app, ["flows", "list"])
    # Then: the existing in-process command remains successful
    assert result.exit_code == 0
