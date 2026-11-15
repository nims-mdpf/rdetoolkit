from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from rdetoolkit.graph.naming import GraphDiagnostic
from rdetoolkit.graph.plan import PlotPlan

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

@dataclass(frozen=True, slots=True)
class GraphResult:
    plan: PlotPlan
    artifacts: tuple[Artifact, ...]
    detection: object | None
    diagnostics: tuple[GraphDiagnostic, ...]
    def manifest(self) -> dict[str, Any]: ...
    def manifest_json(self) -> str: ...
