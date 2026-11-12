"""``rdetoolkit report``: read versioned run-report files.

``show`` summarizes a run; ``trace`` renders the recorded Call Sequence (the
node calls in the order they ran -- a call log, not a dataflow graph).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from rdetoolkit.cli._help import EXIT_CLICK_USAGE, EXIT_OK, CommandHelp
from rdetoolkit.report.run_report import RUN_REPORT_SCHEMA_VERSION, RunReport

if sys.version_info >= (3, 11):
    from typing import Never
else:
    from typing_extensions import Never

_REPORT_INPUT = (
    "`RUN_REPORT`: a `run_report_<run_id>.json` file. `rdetoolkit run` writes it to "
    "`data/logs/` and prints the same JSON to stdout."
)
_EXIT_CODES = (EXIT_OK, EXIT_CLICK_USAGE, (3, "the report file is missing or is not a run report"))

REPORT_HELP = CommandHelp(
    summary="Read run reports written by `rdetoolkit run`: summarize them or trace their node calls.",
    examples=(
        "rdetoolkit report show data/logs/run_report_<id>.json",
        "rdetoolkit report trace data/logs/run_report_<id>.json --format mermaid",
    ),
    exit_codes=_EXIT_CODES,
    see_also=("rdetoolkit run", "rdetoolkit repro export"),
)

SHOW_HELP = CommandHelp(
    summary="Print a run's status, iteration count, failed call ids, and error message.",
    inputs=(_REPORT_INPUT,),
    outputs=(
        "Prints `run_id`, `status`, `iterations`, one `failed call_id` line per failed node call, and `error` when set.",
        "Warns on stderr when the report's `schema_version` is not the one this rdetoolkit writes. Writes no files.",
    ),
    examples=(
        "rdetoolkit report show data/logs/run_report_<id>.json",
        "rdetoolkit report show container/data/logs/run_report_<id>.json",
    ),
    exit_codes=_EXIT_CODES,
    see_also=("rdetoolkit report trace", "rdetoolkit run"),
)

TRACE_HELP = CommandHelp(
    summary="Render the Call Sequence recorded in a run report: every node call in the order it ran.",
    details="The trace is a call log (call ids, parent flow, status, argument previews). It does not draw data dependencies.",
    inputs=(_REPORT_INPUT, "`--format`: `json` (default), `mermaid` (a sequence diagram), or `html` (a standalone page)."),
    outputs=("Prints the rendering to stdout; redirect it to save a file. Writes no files itself.",),
    examples=(
        "rdetoolkit report trace data/logs/run_report_<id>.json",
        "rdetoolkit report trace data/logs/run_report_<id>.json --format html > t.html",
            ),
    exit_codes=(EXIT_OK, EXIT_CLICK_USAGE, (3, "the report file is missing or invalid, or `--format` is not json, mermaid, or html")),
    see_also=("rdetoolkit report show", "rdetoolkit run"),
)

app = typer.Typer(help=REPORT_HELP.render(), short_help=REPORT_HELP.summary, no_args_is_help=True)


def _usage_error(message: str) -> Never:
    typer.echo(message, err=True)
    raise typer.Exit(code=3)


def _load_report(path: Path) -> RunReport:
    try:
        return RunReport.from_json(path.read_text(encoding="utf-8"))
    except (OSError, KeyError, TypeError, ValueError) as exc:
        _usage_error(
            f"Unable to read run report {path}: {exc}\n"
            "Remediation: pass the run_report_<run_id>.json file that 'rdetoolkit run' wrote under data/logs/.",
        )


def _failed_calls(iterations: list[dict[str, Any]]) -> list[str]:
    return [
        str(call.get("call_id", "<unknown>"))
        for iteration in iterations
        for call in iteration.get("node_calls", [])
        if call.get("status") == "failed"
    ]


@app.command("show", help=SHOW_HELP.render(), short_help=SHOW_HELP.summary)
def show(run_report: Annotated[Path, typer.Argument(metavar="RUN_REPORT", help="Path to run_report_<run_id>.json.")]) -> None:
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


@app.command("trace", help=TRACE_HELP.render(), short_help=TRACE_HELP.summary)
def trace(
    run_report: Annotated[Path, typer.Argument(metavar="RUN_REPORT", help="Path to run_report_<run_id>.json.")],
    format_: Annotated[str, typer.Option("--format", help="Output format: json, mermaid, or html.")] = "json",
) -> None:
    """Render the calls recorded in ``run_report`` in chronological order."""
    from rdetoolkit.report.graph_render import render_call_sequence

    report = _load_report(run_report)
    try:
        rendered = render_call_sequence(report, format=format_)
    except ValueError as exc:
        _usage_error(f"{exc}\nRemediation: pass --format json, --format mermaid, or --format html.")
    typer.echo(rendered)
