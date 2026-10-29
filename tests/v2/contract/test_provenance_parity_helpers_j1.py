"""The CB-OBS normalizers are themselves a contract (Session J1, audit Finding 2).

``tests/v2/contract/provenance_parity.py`` decides *what counts as equal* for the
unified-matrix observability columns, and Session J2's CB-ENTRY cells reuse it on
**failure** paths. A normalizer that silently drops a field turns a parity check
into a smoke test, and the CB-OBS cells cannot notice: they compare two successful
runs, where ``error`` and ``stacktrace`` are ``None`` on both sides. These cases
therefore exercise the normalizers directly.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``report_shape`` | two reports differing only in excluded keys | equal | TC-J1-PP-EP-001 |
| ``expected_event_names`` | one tile, no warning | canonical window | TC-J1-PP-EP-002 |
| ``graph_iterations`` | rendered json | ``duration_ms`` dropped, rest kept | TC-J1-PP-EP-003 |
| ``node_call_columns`` | two iterations | ``(node_id, seq, status)`` per iteration | TC-J1-PP-EP-004 |

BV / negative table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| ``report_shape`` | run-level ``error`` differs | **not** equal | TC-J1-PP-BV-001 |
| ``report_shape`` | iteration ``stacktrace`` differs | **not** equal | TC-J1-PP-BV-002 |
| ``report_shape`` | iteration ``error`` differs | **not** equal | TC-J1-PP-BV-003 |
| ``report_shape`` | ``node_calls`` differs | equal (compared elsewhere) | TC-J1-PP-BV-004 |
| ``report_shape`` | excluded key set | exactly the five documented keys | TC-J1-PP-BV-005 |
| ``expected_event_names`` | one run-level warning | placed right after ``run.started`` | TC-J1-PP-BV-006 |
| ``expected_event_names`` | zero tiles | just the run boundary | TC-J1-PP-BV-007 |
| ``read_events`` | ``run.meta`` header line | dropped | TC-J1-PP-BV-008 |
| ``archive_listing`` | run-id-named report entry | tokenized | TC-J1-PP-BV-009 |
| ``recorded_parent_flows`` | no iteration details on disk | empty set, no exception | TC-J1-PP-BV-010 |
"""

from __future__ import annotations

import json
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.report.run_report import RunReport
from tests.v2.contract.provenance_parity import (
    REPORT_SHAPE_EXCLUDED_KEYS,
    archive_listing,
    expected_event_names,
    graph_iterations,
    node_call_columns,
    read_events,
    recorded_parent_flows,
    report_shape,
)

_CALL: dict[str, Any] = {
    "call_id": "pkg.mod.probe#1",
    "node_id": "pkg.mod.probe",
    "seq": 1,
    "status": "completed",
    "duration_ms": 0.5,
}


def _report(**overrides: Any) -> RunReport:
    """Build a two-iteration report with every schema-"2" iteration field set."""
    base: dict[str, Any] = {
        "run_id": "run-a",
        "status": "success",
        "flow_id": "pkg.mod.flow_a",
        "mode": "invoice",
        "started_at": "2026-09-29T00:00:00Z",
        "duration_ms": 1.0,
        "config_digest": "sha256:aaa",
        "iterations": [
            {
                "index": index,
                "datatile_id": f"tile-{index}",
                "status": "completed",
                "title": "t",
                "target": "data/inputdata",
                "stacktrace": None,
                "node_calls": [dict(_CALL)],
                "error": None,
            }
            for index in (0, 1)
        ],
        "warnings": [],
        "error": None,
    }
    base.update(overrides)
    return RunReport(**base)


def _other_report(mutate: Any = None) -> RunReport:
    """Build the "other entry point's" report: only excluded keys differ."""
    report = _report(
        run_id="run-b",
        flow_id="pkg.mod.callback_b",
        started_at="2026-09-29T11:11:11Z",
        duration_ms=999.0,
        config_digest="sha256:bbb",
    )
    if mutate is None:
        return report
    payload = deepcopy(report.to_dict())
    mutate(payload)
    payload.pop("schema_version")
    return RunReport(**payload)


