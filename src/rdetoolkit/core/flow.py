"""V2 @flow decorator, Trace proxy, and DAG construction.

The ``@flow`` decorator enables two modes:

- **Trace mode** (``flow.build()``): Executes the flow body with ``@node``
  calls replaced by proxy objects to record the DAG structure without
  running any actual computation.
- **Execute mode** (``flow.execute(...)``): Runs nodes in topological order
  as determined by the traced DAG.
"""

from __future__ import annotations

import inspect
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import wraps
from typing import Any

from rdetoolkit.core.dag import DAG
from rdetoolkit.core.node import NodeSpec


class FlowDefinitionError(Exception):
    """Raised when a @flow body contains invalid constructs (e.g. data-dependent branching)."""


@dataclass(frozen=True, slots=True)
class FlowResult:
    """Result of tracing a @flow body — the constructed DAG.

    Attributes:
        dag: The constructed DAG with nodes and edges.
        flow_name: Name of the flow function.
    """

    dag: DAG
    flow_name: str


class OutputProxy:
    """Placeholder for a single output port of a traced @node call.

    Attributes:
        node_id: The ID of the producing node.
        port_name: The name of the output port.
    """

    __slots__ = ("node_id", "port_name")

    def __init__(self, node_id: str, port_name: str) -> None:
        self.node_id = node_id
        self.port_name = port_name

    def __bool__(self) -> bool:
        """Prevent data-dependent branching on proxy values."""
        msg = (
            "Data-dependent branching on proxy values is not allowed in @flow. "
            f"Cannot use output '{self.port_name}' from node '{self.node_id}' "
            "in a boolean context (if/while/and/or)."
        )
        raise FlowDefinitionError(msg)

    def __repr__(self) -> str:
        return f"OutputProxy({self.node_id!r}, {self.port_name!r})"


class NodeProxy:
    """Placeholder returned during DAG tracing instead of actual @node execution.

    Supports tuple unpacking so ``meta, df = read_csv(paths)`` works.

    Attributes:
        node_spec: The NodeSpec of the traced node.
        dag: The DAG being constructed.
        output_names: Names for each output (used during iteration).
    """

    __slots__ = ("dag", "node_spec", "output_names")

    def __init__(
        self,
        node_spec: NodeSpec,
        dag: DAG,
        output_names: tuple[str, ...],
    ) -> None:
        self.node_spec = node_spec
        self.dag = dag
        self.output_names = output_names

    def __iter__(self) -> Iterator[OutputProxy]:
        """Yield an OutputProxy for each output name (enables tuple unpack)."""
        for name in self.output_names:
            yield OutputProxy(self.node_id, name)

    def __bool__(self) -> bool:
        """Prevent data-dependent branching on proxy values."""
        msg = (
            "Data-dependent branching on proxy values is not allowed in @flow. "
            f"Cannot use node '{self.node_id}' output in a boolean context."
        )
        raise FlowDefinitionError(msg)

    @property
    def node_id(self) -> str:
        """Return the node ID from the spec."""
        return self.node_spec.id

    def __repr__(self) -> str:
        return f"NodeProxy({self.node_id!r}, outputs={self.output_names!r})"

    @staticmethod
    def record_call(
        *,
        node_spec: NodeSpec,
        dag: DAG,
        args: dict[str, Any],
        output_names: tuple[str, ...],
    ) -> NodeProxy:
        """Record a @node call during tracing: detect edges from OutputProxy args.

        Args:
            node_spec: The NodeSpec of the node being called.
            dag: The DAG being constructed.
            args: Mapping of parameter names to values (may contain OutputProxy).
            output_names: Names for each output of this node.

        Returns:
            A NodeProxy representing this node's outputs.
        """
        # Add node if not already present
        if node_spec.id not in dag.node_ids():
            dag.add_node(node_spec.id, node_spec)

        # Detect edges from OutputProxy arguments
        for param_name, value in args.items():
            if isinstance(value, OutputProxy):
                dag.add_edge(
                    value.node_id,
                    node_spec.id,
                    from_port=value.port_name,
                    to_port=param_name,
                )
            elif isinstance(value, NodeProxy):
                # Single-output node passed directly
                dag.add_edge(
                    value.node_id,
                    node_spec.id,
                    from_port=value.output_names[0] if value.output_names else "out",
                    to_port=param_name,
                )

        return NodeProxy(node_spec=node_spec, dag=dag, output_names=output_names)


