"""Spec-first graph engine: ``render_graph`` (GE-03).

Fixed order: load the source, build the plan, plan every artifact (format support,
destination, within-run uniqueness, ``on_existing``), render each figure, export,
write. Nothing touches the filesystem before the artifact plan is complete, and
nothing is written before every figure has rendered.

Rendering runs inside ``mpl_runtime.style_scope`` so no rcParams leak to the caller,
and every figure is a pyplot-free ``Figure`` (GE-09): written figures are simply
dropped after export, in-memory ones belong to the caller and are detached first.
Until the renderers consume plans directly (GE-06), figures are drawn by the legacy
``MatplotlibRenderer`` with a plan-driven subclass and a ``PlotConfig`` adapter.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from rdetoolkit.graph.config import DEFAULT_FIG_SIZE
from rdetoolkit.graph.exceptions import ArtifactCollisionError, UnsupportedFormatError
from rdetoolkit.graph.models import AxisConfig, DirectionConfig, LegendConfig, OutputConfig, PlotConfig, PlotMode
from rdetoolkit.graph.naming import GraphDiagnostic, collision_key
from rdetoolkit.graph.plan import FigurePlan, PlotData, PlotPlan, SeriesPlan, _as_frames, build_plot_plan
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer
from rdetoolkit.graph.renderers.mpl_runtime import DEFAULT_EXPORT_DPI, detach_figure, export_figure, new_figure, style_scope
from rdetoolkit.graph.result import Artifact, ArtifactRole, GraphResult
from rdetoolkit.graph.spec import AxisSpec, GraphSpec, OutputSpec

RENDERER_ID: Final = "matplotlib"
IMAGE_FORMATS: Final = ("png", "svg", "pdf")
_LINE_WIDTH: Final = 1.5


def render_graph(
    source: pd.DataFrame | Sequence[pd.DataFrame],
    spec: GraphSpec | None = None,
    *,
    output: OutputSpec | None = None,
) -> GraphResult:
    """Plan and render a graph from a spec.

    Args:
        source: One DataFrame or a sequence of DataFrames (planned frame-major).
        spec: What to plot; ``None`` uses ``GraphSpec()``.
        output: Where to write; ``None`` returns caller-owned in-memory figures
            (``Artifact.format == "figure"``).

    Returns:
        The executed plan and one artifact per figure (and per format when written).

    Raises:
        TypeError: If ``source`` is not a DataFrame or a sequence of DataFrames.
        PlotRequestError: For an invalid spec or column reference.
        UnsupportedFormatError: For a format no renderer supports, before rendering.
        OutputPathError: For an unsafe destination, before rendering.
        ArtifactCollisionError: For clashing destinations, or an existing file with
            ``on_existing="error"``, before rendering.
    """
    frames = _load_source(source)
    plan = build_plot_plan(frames, spec, base_name="plot" if output is None else output.base_name)
    data = PlotData(frames=frames)
    if output is None:
        artifacts = _render_in_memory(plan, data)
    else:
        jobs = _plan_artifacts(plan, output)
        artifacts = _render_to_sink(plan, data, jobs, output)
    return GraphResult(plan=plan, artifacts=artifacts, detection=None, diagnostics=plan.diagnostics)


def _load_source(source: pd.DataFrame | Sequence[pd.DataFrame]) -> tuple[pd.DataFrame, ...]:
    """Turn the source into frames (path sources and readers arrive with GE-04)."""
    return _as_frames(source)


@dataclass(frozen=True, slots=True)
class _ArtifactJob:
    figure: FigurePlan
    fmt: str
    role: ArtifactRole
    filename: str
    path: Path
    replaced_existing: bool


def _role(figure: FigurePlan) -> ArtifactRole:
    """Legacy image routing: overlay -> main_image, individual -> individual (HTML arrives with GE-14)."""
    return "main_image" if figure.kind == "overlay" else "individual"


def _plan_artifacts(plan: PlotPlan, output: OutputSpec) -> list[_ArtifactJob]:
    """Decide every destination and reject unusable ones before anything is rendered."""
    _check_formats(output.formats)
    jobs = [_artifact_job(figure, fmt, output) for figure in plan.figures for fmt in output.formats]
    _check_unique_destinations(jobs)
    existing = [str(job.path) for job in jobs if job.replaced_existing]
    if output.on_existing == "error" and existing:
        msg = f"Artifact destinations already exist (on_existing='error'): {existing}"
        raise ArtifactCollisionError(msg)
    return jobs


def _check_formats(formats: Sequence[str]) -> None:
    # HTML (Plotly) through the spec API arrives with injectable renderers (GE-07/GE-14).
    for fmt in formats:
        if fmt not in IMAGE_FORMATS:
            msg = f"Unsupported output format {fmt!r} for render_graph; supported formats: {list(IMAGE_FORMATS)}"
            raise UnsupportedFormatError(msg)


def _artifact_job(figure: FigurePlan, fmt: str, output: OutputSpec) -> _ArtifactJob:
    role = _role(figure)
    filename = f"{figure.stem}.{fmt}"
    path = output.sink.resolve(role, filename)
    return _ArtifactJob(figure, fmt, role, filename, path, path.exists())


def _check_unique_destinations(jobs: Sequence[_ArtifactJob]) -> None:
    """Fail when two artifacts of one run would land on the same file (case-insensitively)."""
    seen: dict[str, str] = {}
    for job in jobs:
        key = collision_key(str(job.path))
        if key in seen:
            msg = f"Artifacts {seen[key]!r} and {job.filename!r} resolve to the same destination {str(job.path)!r}"
            raise ArtifactCollisionError(msg)
        seen[key] = job.filename


def _render_to_sink(plan: PlotPlan, data: PlotData, jobs: Sequence[_ArtifactJob], output: OutputSpec) -> tuple[Artifact, ...]:
    """Render and export every figure first, then write.

    Engine-owned figures are not pyplot-registered, so they are released by
    dropping them after export, also when a later figure fails.
    """
    contents: dict[tuple[str, str], bytes] = {}
    for figure in plan.figures:
        formats = [job.fmt for job in jobs if job.figure.figure_id == figure.figure_id]
        with style_scope():
            fig = _render_figure(plan, figure, data)
            for fmt in formats:
                contents[figure.figure_id, fmt] = _export(fig, fmt, output.dpi)
    artifacts = []
    for job in jobs:
        path = output.sink.write(job.role, job.filename, contents[job.figure.figure_id, job.fmt])
        artifacts.append(_artifact(plan, job.figure, job.role, job.fmt, path=path, replaced=job.replaced_existing))
    return tuple(artifacts)


def _render_in_memory(plan: PlotPlan, data: PlotData) -> tuple[Artifact, ...]:
    """Render caller-owned figures, detached from the style scope they were drawn in.

    The figures are not pyplot-registered: on failure the handles rendered so far
    are simply dropped, and the caller never has to ``plt.close`` them.
    """
    figures: list[Figure] = []
    for figure in plan.figures:
        with style_scope():
            fig = _render_figure(plan, figure, data)
            _detach(fig)
            figures.append(fig)
    return tuple(
        _artifact(plan, figure, _role(figure), "figure", figure_handle=fig)
        for figure, fig in zip(plan.figures, figures, strict=True)
    )


def _artifact(
    plan: PlotPlan,
    figure: FigurePlan,
    role: ArtifactRole,
    fmt: str,
    *,
    path: Path | None = None,
    figure_handle: Any = None,
    replaced: bool = False,
) -> Artifact:
    labels = tuple(_series_of(plan, series_id).label for series_id in figure.series_ids)
    return Artifact(
        figure_id=figure.figure_id,
        kind=figure.kind,
        role=role,
        format=fmt,
        renderer=RENDERER_ID,
        series_ids=figure.series_ids,
        labels=labels,
        path=path,
        figure=figure_handle,
        replaced_existing=replaced,
        diagnostics=_figure_diagnostics(plan.diagnostics, figure),
    )


def _figure_diagnostics(diagnostics: Sequence[GraphDiagnostic], figure: FigurePlan) -> tuple[GraphDiagnostic, ...]:
    return tuple(item for item in diagnostics if figure.figure_id in item.series_ids)


def _series_of(plan: PlotPlan, series_id: str) -> SeriesPlan:
    return next(entry for entry in plan.series if entry.series_id == series_id)


def _export(fig: Figure, fmt: str, dpi: int) -> bytes:
    """Export a figure the way the legacy ``FileWriter`` saves it (tight bounding box)."""
    return export_figure(fig, fmt, dpi=dpi)


def _detach(fig: Figure) -> None:
    """Freeze late-bound layout and font sizes so drawing outside the style scope is stable."""
    detach_figure(fig, dpi=DEFAULT_EXPORT_DPI)


def _render_figure(plan: PlotPlan, figure: FigurePlan, data: PlotData) -> Figure:
    config = _plan_to_legacy_config(plan, figure)
    first = _series_of(plan, figure.series_ids[0])
    return _PlanRenderer(plan, figure, data).render_overlay(data.frames[first.frame], config)


def _legacy_axis(axis: AxisSpec, label: str) -> AxisConfig:
    # Limits pass through unvalidated until GE-13; a None side stays automatic.
    return AxisConfig(
        label=label,
        scale=axis.scale,
        grid=axis.grid,
        invert=axis.invert,
        lim=cast("tuple[float, float] | None", axis.limits),
        tick_format=axis.tick_format,
    )


def _plan_to_legacy_config(plan: PlotPlan, figure: FigurePlan) -> PlotConfig:
    """Adapt one planned figure to the ``PlotConfig`` the legacy renderer reads.

    Columns are not carried: the plan-driven renderer draws from ``PlotData``.
    """
    legend = plan.legend
    return PlotConfig(
        mode=PlotMode.OVERLAY if figure.kind == "overlay" else PlotMode.INDIVIDUAL,
        title=figure.title,
        x_axis=_legacy_axis(plan.x_axis, figure.x_label),
        y_axis=_legacy_axis(plan.y_axis, figure.y_label),
        legend=LegendConfig(
            max_items=legend.max_items,
            info=legend.info,
            loc=legend.loc,
            policy=legend.policy,
            outside_threshold=legend.outside_threshold,
            bottom_threshold=legend.bottom_threshold,
            ncol=legend.ncol,
        ),
        direction=DirectionConfig(
            colors=dict(plan.direction_colors),
            use_custom_colors=bool(plan.direction_colors),
        ),
        output=OutputConfig(base_name=figure.stem),
    )


class _PlanRenderer(MatplotlibRenderer):
    """Draw one planned figure with the legacy house style (axes, ticks, legend).

    Series selection, labels, legend visibility and colours come from the plan;
    everything else is the legacy renderer. Deleted when GE-06 lands.
    """

    def __init__(self, plan: PlotPlan, figure: FigurePlan, data: PlotData) -> None:
        self._plan = plan
        self._figure = figure
        self._data = data

    def _new_figure(self) -> tuple[Figure, Any]:
        # Engine figures are never pyplot-registered (GE-09); size from the legacy renderer.
        return new_figure(DEFAULT_FIG_SIZE)

    def _resolve_overlay_columns(self, df: pd.DataFrame, config: PlotConfig) -> tuple[list[int], list[int], list[int | None]]:
        return [], [], []

    def _plot_overlay_series(
        self,
        ax: Any,
        df: pd.DataFrame,
        config: PlotConfig,
        x_cols: list[int],
        y_cols: list[int],
        direction_cols: list[int | None],
        color_map: dict[object, str],
        direction_filters: set[str],
    ) -> tuple[list[Any], list[str]]:
        series = [_series_of(self._plan, series_id) for series_id in self._figure.series_ids]
        if self._figure.kind == "individual":
            return self._draw_individual(ax, series[0], color_map)
        handles: list[Any] = []
        labels: list[str] = []
        for entry in series:
            first = self._draw_overlay_series(ax, entry, color_map)
            if first is not None and entry.show_in_legend:
                handles.append(first)
                labels.append(entry.label)
        return handles, labels

    def _draw_overlay_series(self, ax: Any, entry: SeriesPlan, color_map: dict[object, str]) -> Any:
        """Draw one overlay series; only its first segment carries the legend label."""
        palette = plt.cm.tab10.colors  # type: ignore[attr-defined]
        base_color = palette[entry.color_index % len(palette)]
        first = None
        for direction, x_values, y_values in self._data.segments(entry):
            color = base_color if direction is None else color_map.get(direction, base_color)
            artist = self._mark(ax, x_values, y_values, color=color, label=entry.label if first is None else "_nolegend_")
            first = artist if first is None else first
        return first

    def _draw_individual(self, ax: Any, entry: SeriesPlan, color_map: dict[object, str]) -> tuple[list[Any], list[str]]:
        """The v1 individual look: default colour without directions, one entry per direction."""
        segments = self._data.segments(entry)
        if entry.direction_index is None:
            _, x_values, y_values = segments[0]
            self._mark(ax, x_values, y_values)
            return [], []
        handles: list[Any] = []
        labels: list[str] = []
        for direction, x_values, y_values in segments:
            colors = {"color": color_map[direction]} if direction in color_map else {}
            handles.append(self._mark(ax, x_values, y_values, label=direction, **colors))
            labels.append(str(direction))
        # v1 draws an individual legend only when there is more than one entry.
        return (handles, labels) if len(handles) > 1 else ([], [])

    def _mark(self, ax: Any, x_values: Any, y_values: Any, **kwargs: Any) -> Any:
        if self._plan.mark == "scatter":
            return ax.scatter(x_values, y_values, **kwargs)
        line, = ax.plot(x_values, y_values, linewidth=_LINE_WIDTH, **kwargs)
        return line

    def _apply_legend(self, ax: Any, handles: list[Any], labels: list[str], config: PlotConfig) -> None:
        if self._figure.kind == "individual" and not handles:
            return
        super()._apply_legend(ax, handles, labels, config)

    def _configure_axes(self, ax: Any, config: PlotConfig, title: str | None) -> None:
        super()._configure_axes(ax, config, self._figure.title)
        # The legacy renderer grids both axes when either asks; honour each axis.
        if self._plan.x_axis.grid != self._plan.y_axis.grid:
            (ax.yaxis if self._plan.x_axis.grid else ax.xaxis).grid(False)
