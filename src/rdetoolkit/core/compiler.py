"""V2 Compiler — validates a DAG and produces an ExecutionPlan.

The Compiler performs three stages:
1. Structural validation (via RustDAG.validate — unconnected nodes)
2. Type checking (comparing output/input type annotations across edges)
3. ExecutionPlan generation (topological order + NodeSpec metadata)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from rdetoolkit.core.dag import DAG
    from rdetoolkit.core.node import NodeSpec


@dataclass(frozen=True, slots=True)
class CompileError:
    """A compile-time error that prevents execution.

    Attributes:
        code: Machine-readable error code (e.g. E_CYCLE, E_UNCONNECTED).
        message: Human-readable description.
        node_id: Optional node ID associated with the error.
    """

    code: str
    message: str
    node_id: str | None = None


@dataclass(frozen=True, slots=True)
class CompileWarning:
    """A compile-time warning that does not prevent execution.

    Attributes:
        code: Machine-readable warning code (e.g. W_TYPE_MISMATCH).
        message: Human-readable description.
        node_id: Optional node ID associated with the warning.
    """

    code: str
    message: str
    node_id: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """The result of successful compilation — a plan for executing the DAG.

    Attributes:
        order: Node IDs in topological execution order.
        node_specs: Mapping of node ID to its NodeSpec (or None).
    """

    order: list[str]
    node_specs: dict[str, NodeSpec | None]


@dataclass(frozen=True, slots=True)
class CompileResult:
    """Result of compiling a DAG.

    Attributes:
        errors: List of compile errors.
        warnings: List of compile warnings.
        plan: The execution plan (None if errors exist).
    """

    errors: list[CompileError] = field(default_factory=list)
    warnings: list[CompileWarning] = field(default_factory=list)
    plan: ExecutionPlan | None = None

    def is_success(self) -> bool:
        """Return True if compilation succeeded (no errors).

        Returns:
            True if no errors were found.
        """
        return len(self.errors) == 0


class Compiler:
    """Validates a DAG and produces an ExecutionPlan.

    Args:
        dag: The DAG to compile.
        type_check: Type checking strictness level.
    """

    def __init__(
        self,
        dag: DAG,
        type_check: Literal["strict", "warn", "off"] = "strict",
    ) -> None:
        self._dag = dag
        self._type_check = type_check

    def compile(self) -> CompileResult:
        """Run all compilation stages and return a CompileResult.

        Returns:
            CompileResult with errors, warnings, and optional plan.
        """
        errors: list[CompileError] = []
        warnings: list[CompileWarning] = []

        # Stage 1: Structural validation (Rust side)
        self._validate_structure(errors)

        # Stage 2: Type checking (Python side)
        if self._type_check != "off":
            self._check_types(errors, warnings)

        # Stage 3: Ambiguous dependency check
        if self._type_check != "off":
            self._check_ambiguous_deps(warnings)

        # Stage 4: Build execution plan if no errors
        plan: ExecutionPlan | None = None
        if not errors:
            plan = self._build_plan()

        return CompileResult(errors=errors, warnings=warnings, plan=plan)

    def _validate_structure(self, errors: list[CompileError]) -> None:
        """Run RustDAG.validate() and convert results to CompileErrors."""
        rust_errors = self._dag.validate()
        for err in rust_errors:
            errors.append(
                CompileError(
                    code="E_UNCONNECTED",
                    message=err["message"],
                    node_id=err["node_id"],
                ),
            )

    def _check_types(
        self,
        errors: list[CompileError],
        warnings: list[CompileWarning],
    ) -> None:
        """Check type compatibility across all edges."""
        edges = self._dag.edge_list()
        for from_id, to_id, from_port, to_port in edges:
            from_spec = self._dag.get_spec(from_id)
            to_spec = self._dag.get_spec(to_id)
            if from_spec is None or to_spec is None:
                continue

            # Resolve output type from the source node's output_schema dict
            output_type = from_spec.output_schema.get(from_port)
            # Resolve input type from the target node
            input_type = to_spec.input_schema.get(to_port)

            if output_type is None or input_type is None:
                continue

            if output_type != input_type:
                msg = (
                    f"Type mismatch on edge {from_id}.{from_port} -> "
                    f"{to_id}.{to_port}: {output_type} != {input_type}"
                )
                if self._type_check == "strict":
                    errors.append(
                        CompileError(
                            code="E_TYPE_MISMATCH",
                            message=msg,
                            node_id=to_id,
                        ),
                    )
                else:  # warn
                    warnings.append(
                        CompileWarning(
                            code="W_TYPE_MISMATCH",
                            message=msg,
                            node_id=to_id,
                        ),
                    )

    def _check_ambiguous_deps(self, warnings: list[CompileWarning]) -> None:
        """Check for unconnected inputs with multiple same-type producers.

        For each node, find input parameters that have no incoming edge.
        If multiple other nodes produce the same type, warn about ambiguity.
        """
        connected_inputs = self._build_connected_inputs_set()
        output_type_producers = self._build_output_type_producers()

        for nid in self._dag.node_ids():
            spec = self._dag.get_spec(nid)
            if spec is None:
                continue
            for param_name, param_type in spec.input_schema.items():
                if (nid, param_name) in connected_inputs:
                    continue
                producers = [p for p in output_type_producers.get(param_type, []) if p != nid]
                if len(producers) > 1:
                    warnings.append(
                        CompileWarning(
                            code="W_AMBIGUOUS_DEP",
                            message=(
                                f"Unconnected input '{param_name}' on node '{nid}' "
                                f"has {len(producers)} possible producers of type "
                                f"'{param_type}': {producers}"
                            ),
                            node_id=nid,
                        ),
                    )

    def _build_connected_inputs_set(self) -> set[tuple[str, str]]:
        """Build a set of (node_id, port_name) for all connected inputs."""
        connected: set[tuple[str, str]] = set()
        for _from_id, to_id, _from_port, to_port in self._dag.edge_list():
            connected.add((to_id, to_port))
        return connected

    def _build_output_type_producers(self) -> dict[type, list[str]]:
        """Build a mapping of output type -> list of producing node IDs."""
        producers: dict[type, list[str]] = {}
        for nid in self._dag.node_ids():
            spec = self._dag.get_spec(nid)
            if spec is None or not spec.output_schema:
                continue
            for _port_name, port_type in spec.output_schema.items():
                if port_type is not type(None):
                    producers.setdefault(port_type, []).append(nid)
        return producers

    def _build_plan(self) -> ExecutionPlan:
        """Build an ExecutionPlan from the topological sort and NodeSpecs.

        Returns:
            An ExecutionPlan with order and node_specs.
        """
        order = self._dag.topological_sort()
        node_specs: dict[str, NodeSpec | None] = {}
        for nid in order:
            node_specs[nid] = self._dag.get_spec(nid)
        return ExecutionPlan(order=order, node_specs=node_specs)
