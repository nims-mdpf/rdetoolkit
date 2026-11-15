"""Completed iteration history survives a post-validation failure (#685, GA-01).

``Runner._execute`` builds a populated report with ``iterate()`` and then
calls ``post_validate()``. When post-validation raised, ``Runner.run`` replaced
that report with ``_failed_report()``, whose ``iterations`` is ``[]``: the
executed tiles and their node calls disappeared from the run report, and with
them from ``report show`` and ``report trace``. The run must still be reported
as ``failed`` with the validation code, but the evidence of what ran is kept.

The shipped command that renders the call sequence is ``report trace`` (the
issue's ``rdetoolkit graph``); the shipped name is used.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-GA685-EP-001 | invalid metadata, every mode | node writes a schema-invalid metadata.json | failed, 4002, iterations + node calls kept |
| TC-GA685-EP-002 | persisted report | same run | run_report JSON is schema "2" with the kept iterations; job.failed = 4002 |
| TC-GA685-EP-003 | CLI traversal | same run | ``report show`` counts the tiles; ``report trace`` names the node |
| TC-GA685-EP-004 | invalid tile invoice | node blanks the tile invoice's basic block | failed, 4001, iterations kept |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-GA685-EV-010 | identity fields | invalid metadata run | run_id / mode / flow_id / config_digest match the run, duration covers the run |
| TC-GA685-EV-011 | no rewrite | invalid metadata run | every kept tile and node call stays ``completed`` |
| TC-GA685-EV-012 | bounded summary | invalid metadata run | node_calls carry only the summary keys (no inputs/outputs) |
| TC-GA685-EV-013 | pre-validation failure | schema-invalid source invoice | failed, 4001, iterations == [] (shape unchanged) |
| TC-GA685-EV-014 | tile failure | node raises under fail_fast | failed, 3001 with call_id, the failed tile listed (shape unchanged) |
| TC-GA685-EV-015 | partial | one of three tiles fails under continue | partial, no run error (shape unchanged) |
| TC-GA685-EV-016 | success, metadata absent | node writes nothing (metadata optional per v1) | success, no job.failed |
| TC-GA685-EV-017 | partial + post-validate | continue, one tile fails, one writes invalid metadata | failed 4002, both tiles kept with their own statuses, warnings kept |
| TC-GA685-EV-018 | v1 callback entry | callback writes invalid metadata | failed 4002 with the tile kept; job.failed 4002 |
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from rdetoolkit.api.request import FlowTarget, LegacyCallbackTarget, RunRequest
from rdetoolkit.cli.app import app
from rdetoolkit.core.flow import derive_flow_id, flow
from rdetoolkit.core.node import node
from rdetoolkit.errors import ERROR_CATALOG
from rdetoolkit.report.run_report import RUN_REPORT_SCHEMA_VERSION, RunReport
from rdetoolkit.runner.config_loader import compute_config_digest
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths, IterationInfo, OutputContext
from tests.v2.contract.fixtures import _generate

ALL_MODES = ("invoice", "excelinvoice", "multidatatile", "rdeformat", "smarttable")
INVALID_METADATA = '{"constant": "not-a-mapping", "variable": 3}'
_NODE_CALL_SUMMARY_KEYS = {"call_id", "node_id", "seq", "status", "duration_ms"}


@node
def write_invalid_metadata(out: OutputContext) -> None:
    """Publish a metadata.json that the per-tile artifact contract rejects."""
    out.meta.mkdir(parents=True, exist_ok=True)
    (out.meta / "metadata.json").write_text(INVALID_METADATA, encoding="utf-8")


@node
def blank_tile_invoice(out: OutputContext) -> None:
    """Rewrite the tile invoice so that it violates the invoice schema."""
    invoice_path = out.invoice / "invoice.json"
    invoice = json.loads(invoice_path.read_text(encoding="utf-8"))
    invoice["basic"] = None
    invoice_path.write_text(json.dumps(invoice), encoding="utf-8")


@node
def touch_nothing(paths: InputPaths) -> int:
    """Run successfully without publishing metadata (metadata is optional)."""
    return len(paths.rawfiles)


@node
def explode(paths: InputPaths) -> None:
    """Fail the tile from inside a node body."""
    _ = paths
    msg = "boom in node body"
    raise RuntimeError(msg)


@node
def fail_second_tile(iteration: IterationInfo) -> None:
    """Fail only tile 1, so a continue run is partial."""
    if iteration.index == 1:
        msg = "tile 1 fails"
        raise RuntimeError(msg)


@node
def fail_tile_one_or_poison_tile_zero(iteration: IterationInfo, out: OutputContext) -> None:
    """Fail tile 1 and leave an invalid metadata.json in every other tile."""
    if iteration.index == 1:
        msg = "tile 1 fails"
        raise RuntimeError(msg)
    out.meta.mkdir(parents=True, exist_ok=True)
    (out.meta / "metadata.json").write_text(INVALID_METADATA, encoding="utf-8")


@flow
def invalid_metadata_flow(out: OutputContext) -> None:
    write_invalid_metadata(out)


@flow
def invalid_invoice_flow(out: OutputContext) -> None:
    blank_tile_invoice(out)


@flow
def metadata_free_flow(paths: InputPaths) -> None:
    touch_nothing(paths)


@flow
def exploding_flow(paths: InputPaths) -> None:
    explode(paths)


@flow
def second_tile_fails_flow(iteration: IterationInfo) -> None:
    fail_second_tile(iteration)


@flow
def partial_then_invalid_flow(iteration: IterationInfo, out: OutputContext) -> None:
    fail_tile_one_or_poison_tile_zero(iteration, out)


def _invalid_metadata_callback(srcpaths: Any, resource_paths: Any) -> None:
    """A v1 dataset callback that publishes an invalid metadata.json."""
    _ = srcpaths
    meta = Path(resource_paths.meta)
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "metadata.json").write_text(INVALID_METADATA, encoding="utf-8")


def _runner(root: Path) -> Runner:
    return Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
    )


def _run_flow(root: Path, mode: str, flow_fn: Any, monkeypatch: pytest.MonkeyPatch) -> RunReport:
    _generate.materialize_sut_case(mode, root)
    monkeypatch.chdir(root)
    return _runner(root).run(
        RunRequest(root=root, target=FlowTarget(function=flow_fn), config_source=_generate.oracle_config(mode)),
    )


def _run_flow_with(root: Path, flow_fn: Any, overrides: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> RunReport:
    """Run a multi-tile MultiDataTile case with mapping overrides (error policy)."""
    _generate.materialize_sut_case("multidatatile", root)
    monkeypatch.chdir(root)
    return _runner(root).run(flow_fn, **overrides)


def _multidatatile_overrides(policy: str) -> dict[str, Any]:
    return {
        "system": {"extended_mode": "MultiDataTile", "save_thumbnail_image": False, "magic_variable": False},
        "execution": {"on_iteration_error": policy},
    }


def _job_failed_code(root: Path) -> str:
    return (root / "data" / "job.failed").read_text(encoding="utf-8").splitlines()[0]


def _persisted(root: Path, report: RunReport) -> dict[str, Any]:
    path = root / "data" / "logs" / f"run_report_{report.run_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _node_ids(report: RunReport) -> list[str]:
    return [call["node_id"] for iteration in report.iterations for call in iteration["node_calls"]]


@pytest.mark.parametrize("mode", ALL_MODES)
def test_invalid_metadata_keeps_executed_tiles_and_calls__tc_ga685_ep_001(
    mode: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-GA685-EP-001: a post-validation failure keeps the executed tiles."""
    # Given: a realistic mode input and a flow whose node publishes invalid metadata
    root = tmp_path / mode

    # When: running the flow through the unified Runner
    report = _run_flow(root, mode, invalid_metadata_flow, monkeypatch)

    # Then: the run failed in validation with the metadata code
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == 4002
    assert report.error["name"] == ERROR_CATALOG[4002].name
    assert "call_id" not in report.error

    # And: the executed tiles and their node calls are still in the report
    assert report.iterations, f"{mode}: post-validation failure dropped the iteration history"
    assert write_invalid_metadata.__node_spec__.id in _node_ids(report)


