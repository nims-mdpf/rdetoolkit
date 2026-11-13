"""Shared helpers for v2 CLI inspection commands."""

from __future__ import annotations

import importlib
import os
import sys
from collections.abc import Sequence
from types import ModuleType

import typer

#: Printed after every failed ``--module`` import.
IMPORT_REMEDIATION = (
    "Remediation: run the command from the project root (the current directory is put on sys.path), "
    "check the dotted module name, and fix any error the module raises on import."
)


def ensure_cwd_on_sys_path() -> None:
    """Give project-module imports ``python -m`` semantics.

    The installed ``rdetoolkit`` console script starts with the venv ``bin/``
    directory as ``sys.path[0]``, so a module sitting in the project directory
    was importable under ``python -m rdetoolkit`` but not under the console
    script (review F02). Putting the working directory at the front of
    ``sys.path`` -- only when no entry already names it -- makes both launchers
    agree. ``PYTHONPATH`` is deliberately not consulted: the interpreter
    already applied it at startup.
    """
    cwd = os.getcwd()
    # ``""`` is how ``python -c`` spells the working directory; ``abspath``
    # maps it (and any equivalent spelling) onto ``cwd`` so it is not doubled.
    if any(isinstance(entry, str) and os.path.abspath(entry) == cwd for entry in sys.path):
        return
    sys.path.insert(0, cwd)


def import_project_module(module_name: str) -> ModuleType:
    """Import a user-named module with the working directory importable.

    Args:
        module_name: Dotted Python module name supplied on the command line.

    Returns:
        The imported module.
    """
    ensure_cwd_on_sys_path()
    return importlib.import_module(module_name)


def load_modules(module_names: Sequence[str]) -> None:
    """Import explicitly requested project modules in command-line order.

    Args:
        module_names: Dotted Python module names supplied by the user.
    """
    for module_name in module_names:
        try:
            import_project_module(module_name)
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"Unable to import module {module_name}: {exc}\n{IMPORT_REMEDIATION}", err=True)
            raise typer.Exit(code=3) from exc
