"""Branch contracts for the Phase H target invoker and tile executor.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``FlowInvoker.invoke`` | FlowTarget | delegates exact tile arguments | TC-EP-HR-F6-101 |
| ``FlowInvoker.invoke`` | LegacyCallbackTarget | rejected; registry owns the routing | TC-EP-HR-F6-102 |
| ``TileExecutor.execute`` | RunInterrupted | propagates code 3004 | TC-EP-HR-F6-103 |
| ``TileExecutor.execute`` | successful external raw path | preserves absolute legacy target | TC-EP-HR-F6-104 |
| ``InvokerRegistry.for_target`` | injected adapters | injected instances are used as-is | TC-EP-I5-112 |
| ``InvokerRegistry.for_target`` | unsupported target type | rejected | TC-EP-I5-113 |
| ``InvokerRegistry.invoke`` | legacy callback target | dispatched to the legacy adapter | TC-EP-I5-114 |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| legacy title enrichment | invoice ``basic=None`` | deterministic datatile fallback | TC-BV-HR-F6-101 |
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from rdetoolkit.api.request import FlowTarget, LegacyCallbackTarget
from rdetoolkit.compat.v1.callback import LegacyCallbackInvoker
from rdetoolkit.core.context import RunContext
from rdetoolkit.errors import ERROR_CATALOG, RdeExecutionError
from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.runner.execute import ExecutionResult
from rdetoolkit.runner.executor import TileExecutor
from rdetoolkit.runner.invoker import FlowInvoker, InvokerRegistry
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.paths import resolve_tile_paths
from rdetoolkit.runner.planner import ExecutionPlan, TileMaterial, TilePlan
from rdetoolkit.types import InputPaths, InvoiceData, IterationInfo, OutputContext, RdeConfig


def _context() -> RunContext:
    return RunContext(iteration=IterationInfo(index=0, total=1, mode="invoice"))


def _result() -> ExecutionResult:
    return ExecutionResult(iteration_index=0, status="completed", call_records=(), outputs=())


def _tile(tmp_path: Path, *, rawfile: Path, invoice: InvoiceData | None = None) -> TilePlan:
    output_paths = resolve_tile_paths(tmp_path / "data", 0)
    return TilePlan(
        iteration=IterationInfo(index=0, total=1, mode="invoice"),
        paths=InputPaths(
            inputdata=rawfile.parent,
            invoice=tmp_path / "invoice",
            tasksupport=tmp_path / "tasksupport",
            raw=rawfile,
            rawfiles=(rawfile,),
        ),
        out=OutputContext.from_resource_paths(output_paths),
        invoice=invoice,
    )


def _plan(tmp_path: Path, tile: TilePlan) -> ExecutionPlan:
    return ExecutionPlan(
        run_id="branch-run",
        target=FlowTarget(function=lambda: None),
        mode=ModeKind.invoice,
        config=RdeConfig(),
        root=tmp_path,
        data_root=tmp_path,
        invoice_source=tmp_path / "data" / "invoice" / "invoice.json",
        error_policy="continue",
        tiles=(tile,),
    )


def test_flow_invoker_delegates_exact_arguments__tc_ep_hr_f6_101(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-EP-HR-F6-101: the flow adapter owns no alternate execution path."""
    # Given: a FlowTarget and a patched eager tile core
    function = lambda: None
    target = FlowTarget(function=function)
    context = _context()
    sink = MemoryEventSink()
    config = RdeConfig()
    expected = _result()
    run_tile = MagicMock(return_value=expected)
    monkeypatch.setattr("rdetoolkit.runner.invoker.run_tile", run_tile)

    # When: invoking the normalized flow target
    material = TileMaterial(invoice_source=Path("invoice.json"))
    actual = FlowInvoker().invoke(target, context, event_sink=sink, run_id="run", config=config, material=material)

    # Then: arguments are delegated exactly and iteration events remain Runner-owned
    assert actual is expected
    run_tile.assert_called_once_with(
        function,
        context,
        event_sink=sink,
        run_id="run",
        config=config,
        emit_iteration_events=False,
    )


def test_flow_invoker_rejects_non_flow_target__tc_ep_hr_f6_102() -> None:
    """TC-EP-HR-F6-102: the flow adapter never silently invokes a legacy callback."""
    # Given: a callback target at the flow-only invoker boundary
    target = LegacyCallbackTarget(function=lambda: None)

    # When / Then: the unsupported target is rejected before execution
    with pytest.raises(TypeError, match="FlowInvoker requires a FlowTarget"):
        FlowInvoker().invoke(
            target,
            _context(),
            event_sink=MemoryEventSink(),
            run_id="run",
            config=RdeConfig(),
            material=TileMaterial(invoice_source=Path("invoice.json")),
        )

    # Then: routing that target is the registry's job, not the flow adapter's
    assert isinstance(InvokerRegistry().for_target(target), LegacyCallbackInvoker)


