"""Tests for RustDAG PyO3 class (Phase 1.3)."""

import pytest

from rdetoolkit._core import RustDAG


# === 1.3.1: Basic add_node / add_edge / node_ids / edge_list ===


class TestRustDAGBasic:
    def test_add_node_appears_in_node_ids(self) -> None:
        dag = RustDAG()
        dag.add_node("a")
        assert "a" in dag.node_ids()

    def test_add_multiple_nodes(self) -> None:
        dag = RustDAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_node("c")
        ids = dag.node_ids()
        assert set(ids) == {"a", "b", "c"}

    def test_add_duplicate_node_raises(self) -> None:
        dag = RustDAG()
        dag.add_node("a")
        with pytest.raises(ValueError, match="already exists"):
            dag.add_node("a")

    def test_add_edge_appears_in_edge_list(self) -> None:
        dag = RustDAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_edge("a", "b", "out", "inp")
        edges = dag.edge_list()
        assert len(edges) == 1
        assert edges[0] == ("a", "b", "out", "inp")

    def test_add_edge_nonexistent_source_raises(self) -> None:
        dag = RustDAG()
        dag.add_node("b")
        with pytest.raises(ValueError, match="not found"):
            dag.add_edge("x", "b", "out", "inp")

    def test_add_edge_nonexistent_target_raises(self) -> None:
        dag = RustDAG()
        dag.add_node("a")
        with pytest.raises(ValueError, match="not found"):
            dag.add_edge("a", "x", "out", "inp")

    def test_empty_dag(self) -> None:
        dag = RustDAG()
        assert dag.node_ids() == []
        assert dag.edge_list() == []


# === 1.3.3: topological_sort ===


class TestTopologicalSort:
    def test_linear_chain(self) -> None:
        dag = RustDAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_node("c")
        dag.add_edge("a", "b", "out", "inp")
        dag.add_edge("b", "c", "out", "inp")
        order = dag.topological_sort()
        assert order.index("a") < order.index("b") < order.index("c")

    def test_branching(self) -> None:
        dag = RustDAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_node("c")
        dag.add_node("d")
        dag.add_edge("a", "b", "out", "inp")
        dag.add_edge("a", "c", "out", "inp")
        dag.add_edge("b", "d", "out", "inp")
        dag.add_edge("c", "d", "out", "inp")
        order = dag.topological_sort()
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_empty_dag(self) -> None:
        dag = RustDAG()
        assert dag.topological_sort() == []

    def test_single_node(self) -> None:
        dag = RustDAG()
        dag.add_node("only")
        assert dag.topological_sort() == ["only"]

    def test_disconnected_nodes(self) -> None:
        dag = RustDAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_node("c")
        order = dag.topological_sort()
        assert set(order) == {"a", "b", "c"}


# === 1.3.5: Cycle detection ===


class TestCycleDetection:
    def test_self_loop_raises(self) -> None:
        dag = RustDAG()
        dag.add_node("a")
        with pytest.raises(ValueError, match="cycle"):
            dag.add_edge("a", "a", "out", "inp")

    def test_two_node_cycle_raises(self) -> None:
        dag = RustDAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_edge("a", "b", "out", "inp")
        with pytest.raises(ValueError, match="cycle"):
            dag.add_edge("b", "a", "out", "inp")

    def test_indirect_cycle_raises(self) -> None:
        dag = RustDAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_node("c")
        dag.add_edge("a", "b", "out", "inp")
        dag.add_edge("b", "c", "out", "inp")
        with pytest.raises(ValueError, match="cycle"):
            dag.add_edge("c", "a", "out", "inp")

    def test_cycle_edge_is_reverted(self) -> None:
        """After a cycle-causing add_edge fails, the edge must not remain."""
        dag = RustDAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_edge("a", "b", "out", "inp")
        with pytest.raises(ValueError, match="cycle"):
            dag.add_edge("b", "a", "out", "inp")
        # Edge list should still contain only the valid edge
        assert len(dag.edge_list()) == 1
        # topological_sort should still work
        order = dag.topological_sort()
        assert order.index("a") < order.index("b")


# === 1.3.6: detect_cycle ===


