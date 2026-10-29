"""Typer-based CLI application for rdetoolkit."""
from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any, Optional

import typer

from . import app as app_module


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

    @property
    def __dict__(self) -> dict[str, Any]:  # type: ignore[override]
        """Present the target module's namespace as this proxy's namespace.

        pytest 9.2 decides how to undo ``monkeypatch.setattr(target, name, ...)``
        by looking ``name`` up in ``target.__dict__``: a name that is not there
        is treated as inherited and undone with ``delattr``. The proxy's names
        live behind ``__getattr__``, so the undo failed and the test stub stayed
        on ``rdetoolkit.workflows`` for the rest of the session. Exposing the
        module's namespace makes the proxy patchable exactly like the module.
        """
        return self._load().__dict__

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"_module_name", "_module"}:
            object.__setattr__(self, name, value)
            return
        module = self._load()
        setattr(module, name, value)

    def __repr__(self) -> str:
        return f"<LazyModuleProxy {self._module_name}>"


app = app_module.app
# typer.main.get_command always returns a click.Group for Typer apps with sub-commands.
# Cast to Any so that mypy allows .commands attribute access without importing click.
_command_group: Any = typer.main.get_command(app)

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
