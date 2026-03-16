from typing import Any

from rdetoolkit.core.dag import DAG
from rdetoolkit.core.node import NodeSpec
from rdetoolkit.types import InputPaths, InvoiceData, IterationInfo, OutputContext

RESERVED: dict[str, type]

def get_reserved_mapping() -> dict[str, type]: ...

class RunContext:
    input_paths: InputPaths | None
    output_context: OutputContext | None
    invoice: InvoiceData | None
    iteration: IterationInfo | None
    def __init__(
        self,
        *,
        input_paths: InputPaths | None = None,
        output_context: OutputContext | None = None,
        invoice: InvoiceData | None = None,
        iteration: IterationInfo | None = None,
    ) -> None: ...
    def reserved_values(self) -> dict[str, Any]: ...

def resolve_inputs(
    node_spec: NodeSpec,
    dag: DAG,
    results: dict[str, dict[str, Any]],
    context: RunContext,
) -> dict[str, Any]: ...
