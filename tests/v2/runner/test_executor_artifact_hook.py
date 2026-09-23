"""Optional per-tile artifact hook contracts for Phase I0.

Equivalence partitions (EP):

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``TileExecutor.execute`` | completed tile + injected services | invokes both services once per tile | TC-EP-I0-101 |
| ``TileExecutor.execute`` | failed result | copies raw (v1 order), publishes no image | TC-EP-I0-102 |
| ``TileExecutor.execute`` | raised tile failure | copies raw (v1 order), publishes no image | TC-EP-I0-103 |

Boundary values (BV):

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| ``TileExecutor`` | no services injected | preserves current completed result | TC-BV-I0-101 |
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rdetoolkit.api.request import FlowTarget
from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.runner.execute import ExecutionResult, TileExecutionError
from rdetoolkit.runner.executor import TileExecutor
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.paths import resolve_tile_paths
from rdetoolkit.runner.planner import ExecutionPlan, TilePlan
from rdetoolkit.types import InputPaths, IterationInfo, OutputContext, RdeConfig


class _Invoker:
    """Return or raise fixed outcomes in call order."""

    def __init__(self, *outcomes: ExecutionResult | Exception) -> None:
        self._outcomes = iter(outcomes)

    def invoke(self, *args: object, **kwargs: object) -> ExecutionResult:
        outcome = next(self._outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _RawArtifactProbe:
    """Record raw-artifact service calls without filesystem writes."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def copy(
        self,
        source_files: tuple[Path, ...],
        *,
        raw_dir: Path,
        nonshared_raw_dir: Path,
        config: RdeConfig,
        smarttable: bool = False,
        data_root: Path,
    ) -> None:
        self.calls.append(
            {
                "source_files": source_files,
                "raw_dir": raw_dir,
                "nonshared_raw_dir": nonshared_raw_dir,
                "config": config,
                "smarttable": smarttable,
                "data_root": data_root,
            },
        )