def test_only_excluded_keys_may_differ__tc_j1_pp_ep_001() -> None:
    """TC-J1-PP-EP-001: per-run values do not make two equal runs unequal."""
    # Given / When: two reports differing in exactly the five excluded keys
    # Then: the normalized shapes are equal
    assert report_shape(_report()) == report_shape(_other_report())


def test_run_level_error_is_compared__tc_j1_pp_bv_001() -> None:
    """TC-J1-PP-BV-001: a different terminal error must not normalize away."""

    # Given: the same run with a terminal error on one side only
    def _mutate(payload: dict[str, Any]) -> None:
        payload["error"] = {"code": 3001, "name": "NodeExecutionFailed", "message": "boom"}

    # When / Then: the shapes differ
    assert report_shape(_report()) != report_shape(_other_report(_mutate))


def test_iteration_stacktrace_is_compared__tc_j1_pp_bv_002() -> None:
    """TC-J1-PP-BV-002: a tile that failed on one side only is visible."""

    # Given: one side's tile carries a traceback
    def _mutate(payload: dict[str, Any]) -> None:
        payload["iterations"][1]["stacktrace"] = "Traceback (most recent call last): ..."

    # When / Then: the shapes differ
    assert report_shape(_report()) != report_shape(_other_report(_mutate))


def test_iteration_error_is_compared__tc_j1_pp_bv_003() -> None:
    """TC-J1-PP-BV-003: a per-tile error difference is visible."""

    # Given: one side's tile carries an error record
    def _mutate(payload: dict[str, Any]) -> None:
        payload["iterations"][0]["error"] = {"code": 999, "name": "StructuredError", "message": "no"}

    # When / Then: the shapes differ
    assert report_shape(_report()) != report_shape(_other_report(_mutate))


def test_node_calls_are_left_to_their_own_comparison__tc_j1_pp_bv_004() -> None:
    """TC-J1-PP-BV-004: ``node_calls`` is dropped here on purpose.

    Its ``call_id`` and ``duration_ms`` are per-run, so ``node_call_columns`` owns
    that comparison. Dropping it here must therefore not be mistaken for "not
    compared at all" -- TC-J1-PP-EP-004 is the other half.
    """

    # Given: one side recorded a different call
    def _mutate(payload: dict[str, Any]) -> None:
        payload["iterations"][0]["node_calls"] = [{**_CALL, "node_id": "pkg.mod.other"}]

    # When / Then: this projection is blind to it by design
    assert report_shape(_report()) == report_shape(_other_report(_mutate))


def test_excluded_key_set_is_exactly_the_documented_five__tc_j1_pp_bv_005() -> None:
    """TC-J1-PP-BV-005: the blacklist is closed, so a new field is compared."""
    # Given: the full serialized report
    payload = _report().to_dict()

    # When: normalizing it
    shape = report_shape(_report())

    # Then: exactly the documented run-level keys are missing
    assert set(payload) - set(shape) == set(REPORT_SHAPE_EXCLUDED_KEYS)
    assert len(REPORT_SHAPE_EXCLUDED_KEYS) == 5

    # And: every remaining run-level key survived, schema_version included
    assert {"schema_version", "status", "mode", "warnings", "error", "iterations"} <= set(shape)

    # And: each iteration keeps every field except node_calls
    assert set(payload["iterations"][0]) - set(shape["iterations"][0]) == {"node_calls"}


def test_canonical_sequence_for_one_tile__tc_j1_pp_ep_002() -> None:
    """TC-J1-PP-EP-002: the canonical window is the §8.1 per-tile order."""
    # Given / When / Then
    assert expected_event_names(tiles=1) == [
        "run.started",
        "iteration.started",
        "node.started",
        "node.completed",
        "iteration.completed",
        "run.completed",
    ]


def test_run_warning_sits_before_the_first_tile__tc_j1_pp_bv_006() -> None:
    """TC-J1-PP-BV-006: W1001 is published by ``resolve_mode``, before iteration."""
    # Given / When
    actual = expected_event_names(tiles=1, run_warnings=1)

    # Then: the warning occupies the slot between run.started and the first tile
    assert actual[:3] == ["run.started", "warning", "iteration.started"]
    assert actual.count("warning") == 1


def test_zero_tiles_is_just_the_run_boundary__tc_j1_pp_bv_007() -> None:
    """TC-J1-PP-BV-007: a run rejected before iteration emits only its boundary."""
    # Given / When / Then
    assert expected_event_names(tiles=0) == ["run.started", "run.completed"]


