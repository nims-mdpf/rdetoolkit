"""V2 RunContext and DI resolution algorithm.

RunContext holds Runner reserved types (InputPaths, OutputContext, etc.)
that can be injected into @node functions via dependency injection.

DI Resolution Priority:
    1. DAG edge result (upstream @node output)
    2. Runner reserved type (InputPaths, OutputContext, RunContext)
    3. UnconnectedInputError
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rdetoolkit.errors import UnconnectedInputError

if TYPE_CHECKING:
    from rdetoolkit.core.dag import DAG
    from rdetoolkit.core.node import NodeSpec
    from rdetoolkit.types import InputPaths, OutputContext


class RunContext:
    """Runtime context providing Runner reserved types for DI resolution.

    Attributes:
        input_paths: Input directory paths (if available).
        output_context: Output directory context (if available).
    """

    __slots__ = ("input_paths", "output_context")

    def __init__(
        self,
        *,
        input_paths: InputPaths | None = None,
        output_context: OutputContext | None = None,
    ) -> None:
        self.input_paths = input_paths
        self.output_context = output_context

    def reserved_types(self) -> dict[str, Any]:
        """Return a mapping of type name -> value for all available reserved types.

        Returns:
            Dict with type name strings as keys and their values.
            RunContext itself is always included.
            None-valued entries (except RunContext) are excluded.
        """
        mapping: dict[str, Any] = {"RunContext": self}
        if self.input_paths is not None:
            mapping["InputPaths"] = self.input_paths
        if self.output_context is not None:
            mapping["OutputContext"] = self.output_context
        return mapping


def _find_edge_result(
    param_name: str,
    node_id: str,
    dag: DAG,
    results: dict[str, dict[str, Any]],
) -> tuple[bool, Any]:
    """Look up the edge result for a given input parameter.

    Searches DAG edges targeting this node for a matching to_port.
    Returns (True, value) if found, (False, None) otherwise.
    """
    edges = dag.edge_list()
    for from_id, to_id, from_port, to_port in edges:
        if to_id == node_id and to_port == param_name:
            node_results = results.get(from_id)
            if node_results is not None and from_port in node_results:
                return True, node_results[from_port]
    return False, None


def resolve_inputs(
    node_spec: NodeSpec,
    dag: DAG,
    results: dict[str, dict[str, Any]],
    context: RunContext,
) -> dict[str, Any]:
    """Resolve all input parameters for a node using the DI priority chain.

    Priority:
        1. DAG edge result (upstream @node output)
        2. Runner reserved type (InputPaths, OutputContext, RunContext)
        3. UnconnectedInputError

    Args:
        node_spec: The NodeSpec describing the node's input requirements.
        dag: The DAG containing edge information.
        results: Mapping of node_id -> {port_name: value} for completed nodes.
        context: RunContext providing reserved types.

    Returns:
        Dict mapping parameter names to resolved values.

    Raises:
        UnconnectedInputError: If a parameter cannot be resolved.
    """
    resolved: dict[str, Any] = {}
    reserved = context.reserved_types()

    for param_name, param_type in node_spec.input_schema.items():
        # Priority 1: DAG edge result
        found, value = _find_edge_result(param_name, node_spec.id, dag, results)
        if found:
            resolved[param_name] = value
            continue

        # Priority 2: Runner reserved type
        if param_type in reserved:
            resolved[param_name] = reserved[param_type]
            continue

        # Priority 3: Unresolvable
        raise UnconnectedInputError(node_spec.id, param_name)

    return resolved
