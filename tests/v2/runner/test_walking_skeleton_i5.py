"""I5 walking skeleton: five modes x two entry points share one Runner lifecycle.

Every case materializes a real committed input family (no mocks) and drives the
production ``Runner``, so a passing case proves the whole ordered lifecycle
``resolve -> validate -> iterate -> prepare tile -> invoke -> validate outputs
-> finalize`` (merge_v1 Design Phase I5).

Equivalence partitions (EP):

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``Runner.run`` | flow entry, 5 modes | success, v1 tile count, ordered lifecycle | TC-EP-I5-201 |
| ``Runner.run`` | legacy callback entry, 5 modes | success, v1 tile count, same lifecycle | TC-EP-I5-202 |
| ``Runner.run`` | callback entry, both v1 signatures | both are dispatched | TC-EP-I5-203 |
| ``Runner.resolve_mode`` | handlers installed | W1001 still warns (I5.3) | TC-EP-I5-301 |

Boundary values (BV):

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| ``Runner.run`` | callback target without a function | success with zero user calls | TC-BV-I5-201 |
| ``Runner.run`` | failing callback | failed run, finalize still reached | TC-BV-I5-202 |
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit import flow
from rdetoolkit.api.request import LegacyCallbackTarget, RunRequest
from rdetoolkit.models.rde2types import RdeDatasetPaths, RdeInputDirPaths, RdeOutputResourcePath
from rdetoolkit.modes import handler_for
from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.paths import resolve_tile_paths
from rdetoolkit.types import OutputContext, RdeConfig, V2SystemSettings
from tests.v2.contract.fixtures import _generate

_MODES = ("invoice", "excelinvoice", "multidatatile", "rdeformat", "smarttable")
# Both v1 callback signatures must appear in the ten accepted cases.
_UNIFIED_SIGNATURE_MODES = frozenset({"excelinvoice", "rdeformat"})
_MARKER = "i5_entry.txt"


def _oracle_tile_count(mode: str) -> int:
    """Return how many tiles v1 produced for this mode's frozen OK observation.

    The frozen G1 snapshot records one callback invocation per tile, so it is
    the tile-count oracle for the walking skeleton. Reading it here keeps the
    expectation from drifting away from the fixture it is derived from.
    """
    snapshot = json.loads((_generate.EXPECTED_ROOT / mode / "ok.json").read_text(encoding="utf-8"))
    return int(snapshot["observed"]["callback_count"])


class _RecordingRunner(Runner):
    """Record lifecycle step order without replacing any production step."""

    def __init__(self, calls: list[str], **kwargs: Any) -> None:
        self._calls = calls
        super().__init__(**kwargs)

    def load_config(self, source: object | None = None) -> RdeConfig:
        self._calls.append("load_config")
        return super().load_config(source)

    def resolve_mode(self, config: RdeConfig) -> ModeKind:
        self._calls.append("resolve_mode")
        return super().resolve_mode(config)

    def pre_validate(self, config: RdeConfig) -> None:
        self._calls.append("pre_validate")
        super().pre_validate(config)

    def iterate(self, target: Any, mode: ModeKind, config: RdeConfig) -> RunReport:
        self._calls.append("iterate")
        return super().iterate(target, mode, config)

    def post_validate(self, config: RdeConfig, report: RunReport) -> None:
        self._calls.append("post_validate")
        super().post_validate(config, report)

    def finalize(self, report: RunReport, config: RdeConfig) -> None:
        self._calls.append("finalize")
        super().finalize(report, config)


def _overrides(mode: str) -> dict[str, dict[str, str]]:
    extended = {"multidatatile": "MultiDataTile", "rdeformat": "rdeformat"}.get(mode)
    return {"system": {"extended_mode": extended}} if extended is not None else {}


def _runner(root: Path, calls: list[str]) -> _RecordingRunner:
    return _RecordingRunner(
        calls,
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "unpacked",
        run_id_factory=lambda: "i5-run",
    )


def _mark(invoice_dir: Path, struct_dir: Path, calls: list[str], entry: str) -> None:
    """Prove the tile was prepared before invocation and outputs are writable."""
    calls.append("invoke")
    assert (invoice_dir / "invoice.json").exists(), "tile invoice must be prepared before invoke"
    (struct_dir / _MARKER).write_text(f"{entry}\n", encoding="utf-8")


def _flow_target(calls: list[str]) -> Callable[..., Any]:
    @flow
    def i5_flow(out: OutputContext) -> None:
        _mark(out.invoice, out.struct, calls, "flow")

    return i5_flow


def _callback_target(calls: list[str], mode: str) -> Callable[..., Any]:
    if mode in _UNIFIED_SIGNATURE_MODES:

        def unified_callback(paths: RdeDatasetPaths) -> None:
            assert isinstance(paths, RdeDatasetPaths)
            _mark(paths.output_paths.invoice, paths.output_paths.struct, calls, "callback")

        return unified_callback

    def legacy_callback(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
        assert isinstance(srcpaths, RdeInputDirPaths)
        assert isinstance(resource_paths, RdeOutputResourcePath)
        _mark(resource_paths.invoice, resource_paths.struct, calls, "callback")

    return legacy_callback


def _execute(root: Path, mode: str, entry: str, calls: list[str]) -> RunReport:
    runner = _runner(root, calls)
    overrides = _overrides(mode)
    if entry == "flow":
        return runner.run(_flow_target(calls), **overrides)
    request = RunRequest(
        root=root,
        target=LegacyCallbackTarget(function=_callback_target(calls, mode)),
        config_source=overrides or None,
    )
    return runner.run(request)


@pytest.mark.parametrize("entry", ["flow", "callback"])
@pytest.mark.parametrize("mode", _MODES)
def test_entry_points_share_one_runner_lifecycle__tc_ep_i5_201_202_203(
    tmp_path: Path,
    mode: str,
    entry: str,
) -> None:
    """TC-EP-I5-201/202/203: ten success cases traverse the same ordered lifecycle."""
    # Given: a materialized real input family for the mode
    _generate.materialize_sut_case(mode, tmp_path)
    calls: list[str] = []

    # When: running the mode through this entry point
    report = _execute(tmp_path, mode, entry, calls)

    # Then: the run succeeded through the registered mode handler, producing
    # exactly the tile count v1 produced for this mode's frozen OK observation
    expected_tiles = _oracle_tile_count(mode)
    assert handler_for(ModeKind(mode)) is not None
    assert report.status == "success", report.error
    assert report.mode == mode
    assert len(report.iterations) == expected_tiles
    assert [iteration["status"] for iteration in report.iterations] == ["completed"] * expected_tiles

    # Then: every lifecycle step ran in Design order, invoking once per tile
    assert calls == [
        "load_config",
        "resolve_mode",
        "pre_validate",
        "iterate",
        *["invoke"] * expected_tiles,
        "post_validate",
        "finalize",
    ]

    # Then: each tile received real, writable output directories
    for iteration in report.iterations:
        struct_dir = resolve_tile_paths(tmp_path / "data", int(iteration["index"])).struct
        assert (struct_dir / _MARKER).exists()


def test_callback_entry_without_a_function_succeeds__tc_bv_i5_201(tmp_path: Path) -> None:
    """TC-BV-I5-201: the v1 callback-free run is still a complete Runner run."""
    # Given: a materialized invoice case and a callback target without a function
    _generate.materialize_sut_case("invoice", tmp_path)
    calls: list[str] = []
    request = RunRequest(root=tmp_path, target=LegacyCallbackTarget(function=None))

    # When: running the callback entry point with nothing to call
    report = _runner(tmp_path, calls).run(request)

    # Then: the lifecycle completed without any user invocation
    assert report.status == "success", report.error
    assert "invoke" not in calls
    assert calls[-1] == "finalize"


def test_failing_callback_reports_failure_and_finalizes__tc_bv_i5_202(tmp_path: Path) -> None:
    """TC-BV-I5-202: callback failures use the common tile failure contract."""
    # Given: a callback that always raises
    _generate.materialize_sut_case("invoice", tmp_path)
    calls: list[str] = []

    def failing_callback(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
        calls.append("invoke")
        msg = "callback exploded"
        raise RuntimeError(msg)

    request = RunRequest(root=tmp_path, target=LegacyCallbackTarget(function=failing_callback))

    # When: running the callback entry point
    report = _runner(tmp_path, calls).run(request)

    # Then: the run failed through the shared executor path and still finalized
    assert report.status == "failed"
    assert "invoke" in calls
    assert calls[-1] == "finalize"
    assert (tmp_path / "data" / "job.failed").exists()


def test_mode_override_warning_survives_handler_installation__tc_ep_i5_301(
    tmp_path: Path,
) -> None:
    """TC-EP-I5-301 (I5.3): W1001 still fires once mode handlers are installed."""
    # Given: an explicit MultiDataTile config contradicted by a SmartTable input
    inputdata = tmp_path / "data" / "inputdata"
    unpacked = tmp_path / "data" / "unpacked"
    for directory in (inputdata, unpacked):
        directory.mkdir(parents=True, exist_ok=True)
    (inputdata / "smarttable_measurements.xlsx").touch()
    sink = MemoryEventSink()
    sink.open("i5-w1001")
    runner = Runner(
        root=tmp_path,
        inputdata_path=inputdata,
        unpacked_dir_path=unpacked,
        event_sink=sink,
        run_id_factory=lambda: "i5-w1001",
    )
    runner.run_id = "i5-w1001"

    # When: resolving the mode with every walking-skeleton handler installed
    resolved = runner.resolve_mode(RdeConfig(system=V2SystemSettings(extended_mode="MultiDataTile")))

    # Then: file detection still wins and still warns with catalogued W1001
    assert handler_for(ModeKind.smarttable) is not None
    assert resolved is ModeKind.smarttable
    codes = [event.payload.get("code") for event in sink.events if event.name == "warning"]
    assert 1001 in codes
