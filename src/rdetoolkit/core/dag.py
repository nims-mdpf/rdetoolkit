"""V2 DAG Python wrapper over RustDAG.

Delegates graph operations (node/edge management, topological sort,
cycle detection) to the Rust ``RustDAG`` class while managing
``NodeSpec`` metadata on the Python side.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rdetoolkit._core import RustDAG

if TYPE_CHECKING:
    from rdetoolkit.core.node import NodeSpec


class DAG:
    """Python DAG wrapper. Delegates graph ops to RustDAG; manages NodeSpec Python-side.

    Attributes:
        _rust: The underlying Rust DAG engine.
        _specs: Mapping of node IDs to their Python-side NodeSpec (or None).
    """

    def __init__(self) -> None:
        self._rust = RustDAG()
        self._specs: dict[str, NodeSpec | None] = {}

    def add_node(self, node_id: str, spec: NodeSpec | None = None) -> None:
        """Add a node to the DAG.

        Args:
            node_id: Unique string identifier for the node.
            spec: Optional NodeSpec metadata (stays Python-side).

        Raises:
            ValueError: If node_id already exists.
        """
        self._rust.add_node(node_id)  # only str crosses boundary
        self._specs[node_id] = spec  # Python object stays Python-side

    def add_edge(
        self,
        from_id: str,
        to_id: str,
        from_port: str,
        to_port: str,
    ) -> None:
        """Add a directed edge between two nodes.

        Args:
            from_id: Source node ID.
            to_id: Target node ID.
            from_port: Output port name on the source node.
            to_port: Input port name on the target node.

        Raises:
            ValueError: If either node is not found or the edge creates a cycle.
        """
        self._rust.add_edge(from_id, to_id, from_port, to_port)

    def topological_sort(self) -> list[str]:
        """Return nodes in topological order.

        Delegates to RustDAG for O(V+E) performance via petgraph.

        Returns:
            List of node IDs in dependency order (sources first).

        Raises:
            ValueError: If the DAG contains a cycle.
        """
        return self._rust.topological_sort()

    def predecessors(self, node_id: str) -> list[str]:
        """Return IDs of all predecessor nodes.

        Args:
            node_id: The node to query.

        Returns:
            List of node IDs with edges pointing to node_id.

        Raises:
            ValueError: If node_id is not found.
        """
        return self._rust.predecessors(node_id)

    def successors(self, node_id: str) -> list[str]:
        """Return IDs of all successor nodes.

        Args:
            node_id: The node to query.

        Returns:
            List of node IDs that node_id has edges pointing to.

        Raises:
            ValueError: If node_id is not found.
        """
        return self._rust.successors(node_id)

    def node_ids(self) -> list[str]:
        """Return all node IDs in the DAG.

        Returns:
            List of node ID strings.
        """
        return self._rust.node_ids()

    def edge_list(self) -> list[tuple[str, str, str, str]]:
        """Return all edges as (from_id, to_id, from_port, to_port) tuples.

        Returns:
            List of edge tuples.
        """
        return self._rust.edge_list()

    def node_count(self) -> int:
        """Return the number of nodes in the DAG.

        Returns:
            Node count.
        """
        return len(self._rust.node_ids())

    def edge_count(self) -> int:
        """Return the number of edges in the DAG.

        Returns:
            Edge count.
        """
        return len(self._rust.edge_list())

    def get_spec(self, node_id: str) -> NodeSpec | None:
        """Return the NodeSpec for a given node ID.

        Args:
            node_id: The node to look up.

        Returns:
            The NodeSpec, or None if not set.

        Raises:
            KeyError: If node_id is not in the DAG.
        """
        if node_id not in self._specs:
            msg = f"Node '{node_id}' not found in DAG specs"
            raise KeyError(msg)
        return self._specs[node_id]
