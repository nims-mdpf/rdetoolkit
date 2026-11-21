from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal
from zipfile import ZipInfo

from rdetoolkit.types import RdeConfig

class ModeKind(str, Enum):
    invoice = "invoice"
    excelinvoice = "excelinvoice"
    multidatatile = "multidatatile"
    smarttable = "smarttable"
    rdeformat = "rdeformat"

@dataclass(frozen=True, slots=True)
class ModeEvidence:
    mode: ModeKind
    filename: str
    indicator: str

SelectionPolicy = Literal["legacy", "fixed", "auto"]
SelectionSource = Literal["registration", "system.extended_mode", "default"]

@dataclass(frozen=True, slots=True)
class ModeSelection:
    policy: SelectionPolicy
    source: SelectionSource
    supported_modes: tuple[ModeKind, ...]
    fallback_mode: ModeKind | None
    def to_dict(self) -> dict[str, Any]: ...

@dataclass(frozen=True, slots=True)
class ModeDecision:
    configured_mode: ModeKind | None
    chosen_mode: ModeKind
    candidates: tuple[ModeKind, ...]
    evidence: tuple[ModeEvidence, ...]
    reason_codes: tuple[str, ...]
    selection: ModeSelection
    ambiguous: bool = ...
    warning_codes: tuple[int, ...] = ...
    schema_version: str = ...
    def to_dict(self) -> dict[str, Any]: ...

def normalize_mode_name(value: object) -> ModeKind: ...
def _normalize_mode_setting(value: object) -> str: ...
def decide_mode(config: RdeConfig, inputdata_path: Path, *, contract: Literal["v1", "v2"] = "v2") -> ModeDecision: ...
def _archive_layout_problem(entries: list[tuple[ZipInfo, str]]) -> str | None: ...
