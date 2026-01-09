"""Typer-based CLI application for rdetoolkit."""
from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any

import typer
import click

from . import app as app_module


class _LazyModuleProxy:
    def __init__(self, module_name: str) -> None:
        self._module_name = module_name
        self._module: ModuleType | None = None

    def _load(self) -> ModuleType:
        if self._module is None:
            self._module = importlib.import_module(self._module_name)
        return self._module

    def __getattr__(self, name: str) -> Any:
        module = self._load()
        return getattr(module, name)

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"_module_name", "_module"}:
            object.__setattr__(self, name, value)
            return
        module = self._load()
        setattr(module, name, value)

    def __repr__(self) -> str:
        return f"<LazyModuleProxy {self._module_name}>"


app = app_module.app
_command = typer.main.get_command(app)
if not isinstance(_command, click.Group):
    msg = "Expected a click.Group for the CLI application."
    raise RuntimeError(msg)
_command_group = _command

artifact = _command_group.commands["artifact"]
csv2graph = _command_group.commands["csv2graph"]
gen_config = _command_group.commands["gen-config"]
init = _command_group.commands["init"]
make_excelinvoice = _command_group.commands["make-excelinvoice"]
run = _command_group.commands["run"]
version = _command_group.commands["version"]
workflows = _LazyModuleProxy("rdetoolkit.workflows")

__all__ = [
    "app",
    "artifact",
    "csv2graph",
    "gen_config",
    "init",
    "make_excelinvoice",
    "run",
    "version",
    "workflows",
]
