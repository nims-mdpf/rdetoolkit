"""Resolved, immutable plotting plans (GE-03).

``build_plot_plan`` turns DataFrames plus a ``GraphSpec`` into a ``PlotPlan``: which
columns every series uses, its final label and unit, which figures are produced,
their axis labels, titles and reserved file stems, and where every decision came
from (``origins``). The plan holds no data, so it can be compared, snapshotted
(``to_dict``) and handed to any renderer. ``PlotData`` is the only place that turns
a plan back into row selections.

All validation happens here, before anything is rendered or written.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

import pandas as pd

from rdetoolkit.graph.config import DEFAULT_FIG_SIZE, DEFAULT_PLOT_PARAMS
from rdetoolkit.graph.exceptions import PlotRequestError
from rdetoolkit.graph.naming import DEFAULT_BASE_STEM, GraphDiagnostic, reserve_stems, sanitize_stem, series_stem
from rdetoolkit.graph.spec import AxisSpec, ColumnRef, GraphSpec, LegendSpec, Origin, SeriesSpec, StyleSpec
from rdetoolkit.graph.textutils import parse_header
from rdetoolkit.graph.validation import validate_axis_limits

__all__ = [
    "FigurePlan",
    "GraphDiagnostic",
    "PlotData",
    "PlotPlan",
    "SeriesPlan",
    "build_plot_plan",
]

OVERLAY_FIGURE_ID = "overlay"
_INDEX_NAME = "index"
_DEFAULT_INDIVIDUAL_TITLE = "Plot"
_NO_SERIES_MESSAGE = "DataFrame must have at least one y column for plotting"


@dataclass(frozen=True, slots=True)
class SeriesPlan:
    """One resolved series: positional columns, label, unit and legend role.

    Attributes:
        series_id: ``"s000"``, ``"s001"``, ... = position in ``PlotPlan.series``.
        frame: Index into ``PlotData.frames``.
        x_index: Column position of x; ``None`` plots against the frame index.
        y_index: Column position of y.
        x_name: Header of the x column (``str``), or the index name.
        y_name: Header of the y column (``str``).
        direction_index: Column position of the direction column, if any.
        directions: Normalized direction values that will be drawn, in first
            appearance order, after the direction filter; ``()`` without a column.
        label: Final legend label.
        show_in_legend: ``True`` only for the first series of a label that draws
            something; ``False`` for later series with an equal label and for a
            series whose rows the direction filter removed entirely.
        color_index: Position-based palette index, identical for every backend.
        header_series: Series prefix parsed from the y header, un-humanized.
        header_label: Label part of the y header, un-humanized.
        unit: Unit of the series; ``None`` = unknown.
        unit_group: Index into ``PlotPlan.unit_groups``.
    """

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
    """One figure to produce.

    Attributes:
        figure_id: ``"overlay"`` or the series id of an individual figure.
        kind: ``"overlay"`` or ``"individual"``.
        series_ids: Series drawn in this figure, in plan order.
        title: Figure title (``None`` = no title).
        x_label: Final x axis label.
        y_label: Final y axis label.
        stem: Reserved file-name stem, unique within the plan.
    """

    figure_id: str
    kind: Literal["overlay", "individual"]
    series_ids: tuple[str, ...]
    title: str | None
    x_label: str
    y_label: str
    stem: str


@dataclass(frozen=True, slots=True)
class PlotPlan:
    """The complete, data-free decision record of one graph request.

    Attributes:
        spec_version: ``GraphSpec.version`` the plan was built from.
        mark: ``"line"`` or ``"scatter"``.
        series: Every series, frame-major, in selection order.
        figures: Overlay figure first, then individual figures in series order.
        x_axis: X axis settings.
        y_axis: Y axis settings.
        legend: Legend settings.
        direction_colors: Caller-supplied colour per direction value only.
        style: Resolved style (concrete figure size, rcParams over the defaults).
        unit_groups: ``(unit, series_ids)`` per unit group, first-appearance order.
        diagnostics: Non-fatal findings made while planning.
        origins: ``"explicit"``, ``"default"`` or ``"derived"`` per decision key
            (``"title"``, ``"x"``, ``"series"``, ``"x_axis.label"``,
            ``"series[s000].label"``, ``"style.figure_size"``, ...).
    """

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

    def __post_init__(self) -> None:
        """Freeze the mapping fields so a plan cannot change after it was built."""
        object.__setattr__(self, "direction_colors", MappingProxyType(dict(self.direction_colors)))
        object.__setattr__(self, "origins", MappingProxyType(dict(self.origins)))

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic, JSON-safe representation for snapshots.

        Mapping keys are sorted at every level, tuples become lists and values
        without a JSON form are rendered with ``str``.

        Returns:
            The plan as nested dicts and lists.
        """
        result: dict[str, Any] = _jsonable(self)
        return result

    def with_labels(self, labels: Sequence[str]) -> PlotPlan:
        """Return a copy whose series carry the given legend labels.

        Legend visibility and individual figure titles are recomputed; the
        label origins become ``"explicit"``. File stems do not change.

        Args:
            labels: One label per series, in plan order.

        Returns:
            The relabelled plan.

        Raises:
            ValueError: If the number of labels differs from the number of series.
        """
        labels = [str(label) for label in labels]
        if len(labels) != len(self.series):
            msg = f"{len(labels)} labels for {len(self.series)} series"
            raise ValueError(msg)
        seen: set[str] = set()
        series: list[SeriesPlan] = []
        for current, label in zip(self.series, labels, strict=True):
            owns_label = _draws(current) and label not in seen
            series.append(dataclasses.replace(current, label=label, show_in_legend=owns_label))
            if owns_label:
                seen.add(label)
        relabelled = {entry.series_id: entry for entry in series}
        figures = tuple(_relabel_figure(figure, self.series, relabelled) for figure in self.figures)
        origins = dict(self.origins)
        origins.update({f"series[{entry.series_id}].label": "explicit" for entry in series})
        return dataclasses.replace(self, series=tuple(series), figures=figures, origins=origins)


