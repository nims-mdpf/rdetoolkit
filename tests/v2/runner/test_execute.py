"""Tests for rdetoolkit v2 eager tile execution (TC-EXEC-001..018) — Session D1.

Written before implementation (TDD Red phase).
Target: make all tests pass in codex-worker Green phase.

Design authority: local/develop/v2/Design.md v2.1 §7.1-7.5, §4.2, §4.3, §2.2
    (steps 4b-4d)
Session authority: local/develop/v2/tasks/session_d1.md
    ("D1 implementation scope: runner/execute.py", Decisions D1-B/C/D),
    D1.9 (iteration-awareness: undeclared vs. declared IterationInfo param).

Target import (fails until implementation exists — expected in Red phase):
    from rdetoolkit.runner.execute import ExecutionResult, run_tile
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from types import SimpleNamespace

import pytest

# Target imports — fail until implementation exists (expected in Red phase):
# from rdetoolkit.runner.execute import ExecutionResult, run_tile
from rdetoolkit.core.context import RunContext
from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.runner.iterator import iterate_tiles  # noqa: F401 (used by D1.9 tests below)
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import InputPaths, InvoiceData, IterationInfo, OutputContext, RdeConfig


def _make_paths(tmp_path: Path) -> InputPaths:
    return InputPaths(
        inputdata=tmp_path / "inputdata",
        invoice=tmp_path / "invoice",
        tasksupport=tmp_path / "tasksupport",
    )


def _make_out(tmp_path: Path) -> OutputContext:
    base = tmp_path / "data"
    names = (
        "struct",
        "meta",
        "main_image",
        "other_image",
        "thumbnail",
        "attachment",
        "nonshared_raw",
        "raw",
        "invoice",
        "logs",
    )
    return OutputContext.from_resource_paths(SimpleNamespace(**{n: base / n for n in names}))


def _make_context(
    tmp_path: Path,
    *,
    config: RdeConfig | None = None,
    index: int = 0,
    total: int = 1,
    mode: str = "invoice",
) -> RunContext:
    return RunContext(
        paths=_make_paths(tmp_path),
        out=_make_out(tmp_path),
        config=config or RdeConfig(),
        invoice=None,
        iteration=IterationInfo(index=index, total=total, mode=mode),
    )


class TestExecutionResultShape:
    """ExecutionResult (Decision D1-B) is a minimal frozen dataclass."""

    def test_execution_result_has_expected_fields(self) -> None:
        """TC-EXEC-001: dataclass fields match Decision D1-B's definition."""
        from rdetoolkit.runner.execute import ExecutionResult  # noqa: PLC0415

        field_names = {f.name for f in dataclasses.fields(ExecutionResult)}
        assert field_names == {
            "iteration_index",
            "status",
            "call_records",
            "outputs",
            "error",
            "datatile_id",
            "title",
            "target",
            "stacktrace",
        }

    def test_execution_result_error_defaults_to_none(self) -> None:
        """TC-EXEC-002: error is optional with a None default."""
        from rdetoolkit.runner.execute import ExecutionResult  # noqa: PLC0415

        for f in dataclasses.fields(ExecutionResult):
            if f.name == "error":
                assert f.default is None