class _ImageArtifactProbe:
    """Record image-artifact service calls without filesystem writes."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate(
        self,
        *,
        main_image_dir: Path,
        thumbnail_dir: Path,
        config: RdeConfig,
    ) -> None:
        self.calls.append(
            {
                "main_image_dir": main_image_dir,
                "thumbnail_dir": thumbnail_dir,
                "config": config,
            },
        )


def _tile(tmp_path: Path, index: int) -> TilePlan:
    rawfile = tmp_path / "inputdata" / f"sample-{index}.txt"
    output_paths = resolve_tile_paths(tmp_path / "data", index)
    return TilePlan(
        iteration=IterationInfo(index=index, total=2, mode="invoice"),
        paths=InputPaths(
            inputdata=rawfile.parent,
            invoice=tmp_path / "invoice",
            tasksupport=tmp_path / "tasksupport",
            raw=rawfile,
            rawfiles=(rawfile,),
        ),
        out=OutputContext.from_resource_paths(output_paths),
        invoice=None,
    )


def _plan(tmp_path: Path, tiles: tuple[TilePlan, ...]) -> ExecutionPlan:
    return ExecutionPlan(
        run_id="i0-artifacts",
        target=FlowTarget(function=lambda: None),
        mode=ModeKind.invoice,
        config=RdeConfig(),
        root=tmp_path,
        data_root=tmp_path,
        invoice_source=tmp_path / "data" / "invoice" / "invoice.json",
        error_policy="continue",
        tiles=tiles,
    )


def _result(index: int, status: str = "completed") -> ExecutionResult:
    return ExecutionResult(  # type: ignore[arg-type]
        iteration_index=index,
        status=status,
        call_records=(),
        outputs=(),
    )


def test_completed_tiles_invoke_each_artifact_service__tc_ep_i0_101(tmp_path: Path) -> None:
    """TC-EP-I0-101: injected artifact services run once after every completed tile."""
    # Given: two tiles, completed outcomes, and injected artifact probes
    tiles = (_tile(tmp_path, 0), _tile(tmp_path, 1))
    plan = _plan(tmp_path, tiles)
    raw_service = _RawArtifactProbe()
    image_service = _ImageArtifactProbe()
    executor = TileExecutor(
        event_sink=MemoryEventSink(),
        flow_invoker=_Invoker(_result(0), _result(1)),  # type: ignore[arg-type]
        raw_artifact_service=raw_service,  # type: ignore[arg-type]
        image_artifact_service=image_service,  # type: ignore[arg-type]
    )

    # When: executing both completed tiles
    results = tuple(executor.execute(plan, tile) for tile in tiles)

    # Then: both services receive each tile's exact artifact paths once
    assert [result.status for result in results] == ["completed", "completed"]
    assert [call["source_files"] for call in raw_service.calls] == [
        tiles[0].paths.rawfiles,
        tiles[1].paths.rawfiles,
    ]
    assert [call["raw_dir"] for call in raw_service.calls] == [tiles[0].out.raw, tiles[1].out.raw]
    assert [call["main_image_dir"] for call in image_service.calls] == [
        tiles[0].out.main_image,
        tiles[1].out.main_image,
    ]
    assert all(call["config"] is plan.config for call in (*raw_service.calls, *image_service.calls))


def test_failed_result_keeps_raw_and_skips_images__tc_ep_i0_102(tmp_path: Path) -> None:
    """TC-EP-I0-102: a failed tile still has its raw inputs copied, as v1 does.

    Updated in Session I6-1: every v1 pipeline runs its FileCopier *before*
    DatasetRunner (``processing/factories.py``), so a tile that fails keeps the
    raw copies v1 would have made. Only the post-invoke services are skipped.
    """
    # Given: one tile whose invoker returns a failed primary result
    tile = _tile(tmp_path, 0)
    plan = _plan(tmp_path, (tile,))
    raw_service = _RawArtifactProbe()
    image_service = _ImageArtifactProbe()
    executor = TileExecutor(
        event_sink=MemoryEventSink(),
        flow_invoker=_Invoker(_result(0, "failed")),  # type: ignore[arg-type]
        raw_artifact_service=raw_service,  # type: ignore[arg-type]
        image_artifact_service=image_service,  # type: ignore[arg-type]
    )

    # When: executing the failed tile
    result = executor.execute(plan, tile)

    # Then: failure remains primary, raw is published, images are not
    assert result.status == "failed"
    assert len(raw_service.calls) == 1
    assert image_service.calls == []


def test_raised_tile_failure_keeps_raw_and_skips_images__tc_ep_i0_103(tmp_path: Path) -> None:
    """TC-EP-I0-103: a raised tile failure keeps the pre-invoke raw copy only.

    Updated in Session I6-1 for the same v1 ordering reason as TC-EP-I0-102.
    """
    # Given: one tile whose invoker raises its failed recorder snapshot
    tile = _tile(tmp_path, 0)
    plan = _plan(tmp_path, (tile,))
    failed = _result(0, "failed")
    error = TileExecutionError(failed, ValueError("flow failed"))
    raw_service = _RawArtifactProbe()
    image_service = _ImageArtifactProbe()
    executor = TileExecutor(
        event_sink=MemoryEventSink(),
        flow_invoker=_Invoker(error),  # type: ignore[arg-type]
        raw_artifact_service=raw_service,  # type: ignore[arg-type]
        image_artifact_service=image_service,  # type: ignore[arg-type]
    )

    # When: executing the tile through the normalization boundary
    result = executor.execute(plan, tile)

    # Then: the failed result is returned with raw published and images not
    assert result.status == "failed"
    assert len(raw_service.calls) == 1
    assert image_service.calls == []


def test_no_injected_services_preserves_completed_result__tc_bv_i0_101(tmp_path: Path) -> None:
    """TC-BV-I0-101: the default-off seam preserves existing executor behavior."""
    # Given: a completed tile and no artifact services
    tile = _tile(tmp_path, 0)
    expected = _result(0)
    executor = TileExecutor(
        event_sink=MemoryEventSink(),
        flow_invoker=_Invoker(expected),  # type: ignore[arg-type]
    )

    # When: executing through the default constructor path
    actual = executor.execute(_plan(tmp_path, (tile,)), tile)

    # Then: completion is returned without requiring artifact configuration
    assert actual.status == "completed"
    assert actual.iteration_index == expected.iteration_index
