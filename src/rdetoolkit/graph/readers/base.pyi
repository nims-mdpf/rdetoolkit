from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

import pandas as pd

ColumnSource = Literal["header", "generated", "metadata"]

@dataclass(frozen=True, slots=True)
class ColumnProvenance:
    name: str
    source: ColumnSource
    source_index: int

@dataclass(frozen=True, slots=True, eq=False)
class TableData:
    frame: pd.DataFrame
    reader_id: str
    columns: tuple[ColumnProvenance, ...]
    metadata: Mapping[str, Any] = ...
    def __post_init__(self) -> None: ...

@runtime_checkable
class TableReader(Protocol):
    @property
    def reader_id(self) -> str: ...
    @property
    def extensions(self) -> tuple[str, ...]: ...
    def read(self, path: Path) -> TableData: ...

@dataclass(frozen=True, slots=True)
class FormatCandidate:
    reader_id: str
    confidence: float
    evidence: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class DetectionDecision:
    selected: str | None
    forced: bool
    candidates: tuple[FormatCandidate, ...]
    encoding: str | None = None
    delimiter: str | None = None
    sampled_bytes: int = 0
    sampled_rows: int = 0
    truncated: bool = False
    preview_columns: tuple[str, ...] = ()
    data_rows: int | None = None
    def explain(self) -> str: ...