@dataclass(frozen=True, slots=True)
class PlotData:
    """The frames a plan refers to, kept apart from the plan itself.

    Attributes:
        frames: DataFrames addressed by ``SeriesPlan.frame``.
    """

    frames: tuple[pd.DataFrame, ...]

    def segments(self, series: SeriesPlan) -> tuple[tuple[str | None, Any, Any], ...]:
        """Return the rows of one series, split by direction.

        Args:
            series: A series of a plan built from these frames.

        Returns:
            ``((direction, x_values, y_values), ...)`` in ``series.directions``
            order; a single ``(None, x, y)`` segment without a direction column,
            and ``()`` when the direction filter removed every value.
        """
        frame = self.frames[series.frame]
        x_values: Any = frame.index if series.x_index is None else frame.iloc[:, series.x_index]
        y_values = frame.iloc[:, series.y_index]
        if series.direction_index is None:
            return ((None, x_values, y_values),)
        normalized = frame.iloc[:, series.direction_index].map(_direction_or_none)
        segments = []
        for direction in series.directions:
            mask = (normalized == direction).to_numpy()
            segments.append((direction, x_values[mask], y_values[mask]))
        return tuple(segments)


def build_plot_plan(
    frames: pd.DataFrame | Sequence[pd.DataFrame],
    spec: GraphSpec | None = None,
    *,
    base_name: str = "plot",
) -> PlotPlan:
    """Resolve a spec against one or more DataFrames into a plan.

    Rules: columns are resolved by position (a label must match exactly one
    column); several frames are planned frame-major with the same selections;
    file stems are reserved for every figure before anything is rendered.

    Args:
        frames: One DataFrame or a sequence of DataFrames.
        spec: The graph spec; ``None`` uses ``GraphSpec()``.
        base_name: Base file name of the overlay and prefix of individual stems.

    Returns:
        The resolved plan.

    Raises:
        TypeError: If ``frames`` is not a DataFrame or a sequence of DataFrames.
        PlotRequestError: ``reason="unknown_column"`` / ``"ambiguous_column"`` for
            a column reference that matches no / several columns;
            ``reason="invalid_axis_limits"`` for invalid ``AxisSpec.limits``.
        ValueError: If the request selects no series ("at least one y column").
    """
    frames_tuple = _as_frames(frames)
    spec = GraphSpec() if spec is None else spec
    # Reject invalid limits before any column is resolved; the plan keeps them as given.
    validate_axis_limits(spec.x_axis.limits, scale=spec.x_axis.scale, axis="x")
    validate_axis_limits(spec.y_axis.limits, scale=spec.y_axis.scale, axis="y")
    series = _plan_series(frames_tuple, spec)
    if not series:
        raise ValueError(_NO_SERIES_MESSAGE)
    figures, diagnostics = _plan_figures(series, spec, base_name)
    first_unit = next((entry.unit for entry in series if entry.unit is not None), None)
    return PlotPlan(
        spec_version=spec.version,
        mark=spec.mark,
        series=series,
        figures=figures,
        x_axis=spec.x_axis,
        y_axis=spec.y_axis,
        legend=spec.legend,
        direction_colors=spec.direction_colors,
        style=_resolve_style(spec.style),
        # Unit grouping arrives with GE-11; until then every series shares one group.
        unit_groups=((first_unit, tuple(entry.series_id for entry in series)),),
        diagnostics=diagnostics,
        origins=_origins(spec, series),
    )


