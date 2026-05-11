"""V2 ExecutionPlan JSON output.

Converts a compiled ExecutionPlan into a JSON-serializable dict
for inspection, logging, or CLI output.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rdetoolkit.core.compiler import ExecutionPlan
    from rdetoolkit.core.node import NodeSpec


def _spec_to_dict(spec: NodeSpec | None) -> dict[str, Any] | None:
    """Serialize a NodeSpec to a plain dict, or None if spec is None.

    Args:
        spec: The NodeSpec to serialize, or None.

    Returns:
        A dict representation, or None.
    """
    if spec is None:
        return None
    return {
        "id": spec.id,
        "name": spec.name,
        "tags": list(spec.tags),
        "version": spec.version,
        "idempotent": spec.idempotent,
        "source_location": spec.source_location,
        "input_ports": list(spec.input_schema.keys()),
        "output_ports": list(spec.output_schema.keys()),
    }


def plan_to_dict(plan: ExecutionPlan) -> dict[str, Any]:
    """Convert an ExecutionPlan to a serializable dict.

    Args:
        plan: The compiled execution plan.

    Returns:
        A dict suitable for JSON serialization.
    """
    return {
        "order": list(plan.order),
        "node_specs": {
            nid: _spec_to_dict(spec) for nid, spec in plan.node_specs.items()
        },
    }


def plan_to_json(plan: ExecutionPlan, *, indent: int | None = 2) -> str:
    """Convert an ExecutionPlan to a JSON string.

    Args:
        plan: The compiled execution plan.
        indent: JSON indentation level (None for compact).

    Returns:
        JSON string representation of the plan.
    """
    return json.dumps(plan_to_dict(plan), ensure_ascii=False, indent=indent)
