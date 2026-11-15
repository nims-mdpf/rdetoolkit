"""``rdetoolkit test``: a thin entry that runs pytest on the project's tests.

``rdetoolkit test ARGS...`` runs ``python -m pytest ARGS...`` with the same
interpreter, in the current directory, and exits with pytest's exit code.
pytest does all of the work -- collection, markers, parametrization,
fixtures, reporting -- so plain ``pytest`` stays fully equivalent (and is the
recommended command in CI). The rdetoolkit pytest plugin adds the retained
RDE run paths to the report of a failing test, under either command.

pytest runs in a child process rather than through ``pytest.main()``: the
CLI process has already imported rdetoolkit (and possibly user modules), so
an in-process session would see stale modules, skip pytest's assertion
rewriting for them, and could not be repeated safely. A child process gets a
fresh interpreter and pytest's exact exit code.

pytest is optional (``pip install "rdetoolkit[testing]"``); this module never
imports it.
"""

# Avoid postponed evaluation so Typer can read the command signature.

import importlib.util
import subprocess
import sys
from collections.abc import Sequence

import typer

from rdetoolkit.cli._help import EXIT_CLICK_USAGE, CommandHelp

TEST_HELP = CommandHelp(
    summary="Run the project's pytest tests: `rdetoolkit test ARGS` runs `python -m pytest ARGS`.",
    details=(
        "A thin wrapper for first-time users: every argument goes to pytest unchanged, the current directory and "
        "pytest's configuration are used as they are, and pytest's exit code is returned. Plain `pytest` is fully "
        'equivalent and remains the recommended command in CI. Needs pytest: `pip install "rdetoolkit[testing]"`.'
    ),
    inputs=(
        "`PATH`: test files or directories; default: pytest's own discovery from the current directory.",
        "`PYTEST_ARGS`: any pytest option, e.g. `-k EXPR`, `-m MARK`, `-x`, `-v`, `--rde-update-snapshots`. "
        "Put `--` first to pass an option rdetoolkit would read itself: `rdetoolkit test -- --help`.",
    ),
    outputs=(
        "pytest's own output. A failing test that used `rde_runner` or `rde_run` also gets an `rdetoolkit: retained runs` "
        "section with each retained data root, run report, diagnostics sidecar and `job.failed`.",
    ),
    examples=(
        "rdetoolkit test",
        "rdetoolkit test tests/ -k xrd -x",
        "rdetoolkit test -- --help",
    ),
    exit_codes=(
        (0, "all collected tests passed"),
        (1, "some tests failed"),
        (2, "pytest is not installed (an installation hint is printed), or the run was interrupted"),
        (3, "pytest internal error"),
        (4, "pytest rejected the command line"),
        (5, "no tests were collected"),
    ),
    see_also=("rdetoolkit doctor", "rdetoolkit run"),
)

MISSING_PYTEST_MESSAGE = (
    "Error: pytest is not installed, and `rdetoolkit test` runs pytest.\n"
    'Remediation: install the testing extra with `pip install "rdetoolkit[testing]"` (or `pip install pytest`), '
    "then rerun the command."
)

#: pytest's exit code for an interrupted session.
_EXIT_INTERRUPTED = 2


def pytest_available() -> bool:
    """Return whether pytest can be imported by this interpreter (without importing it)."""
    try:
        return importlib.util.find_spec("pytest") is not None
    except (ImportError, ValueError):
        return False


def pytest_command(args: Sequence[str]) -> list[str]:
    """Return the child-process command that runs pytest with ``args`` unchanged."""
    return [sys.executable, "-m", "pytest", *args]


def run_tests(ctx: typer.Context) -> None:
    """Run pytest with every argument forwarded and exit with its exit code."""
    if not pytest_available():
        typer.echo(MISSING_PYTEST_MESSAGE, err=True)
        raise typer.Exit(EXIT_CLICK_USAGE[0])
    try:
        completed = subprocess.run(pytest_command(list(ctx.args)), check=False)  # noqa: S603 - fixed interpreter and module
    except KeyboardInterrupt:
        # The child receives the same Ctrl-C and reports it; exit like pytest does.
        raise typer.Exit(_EXIT_INTERRUPTED) from None
    raise typer.Exit(completed.returncode)
