from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass(frozen=True, slots=True)
class InputPaths:
    inputdata: Path
    invoice: Path
    tasksupport: Path

@dataclass(frozen=True, slots=True)
class OutputContext:
    raw: Path
    struct: Path
    main_image: Path
    other_image: Path
    meta: Path
    thumbnail: Path
    logs: Path

@dataclass(frozen=True, slots=True)
class Metadata:
    data: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class InvoiceData:
    schema: dict[str, Any] = field(default_factory=dict)
    content: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class IterationInfo:
    index: int
    total: int
    mode: str
