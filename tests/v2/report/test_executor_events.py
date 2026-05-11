"""Tests for Phase 2.1.6: EventSink integration with Executor.

EP Table:
| API                    | Partition                | Rationale           | Expected                        | Test ID    |
|------------------------|--------------------------|---------------------|-------------------------------- |------------|
| Executor + EventSink   | successful node          | normal              | started + finished events       | TC-EP-001  |
| Executor + EventSink   | failing node             | error path          | started + failed events         | TC-EP-002  |
| Executor + EventSink   | skipped downstream       | cascade failure     | started + failed for downstream | TC-EP-003  |
| Executor (no sink)     | None event_sink          | backward compat     | works without sink              | TC-EP-004  |

BV Table:
| API                    | Boundary                 | Rationale           | Expected                        | Test ID    |
|------------------------|--------------------------|---------------------|-------------------------------- |------------|
| Executor + EventSink   | empty plan               | no nodes            | no events emitted               | TC-BV-001  |
"""

from __future__ import annotations

import pytest

from rdetoolkit.core.compiler import ExecutionPlan
from rdetoolkit.core.context import RunContext
from rdetoolkit.core.dag import DAG
from rdetoolkit.core.executor import Executor
from rdetoolkit.core.node import node
from rdetoolkit.report.events import MemoryEventSink


