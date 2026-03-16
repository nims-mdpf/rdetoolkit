use std::collections::HashMap;

use petgraph::algo::{tarjan_scc, toposort};
use petgraph::graph::{DiGraph, NodeIndex};
use petgraph::Direction;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

/// Internal edge metadata (not exposed to Python).
struct EdgeInfo {
    from_port: String,
    to_port: String,
}

/// A directed acyclic graph backed by petgraph.
///
/// Nodes are identified by unique string IDs. Edges carry port metadata.
/// Cycle detection is enforced on every `add_edge` call.
#[pyclass]
pub struct RustDAG {
    graph: DiGraph<String, EdgeInfo>,
    node_index: HashMap<String, NodeIndex>,
}

#[pymethods]
impl RustDAG {
    #[new]
    fn new() -> Self {
        RustDAG {
            graph: DiGraph::new(),
            node_index: HashMap::new(),
        }
    }

    /// Add a node with the given ID. Raises ValueError if the ID already exists.
    fn add_node(&mut self, node_id: &str) -> PyResult<()> {
        if self.node_index.contains_key(node_id) {
            return Err(PyValueError::new_err(format!(
                "Node '{}' already exists",
                node_id
            )));
        }
        let idx = self.graph.add_node(node_id.to_string());
        self.node_index.insert(node_id.to_string(), idx);
        Ok(())
    }

    /// Add a directed edge. Raises ValueError if either node is not found or
    /// the edge would create a cycle.
    fn add_edge(
        &mut self,
        from_id: &str,
        to_id: &str,
        from_port: &str,
        to_port: &str,
    ) -> PyResult<()> {
        let from_idx = self
            .node_index
            .get(from_id)
            .copied()
            .ok_or_else(|| PyValueError::new_err(format!("Node '{}' not found", from_id)))?;
        let to_idx = self
            .node_index
            .get(to_id)
            .copied()
            .ok_or_else(|| PyValueError::new_err(format!("Node '{}' not found", to_id)))?;

        let edge_info = EdgeInfo {
            from_port: from_port.to_string(),
            to_port: to_port.to_string(),
        };
        let edge_idx = self.graph.add_edge(from_idx, to_idx, edge_info);

        // Check for cycles using toposort. If a cycle is detected, revert.
        if toposort(&self.graph, None).is_err() {
            self.graph.remove_edge(edge_idx);
            return Err(PyValueError::new_err("DAG contains a cycle"));
        }

        Ok(())
    }

    /// Return all node IDs.
    fn node_ids(&self) -> Vec<String> {
        self.graph
            .node_weights()
            .cloned()
            .collect()
    }

    /// Return all edges as list of (from_id, to_id, from_port, to_port) tuples.
    fn edge_list(&self) -> Vec<(String, String, String, String)> {
        self.graph
            .edge_indices()
            .filter_map(|ei| {
                let (src, tgt) = self.graph.edge_endpoints(ei)?;
                let weight = self.graph.edge_weight(ei)?;
                Some((
                    self.graph[src].clone(),
                    self.graph[tgt].clone(),
                    weight.from_port.clone(),
                    weight.to_port.clone(),
                ))
            })
            .collect()
    }

    /// Return a topological ordering of node IDs.
    fn topological_sort(&self) -> PyResult<Vec<String>> {
        let sorted = toposort(&self.graph, None).map_err(|_| {
            PyValueError::new_err("DAG contains a cycle")
        })?;
        Ok(sorted.into_iter().map(|idx| self.graph[idx].clone()).collect())
    }

    /// Return the IDs of all predecessor nodes (nodes with edges pointing to `node_id`).
    fn predecessors(&self, node_id: &str) -> PyResult<Vec<String>> {
        let idx = self
            .node_index
            .get(node_id)
            .copied()
            .ok_or_else(|| PyValueError::new_err(format!("Node '{}' not found", node_id)))?;
        Ok(self
            .graph
            .neighbors_directed(idx, Direction::Incoming)
            .map(|ni| self.graph[ni].clone())
            .collect())
    }

