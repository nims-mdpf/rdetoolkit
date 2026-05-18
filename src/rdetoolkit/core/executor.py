"""V2 Executor — runs nodes in ExecutionPlan order with DI resolution.

The Executor takes a compiled ExecutionPlan and executes each @node function
in topological order, resolving inputs via the DI algorithm in context.py.

Includes intermediate result memory management (_maybe_release) to free
completed node outputs once all downstream consumers have executed.

Optionally accepts an ``EventSink`` to emit lifecycle events (node_started,
node_finished, node_failed, node_skipped) during execution.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from rdetoolkit.core.context import resolve_inputs

if TYPE_CHECKING:
    from rdetoolkit.core.compiler import ExecutionPlan
    from rdetoolkit.core.context import RunContext
    from rdetoolkit.core.dag import DAG
    from rdetoolkit.report.events import EventSink


@dataclass
class ExecutionResult:
    """Result of executing an ExecutionPlan.

    Attributes:
        outputs: Mapping of node_id -> {port_name: value} for successful nodes.
        failures: Mapping of node_id -> Exception for failed nodes.
        skipped: Mapping of node_id -> reason for skipped nodes.
    """

    outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    failures: dict[str, Exception] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)

    def is_success(self) -> bool:
        """Return True if no nodes failed.

        Skipped nodes do not affect success status.

        Returns:
            True if all nodes completed successfully (failures is empty).
        """
        return len(self.failures) == 0


def _store_output(
    node_id: str,
    output_schema: dict[str, type],
    raw_output: Any,
) -> dict[str, Any]:
    """Store a node's raw output under the correct port names.

    For multi-output nodes (multiple keys in output_schema), splits a tuple
    into named ports. For single-output nodes, stores under the single key.
    For empty output_schema (None return), stores under ``_return``.
    """
    if not output_schema:
        return {"_return": raw_output}

    keys = list(output_schema.keys())
    if len(keys) == 1:
        return {keys[0]: raw_output}

    # Multiple outputs — expect a tuple matching the port count
    if isinstance(raw_output, tuple) and len(raw_output) == len(keys):
        return dict(zip(keys, raw_output, strict=True))

    return {"_return": raw_output}


class Executor:
    """Executes nodes in topological order with DI resolution.

    Args:
        plan: The compiled ExecutionPlan.
        dag: The DAG with edge information.
        context: RunContext providing reserved types.
        event_sink: Optional event sink for lifecycle events.
    """

    def __init__(
        self,
        *,
        plan: ExecutionPlan,
        dag: DAG,
        context: RunContext,
        event_sink: EventSink | None = None,
    ) -> None:
        self._plan = plan
        self._dag = dag
        self._context = context
        self._event_sink = event_sink
        self._results: dict[str, dict[str, Any]] = {}
        self._released_nodes: set[str] = set()

    def _emit(self, node_id: str, kind: str, **kwargs: Any) -> None:
        """Emit a lifecycle event if a sink is configured.

        Args:
            node_id: The node that produced the event.
            kind: Event kind string ("node_started", "node_finished", "node_failed", "node_skipped").
            **kwargs: Additional keyword arguments for the event factory.
        """
        if self._event_sink is None:
            return
        from rdetoolkit.report.events import Event  # noqa: PLC0415

        if kind == "node_started":
            self._event_sink.emit(Event.node_started(node_id))
        elif kind == "node_finished":
            self._event_sink.emit(Event.node_finished(node_id, duration=kwargs.get("duration", 0.0)))
        elif kind == "node_failed":
            self._event_sink.emit(Event.node_failed(node_id, error=kwargs["error"]))
        elif kind == "node_skipped":
            self._event_sink.emit(Event.node_skipped(node_id, reason=kwargs["reason"]))

    def execute(self) -> ExecutionResult:
        """Execute all nodes in plan order.

        Uses ``NodeSpec.fn`` to obtain the callable for each node.

        Returns:
            ExecutionResult with outputs, failures, and skipped.
        """
        outputs: dict[str, dict[str, Any]] = {}
        failures: dict[str, Exception] = {}
        skipped: dict[str, str] = {}
        failed_nodes: set[str] = set()
        skipped_nodes: set[str] = set()
        unreachable_nodes = failed_nodes | skipped_nodes

        # Pre-compute consumer counts for memory management
        consumer_counts = self._compute_consumer_counts()
        remaining_consumers: dict[str, int] = dict(consumer_counts)

        for node_id in self._plan.order:
            # Check if any upstream dependency has failed or been skipped
            if self._has_unreachable_upstream(node_id, unreachable_nodes):
                predecessors = self._dag.predecessors(node_id)
                upstream_failed = [n for n in predecessors if n in failed_nodes]
                upstream_skipped = [n for n in predecessors if n in skipped_nodes]
                if upstream_failed:
                    reason = f"upstream '{upstream_failed[0]}' failed"
                elif upstream_skipped:
                    up_id = upstream_skipped[0]
                    up_reason = skipped.get(up_id, "unknown")
                    reason = f"upstream '{up_id}' skipped ({up_reason})"
                else:
                    reason = "upstream dependency unreachable"
                skipped[node_id] = reason
                skipped_nodes.add(node_id)
                unreachable_nodes = failed_nodes | skipped_nodes
                self._emit(node_id, "node_skipped", reason=reason)
                continue

            spec = self._plan.node_specs.get(node_id)
            if spec is None:
                continue

            func = spec.fn
            t0 = time.monotonic()

            try:
                # Resolve inputs via DI
                resolved = resolve_inputs(spec, self._dag, self._results, self._context)
                # Emit node_started only after DI succeeds
                self._emit(node_id, "node_started")
                # Execute the node function
                raw_output = func(**resolved)
                # Store output under port names
                port_outputs = _store_output(node_id, spec.output_schema, raw_output)
                self._results[node_id] = port_outputs
                outputs[node_id] = port_outputs
            except Exception as e:
                failures[node_id] = e
                failed_nodes.add(node_id)
                unreachable_nodes = failed_nodes | skipped_nodes
                self._emit(node_id, "node_failed", error=e)
                continue

            duration = time.monotonic() - t0
            self._emit(node_id, "node_finished", duration=duration)

            # Try to release upstream results no longer needed
            self._maybe_release(node_id, remaining_consumers)

        return ExecutionResult(outputs=outputs, failures=failures, skipped=skipped)

    def _has_unreachable_upstream(self, node_id: str, unreachable_nodes: set[str]) -> bool:
        """Check if any predecessor of node_id has failed or been skipped."""
        predecessors = self._dag.predecessors(node_id)
        return any(pred in unreachable_nodes for pred in predecessors)

    def _compute_consumer_counts(self) -> dict[str, int]:
        """Compute how many downstream nodes consume each node's output.

        Returns:
            Mapping of node_id -> number of downstream consumers.
        """
        counts: dict[str, int] = {}
        edges = self._dag.edge_list()
        for from_id, _to_id, _from_port, _to_port in edges:
            counts[from_id] = counts.get(from_id, 0) + 1
        return counts

    def _maybe_release(
        self,
        completed_node_id: str,
        remaining_consumers: dict[str, int],
    ) -> None:
        """Release intermediate results that are no longer needed.

        After a node completes, decrements the consumer count of all its
        upstream nodes. If an upstream node's consumer count reaches zero,
        its results are released from the internal store.

        Args:
            completed_node_id: The node that just finished executing.
            remaining_consumers: Mutable dict tracking remaining consumer counts.
        """
        # Decrement consumer counts for all predecessors
        predecessors = self._dag.predecessors(completed_node_id)
        for pred_id in predecessors:
            if pred_id in remaining_consumers:
                remaining_consumers[pred_id] -= 1
                if remaining_consumers[pred_id] <= 0 and pred_id in self._results:
                    del self._results[pred_id]
                    self._released_nodes.add(pred_id)
