from typing import Any

from rdetoolkit.core.node import NodeSpec
from rdetoolkit.types import InputPaths, InvoiceData, IterationInfo, OutputContext, RdeConfig

RESERVED: dict[str, type]

def get_reserved_mapping() -> dict[str, type]: ...

class RunContext:
    paths: InputPaths | None
    out: OutputContext | None
    config: RdeConfig | None
    invoice: InvoiceData | None
    iteration: IterationInfo | None
    def __init__(
        self,
        *,
        paths: InputPaths | None = None,
        out: OutputContext | None = None,
        config: RdeConfig | None = None,
        input_paths: InputPaths | None = None,
        output_context: OutputContext | None = None,
        invoice: InvoiceData | None = None,
        iteration: IterationInfo | None = None,
    ) -> None: ...
    @property
    def input_paths(self) -> InputPaths | None: ...
    @property
    def output_context(self) -> OutputContext | None: ...
    def reserved_values(self) -> dict[str, Any]: ...
