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

            # Resolve output type from the source node
            output_type = self._resolve_output_type(from_spec, from_port)
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

    def _resolve_output_type(self, spec: NodeSpec, port: str) -> str | None:
        """Resolve the type string for a given output port.

        For single-output nodes (_return), uses the output_schema directly.
        For tuple-output nodes (_0, _1, ...), parses the tuple type.

        Args:
            spec: The NodeSpec of the producing node.
            port: The output port name.

        Returns:
            The type string, or None if unresolvable.
        """
        output_schema = spec.output_schema
        if output_schema is None:
            return None

        if port == "_return":
            return output_schema

        # Tuple output: parse positional types
        if output_schema.startswith("tuple["):
            inner = output_schema[6:-1]
            types = self._parse_tuple_types(inner)
            if port.startswith("_") and port[1:].isdigit():
                idx = int(port[1:])
                if idx < len(types):
                    return types[idx].strip()
        return None

    @staticmethod
    def _parse_tuple_types(inner: str) -> list[str]:
        """Parse the inner types of a tuple annotation string.

        Args:
            inner: The string inside tuple[...].

        Returns:
            List of type strings.
        """
        types: list[str] = []
        depth = 0
        current: list[str] = []
        for ch in inner:
            if ch in "([":
                depth += 1
                current.append(ch)
            elif ch in ")]":
                depth -= 1
                current.append(ch)
            elif ch == "," and depth == 0:
                types.append("".join(current).strip())
                current = []
            else:
                current.append(ch)
        if current:
            types.append("".join(current).strip())
        return types

    def _check_ambiguous_deps(self, warnings: list[CompileWarning]) -> None:
        """Check for unconnected inputs with multiple same-type producers.

        For each node, find input parameters that have no incoming edge.
        If multiple other nodes produce the same type, warn about ambiguity.
        """
        edges = self._dag.edge_list()
        # Build map: (to_id, to_port) -> True for connected inputs
        connected_inputs: set[tuple[str, str]] = set()
        for _from_id, to_id, _from_port, to_port in edges:
            connected_inputs.add((to_id, to_port))

        # Build map: output_type -> list of producing node IDs
        output_type_producers: dict[str, list[str]] = {}
        for nid in self._dag.node_ids():
            spec = self._dag.get_spec(nid)
            if spec is None or spec.output_schema is None:
                continue
            out_type = spec.output_schema
            if out_type not in ("None", "NoneType"):
                output_type_producers.setdefault(out_type, []).append(nid)

        # Check each node's unconnected inputs
        for nid in self._dag.node_ids():
            spec = self._dag.get_spec(nid)
            if spec is None:
                continue
            for param_name, param_type in spec.input_schema.items():
                if (nid, param_name) not in connected_inputs:
                    # This input is unconnected — check if multiple producers exist
                    producers = output_type_producers.get(param_type, [])
                    # Exclude self
                    producers = [p for p in producers if p != nid]
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
