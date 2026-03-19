from dataclasses import dataclass
from typing import Literal

from rdetoolkit.core.dag import DAG
from rdetoolkit.core.node import NodeSpec

@dataclass(frozen=True, slots=True)
class CompileError:
    code: str
    message: str
    node_id: str | None = None

@dataclass(frozen=True, slots=True)
class CompileWarning:
    code: str
    message: str
    node_id: str | None = None

@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    order: list[str]
    node_specs: dict[str, NodeSpec | None]

@dataclass(frozen=True, slots=True)
class CompileResult:
    errors: list[CompileError] = ...
    warnings: list[CompileWarning] = ...
    plan: ExecutionPlan | None = None
    def is_success(self) -> bool: ...

class Compiler:
    def __init__(
        self,
        dag: DAG,
        type_check: Literal["strict", "warn", "off"] = "strict",
    ) -> None: ...
    def compile(self) -> CompileResult: ...
