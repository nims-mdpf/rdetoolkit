"""Minimal v1 callback invoker (Session I5.1b, merge_v1 Design §7).

The invoker only converts arguments and calls; provenance semantics for the
callback entry point stay with Session I8. The signature-dispatch rules are a
port of v1 ``processing/processors/datasets.py`` (DatasetRunner), which is the
behavioral oracle for every case below.

Equivalence partitions (EP):

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``accepts_unified_argument`` | one positional parameter | ``True`` | TC-EP-I5-101 |
| ``accepts_unified_argument`` | two positional parameters | ``False`` | TC-EP-I5-102 |
| ``accepts_unified_argument`` | ``*args`` / zero parameters | ``None`` (ambiguous) | TC-EP-I5-103 |
| ``LegacyCallbackInvoker.invoke`` | unified callback | receives ``RdeDatasetPaths`` | TC-EP-I5-104 |
| ``LegacyCallbackInvoker.invoke`` | legacy two-argument callback | receives the v1 pair | TC-EP-I5-105 |
| ``LegacyCallbackInvoker.invoke`` | ambiguous callback | unified attempted first | TC-EP-I5-106 |
| ``LegacyCallbackInvoker.invoke`` | ambiguous + arity ``TypeError`` | legacy fallback | TC-EP-I5-107 |
| ``LegacyCallbackInvoker.invoke`` | callback raising a domain ``TypeError`` | propagates unchanged | TC-EP-I5-108 |
| ``LegacyCallbackInvoker.invoke`` | ``FlowTarget`` | rejected | TC-EP-I5-109 |
| ``to_legacy_dataset_paths`` | complete run context | v1 field mapping | TC-EP-I5-110 |
| ``to_legacy_dataset_paths`` | ``on_iteration_error='continue'`` | v1 ``ignore_errors=True`` | TC-EP-I5-111 |

Boundary values (BV):

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| ``LegacyCallbackInvoker.invoke`` | ``function=None`` | completed result, nothing called | TC-BV-I5-101 |
| ``to_legacy_dataset_paths`` | ``data/temp/invoice_org.json`` present | backup wins as ``invoice_org`` | TC-BV-I5-102 |
| ``to_legacy_dataset_paths`` | v2 ``extended_mode='invoice'`` | v1 ``extended_mode=None`` | TC-BV-I5-103 |
| ``to_legacy_dataset_paths`` | context without paths or out | ``ValueError`` | TC-BV-I5-104 |
| ``LegacyCallbackInvoker.invoke`` | context without iteration | ``ValueError`` | TC-BV-I5-105 |
| ``to_legacy_dataset_paths`` | context without config | v1 default ``Config`` | TC-BV-I5-106 |
| ``LegacyCallbackInvoker.invoke`` | tile without raw files | index-based datatile id | TC-BV-I5-107 |
| ``accepts_unified_argument`` | un-introspectable value | ``None`` (ambiguous) | TC-BV-I5-108 |
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.api.request import FlowTarget, LegacyCallbackTarget
from rdetoolkit.compat.v1.callback import (
    LegacyCallbackInvoker,
    accepts_unified_argument,
    to_legacy_dataset_paths,
)
from rdetoolkit.core.context import RunContext
from rdetoolkit.models.rde2types import RdeDatasetPaths, RdeInputDirPaths, RdeOutputResourcePath
from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.runner.paths import resolve_tile_paths
from rdetoolkit.runner.planner import TileMaterial
from rdetoolkit.types import (
    InputPaths,
    IterationInfo,
    OutputContext,
    RdeConfig,
    V2ExecutionSettings,
    V2SystemSettings,
)


def _context(tmp_path: Path, *, config: RdeConfig | None = None) -> RunContext:
    data_root = tmp_path / "data"
    rawfile = data_root / "inputdata" / "sample.txt"
    rawfile.parent.mkdir(parents=True, exist_ok=True)
    rawfile.write_text("raw\n", encoding="utf-8")
    return RunContext(
        paths=InputPaths(
            inputdata=data_root / "inputdata",
            invoice=data_root / "invoice",
            tasksupport=data_root / "tasksupport",
            raw=rawfile,
            rawfiles=(rawfile,),
        ),
        out=OutputContext.from_resource_paths(resolve_tile_paths(data_root, 0)),
        config=config or RdeConfig(),
        iteration=IterationInfo(index=0, total=1, mode="invoice"),
    )


def _material(context: RunContext, *, invoice_source: Path | None = None) -> TileMaterial:
    """Build the run-owned material the Runner hands to this invoker.

    The default is the plan's invoice-mode decision (ruling #3): the adapter
    never probes the filesystem for a backup of its own.
    """
    assert context.paths is not None
    default = context.paths.invoice / "invoice.json"
    return TileMaterial(invoice_source=invoice_source or default)


def _invoke(target: LegacyCallbackTarget | FlowTarget, context: RunContext) -> Any:
    return LegacyCallbackInvoker().invoke(
        target,
        context,
        event_sink=MemoryEventSink(),
        run_id="i5-run",
        config=context.config or RdeConfig(),
        material=_material(context) if context.paths is not None else TileMaterial(invoice_source=Path()),
    )


def _unified(paths: RdeDatasetPaths) -> None:
    return None


def _legacy(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    return None


def test_single_positional_parameter_is_unified__tc_ep_i5_101() -> None:
    """TC-EP-I5-101: one positional parameter means the unified signature."""
    # Given / When: inspecting a single-argument callback
    actual = accepts_unified_argument(_unified)

    # Then: the unified argument style is selected
    assert actual is True


def test_two_positional_parameters_are_legacy__tc_ep_i5_102() -> None:
    """TC-EP-I5-102: two positional parameters mean the v1 pair signature."""
    # Given / When: inspecting a two-argument callback
    actual = accepts_unified_argument(_legacy)

    # Then: the legacy argument style is selected
    assert actual is False


@pytest.mark.parametrize(
    "callback",
    [
        pytest.param(lambda *args: None, id="var-positional"),
        pytest.param(lambda: None, id="zero-parameters"),
        pytest.param(lambda *, only_kw=None: None, id="keyword-only"),
    ],
)
def test_undecidable_signatures_are_ambiguous__tc_ep_i5_103(callback: Any) -> None:
    """TC-EP-I5-103: v1 defers the decision instead of guessing (DatasetRunner)."""
    # Given / When: inspecting a callback whose arity is not decidable
    actual = accepts_unified_argument(callback)

    # Then: ambiguity is explicit so the caller can try-then-fall-back
    assert actual is None


def test_unified_callback_receives_dataset_paths__tc_ep_i5_104(tmp_path: Path) -> None:
    """TC-EP-I5-104: the unified callback is called with one RdeDatasetPaths."""
    # Given: a single-argument callback recording its argument
    received: list[Any] = []

    def callback(paths: RdeDatasetPaths) -> None:
        received.append(paths)

    context = _context(tmp_path)

    # When: invoking the legacy target
    result = _invoke(LegacyCallbackTarget(function=callback), context)

    # Then: exactly the v1 unified argument arrives and the tile completes
    assert len(received) == 1
    assert isinstance(received[0], RdeDatasetPaths)
    assert result.status == "completed"
    assert result.iteration_index == 0


def test_legacy_callback_receives_the_v1_pair__tc_ep_i5_105(tmp_path: Path) -> None:
    """TC-EP-I5-105: the legacy callback keeps the v1 two-argument contract."""
    # Given: a two-argument callback recording both arguments
    received: list[tuple[Any, Any]] = []

    def callback(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
        received.append((srcpaths, resource_paths))

    context = _context(tmp_path)

    # When: invoking the legacy target
    result = _invoke(LegacyCallbackTarget(function=callback), context)

    # Then: the v1 pair arrives unchanged in order and type
    assert len(received) == 1
    srcpaths, resource_paths = received[0]
    assert isinstance(srcpaths, RdeInputDirPaths)
    assert isinstance(resource_paths, RdeOutputResourcePath)
    assert result.status == "completed"


def test_ambiguous_callback_tries_unified_first__tc_ep_i5_106(tmp_path: Path) -> None:
    """TC-EP-I5-106: v1 attempts the unified call before the legacy pair."""
    # Given: a *args callback that accepts anything
    received: list[tuple[Any, ...]] = []

    def callback(*args: Any) -> None:
        received.append(args)

    # When: invoking the ambiguous target
    _invoke(LegacyCallbackTarget(function=callback), _context(tmp_path))

    # Then: exactly one unified argument was passed
    assert len(received) == 1
    assert len(received[0]) == 1
    assert isinstance(received[0][0], RdeDatasetPaths)


def test_ambiguous_callback_falls_back_on_arity_error__tc_ep_i5_107(tmp_path: Path) -> None:
    """TC-EP-I5-107: an arity TypeError retries with the legacy pair (v1 guard)."""
    # Given: a *args callback that rejects the unified arity exactly once
    received: list[tuple[Any, ...]] = []

    def callback(*args: Any) -> None:
        if len(args) == 1:
            msg = "callback() missing 1 required positional argument: 'resource_paths'"
            raise TypeError(msg)
        received.append(args)

    # When: invoking the ambiguous target
    _invoke(LegacyCallbackTarget(function=callback), _context(tmp_path))

    # Then: the guarded fallback delivered the two legacy arguments
    assert len(received) == 1
    assert len(received[0]) == 2
    assert isinstance(received[0][0], RdeInputDirPaths)
    assert isinstance(received[0][1], RdeOutputResourcePath)


def test_domain_type_error_is_not_retried__tc_ep_i5_108(tmp_path: Path) -> None:
    """TC-EP-I5-108: a user TypeError must not be masked by an arity retry."""
    # Given: a *args callback raising an unrelated TypeError
    calls: list[int] = []

    def callback(*args: Any) -> None:
        calls.append(len(args))
        msg = "unsupported operand type(s) for +: 'int' and 'str'"
        raise TypeError(msg)

    # When / Then: the original failure propagates after a single attempt
    with pytest.raises(TypeError, match="unsupported operand"):
        _invoke(LegacyCallbackTarget(function=callback), _context(tmp_path))
    assert calls == [1]


def test_flow_target_is_rejected__tc_ep_i5_109(tmp_path: Path) -> None:
    """TC-EP-I5-109: the compat invoker never executes a v2 flow target."""
    # Given: a flow target at the legacy-callback invoker boundary
    target = FlowTarget(function=lambda: None)

    # When / Then: the unsupported target is rejected before execution
    with pytest.raises(TypeError, match="LegacyCallbackTarget"):
        _invoke(target, _context(tmp_path))


def test_absent_callback_completes_without_invocation__tc_bv_i5_101(tmp_path: Path) -> None:
    """TC-BV-I5-101: a callback-free v1 run is a completed, empty tile."""
    # Given: the v1 "no custom_dataset_function" boundary
    target = LegacyCallbackTarget(function=None)

    # When: invoking it for one tile
    result = _invoke(target, _context(tmp_path))

    # Then: the tile completes with no call log and no outputs (provenance is I8)
    assert result.status == "completed"
    assert result.call_records == ()
    assert result.outputs == ()
    assert result.datatile_id == "sample"


def test_legacy_paths_map_v2_material__tc_ep_i5_110(tmp_path: Path) -> None:
    """TC-EP-I5-110: every v1 path field is derived from the tile's own material."""
    # Given: a complete tile context
    context = _context(tmp_path)
    assert context.paths is not None
    assert context.out is not None

    # When: converting to the v1 dataset paths
    legacy = to_legacy_dataset_paths(context, material=_material(context))

    # Then: input, output, and tile-scoped file paths match the v2 material
    assert legacy.input_paths.inputdata == context.paths.inputdata
    assert legacy.input_paths.invoice == context.paths.invoice
    assert legacy.input_paths.tasksupport == context.paths.tasksupport
    assert legacy.output_paths.rawfiles == context.paths.rawfiles
    assert legacy.output_paths.struct == context.out.struct
    assert legacy.output_paths.meta == context.out.meta
    assert legacy.output_paths.main_image == context.out.main_image
    assert legacy.output_paths.other_image == context.out.other_image
    assert legacy.output_paths.thumbnail == context.out.thumbnail
    assert legacy.output_paths.logs == context.out.logs
    assert legacy.output_paths.raw == context.out.raw
    assert legacy.output_paths.nonshared_raw == context.out.nonshared_raw
    assert legacy.output_paths.invoice == context.out.invoice
    assert legacy.output_paths.attachment == context.out.attachment
    assert legacy.output_paths.invoice_schema_json == context.paths.tasksupport / "invoice.schema.json"
    assert legacy.output_paths.invoice_org == context.paths.invoice / "invoice.json"