def _as_frames(frames: pd.DataFrame | Sequence[pd.DataFrame]) -> tuple[pd.DataFrame, ...]:
    """Normalize one DataFrame or a sequence of DataFrames into a tuple.

    Args:
        frames: The frames to plot.

    Returns:
        The frames as a tuple.

    Raises:
        TypeError: If ``frames`` (or one of its items) is not a DataFrame; a
            ``str``/``bytes``/``Path`` is rejected rather than iterated.
    """
    if isinstance(frames, pd.DataFrame):
        return (frames,)
    if isinstance(frames, (str, bytes, Path)) or not isinstance(frames, Sequence):
        msg = f"expected a pandas DataFrame or a sequence of DataFrames, got {type(frames).__name__}"
        raise TypeError(msg)
    for item in frames:
        if not isinstance(item, pd.DataFrame):
            msg = f"expected a sequence of DataFrames, found {type(item).__name__}"
            raise TypeError(msg)
    return tuple(frames)


def _plan_series(frames: tuple[pd.DataFrame, ...], spec: GraphSpec) -> tuple[SeriesPlan, ...]:
    """Resolve the selections of every frame, frame-major, and assign legend roles once."""
    series: list[SeriesPlan] = []
    seen_labels: set[str] = set()
    for frame_index, frame in enumerate(frames):
        for selection in _selections(frame, spec):
            entry = _series_plan(len(series), frame_index, frame, selection, spec, seen_labels)
            if entry.show_in_legend:
                seen_labels.add(entry.label)
            series.append(entry)
    return tuple(series)


def _selections(frame: pd.DataFrame, spec: GraphSpec) -> tuple[SeriesSpec, ...]:
    """Return the explicit series, or every column except the x column by default."""
    if spec.series:
        return spec.series
    if frame.shape[1] == 0:
        return ()
    excluded = _resolve_x(frame, spec.x, spec)
    return tuple(SeriesSpec(y=position) for position in range(frame.shape[1]) if position != excluded)


def _resolve_x(frame: pd.DataFrame, ref: ColumnRef | None, spec: GraphSpec) -> int | None:
    """Resolve an x reference; ``None`` falls back to ``x_default``."""
    if ref is not None:
        return _resolve_column(frame, ref, "x")
    if spec.x_default == "index":
        return None
    return _resolve_column(frame, 0, "x")


