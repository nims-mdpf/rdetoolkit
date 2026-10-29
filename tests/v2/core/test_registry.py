"""Tests for the Session E1 boundary amendment to ``core/registry.py``
(TC-REG-*): three new, strictly-additive public functions needed by the
``nodes``/``flows`` CLI commands (session_e1.md Conflict #4).

Written before implementation (TDD Red phase). Target: make all tests pass
in codex-worker Green phase.

Pinned API shapes (this file is the binding contract for the additive
amendment):
- ``list_nodes() -> tuple[_Spec, ...]`` -- all registered node specs.
- ``list_flows() -> tuple[FlowSpec, ...]`` -- all registered flow specs.
- ``get_flow_function(flow_id: str) -> Any`` -- the exact callable
  registered by ``@flow`` for ``flow_id``; raises ``KeyError`` for an
  unknown id.

Registry-persistence note: ``core/registry.py`` has no reset function and
its module-level dicts persist for the whole pytest process (session_e1.md
Conflict #7). Every fixture below uses a locally-scoped function (its
default, ``<locals>``-qualified id is unique per test) and asserts only
PRESENCE of its own entry -- never an exact ``len(list_nodes())``/
``len(list_flows())`` count.
"""

from __future__ import annotations

from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.types import InputPaths


class TestListNodes:
    """TC-REG-001."""

    def test_list_nodes_contains_just_registered_spec__tc_reg_001(self) -> None:
        from rdetoolkit.core.registry import list_nodes

        @node
        def _fixture_node_reg001(paths: InputPaths) -> None:
            return None

        result = list_nodes()

        assert isinstance(result, tuple)
        ids = {spec.id for spec in result}
        assert _fixture_node_reg001.__node_spec__.id in ids


class TestListFlows:
    """TC-REG-002."""

    def test_list_flows_contains_just_registered_spec__tc_reg_002(self) -> None:
        from rdetoolkit.core.registry import list_flows

        @flow
        def _fixture_flow_reg002(paths: InputPaths) -> None:
            return None

        result = list_flows()

        assert isinstance(result, tuple)
        ids = {spec.id for spec in result}
        assert _fixture_flow_reg002.__flow_spec__.id in ids


class TestGetFlowFunction:
    """TC-REG-003."""

    def test_get_flow_function_returns_exact_registered_callable__tc_reg_003(self) -> None:
        from rdetoolkit.core.registry import get_flow_function

        @flow
        def _fixture_flow_reg003(paths: InputPaths) -> None:
            return None

        flow_id = _fixture_flow_reg003.__flow_spec__.id
        result = get_flow_function(flow_id)

        # The wrapper itself is the registered callable (core/flow.py:
        # register_flow(spec, wrapper)) -- identity, not just equivalence.
        assert result is _fixture_flow_reg003

    def test_get_flow_function_unknown_id_raises_keyerror__tc_reg_003_negative(self) -> None:
        from rdetoolkit.core.registry import get_flow_function

        try:
            get_flow_function("definitely.not.a.registered.flow.id.e1.registry")
        except KeyError:
            pass
        else:
            msg = "get_flow_function must raise KeyError for an unregistered flow id"
            raise AssertionError(msg)


class TestExistingRegistryBehaviorUnaffected:
    """TC-REG-004 (regression guard): the additive amendment must not
    change any pre-existing registry.py behavior (get_node,
    find_unstable_node_ids, register_node duplicate-id raise, register_flow,
    get_flow) -- these already have full coverage in tests/v2/core/
    test_node.py and tests/v2/core/test_flow.py; this is a lightweight
    smoke re-check, not a duplicate of that coverage."""

    def test_get_node_and_find_unstable_node_ids_still_work__tc_reg_004(self) -> None:
        from rdetoolkit.core.registry import find_unstable_node_ids, get_node

        @node
        def _fixture_node_reg004(paths: InputPaths) -> None:
            return None

        node_id = _fixture_node_reg004.__node_spec__.id

        assert get_node(node_id) is _fixture_node_reg004.__node_spec__
        assert node_id in find_unstable_node_ids()

    def test_register_node_duplicate_id_still_raises_2001__tc_reg_004(self) -> None:
        from rdetoolkit.errors import RdeRegistryError

        @node(id="e1_reg004_duplicate_guard")
        def _fixture_node_reg004_dup(paths: InputPaths) -> None:
            return None

        try:

            @node(id="e1_reg004_duplicate_guard")
            def _fixture_node_reg004_dup2(paths: InputPaths) -> None:
                return None

        except RdeRegistryError as exc:
            assert exc.code == 2001
        else:
            msg = "register_node must still raise RdeRegistryError(2001) on a duplicate id"
            raise AssertionError(msg)

    def test_register_flow_and_get_flow_still_work__tc_reg_004(self) -> None:
        from rdetoolkit.core.registry import get_flow

        @flow
        def _fixture_flow_reg004(paths: InputPaths) -> None:
            return None

        flow_id = _fixture_flow_reg004.__flow_spec__.id

        assert get_flow(flow_id) is _fixture_flow_reg004.__flow_spec__
