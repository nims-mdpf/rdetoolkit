"""Spec-first graph engine: ``render_graph`` (GE-03).

Fixed order: load the source, build the plan, plan every artifact (renderer selection
by declared capabilities, optional-dependency check, destination, within-run
uniqueness, ``on_existing``), render each figure, export, write. Nothing touches the
filesystem before the artifact plan is complete, and nothing is written before every
figure has rendered.

Renderers come from the caller's ``RendererRegistry`` or, by default, from a fresh
``builtin_renderers()`` registry created for this call (GE-07): an artifact goes to
the first registered renderer whose capabilities cover its format and figure kind.
Rendering runs inside ``mpl_runtime.style_scope`` so no rcParams leak to the caller.
Written handles are exported and closed through their renderer; in-memory handles
belong to the caller, and Matplotlib figures among them are detached first (GE-09).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from matplotlib.figure import Figure

from rdetoolkit.graph.exceptions import ArtifactCollisionError, PlotRequestError
from rdetoolkit.graph.naming import GraphDiagnostic, collision_key
from rdetoolkit.graph.plan import (
    UNIT_MISMATCH,
    UNIT_UNKNOWN,
    FigurePlan,
    PlotData,
    PlotPlan,
    SeriesPlan,
    _as_frames,
    build_plot_plan,
)
from rdetoolkit.graph.readers.base import DetectionDecision, TableData, TableReader
from rdetoolkit.graph.readers.registry import AUTO, ReaderRegistry, _load_table
from rdetoolkit.graph.renderers.base import GraphRenderer
from rdetoolkit.graph.renderers.mpl_runtime import DEFAULT_EXPORT_DPI, detach_figure, style_scope
from rdetoolkit.graph.renderers.registry import RendererRegistry, builtin_renderers, check_requirements
from rdetoolkit.graph.result import Artifact, ArtifactRole, GraphResult
from rdetoolkit.graph.spec import GraphSpec, OutputSpec


def render_graph(
    source: pd.DataFrame | Sequence[pd.DataFrame] | TableData | str | Path,
    spec: GraphSpec | None = None,
    *,
    output: OutputSpec | None = None,
    reader: str | TableReader = AUTO,
    readers: ReaderRegistry | None = None,
    renderers: RendererRegistry | None = None,
) -> GraphResult:
    """Plan and render a graph from a spec.

    Args:
        source: One DataFrame or a sequence of DataFrames (planned frame-major), a
            ``TableData``, or a file path read by a table reader.
        spec: What to plot; ``None`` uses ``GraphSpec()``.
        output: Where to write; ``None`` returns caller-owned in-memory handles
            (``Artifact.format == "figure"``) from the first renderer drawing each
            figure kind.
        reader: For path sources: a reader id, ``"auto"`` (the reader claiming the
            suffix) or a ``TableReader`` instance.
        readers: For path sources: a caller registry consulted before the builtin
            readers and the ``rdetoolkit.graph.readers`` entry points.
        renderers: The renderers to select from, in priority order; ``None`` uses a
            new ``builtin_renderers()`` registry (Matplotlib for images, Plotly for
            overlay HTML).

    Returns:
        The executed plan and one artifact per figure (and per format when written).

    Raises:
        TypeError: If ``source`` is not a DataFrame, a sequence of DataFrames, a
            ``TableData`` or a path, or ``renderers`` is not a ``RendererRegistry``.
        PlotRequestError: For an invalid spec or column reference, or
            (``reason="contradictory_switches"``) reader options with a non-path source.
        UnknownReaderError: For a reader id registered nowhere.
        AmbiguousFormatError: When several readers claim the path suffix under ``"auto"``.
        UnsupportedFormatError: For a format, or a format and figure kind, no renderer
            supports, before rendering.
        RendererUnavailableError: When a selected renderer's optional dependency is not
            installed, before rendering.
        OutputPathError: For an unsafe destination, before rendering.
        ArtifactCollisionError: For clashing destinations, or an existing file with
            ``on_existing="error"``, before rendering.
    """
    registry = _registry(renderers)
    frames, detection = _load_source(source, reader, readers)
    plan = build_plot_plan(frames, spec, base_name="plot" if output is None else output.base_name)
    data = PlotData(frames=frames)
    if output is None:
        artifacts = _render_in_memory(plan, data, registry)
    else:
        jobs = _plan_artifacts(plan, output, registry)
        artifacts = _render_to_sink(plan, data, jobs, output)
    return GraphResult(plan=plan, artifacts=artifacts, detection=detection, diagnostics=_result_diagnostics(plan, artifacts))


def _registry(renderers: RendererRegistry | None) -> RendererRegistry:
    """Use the caller's registry, or a new builtin one scoped to this call."""
    if renderers is None:
        return builtin_renderers()
    if not isinstance(renderers, RendererRegistry):
        msg = f"renderers must be a RendererRegistry or None, got {renderers!r}"
        raise TypeError(msg)
    return renderers