class TestRunTileDIWiring:
    """run_tile wires DI via core.injection.resolve_flow_kwargs before the flow call."""

    def test_iterationinfo_is_required_for_tile_execution(self, tmp_path: Path) -> None:
        """TC-EXEC-020: run_tile rejects a context with no IterationInfo."""
        from rdetoolkit.runner.execute import run_tile  # noqa: PLC0415

        ctx = RunContext(
            paths=_make_paths(tmp_path),
            out=_make_out(tmp_path),
            config=RdeConfig(),
            invoice=None,
            iteration=None,
        )

        @flow
        def _noop_flow(paths: InputPaths) -> None:
            return None

        sink = MemoryEventSink()
        sink.open("run-1")
        with pytest.raises(ValueError, match="RunContext.iteration is required"):
            run_tile(_noop_flow, ctx, event_sink=sink, run_id="run-1", config=ctx.config)

    def test_paths_out_config_are_injected_by_type_annotation(self, tmp_path: Path) -> None:
        """TC-EXEC-003: a flow declaring paths/out/config receives the exact RunContext values."""
        from rdetoolkit.runner.execute import run_tile  # noqa: PLC0415

        ctx = _make_context(tmp_path)
        received: dict[str, object] = {}

        @flow
        def _di_flow(paths: InputPaths, out: OutputContext, config: RdeConfig) -> None:
            received["paths"] = paths
            received["out"] = out
            received["config"] = config

        sink = MemoryEventSink()
        sink.open("run-1")
        run_tile(_di_flow, ctx, event_sink=sink, run_id="run-1", config=ctx.config)

        assert received["paths"] is ctx.paths
        assert received["out"] is ctx.out
        assert received["config"] is ctx.config

    def test_invoice_is_injected_as_none_without_raising__decision_d1_d(self, tmp_path: Path) -> None:
        """TC-EXEC-004 (Decision D1-D): invoice is None for every tile in D1."""
        from rdetoolkit.runner.execute import run_tile  # noqa: PLC0415

        ctx = _make_context(tmp_path)
        received: list[object] = []

        @flow
        def _invoice_flow(invoice: InvoiceData) -> None:
            received.append(invoice)

        sink = MemoryEventSink()
        sink.open("run-1")
        run_tile(_invoice_flow, ctx, event_sink=sink, run_id="run-1", config=ctx.config)

        assert received == [None]

    def test_iterationinfo_is_injected_when_declared(self, tmp_path: Path) -> None:
        """TC-EXEC-005: a flow declaring iteration: IterationInfo receives the tile's info."""
        from rdetoolkit.runner.execute import run_tile  # noqa: PLC0415

        ctx = _make_context(tmp_path, index=2, total=5, mode="multidatatile")
        received: list[IterationInfo] = []

        @flow
        def _iter_flow(iteration: IterationInfo) -> None:
            received.append(iteration)

        sink = MemoryEventSink()
        sink.open("run-1")
        run_tile(_iter_flow, ctx, event_sink=sink, run_id="run-1", config=ctx.config)

        assert received == [IterationInfo(index=2, total=5, mode="multidatatile")]


