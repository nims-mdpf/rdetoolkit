"""Commands for inspecting registered v2 flows."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Annotated

import typer

from rdetoolkit.cli._help import EXIT_CLICK_USAGE, EXIT_OK, CommandHelp
from rdetoolkit.cli._v2_common import load_modules
from rdetoolkit.core import registry

_MODULE_INPUT = "`--module`: import a project module first so its flows are registered (repeatable)."

FLOWS_HELP = CommandHelp(
    summary="List and show registered flows (functions decorated with flow()).",
    examples=(
        "rdetoolkit flows list --module modules.processing",
        "rdetoolkit flows show pkg.flows.pipeline --module pkg.flows",
    ),
    exit_codes=(EXIT_OK, EXIT_CLICK_USAGE, (3, "unknown flow id or a module that fails to import")),
    see_also=("rdetoolkit run", "rdetoolkit nodes list"),
)

LIST_HELP = CommandHelp(
    summary="List registered flow ids, one per line.",
    inputs=(_MODULE_INPUT,),
    outputs=("Prints flow ids, or a JSON array of flow specs with `--json`. Writes no files.",),
    examples=("rdetoolkit flows list --module modules.processing", "rdetoolkit flows list --module modules.processing --json"),
    exit_codes=(EXIT_OK, EXIT_CLICK_USAGE, (3, "a module given with `--module` fails to import")),
    see_also=("rdetoolkit flows show", "rdetoolkit run"),
)

SHOW_HELP = CommandHelp(
    summary="Show one registered flow: id, version, and signature.",
    inputs=("`NAME`: a flow id as printed by `rdetoolkit flows list`.", _MODULE_INPUT),
    outputs=("Prints `field: value` lines, or one JSON object with `--json`. Writes no files.",),
    examples=(
        "rdetoolkit flows show pkg.flows.pipeline --module pkg.flows",
        "rdetoolkit flows show pkg.flows.pipeline --module pkg.flows --json",
    ),
    exit_codes=(EXIT_OK, EXIT_CLICK_USAGE, (3, "unknown flow id or a module that fails to import")),
    see_also=("rdetoolkit run",),
)

app = typer.Typer(help=FLOWS_HELP.render(), short_help=FLOWS_HELP.summary, no_args_is_help=True)


def _emit_usage_error(message: str) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(code=3)


@app.command("list", help=LIST_HELP.render(), short_help=LIST_HELP.summary)
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


@app.command("show", help=SHOW_HELP.render(), short_help=SHOW_HELP.summary)
def show(
    flow_id: Annotated[str, typer.Argument(metavar="NAME")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
    modules: Annotated[
        list[str] | None,
        typer.Option("--module", help="Import a project module before showing; repeatable."),
    ] = None,
) -> None:
    """Show a registered flow."""
    load_modules(modules or [])
    try:
        value = asdict(registry.get_flow(flow_id))
    except KeyError:
        _emit_usage_error(
            f"Unknown flow id: {flow_id}\n"
            "Remediation: run 'rdetoolkit flows list' for registered ids, and pass --module for the module that defines the flow.",
        )
    if as_json:
        typer.echo(json.dumps(value, sort_keys=True))
        return
    for name, field_value in value.items():
        typer.echo(f"{name}: {field_value}")
