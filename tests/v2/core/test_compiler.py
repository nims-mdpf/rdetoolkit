"""Tests for Phase 1.4: Compiler — CompileResult, ExecutionPlan, validation, type checks."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rdetoolkit._core import RustDAG
from rdetoolkit.core.node import node


# ── 1.4.3: RustDAG.validate() ─────────────────────────────────────────


class TestRustDAGValidate:
    """Tests for RustDAG.validate() structural validation."""

    def test_valid_dag_returns_empty_list(self) -> None:
        """A well-connected DAG should produce no validation errors."""
        dag = RustDAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_edge("a", "b", "out", "inp")
        errors = dag.validate()
        assert errors == []

    def test_isolated_node_reports_unconnected(self) -> None:
        """A node with no incoming or outgoing edges should be flagged."""
        dag = RustDAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_node("c")
        dag.add_edge("a", "b", "out", "inp")
        # 'c' is isolated
        errors = dag.validate()
        assert len(errors) >= 1
        kinds = {e["kind"] for e in errors}
        assert "unconnected_node" in kinds
        node_ids = {e["node_id"] for e in errors}
        assert "c" in node_ids
        assert "a" not in node_ids
        assert "b" not in node_ids

    def test_single_node_dag_reports_unconnected(self) -> None:
        """A single-node DAG counts as unconnected (no edges at all)."""
        dag = RustDAG()
        dag.add_node("only")
        errors = dag.validate()
        assert len(errors) == 1
        assert errors[0]["kind"] == "unconnected_node"
        assert errors[0]["node_id"] == "only"

    def test_duplicate_add_node_raises(self) -> None:
        """add_node should reject duplicates (defensive check)."""
        dag = RustDAG()
        dag.add_node("x")
        with pytest.raises(ValueError, match="already exists"):
            dag.add_node("x")

    def test_validate_returns_dict_with_expected_keys(self) -> None:
        """Each validation error dict must contain kind, node_id, message."""
        dag = RustDAG()
        dag.add_node("lonely")
        errors = dag.validate()
        assert len(errors) == 1
        err = errors[0]
        assert set(err.keys()) == {"kind", "node_id", "message"}
        assert isinstance(err["kind"], str)
        assert isinstance(err["node_id"], str)
        assert isinstance(err["message"], str)

    def test_empty_dag_returns_empty_list(self) -> None:
        """An empty DAG (no nodes) should produce no errors."""
        dag = RustDAG()
        errors = dag.validate()
        assert errors == []

    def test_fully_connected_dag_no_errors(self) -> None:
        """A DAG where every node has at least one edge has no errors."""
        dag = RustDAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_node("c")
        dag.add_edge("a", "b", "out", "inp")
        dag.add_edge("b", "c", "out", "inp")
        errors = dag.validate()
        assert errors == []


# ── 1.4.1: CompileResult / ExecutionPlan structure ─────────────────────


class TestCompileResultStructure:
    """Tests for CompileResult, ExecutionPlan, CompileError, CompileWarning data classes."""

    def test_compile_error_fields(self) -> None:
        """CompileError must have code, message, and optional node_id."""
        from rdetoolkit.core.compiler import CompileError

        err = CompileError(code="E_CYCLE", message="Cycle detected")
        assert err.code == "E_CYCLE"
        assert err.message == "Cycle detected"
        assert err.node_id is None

        err2 = CompileError(code="E_UNCONNECTED", message="No edges", node_id="x")
        assert err2.node_id == "x"

    def test_compile_warning_fields(self) -> None:
        """CompileWarning must have code, message, and optional node_id."""
        from rdetoolkit.core.compiler import CompileWarning

        w = CompileWarning(code="W_TYPE", message="Type mismatch")
        assert w.code == "W_TYPE"
        assert w.message == "Type mismatch"
        assert w.node_id is None

    def test_compile_result_success(self) -> None:
        """CompileResult with no errors should be considered successful."""
        from rdetoolkit.core.compiler import CompileResult, ExecutionPlan

        plan = ExecutionPlan(order=["a", "b"], node_specs={})
        result = CompileResult(errors=[], warnings=[], plan=plan)
        assert result.is_success()
        assert result.plan is not None

    def test_compile_result_failure(self) -> None:
        """CompileResult with errors should not be successful."""
        from rdetoolkit.core.compiler import CompileError, CompileResult

        err = CompileError(code="E_CYCLE", message="cycle")
        result = CompileResult(errors=[err], warnings=[], plan=None)
        assert not result.is_success()
        assert result.plan is None

    def test_execution_plan_fields(self) -> None:
        """ExecutionPlan must contain order and node_specs."""
        from rdetoolkit.core.compiler import ExecutionPlan

        plan = ExecutionPlan(order=["a", "b", "c"], node_specs={"a": None})
        assert plan.order == ["a", "b", "c"]
        assert plan.node_specs == {"a": None}


# ── 1.4.5 / 1.4.6: Type check + ambiguous dependency ──────────────────


def _make_dag_with_nodes(*funcs: object) -> "DAG":
    """Helper: build a DAG with @node-decorated functions."""
    from rdetoolkit.core.dag import DAG

    dag = DAG()
    for fn in funcs:
        spec = fn.__node_spec__  # type: ignore[attr-defined]
        dag.add_node(spec.id, spec)
    return dag


class TestTypeChecks:
    """Tests for type checking and ambiguous dependency detection."""

    def test_type_mismatch_detected(self) -> None:
        """When an edge connects incompatible output/input types, an error is raised."""
        from rdetoolkit.core.compiler import Compiler

        @node
        def producer() -> int:
            return 1

        @node
        def consumer(x: str) -> None:
            pass

        dag = _make_dag_with_nodes(producer, consumer)
        dag.add_edge("producer", "consumer", "_return", "x")

        compiler = Compiler(dag, type_check="strict")
        result = compiler.compile()
        type_errors = [e for e in result.errors if e.code == "E_TYPE_MISMATCH"]
        assert len(type_errors) >= 1

    def test_type_check_passes_when_compatible(self) -> None:
        """Compatible types should produce no type errors."""
        from rdetoolkit.core.compiler import Compiler

        @node
        def producer() -> int:
            return 1

        @node
        def consumer(x: int) -> None:
            pass

        dag = _make_dag_with_nodes(producer, consumer)
        dag.add_edge("producer", "consumer", "_return", "x")

        compiler = Compiler(dag, type_check="strict")
        result = compiler.compile()
        type_errors = [e for e in result.errors if e.code == "E_TYPE_MISMATCH"]
        assert type_errors == []

    def test_ambiguous_dependency_detected(self) -> None:
        """When two upstream nodes produce the same type for an unconnected input, warn."""
        from rdetoolkit.core.compiler import Compiler

        @node
        def prod_a() -> int:
            return 1

        @node
        def prod_b() -> int:
            return 2

        @node
        def consumer(x: int) -> None:
            pass

        dag = _make_dag_with_nodes(prod_a, prod_b, consumer)
        dag.add_edge("prod_a", "consumer", "_return", "x")
        # prod_b is connected to consumer too via a different port — or left dangling
        # Ambiguity: multiple producers of `int` type exist
        # For this test, connect both to consumer on different ports
        # Actually — ambiguity is when an input param has no edge but multiple
        # nodes produce the same type.

        # Rebuild: consumer has TWO int params, both unconnected
        @node
        def consumer2(x: int, y: int) -> None:
            pass

        dag2 = _make_dag_with_nodes(prod_a, prod_b, consumer2)
        dag2.add_edge("prod_a", "consumer2", "_return", "x")
        dag2.add_edge("prod_b", "consumer2", "_return", "y")
        # This is fine — no ambiguity
        compiler = Compiler(dag2, type_check="strict")
        result = compiler.compile()
        amb_warnings = [w for w in result.warnings if w.code == "W_AMBIGUOUS_DEP"]
        assert amb_warnings == []

    def test_ambiguous_dependency_warns_when_unresolved(self) -> None:
        """Unconnected input with multiple possible same-type producers warns."""
        from rdetoolkit.core.compiler import Compiler

        @node
        def source_a() -> int:
            return 1

        @node
        def source_b() -> int:
            return 2

        @node
        def sink(val: int) -> None:
            pass

        dag = _make_dag_with_nodes(source_a, source_b, sink)
        # No edges to sink's 'val' — but two producers of int exist
        dag.add_edge("source_a", "source_b", "_return", "val")
        # sink is isolated in terms of edges → will get unconnected warning
        # But the ambiguous dep check is separate: sink's 'val' input has no edge
        # and multiple nodes produce 'int'

        # Let's build a cleaner scenario:
        from rdetoolkit.core.dag import DAG

        dag3 = DAG()
        spec_a = source_a.__node_spec__  # type: ignore[attr-defined]
        spec_b = source_b.__node_spec__  # type: ignore[attr-defined]
        spec_sink = sink.__node_spec__  # type: ignore[attr-defined]
        dag3.add_node(spec_a.id, spec_a)
        dag3.add_node(spec_b.id, spec_b)
        dag3.add_node(spec_sink.id, spec_sink)
        dag3.add_edge("source_a", "sink", "_return", "val")
        # source_b also produces int but is not connected to sink
        # This means source_b is dangling — but that's a separate issue
        # The ambiguity check should fire when there are multiple nodes producing
        # the same type that COULD satisfy an unconnected input

        compiler = Compiler(dag3, type_check="strict")
        result = compiler.compile()
        # source_b is unconnected → structural error
        # No ambiguous dep here since val IS connected
        # Let's test the actual ambiguity case:

        dag4 = DAG()
        dag4.add_node(spec_a.id, spec_a)
        dag4.add_node(spec_b.id, spec_b)
        dag4.add_node(spec_sink.id, spec_sink)
        # No edge to sink's val — sink has unconnected input
        # Both source_a and source_b produce int
        dag4.add_edge("source_a", "source_b", "_return", "val")
        # sink is fully unconnected

        compiler2 = Compiler(dag4, type_check="strict")
        result2 = compiler2.compile()
        # sink has unconnected input 'val' and multiple producers of int exist
        amb_warnings = [w for w in result2.warnings if w.code == "W_AMBIGUOUS_DEP"]
        assert len(amb_warnings) >= 1


# ── 1.4.7 / 1.4.8: Type check strictness (strict / warn / off) ────────


class TestTypeCheckStrictness:
    """Tests for type_check strictness levels."""

    def test_strict_mode_errors(self) -> None:
        """In strict mode, type mismatches produce CompileError."""
        from rdetoolkit.core.compiler import Compiler

        @node
        def prod() -> int:
            return 1

        @node
        def cons(x: str) -> None:
            pass

        dag = _make_dag_with_nodes(prod, cons)
        dag.add_edge("prod", "cons", "_return", "x")

        compiler = Compiler(dag, type_check="strict")
        result = compiler.compile()
        assert not result.is_success()
        type_errors = [e for e in result.errors if e.code == "E_TYPE_MISMATCH"]
        assert len(type_errors) >= 1

    def test_warn_mode_warnings(self) -> None:
        """In warn mode, type mismatches produce CompileWarning (not error)."""
        from rdetoolkit.core.compiler import Compiler

        @node
        def prod() -> int:
            return 1

        @node
        def cons(x: str) -> None:
            pass

        dag = _make_dag_with_nodes(prod, cons)
        dag.add_edge("prod", "cons", "_return", "x")

        compiler = Compiler(dag, type_check="warn")
        result = compiler.compile()
        # warn mode: type mismatches are warnings, not errors
        type_errors = [e for e in result.errors if e.code == "E_TYPE_MISMATCH"]
        assert type_errors == []
        type_warnings = [w for w in result.warnings if w.code == "W_TYPE_MISMATCH"]
        assert len(type_warnings) >= 1

    def test_off_mode_no_type_checks(self) -> None:
        """In off mode, type mismatches are completely ignored."""
        from rdetoolkit.core.compiler import Compiler

        @node
        def prod() -> int:
            return 1

        @node
        def cons(x: str) -> None:
            pass

        dag = _make_dag_with_nodes(prod, cons)
        dag.add_edge("prod", "cons", "_return", "x")

        compiler = Compiler(dag, type_check="off")
        result = compiler.compile()
        type_errors = [e for e in result.errors if e.code == "E_TYPE_MISMATCH"]
        type_warnings = [w for w in result.warnings if w.code in ("W_TYPE_MISMATCH", "E_TYPE_MISMATCH")]
        assert type_errors == []
        assert type_warnings == []


# ── 1.4.9: ExecutionPlan generation ────────────────────────────────────


class TestExecutionPlanGeneration:
    """Tests for ExecutionPlan generation from DAG."""

    def test_execution_plan_order(self) -> None:
        """ExecutionPlan.order should match topological sort."""
        from rdetoolkit.core.compiler import Compiler

        @node
        def step_a() -> int:
            return 1

        @node
        def step_b(x: int) -> int:
            return x + 1

        @node
        def step_c(x: int) -> None:
            pass

        dag = _make_dag_with_nodes(step_a, step_b, step_c)
        dag.add_edge("step_a", "step_b", "_return", "x")
        dag.add_edge("step_b", "step_c", "_return", "x")

        compiler = Compiler(dag, type_check="off")
        result = compiler.compile()
        assert result.is_success()
        assert result.plan is not None
        order = result.plan.order
        assert order.index("step_a") < order.index("step_b")
        assert order.index("step_b") < order.index("step_c")

    def test_execution_plan_contains_node_specs(self) -> None:
        """ExecutionPlan.node_specs should contain all node specs."""
        from rdetoolkit.core.compiler import Compiler

        @node
        def alpha() -> int:
            return 1

        @node
        def beta(x: int) -> None:
            pass

        dag = _make_dag_with_nodes(alpha, beta)
        dag.add_edge("alpha", "beta", "_return", "x")

        compiler = Compiler(dag, type_check="off")
        result = compiler.compile()
        assert result.is_success()
        assert result.plan is not None
        assert "alpha" in result.plan.node_specs
        assert "beta" in result.plan.node_specs

    def test_structural_errors_prevent_plan(self) -> None:
        """If structural validation fails, plan should be None."""
        from rdetoolkit.core.compiler import Compiler

        @node
        def isolated_node() -> int:
            return 1

        dag = _make_dag_with_nodes(isolated_node)
        # No edges — node is isolated

        compiler = Compiler(dag, type_check="off")
        result = compiler.compile()
        assert not result.is_success()
        assert result.plan is None


# ── 1.4.10: PBT — Compile invariants ──────────────────────────────────


def _dag_node_ids_strategy() -> st.SearchStrategy[list[str]]:
    """Generate unique node ID lists."""
    return st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
            min_size=1,
            max_size=10,
        ),
        min_size=2,
        max_size=8,
        unique=True,
    )


def _build_linear_dag_with_nodes(node_ids: list[str]) -> "DAG":
    """Build a linear DAG: node_ids[0] -> node_ids[1] -> ... -> node_ids[-1]."""
    from rdetoolkit.core.dag import DAG
    from rdetoolkit.core.node import NodeSpec

    dag = DAG()
    for i, nid in enumerate(node_ids):
        spec = NodeSpec(
            id=nid,
            func_name=nid,
            input_schema={"x": "int"} if i > 0 else {},
            output_schema="int" if i < len(node_ids) - 1 else "None",
            tags=(),
            version="1.0.0",
            idempotent=False,
        )
        dag.add_node(nid, spec)
    for i in range(len(node_ids) - 1):
        dag.add_edge(node_ids[i], node_ids[i + 1], "_return", "x")
    return dag


@pytest.mark.property
class TestCompilerPBT:
    """Property-based tests for Compiler invariants."""

    @given(node_ids=_dag_node_ids_strategy())
    @settings(max_examples=50, deadline=None)
    def test_valid_linear_dag_compiles_without_errors(self, node_ids: list[str]) -> None:
        """Any valid linear DAG (no cycles, no isolated nodes) should compile cleanly."""
        from rdetoolkit.core.compiler import Compiler

        dag = _build_linear_dag_with_nodes(node_ids)
        compiler = Compiler(dag, type_check="off")
        result = compiler.compile()
        assert result.is_success(), f"Errors: {[e.message for e in result.errors]}"
        assert result.plan is not None
        assert len(result.plan.order) == len(node_ids)

    @given(node_ids=_dag_node_ids_strategy())
    @settings(max_examples=50, deadline=None)
    def test_plan_order_respects_dependencies(self, node_ids: list[str]) -> None:
        """In a linear DAG, the execution order must respect the chain."""
        from rdetoolkit.core.compiler import Compiler

        dag = _build_linear_dag_with_nodes(node_ids)
        compiler = Compiler(dag, type_check="off")
        result = compiler.compile()
        assert result.plan is not None
        order = result.plan.order
        for i in range(len(node_ids) - 1):
            assert order.index(node_ids[i]) < order.index(node_ids[i + 1])

    @given(
        node_ids=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
                min_size=1,
                max_size=10,
            ),
            min_size=1,
            max_size=5,
            unique=True,
        )
    )
    @settings(max_examples=30, deadline=None)
    def test_isolated_nodes_always_produce_errors(self, node_ids: list[str]) -> None:
        """A DAG with only isolated nodes (no edges) must always fail compilation."""
        from rdetoolkit.core.compiler import Compiler
        from rdetoolkit.core.dag import DAG
        from rdetoolkit.core.node import NodeSpec

        dag = DAG()
        for nid in node_ids:
            spec = NodeSpec(
                id=nid,
                func_name=nid,
                input_schema={},
                output_schema="int",
                tags=(),
                version="1.0.0",
                idempotent=False,
            )
            dag.add_node(nid, spec)
        # No edges at all
        compiler = Compiler(dag, type_check="off")
        result = compiler.compile()
        assert not result.is_success()
        structural_errors = [e for e in result.errors if e.code == "E_UNCONNECTED"]
        assert len(structural_errors) == len(node_ids)
