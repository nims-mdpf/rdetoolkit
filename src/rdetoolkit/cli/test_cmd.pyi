from collections.abc import Sequence

import typer

from rdetoolkit.cli._help import CommandHelp

TEST_HELP: CommandHelp
MISSING_PYTEST_MESSAGE: str

def pytest_available() -> bool: ...
def pytest_command(args: Sequence[str]) -> list[str]: ...
def run_tests(ctx: typer.Context) -> None: ...
