"""Tests for Phase 1.5: RunContext and DI resolution algorithm."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rdetoolkit.core.node import NodeSpec, node
from rdetoolkit.errors import UnconnectedInputError
from rdetoolkit.types import InputPaths, OutputContext


# ── 1.5.1: RunContext construction and field access ─────────────────────


class TestRunContext:
    """Tests for RunContext construction and field access."""

    def test_construction_with_input_paths(self) -> None:
        """RunContext stores InputPaths and makes it accessible."""
        from rdetoolkit.core.context import RunContext

        ip = InputPaths(
            inputdata=Path("/data/input"),
            invoice=Path("/data/invoice"),
            tasksupport=Path("/data/task"),
        )
        ctx = RunContext(input_paths=ip)
        assert ctx.input_paths is ip

    def test_construction_with_output_context(self) -> None:
        """RunContext stores OutputContext and makes it accessible."""
        from rdetoolkit.core.context import RunContext

        oc = OutputContext(
            raw=Path("/out/raw"),
            struct=Path("/out/struct"),
            main_image=Path("/out/main"),
            other_image=Path("/out/other"),
            meta=Path("/out/meta"),
            thumbnail=Path("/out/thumb"),
            logs=Path("/out/logs"),
        )
        ctx = RunContext(output_context=oc)
        assert ctx.output_context is oc

    def test_construction_with_both(self) -> None:
        """RunContext accepts both InputPaths and OutputContext."""
        from rdetoolkit.core.context import RunContext

        ip = InputPaths(
            inputdata=Path("/data/input"),
            invoice=Path("/data/invoice"),
            tasksupport=Path("/data/task"),
        )
        oc = OutputContext(
            raw=Path("/out/raw"),
            struct=Path("/out/struct"),
            main_image=Path("/out/main"),
            other_image=Path("/out/other"),
            meta=Path("/out/meta"),
            thumbnail=Path("/out/thumb"),
            logs=Path("/out/logs"),
        )
        ctx = RunContext(input_paths=ip, output_context=oc)
        assert ctx.input_paths is ip
        assert ctx.output_context is oc

    def test_construction_with_none(self) -> None:
        """RunContext can be constructed with no reserved types."""
        from rdetoolkit.core.context import RunContext

        ctx = RunContext()
        assert ctx.input_paths is None
        assert ctx.output_context is None

    def test_reserved_types_returns_mapping(self) -> None:
        """reserved_types() returns a dict mapping type names to values."""
        from rdetoolkit.core.context import RunContext

        ip = InputPaths(
            inputdata=Path("/data/input"),
            invoice=Path("/data/invoice"),
            tasksupport=Path("/data/task"),
        )
        ctx = RunContext(input_paths=ip)
        reserved = ctx.reserved_types()
        assert "InputPaths" in reserved
        assert reserved["InputPaths"] is ip

    def test_reserved_types_excludes_none(self) -> None:
        """reserved_types() does not include None-valued entries (except RunContext)."""
        from rdetoolkit.core.context import RunContext

        ctx = RunContext()
        reserved = ctx.reserved_types()
        # Only RunContext itself should be present; InputPaths/OutputContext are None
        assert "InputPaths" not in reserved
        assert "OutputContext" not in reserved
        assert "RunContext" in reserved

    def test_self_reference_in_reserved_types(self) -> None:
        """RunContext itself is available as a reserved type."""
        from rdetoolkit.core.context import RunContext

        ctx = RunContext()
        reserved = ctx.reserved_types()
        assert "RunContext" in reserved
        assert reserved["RunContext"] is ctx


# ── 1.5.3: DI resolution algorithm ─────────────────────────────────────


def _make_spec(
    node_id: str,
    input_schema: dict[str, str],
    output_schema: str | None = None,
) -> NodeSpec:
    """Helper to build a NodeSpec for testing."""
    return NodeSpec(
        id=node_id,
        func_name=node_id,
        input_schema=input_schema,
        output_schema=output_schema,
        tags=(),
        version="1.0.0",
        idempotent=False,
    )


class TestResolveInputs:
    """Tests for the DI resolution algorithm."""

    def test_edge_resolution(self) -> None:
        """Priority 1: upstream node output is injected via DAG edge."""
        from rdetoolkit.core.context import RunContext, resolve_inputs
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        spec_a = _make_spec("a", {}, output_schema="str")
        spec_b = _make_spec("b", {"data": "str"})
        dag.add_node("a", spec_a)
        dag.add_node("b", spec_b)
        dag.add_edge("a", "b", "_return", "data")

        results: dict[str, dict[str, Any]] = {"a": {"_return": "hello"}}
        ctx = RunContext()

        resolved = resolve_inputs(spec_b, dag, results, ctx)
        assert resolved == {"data": "hello"}

    def test_reserved_type_resolution(self) -> None:
        """Priority 2: InputPaths auto-injected when no edge provides it."""
        from rdetoolkit.core.context import RunContext, resolve_inputs
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        spec = _make_spec("reader", {"paths": "InputPaths"})
        dag.add_node("reader", spec)

        ip = InputPaths(
            inputdata=Path("/data/input"),
            invoice=Path("/data/invoice"),
            tasksupport=Path("/data/task"),
        )
        ctx = RunContext(input_paths=ip)
        results: dict[str, dict[str, Any]] = {}

        resolved = resolve_inputs(spec, dag, results, ctx)
        assert resolved["paths"] is ip

    def test_unconnected_input_error(self) -> None:
        """Priority 3: UnconnectedInputError when no resolution is found."""
        from rdetoolkit.core.context import RunContext, resolve_inputs
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        spec = _make_spec("proc", {"unknown_param": "SomeType"})
        dag.add_node("proc", spec)

        ctx = RunContext()
        results: dict[str, dict[str, Any]] = {}

        with pytest.raises(UnconnectedInputError) as exc_info:
            resolve_inputs(spec, dag, results, ctx)
        assert exc_info.value.node_id == "proc"
        assert exc_info.value.param_name == "unknown_param"

    def test_edge_takes_priority_over_reserved(self) -> None:
        """DAG edge results override reserved type injection."""
        from rdetoolkit.core.context import RunContext, resolve_inputs
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        spec_a = _make_spec("a", {}, output_schema="InputPaths")
        spec_b = _make_spec("b", {"paths": "InputPaths"})
        dag.add_node("a", spec_a)
        dag.add_node("b", spec_b)
        dag.add_edge("a", "b", "_return", "paths")

        edge_ip = InputPaths(
            inputdata=Path("/edge"),
            invoice=Path("/edge"),
            tasksupport=Path("/edge"),
        )
        reserved_ip = InputPaths(
            inputdata=Path("/reserved"),
            invoice=Path("/reserved"),
            tasksupport=Path("/reserved"),
        )
        results: dict[str, dict[str, Any]] = {"a": {"_return": edge_ip}}
        ctx = RunContext(input_paths=reserved_ip)

        resolved = resolve_inputs(spec_b, dag, results, ctx)
        assert resolved["paths"] is edge_ip

    def test_multiple_inputs_mixed_resolution(self) -> None:
        """A node can have inputs resolved via different mechanisms."""
        from rdetoolkit.core.context import RunContext, resolve_inputs
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        spec_a = _make_spec("a", {}, output_schema="str")
        spec_b = _make_spec("b", {"data": "str", "paths": "InputPaths"})
        dag.add_node("a", spec_a)
        dag.add_node("b", spec_b)
        dag.add_edge("a", "b", "_return", "data")

        ip = InputPaths(
            inputdata=Path("/data/input"),
            invoice=Path("/data/invoice"),
            tasksupport=Path("/data/task"),
        )
        results: dict[str, dict[str, Any]] = {"a": {"_return": "value"}}
        ctx = RunContext(input_paths=ip)

        resolved = resolve_inputs(spec_b, dag, results, ctx)
        assert resolved["data"] == "value"
        assert resolved["paths"] is ip

    def test_output_context_reserved_resolution(self) -> None:
        """OutputContext is injected as a reserved type."""
        from rdetoolkit.core.context import RunContext, resolve_inputs
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        spec = _make_spec("writer", {"out": "OutputContext"})
        dag.add_node("writer", spec)

        oc = OutputContext(
            raw=Path("/out/raw"),
            struct=Path("/out/struct"),
            main_image=Path("/out/main"),
            other_image=Path("/out/other"),
            meta=Path("/out/meta"),
            thumbnail=Path("/out/thumb"),
            logs=Path("/out/logs"),
        )
        ctx = RunContext(output_context=oc)
        results: dict[str, dict[str, Any]] = {}

        resolved = resolve_inputs(spec, dag, results, ctx)
        assert resolved["out"] is oc

    def test_run_context_self_injection(self) -> None:
        """RunContext itself can be injected as a reserved type."""
        from rdetoolkit.core.context import RunContext, resolve_inputs
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        spec = _make_spec("meta_node", {"ctx": "RunContext"})
        dag.add_node("meta_node", spec)

        ctx = RunContext()
        results: dict[str, dict[str, Any]] = {}

        resolved = resolve_inputs(spec, dag, results, ctx)
        assert resolved["ctx"] is ctx

    def test_tuple_output_edge_resolution(self) -> None:
        """DAG edge with positional output ports (_0, _1) resolves correctly."""
        from rdetoolkit.core.context import RunContext, resolve_inputs
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        spec_a = _make_spec("a", {}, output_schema="tuple[str, int]")
        spec_b = _make_spec("b", {"name": "str", "count": "int"})
        dag.add_node("a", spec_a)
        dag.add_node("b", spec_b)
        dag.add_edge("a", "b", "_0", "name")
        dag.add_edge("a", "b", "_1", "count")

        results: dict[str, dict[str, Any]] = {"a": {"_0": "hello", "_1": 42}}
        ctx = RunContext()

        resolved = resolve_inputs(spec_b, dag, results, ctx)
        assert resolved == {"name": "hello", "count": 42}

    def test_no_inputs_returns_empty_dict(self) -> None:
        """A node with no inputs resolves to an empty dict."""
        from rdetoolkit.core.context import RunContext, resolve_inputs
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        spec = _make_spec("source", {})
        dag.add_node("source", spec)

        ctx = RunContext()
        results: dict[str, dict[str, Any]] = {}

        resolved = resolve_inputs(spec, dag, results, ctx)
        assert resolved == {}


# ── 1.5.5: PBT for DI resolution edge cases ────────────────────────────

# Strategies for generating valid node IDs and parameter names
_node_id_st = st.text(
    alphabet=st.characters(categories=("L", "N"), min_codepoint=ord("a"), max_codepoint=ord("z")),
    min_size=1,
    max_size=10,
)
_param_name_st = st.text(
    alphabet=st.characters(categories=("L",), min_codepoint=ord("a"), max_codepoint=ord("z")),
    min_size=1,
    max_size=8,
)


@pytest.mark.property
class TestDIResolutionPBT:
    """Property-based tests for DI resolution edge cases."""

    @given(
        node_id=_node_id_st,
        param_name=_param_name_st,
    )
    @settings(max_examples=50)
    def test_unconnected_always_raises(self, node_id: str, param_name: str) -> None:
        """Any unconnected, non-reserved input must raise UnconnectedInputError."""
        from rdetoolkit.core.context import RunContext, resolve_inputs
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        spec = _make_spec(node_id, {param_name: "UnknownType"})
        dag.add_node(node_id, spec)

        ctx = RunContext()
        results: dict[str, dict[str, Any]] = {}

        with pytest.raises(UnconnectedInputError) as exc_info:
            resolve_inputs(spec, dag, results, ctx)
        assert exc_info.value.node_id == node_id
        assert exc_info.value.param_name == param_name

    @given(
        node_id=_node_id_st,
        param_name=_param_name_st,
        value=st.text(min_size=0, max_size=20),
    )
    @settings(max_examples=50)
    def test_edge_result_always_resolves(self, node_id: str, param_name: str, value: str) -> None:
        """An edge result for a parameter always takes priority."""
        from rdetoolkit.core.context import RunContext, resolve_inputs
        from rdetoolkit.core.dag import DAG

        src_id = f"src_{node_id}"
        dag = DAG()
        spec_src = _make_spec(src_id, {}, output_schema="str")
        spec_tgt = _make_spec(node_id, {param_name: "str"})
        dag.add_node(src_id, spec_src)
        dag.add_node(node_id, spec_tgt)
        dag.add_edge(src_id, node_id, "_return", param_name)

        results: dict[str, dict[str, Any]] = {src_id: {"_return": value}}
        ctx = RunContext()

        resolved = resolve_inputs(spec_tgt, dag, results, ctx)
        assert resolved[param_name] == value

    @given(
        node_id=_node_id_st,
        param_name=_param_name_st,
    )
    @settings(max_examples=50)
    def test_reserved_type_always_resolves(self, node_id: str, param_name: str) -> None:
        """InputPaths parameter always resolves when RunContext provides it."""
        from rdetoolkit.core.context import RunContext, resolve_inputs
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        spec = _make_spec(node_id, {param_name: "InputPaths"})
        dag.add_node(node_id, spec)

        ip = InputPaths(
            inputdata=Path("/d/in"),
            invoice=Path("/d/inv"),
            tasksupport=Path("/d/ts"),
        )
        ctx = RunContext(input_paths=ip)
        results: dict[str, dict[str, Any]] = {}

        resolved = resolve_inputs(spec, dag, results, ctx)
        assert resolved[param_name] is ip

    @given(
        n_edges=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=20)
    def test_all_edge_inputs_resolve(self, n_edges: int) -> None:
        """All edge-connected inputs resolve correctly for a chain of nodes."""
        from rdetoolkit.core.context import RunContext, resolve_inputs
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        # Create source nodes
        input_schema: dict[str, str] = {}
        results: dict[str, dict[str, Any]] = {}
        for i in range(n_edges):
            src_id = f"src{i}"
            param = f"p{i}"
            spec_src = _make_spec(src_id, {}, output_schema="str")
            dag.add_node(src_id, spec_src)
            input_schema[param] = "str"
            results[src_id] = {"_return": f"val{i}"}

        target_spec = _make_spec("target", input_schema)
        dag.add_node("target", target_spec)

        for i in range(n_edges):
            dag.add_edge(f"src{i}", "target", "_return", f"p{i}")

        ctx = RunContext()
        resolved = resolve_inputs(target_spec, dag, results, ctx)
        assert len(resolved) == n_edges
        for i in range(n_edges):
            assert resolved[f"p{i}"] == f"val{i}"