def test_planned_invoice_source_is_the_v1_invoice_org__tc_bv_i5_102(tmp_path: Path) -> None:
    """TC-BV-I5-102 (UPDATED, ruling #3): the plan decides ``invoice_org``.

    The previous expectation was that an existing ``data/temp/invoice_org.json``
    *wins*. That presence rule is exactly review R2's defect: a backup left
    behind by an earlier run silently became this run's source. v1 decides from
    the mode, so the planner's answer travels on the tile material and a
    leftover file on disk changes nothing.
    """
    # Given: a run whose planner selected the backup, plus an unrelated leftover
    context = _context(tmp_path)
    backup = tmp_path / "data" / "temp" / "invoice_org.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text("{}", encoding="utf-8")

    # When: converting with a plan that chose the original invoice
    legacy = to_legacy_dataset_paths(context, material=_material(context))

    # Then: the leftover backup is ignored, because nothing re-decides here
    assert legacy.output_paths.invoice_org == context.paths.invoice / "invoice.json"

    # And: a plan that chose the backup gets the backup
    planned = to_legacy_dataset_paths(context, material=_material(context, invoice_source=backup))
    assert planned.output_paths.invoice_org == backup


def test_v2_invoice_mode_maps_to_v1_none__tc_bv_i5_103(tmp_path: Path) -> None:
    """TC-BV-I5-103: v1 only accepts rdeformat/MultiDataTile as extended_mode."""
    # Given: the canonical v2 default mode plus a v1-invalid mode value
    default_context = _context(tmp_path / "default")
    smarttable_context = _context(
        tmp_path / "smarttable",
        config=RdeConfig(system=V2SystemSettings(extended_mode="smarttable")),
    )

    # When: converting both contexts
    default_legacy = to_legacy_dataset_paths(default_context, material=_material(default_context))
    smarttable_legacy = to_legacy_dataset_paths(smarttable_context, material=_material(smarttable_context))

    # Then: neither projection can violate the v1 Config validator
    assert default_legacy.input_paths.config.system.extended_mode is None
    assert smarttable_legacy.input_paths.config.system.extended_mode is None