class TestDetectCycle:
    """Tests for RustDAG.detect_cycle() method."""

    def test_self_loop_detected(self) -> None:
        """Self-loop a→a: detect_cycle() returns [a]."""
        dag = RustDAG()
        dag.add_node("a")
        dag._add_edge_unchecked("a", "a", "out", "inp")
        result = dag.detect_cycle()
        assert result is not None
        assert "a" in result

    def test_two_node_cycle_detected(self) -> None:
        """Two-node cycle a→b→a: detect_cycle() returns cycle path."""
        dag = RustDAG()
        dag.add_node("a")
        dag.add_node("b")
        dag._add_edge_unchecked("a", "b", "out", "inp")
        dag._add_edge_unchecked("b", "a", "out", "inp")
        result = dag.detect_cycle()
        assert result is not None
        assert set(result) == {"a", "b"}

    def test_indirect_cycle_detected(self) -> None:
        """Indirect cycle a→b→c→a: detect_cycle() returns cycle path."""
        dag = RustDAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_node("c")
        dag._add_edge_unchecked("a", "b", "out", "inp")
        dag._add_edge_unchecked("b", "c", "out", "inp")
        dag._add_edge_unchecked("c", "a", "out", "inp")
        result = dag.detect_cycle()
        assert result is not None
        assert set(result) == {"a", "b", "c"}

    def test_acyclic_dag_returns_none(self) -> None:
        """Acyclic DAG: detect_cycle() returns None."""
        dag = RustDAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_node("c")
        dag.add_edge("a", "b", "out", "inp")
        dag.add_edge("b", "c", "out", "inp")
        assert dag.detect_cycle() is None

    def test_empty_dag_returns_none(self) -> None:
        """Empty DAG: detect_cycle() returns None."""
        dag = RustDAG()
        assert dag.detect_cycle() is None

    def test_single_node_no_cycle(self) -> None:
        """Single node without self-loop: detect_cycle() returns None."""
        dag = RustDAG()
        dag.add_node("a")
        assert dag.detect_cycle() is None


class TestDetectCyclePythonWrapper:
    """Tests for DAG Python wrapper detect_cycle() delegation."""

    def test_acyclic_returns_none(self) -> None:
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_edge("a", "b", "out", "inp")
        assert dag.detect_cycle() is None

    def test_delegates_to_rust(self) -> None:
        """Wrapper delegates detect_cycle to RustDAG."""
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        dag.add_node("a")
        dag.add_node("b")
        dag._rust._add_edge_unchecked("a", "b", "out", "inp")
        dag._rust._add_edge_unchecked("b", "a", "out", "inp")
        result = dag.detect_cycle()
        assert result is not None
        assert set(result) == {"a", "b"}


# === 1.3.7: predecessors / successors ===


class TestPredecessorsSuccessors:
    def test_predecessors(self) -> None:
        dag = RustDAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_node("c")
        dag.add_edge("a", "c", "out", "inp")
        dag.add_edge("b", "c", "out", "inp")
        preds = dag.predecessors("c")
        assert set(preds) == {"a", "b"}

    def test_successors(self) -> None:
        dag = RustDAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_node("c")
        dag.add_edge("a", "b", "out", "inp")
        dag.add_edge("a", "c", "out", "inp")
        succs = dag.successors("a")
        assert set(succs) == {"b", "c"}

    def test_predecessors_empty(self) -> None:
        dag = RustDAG()
        dag.add_node("a")
        assert dag.predecessors("a") == []

    def test_successors_empty(self) -> None:
        dag = RustDAG()
        dag.add_node("a")
        assert dag.successors("a") == []

    def test_predecessors_nonexistent_raises(self) -> None:
        dag = RustDAG()
        with pytest.raises(ValueError, match="not found"):
            dag.predecessors("x")

    def test_successors_nonexistent_raises(self) -> None:
        dag = RustDAG()
        with pytest.raises(ValueError, match="not found"):
            dag.successors("x")


# === 1.3.8: DAG Python wrapper ===


