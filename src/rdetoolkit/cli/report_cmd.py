"""Display summaries from versioned run-report files."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from rdetoolkit.report.run_report import RUN_REPORT_SCHEMA_VERSION, RunReport

if sys.version_info >= (3, 11):
    from typing import Never
else:
    from typing_extensions import Never


app = typer.Typer(help="Inspect run reports.")


def _usage_error(message: str) -> Never:
    typer.echo(message, err=True)
    raise typer.Exit(code=3)


def _load_report(path: Path) -> RunReport:
    try:
        return RunReport.from_json(path.read_text(encoding="utf-8"))
    except (OSError, KeyError, TypeError, ValueError) as exc:
        _usage_error(f"Unable to read run report {path}: {exc}")


def _failed_calls(iterations: list[dict[str, Any]]) -> list[str]:
    return [
        str(call.get("call_id", "<unknown>"))
        for iteration in iterations
        for call in iteration.get("node_calls", [])
        if call.get("status") == "failed"
    ]


@app.command()
def show(run_report: Annotated[Path, typer.Argument(metavar="<run_report.json>")]) -> None:
    """Display status, iterations, and failed calls from a run report."""
    report = _load_report(run_report)
    if report.schema_version != RUN_REPORT_SCHEMA_VERSION:
        typer.echo(f"Warning: unrecognized schema_version {report.schema_version}", err=True)
    typer.echo(f"run_id: {report.run_id}")
    typer.echo(f"status: {report.status}")
    typer.echo(f"iterations: {len(report.iterations)}")
    for call_id in _failed_calls(report.iterations):
        typer.echo(f"failed call_id: {call_id}")
    if report.error:
        typer.echo(f"error: {report.error.get('message', report.error)}")
