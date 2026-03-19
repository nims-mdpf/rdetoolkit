"""Tests for Phase 1.5: Executor and ExecutionResult."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.core.compiler import ExecutionPlan
from rdetoolkit.core.context import RunContext
from rdetoolkit.core.dag import DAG
from rdetoolkit.core.node import NodeSpec, node
from rdetoolkit.types import InputPaths


# ── 1.5.6: Executor tests ──────────────────────────────────────────────


class TestExecutor:
    """Tests for the Executor class."""

    def test_normal_execution_in_plan_order(self) -> None:
        """Nodes execute in ExecutionPlan order and results are recorded."""
        from rdetoolkit.core.executor import ExecutionResult, Executor

        call_order: list[str] = []

        @node
        def source() -> str:
            call_order.append("source")
            return "data"

        @node
        def sink(data: str) -> str:
            call_order.append("sink")
            return f"processed_{data}"

        dag = DAG()
        dag.add_node("source", source.__node_spec__)  # type: ignore[attr-defined]
        dag.add_node("sink", sink.__node_spec__)  # type: ignore[attr-defined]
        dag.add_edge("source", "sink", "_return", "data")

        plan = ExecutionPlan(
            order=["source", "sink"],
            node_specs={"source": source.__node_spec__, "sink": sink.__node_spec__},  # type: ignore[attr-defined]
        )

        executor = Executor(plan=plan, dag=dag, context=RunContext())
        result = executor.execute()

        assert isinstance(result, ExecutionResult)
        assert call_order == ["source", "sink"]
        assert result.is_success()
        assert result.outputs["source"]["_return"] == "data"
        assert result.outputs["sink"]["_return"] == "processed_data"

    def test_node_failure_recorded_in_result(self) -> None:
        """A node that raises an exception has its Failure recorded."""
        from rdetoolkit.core.executor import ExecutionResult, Executor

        @node
        def good_node() -> str:
            return "ok"

        @node
        def bad_node(data: str) -> str:
            msg = "intentional error"
            raise ValueError(msg)

        dag = DAG()
        dag.add_node("good_node", good_node.__node_spec__)  # type: ignore[attr-defined]
        dag.add_node("bad_node", bad_node.__node_spec__)  # type: ignore[attr-defined]
        dag.add_edge("good_node", "bad_node", "_return", "data")

        plan = ExecutionPlan(
            order=["good_node", "bad_node"],
            node_specs={
                "good_node": good_node.__node_spec__,  # type: ignore[attr-defined]
                "bad_node": bad_node.__node_spec__,  # type: ignore[attr-defined]
            },
        )

        executor = Executor(plan=plan, dag=dag, context=RunContext())
        result = executor.execute()

        assert not result.is_success()
        assert "good_node" in result.outputs
        assert "bad_node" in result.failures
        assert isinstance(result.failures["bad_node"], ValueError)

    def test_execution_result_structure(self) -> None:
        """ExecutionResult has outputs, failures, and status."""
        from rdetoolkit.core.executor import ExecutionResult

        result = ExecutionResult(
            outputs={"a": {"_return": 1}},
            failures={},
        )
        assert result.is_success()
        assert result.outputs == {"a": {"_return": 1}}
        assert result.failures == {}

        result_fail = ExecutionResult(
            outputs={"a": {"_return": 1}},
            failures={"b": ValueError("err")},
        )
        assert not result_fail.is_success()

    def test_empty_plan_succeeds(self) -> None:
        """An empty plan executes successfully with no outputs."""
        from rdetoolkit.core.executor import Executor

        dag = DAG()
        plan = ExecutionPlan(order=[], node_specs={})
        executor = Executor(plan=plan, dag=dag, context=RunContext())
        result = executor.execute()

        assert result.is_success()
        assert result.outputs == {}
        assert result.failures == {}

    def test_reserved_type_injection(self) -> None:
        """Executor injects reserved types (InputPaths) via DI resolution."""
        from rdetoolkit.core.executor import Executor

        received: dict[str, Any] = {}

        @node
        def reader(paths: InputPaths) -> str:
            received["paths"] = paths
            return "read_done"

        ip = InputPaths(
            inputdata=Path("/data/input"),
            invoice=Path("/data/invoice"),
            tasksupport=Path("/data/task"),
        )
        dag = DAG()
        dag.add_node("reader", reader.__node_spec__)  # type: ignore[attr-defined]

        plan = ExecutionPlan(
            order=["reader"],
            node_specs={"reader": reader.__node_spec__},  # type: ignore[attr-defined]
        )

        ctx = RunContext(input_paths=ip)
        executor = Executor(plan=plan, dag=dag, context=ctx)
        result = executor.execute()

        assert result.is_success()
        assert received["paths"] is ip

    def test_tuple_output_stored_with_ports(self) -> None:
        """Tuple output nodes store results under positional port names."""
        from rdetoolkit.core.executor import Executor

        @node
        def multi() -> tuple[str, int]:
            return ("hello", 42)

        dag = DAG()
        dag.add_node("multi", multi.__node_spec__)  # type: ignore[attr-defined]

        plan = ExecutionPlan(
            order=["multi"],
            node_specs={"multi": multi.__node_spec__},  # type: ignore[attr-defined]
        )

        executor = Executor(plan=plan, dag=dag, context=RunContext())
        result = executor.execute()

        assert result.is_success()
        assert result.outputs["multi"]["_0"] == "hello"
        assert result.outputs["multi"]["_1"] == 42

    def test_three_node_chain(self) -> None:
        """A -> B -> C chain executes correctly with DI resolution."""
        from rdetoolkit.core.executor import Executor

        @node
        def a() -> int:
            return 10

        @node
        def b(x: int) -> int:
            return x * 2

        @node
        def c(x: int) -> str:
            return str(x)

        dag = DAG()
        dag.add_node("a", a.__node_spec__)  # type: ignore[attr-defined]
        dag.add_node("b", b.__node_spec__)  # type: ignore[attr-defined]
        dag.add_node("c", c.__node_spec__)  # type: ignore[attr-defined]
        dag.add_edge("a", "b", "_return", "x")
        dag.add_edge("b", "c", "_return", "x")

        plan = ExecutionPlan(
            order=["a", "b", "c"],
            node_specs={
                "a": a.__node_spec__,  # type: ignore[attr-defined]
                "b": b.__node_spec__,  # type: ignore[attr-defined]
                "c": c.__node_spec__,  # type: ignore[attr-defined]
            },
        )

        executor = Executor(plan=plan, dag=dag, context=RunContext())
        result = executor.execute()

        assert result.is_success()
        assert result.outputs["a"]["_return"] == 10
        assert result.outputs["b"]["_return"] == 20
        assert result.outputs["c"]["_return"] == "20"

    def test_failure_stops_downstream(self) -> None:
        """When a node fails, downstream nodes depending on it also fail."""
        from rdetoolkit.core.executor import Executor

        @node
        def a() -> int:
            msg = "a failed"
            raise RuntimeError(msg)

        @node
        def b(x: int) -> int:
            return x * 2

        dag = DAG()
        dag.add_node("a", a.__node_spec__)  # type: ignore[attr-defined]
        dag.add_node("b", b.__node_spec__)  # type: ignore[attr-defined]
        dag.add_edge("a", "b", "_return", "x")

        plan = ExecutionPlan(
            order=["a", "b"],
            node_specs={
                "a": a.__node_spec__,  # type: ignore[attr-defined]
                "b": b.__node_spec__,  # type: ignore[attr-defined]
            },
        )

        executor = Executor(plan=plan, dag=dag, context=RunContext())
        result = executor.execute()

        assert not result.is_success()
        assert "a" in result.failures
        assert "b" in result.failures


# ── 1.5.8: _maybe_release memory management ────────────────────────────


class TestMaybeRelease:
    """Tests for intermediate result memory management."""

    def test_intermediate_results_released(self) -> None:
        """Completed node outputs are released when no longer needed downstream."""
        from rdetoolkit.core.executor import Executor

        @node
        def a() -> str:
            return "large_data"

        @node
        def b(data: str) -> str:
            return f"processed_{data}"

        @node
        def c(data: str) -> str:
            return f"final_{data}"

        dag = DAG()
        dag.add_node("a", a.__node_spec__)  # type: ignore[attr-defined]
        dag.add_node("b", b.__node_spec__)  # type: ignore[attr-defined]
        dag.add_node("c", c.__node_spec__)  # type: ignore[attr-defined]
        dag.add_edge("a", "b", "_return", "data")
        dag.add_edge("b", "c", "_return", "data")

        plan = ExecutionPlan(
            order=["a", "b", "c"],
            node_specs={
                "a": a.__node_spec__,  # type: ignore[attr-defined]
                "b": b.__node_spec__,  # type: ignore[attr-defined]
                "c": c.__node_spec__,  # type: ignore[attr-defined]
            },
        )

        executor = Executor(plan=plan, dag=dag, context=RunContext())
        result = executor.execute()

        assert result.is_success()
        assert executor._released_nodes == {"a", "b"}

    def test_multi_consumer_not_released_early(self) -> None:
        """A node with multiple consumers is not released until all have executed."""
        from rdetoolkit.core.executor import Executor

        @node
        def source() -> str:
            return "shared"

        @node
        def consumer1(data: str) -> str:
            return f"c1_{data}"

        @node
        def consumer2(data: str) -> str:
            return f"c2_{data}"

        dag = DAG()
        dag.add_node("source", source.__node_spec__)  # type: ignore[attr-defined]
        dag.add_node("consumer1", consumer1.__node_spec__)  # type: ignore[attr-defined]
        dag.add_node("consumer2", consumer2.__node_spec__)  # type: ignore[attr-defined]
        dag.add_edge("source", "consumer1", "_return", "data")
        dag.add_edge("source", "consumer2", "_return", "data")

        plan = ExecutionPlan(
            order=["source", "consumer1", "consumer2"],
            node_specs={
                "source": source.__node_spec__,  # type: ignore[attr-defined]
                "consumer1": consumer1.__node_spec__,  # type: ignore[attr-defined]
                "consumer2": consumer2.__node_spec__,  # type: ignore[attr-defined]
            },
        )

        executor = Executor(plan=plan, dag=dag, context=RunContext())
        result = executor.execute()

        assert result.is_success()
        assert "source" in executor._released_nodes

    def test_leaf_node_not_released(self) -> None:
        """Leaf nodes (no downstream consumers) are never released."""
        from rdetoolkit.core.executor import Executor

        @node
        def leaf() -> str:
            return "leaf_data"

        dag = DAG()
        dag.add_node("leaf", leaf.__node_spec__)  # type: ignore[attr-defined]

        plan = ExecutionPlan(
            order=["leaf"],
            node_specs={"leaf": leaf.__node_spec__},  # type: ignore[attr-defined]
        )

        executor = Executor(plan=plan, dag=dag, context=RunContext())
        result = executor.execute()

        assert result.is_success()
        assert "leaf" not in executor._released_nodes