class TestRunTileEagerExecutionAndCallLog:
    """run_tile calls the flow eagerly inside a CallLogRecorder (step 4c)."""

    def test_returns_completed_execution_result(self, tmp_path: Path) -> None:
        """TC-EXEC-006: a normal flow call yields status='completed', error=None."""
        from rdetoolkit.runner.execute import ExecutionResult, run_tile  # noqa: PLC0415

        ctx = _make_context(tmp_path)

        @flow
        def _noop_flow(paths: InputPaths) -> None:
            return None

        sink = MemoryEventSink()
        sink.open("run-1")
        result = run_tile(_noop_flow, ctx, event_sink=sink, run_id="run-1", config=ctx.config)

        assert isinstance(result, ExecutionResult)
        assert result.status == "completed"
        assert result.error is None
        assert result.iteration_index == 0

    def test_node_calls_inside_the_flow_are_recorded(self, tmp_path: Path) -> None:
        """TC-EXEC-007: @node calls made during the flow call appear in call_records."""
        from rdetoolkit.runner.execute import run_tile  # noqa: PLC0415

        ctx = _make_context(tmp_path)

        @node
        def _add_one(x: int) -> int:
            return x + 1

        @flow
        def _node_flow(paths: InputPaths) -> int:
            return _add_one(1)

        sink = MemoryEventSink()
        sink.open("run-1")
        result = run_tile(_node_flow, ctx, event_sink=sink, run_id="run-1", config=ctx.config)

        assert len(result.call_records) == 1
        assert result.call_records[0].status == "completed"

    def test_call_records_are_tagged_with_the_tile_iteration_index(self, tmp_path: Path) -> None:
        """TC-EXEC-008: CallLogRecorder is constructed with the tile's iteration_index."""
        from rdetoolkit.runner.execute import run_tile  # noqa: PLC0415

        ctx = _make_context(tmp_path, index=3, total=7, mode="rdeformat")

        @node
        def _mark(x: int) -> int:
            return x

        @flow
        def _tagged_flow(paths: InputPaths) -> int:
            return _mark(1)

        sink = MemoryEventSink()
        sink.open("run-1")
        result = run_tile(_tagged_flow, ctx, event_sink=sink, run_id="run-1", config=ctx.config)

        assert result.iteration_index == 3
        assert all(record.iteration_index == 3 for record in result.call_records)

    def test_repr_head_off_config_suppresses_input_repr_capture(self, tmp_path: Path) -> None:
        """TC-EXEC-009: config.provenance.repr_head='off' propagates to CallLogRecorder."""
        from rdetoolkit.runner.execute import run_tile  # noqa: PLC0415

        config = RdeConfig(provenance={"repr_head": "off"})
        ctx = _make_context(tmp_path, config=config)

        @node
        def _echo(x: str) -> str:
            return x

        @flow
        def _repr_flow(paths: InputPaths) -> str:
            return _echo("hello")

        sink = MemoryEventSink()
        sink.open("run-1")
        result = run_tile(_repr_flow, ctx, event_sink=sink, run_id="run-1", config=config)

        assert result.call_records, "expected at least one recorded @node call"
        for record in result.call_records:
            for summary in record.inputs.values():
                assert summary.repr_head is None

    def test_repr_head_on_default_captures_input_repr(self, tmp_path: Path) -> None:
        """TC-EXEC-010: default config.provenance.repr_head='on' captures repr text."""
        from rdetoolkit.runner.execute import run_tile  # noqa: PLC0415

        ctx = _make_context(tmp_path)  # default RdeConfig() -> repr_head="on"

        @node
        def _echo(x: str) -> str:
            return x

        @flow
        def _repr_flow(paths: InputPaths) -> str:
            return _echo("hello")

        sink = MemoryEventSink()
        sink.open("run-1")
        result = run_tile(_repr_flow, ctx, event_sink=sink, run_id="run-1", config=ctx.config)

        assert result.call_records
        summary = next(iter(result.call_records[0].inputs.values()))
        assert summary.repr_head is not None
        assert "hello" in summary.repr_head

    def test_type_check_strict_propagates_mismatch_error(self, tmp_path: Path) -> None:
        """TC-EXEC-011: config.execution.type_check='strict' propagates the cataloged error."""
        from rdetoolkit.errors import RdeExecutionError  # noqa: PLC0415
        from rdetoolkit.runner.execute import run_tile  # noqa: PLC0415

        config = RdeConfig(execution={"type_check": "strict"})
        ctx = _make_context(tmp_path, config=config)

        @node
        def _typed(x: int) -> int:
            return x

        @flow
        def _mismatch_flow(paths: InputPaths) -> int:
            return _typed("not-an-int")  # type: ignore[arg-type]

        sink = MemoryEventSink()
        sink.open("run-1")
        with pytest.raises(RdeExecutionError):
            run_tile(_mismatch_flow, ctx, event_sink=sink, run_id="run-1", config=config)

    def test_type_check_off_default_allows_mismatched_types(self, tmp_path: Path) -> None:
        """TC-EXEC-012: default type_check='off' does not raise on a mismatched call."""
        from rdetoolkit.runner.execute import run_tile  # noqa: PLC0415

        ctx = _make_context(tmp_path)  # default RdeConfig() -> type_check="off"

        @node
        def _typed(x: int) -> int:
            return x

        @flow
        def _mismatch_flow(paths: InputPaths) -> int:
            return _typed("not-an-int")  # type: ignore[arg-type]

        sink = MemoryEventSink()
        sink.open("run-1")
        result = run_tile(_mismatch_flow, ctx, event_sink=sink, run_id="run-1", config=ctx.config)

        assert result.status == "completed"


