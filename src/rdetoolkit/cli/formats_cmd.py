"""Commands for listing plugin-provided file format handlers."""

from __future__ import annotations

import json
from typing import Annotated, Any

import typer

from rdetoolkit.plugin import discover_plugins

app = typer.Typer(help="Inspect plugin-provided file format handlers.")


def _values() -> list[dict[str, Any]]:
    return [
        {
            "name": handler.name,
            "extensions": handler.extensions,
            "target": handler.target,
            "plugin": plugin.name,
        }
        for plugin in discover_plugins()
        for handler in plugin.format_handlers
    ]


@app.command("list")
def list_formats(
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """List file format handlers declared by discovered plugins."""
    values = _values()
    if as_json:
        typer.echo(json.dumps(values, sort_keys=True))
        return
    for value in values:
        extensions = ", ".join(value["extensions"])
        typer.echo(f"{value['name']} ({extensions}) -> {value['target']} [{value['plugin']}]")
