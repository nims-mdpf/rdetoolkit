"""Walking-skeleton mode handlers (Session I5.1): thin adapters over the planner.

The five handlers introduced in I5 are *adapters*: installing them must not
change a single planned tile. These tests prove that by planning the same
materialized input twice — once through the legacy planner fallback and once
through the registered handler — and comparing the produced ``TilePlan``
sequences attribute by attribute.

Equivalence partitions (EP):

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``RunPlanner.create`` | handler installed, 5 modes | tile sequence identical to fallback | TC-EP-I5-001 |
| ``install_default_handlers`` | fresh registry | exactly the five walking-skeleton modes | TC-EP-I5-002 |
| mode module import | module executed | no registration side effect | TC-EP-I5-003 |
| ``RunPlanner.create`` | registry cleared again | legacy fallback still owns planning | TC-EP-I5-004 |
| module import | either import order | no circular import | TC-EP-I5-005 |

Boundary values (BV):

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| ``install_default_handlers`` | called twice | idempotent, one handler per mode | TC-BV-I5-001 |
| handler ``kind`` | five registry keys | handler kind equals its registry key | TC-BV-I5-002 |
"""

from __future__ import annotations

import dataclasses
import importlib
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.api.request import FlowTarget, RunRequest
from rdetoolkit.modes import handler_for
from rdetoolkit.modes.install import install_default_handlers
from rdetoolkit.modes.registry import clear
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.planner import RunPlanner, TilePlan
from rdetoolkit.types import RdeConfig
from tests.v2.contract.fixtures import _generate

_MODES = ("invoice", "excelinvoice", "multidatatile", "rdeformat", "smarttable")
_MODE_MODULES = (
    "rdetoolkit.modes.invoice",
    "rdetoolkit.modes.excelinvoice",
    "rdetoolkit.modes.multidatatile",
    "rdetoolkit.modes.rdeformat",
    "rdetoolkit.modes.smarttable",
)


_VALUE_TYPES = (str, int, float, bool, type(None), Enum)


def _relative(value: Any, root: Path) -> Any:
    """Make one planned value root-independent so two roots stay comparable.

    Enum members (notably ``ModeKind``) are kept as-is: the mode carried by a
    tile's invoice-preparation call is exactly what must not drift between a
    handler and the fallback. Run-scoped collaborators such as
    ``InvoiceService`` are per-planner instances, so they compare by type.
    """
    if isinstance(value, Path):
        return value.relative_to(root).as_posix() if value.is_relative_to(root) else value.as_posix()
    if isinstance(value, (tuple, list)):
        return tuple(_relative(item, root) for item in value)
    if isinstance(value, dict):
        return {key: _relative(item, root) for key, item in sorted(value.items())}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return (
            type(value).__name__,
            {field.name: _relative(getattr(value, field.name), root) for field in dataclasses.fields(value)},
        )
    if isinstance(value, _VALUE_TYPES):
        return value
    return type(value).__name__


def _prepare_signature(prepare: Any, root: Path) -> Any:
    """Describe the tile's invoice-preparation callable structurally."""
    if prepare is None:
        return None
    func = getattr(prepare, "func", prepare)
    return {
        "func": f"{getattr(func, '__module__', '')}.{getattr(func, '__qualname__', repr(func))}",
        "args": _relative(tuple(getattr(prepare, "args", ())), root),
        "keywords": _relative(dict(getattr(prepare, "keywords", None) or {}), root),
    }


def _normalize(tile: TilePlan, root: Path) -> dict[str, Any]:
    """Project every TilePlan field onto comparable, root-relative values."""
    normalized = {
        field.name: _relative(getattr(tile, field.name), root)
        for field in dataclasses.fields(tile)
        if field.name != "prepare_invoice"
    }
    normalized["prepare_invoice"] = _prepare_signature(tile.prepare_invoice, root)
    return normalized


def _planned(root: Path, mode: ModeKind) -> list[dict[str, Any]]:
    """Enumerate one full plan for a materialized case."""
    planner = RunPlanner(
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "unpacked",
        run_id_factory=lambda: "i5-plan",
    )
    request = RunRequest(root=root, target=FlowTarget(function=lambda: None))
    plan = planner.create(request, config=RdeConfig(), mode=mode, data_root=root / "data")
    return [_normalize(tile, root) for tile in plan.tiles]


