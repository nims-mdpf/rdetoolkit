"""Typer-based CLI application for rdetoolkit."""
from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any, Optional

import typer

from .app import (
    app,
    artifact,
    csv2graph,
    gen_config,
    init,
    make_excelinvoice,
    version,
)


class _LazyModuleProxy:
    def __init__(self, module_name: str) -> None:
        self._module_name = module_name
        self._module: Optional[ModuleType] = None

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


workflows = _LazyModuleProxy("rdetoolkit.workflows")
run = typer.main.get_command(app).commands["run"]

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
