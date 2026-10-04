"""Normalizers comparing the observability of two entry points (Session J1).

The unified-matrix columns 6 (RunReport), 7 (Events), 8 (Provenance) and 12
(repro archive) of ``merge_v1/contract_matrix.md`` are all "does the v1 callback
entry point produce the same thing a ``@flow`` produces?" questions. Every one of
them needs the same normalization — run ids, absolute paths, timestamps and
durations differ between two runs by construction — so the normalizers live here
instead of in the cells.

Session J2 reuses these for the ``TC-UM-*-CB-ENTRY-*`` cells: the public
``workflows.run`` entry point has to produce the same observability as the
``LegacyCallbackTarget`` path this session pins.

Nothing here reads a frozen fixture: these functions compare two *live* runs with
each other. Frozen-observation comparison stays in ``observe.py``.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from rdetoolkit.report.run_report import RunReport

#: The only ``name`` values §8.1 allows for a node call, in bridge order.
NODE_EVENT_NAMES = ("node.started", "node.completed", "node.failed")

#: One tile's canonical event window for a run whose target performs exactly one
#: recorded ``@node`` call and succeeds.
SINGLE_NODE_TILE_EVENTS = (
    "iteration.started",
    "node.started",
    "node.completed",
    "iteration.completed",
)


def expected_event_names(
    *,
    tiles: int,
    tile_window: tuple[str, ...] = SINGLE_NODE_TILE_EVENTS,
    run_warnings: int = 0,
) -> list[str]:
    """Return the full canonical event-name sequence for a successful run.

    Args:
        tiles: Number of iterations the run executes.
        tile_window: Event names one tile contributes, in order.
        run_warnings: Run-level ``warning`` events. They are emitted by
            ``resolve_mode``, which runs between ``run.started`` and the first
            tile, so they occupy that position.

    Returns:
        ``run.started``, the run-level warnings, one window per tile, then
        ``run.completed``.
    """
    return ["run.started", *["warning"] * run_warnings, *list(tile_window) * tiles, "run.completed"]


def read_events(logs_dir: Path, run_id: str) -> list[dict[str, Any]]:
    """Return the JSONL events of one run, without the ``run.meta`` header.

    Args:
        logs_dir: Directory a ``FileEventSink`` wrote to.
        run_id: Run identifier naming the event log.

    Returns:
        The decoded event records in written order.
    """
    path = logs_dir / f"events_{run_id}.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return [record for record in records if record.get("type") != "run.meta"]


def event_names(logs_dir: Path, run_id: str) -> list[str]:
    """Return the ordered event names of one run (matrix column 7)."""
    return [str(record["name"]) for record in read_events(logs_dir, run_id)]


def node_event_ids(logs_dir: Path, run_id: str) -> list[tuple[str, str]]:
    """Return ``(name, node_id)`` for the node events only.

    ``call_id`` and timestamps are deliberately dropped: they are per-run values,
    while the node identity and the bridge order are the contract.
    """
    return [
        (str(record["name"]), str(record.get("node_id")))
        for record in read_events(logs_dir, run_id)
        if record["name"] in NODE_EVENT_NAMES
    ]


def node_call_columns(report: RunReport) -> list[list[tuple[str, int, str]]]:
    """Return ``(node_id, seq, status)`` per iteration (matrix column 8).

    ``call_id`` carries the node id and the seq already, and ``duration_ms`` is
    wall-clock, so neither is comparable across two runs.
    """
    return [
        [
            (str(call["node_id"]), int(call["seq"]), str(call["status"]))
            for call in iteration.get("node_calls", [])
        ]
        for iteration in report.to_dict()["iterations"]
    ]


def recorded_parent_flows(data_root: Path) -> set[str | None]:
    """Return every ``parent_flow`` the run streamed to its iteration details.

    ``RunReport.iterations[*].node_calls`` is a summary that does not carry
    ``parent_flow`` (schema "2"), so the full ``NodeCallRecord`` is read back from
    ``logs/iterations/iteration_*.json`` — the primary record the aggregator
    streams per tile.

    Args:
        data_root: The run's data root.

    Returns:
        The distinct ``parent_flow`` values of every recorded call. Empty when
        the run recorded no call at all.
    """
    iterations_dir = data_root / "logs" / "iterations"
    parents: set[str | None] = set()
    for path in sorted(iterations_dir.glob("iteration_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for record in payload.get("call_records", []):
            parents.add(record.get("parent_flow"))
    return parents


#: Run-level RunReport keys two runs of the same work cannot reproduce.
#: ``run_id`` / ``started_at`` / ``duration_ms`` are per-run values; ``flow_id``
#: is *supposed* to differ (it identifies the callback on one side and the flow on
#: the other, and is checked separately against ``parent_flow``);
#: ``config_digest`` is a digest of the effective config, which the two runs reach
#: through different normalization origins.
REPORT_SHAPE_EXCLUDED_KEYS = ("run_id", "flow_id", "started_at", "duration_ms", "config_digest")

#: Per-iteration key compared by :func:`node_call_columns` instead, because its
#: ``call_id`` and ``duration_ms`` entries are per-run values.
_ITERATION_EXCLUDED_KEY = "node_calls"


def report_shape(report: RunReport) -> dict[str, Any]:
    """Return the RunReport values two entry points must share (column 6).

    This is a **blacklist** over ``report.to_dict()``, not a whitelist: a field the
    schema gains is compared by default, and only the five run-level keys in
    :data:`REPORT_SHAPE_EXCLUDED_KEYS` plus each iteration's ``node_calls`` are
    dropped. Everything else is compared — notably the run-level ``error`` and
    each iteration's ``error`` and ``stacktrace``. Session J2's CB-ENTRY cells
    reuse this on failure paths, where silently skipping those three would be the
    difference between a parity check and a smoke test.

    Args:
        report: Report produced by one of the two entry points.

    Returns:
        The comparable projection of the report.
    """
    payload = report.to_dict()
    shape = {key: value for key, value in payload.items() if key not in REPORT_SHAPE_EXCLUDED_KEYS}
    shape["iterations"] = [
        {key: value for key, value in iteration.items() if key != _ITERATION_EXCLUDED_KEY}
        for iteration in payload["iterations"]
    ]
    return shape


def graph_iterations(rendered: str) -> list[dict[str, Any]]:
    """Return ``graph --format json`` iterations with wall-clock values dropped.

    ``duration_ms`` is measured, so two runs of the same work never agree on it;
    every other rendered field is a contract.

    Args:
        rendered: Standard output of ``rdetoolkit graph --format json``.

    Returns:
        The iteration objects, each ``node_calls`` entry without ``duration_ms``.
    """
    payload = json.loads(rendered)
    return [
        {
            **iteration,
            "node_calls": [
                {key: value for key, value in call.items() if key != "duration_ms"}
                for call in iteration["node_calls"]
            ],
        }
        for iteration in payload["iterations"]
    ]


def archive_listing(archive: Path, *, report_name: str) -> set[str]:
    """Return an archive's member names with the run-specific report normalized.

    Args:
        archive: Zip produced by ``rdetoolkit repro export``.
        report_name: File name of the run report inside the archive; it embeds
            the run id, so it is replaced by a stable token.

    Returns:
        The member name set, report entry normalized (matrix column 12).
    """
    with zipfile.ZipFile(archive) as handle:
        names = set(handle.namelist())
    return {"data/logs/<RUN_REPORT>" if name.endswith(report_name) else name for name in names}


def run_report_path(data_root: Path, run_id: str) -> Path:
    """Return the report file the finalizer wrote for one run."""
    return data_root / "logs" / f"run_report_{run_id}.json"
