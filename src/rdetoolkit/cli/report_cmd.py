"""``rdetoolkit report``: read versioned run-report files.

``show`` summarizes a run; ``trace`` renders the recorded Call Sequence (the
node calls in the order they ran -- a call log, not a dataflow graph);
``diagnose`` reports its failures with catalog guidance and checks which
supporting logs belong to the same run; ``explain`` tells why it failed,
joining the report with its failure-diagnostics file (#687).
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
    summary="Read run reports written by `rdetoolkit run`: summarize, trace, diagnose, or explain them.",
    examples=(
        "rdetoolkit report show data/logs/run_report_<id>.json",
        "rdetoolkit report trace data/logs/run_report_<id>.json --format mermaid",
        "rdetoolkit report diagnose data/logs/run_report_<id>.json --json",
        "rdetoolkit report explain data/logs/run_report_<id>.json",
    ),
    exit_codes=(EXIT_OK, (1, "`diagnose --fail-on-error`: the run recorded failures"), *_EXIT_CODES[1:]),
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
        "rdetoolkit report trace run_report_<id>.json --format html > trace.html",
    ),
    exit_codes=(EXIT_OK, EXIT_CLICK_USAGE, (3, "the report file is missing or invalid, or `--format` is not json, mermaid, or html")),
    see_also=("rdetoolkit report show", "rdetoolkit run"),
)

DIAGNOSE_HELP = CommandHelp(
    summary="Diagnose a run report: failed iterations, node and call ids, catalog codes, and remediation.",
    details=(
        "Failures come from the report only; they are observed calls, not inferred dependencies. "
        "The `iterations/` details and `events_<run_id>.jsonl` next to the report are used as evidence only "
        "when their run id matches, and are otherwise flagged (missing, unverified, mismatched, ...). "
        "Runtime error messages, tracebacks and argument previews are never printed."
    ),
    inputs=(
        _REPORT_INPUT + " Keep it next to its `iterations/` and `events_<run_id>.jsonl`.",
        "`--json`: print the versioned diagnostics envelope. `--fail-on-error`: exit 1 when the run recorded a failure.",
    ),
    outputs=("Prints one line per failure and evidence warning, or one JSON object with `--json`. Writes no files.",),
    examples=(
        "rdetoolkit report diagnose data/logs/run_report_<id>.json",
        "rdetoolkit report diagnose run_report_<id>.json --json --fail-on-error",
    ),
    exit_codes=(
        (0, "the report was diagnosed (also when the run itself failed)"),
        (1, "with `--fail-on-error`: the run recorded at least one failure"),
        EXIT_CLICK_USAGE,
        (3, "the report file is missing, unreadable, or not a supported run report"),
    ),
    see_also=("rdetoolkit report show", "rdetoolkit report trace", "rdetoolkit doctor"),
)

EXPLAIN_HELP = CommandHelp(
    summary="Explain why a run failed: phase, tile, node, exception, source location, and remediation.",
    details=(
        "The run report decides the outcome; `diagnostics_<run_id>.json` next to it adds the phase, the exception "
        "chain and the source frame when its run id matches. Without it (older runs, a moved report) the explanation "
        "uses the report alone and says the diagnostics are unavailable. A successful run is not given a cause. "
        "Text output shows the recorded exception messages; `--format json` follows the diagnostics envelope rules "
        "and copies no runtime text."
    ),
    inputs=(
        _REPORT_INPUT + " Keep it next to its `diagnostics_<run_id>.json`, `iterations/` and `events_<run_id>.jsonl`.",
        ("`--format`: `text` (default) or `json`. `--iteration N`: explain only tile N. "
        "`--full-traceback`: add every recorded frame (file, line, function) of each exception."),
    ),
    outputs=("Prints the explanation, or one JSON object with `--format json`. Writes no files.",),
    examples=(
        "rdetoolkit report explain data/logs/run_report_<id>.json",
        "rdetoolkit report explain run_report_<id>.json --format json",
        "rdetoolkit report explain run_report_<id>.json --iteration 2 \\",
        "    --full-traceback",
    ),
    exit_codes=(
        (0, "the report was explained (also when the run itself failed)"),
        EXIT_CLICK_USAGE,
        (3, "the report is missing or not a supported run report, `--format` is unknown, or `--iteration` is not in the report"),
    ),
    see_also=("rdetoolkit report diagnose", "rdetoolkit report show", "rdetoolkit report trace"),
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


@app.command("diagnose", help=DIAGNOSE_HELP.render(), short_help=DIAGNOSE_HELP.summary)
def diagnose(
    run_report: Annotated[Path, typer.Argument(metavar="RUN_REPORT", help="Path to run_report_<run_id>.json.")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit the versioned diagnostics envelope.")] = False,
    fail_on_error: Annotated[bool, typer.Option("--fail-on-error", help="Exit 1 when the run recorded a failure.")] = False,
) -> None:
    """Diagnose the failures recorded in ``run_report`` with run-bound evidence."""
    import json

    from rdetoolkit.report.diagnosis import diagnose_report
    from rdetoolkit.report.diagnostics import diagnostic, envelope

    try:
        result = diagnose_report(run_report)
    except (OSError, UnicodeError, KeyError, TypeError, ValueError, RecursionError):
        # The exception text is not printed: it can quote the file's contents.
        finding = diagnostic(
            code=None, severity="error", name="ReportInputInvalid", subject="run_report",
            message="Unable to read a supported run report.",
            remediation="Pass the run_report_<run_id>.json file that 'rdetoolkit run' wrote under data/logs/, unmodified.",
        )
        if as_json:
            typer.echo(json.dumps(envelope([finding], command="report diagnose"), ensure_ascii=False, sort_keys=True, indent=2))
        else:
            typer.echo(f"{finding['message']}\nRemediation: {finding['remediation']}", err=True)
        raise typer.Exit(code=3) from None
    if as_json:
        typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        typer.echo(f"run_id: {result['run_id']}")
        typer.echo(f"status: {result['run_status']}")
        for failure in result["failures"]:
            where = "run" if failure["iteration_index"] is None else f"iteration {failure['iteration_index']}"
            call = failure["call_id"] or ("<redacted call id>" if "call_id" in failure["redacted"] else "no node call")
            typer.echo(f"{where}: {call}: {failure['name']} ({failure['code']})")
            typer.echo(f"  Remediation: {failure['remediation']}")
        for finding in result["diagnostics"]:
            if finding["severity"] == "warning":
                typer.echo(f"warning: {finding['subject']}: {finding['message']}")
    if fail_on_error and result["failures"]:
        raise typer.Exit(code=1)


_EXPLAIN_FORMATS = ("text", "json")


def _explain_input_error(*, as_json: bool, name: str, message: str, remediation: str) -> Never:
    """Report an input the command cannot explain, as JSON on stdout or text on stderr, and exit 3."""
    import json

    from rdetoolkit.report.diagnostics import diagnostic, envelope
    from rdetoolkit.report.explanation import EXPLAIN_COMMAND

    finding = diagnostic(code=None, severity="error", name=name, subject="run_report", message=message, remediation=remediation)
    if as_json:
        typer.echo(json.dumps(envelope([finding], command=EXPLAIN_COMMAND), ensure_ascii=False, sort_keys=True, indent=2))
    else:
        typer.echo(f"{message}\nRemediation: {remediation}", err=True)
    raise typer.Exit(code=3)


@app.command("explain", help=EXPLAIN_HELP.render(), short_help=EXPLAIN_HELP.summary)
def explain(
    run_report: Annotated[Path, typer.Argument(metavar="RUN_REPORT", help="Path to run_report_<run_id>.json.")],
    format_: Annotated[str, typer.Option("--format", help="Output format: text or json.")] = "text",
    iteration: Annotated[int | None, typer.Option("--iteration", help="Explain only this tile index.", min=0)] = None,
    full_traceback: Annotated[bool, typer.Option("--full-traceback", help="Show every recorded frame of each exception.")] = False,
) -> None:
    """Explain the failures recorded for ``run_report`` and where they happened."""
    import json

    from rdetoolkit.report.explanation import IterationNotInReportError, explain_report, render_text

    as_json = format_ == "json"
    if format_ not in _EXPLAIN_FORMATS:
        _usage_error(f"Unknown --format {format_!r}.\nRemediation: pass --format text or --format json.")
    try:
        result = explain_report(run_report, iteration=iteration, full_traceback=full_traceback)
    except IterationNotInReportError:
        _explain_input_error(
            as_json=as_json, name="IterationNotInReport", message=f"Iteration {iteration} is not recorded in the run report.",
            remediation="Pass an iteration index that 'rdetoolkit report show' lists, or omit --iteration.",
        )
    except (OSError, UnicodeError, KeyError, TypeError, ValueError, RecursionError):
        # The exception text is not printed: it can quote the file's contents.
        _explain_input_error(
            as_json=as_json, name="ReportInputInvalid", message="Unable to read a supported run report.",
            remediation="Pass the run_report_<run_id>.json file that 'rdetoolkit run' wrote under data/logs/, unmodified.",
        )
    if as_json:
        typer.echo(json.dumps(result.document, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        typer.echo(render_text(result, run_report, full_traceback=full_traceback))
