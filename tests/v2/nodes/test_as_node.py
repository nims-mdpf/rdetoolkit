"""Tests for ``rdetoolkit.as_node`` (Session F1.9, TC-F1-ASNODE-*).

Written before implementation (TDD Red phase). Target: make all tests pass
in codex-worker Green phase. Authority: local/develop/v2/tasks/session_f1.md
Conflict #8 (the exact ruling reproduced below).

Pinned API shape (binding contract for this file, Conflict #8's exact
ruling):

    rdetoolkit.as_node(instance: Any, *, method: str, id: str | None = None, ...) -> Callable[..., Any]

Implemented inside ``src/rdetoolkit/nodes/__init__.py``, reusing the
existing ``rdetoolkit.core.node.node(id=..., ...)`` decorator factory
internally (no new registration machinery -- "no privilege," exactly like
every other node). Default ``id`` when not given:
``f"{type(instance).__module__}.{type(instance).__qualname__}.{method}"``.
Exposed at the top level via ``rdetoolkit/__init__.py``'s ``_LAZY_ATTRS``
(``"as_node": ("rdetoolkit.nodes", "as_node")``), mirroring the existing
``node``/``flow`` entries -- this file imports it as ``from rdetoolkit
import as_node``, matching PhaseF_prompts.md F1.9's literal call shape
``rdetoolkit.as_node(instance, method="read")``.

Each functional test below uses its own dedicated module-level fixture
class (rather than sharing one class+method across tests) specifically so
that each test's default-id registration is independent -- the process-wide
node registry persists for the whole pytest session (the same registry-
isolation constraint documented in ``tests/v2/cli/test_cli_nodes.py``), so
two tests both calling ``as_node(instance, method="read")`` on the *same*
class without an explicit ``id`` would collide on the second call. The one
test that specifically wants that collision
(``test_duplicate_registration_raises_e2001``) triggers it deliberately and
is the only place two ``as_node`` calls share a class+method.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.errors import RdeRegistryError
from rdetoolkit.types import InputPaths


class _ReadHandlerForIdShape:
    """v1-style handler class fixture: a plain class with a 2-arg-plus-self
    method, mirroring the "old handler class" heuristic (mimics a
    ``custom_dataset_function``-style handler asset)."""

    def read(self, paths: InputPaths) -> InputPaths:
        """Return the input paths unchanged (identity, for assertion simplicity)."""
        return paths


class _ReadHandlerForInvocation:
    def read(self, paths: InputPaths) -> tuple[str, InputPaths]:
        return ("invoked", paths)


class _ReadHandlerForFlow:
    def read(self, paths: InputPaths) -> InputPaths:
        return paths


class _ReadHandlerForDuplicate:
    def read(self, paths: InputPaths) -> InputPaths:
        return paths


class _ReadHandlerForExplicitId:
    def read(self, paths: InputPaths) -> InputPaths:
        return paths


class _ReadHandlerForRegistryPresence:
    def read(self, paths: InputPaths) -> InputPaths:
        return paths


class _ReadHandlerForPrivilegeCheck:
    def read(self, paths: InputPaths) -> InputPaths:
        return paths


class TestAsNodeIdShape:
    """TC-F1-ASNODE-ID-*."""

    def test_returns_callable_with_module_class_method_id(self) -> None:
        """EP: as_node returns a callable whose registered id is "module.Class.method" (Conflict #8's exact default-id formula)."""
        from rdetoolkit import as_node

        instance = _ReadHandlerForIdShape()

        result = as_node(instance, method="read")

        assert callable(result)
        expected_id = f"{_ReadHandlerForIdShape.__module__}.{_ReadHandlerForIdShape.__qualname__}.read"
        assert result.__node_spec__.id == expected_id

    def test_registers_in_registry(self) -> None:
        """as_node's produced callable is registered in registry.list_nodes()
        (self-contained: uses its own dedicated fixture class so this test
        does not depend on any other test having already run)."""
        from rdetoolkit import as_node
        from rdetoolkit.core import registry

        as_node(_ReadHandlerForRegistryPresence(), method="read")
        expected_id = f"{_ReadHandlerForRegistryPresence.__module__}.{_ReadHandlerForRegistryPresence.__qualname__}.read"

        ids = {spec.id for spec in registry.list_nodes()}
        assert expected_id in ids, ids

    def test_produces_ordinary_nodespec_no_special_privilege(self) -> None:
        """as_node's spec is a plain core.node.NodeSpec, the exact same type
        ordinary @node-decorated functions get -- structural evidence that
        as_node carries no special privilege (⚠️ constraint)."""
        from rdetoolkit import as_node
        from rdetoolkit.core.node import NodeSpec

        instance = _ReadHandlerForPrivilegeCheck()
        result = as_node(instance, method="read")

        assert type(result.__node_spec__) is NodeSpec


class TestAsNodeInvocation:
    """TC-F1-ASNODE-INVOKE-*."""

    def test_calling_returned_callable_invokes_bound_method(self) -> None:
        """Calling the returned callable actually invokes the bound method (return value passthrough)."""
        from rdetoolkit import as_node

        instance = _ReadHandlerForInvocation()
        wrapped = as_node(instance, method="read")

        sentinel_paths = object()
        result = wrapped(sentinel_paths)

        assert result == ("invoked", sentinel_paths)


class TestAsNodeExplicitId:
    """TC-F1-ASNODE-EXPLICIT-ID-*."""

    def test_explicit_id_overrides_default(self) -> None:
        """Passing id= explicitly overrides the default "module.Class.method" computation."""
        from rdetoolkit import as_node

        instance = _ReadHandlerForExplicitId()
        wrapped = as_node(instance, method="read", id="explicit.custom.node.id")

        assert wrapped.__node_spec__.id == "explicit.custom.node.id"


class TestAsNodeDuplicateRegistration:
    """TC-F1-ASNODE-DUP-*."""

    def test_duplicate_registration_raises_e2001(self) -> None:
        """as_node gets no special exemption from ordinary @node duplicate-id
        rules (⚠️ "no privilege" constraint): registering the same default id
        twice raises E2001 RdeRegistryError, exactly like a plain @node
        double-decoration would."""
        from rdetoolkit import as_node

        first_instance = _ReadHandlerForDuplicate()
        as_node(first_instance, method="read")

        second_instance = _ReadHandlerForDuplicate()
        with pytest.raises(RdeRegistryError) as exc_info:
            as_node(second_instance, method="read")

        assert exc_info.value.code == 2001


class TestAsNodeFlowParticipation:
    """TC-F1-ASNODE-FLOW-*."""

    def test_v1_style_handler_participates_in_flow_end_to_end(self, tmp_path: Path) -> None:
        """F1.9's migration-intermediate-form proof: a v1-style handler
        class's method, wrapped via as_node, participates in an ordinary
        @flow exactly like any other node -- no special integration path."""
        from rdetoolkit import as_node
        from rdetoolkit.core.flow import flow
        from rdetoolkit.testing.builders import make_input_paths

        read_via_node = as_node(_ReadHandlerForFlow(), method="read")

        @flow
        def _fixture_flow_as_node_e2e(paths: InputPaths) -> InputPaths:
            return read_via_node(paths)

        input_paths = make_input_paths(tmp_path)

        result: Any = _fixture_flow_as_node_e2e(input_paths)

        assert result is input_paths
