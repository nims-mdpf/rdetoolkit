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