def _resolve_column(frame: pd.DataFrame, ref: ColumnRef, role: str) -> int:
    """Resolve a column reference to a position without round-tripping through labels.

    Args:
        frame: The DataFrame.
        ref: 0-based position (``int``) or exact column label (``str``).
        role: ``"x"``, ``"y"`` or ``"direction"``, used in messages.

    Returns:
        The column position.

    Raises:
        PlotRequestError: ``reason="unknown_column"`` for an out-of-range position or
            an unmatched label, ``reason="ambiguous_column"`` for a label carried by
            several columns (address those by position).
    """
    columns = list(frame.columns)
    if isinstance(ref, int):
        if 0 <= ref < len(columns):
            return ref
        msg = f"{role} column position {ref} is out of range for {len(columns)} columns"
        raise PlotRequestError(msg, reason="unknown_column")
    matches = [position for position, label in enumerate(columns) if label == ref]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        msg = f"{role} column {ref!r} not found. Available columns: {[str(label) for label in columns]}"
        raise PlotRequestError(msg, reason="unknown_column")
    msg = f"{role} column {ref!r} matches columns {matches}; address one of them by position"
    raise PlotRequestError(msg, reason="ambiguous_column")


def _series_plan(
    position: int,
    frame_index: int,
    frame: pd.DataFrame,
    selection: SeriesSpec,
    spec: GraphSpec,
    seen_labels: set[str],
) -> SeriesPlan:
    """Resolve one selection of one frame."""
    x_index = _resolve_x(frame, selection.x if selection.x is not None else spec.x, spec)
    y_index = _resolve_column(frame, selection.y, "y")
    direction_index = None if selection.direction is None else _resolve_column(frame, selection.direction, "direction")
    y_name = str(frame.columns[y_index])
    header_series, header_label, header_unit = parse_header(y_name, humanize=False)
    label = selection.label if selection.label is not None else _series_label(y_name, spec.label_style)
    directions = _directions(frame, direction_index, spec.direction_filter)
    # A series the direction filter empties draws nothing, so it cannot own its label's legend entry.
    draws = direction_index is None or bool(directions)
    return SeriesPlan(
        series_id=_series_id(position),
        frame=frame_index,
        x_index=x_index,
        y_index=y_index,
        x_name=_index_name(frame) if x_index is None else str(frame.columns[x_index]),
        y_name=y_name,
        direction_index=direction_index,
        directions=directions,
        label=label,
        show_in_legend=draws and label not in seen_labels,
        color_index=position,
        header_series=header_series,
        header_label=header_label,
        unit=_clean_unit(selection.unit if selection.unit is not None else header_unit),
        unit_group=0,
    )


def _draws(series: SeriesPlan) -> bool:
    """Whether a series draws at least one segment (no direction column, or a direction left after the filter)."""
    return series.direction_index is None or bool(series.directions)


def _series_id(position: int) -> str:
    """Return the stable id of the series at ``position`` (``s000``, ``s001``, ...).

    Args:
        position: 0-based position in ``PlotPlan.series``.

    Returns:
        The series id.
    """
    return f"s{position:03d}"


def _series_label(header: str, label_style: str) -> str:
    """Derive a legend label from a header.

    Args:
        header: Column header text.
        label_style: ``"humanized"``, ``"header"`` or ``"raw"``.

    Returns:
        ``raw``: the header itself; otherwise the series prefix, else the label
        part, else the header (humanized for ``"humanized"``).
    """
    if label_style == "raw":
        return header
    parsed_series, parsed_label, _ = parse_header(header, humanize=label_style == "humanized")
    return parsed_series or parsed_label or header


def _axis_label(header: str, label_style: str) -> str:
    """Derive an axis label (``"label (unit)"``) from a header.

    Args:
        header: Column header text.
        label_style: ``"humanized"``, ``"header"`` or ``"raw"``.

    Returns:
        ``raw``: the header itself; otherwise the label part (or the header) with
        the unit in parentheses when the header carries one.
    """
    if label_style == "raw":
        return header
    _, parsed_label, unit = parse_header(header, humanize=label_style == "humanized")
    base = parsed_label or header
    return f"{base} ({unit})" if unit else base


def _index_name(frame: pd.DataFrame) -> str:
    return _INDEX_NAME if frame.index.name is None else str(frame.index.name)


def _clean_unit(unit: str | None) -> str | None:
    """Strip a unit; an empty unit is unknown (full normalization arrives with GE-11)."""
    if unit is None:
        return None
    stripped = unit.strip()
    return stripped or None