class TestExecutorEventSinkIntegration:
    """Tests for EventSink integration with Executor."""

    def test_successful_node_emits_started_and_finished__tc_ep_001(self) -> None:
        """TC-EP-001: A successful node emits started and finished events."""
        # Given: a simple one-node plan
        @node
        def source() -> str:
            return "data"

        dag = DAG()
        dag.add_node("source", source.__node_spec__)  # type: ignore[attr-defined]
        plan = ExecutionPlan(
            order=["source"],
            node_specs={"source": source.__node_spec__},  # type: ignore[attr-defined]
        )
        sink = MemoryEventSink()

        # When: executing with an event sink
        executor = Executor(plan=plan, dag=dag, context=RunContext(), event_sink=sink)
        result = executor.execute()

        # Then: two events emitted (started + finished)
        assert result.is_success()
        assert len(sink.events) == 2
        assert sink.events[0].kind == "node_started"
        assert sink.events[0].node_id == "source"
        assert sink.events[1].kind == "node_finished"
        assert sink.events[1].node_id == "source"
        assert "duration" in sink.events[1].payload

    def test_failing_node_emits_started_and_failed__tc_ep_002(self) -> None:
        """TC-EP-002: A failing node emits started and failed events."""
        # Given: a node that raises
        @node
        def bad_node() -> str:
            msg = "boom"
            raise ValueError(msg)

        dag = DAG()
        dag.add_node("bad_node", bad_node.__node_spec__)  # type: ignore[attr-defined]
        plan = ExecutionPlan(
            order=["bad_node"],
            node_specs={"bad_node": bad_node.__node_spec__},  # type: ignore[attr-defined]
        )
        sink = MemoryEventSink()

        # When: executing
        executor = Executor(plan=plan, dag=dag, context=RunContext(), event_sink=sink)
        result = executor.execute()

        # Then: started + failed events
        assert not result.is_success()
        assert len(sink.events) == 2
        assert sink.events[0].kind == "node_started"
        assert sink.events[1].kind == "node_failed"
        assert sink.events[1].payload["error_type"] == "ValueError"
        assert sink.events[1].payload["error_msg"] == "boom"

    def test_skipped_downstream_emits_node_skipped__tc_ep_003(self) -> None:
        """TC-EP-003: Downstream of a failed node emits node_skipped event."""
        # Given: A -> B chain where A fails
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
        sink = MemoryEventSink()

        # When: executing
        executor = Executor(plan=plan, dag=dag, context=RunContext(), event_sink=sink)
        result = executor.execute()

        # Then: a gets started+failed, b gets node_skipped (not started, not failed)
        assert not result.is_success()
        kinds = [(e.node_id, e.kind) for e in sink.events]
        assert ("a", "node_started") in kinds
        assert ("a", "node_failed") in kinds
        assert ("b", "node_skipped") in kinds
        assert ("b", "node_started") not in kinds
        assert ("b", "node_failed") not in kinds
        # Check that b's skip reason mentions upstream failure
        b_skipped_event = next(e for e in sink.events if e.node_id == "b" and e.kind == "node_skipped")
        assert "upstream" in b_skipped_event.payload["reason"]
        assert result.skipped.get("b") == b_skipped_event.payload["reason"]

    def test_backward_compat_no_sink__tc_ep_004(self) -> None:
        """TC-EP-004: Executor works without an event sink (backward compat)."""
        # Given: a plan without event_sink
        @node
        def source() -> str:
            return "data"

        dag = DAG()
        dag.add_node("source", source.__node_spec__)  # type: ignore[attr-defined]
        plan = ExecutionPlan(
            order=["source"],
            node_specs={"source": source.__node_spec__},  # type: ignore[attr-defined]
        )

        # When: executing without event_sink
        executor = Executor(plan=plan, dag=dag, context=RunContext())
        result = executor.execute()

        # Then: works fine
        assert result.is_success()

    def test_empty_plan_no_events__tc_bv_001(self) -> None:
        """TC-BV-001: Empty plan emits no events."""
        # Given: empty plan
        dag = DAG()
        plan = ExecutionPlan(order=[], node_specs={})
        sink = MemoryEventSink()

        # When: executing
        executor = Executor(plan=plan, dag=dag, context=RunContext(), event_sink=sink)
        result = executor.execute()

        # Then: no events
        assert result.is_success()
        assert len(sink.events) == 0

    def test_transitive_skip__new_p2_b(self) -> None:
        """NEW (P2-B): Transitive skip — A fails, B skips, C skips (not failed)."""
        # Given: A -> B -> C where A fails
        @node
        def a() -> int:
            raise ValueError("a fails")

        @node
        def b(x: int) -> int:
            return x * 2

        @node
        def c(y: int) -> str:
            return str(y)

        dag = DAG()
        dag.add_node("a", a.__node_spec__)  # type: ignore[attr-defined]
        dag.add_node("b", b.__node_spec__)  # type: ignore[attr-defined]
        dag.add_node("c", c.__node_spec__)  # type: ignore[attr-defined]
        dag.add_edge("a", "b", "_return", "x")
        dag.add_edge("b", "c", "_return", "y")

        plan = ExecutionPlan(
            order=["a", "b", "c"],
            node_specs={
                "a": a.__node_spec__,  # type: ignore[attr-defined]
                "b": b.__node_spec__,  # type: ignore[attr-defined]
                "c": c.__node_spec__,  # type: ignore[attr-defined]
            },
        )
        sink = MemoryEventSink()

        # When: executing
        executor = Executor(plan=plan, dag=dag, context=RunContext(), event_sink=sink)
        result = executor.execute()

        # Then: c emits node_skipped (not node_failed)
        c_events = [e for e in sink.events if e.node_id == "c"]
        assert len(c_events) == 1
        assert c_events[0].kind == "node_skipped"
        assert "c" in result.skipped
        assert "c" not in result.failures

    def test_di_failure_no_node_started__new_p1_a(self) -> None:
        """NEW (P1-A): DI failure — node_started is NOT emitted."""
        # Given: a node requiring an input that won't be connected
        @node
        def orphan(x: int) -> int:
            return x * 2

        dag = DAG()
        dag.add_node("orphan", orphan.__node_spec__)  # type: ignore[attr-defined]

        plan = ExecutionPlan(
            order=["orphan"],
            node_specs={"orphan": orphan.__node_spec__},  # type: ignore[attr-defined]
        )
        sink = MemoryEventSink()

        # When: executing
        executor = Executor(plan=plan, dag=dag, context=RunContext(), event_sink=sink)
        result = executor.execute()

        # Then: node_started is NOT emitted, node_failed is
        kinds = [e.kind for e in sink.events if e.node_id == "orphan"]
        assert "node_started" not in kinds
        assert "node_failed" in kinds
        assert not result.is_success()

    def test_multi_node_chain_event_order(self) -> None:
        """Events are emitted in correct execution order for a chain."""
        # Given: A -> B -> C chain
        @node
        def a() -> int:
            return 1

        @node
        def b(x: int) -> int:
            return x + 1

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
        sink = MemoryEventSink()

        # When: executing
        executor = Executor(plan=plan, dag=dag, context=RunContext(), event_sink=sink)
        result = executor.execute()

        # Then: 6 events in correct order
        assert result.is_success()
        assert len(sink.events) == 6
        expected_order = [
            ("a", "node_started"),
            ("a", "node_finished"),
            ("b", "node_started"),
            ("b", "node_finished"),
            ("c", "node_started"),
            ("c", "node_finished"),
        ]
        actual_order = [(e.node_id, e.kind) for e in sink.events]
        assert actual_order == expected_order