def _load_source(
    source: pd.DataFrame | Sequence[pd.DataFrame] | TableData | str | Path,
    reader: str | TableReader,
    readers: ReaderRegistry | None,
) -> tuple[tuple[pd.DataFrame, ...], DetectionDecision | None]:
    """Turn the source into frames; a path is read by the resolved table reader."""
    if isinstance(source, (str, Path)):
        table, decision = _load_table(source, reader=reader, readers=readers)
        return (table.frame,), decision
    if not (isinstance(reader, str) and reader == AUTO) or readers is not None:
        msg = "reader= and readers= apply to path sources only; this source is already a table"
        raise PlotRequestError(msg, reason="contradictory_switches")
    if isinstance(source, TableData):
        return (source.frame,), None
    return _as_frames(source), None


@dataclass(frozen=True, slots=True)
class _ArtifactJob:
    figure: FigurePlan
    fmt: str
    role: ArtifactRole
    filename: str
    path: Path
    replaced_existing: bool
    renderer: GraphRenderer


def _role(figure: FigurePlan, fmt: str) -> ArtifactRole:
    """Legacy routing: HTML -> html, overlay image -> main_image, individual image -> individual."""
    if fmt == "html":
        return "html"
    return "main_image" if figure.kind == "overlay" else "individual"


def _plan_artifacts(plan: PlotPlan, output: OutputSpec, registry: RendererRegistry) -> list[_ArtifactJob]:
    """Decide every renderer and destination and reject unusable ones before anything is rendered."""
    selected = _select_renderers(plan, output.formats, registry)
    jobs = [_artifact_job(figure, fmt, output, selected[figure.kind, fmt]) for figure in plan.figures for fmt in output.formats]
    _check_unique_destinations(jobs)
    existing = [str(job.path) for job in jobs if job.replaced_existing]
    if output.on_existing == "error" and existing:
        msg = f"Artifact destinations already exist (on_existing='error'): {existing}"
        raise ArtifactCollisionError(msg)
    return jobs


def _figure_kinds(plan: PlotPlan) -> list[str]:
    return list(dict.fromkeys(figure.kind for figure in plan.figures))


def _select_renderers(plan: PlotPlan, formats: Sequence[str], registry: RendererRegistry) -> dict[tuple[str, str], GraphRenderer]:
    """Pick one renderer per (figure kind, format); every pick must have its optional modules."""
    selected = {(kind, fmt): registry.for_format(fmt, kind) for kind in _figure_kinds(plan) for fmt in formats}
    _check_all_requirements(selected.values())
    return selected


def _check_all_requirements(renderers: Iterable[GraphRenderer]) -> None:
    for renderer in {id(item): item for item in renderers}.values():
        check_requirements(renderer)


def _artifact_job(figure: FigurePlan, fmt: str, output: OutputSpec, renderer: GraphRenderer) -> _ArtifactJob:
    role = _role(figure, fmt)
    filename = f"{figure.stem}.{fmt}"
    path = output.sink.resolve(role, filename)
    return _ArtifactJob(figure, fmt, role, filename, path, path.exists(), renderer)


def _check_unique_destinations(jobs: Sequence[_ArtifactJob]) -> None:
    """Fail when two artifacts of one run would land on the same file.

    Two destinations clash when they are in the same directory (compared exactly,
    after resolving symlinks) and their file names share a collision key (case and
    Unicode normalization, as on macOS / Windows). Directories differing only by
    case are different directories on a case-sensitive filesystem.
    """
    seen: dict[tuple[Path, str], str] = {}
    for job in jobs:
        key = (job.path.parent.resolve(), collision_key(job.path.name))
        if key in seen:
            msg = f"Artifacts {seen[key]!r} and {job.filename!r} resolve to the same destination {str(job.path)!r}"
            raise ArtifactCollisionError(msg)
        seen[key] = job.filename


def _render_to_sink(plan: PlotPlan, data: PlotData, jobs: Sequence[_ArtifactJob], output: OutputSpec) -> tuple[Artifact, ...]:
    """Render and export every figure first, then write.

    Each handle is closed through its renderer right after export, also when the
    export fails, so a failure never leaves a handle behind.
    """
    contents: dict[tuple[str, str], bytes] = {}
    for figure in plan.figures:
        for renderer, formats in _formats_by_renderer([job for job in jobs if job.figure.figure_id == figure.figure_id]):
            contents.update(_render_and_export(plan, figure, data, renderer, formats, output.dpi))
    artifacts = []
    for job in jobs:
        path = output.sink.write(job.role, job.filename, contents[job.figure.figure_id, job.fmt])
        artifacts.append(
            _artifact(plan, job.figure, job.role, job.fmt, job.renderer, path=path, replaced=job.replaced_existing),
        )
    return tuple(artifacts)


def _formats_by_renderer(jobs: Sequence[_ArtifactJob]) -> list[tuple[GraphRenderer, list[str]]]:
    """Group one figure's formats by renderer, in format order, so each renderer draws it once."""
    groups: dict[int, tuple[GraphRenderer, list[str]]] = {}
    for job in jobs:
        groups.setdefault(id(job.renderer), (job.renderer, []))[1].append(job.fmt)
    return list(groups.values())