def _direction_or_none(value: Any) -> str | None:
    """Normalize one direction cell: enum members by value, everything else by ``str``."""
    if not isinstance(value, Enum) and pd.isna(value):
        return None
    return str(value.value) if isinstance(value, Enum) else str(value)


def _directions(frame: pd.DataFrame, direction_index: int | None, direction_filter: tuple[str, ...]) -> tuple[str, ...]:
    """Unique non-NA direction values in first-appearance order, after the filter."""
    if direction_index is None:
        return ()
    values: list[str] = []
    for raw in frame.iloc[:, direction_index].unique():
        value = _direction_or_none(raw)
        if value is None or value in values:
            continue
        if direction_filter and value not in direction_filter:
            continue
        values.append(value)
    return tuple(values)


def _plan_figures(
    series: tuple[SeriesPlan, ...],
    spec: GraphSpec,
    base_name: str,
) -> tuple[tuple[FigurePlan, ...], tuple[GraphDiagnostic, ...]]:
    """Choose the figures of the layout and reserve one unique stem per figure."""
    with_overlay, individuals = _layout_figures(series, spec.layout)
    candidates = _stem_candidates(with_overlay, individuals, base_name)
    stems, diagnostics = reserve_stems(candidates)
    stem_of = dict(zip((figure_id for figure_id, _ in candidates), stems, strict=True))
    figures: list[FigurePlan] = []
    if with_overlay:
        figures.append(_overlay_figure(series, spec, stem_of[OVERLAY_FIGURE_ID]))
    figures.extend(_individual_figure(entry, spec, stem_of[entry.series_id]) for entry in individuals)
    return tuple(figures), diagnostics


def _layout_figures(series: tuple[SeriesPlan, ...], layout: str) -> tuple[bool, tuple[SeriesPlan, ...]]:
    """Return whether the layout has an overlay figure and which series get their own figure."""
    with_overlay = layout in ("auto", "overlay", "both")
    with_individual = layout in ("individual", "both") or (layout == "auto" and len(series) > 1)
    return with_overlay, series if with_individual else ()


def _stem_candidates(with_overlay: bool, individuals: tuple[SeriesPlan, ...], base_name: str) -> list[tuple[str, str]]:
    """Candidate stems in figure order; the overlay stem is the sanitized base name."""
    candidates: list[tuple[str, str]] = []
    if with_overlay:
        candidates.append((OVERLAY_FIGURE_ID, sanitize_stem(base_name) or DEFAULT_BASE_STEM))
    for entry in individuals:
        # The v1 stem uses the humanized series prefix; keep it byte-identical.
        humanized_series, _, _ = parse_header(entry.y_name)
        candidates.append((entry.series_id, series_stem(base_name, humanized_series, entry.y_name)))
    return candidates


def _overlay_figure(series: tuple[SeriesPlan, ...], spec: GraphSpec, stem: str) -> FigurePlan:
    first = series[0]
    return FigurePlan(
        figure_id=OVERLAY_FIGURE_ID,
        kind="overlay",
        series_ids=tuple(entry.series_id for entry in series),
        title=spec.title,
        x_label=spec.x_axis.label if spec.x_axis.label is not None else _axis_label(first.x_name, spec.label_style),
        y_label=spec.y_axis.label if spec.y_axis.label is not None else _axis_label(first.y_name, spec.label_style),
        stem=stem,
    )


def _individual_figure(entry: SeriesPlan, spec: GraphSpec, stem: str) -> FigurePlan:
    # Unlike the v1 facade (first column's label everywhere), an individual
    # figure is labelled after its own columns.
    return FigurePlan(
        figure_id=entry.series_id,
        kind="individual",
        series_ids=(entry.series_id,),
        title=_individual_title(spec.title, entry.label),
        x_label=spec.x_axis.label if spec.x_axis.label is not None else _axis_label(entry.x_name, spec.label_style),
        y_label=spec.y_axis.label if spec.y_axis.label is not None else _axis_label(entry.y_name, spec.label_style),
        stem=stem,
    )


