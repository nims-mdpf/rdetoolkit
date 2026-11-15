# Canonical type source for the ``rdetoolkit.cli`` package (supersedes the
# former ``rdetoolkit/cli.pyi``, which no type checker ever selected because
# the package directory wins module resolution). The command exports are the
# Click command objects Typer builds from ``rdetoolkit.cli.app`` -- not plain
# functions -- so calling them runs Click's argument parsing. They are typed as
# ``typer.core.TyperCommand`` (the runtime class) rather than
# ``click.Command``: the Click base class depends on the typer release
# (``click.core.Command`` or the vendored ``typer._click``), while
# ``typer.core.TyperCommand`` exists in every supported typer version.
from typing import Any

import typer
import typer.core

class _LazyModuleProxy:
    """Attribute proxy that imports its target module on first access."""

    def __init__(self, module_name: str) -> None: ...
    def __getattr__(self, name: str) -> Any: ...
    def __setattr__(self, name: str, value: object) -> None: ...

app: typer.Typer
artifact: typer.core.TyperCommand
csv2graph: typer.core.TyperCommand
gen_config: typer.core.TyperCommand
init: typer.core.TyperCommand
make_excelinvoice: typer.core.TyperCommand
run: typer.core.TyperCommand
version: typer.core.TyperCommand
workflows: _LazyModuleProxy

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