def _render_and_export(
    plan: PlotPlan,
    figure: FigurePlan,
    data: PlotData,
    renderer: GraphRenderer,
    formats: Sequence[str],
    dpi: int,
) -> dict[tuple[str, str], bytes]:
    with style_scope():
        handle = renderer.render(plan, figure, data)
        try:
            return {(figure.figure_id, fmt): renderer.export(handle, fmt, dpi=dpi) for fmt in formats}
        finally:
            renderer.close(handle)


def _render_in_memory(plan: PlotPlan, data: PlotData, registry: RendererRegistry) -> tuple[Artifact, ...]:
    """Render caller-owned handles; Matplotlib figures are detached from the style scope.

    On failure the handles rendered so far are closed through their renderer, since
    the caller never receives them.
    """
    selected = {kind: registry.for_kind(kind) for kind in _figure_kinds(plan)}
    _check_all_requirements(selected.values())
    rendered: list[tuple[GraphRenderer, Any]] = []
    try:
        for figure in plan.figures:
            rendered.append(_render_handle(plan, figure, data, selected[figure.kind]))
    except BaseException:
        for renderer, handle in rendered:
            renderer.close(handle)
        raise
    return tuple(
        _artifact(plan, figure, _role(figure, "figure"), "figure", renderer, figure_handle=handle)
        for figure, (renderer, handle) in zip(plan.figures, rendered, strict=True)
    )


def _render_handle(
    plan: PlotPlan,
    figure: FigurePlan,
    data: PlotData,
    renderer: GraphRenderer,
) -> tuple[GraphRenderer, Any]:
    with style_scope():
        handle = renderer.render(plan, figure, data)
        if isinstance(handle, Figure):
            try:
                _detach(handle)
            except BaseException:
                renderer.close(handle)
                raise
    return renderer, handle


def _artifact(
    plan: PlotPlan,
    figure: FigurePlan,
    role: ArtifactRole,
    fmt: str,
    renderer: GraphRenderer,
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
        renderer=renderer.capabilities.renderer_id,
        series_ids=figure.series_ids,
        labels=labels,
        path=path,
        figure=figure_handle,
        replaced_existing=replaced,
        diagnostics=_figure_diagnostics(plan, figure) + _style_diagnostics(plan, renderer),
    )


def _style_diagnostics(plan: PlotPlan, renderer: GraphRenderer) -> tuple[GraphDiagnostic, ...]:
    """Report explicit rcParams that the renderer cannot apply (for example Plotly)."""
    caps = renderer.capabilities
    if plan.origins.get("style.rc_params") != "explicit" or caps.applies_rc_params:
        return ()
    message = (
        f"Renderer {caps.renderer_id!r} does not apply StyleSpec.rc_params (Matplotlib rcParams); "
        "they were ignored for its artifacts"
    )
    return (GraphDiagnostic(code="style_ignored", severity="info", message=message),)


def _result_diagnostics(plan: PlotPlan, artifacts: Sequence[Artifact]) -> tuple[GraphDiagnostic, ...]:
    """The plan's diagnostics, then each distinct render-time diagnostic once, in artifact order."""
    extra = [item for artifact in artifacts for item in artifact.diagnostics if item not in plan.diagnostics]
    return plan.diagnostics + tuple(dict.fromkeys(extra))


def _figure_diagnostics(plan: PlotPlan, figure: FigurePlan) -> tuple[GraphDiagnostic, ...]:
    """The plan diagnostics that describe this figure, in plan order."""
    return tuple(item for item in plan.diagnostics if _applies_to(plan, item, figure))


def _applies_to(plan: PlotPlan, diagnostic: GraphDiagnostic, figure: FigurePlan) -> bool:
    """Whether a plan diagnostic describes ``figure``.

    Unit diagnostics name series (not figures) and describe a shared overlay axis:
    ``unit_mismatch`` belongs to the overlay figures of those series that mix units,
    ``unit_unknown`` to the overlay figures holding the unit-less series. Every other
    diagnostic (``filename_collision``) names the figures it concerns.
    """
    overlaps = not set(diagnostic.series_ids).isdisjoint(figure.series_ids)
    if diagnostic.code == UNIT_MISMATCH:
        return figure.kind == "overlay" and overlaps and _mixes_units(plan, figure)
    if diagnostic.code == UNIT_UNKNOWN:
        return figure.kind == "overlay" and overlaps
    return figure.figure_id in diagnostic.series_ids


def _mixes_units(plan: PlotPlan, figure: FigurePlan) -> bool:
    units = {_series_of(plan, series_id).unit for series_id in figure.series_ids} - {None}
    return len(units) > 1


def _series_of(plan: PlotPlan, series_id: str) -> SeriesPlan:
    return next(entry for entry in plan.series if entry.series_id == series_id)


def _detach(fig: Figure) -> None:
    """Freeze late-bound layout and font sizes so drawing outside the style scope is stable."""
    detach_figure(fig, dpi=DEFAULT_EXPORT_DPI)
