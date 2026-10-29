"""Render a recorded Call Sequence from a run-report file."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from rdetoolkit.report.graph_render import render_call_sequence
from rdetoolkit.report.run_report import RunReport

if sys.version_info >= (3, 11):
    from typing import Never
else:
    from typing_extensions import Never


app = typer.Typer(
    help="Render a recorded Call Sequence.",
    invoke_without_command=True,
    context_settings={"allow_interspersed_args": True},
)


def _usage_error(message: str) -> Never:
    typer.echo(message, err=True)
    raise typer.Exit(code=3)


def _load_report(path: Path) -> RunReport:
    try:
        return RunReport.from_json(path.read_text(encoding="utf-8"))
    except (OSError, KeyError, TypeError, ValueError) as exc:
        _usage_error(f"Unable to read run report {path}: {exc}")


@app.callback()
def graph(
    run_report: Annotated[Path, typer.Argument(metavar="<run_report.json>")],
    format_: Annotated[str, typer.Option("--format", help="Output format: json, mermaid, or html.")] = "json",
) -> None:
    """Render the calls recorded in ``run_report`` in chronological order."""
    report = _load_report(run_report)
    try:
        rendered = render_call_sequence(report, format=format_)
    except ValueError as exc:
        _usage_error(str(exc))
    typer.echo(rendered)