    /// Return the IDs of all successor nodes (nodes that `node_id` has edges pointing to).
    fn successors(&self, node_id: &str) -> PyResult<Vec<String>> {
        let idx = self
            .node_index
            .get(node_id)
            .copied()
            .ok_or_else(|| PyValueError::new_err(format!("Node '{}' not found", node_id)))?;
        Ok(self
            .graph
            .neighbors_directed(idx, Direction::Outgoing)
            .map(|ni| self.graph[ni].clone())
            .collect())
    }

    /// Validate the DAG structure and return a list of validation errors.
    ///
    /// Each error is a dict with keys: "kind", "node_id", "message".
    /// Detects: cycles, unconnected nodes (no incoming or outgoing edges).
    fn validate(&self) -> Vec<HashMap<String, String>> {
        let mut errors = Vec::new();

        // Check for cycles
        if let Some(cycle_nodes) = self.find_cycle_nodes() {
            let mut err = HashMap::new();
            err.insert("kind".to_string(), "cycle".to_string());
            err.insert("node_id".to_string(), cycle_nodes.first().cloned().unwrap_or_default());
            err.insert(
                "message".to_string(),
                format!(
                    "DAG contains a cycle involving nodes: {}",
                    cycle_nodes.join(" -> ")
                ),
            );
            errors.push(err);
        }

        // Check for unconnected nodes
        for (node_id, &idx) in &self.node_index {
            let has_incoming = self
                .graph
                .neighbors_directed(idx, Direction::Incoming)
                .next()
                .is_some();
            let has_outgoing = self
                .graph
                .neighbors_directed(idx, Direction::Outgoing)
                .next()
                .is_some();

            if !has_incoming && !has_outgoing {
                let mut err = HashMap::new();
                err.insert("kind".to_string(), "unconnected_node".to_string());
                err.insert("node_id".to_string(), node_id.clone());
                err.insert(
                    "message".to_string(),
                    format!(
                        "Node '{}' has no incoming or outgoing edges",
                        node_id
                    ),
                );
                errors.push(err);
            }
        }

        errors
    }

    /// Detect cycles in the DAG.
    ///
    /// Returns a list of node IDs forming a cycle, or None if the DAG is acyclic.
    fn detect_cycle(&self) -> Option<Vec<String>> {
        self.find_cycle_nodes()
    }

    /// Add edge without cycle check. For testing ``detect_cycle()`` only.
    fn _add_edge_unchecked(
        &mut self,
        from_id: &str,
        to_id: &str,
        from_port: &str,
        to_port: &str,
    ) -> PyResult<()> {
        let from_idx = self
            .node_index
            .get(from_id)
            .copied()
            .ok_or_else(|| PyValueError::new_err(format!("Node '{}' not found", from_id)))?;
        let to_idx = self
            .node_index
            .get(to_id)
            .copied()
            .ok_or_else(|| PyValueError::new_err(format!("Node '{}' not found", to_id)))?;

        self.graph.add_edge(
            from_idx,
            to_idx,
            EdgeInfo {
                from_port: from_port.to_string(),
                to_port: to_port.to_string(),
            },
        );
        Ok(())
    }
}

impl RustDAG {
    /// Internal helper: find cycle nodes using Tarjan's SCC algorithm.
    fn find_cycle_nodes(&self) -> Option<Vec<String>> {
        // Fast path: if toposort succeeds, no cycles exist
        if toposort(&self.graph, None).is_ok() {
            return None;
        }

        // Find cycles using Tarjan's strongly connected components
        for scc in tarjan_scc(&self.graph) {
            if scc.len() > 1 {
                return Some(scc.iter().map(|&idx| self.graph[idx].clone()).collect());
            }
            // Single-node SCC: check for self-loop
            if scc.len() == 1 {
                let idx = scc[0];
                if self.graph.find_edge(idx, idx).is_some() {
                    return Some(vec![self.graph[idx].clone()]);
                }
            }
        }

        None
    }
}
