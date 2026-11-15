from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

import pandas as pd

from rdetoolkit.graph.naming import GraphDiagnostic as GraphDiagnostic
from rdetoolkit.graph.spec import AxisSpec, GraphSpec, LegendSpec, Origin, StyleSpec

__all__ = ["FigurePlan", "GraphDiagnostic", "PlotData", "PlotPlan", "SeriesPlan", "build_plot_plan", "column_position"]

OVERLAY_FIGURE_ID: Final[str]
UNIT_MISMATCH: Final[str]
UNIT_UNKNOWN: Final[str]

@dataclass(frozen=True, slots=True)
class SeriesPlan:
    series_id: str
    frame: int
    x_index: int | None
    y_index: int
    x_name: str
    y_name: str
    direction_index: int | None
    directions: tuple[str, ...]
    label: str
    show_in_legend: bool
    color_index: int
    header_series: str | None
    header_label: str
    unit: str | None
    unit_group: int

@dataclass(frozen=True, slots=True)
class FigurePlan:
    figure_id: str
    kind: Literal["overlay", "individual"]
    series_ids: tuple[str, ...]
    title: str | None
    x_label: str
    y_label: str
    stem: str

@dataclass(frozen=True, slots=True)
class PlotPlan:
    spec_version: int
    mark: Literal["line", "scatter"]
    series: tuple[SeriesPlan, ...]
    figures: tuple[FigurePlan, ...]
    x_axis: AxisSpec
    y_axis: AxisSpec
    legend: LegendSpec
    direction_colors: Mapping[str, str]
    style: StyleSpec
    unit_groups: tuple[tuple[str | None, tuple[str, ...]], ...]
    diagnostics: tuple[GraphDiagnostic, ...]
    origins: Mapping[str, Origin]
    def to_dict(self) -> dict[str, Any]: ...
    def with_labels(self, labels: Sequence[str]) -> PlotPlan: ...

@dataclass(frozen=True, slots=True)
class PlotData:
    frames: tuple[pd.DataFrame, ...]
    def segments(self, series: SeriesPlan) -> tuple[tuple[str | None, Any, Any], ...]: ...

def build_plot_plan(
    frames: pd.DataFrame | Sequence[pd.DataFrame],
    spec: GraphSpec | None = None,
    *,
    base_name: str = "plot",
) -> PlotPlan: ...
def column_position(frame: pd.DataFrame, label: Hashable, role: str) -> int: ...
def _as_frames(frames: pd.DataFrame | Sequence[pd.DataFrame]) -> tuple[pd.DataFrame, ...]: ...
