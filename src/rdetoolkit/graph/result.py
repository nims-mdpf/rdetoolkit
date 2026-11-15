"""Results of the spec API: the plan that was executed and the artifacts it produced."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from rdetoolkit.graph.naming import GraphDiagnostic
from rdetoolkit.graph.plan import PlotPlan

MANIFEST_SCHEMA_VERSION: Final = 1
ArtifactRole = Literal["main_image", "individual", "html"]


@dataclass(frozen=True, slots=True)
class Artifact:
    """One produced output: a written file or a caller-owned in-memory figure.

    Exactly one of ``path`` and ``figure`` is set.

    Attributes:
        figure_id: Id of the planned figure (``"overlay"`` or a series id).
        kind: ``"overlay"`` or ``"individual"``.
        role: ``"main_image"``, ``"individual"`` or ``"html"``.
        format: ``"png"``, ``"svg"``, ``"pdf"``, ``"html"``, or ``"figure"`` for an
            in-memory handle.
        renderer: Id of the renderer that produced it.
        series_ids: Series drawn in the figure.
        labels: Their legend labels, in the same order.
        path: Written file, or ``None`` for an in-memory figure.
        figure: In-memory figure owned by the caller, or ``None`` when written.
        replaced_existing: Whether writing replaced a file that already existed.
        diagnostics: Findings that concern this figure.
    """

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

    def __post_init__(self) -> None:
        """Enforce the path-xor-figure invariant.

        Raises:
            ValueError: If neither or both of ``path`` and ``figure`` are set.
        """
        if (self.path is None) == (self.figure is None):
            msg = "Artifact needs exactly one of path or figure"
            raise ValueError(msg)

    def manifest_entry(self) -> dict[str, Any]:
        """Return the machine-independent manifest record of this artifact.

        Only the file name is recorded, never the absolute path, so the entry is
        byte-stable across machines.

        Returns:
            The JSON-safe record.
        """
        return {
            "figure_id": self.figure_id,
            "kind": self.kind,
            "role": self.role,
            "format": self.format,
            "renderer": self.renderer,
            "series_ids": list(self.series_ids),
            "labels": list(self.labels),
            "file": None if self.path is None else self.path.name,
            "replaced_existing": self.replaced_existing,
            "diagnostics": [_diagnostic_entry(item) for item in self.diagnostics],
        }


@dataclass(frozen=True, slots=True)
class GraphResult:
    """Everything one ``render_graph`` call decided and produced.

    Attributes:
        plan: The executed plan.
        artifacts: Outputs in plan figure order, then output format order.
        detection: Table-format detection decision; ``None`` for DataFrame sources.
        diagnostics: Findings of the whole request.
    """

    plan: PlotPlan
    artifacts: tuple[Artifact, ...]
    detection: object | None
    diagnostics: tuple[GraphDiagnostic, ...]

    def manifest(self) -> dict[str, Any]:
        """Return the versioned, machine-independent manifest of this result.

        Returns:
            ``{"schema_version", "artifacts", "diagnostics", "detection"}``.
        """
        return {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "artifacts": [artifact.manifest_entry() for artifact in self.artifacts],
            "diagnostics": [_diagnostic_entry(item) for item in self.diagnostics],
            "detection": None if self.detection is None else str(self.detection),
        }

    def manifest_json(self) -> str:
        """Return the manifest as stable JSON text.

        The engine never writes it; callers that want a file write this text.

        Returns:
            JSON with sorted keys, two-space indentation and a trailing newline.
        """
        return json.dumps(self.manifest(), sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def _diagnostic_entry(diagnostic: GraphDiagnostic) -> dict[str, Any]:
    return {
        "code": diagnostic.code,
        "severity": diagnostic.severity,
        "message": diagnostic.message,
        "series_ids": list(diagnostic.series_ids),
    }
