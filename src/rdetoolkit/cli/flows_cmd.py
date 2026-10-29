"""Commands for inspecting registered v2 flows."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Annotated

import typer

from rdetoolkit.cli._v2_common import load_modules
from rdetoolkit.core import registry

app = typer.Typer(help="Inspect registered v2 flows.")


def _emit_usage_error(message: str) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(code=3)


@app.command("list")
def list_flows(
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
    modules: Annotated[
        list[str] | None,
        typer.Option("--module", help="Import a project module before listing; repeatable."),
    ] = None,
) -> None:
    """List flows in the current process registry."""
    load_modules(modules or [])
    values = [asdict(spec) for spec in registry.list_flows()]
    if as_json:
        typer.echo(json.dumps(values, sort_keys=True))
        return
    for value in values:
        typer.echo(value["id"])


@app.command()
def describe(
    flow_id: Annotated[str, typer.Argument(metavar="<name>")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
    modules: Annotated[
        list[str] | None,
        typer.Option("--module", help="Import a project module before describing; repeatable."),
    ] = None,
) -> None:
    """Describe a registered flow."""
    load_modules(modules or [])
    try:
        value = asdict(registry.get_flow(flow_id))
    except KeyError:
        _emit_usage_error(f"Unknown flow id: {flow_id}")
    if as_json:
        typer.echo(json.dumps(value, sort_keys=True))
        return
    for name, field_value in value.items():
        typer.echo(f"{name}: {field_value}")
