"""Equivalence Partitioning Table
| API | Input/State Partition | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `cli.run` | File target with function (>=2 positional args) | Valid file-based target | workflows.run invoked, output emitted | TC-EP-RUN-001 |
| `cli.run` | Missing `::` separator | Invalid target format | ClickException with format error | TC-EP-RUN-002 |
| `cli.run` | Attribute missing on module | Missing attribute | ClickException with missing attr message | TC-EP-RUN-003 |
| `cli.run` | Attribute is class | Reject classes | ClickException with class error | TC-EP-RUN-004 |
| `cli.run` | Attribute is callable instance | Reject non-function callable | ClickException with function-only error | TC-EP-RUN-005 |
| `cli.run` | File path does not exist | I/O failure | ClickException with file-not-found error | TC-EP-RUN-006 |

Boundary Value Table
| API | Boundary | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `cli.run` | 1 positional arg (min-1) | Below required positional args | ClickException with signature error | TC-BV-RUN-001 |
| `cli.run` | 2 positional args (min) | Minimum allowed positional args | workflows.run invoked, output emitted | TC-BV-RUN-002 |

Test execution (local env):
- pytest -q --maxfail=1 --cov=rdetoolkit --cov-branch --cov-report=term-missing --cov-report=html
- tox
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import pytest
from click.testing import CliRunner

import rdetoolkit.cli as cli_module
from rdetoolkit.cli import run as run_cli


@dataclass(frozen=True)
class RunTargetFiles:
    module_name: str
    module_path: Path
    file_path: Path


@pytest.fixture()
def run_target_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RunTargetFiles:
    module_path = tmp_path / "run_target_module.py"
    module_path.write_text(
        """
class Example:
    pass


class CallableThing:
    def __call__(self, a, b):
        return a + b


callable_instance = CallableThing()


def good(a, b):
    return a + b


def bad(a):
    return a
""".lstrip(),
        encoding="utf-8",
    )

    file_path = tmp_path / "run_target_file.py"
    file_path.write_text(
        """

def file_main(a, b, c=None):
    return a + b
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(tmp_path)

    return RunTargetFiles(
        module_name=module_path.stem,
        module_path=module_path,
        file_path=file_path,
    )


@pytest.fixture()
def stub_workflow_run(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    captured: dict[str, object] = {}

    def _stub_run(*, custom_dataset_function, config=None):
        captured["func"] = custom_dataset_function
        return "run-ok"

    monkeypatch.setattr(cli_module.workflows, "run", _stub_run)
    return captured


def test_cli_run_file_target_executes__tc_ep_run_001(
    run_target_files: RunTargetFiles,
    stub_workflow_run: dict[str, object],
) -> None:
    # Given: a file target with a valid function
    runner = CliRunner()
    target = f"{run_target_files.file_path}::file_main"

    # When: invoking the CLI run command
    result = runner.invoke(run_cli, [target])

    # Then: workflows.run receives the loaded function and prints output
    assert result.exit_code == 0
    assert result.output.strip() == "run-ok"
    assert getattr(stub_workflow_run["func"], "__name__") == "file_main"


def test_cli_run_missing_separator__tc_ep_run_002() -> None:
    # Given: a target without the required separator
    runner = CliRunner()

    # When: invoking the CLI run command
    result = runner.invoke(run_cli, ["process"])

    # Then: it fails with a format error
    assert isinstance(result.exception, SystemExit)
    assert result.exit_code != 0
    assert "TARGET must be 'module_or_file::attr'" in result.output


def test_cli_run_missing_attribute__tc_ep_run_003(
    run_target_files: RunTargetFiles,
) -> None:
    # Given: a module target missing the requested attribute
    runner = CliRunner()
    target = f"{run_target_files.module_name}::missing"

    # When: invoking the CLI run command
    result = runner.invoke(run_cli, [target])

    # Then: it fails with a missing attribute error
    assert isinstance(result.exception, SystemExit)
    assert result.exit_code != 0
    assert "Attribute not found: missing" in result.output


def test_cli_run_class_target__tc_ep_run_004(
    run_target_files: RunTargetFiles,
) -> None:
    # Given: a class target
    runner = CliRunner()
    target = f"{run_target_files.module_name}::Example"

    # When: invoking the CLI run command
    result = runner.invoke(run_cli, [target])

    # Then: it rejects the class target
    assert isinstance(result.exception, SystemExit)
    assert result.exit_code != 0
    assert "Classes are not allowed" in result.output


def test_cli_run_callable_instance__tc_ep_run_005(
    run_target_files: RunTargetFiles,
) -> None:
    # Given: a callable instance target
    runner = CliRunner()
    target = f"{run_target_files.module_name}::callable_instance"

    # When: invoking the CLI run command
    result = runner.invoke(run_cli, [target])

    # Then: it rejects non-function callables
    assert isinstance(result.exception, SystemExit)
    assert result.exit_code != 0
    assert "Only functions are allowed" in result.output


def test_cli_run_missing_file__tc_ep_run_006(tmp_path: Path) -> None:
    # Given: a missing file target
    runner = CliRunner()
    target = f"{tmp_path / 'missing.py'}::main"

    # When: invoking the CLI run command
    result = runner.invoke(run_cli, [target])

    # Then: it reports the missing file
    assert isinstance(result.exception, SystemExit)
    assert result.exit_code != 0
    assert "File not found" in result.output


def test_cli_run_signature_too_few_args__tc_bv_run_001(
    run_target_files: RunTargetFiles,
) -> None:
    # Given: a function that accepts only one positional argument
    runner = CliRunner()
    target = f"{run_target_files.module_name}::bad"

    # When: invoking the CLI run command
    result = runner.invoke(run_cli, [target])

    # Then: it rejects the signature below the minimum boundary
    assert isinstance(result.exception, SystemExit)
    assert result.exit_code != 0
    assert "cannot be called with two positional arguments" in result.output


def test_cli_run_signature_min_args__tc_bv_run_002(
    run_target_files: RunTargetFiles,
    stub_workflow_run: dict[str, object],
) -> None:
    # Given: a function that meets the minimum positional argument boundary
    runner = CliRunner()
    target = f"{run_target_files.module_name}::good"

    # When: invoking the CLI run command
    result = runner.invoke(run_cli, [target])

    # Then: workflows.run receives the loaded function and prints output
    assert result.exit_code == 0
    assert result.output.strip() == "run-ok"
    assert getattr(stub_workflow_run["func"], "__name__") == "good"