def _individual_title(title: str | None, label: str) -> str:
    """The v1 individual title: ``"{title or 'Plot'} - {label}"``."""
    return f"{title or _DEFAULT_INDIVIDUAL_TITLE} - {label}"


def _relabel_figure(
    figure: FigurePlan,
    old_series: tuple[SeriesPlan, ...],
    relabelled: Mapping[str, SeriesPlan],
) -> FigurePlan:
    """Recompute the title of an individual figure whose series label changed."""
    if figure.kind != "individual" or figure.title is None:
        return figure
    old_label = next(entry.label for entry in old_series if entry.series_id == figure.figure_id)
    suffix = f" - {old_label}"
    base = figure.title[: -len(suffix)] if figure.title.endswith(suffix) else figure.title
    new_title = f"{base} - {relabelled[figure.figure_id].label}"
    return dataclasses.replace(figure, title=new_title)


def _resolve_style(style: StyleSpec) -> StyleSpec:
    """Make the figure size concrete and merge rcParams over the engine defaults."""
    figure_size = DEFAULT_FIG_SIZE if style.figure_size is None else style.figure_size
    return StyleSpec(figure_size=figure_size, rc_params={**DEFAULT_PLOT_PARAMS, **style.rc_params})


def _explicit_or(value: object, fallback: Origin) -> Origin:
    return "explicit" if value is not None else fallback


def _origins(spec: GraphSpec, series: tuple[SeriesPlan, ...]) -> dict[str, Origin]:
    """Record where each resolved decision came from."""
    any_series_x = any(selection.x is not None for selection in spec.series)
    origins: dict[str, Origin] = {
        "title": _explicit_or(spec.title, "default"),
        "x": "explicit" if spec.x is not None or any_series_x else "default",
        "series": "explicit" if spec.series else "default",
        "x_axis.label": _explicit_or(spec.x_axis.label, "derived"),
        "y_axis.label": _explicit_or(spec.y_axis.label, "derived"),
        "x_axis.limits": _explicit_or(spec.x_axis.limits, "default"),
        "y_axis.limits": _explicit_or(spec.y_axis.limits, "default"),
        "style.figure_size": _explicit_or(spec.style.figure_size, "default"),
        "style.rc_params": "explicit" if spec.style.rc_params else "default",
    }
    origins.update(_series_origins(spec, series))
    return origins


def _series_origins(spec: GraphSpec, series: tuple[SeriesPlan, ...]) -> dict[str, Origin]:
    """Label and unit origins of every series."""
    origins: dict[str, Origin] = {}
    selections = _selection_by_series(spec, series)
    for entry in series:
        selection = selections.get(entry.series_id)
        origins[f"series[{entry.series_id}].label"] = _explicit_or(selection.label if selection else None, "derived")
        origins[f"series[{entry.series_id}].unit"] = _unit_origin(selection, entry)
    return origins


def _selection_by_series(spec: GraphSpec, series: tuple[SeriesPlan, ...]) -> dict[str, SeriesSpec]:
    """Map each series id to the explicit selection it came from (frame-major order)."""
    if not spec.series:
        return {}
    count = len(spec.series)
    return {entry.series_id: spec.series[position % count] for position, entry in enumerate(series)}


def _unit_origin(selection: SeriesSpec | None, entry: SeriesPlan) -> Origin:
    if selection is not None and selection.unit is not None:
        return "explicit"
    return "derived" if entry.unit is not None else "default"


def _jsonable(value: Any) -> Any:
    """Convert a plan value into JSON-safe data with sorted mapping keys."""
    # Enum first: a str-valued enum member is also a str and must become its value.
    if isinstance(value, Enum):
        return _jsonable(value.value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return _jsonable_container(value)


def _jsonable_container(value: Any) -> Any:
    """Dataclasses and mappings become dicts with sorted keys; anything else becomes text."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {item.name: _jsonable(getattr(value, item.name)) for item in sorted(dataclasses.fields(value), key=lambda item: item.name)}
    if isinstance(value, Mapping):
        return {str(key): _jsonable(value[key]) for key in sorted(value, key=str)}
    return str(value)

