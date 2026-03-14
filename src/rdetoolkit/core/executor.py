"""V2 Executor — runs nodes in ExecutionPlan order with DI resolution.

The Executor takes a compiled ExecutionPlan and executes each @node function
in topological order, resolving inputs via the DI algorithm in context.py.

Includes intermediate result memory management (_maybe_release) to free
completed node outputs once all downstream consumers have executed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from rdetoolkit.core.context import resolve_inputs

if TYPE_CHECKING:
    from rdetoolkit.core.compiler import ExecutionPlan
    from rdetoolkit.core.context import RunContext
    from rdetoolkit.core.dag import DAG


@dataclass
class ExecutionResult:
    """Result of executing an ExecutionPlan.

    Attributes:
        outputs: Mapping of node_id -> {port_name: value} for successful nodes.
        failures: Mapping of node_id -> Exception for failed nodes.
    """

    outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    failures: dict[str, Exception] = field(default_factory=dict)

    def is_success(self) -> bool:
        """Return True if no nodes failed.

        Returns:
            True if all nodes completed successfully.
        """
        return len(self.failures) == 0


def _store_output(
    node_id: str,
    output_schema: str | None,
    raw_output: Any,
) -> dict[str, Any]:
    """Store a node's raw output under the correct port names.

    For tuple outputs, splits into positional ports (_0, _1, ...).
    For single outputs, stores under _return.
    """
    if output_schema is not None and output_schema.startswith("tuple["):
        # Parse tuple type to determine expected element count
        inner = output_schema[6:-1]
        depth = 0
        count = 1
        for ch in inner:
            if ch in "([":
                depth += 1
            elif ch in ")]":
                depth -= 1
            elif ch == "," and depth == 0:
                count += 1

        if isinstance(raw_output, tuple) and len(raw_output) == count:
            return {f"_{i}": raw_output[i] for i in range(count)}

    return {"_return": raw_output}


class Executor:
    """Executes nodes in topological order with DI resolution.

    Args:
        plan: The compiled ExecutionPlan.
        dag: The DAG with edge information.
        context: RunContext providing reserved types.
    """

    def __init__(
        self,
        *,
        plan: ExecutionPlan,
        dag: DAG,
        context: RunContext,
    ) -> None:
        self._plan = plan
        self._dag = dag
        self._context = context
        self._results: dict[str, dict[str, Any]] = {}
        self._released_nodes: set[str] = set()

    def execute(
        self,
        *,
        funcs: dict[str, Callable[..., Any]],
    ) -> ExecutionResult:
        """Execute all nodes in plan order.

        Args:
            funcs: Mapping of node_id -> callable function to execute.

        Returns:
            ExecutionResult with outputs and failures.
        """
        outputs: dict[str, dict[str, Any]] = {}
        failures: dict[str, Exception] = {}
        failed_nodes: set[str] = set()

        # Pre-compute consumer counts for memory management
        consumer_counts = self._compute_consumer_counts()
        remaining_consumers: dict[str, int] = dict(consumer_counts)

        for node_id in self._plan.order:
            # Skip if any upstream dependency has failed
            if self._has_failed_upstream(node_id, failed_nodes):
                err = RuntimeError(
                    f"Skipped: upstream dependency of '{node_id}' failed",
                )
                failures[node_id] = err
                failed_nodes.add(node_id)
                continue

            spec = self._plan.node_specs.get(node_id)
            func = funcs.get(node_id)
            if spec is None or func is None:
                continue

            try:
                # Resolve inputs via DI
                resolved = resolve_inputs(spec, self._dag, self._results, self._context)
                # Execute the node function
                raw_output = func(**resolved)
                # Store output under port names
                port_outputs = _store_output(node_id, spec.output_schema, raw_output)
                self._results[node_id] = port_outputs
                outputs[node_id] = port_outputs
            except Exception as e:
                failures[node_id] = e
                failed_nodes.add(node_id)
                continue

            # Try to release upstream results no longer needed
            self._maybe_release(node_id, remaining_consumers)

        return ExecutionResult(outputs=outputs, failures=failures)

    def _has_failed_upstream(self, node_id: str, failed_nodes: set[str]) -> bool:
        """Check if any predecessor of node_id has failed."""
        predecessors = self._dag.predecessors(node_id)
        return any(pred in failed_nodes for pred in predecessors)

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
