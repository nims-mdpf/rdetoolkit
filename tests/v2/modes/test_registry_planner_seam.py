"""Mode registry and planner delegation contracts for Phase I0.

Equivalence partitions (EP):

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``register`` / ``handler_for`` | registered mode | returns the exact handler | TC-EP-I0-001 |
| ``RunPlanner.create`` | registered handler | delegates tile material creation | TC-EP-I0-002 |
| ``RunPlanner.create`` | unregistered mode | retains the legacy fallback | TC-EP-I0-003 |

Boundary values (BV):

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| ``handler_for`` | empty registry | returns ``None`` | TC-BV-I0-001 |
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.api.request import FlowTarget, RunRequest
from rdetoolkit.modes import ModeHandler, PlanningContext, handler_for, register
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.paths import resolve_tile_paths
from rdetoolkit.runner.planner import RunPlanner, TilePlan
from rdetoolkit.types import InputPaths, IterationInfo, OutputContext, RdeConfig


class _InvoiceServiceProbe:
    """Keep planner tests independent from filesystem invoice preparation."""

    def begin_run(self, data_root: Path) -> None:
        self.data_root = data_root

    def invariant_invoice(self, mode: ModeKind, *, data_root: Path) -> None:
        return None

    def backup(self, mode: ModeKind, **kwargs: Any) -> Path:
        return Path(kwargs["data_root"]) / "invoice" / "invoice.json"

    def prepare_tile(self, mode: ModeKind, **kwargs: Any) -> None:
        return None


class _FakeHandler:
    """Return fixed tile plans and record the planning boundary."""

    kind = ModeKind.invoice

    def __init__(self, tiles: tuple[TilePlan, ...]) -> None:
        self.tiles = tiles
        self.contexts: list[PlanningContext] = []

    def create_tiles(self, context: PlanningContext) -> Iterable[TilePlan]:
        self.contexts.append(context)
        return self.tiles


def _tile(tmp_path: Path) -> TilePlan:
    rawfile = tmp_path / "inputdata" / "sample.txt"
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
        invoice=None,
    )


def _planner(tmp_path: Path) -> RunPlanner:
    return RunPlanner(
        inputdata_path=tmp_path / "inputdata",
        unpacked_dir_path=tmp_path / "temp",
        run_id_factory=lambda: "i0-run",
        invoice_service=_InvoiceServiceProbe(),  # type: ignore[arg-type]
    )


def _request(tmp_path: Path) -> RunRequest:
    return RunRequest(root=tmp_path, target=FlowTarget(function=lambda: None))


@pytest.mark.usefixtures("empty_mode_registry")
def test_registry_returns_registered_handler__tc_ep_i0_001() -> None:
    """TC-EP-I0-001: registration exposes the exact mode handler instance."""
    # Given: an isolated empty registry and one mode handler
    handler: ModeHandler = _FakeHandler(())

    # When: registering and resolving the handler by mode
    register(ModeKind.invoice, handler)

    # Then: the registry preserves the handler identity
    assert handler_for(ModeKind.invoice) is handler


@pytest.mark.usefixtures("empty_mode_registry")
def test_empty_registry_returns_none__tc_bv_i0_001() -> None:
    """TC-BV-I0-001: an unregistered mode has no handler during the I0 transition."""
    # Given: an isolated empty registry

    # When: resolving a mode before I5/I6 registrations exist
    actual = handler_for(ModeKind.invoice)

    # Then: absence is explicit so the planner can retain its fallback
    assert actual is None


@pytest.mark.usefixtures("empty_mode_registry")
def test_planner_delegates_to_registered_handler__tc_ep_i0_002(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-EP-I0-002: a registered handler owns tile material creation."""
    # Given: a registered fake handler returning one fixed tile
    expected = _tile(tmp_path)
    handler = _FakeHandler((expected,))
    register(ModeKind.invoice, handler)

    def _unexpected_fallback(*args: object, **kwargs: object) -> None:
        message = "registered modes must not enumerate through the fallback"
        raise AssertionError(message)

    monkeypatch.setattr("rdetoolkit.runner.planner.iterate_tiles", _unexpected_fallback)

    # When: creating and enumerating the execution plan
    plan = _planner(tmp_path).create(_request(tmp_path), config=RdeConfig(), mode=ModeKind.invoice, data_root=tmp_path)
    actual = tuple(plan.tiles)

    # Then: the handler supplies the tile and receives explicit planning material
    assert actual == (expected,)
    assert len(handler.contexts) == 1
    context = handler.contexts[0]
    assert context.root == tmp_path
    assert context.inputdata_path == tmp_path / "inputdata"
    assert context.unpacked_dir_path == tmp_path / "temp"
    # The Runner-resolved data root travels on the context (ruling #1).
    assert context.data_root == tmp_path


@pytest.mark.usefixtures("empty_mode_registry")
def test_planner_falls_back_when_mode_is_unregistered__tc_ep_i0_003(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-EP-I0-003: an unregistered mode retains the existing iterator path."""
    # Given: an empty registry and one tile from the existing iterator
    expected = _tile(tmp_path)
    fallback_calls: list[tuple[object, ...]] = []

    def _fallback(*args: object) -> Iterable[tuple[IterationInfo, InputPaths, OutputContext]]:
        fallback_calls.append(args)
        return ((expected.iteration, expected.paths, expected.out),)

    monkeypatch.setattr("rdetoolkit.runner.planner.iterate_tiles", _fallback)

    # When: creating and enumerating a plan before mode handlers are installed
    plan = _planner(tmp_path).create(_request(tmp_path), config=RdeConfig(), mode=ModeKind.invoice, data_root=tmp_path)
    actual = tuple(plan.tiles)

    # Then: the original iterator remains the complete fallback
    assert [tile.iteration for tile in actual] == [expected.iteration]
    assert len(fallback_calls) == 1