def test_continue_policy_maps_to_v1_ignore_errors__tc_ep_i5_111(tmp_path: Path) -> None:
    """TC-EP-I5-111: the v1 policy field is restored from the v2 error policy."""
    # Given: both canonical error policies
    continue_context = _context(
        tmp_path / "continue",
        config=RdeConfig(execution=V2ExecutionSettings(on_iteration_error="continue")),
    )
    fail_fast_context = _context(
        tmp_path / "fail-fast",
        config=RdeConfig(execution=V2ExecutionSettings(on_iteration_error="fail_fast")),
    )

    # When: converting both contexts
    continue_legacy = to_legacy_dataset_paths(continue_context, material=_material(continue_context))
    fail_fast_legacy = to_legacy_dataset_paths(fail_fast_context, material=_material(fail_fast_context))

    # Then: v1 ignore_errors mirrors the policy in both directions
    assert continue_legacy.input_paths.config.multidata_tile is not None
    assert continue_legacy.input_paths.config.multidata_tile.ignore_errors is True
    assert fail_fast_legacy.input_paths.config.multidata_tile is not None
    assert fail_fast_legacy.input_paths.config.multidata_tile.ignore_errors is False


@pytest.mark.parametrize(
    "context",
    [
        pytest.param(RunContext(iteration=IterationInfo(index=0, total=1, mode="invoice")), id="no-paths"),
        pytest.param(RunContext(), id="empty"),
    ],
)
def test_incomplete_context_is_rejected__tc_bv_i5_104(context: RunContext) -> None:
    """TC-BV-I5-104: v1 arguments cannot be fabricated from a partial context."""
    # Given / When / Then: conversion refuses to invent paths
    with pytest.raises(ValueError, match="RunContext"):
        to_legacy_dataset_paths(context, material=TileMaterial(invoice_source=Path()))


