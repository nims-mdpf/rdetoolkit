"""Shared helpers for v2 CLI inspection commands."""

from __future__ import annotations

import importlib
from collections.abc import Sequence

import typer


def load_modules(module_names: Sequence[str]) -> None:
    """Import explicitly requested project modules in command-line order.

    Args:
        module_names: Dotted Python module names supplied by the user.
    """
    for module_name in module_names:
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"Unable to import module {module_name}: {exc}", err=True)
            raise typer.Exit(code=3) from exc
