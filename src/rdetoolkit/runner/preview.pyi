from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from rdetoolkit.domain.magic import ResolutionDiagnostic
from rdetoolkit.domain.mode_selection import ModeDecision
from rdetoolkit.modes.stages import StageSpec
from rdetoolkit.runner.graph_preview import GraphPreview

@dataclass(frozen=True, slots=True)
class PlannedTile:
    index: int
    input_names: tuple[str, ...]
    source_row: int | None
    invoice_origin: str
    output_paths: tuple[tuple[str, str], ...]
    invokes_flow: bool
    stages: tuple[StageSpec, ...]

@dataclass(frozen=True, slots=True)
class MagicTilePreview:
    index: int
    status: str
    reason: str
    diagnostics: tuple[ResolutionDiagnostic, ...] = ...
    def to_dict(self) -> dict[str, Any]: ...

@dataclass(frozen=True, slots=True)
class MagicPreview:
    status: str
    reason: str
    tiles: tuple[MagicTilePreview, ...] = ...
    def to_dict(self) -> dict[str, Any]: ...

@dataclass(frozen=True, slots=True)
class RegistrationPreview:
    decision: ModeDecision
    tiles: tuple[PlannedTile, ...]
    stages: tuple[StageSpec, ...]
    config_source: str
    iteration_policy: str
    deterministic_order: bool
    warnings: tuple[str, ...]
    magic: MagicPreview
    graph: GraphPreview
    schema_version: str = ...
    def to_dict(self) -> dict[str, Any]: ...

def preview_registration(root: Path, *, overrides: Mapping[str, Any] | None = ...) -> RegistrationPreview: ...