def test_missing_iteration_is_rejected__tc_bv_i5_105(tmp_path: Path) -> None:
    """TC-BV-I5-105: a tile without iteration information cannot be executed."""
    # Given: a tile context that lost its iteration information
    context = _context(tmp_path)
    context.iteration = None

    # When / Then: the invoker refuses to execute an unidentifiable tile
    with pytest.raises(ValueError, match="RunContext.iteration"):
        _invoke(LegacyCallbackTarget(function=lambda paths: None), context)


def test_absent_config_projects_v1_defaults__tc_bv_i5_106(tmp_path: Path) -> None:
    """TC-BV-I5-106: a context without config yields the v1 default Config."""
    # Given: a complete tile context whose config was never resolved
    context = _context(tmp_path)
    context.config = None

    # When: converting to the v1 dataset paths
    legacy = to_legacy_dataset_paths(context, material=_material(context))

    # Then: the v1 defaults apply instead of a fabricated projection
    assert legacy.input_paths.config.system.extended_mode is None
    assert legacy.input_paths.config.system.save_nonshared_raw is True


def test_tile_without_rawfiles_uses_its_index__tc_bv_i5_107(tmp_path: Path) -> None:
    """TC-BV-I5-107: the tile identifier stays deterministic without raw files."""
    # Given: a tile context that has no raw files
    context = _context(tmp_path)
    assert context.paths is not None
    context.paths = InputPaths(
        inputdata=context.paths.inputdata,
        invoice=context.paths.invoice,
        tasksupport=context.paths.tasksupport,
    )
    context.iteration = IterationInfo(index=3, total=4, mode="invoice")

    # When: invoking a callback-free target
    result = _invoke(LegacyCallbackTarget(function=None), context)

    # Then: the decimal iteration index identifies the tile
    assert result.datatile_id == "3"


def test_uninspectable_callable_is_ambiguous__tc_bv_i5_108() -> None:
    """TC-BV-I5-108: an object without a signature must not be guessed at."""
    # Given: a value whose signature cannot be introspected
    uninspectable: Any = object()

    # When / Then: ambiguity is reported instead of an exception
    assert accepts_unified_argument(uninspectable) is None