def test_run_meta_header_is_not_an_event__tc_j1_pp_bv_008(tmp_path: Path) -> None:
    """TC-J1-PP-BV-008: ``FileEventSink``'s header line must not enter the sequence."""
    # Given: a JSONL log shaped like FileEventSink's output
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "events_r1.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"schema_version": "1", "type": "run.meta", "run_id": "r1", "timestamp": 0}),
                json.dumps({"run_id": "r1", "name": "run.started"}),
                json.dumps({"run_id": "r1", "name": "run.completed"}),
                "",
            ],
        ),
        encoding="utf-8",
    )

    # When: reading it back
    actual = read_events(logs, "r1")

    # Then: only the two events are returned, and the blank line is ignored
    assert [record["name"] for record in actual] == ["run.started", "run.completed"]


def test_report_entry_is_tokenized_in_the_listing__tc_j1_pp_bv_009(tmp_path: Path) -> None:
    """TC-J1-PP-BV-009: two archives differing only by run id compare equal."""
    # Given: two archives whose report member embeds a different run id
    listings = []
    for run_id in ("run-a", "run-b"):
        archive = tmp_path / f"{run_id}.zip"
        name = f"run_report_{run_id}.json"
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("data/inputdata/x.txt", "x")
            handle.writestr(f"data/logs/{name}", "{}")
        listings.append(archive_listing(archive, report_name=name))

    # When / Then: the run-specific entry is normalized away, the rest is not
    assert listings[0] == listings[1]
    assert listings[0] == {"data/inputdata/x.txt", "data/logs/<RUN_REPORT>"}


def test_missing_iteration_details_are_an_empty_set__tc_j1_pp_bv_010(tmp_path: Path) -> None:
    """TC-J1-PP-BV-010: a run that recorded nothing yields no parent flow.

    The negative-control cell relies on this: ``set()`` -- not an exception, and
    not ``{None}`` -- is what "the pre-J1 invoker recorded nothing" looks like.
    """
    # Given: a data root whose logs directory has no iteration details
    (tmp_path / "logs").mkdir(parents=True)

    # When / Then
    assert recorded_parent_flows(tmp_path) == set()


def test_graph_drops_only_wall_clock_values__tc_j1_pp_ep_003() -> None:
    """TC-J1-PP-EP-003: ``duration_ms`` goes, node identity and order stay."""
    # Given: a rendered call sequence
    rendered = json.dumps(
        {
            "title": "Call Sequence",
            "run_id": "run-a",
            "iterations": [
                {"index": 0, "datatile_id": "t0", "status": "completed", "node_calls": [dict(_CALL)]},
            ],
        },
    )

    # When: normalizing it
    actual = graph_iterations(rendered)

    # Then: every field except duration_ms survives
    assert actual == [
        {
            "index": 0,
            "datatile_id": "t0",
            "status": "completed",
            "node_calls": [{"call_id": "pkg.mod.probe#1", "node_id": "pkg.mod.probe", "seq": 1, "status": "completed"}],
        },
    ]


def test_node_call_columns_are_per_iteration__tc_j1_pp_ep_004() -> None:
    """TC-J1-PP-EP-004: the provenance column is one list per iteration."""
    # Given / When / Then
    assert node_call_columns(_report()) == [
        [("pkg.mod.probe", 1, "completed")],
        [("pkg.mod.probe", 1, "completed")],
    ]


@pytest.mark.parametrize(
    "excluded",
    [pytest.param(key, id=key) for key in REPORT_SHAPE_EXCLUDED_KEYS],
)
def test_each_excluded_key_is_individually_ignored__tc_j1_pp_bv_011(excluded: str) -> None:
    """TC-J1-PP-BV-011: no excluded key leaks into the comparison through aliasing."""
    # Given: a report differing from the baseline in exactly one excluded key
    payload = deepcopy(_report().to_dict())
    payload[excluded] = "sentinel-value" if isinstance(payload[excluded], str) else -1.0
    payload.pop("schema_version")

    # When / Then: the shapes still compare equal
    assert report_shape(_report()) == report_shape(RunReport(**payload))