def test_registry_uses_injected_adapters__tc_ep_i5_112() -> None:
    """TC-EP-I5-112: both adapters are replaceable for alternate hosts."""
    # Given: a registry built from two injected adapters
    flow_invoker = MagicMock()
    legacy_invoker = MagicMock()
    registry = InvokerRegistry(flow_invoker=flow_invoker, legacy_invoker=legacy_invoker)

    # When / Then: each target type resolves to its injected adapter
    assert registry.for_target(FlowTarget(function=lambda: None)) is flow_invoker
    assert registry.for_target(LegacyCallbackTarget(function=None)) is legacy_invoker


def test_registry_rejects_unknown_target__tc_ep_i5_113() -> None:
    """TC-EP-I5-113: only normalized execution targets can be routed."""
    # Given: an object that is not an execution target
    target: Any = object()

    # When / Then: the registry refuses to guess an adapter
    with pytest.raises(TypeError, match="Unsupported execution target"):
        InvokerRegistry().for_target(target)


def test_registry_dispatches_legacy_target__tc_ep_i5_114() -> None:
    """TC-EP-I5-114: dispatch forwards the exact tile arguments once."""
    # Given: a registry whose legacy adapter is observable
    legacy_invoker = MagicMock()
    legacy_invoker.invoke.return_value = _result()
    registry = InvokerRegistry(legacy_invoker=legacy_invoker)
    target = LegacyCallbackTarget(function=None)
    context = _context()
    sink = MemoryEventSink()
    config = RdeConfig()
    material = TileMaterial(invoice_source=Path("invoice.json"))

    # When: invoking through the registry
    actual = registry.invoke(
        target,
        context,
        event_sink=sink,
        run_id="run",
        config=config,
        material=material,
    )

    # Then: the legacy adapter received the arguments unchanged
    assert actual.status == "completed"
    legacy_invoker.invoke.assert_called_once_with(
        target,
        context,
        event_sink=sink,
        run_id="run",
        config=config,
        material=material,
    )


def test_tile_executor_propagates_run_interrupted__tc_ep_hr_f6_103(tmp_path: Path) -> None:
    """TC-EP-HR-F6-103: cancellation is not normalized into a tile failure."""
    # Given: an invoker that raises the catalogued external interruption
    error_def = ERROR_CATALOG[3004]
    interrupted = RdeExecutionError(code=3004, name=error_def.name, message=error_def.message_template)
    invoker = MagicMock()
    invoker.invoke.side_effect = interrupted
    tile = _tile(tmp_path, rawfile=tmp_path / "input.txt")

    # When / Then: the executor propagates the cancellation unchanged
    with pytest.raises(RdeExecutionError) as exc_info:
        TileExecutor(event_sink=MemoryEventSink(), flow_invoker=invoker).execute(_plan(tmp_path, tile), tile)
    assert exc_info.value is interrupted


@pytest.mark.parametrize(
    ("invoice", "expected_title"),
    [
        pytest.param(InvoiceData(raw={"basic": {"dataName": "invoice-title"}}), "invoice-title", id="title"),
        pytest.param(InvoiceData(raw={"basic": None}), "external", id="fallback"),
    ],
)
def test_tile_executor_enriches_external_target__tc_ep_hr_f6_104_bv_101(
    tmp_path: Path,
    invoice: InvoiceData,
    expected_title: str,
) -> None:
    """TC-EP/BV-HR-F6-104/101: metadata enrichment is total outside root."""
    # Given: a successful result whose raw file lives outside the plan root
    external = tmp_path.parent / "external.txt"
    tile = _tile(tmp_path, rawfile=external, invoice=invoice)
    invoker = MagicMock()
    invoker.invoke.return_value = ExecutionResult(
        iteration_index=0,
        status="completed",
        call_records=(),
        outputs=(),
        datatile_id="external",
    )

    # When: executing and enriching the primary result
    result = TileExecutor(event_sink=MemoryEventSink(), flow_invoker=invoker).execute(_plan(tmp_path, tile), tile)

    # Then: title is total and a non-relative target remains absolute
    assert result.title == expected_title
    assert result.target == external.parent.as_posix()
