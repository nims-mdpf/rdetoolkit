from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final, Literal

from rdetoolkit.graph.outputs import ArtifactSink

SPEC_VERSION: Final[int]
ColumnRef = int | str
AxisLimits = tuple[float | None, float | None]
Origin = Literal["explicit", "default", "derived"]
INVALID_SPEC: Final[str]

@dataclass(frozen=True, slots=True)
class SeriesSpec:
    y: ColumnRef
    x: ColumnRef | None = None
    direction: ColumnRef | None = None
    label: str | None = None
    unit: str | None = None

@dataclass(frozen=True, slots=True)
class AxisSpec:
    label: str | None = None
    scale: Literal["linear", "log"] = "linear"
    limits: AxisLimits | None = None
    grid: bool = False
    invert: bool = False
    tick_format: Literal["auto", "plain", "sci", "eng"] = "auto"

@dataclass(frozen=True, slots=True)
class LegendSpec:
    max_items: int | None = 20
    info: str | None = None
    loc: str | int | None = None
    policy: Literal["legacy", "auto", "inside", "outside_right", "outside_bottom", "hide"] = "legacy"
    outside_threshold: int = 8
    bottom_threshold: int | None = 21
    ncol: int | None = None

@dataclass(frozen=True, slots=True)
class StyleSpec:
    figure_size: tuple[float, float] | None = None
    rc_params: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class GraphSpec:
    version: int = ...
    x: ColumnRef | None = None
    x_default: Literal["first_column", "index"] = "first_column"
    series: tuple[SeriesSpec, ...] = ()
    layout: Literal["auto", "overlay", "individual", "both"] = "auto"
    mark: Literal["line", "scatter"] = "line"
    title: str | None = None
    x_axis: AxisSpec = ...
    y_axis: AxisSpec = ...
    legend: LegendSpec = ...
    direction_filter: tuple[str, ...] = ()
    direction_colors: Mapping[str, str] = field(default_factory=dict)
    label_style: Literal["humanized", "header", "raw"] = "humanized"
    unit_policy: Literal["error", "split", "warn", "allow"] = "error"
    style: StyleSpec = ...

@dataclass(frozen=True, slots=True)
class OutputSpec:
    sink: ArtifactSink
    formats: tuple[str, ...] = ("png",)
    base_name: str = "plot"
    on_existing: Literal["overwrite", "error"] = "overwrite"
    dpi: int = 300
