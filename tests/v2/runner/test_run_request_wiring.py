"""RunRequest wiring tests for the flow-only Phase H Runner boundary.

EP table:

| Runner input | Partition | Expected | Test ID |
|---|---|---|---|
| ``RunRequest(FlowTarget)`` | valid flow request | target and RdeConfig reach lifecycle | TC-EP-H1-201 |
| ``RunRequest(LegacyCallbackTarget)`` | legacy callback request | target reaches the same lifecycle (I5) | TC-EP-H1-202 |
| ``Runner.load_config(Config)`` | v1 model | normalize with origin=v1 | TC-EP-HR-F3-001 |

BV table:

| Boundary | Expected | Test ID |
|---|---|---|
| empty v2 mapping source | canonical defaults | TC-BV-H1-201 |
| v1 MultiDataTile policy | legacy field accepted and mapped | TC-BV-HR-F3-001 |
"""

from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.api.request import FlowTarget, LegacyCallbackTarget, build_run_request
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import RdeConfig


def _flow() -> None:
    return None


def _report() -> RunReport:
    return RunReport(
        run_id="run",
        status="success",
        flow_id="tests._flow",
        mode="invoice",
        started_at="<DATE>",
        duration_ms=0.0,
        config_digest="sha256:<NORMALIZED>",
        iterations=[],
        warnings=[],
    )


def test_runner_accepts_flow_run_request__tc_ep_h1_201(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-EP-H1-201/TC-BV-H1-201: Runner consumes a normalized flow request."""
    # Given: a flow request with the empty strict-v2 configuration boundary
    request = build_run_request(
        flow=_flow,
        custom_dataset_function=None,
        config={},
        root=tmp_path,
    )
    runner = Runner(root=tmp_path, run_id_factory=lambda: "run")
    captured: dict[str, Any] = {}
    monkeypatch.setattr(runner, "resolve_mode", lambda config: ModeKind.invoice)
    monkeypatch.setattr(runner, "pre_validate", lambda config: None)
    monkeypatch.setattr(runner, "post_validate", lambda config, report: None)
    monkeypatch.setattr(runner, "finalize", lambda report, config: None)

    def _iterate(target: object, mode: ModeKind, config: RdeConfig) -> RunReport:
        captured.update(target=target, mode=mode, config=config)
        return _report()

    monkeypatch.setattr(runner, "iterate", _iterate)

    # When: executing through the normalized request entrance
    report = runner.run(request)

    # Then: the normalized target and canonical config enter the lifecycle
    assert report.status == "success"
    assert captured["target"] == FlowTarget(function=_flow)
    assert captured["mode"] is ModeKind.invoice
    assert captured["config"] == RdeConfig()


def test_runner_routes_legacy_request_through_the_lifecycle__tc_ep_h1_202(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-EP-H1-202: a legacy callback target reaches the unified lifecycle (I5)."""
    # Given: a normalized legacy callback request
    callback = lambda _src, _out: None  # noqa: E731
    request = build_run_request(
        flow=None,
        custom_dataset_function=callback,
        config=None,
        root=tmp_path,
    )
    runner = Runner(root=tmp_path, run_id_factory=lambda: "run")
    captured: dict[str, Any] = {}
    monkeypatch.setattr(runner, "resolve_mode", lambda config: ModeKind.invoice)
    monkeypatch.setattr(runner, "pre_validate", lambda config: None)
    monkeypatch.setattr(runner, "post_validate", lambda config, report: None)
    monkeypatch.setattr(runner, "finalize", lambda report, config: None)

    def _iterate(target: object, mode: ModeKind, config: RdeConfig) -> RunReport:
        captured.update(target=target, mode=mode, config=config)
        return _report()

    monkeypatch.setattr(runner, "iterate", _iterate)

    # When: executing the callback entry point through the same entrance
    report = runner.run(request)

    # Then: the callback target is carried into iteration instead of rejected
    assert report.status == "success"
    assert captured["target"] == LegacyCallbackTarget(function=callback)
    assert captured["mode"] is ModeKind.invoice


def test_runner_load_config_classifies_v1_model_origin__tc_ep_hr_f3_001(
    tmp_path: Path,
) -> None:
    """TC-EP/BV-HR-F3-001: v1 Config accepts and maps MultiDataTile fields."""
    # Given: an explicit v1 Config carrying a legacy-only nested section
    from rdetoolkit.models.config import Config, MultiDataTileSettings, SystemSettings

    source = Config(
        system=SystemSettings(extended_mode="MultiDataTile"),
        multidata_tile=MultiDataTileSettings(ignore_errors=True),
    )

    # When: normalizing at the Runner request boundary
    config = Runner(root=tmp_path).load_config(source)

    # Then: v1 policy and mode fields are accepted and mapped canonically
    assert config.system.extended_mode == "MultiDataTile"
    assert config.execution.on_iteration_error == "continue"
