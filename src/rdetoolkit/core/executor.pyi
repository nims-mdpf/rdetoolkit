from dataclasses import dataclass
from typing import Any

from rdetoolkit.core.compiler import ExecutionPlan
from rdetoolkit.core.context import RunContext
from rdetoolkit.core.dag import DAG

@dataclass
class ExecutionResult:
    outputs: dict[str, dict[str, Any]] = ...
    failures: dict[str, Exception] = ...
    def is_success(self) -> bool: ...

class Executor:
    _released_nodes: set[str]
    def __init__(
        self,
        *,
        plan: ExecutionPlan,
        dag: DAG,
        context: RunContext,
    ) -> None: ...
    def execute(self) -> ExecutionResult: ...
