"""1000-tile scale seat for the unified Runner (Session K3, ruling #5).

Design authority: PhaseK_prompts ruling #6(d)/(e). One MultiDataTile run of
1000 single-file tiles through a three-node flow, recorded by the Runner's
default ``FileEventSink``, must succeed within the CI budget and stay well
inside the size envelope Q6 estimated, and two runs over identical inputs
must agree on tile order and on every ordering column the logs expose.

The test is marked ``slow`` but is **not** deselected by default: the project
``addopts`` only deselects ``legacy``, so ``tox -e py3xx-module`` runs it. A
local run takes roughly 5 s per Runner pass; deselect with ``-m "not slow"``
when iterating.

EP table:

| TC-ID           | Partition                         | Expected                                               |
|-----------------|-----------------------------------|--------------------------------------------------------|
| TC-K3-SCALE-001 | 1000 tiles x 3 nodes, run twice   | both runs succeed, 1000 completed iterations each      |
| TC-K3-SCALE-002 | same                              | events file ends with run.completed, every line parses  |
| TC-K3-SCALE-003 | same, run A vs run B              | identical index/datatile_id/target/status columns      |
| TC-K3-SCALE-004 | same, run A vs run B              | identical node_calls (call_id, node_id, seq) columns   |
| TC-K3-SCALE-005 | same, run A vs run B              | identical event (name, node_id, call_id, index) stream |

BV table:

| TC-ID           | Boundary                          | Expected                                               |
|-----------------|-----------------------------------|--------------------------------------------------------|
| TC-K3-SCALE-BV1 | events file size                  | < 16 MiB (no W1002 at the 64 MiB cap)                  |
| TC-K3-SCALE-BV2 | RunReport JSON size               | < 8 MiB                                                |
| TC-K3-SCALE-BV3 | wall clock per run                | < 120 s                                                |
| TC-K3-SCALE-BV4 | tile order                        | index 0..999 follows sorted input names                |
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import IterationInfo

_TILES = 1000
_EVENTS_LIMIT = 16 * 1024 * 1024
_REPORT_LIMIT = 8 * 1024 * 1024
_WALL_CLOCK_LIMIT_S = 120.0

_INVOICE: dict[str, Any] = {
    "datasetId": "k3-scale",
    "basic": {"dateSubmitted": "2026-10-16", "dataOwnerId": "0" * 56, "dataName": "k3-scale"},
}


@node(id="k3_scale_read")
def _read(iteration: IterationInfo) -> int:
    return iteration.index


@node(id="k3_scale_transform")
def _transform(value: int) -> int:
    return value + 1


@node(id="k3_scale_write")
def _write(value: int) -> None:
    del value


@flow
def _scale_flow(iteration: IterationInfo) -> None:
    _write(_transform(_read(iteration)))


def _build_root(root: Path) -> Path:
    data_root = root / "data"
    inputdata = data_root / "inputdata"
    inputdata.mkdir(parents=True)
    # Reverse creation order so a directory-order dependency would show up.
    for index in reversed(range(_TILES)):
        (inputdata / f"tile_{index:04d}.txt").write_text(f"{index}", encoding="utf-8")
    (data_root / "invoice").mkdir()
    (data_root / "invoice" / "invoice.json").write_text(json.dumps(_INVOICE), encoding="utf-8")
    (data_root / "tasksupport").mkdir()
    # The schema below is the minimal valid invoice schema; jsonschema still emits its
    # metaschema DeprecationWarning per tile (known noise, see contracts §K3 debts).
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "properties": {}}
    (data_root / "tasksupport" / "invoice.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    (data_root / "temp").mkdir()
    return data_root


def _run_once(root: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, Any], list[dict[str, Any]], int, int, float]:
    data_root = _build_root(root)
    monkeypatch.chdir(root)
    runner = Runner(root=root, inputdata_path=data_root / "inputdata", unpacked_dir_path=data_root / "temp")
    started = time.perf_counter()
    report = runner.run(_scale_flow, system={"extended_mode": "MultiDataTile"})
    elapsed = time.perf_counter() - started
    events_path = data_root / "logs" / f"events_{report.run_id}.jsonl"
    report_path = data_root / "logs" / f"run_report_{report.run_id}.json"
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    persisted = json.loads(report_path.read_text(encoding="utf-8"))
    return persisted, events, events_path.stat().st_size, report_path.stat().st_size, elapsed


def _iteration_columns(report: dict[str, Any]) -> list[tuple[Any, ...]]:
    return [(entry["index"], entry["datatile_id"], entry["target"], entry["status"]) for entry in report["iterations"]]


def _call_columns(report: dict[str, Any]) -> list[tuple[Any, ...]]:
    return [
        (entry["index"], call["call_id"], call["node_id"], call["seq"])
        for entry in report["iterations"]
        for call in entry["node_calls"]
    ]


def _event_columns(events: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    return [
        (
            event.get("name"),
            event.get("node_id"),
            event.get("payload", {}).get("call_id"),
            event.get("payload", {}).get("iteration_index"),
        )
        for event in events[1:]
    ]


@pytest.mark.slow
def test_thousand_tile_run_is_bounded_and_deterministic__tc_k3_scale_001(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K3-SCALE-001..005 / BV1..BV4: 1000 tiles, twice, bounded and identical."""
    # Given/When: two independent 1000-tile runs over identical inputs
    report_a, events_a, events_size_a, report_size_a, elapsed_a = _run_once(tmp_path / "a", monkeypatch)
    report_b, events_b, events_size_b, report_size_b, elapsed_b = _run_once(tmp_path / "b", monkeypatch)

    # Then: both succeed with every tile completed
    for report in (report_a, report_b):
        assert report["status"] == "success"
        assert report["schema_version"] == "2"
        assert len(report["iterations"]) == _TILES
        assert {entry["status"] for entry in report["iterations"]} == {"completed"}
    # And: the event streams are complete and below the cap with no truncation
    for events in (events_a, events_b):
        assert events[0]["type"] == "run.meta"
        assert events[-1]["name"] == "run.completed"
        assert events[-1]["payload"] == {"status": "success"}
        assert not [event for event in events if event.get("name") == "warning"]
        assert len([event for event in events if event.get("name") == "node.completed"]) == 3 * _TILES
    # And: the size and time envelopes hold
    assert max(events_size_a, events_size_b) < _EVENTS_LIMIT
    assert max(report_size_a, report_size_b) < _REPORT_LIMIT
    assert max(elapsed_a, elapsed_b) < _WALL_CLOCK_LIMIT_S, f"wall clock {elapsed_a:.1f}s / {elapsed_b:.1f}s"
    # And: tiles follow sorted input names regardless of creation order
    assert [entry["index"] for entry in report_a["iterations"]] == list(range(_TILES))
    assert [entry["datatile_id"] for entry in report_a["iterations"]] == [f"tile_{i:04d}" for i in range(_TILES)]
    # And: every ordering column agrees across the two runs
    assert _iteration_columns(report_a) == _iteration_columns(report_b)
    assert _call_columns(report_a) == _call_columns(report_b)
    assert _event_columns(events_a) == _event_columns(events_b)
    print(  # noqa: T201 - the wall clock is the seat's evidence
        f"\nK3 scale: run A {elapsed_a:.2f}s, run B {elapsed_b:.2f}s, "
        f"events {events_size_a} B, report {report_size_a} B",
    )
