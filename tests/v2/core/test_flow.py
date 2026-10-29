"""Tests for v2 @flow decorator and Flow Registry (Session C1, Design §3.3).

``@flow`` must be a completely transparent plain-Python call boundary: no
proxying, no trace, no compile step. It registers into a Flow Registry (the
foundation for Phase E's ``flows list``) and, when nested, attributes the
inner flow's node calls' ``NodeCallRecord.parent_flow`` to the immediately
enclosing flow (stack-based — the direct parent, not the outermost ancestor).

EP Table:
| API                    | Partition                          | Rationale               | Expected                                                | Test ID   |
|------------------------|---------------------------------------|--------------------------|------------------------------------------------------------|-----------|
| @flow direct call      | positional args                       | complete transparency    | same result as a bare function                              | TC-EP-201 |
| @flow direct call      | keyword args                          | complete transparency    | same result as a bare function                              | TC-EP-202 |
| @flow exception        | raises inside the flow body           | complete transparency    | original exception type propagates unwrapped                | TC-EP-203 |
| @flow                  | functools.wraps                       | metadata preservation    | __name__ / __doc__ preserved                                 | TC-EP-204 |
| Flow Registry          | registration                          | foundation for flows list | registered flow is retrievable from the registry            | TC-EP-205 |
| Nested flow            | inner flow's node call                | parent_flow recording    | NodeCallRecord.parent_flow == the immediately enclosing flow's id | TC-EP-206 |
| Missing required arg   | flow called without a required arg    | standard Python semantics | plain TypeError                                             | TC-EP-207 |

BV Table:
| API           | Boundary            | Rationale        | Expected                                                     | Test ID   |
|---------------|----------------------|-------------------|-----------------------------------------------------------------|-----------|
| @flow         | zero-argument flow   | minimal form      | callable normally                                                | TC-BV-201 |
| Nested flow   | 3 levels deep        | deep nesting      | innermost node's parent_flow is the direct parent, not the grandparent | TC-BV-202 |
"""

from __future__ import annotations

import pytest

from rdetoolkit.core.calllog import CallLogRecorder
from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node

# --- Module-level fixtures for nested-flow parent_flow tests -----------------
# Decorated once at import time; reused across TC-EP-206 and TC-BV-202 so
# registration (id assignment) happens exactly once.


@node
def inner_node_fn(x: int) -> int:
    """A node called from inside `inner_flow_fn`."""
    return x + 1


@flow
def inner_flow_fn(x: int) -> int:
    """The immediate parent flow for `inner_node_fn`."""
    return inner_node_fn(x)


@flow
def outer_flow_fn(x: int) -> int:
    """Calls `inner_flow_fn`; a plain nested function call."""
    return inner_flow_fn(x)


@node
def deepest_node_fn(x: int) -> int:
    """A node three flow-levels deep, used by the TC-BV-202 nesting test."""
    return x


@flow
def level3_flow_fn(x: int) -> int:
    """Immediate parent of `deepest_node_fn`."""
    return deepest_node_fn(x)


@flow
def level2_flow_fn(x: int) -> int:
    """Middle flow: calls level3, itself called by level1."""
    return level3_flow_fn(x)


@flow
def level1_flow_fn(x: int) -> int:
    """Outermost flow of the 3-level nesting scenario."""
    return level2_flow_fn(x)


class TestFlowTransparency:
    """TC-EP-201..204, TC-EP-207, TC-BV-201: @flow is a plain function call."""

    def test_direct_call_positional_args__tc_ep_201(self) -> None:
        """TC-EP-201: @flow direct call with positional args behaves like a
        bare function."""

        @flow
        def add_flow_fn(a: int, b: int) -> int:
            return a + b

        assert add_flow_fn(2, 3) == 5

    def test_direct_call_keyword_args__tc_ep_202(self) -> None:
        """TC-EP-202: @flow direct call with keyword args behaves like a
        bare function."""

        @flow
        def add_kw_flow_fn(a: int, b: int) -> int:
            return a + b

        assert add_kw_flow_fn(a=2, b=3) == 5

    def test_exception_propagates_unwrapped__tc_ep_203(self) -> None:
        """TC-EP-203: an exception raised inside a flow body propagates with
        its original type — @flow never wraps or swallows it."""

        @flow
        def raises_flow_fn() -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            raises_flow_fn()

    def test_wraps_metadata_preserved__tc_ep_204(self) -> None:
        """TC-EP-204: @flow preserves __name__ and __doc__ via functools.wraps."""

        @flow
        def documented_flow_fn(x: int) -> int:
            """Flow docstring."""
            return x

        assert documented_flow_fn.__name__ == "documented_flow_fn"
        assert documented_flow_fn.__doc__ == "Flow docstring."

    def test_missing_required_argument_raises_type_error__tc_ep_207(self) -> None:
        """TC-EP-207: calling a flow without a required argument raises a
        plain TypeError (standard Python argument-binding semantics)."""

        @flow
        def requires_two_args_flow_fn(a: int, b: int) -> int:
            return a + b

        with pytest.raises(TypeError):
            requires_two_args_flow_fn(1)  # type: ignore[call-arg]

    def test_zero_argument_flow__tc_bv_201(self) -> None:
        """TC-BV-201: a flow with no parameters is callable normally."""

        @flow
        def zero_arg_flow_fn() -> str:
            return "ok"

        assert zero_arg_flow_fn() == "ok"


class TestFlowRegistry:
    """TC-EP-205: Flow Registry registration + lookup."""

    def test_flow_registered_and_retrievable__tc_ep_205(self) -> None:
        """TC-EP-205: a decorated flow is registered and retrievable from the
        Flow Registry (foundation for Phase E's `flows list`)."""
        from rdetoolkit.core.registry import get_flow

        @flow
        def registrable_flow_fn(x: int) -> int:
            return x

        spec = registrable_flow_fn.__flow_spec__  # type: ignore[attr-defined]
        fetched = get_flow(spec.id)
        assert fetched.id == spec.id


class TestNestedFlowParentTracking:
    """TC-EP-206, TC-BV-202: parent_flow attribution for nested flows."""

    def test_nested_flow_records_immediate_parent__tc_ep_206(self) -> None:
        """TC-EP-206: a node called from an inner flow records that inner
        flow's id as parent_flow (not the outer flow that called the inner
        flow)."""
        with CallLogRecorder() as recorder:
            result = outer_flow_fn(1)

        assert result == 2
        records = recorder.records
        node_record = next(r for r in records if r.node_id == inner_node_fn.__node_spec__.id)  # type: ignore[attr-defined]
        assert node_record.parent_flow == inner_flow_fn.__flow_spec__.id  # type: ignore[attr-defined]

    def test_three_level_nested_flow_uses_immediate_parent__tc_bv_202(self) -> None:
        """TC-BV-202: with 3 levels of flow nesting, the innermost node's
        parent_flow is the direct (level3) parent, not the outermost
        (level1) ancestor."""
        with CallLogRecorder() as recorder:
            level1_flow_fn(5)

        records = recorder.records
        node_record = next(r for r in records if r.node_id == deepest_node_fn.__node_spec__.id)  # type: ignore[attr-defined]

        assert node_record.parent_flow == level3_flow_fn.__flow_spec__.id  # type: ignore[attr-defined]
        assert node_record.parent_flow != level1_flow_fn.__flow_spec__.id  # type: ignore[attr-defined]
