"""Render call sequences from run-report iteration summaries."""

from __future__ import annotations

import html
import json
from typing import Any

from rdetoolkit.report.run_report import RunReport

_CALL_FIELDS = ("call_id", "node_id", "seq", "status", "duration_ms")


def render_call_sequence(report: RunReport, format: str = "json") -> str:  # noqa: A002
    """Render the recorded call order in the requested representation.

    Args:
        report: Run report containing per-iteration call summaries.
        format: One of ``json``, ``mermaid``, or ``html``.

    Returns:
        The rendered call sequence.

    Raises:
        ValueError: If ``format`` is unsupported.
    """
    iterations = [_iteration_summary(item) for item in report.iterations]
    if format == "json":
        return json.dumps(
            {"title": "Call Sequence", "run_id": report.run_id, "iterations": iterations},
            ensure_ascii=False,
            indent=2,
        )
    if format == "mermaid":
        return _render_mermaid(iterations)
    if format == "html":
        return _render_html(iterations)
    msg = f"Unsupported format: {format}"
    raise ValueError(msg)


def _iteration_summary(iteration: dict[str, Any]) -> dict[str, Any]:
    calls = sorted(iteration.get("node_calls", []), key=lambda call: call.get("seq", 0))
    return {
        "index": iteration.get("index"),
        "datatile_id": iteration.get("datatile_id", ""),
        "status": iteration.get("status", ""),
        "node_calls": [{field: call.get(field) for field in _CALL_FIELDS} for call in calls],
    }


def _render_mermaid(iterations: list[dict[str, Any]]) -> str:
    lines = ["flowchart TB", "    %% Call Sequence"]
    for position, iteration in enumerate(iterations):
        lines.append(f'    subgraph tile_{position}["Tile {iteration["index"]}: {iteration["status"]}"]')
        calls = iteration["node_calls"]
        if not calls:
            lines.append(f'        empty_{position}["No recorded calls"]')
        for call_position, call in enumerate(calls):
            label = _call_label(call).replace('"', "'")
            lines.append(f'        call_{position}_{call_position}["{label}"]')
        for call_position in range(len(calls) - 1):
            lines.append(f"        call_{position}_{call_position} -->|seq| call_{position}_{call_position + 1}")
        lines.append("    end")
    return "\n".join(lines)


def _render_html(iterations: list[dict[str, Any]]) -> str:
    sections: list[str] = []
    for iteration in iterations:
        calls = iteration["node_calls"]
        items = "".join(f"<li>{html.escape(_call_label(call))}</li>" for call in calls)
        if not items:
            items = "<li>No recorded calls</li>"
        heading = html.escape(f'Tile {iteration["index"]}: {iteration["status"]}')
        sections.append(f"<section><h2>{heading}</h2><ol>{items}</ol></section>")
    body = "".join(sections)
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<title>Call Sequence</title><style>body{font-family:sans-serif}li{margin:.4rem}</style>"
        f"</head><body><h1>Call Sequence</h1>{body}</body></html>"
    )


def _call_label(call: dict[str, Any]) -> str:
    return (
        f'{call["seq"]}. {call["call_id"]} ({call["node_id"]}) '
        f'- {call["status"]}, {call["duration_ms"]} ms'
    )
