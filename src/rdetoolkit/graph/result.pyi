from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from rdetoolkit.graph.naming import GraphDiagnostic
from rdetoolkit.graph.plan import PlotPlan
from rdetoolkit.graph.readers.base import DetectionDecision

MANIFEST_SCHEMA_VERSION: Final[int]
ArtifactRole = Literal["main_image", "individual", "html"]

@dataclass(frozen=True, slots=True)
class Artifact:
    figure_id: str
    kind: Literal["overlay", "individual"]
    role: ArtifactRole
    format: str
    renderer: str
    series_ids: tuple[str, ...]
    labels: tuple[str, ...]
    path: Path | None
    figure: Any | None
    replaced_existing: bool = False
    diagnostics: tuple[GraphDiagnostic, ...] = ()
    def manifest_entry(self) -> dict[str, Any]: ...
    def __post_init__(self) -> None: ...

@dataclass(frozen=True, slots=True)
class GraphResult:
    plan: PlotPlan
    artifacts: tuple[Artifact, ...]
    detection: DetectionDecision | None
    diagnostics: tuple[GraphDiagnostic, ...]
    def manifest(self) -> dict[str, Any]: ...
    def manifest_json(self) -> str: ...