@pytest.mark.parametrize("mode", ["invoice", "multidatatile"])
def test_post_validate_failure_persists_complete_report__tc_ga685_ep_002(
    mode: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-GA685-EP-002: report JSON and job.failed both describe the failure."""
    # Given: a run that fails in post-validation
    root = tmp_path / mode

    # When: running it
    report = _run_flow(root, mode, invalid_metadata_flow, monkeypatch)

    # Then: job.failed carries the validation code
    assert _job_failed_code(root) == "ErrorCode=4002"

    # And: the persisted report is version-compatible and keeps the history
    persisted = _persisted(root, report)
    assert persisted["schema_version"] == RUN_REPORT_SCHEMA_VERSION
    assert persisted["status"] == "failed"
    assert persisted["error"]["code"] == 4002
    assert persisted["iterations"] == report.iterations
    assert RunReport.from_json(json.dumps(persisted)) == report

    # And: the failure keeps its distinct phase for GA-02 (#686 sidecar)
    sidecar_path = root / "data" / "logs" / f"diagnostics_{report.run_id}.json"
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert [item["phase"] for item in sidecar["diagnostics"]] == ["post_validate"]
    assert sidecar["diagnostics"][0]["code"] == 4002


def test_cli_traverses_preserved_call_summary__tc_ga685_ep_003(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-GA685-EP-003: ``report show`` and ``report trace`` read the kept calls."""
    # Given: a persisted report of a post-validation failure
    root = tmp_path / "invoice"
    report = _run_flow(root, "invoice", invalid_metadata_flow, monkeypatch)
    report_path = root / "data" / "logs" / f"run_report_{report.run_id}.json"
    cli = CliRunner()

    # When: displaying and tracing it
    shown = cli.invoke(app, ["report", "show", str(report_path)])
    traced = cli.invoke(app, ["report", "trace", str(report_path), "--format", "json"])

    # Then: both commands see the executed tile and node call
    assert shown.exit_code == 0, shown.output
    assert "status: failed" in shown.output
    assert "iterations: 1" in shown.output
    assert traced.exit_code == 0, traced.output
    rendered = json.loads(traced.output)
    calls = [call for iteration in rendered["iterations"] for call in iteration["node_calls"]]
    assert [call["node_id"] for call in calls] == [write_invalid_metadata.__node_spec__.id]


def test_invalid_tile_invoice_keeps_history__tc_ga685_ep_004(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-GA685-EP-004: an invoice-schema post-validation failure also keeps tiles."""
    # Given: a flow whose node invalidates the published tile invoice
    root = tmp_path / "invoice"

    # When: running it
    report = _run_flow(root, "invoice", invalid_invoice_flow, monkeypatch)

    # Then: the run failed with 4001 and the tile is kept
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == 4001
    assert _node_ids(report) == [blank_tile_invoice.__node_spec__.id]
    assert _job_failed_code(root) == "ErrorCode=4001"


def test_identity_fields_are_those_of_the_run__tc_ga685_ev_010(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-GA685-EV-010: run_id, mode, flow_id and config_digest are kept."""
    # Given: a post-validation failure under the v1 oracle config
    root = tmp_path / "multidatatile"
    runs: list[str] = []
    _generate.materialize_sut_case("multidatatile", root)
    monkeypatch.chdir(root)
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
        run_id_factory=lambda: runs.append("x") or "ga685-identity-run",
    )
    config = _generate.oracle_config("multidatatile")

    # When: running it
    report = runner.run(RunRequest(root=root, target=FlowTarget(function=invalid_metadata_flow), config_source=config))

    # Then: the identity fields are the run's own
    assert report.run_id == "ga685-identity-run"
    assert report.mode == "multidatatile"
    assert report.flow_id == derive_flow_id(invalid_metadata_flow)
    assert report.config_digest == compute_config_digest(runner.load_config(config))
    assert report.duration_ms > 0.0
    assert report.started_at
    assert len(runs) == 1


def test_kept_tiles_are_not_rewritten_as_failed__tc_ga685_ev_011(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-GA685-EV-011: successful tile execution stays ``completed``."""
    # Given / When: a multi-tile post-validation failure
    report = _run_flow(tmp_path / "multidatatile", "multidatatile", invalid_metadata_flow, monkeypatch)

    # Then: every kept tile and call is reported as it executed
    assert report.status == "failed"
    assert len(report.iterations) == 2
    assert {iteration["status"] for iteration in report.iterations} == {"completed"}
    assert {call["status"] for iteration in report.iterations for call in iteration["node_calls"]} == {"completed"}
    assert all(iteration["error"] is None for iteration in report.iterations)
    assert [iteration["index"] for iteration in report.iterations] == [0, 1]


def test_kept_summary_is_bounded__tc_ga685_ev_012(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-GA685-EV-012: only the lightweight call summary is kept in memory."""
    # Given / When: a post-validation failure
    report = _run_flow(tmp_path / "invoice", "invoice", invalid_metadata_flow, monkeypatch)

    # Then: node calls carry the summary keys only, not the per-call detail
    calls = [call for iteration in report.iterations for call in iteration["node_calls"]]
    assert calls
    assert all(set(call) == _NODE_CALL_SUMMARY_KEYS for call in calls)


@pytest.mark.parametrize("mode", ALL_MODES)
def test_pre_validation_failure_keeps_empty_iterations__tc_ga685_ev_013(
    mode: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-GA685-EV-013: no tile ran, so the shape is unchanged (``[]``)."""
    # Given: a source invoice that violates its schema
    root = tmp_path / mode
    _generate.materialize_sut_case(mode, root)
    _generate._invalidate_invoice(root)  # noqa: SLF001 -- the generator owns the defect
    monkeypatch.chdir(root)

    # When: running a flow that would publish invalid metadata
    report = _runner(root).run(
        RunRequest(
            root=root,
            target=FlowTarget(function=invalid_metadata_flow),
            config_source=_generate.oracle_config(mode),
        ),
    )

    # Then: the run failed before any tile, with no iteration history
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == 4001
    assert report.iterations == []


def test_tile_failure_shape_is_unchanged__tc_ga685_ev_014(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-GA685-EV-014: a node failure keeps its call-attributed shape."""
    # Given / When: a node raising under fail_fast
    report = _run_flow_with(tmp_path / "mdt", exploding_flow, _multidatatile_overrides("fail_fast"), monkeypatch)

    # Then: the first tile failed, the run error names the call
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == 3001
    assert report.error["call_id"] == f"{explode.__node_spec__.id}#1"
    assert [iteration["status"] for iteration in report.iterations] == ["failed"]


def test_partial_shape_is_unchanged__tc_ga685_ev_015(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-GA685-EV-015: a partial run has no run error and keeps every tile."""
    # Given / When: one failing tile of two under continue
    report = _run_flow_with(tmp_path / "mdt", second_tile_fails_flow, _multidatatile_overrides("continue"), monkeypatch)

    # Then: partial, with both tiles and no run-level error
    assert report.status == "partial"
    assert report.error is None
    assert [iteration["status"] for iteration in report.iterations] == ["completed", "failed"]
    assert report.warnings[0]["code"] == 3001


@pytest.mark.parametrize("mode", ALL_MODES)
def test_success_without_metadata_is_unchanged__tc_ga685_ev_016(
    mode: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-GA685-EV-016: an absent metadata.json is optional and still succeeds."""
    # Given / When: a flow that publishes no metadata
    root = tmp_path / mode
    report = _run_flow(root, mode, metadata_free_flow, monkeypatch)

    # Then: the run succeeds and leaves no job.failed
    assert report.status == "success"
    assert report.error is None
    assert report.iterations
    assert not (root / "data" / "job.failed").exists()


def test_partial_then_post_validate_failure_keeps_both_tiles__tc_ga685_ev_017(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-GA685-EV-017: the failed and the completed tile keep their own statuses."""
    # Given / When: tile 1 fails, tile 0 publishes invalid metadata, under continue
    report = _run_flow_with(
        tmp_path / "mdt",
        partial_then_invalid_flow,
        _multidatatile_overrides("continue"),
        monkeypatch,
    )

    # Then: the run failed with the validation error of the completed tile
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == 4002

    # And: tile statuses are as executed, and the iteration warning survives
    assert [iteration["status"] for iteration in report.iterations] == ["completed", "failed"]
    assert report.iterations[1]["error"]["code"] == 3001
    assert report.warnings and report.warnings[0]["code"] == 3001


def test_v1_callback_entry_keeps_the_tile__tc_ga685_ev_018(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-GA685-EV-018: the legacy callback target keeps the executed tile too."""
    # Given: a v1 callback that publishes invalid metadata
    root = tmp_path / "invoice"
    _generate.materialize_sut_case("invoice", root)
    monkeypatch.chdir(root)

    # When: running it as the v1 entry does
    report = _runner(root).run(
        RunRequest(
            root=root,
            target=LegacyCallbackTarget(function=_invalid_metadata_callback),
            config_source=_generate.oracle_config("invoice"),
        ),
    )

    # Then: failed with 4002 and the executed tile kept
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == 4002
    assert [iteration["status"] for iteration in report.iterations] == ["completed"]
    assert _job_failed_code(root) == "ErrorCode=4002"
