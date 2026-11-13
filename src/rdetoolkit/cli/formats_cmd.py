"""Commands for listing plugin-provided file format handlers."""

from __future__ import annotations

import json
from typing import Annotated, Any

import typer

from rdetoolkit.cli._help import EXIT_CLICK_USAGE, EXIT_OK, CommandHelp
from rdetoolkit.plugin import discover_plugins

FORMATS_HELP = CommandHelp(
    summary="List file format handlers that installed plugins declare.",
    examples=("rdetoolkit formats list", "rdetoolkit formats list --json"),
    exit_codes=(EXIT_OK, EXIT_CLICK_USAGE),
    see_also=("rdetoolkit nodes list --plugin",),
)

LIST_HELP = CommandHelp(
    summary="List format handlers from installed `rdetoolkit.plugins` entry points.",
    outputs=(
        "Prints `name (extensions) -> target [plugin]` per handler, or a JSON array with `--json`. "
        "Prints nothing when no plugin declares a handler. Writes no files.",
    ),
    examples=("rdetoolkit formats list", "rdetoolkit formats list --json"),
    exit_codes=(EXIT_OK, EXIT_CLICK_USAGE),
    see_also=("rdetoolkit nodes list --plugin",),
)

app = typer.Typer(help=FORMATS_HELP.render(), short_help=FORMATS_HELP.summary, no_args_is_help=True)


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


@app.command("list", help=LIST_HELP.render(), short_help=LIST_HELP.summary)
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