class TestRunTileEventEmission:
    """Step 4d: iteration.started/iteration.completed are emitted around the flow call."""

    def test_iteration_started_then_completed_in_order(self, tmp_path: Path) -> None:
        """TC-EXEC-013: event order is exactly [iteration.started, iteration.completed]."""
        from rdetoolkit.runner.execute import run_tile  # noqa: PLC0415

        ctx = _make_context(tmp_path, index=1, total=4, mode="invoice")

        @flow
        def _noop_flow(paths: InputPaths) -> None:
            return None

        sink = MemoryEventSink()
        sink.open("run-1")
        run_tile(_noop_flow, ctx, event_sink=sink, run_id="run-1", config=ctx.config)

        names = [event.name for event in sink.events]
        assert names == ["iteration.started", "iteration.completed"]

    def test_events_carry_the_tile_iteration_index_in_payload(self, tmp_path: Path) -> None:
        """TC-EXEC-014: both events' payload["iteration_index"] equals the tile index."""
        from rdetoolkit.runner.execute import run_tile  # noqa: PLC0415

        ctx = _make_context(tmp_path, index=4, total=9, mode="smarttable")

        @flow
        def _noop_flow(paths: InputPaths) -> None:
            return None

        sink = MemoryEventSink()
        sink.open("run-1")
        run_tile(_noop_flow, ctx, event_sink=sink, run_id="run-1", config=ctx.config)

        assert sink.events[0].payload["iteration_index"] == 4
        assert sink.events[1].payload["iteration_index"] == 4
        assert sink.events[0].run_id == "run-1"


class TestExecutionResultOutputsConstruction:
    """ExecutionResult.outputs holds the flow return value's TypeSummary (Decision D1-B)."""

    class _CustomOutput:
        """Non-builtin value used to verify fully qualified type names."""

    def test_outputs_is_empty_tuple_when_flow_returns_none(self, tmp_path: Path) -> None:
        """TC-EXEC-015: a flow returning None yields outputs == ()."""
        from rdetoolkit.runner.execute import run_tile  # noqa: PLC0415

        ctx = _make_context(tmp_path)

        @flow
        def _none_flow(paths: InputPaths) -> None:
            return None

        sink = MemoryEventSink()
        sink.open("run-1")
        result = run_tile(_none_flow, ctx, event_sink=sink, run_id="run-1", config=ctx.config)

        assert result.outputs == ()

    def test_outputs_summarizes_none_inside_tuple_and_non_builtin_value(self, tmp_path: Path) -> None:
        """TC-EXEC-021: tuple elements cover None and non-builtin type summaries."""
        from rdetoolkit.runner.execute import run_tile  # noqa: PLC0415

        ctx = _make_context(tmp_path)

        @flow
        def _mixed_flow(paths: InputPaths) -> tuple[None, TestExecutionResultOutputsConstruction._CustomOutput]:
            return None, TestExecutionResultOutputsConstruction._CustomOutput()

        sink = MemoryEventSink()
        sink.open("run-1")
        result = run_tile(_mixed_flow, ctx, event_sink=sink, run_id="run-1", config=ctx.config)

        assert result.outputs[0].type_name == "None"
        assert result.outputs[1].type_name.endswith("TestExecutionResultOutputsConstruction._CustomOutput")

    def test_outputs_repr_fallback_returns_none_when_repr_raises(self, tmp_path: Path) -> None:
        """TC-EXEC-022: repr capture failure is contained in TypeSummary."""
        from rdetoolkit.runner.execute import run_tile  # noqa: PLC0415

        class BrokenRepr:
            def __repr__(self) -> str:
                msg = "repr failed"
                raise RuntimeError(msg)

        ctx = _make_context(tmp_path)

        @flow
        def _broken_repr_flow(paths: InputPaths) -> BrokenRepr:
            return BrokenRepr()

        sink = MemoryEventSink()
        sink.open("run-1")
        result = run_tile(_broken_repr_flow, ctx, event_sink=sink, run_id="run-1", config=ctx.config)

        assert result.outputs[0].type_name.endswith("BrokenRepr")
        assert result.outputs[0].repr_head is None

    def test_outputs_summarizes_a_single_scalar_return_value(self, tmp_path: Path) -> None:
        """TC-EXEC-016: a flow returning a bare int yields a single TypeSummary."""
        from rdetoolkit.runner.execute import run_tile  # noqa: PLC0415

        ctx = _make_context(tmp_path)

        @flow
        def _scalar_flow(paths: InputPaths) -> int:
            return 42

        sink = MemoryEventSink()
        sink.open("run-1")
        result = run_tile(_scalar_flow, ctx, event_sink=sink, run_id="run-1", config=ctx.config)

        assert len(result.outputs) == 1
        assert result.outputs[0].type_name == "int"

    def test_outputs_summarizes_a_tuple_return_value_element_wise(self, tmp_path: Path) -> None:
        """TC-EXEC-017: a flow returning a tuple yields one TypeSummary per element."""
        from rdetoolkit.runner.execute import run_tile  # noqa: PLC0415

        ctx = _make_context(tmp_path)

        @flow
        def _tuple_flow(paths: InputPaths) -> tuple[int, str]:
            return (1, "a")

        sink = MemoryEventSink()
        sink.open("run-1")
        result = run_tile(_tuple_flow, ctx, event_sink=sink, run_id="run-1", config=ctx.config)

        assert len(result.outputs) == 2
        assert {summary.type_name for summary in result.outputs} == {"int", "str"}