@pytest.mark.parametrize(
    "first",
    [
        pytest.param("rdetoolkit.modes.install", id="modes-first"),
        pytest.param("rdetoolkit.runner.lifecycle", id="runner-first"),
        pytest.param("rdetoolkit.compat.v1.callback", id="compat-first"),
    ],
)
def test_handler_modules_import_in_any_order__tc_ep_i5_005(first: str) -> None:
    """TC-EP-I5-005: no import order may create a circular import.

    The mode modules import the planner, the Runner installs the mode
    handlers, and the invoker registry reaches into compat. That is verified in
    a fresh interpreter rather than relying on whatever the current test
    session happened to import first.
    """
    # Given: a fresh interpreter that imports the given entry point first
    program = (
        f"import {first}\n"
        "from rdetoolkit.modes.install import install_default_handlers\n"
        "from rdetoolkit.runner.lifecycle import Runner\n"
        "from rdetoolkit.runner.invoker import InvokerRegistry\n"
        "install_default_handlers()\n"
        "InvokerRegistry()\n"
    )

    # When: importing and wiring both sides in that order
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        check=False,
    )

    # Then: nothing resolves against a partially initialized module
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("mode", _MODES)
@pytest.mark.usefixtures("empty_mode_registry")
def test_installed_handler_plans_the_same_tiles_as_the_fallback__tc_ep_i5_001(
    tmp_path: Path,
    mode: str,
) -> None:
    """TC-EP-I5-001: an I5 handler is thin — its tile sequence is the fallback's.

    Every ``TilePlan`` field is compared, including the ``prepare_invoice``
    callable: its target function, its bound mode, and every bound keyword
    (paths, invoice source state, iteration index) must match the fallback, so
    a handler that binds another mode's preparation cannot pass.
    """
    # Given: two identical materialized roots and an empty handler registry
    fallback_root = tmp_path / "fallback"
    handler_root = tmp_path / "handler"
    for root in (fallback_root, handler_root):
        _generate.materialize_sut_case(mode, root)
    kind = ModeKind(mode)

    # When: planning through the fallback and then through the installed handler
    fallback_tiles = _planned(fallback_root, kind)
    install_default_handlers()
    assert handler_for(kind) is not None, "install_default_handlers must register every I5 mode"
    handler_tiles = _planned(handler_root, kind)

    # Then: the handler adds nothing and drops nothing
    assert handler_tiles == fallback_tiles
    assert fallback_tiles, "the materialized case must plan at least one tile"
    assert all(tile["prepare_invoice"]["args"] == (kind,) for tile in handler_tiles)


@pytest.mark.usefixtures("empty_mode_registry")
def test_install_registers_exactly_the_five_modes__tc_ep_i5_002_bv_002() -> None:
    """TC-EP-I5-002/TC-BV-I5-002: installation covers the five modes, keyed by kind."""
    # Given: an isolated empty registry
    assert [handler_for(kind) for kind in ModeKind] == [None] * len(ModeKind)

    # When: installing the walking-skeleton handlers
    install_default_handlers()

    # Then: every ModeKind has a handler whose kind equals its registry key
    handlers = {kind: handler_for(kind) for kind in ModeKind}
    assert len(handlers) == len(_MODES)
    for kind, handler in handlers.items():
        assert handler is not None
        assert handler.kind is kind


@pytest.mark.usefixtures("empty_mode_registry")
def test_importing_a_mode_module_does_not_register__tc_ep_i5_003() -> None:
    """TC-EP-I5-003: registration is explicit, never an import side effect."""
    # Given: an isolated empty registry

    # When: re-executing every mode module body
    for name in _MODE_MODULES:
        importlib.reload(importlib.import_module(name))

    # Then: no handler was installed by import alone
    assert [handler_for(kind) for kind in ModeKind] == [None] * len(ModeKind)


@pytest.mark.usefixtures("empty_mode_registry")
def test_install_is_idempotent__tc_bv_i5_001() -> None:
    """TC-BV-I5-001: a second installation neither duplicates nor swaps semantics."""
    # Given: an isolated empty registry with handlers already installed
    install_default_handlers()
    first = {kind: handler_for(kind) for kind in ModeKind}

    # When: installing a second time
    install_default_handlers()

    # Then: the registry still holds exactly one handler per mode
    second = {kind: handler_for(kind) for kind in ModeKind}
    assert set(second) == set(first)
    assert all(type(second[kind]) is type(first[kind]) for kind in first)


@pytest.mark.usefixtures("empty_mode_registry")
def test_cleared_registry_returns_to_the_planner_fallback__tc_ep_i5_004(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-EP-I5-004: I0's fallback stays reachable when no handler is installed."""
    # Given: an installed registry that is then cleared, and one materialized case
    install_default_handlers()
    clear()
    root = tmp_path / "fallback-only"
    _generate.materialize_sut_case("invoice", root)
    calls: list[object] = []
    original = importlib.import_module("rdetoolkit.runner.planner").iterate_tiles

    def _spy(*args: object) -> Any:
        calls.append(args)
        return original(*args)

    monkeypatch.setattr("rdetoolkit.runner.planner.iterate_tiles", _spy)

    # When: planning without any registered handler
    tiles = _planned(root, ModeKind.invoice)

    # Then: the legacy iterator produced the tiles
    assert tiles
    assert len(calls) == 1