class TestDAGPythonWrapper:
    """Tests for the Python DAG wrapper (core/dag.py)."""

    def test_add_node_with_spec(self) -> None:
        """DAG wrapper stores NodeSpec Python-side."""
        from rdetoolkit.core.dag import DAG
        from rdetoolkit.core.node import NodeSpec

        def _dummy() -> None:
            pass

        dag = DAG()
        spec = NodeSpec(
            id="a",
            name="a",
            fn=_dummy,
            input_schema={},
            output_schema={},
            tags=(),
            version="0.0.0",
            idempotent=False,
            source_location="test:a",
        )
        dag.add_node("a", spec)
        assert "a" in dag.node_ids()
        assert dag.get_spec("a") is spec

    def test_add_node_none_spec(self) -> None:
        """DAG wrapper accepts None as spec."""
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        dag.add_node("a")
        assert "a" in dag.node_ids()
        assert dag.get_spec("a") is None

    def test_add_edge_delegated(self) -> None:
        """DAG wrapper delegates add_edge to RustDAG."""
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_edge("a", "b", "out", "inp")
        assert dag.edge_list() == [("a", "b", "out", "inp")]

    def test_topological_sort_delegated(self) -> None:
        """DAG wrapper delegates topological_sort to RustDAG."""
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_edge("a", "b", "out", "inp")
        order = dag.topological_sort()
        assert order.index("a") < order.index("b")

    def test_predecessors_delegated(self) -> None:
        """DAG wrapper delegates predecessors to RustDAG."""
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_edge("a", "b", "out", "inp")
        assert dag.predecessors("b") == ["a"]

    def test_successors_delegated(self) -> None:
        """DAG wrapper delegates successors to RustDAG."""
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_edge("a", "b", "out", "inp")
        assert dag.successors("a") == ["b"]

    def test_node_count(self) -> None:
        """DAG wrapper returns correct node count."""
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        assert dag.node_count() == 0
        dag.add_node("a")
        dag.add_node("b")
        assert dag.node_count() == 2

    def test_edge_count(self) -> None:
        """DAG wrapper returns correct edge count."""
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        dag.add_node("a")
        dag.add_node("b")
        assert dag.edge_count() == 0
        dag.add_edge("a", "b", "out", "inp")
        assert dag.edge_count() == 1

    def test_get_spec_nonexistent_raises(self) -> None:
        """get_spec raises KeyError for unknown node."""
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        with pytest.raises(KeyError, match="not found"):
            dag.get_spec("x")

    def test_duplicate_node_raises(self) -> None:
        """DAG wrapper propagates duplicate node error from Rust."""
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        dag.add_node("a")
        with pytest.raises(ValueError, match="already exists"):
            dag.add_node("a")

    def test_cycle_raises(self) -> None:
        """DAG wrapper propagates cycle error from Rust."""
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        dag.add_node("a")
        dag.add_node("b")
        dag.add_edge("a", "b", "out", "inp")
        with pytest.raises(ValueError, match="cycle"):
            dag.add_edge("b", "a", "out", "inp")


# === 1.3.9: PBT (Property-Based Testing) ===


from hypothesis import given, settings, strategies as st


@pytest.mark.property
class TestDAGProperties:
    """Property-based tests for DAG operations."""

    @given(
        node_ids=st.lists(
            st.text(min_size=1, max_size=8, alphabet="abcdefghij"),
            min_size=0,
            max_size=15,
            unique=True,
        )
    )
    def test_topological_sort_contains_each_node_exactly_once(
        self, node_ids: list[str]
    ) -> None:
        """Property: sort result contains each node exactly once (no edges = always acyclic)."""
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        for nid in node_ids:
            dag.add_node(nid)
        order = dag.topological_sort()
        assert sorted(order) == sorted(node_ids)
        assert len(order) == len(set(order))

    @given(
        node_ids=st.lists(
            st.text(min_size=1, max_size=8, alphabet="abcdefghij"),
            min_size=0,
            max_size=15,
            unique=True,
        )
    )
    def test_acyclic_dag_topological_sort_does_not_raise(
        self, node_ids: list[str]
    ) -> None:
        """Property: an acyclic DAG never raises on topological_sort."""
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        for nid in node_ids:
            dag.add_node(nid)
        # Add only forward edges (i < j) to guarantee acyclicity
        for i in range(len(node_ids) - 1):
            dag.add_edge(node_ids[i], node_ids[i + 1], "out", "inp")
        order = dag.topological_sort()
        # Verify ordering respects edges
        for i in range(len(node_ids) - 1):
            assert order.index(node_ids[i]) < order.index(node_ids[i + 1])

    @given(
        n=st.integers(min_value=2, max_value=10),
    )
    def test_cycle_detection_consistent_with_topological_sort(
        self, n: int
    ) -> None:
        """Property: creating a cycle causes add_edge to raise ValueError."""
        from rdetoolkit.core.dag import DAG

        dag = DAG()
        nodes = [f"n{i}" for i in range(n)]
        for nid in nodes:
            dag.add_node(nid)
        # Build a chain
        for i in range(n - 1):
            dag.add_edge(nodes[i], nodes[i + 1], "out", "inp")
        # Close the cycle: last -> first should raise
        with pytest.raises(ValueError, match="cycle"):
            dag.add_edge(nodes[-1], nodes[0], "out", "inp")