# Thread-local storage for trace mode context
_trace_context: threading.local = threading.local()


def _is_tracing() -> bool:
    """Check if we are currently in trace mode."""
    return getattr(_trace_context, "dag", None) is not None


def _get_trace_dag() -> DAG:
    """Get the DAG being constructed during tracing."""
    return _trace_context.dag


def _infer_output_names(spec: NodeSpec) -> tuple[str, ...]:
    """Infer output names from the NodeSpec's output_schema dict.

    output_schema is ``dict[str, type]`` where keys are port names
    (e.g. ``_0``, ``_1``, ``_return``).  An empty dict means
    no meaningful output (None return) — we still yield ``("_return",)``.
    """
    if not spec.output_schema:
        return ("_return",)
    return tuple(spec.output_schema.keys())


class _Flow:
    """Wrapper around a flow function that supports build() and execute() modes."""

    def __init__(self, func: Callable[..., Any]) -> None:
        self._func = func
        self._name = func.__name__
        wraps(func)(self)

    def build(self) -> FlowResult:
        """Trace the flow body to construct a DAG (trace mode).

        Returns:
            FlowResult containing the constructed DAG.

        Raises:
            FlowDefinitionError: If the flow body contains data-dependent branching.
        """
        dag = DAG()
        _trace_context.dag = dag
        try:
            sig = inspect.signature(self._func)
            dummy_args: dict[str, Any] = {}
            for pname, _param in sig.parameters.items():
                dummy_args[pname] = _FlowInputProxy(pname)
            self._func(**dummy_args)
        finally:
            _trace_context.dag = None
        return FlowResult(dag=dag, flow_name=self._name)

    def execute(self, *args: Any, **kwargs: Any) -> None:
        """Execute the flow: build DAG then run nodes in topological order.

        Args:
            *args: Positional arguments to the flow function.
            **kwargs: Keyword arguments to the flow function.
        """
        # Build the DAG to validate structure
        result = self.build()
        result.dag.topological_sort()

        # Execute nodes by re-calling the flow function directly
        self._func(*args, **kwargs)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Direct call delegates to execute mode."""
        return self.execute(*args, **kwargs)


class _FlowInputProxy:
    """Proxy for flow function input parameters during tracing."""

    __slots__ = ("_name",)

    def __init__(self, name: str) -> None:
        self._name = name

    def __bool__(self) -> bool:
        """Prevent data-dependent branching on flow inputs during tracing."""
        msg = (
            "Data-dependent branching on proxy values is not allowed in @flow. "
            f"Cannot use flow input '{self._name}' in a boolean context."
        )
        raise FlowDefinitionError(msg)

    def __repr__(self) -> str:
        return f"_FlowInputProxy({self._name!r})"


def _trace_node_call(func: Callable[..., Any], *args: Any, **kwargs: Any) -> NodeProxy | Any:
    """Intercept a @node call during tracing to record it in the DAG.

    If we are in trace mode, returns a NodeProxy instead of executing.
    Otherwise, calls the function normally.
    """
    if not _is_tracing():
        return func(*args, **kwargs)

    dag = _get_trace_dag()
    spec: NodeSpec = func.__node_spec__  # type: ignore[attr-defined]

    # Build args dict mapping param names to values
    sig = inspect.signature(func)
    bound = sig.bind(*args, **kwargs)
    bound.apply_defaults()
    call_args = dict(bound.arguments)

    # Infer output names
    output_names = _infer_output_names(spec)

    # Record the call and edges
    return NodeProxy.record_call(
        node_spec=spec,
        dag=dag,
        args=call_args,
        output_names=output_names,
    )


def flow(func: Callable[..., Any]) -> _Flow:
    """Decorator that marks a function as a DAG flow.

    In trace mode (``flow.build()``), the flow body is executed with
    @node calls replaced by proxy objects that record the DAG structure.

    In execute mode (``flow.execute(...)``), nodes run in topological order.

    Args:
        func: The flow function to decorate.

    Returns:
        A _Flow wrapper supporting build() and execute() methods.
    """
    return _Flow(func)
