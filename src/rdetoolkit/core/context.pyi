from typing import Any

from rdetoolkit.core.dag import DAG
from rdetoolkit.core.node import NodeSpec
from rdetoolkit.types import InputPaths, OutputContext

class RunContext:
    input_paths: InputPaths | None
    output_context: OutputContext | None
    def __init__(
        self,
        *,
        input_paths: InputPaths | None = None,
        output_context: OutputContext | None = None,
    ) -> None: ...
    def reserved_types(self) -> dict[type, Any]: ...

def resolve_inputs(
    node_spec: NodeSpec,
    dag: DAG,
    results: dict[str, dict[str, Any]],
    context: RunContext,
) -> dict[str, Any]: ...