class TestIterationAwareness:
    """D1.9: flows are called once per tile whether or not they declare IterationInfo."""

    def _multidatatile_inputs(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        inputdata = tmp_path / "inputdata"
        inputdata.mkdir()
        (inputdata / "a.txt").write_text("a")
        (inputdata / "b.txt").write_text("b")
        unpacked = tmp_path / "unpacked"
        unpacked.mkdir()
        base_output = tmp_path / "data"
        return inputdata, unpacked, base_output

    def test_flow_without_iterationinfo_param_is_called_once_per_tile(self, tmp_path: Path) -> None:
        """TC-EXEC-018: an undeclared IterationInfo param still calls the flow N times."""
        from rdetoolkit.runner.execute import run_tile  # noqa: PLC0415

        inputdata, unpacked, base_output = self._multidatatile_inputs(tmp_path)
        calls: list[Path] = []

        @flow
        def _no_iter_flow(paths: InputPaths) -> None:
            calls.append(paths.inputdata)

        config = RdeConfig()
        sink = MemoryEventSink()
        sink.open("run-x")
        for info, paths, out in iterate_tiles(ModeKind.multidatatile, inputdata, unpacked, base_output):
            ctx = RunContext(paths=paths, out=out, config=config, invoice=None, iteration=info)
            run_tile(_no_iter_flow, ctx, event_sink=sink, run_id="run-x", config=config)

        assert len(calls) == 2

    def test_flow_with_iterationinfo_param_receives_correct_index_total_mode(self, tmp_path: Path) -> None:
        """TC-EXEC-019: a declared IterationInfo param carries the correct per-tile values."""
        from rdetoolkit.runner.execute import run_tile  # noqa: PLC0415

        inputdata, unpacked, base_output = self._multidatatile_inputs(tmp_path)
        received: list[IterationInfo] = []

        @flow
        def _iter_flow(iteration: IterationInfo) -> None:
            received.append(iteration)

        config = RdeConfig()
        sink = MemoryEventSink()
        sink.open("run-x")
        for info, paths, out in iterate_tiles(ModeKind.multidatatile, inputdata, unpacked, base_output):
            ctx = RunContext(paths=paths, out=out, config=config, invoice=None, iteration=info)
            run_tile(_iter_flow, ctx, event_sink=sink, run_id="run-x", config=config)

        assert [info.index for info in received] == [0, 1]
        assert all(info.total == 2 for info in received)
        assert all(info.mode == "multidatatile" for info in received)
