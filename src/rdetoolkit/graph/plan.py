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
import warnings
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

import pandas as pd

from rdetoolkit.graph.config import DEFAULT_FIG_SIZE, DEFAULT_PLOT_PARAMS
from rdetoolkit.graph.exceptions import GraphUserWarning, PlotRequestError
from rdetoolkit.graph.naming import DEFAULT_BASE_STEM, GraphDiagnostic, reserve_stems, sanitize_stem, series_stem
from rdetoolkit.graph.spec import AxisSpec, ColumnRef, GraphSpec, LegendSpec, Origin, SeriesSpec, StyleSpec
from rdetoolkit.graph.textutils import parse_header
from rdetoolkit.graph.units import group_units, normalize_unit
from rdetoolkit.graph.validation import validate_axis_limits, validate_style

__all__ = [
    "FigurePlan",
    "GraphDiagnostic",
    "PlotData",
    "PlotPlan",
    "SeriesPlan",
    "build_plot_plan",
    "column_position",
]

OVERLAY_FIGURE_ID = "overlay"
UNIT_MISMATCH = "unit_mismatch"
UNIT_UNKNOWN = "unit_unknown"
_LABEL_JOINER = " / "
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
        figure_id: ``"overlay"``, ``"overlay_g0"``, ``"overlay_g1"``, ... (one overlay
            per unit group under ``unit_policy="split"``), or the series id of an
            individual figure.
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
        renamed = tuple(dataclasses.replace(current, label=label) for current, label in zip(self.series, labels, strict=True))
        # Legend ownership is decided per overlay figure, as when the plan was built.
        series = _assign_legend_roles(renamed, _legend_scopes(self.figures, renamed))
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
            ``reason="invalid_axis_limits"`` for invalid ``AxisSpec.limits``;
            ``reason="invalid_figure_size"`` / ``"invalid_rc_param"`` for an invalid
            ``GraphSpec.style``; ``reason="unit_mismatch"`` when an overlay figure
            would combine different known units under ``unit_policy="error"``.
        ValueError: If the request selects no series ("at least one y column").

    Warns:
        GraphUserWarning: Once, when an overlay figure combines different known
            units under ``unit_policy="warn"``.
    """
    frames_tuple = _as_frames(frames)
    spec = GraphSpec() if spec is None else spec
    # Reject invalid limits before any column is resolved; the plan keeps them as given.
    validate_axis_limits(spec.x_axis.limits, scale=spec.x_axis.scale, axis="x")
    validate_axis_limits(spec.y_axis.limits, scale=spec.y_axis.scale, axis="y")
    style = _resolve_style(validate_style(spec.style))
    series = _plan_series(frames_tuple, spec)
    if not series:
        raise ValueError(_NO_SERIES_MESSAGE)
    series, unit_groups = _group_series(series)
    figures, diagnostics = _plan_figures(series, unit_groups, spec, base_name)
    series = _assign_legend_roles(series, _legend_scopes(figures, series))
    return PlotPlan(
        spec_version=spec.version,
        mark=spec.mark,
        series=series,
        figures=figures,
        x_axis=spec.x_axis,
        y_axis=spec.y_axis,
        legend=spec.legend,
        direction_colors=spec.direction_colors,
        style=style,
        unit_groups=unit_groups,
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
    if isinstance(ref, int):
        count = frame.shape[1]
        if 0 <= ref < count:
            return ref
        msg = f"{role} column position {ref} is out of range for {count} columns"
        raise PlotRequestError(msg, reason="unknown_column")
    return column_position(frame, ref, role)


def column_position(frame: pd.DataFrame, label: Hashable, role: str) -> int:
    """Resolve an exact column label (never a position) to its column position.

    This is the single label resolver of the Graph Engine: the planner uses it for
    ``str`` references, and callers whose column references are labels of any type
    (the builtin plot nodes address ``df[x]``-style labels such as ``0``) use it to
    turn labels into positions before building a ``GraphSpec``.

    Args:
        frame: The DataFrame.
        label: The column label, compared with ``==``; a ``bool`` only matches a
            ``bool`` label (``True == 1`` in Python, but they are different labels).
        role: ``"x"``, ``"y"`` or ``"direction"``, used in messages.

    Returns:
        The position of the only column carrying ``label``.

    Raises:
        PlotRequestError: ``reason="unknown_column"`` if no column carries the
            label, ``reason="ambiguous_column"`` if several columns do (address
            those by position).
    """
    columns = list(frame.columns)
    matches = [position for position, column in enumerate(columns) if _same_label(column, label)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        msg = f"{role} column {label!r} not found. Available columns: {[str(column) for column in columns]}"
        raise PlotRequestError(msg, reason="unknown_column")
    msg = f"{role} column {label!r} matches columns {matches}; address one of them by position"
    raise PlotRequestError(msg, reason="ambiguous_column")


def _same_label(column: Any, label: Hashable) -> bool:
    """Exact label equality; a bool and a non-bool never match each other."""
    if isinstance(column, bool) != isinstance(label, bool):
        return False
    try:
        return bool(column == label)
    except (TypeError, ValueError):
        # An array-like or incomparable label is not the requested one.
        return False


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
        unit=normalize_unit(selection.unit if selection.unit is not None else header_unit),
        unit_group=0,  # assigned by _group_series once every series is known
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


def _axis_label(header: str, label_style: str, unit: str | None = None) -> str:
    """Derive an axis label (``"label (unit)"``) from a header.

    Args:
        header: Column header text.
        label_style: ``"humanized"``, ``"header"`` or ``"raw"``.
        unit: Explicit unit shown instead of the header unit (``SeriesSpec.unit``).

    Returns:
        ``raw``: the header itself; otherwise the label part (or the header) with
        the unit in parentheses when there is one. The header unit is shown as
        written, so a derived label keeps its v1 text.
    """
    if label_style == "raw":
        return header
    _, parsed_label, header_unit = parse_header(header, humanize=label_style == "humanized")
    base = parsed_label or header
    shown = header_unit if unit is None else unit
    return f"{base} ({shown})" if shown else base


def _index_name(frame: pd.DataFrame) -> str:
    return _INDEX_NAME if frame.index.name is None else str(frame.index.name)


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


@dataclass(frozen=True, slots=True)
class _Overlay:
    """One overlay figure chosen by the unit policy, before its stem is reserved.

    Attributes:
        figure_id: ``"overlay"`` or ``"overlay_g{n}"``.
        series: The series drawn in it, in plan order.
        unit: The unit group's unit for a split overlay; ``None`` for the single overlay.
        mixed: The single overlay deliberately combines several known units.
    """

    figure_id: str
    series: tuple[SeriesPlan, ...]
    unit: str | None = None
    mixed: bool = False


def _group_series(
    series: tuple[SeriesPlan, ...],
) -> tuple[tuple[SeriesPlan, ...], tuple[tuple[str | None, tuple[str, ...]], ...]]:
    """Assign every series its unit group (see ``units.group_units``)."""
    indices, units = group_units([entry.unit for entry in series])
    grouped = tuple(dataclasses.replace(entry, unit_group=index) for entry, index in zip(series, indices, strict=True))
    groups = tuple(
        (unit, tuple(entry.series_id for entry in grouped if entry.unit_group == position))
        for position, unit in enumerate(units)
    )
    return grouped, groups


def _plan_figures(
    series: tuple[SeriesPlan, ...],
    unit_groups: tuple[tuple[str | None, tuple[str, ...]], ...],
    spec: GraphSpec,
    base_name: str,
) -> tuple[tuple[FigurePlan, ...], tuple[GraphDiagnostic, ...]]:
    """Choose the figures of the layout and reserve one unique stem per figure."""
    with_overlay, individuals = _layout_figures(series, spec.layout)
    # Individual figures are never affected by the unit policy.
    overlays, unit_diagnostics = _plan_overlays(series, unit_groups, spec.unit_policy) if with_overlay else ((), ())
    candidates = _stem_candidates(overlays, individuals, base_name)
    stems, diagnostics = reserve_stems(candidates)
    stem_of = dict(zip((figure_id for figure_id, _ in candidates), stems, strict=True))
    y_labels = _series_y_labels(series, spec)
    figures = [_overlay_figure(overlay, spec, stem_of[overlay.figure_id], y_labels) for overlay in overlays]
    figures.extend(_individual_figure(entry, spec, stem_of[entry.series_id], y_labels) for entry in individuals)
    return tuple(figures), diagnostics + unit_diagnostics


def _plan_overlays(
    series: tuple[SeriesPlan, ...],
    unit_groups: tuple[tuple[str | None, tuple[str, ...]], ...],
    policy: str,
) -> tuple[tuple[_Overlay, ...], tuple[GraphDiagnostic, ...]]:
    """Apply the unit policy to the overlay figure.

    Raises:
        PlotRequestError: ``reason="unit_mismatch"`` under the ``"error"`` policy
            when the overlay would combine more than one known unit.
    """
    # Unknown units join the first group, so several groups means several known units.
    if len(unit_groups) <= 1:
        overlays: tuple[_Overlay, ...] = (_Overlay(OVERLAY_FIGURE_ID, series),)
        return overlays, _unknown_unit_diagnostics(overlays)
    description = _describe_unit_groups(series, unit_groups)
    if policy == "error":
        msg = (
            f"Series with different units would share one overlay y axis: {description}. "
            "No unit is converted. Use unit_policy='split' for one overlay figure per unit, "
            "layout='individual' for one figure per series, or unit_policy='allow' "
            "(or 'warn') to share the axis deliberately."
        )
        raise PlotRequestError(msg, reason=UNIT_MISMATCH)
    if policy == "split":
        overlays = _split_overlays(series, unit_groups)
        message = f"Series with different units were split into {len(overlays)} overlay figures, one per unit: {description}"
        mismatch = _mismatch_diagnostic(series, "info", message)
    else:
        overlays = (_Overlay(OVERLAY_FIGURE_ID, series, mixed=True),)
        mismatch = _shared_axis_diagnostic(series, description, warn=policy == "warn")
    return overlays, (mismatch, *_unknown_unit_diagnostics(overlays))


def _describe_unit_groups(
    series: tuple[SeriesPlan, ...],
    unit_groups: tuple[tuple[str | None, tuple[str, ...]], ...],
) -> str:
    """``unit 'V': s000 (voltage (V)); unit 'A': s001 (current (A))``."""
    header_of = {entry.series_id: entry.y_name for entry in series}
    parts = [
        f"unit {unit!r}: " + ", ".join(f"{series_id} ({header_of[series_id]})" for series_id in series_ids)
        for unit, series_ids in unit_groups
    ]
    return "; ".join(parts)


def _mismatch_diagnostic(series: tuple[SeriesPlan, ...], severity: Literal["info", "warning"], message: str) -> GraphDiagnostic:
    return GraphDiagnostic(
        code=UNIT_MISMATCH,
        severity=severity,
        message=message,
        series_ids=tuple(entry.series_id for entry in series),
    )


def _shared_axis_diagnostic(series: tuple[SeriesPlan, ...], description: str, *, warn: bool) -> GraphDiagnostic:
    """Report a deliberately shared axis; the ``"warn"`` policy also emits a ``GraphUserWarning``."""
    message = (
        f"Series with different units share one overlay y axis ({description}); "
        "no unit was converted and the y label lists every unit"
    )
    if warn:
        # stacklevel points at the caller of build_plot_plan.
        warnings.warn(message, GraphUserWarning, stacklevel=6)
    return _mismatch_diagnostic(series, "warning" if warn else "info", message)


def _split_overlays(
    series: tuple[SeriesPlan, ...],
    unit_groups: tuple[tuple[str | None, tuple[str, ...]], ...],
) -> tuple[_Overlay, ...]:
    """One overlay per unit group: ``overlay_g0``, ``overlay_g1``, ..."""
    by_id = {entry.series_id: entry for entry in series}
    return tuple(
        _Overlay(f"{OVERLAY_FIGURE_ID}_g{position}", tuple(by_id[series_id] for series_id in series_ids), unit=unit)
        for position, (unit, series_ids) in enumerate(unit_groups)
    )


def _unknown_unit_diagnostics(overlays: tuple[_Overlay, ...]) -> tuple[GraphDiagnostic, ...]:
    """Report series without unit that share an overlay axis with a known unit.

    A lone series, or an overlay where no unit is known at all, involves no
    compatibility assumption and is not reported.
    """
    diagnostics: list[GraphDiagnostic] = []
    for overlay in overlays:
        unknown = tuple(entry.series_id for entry in overlay.series if entry.unit is None)
        known = [entry.unit for entry in overlay.series if entry.unit is not None]
        if unknown and known:
            message = (
                f"Series {', '.join(unknown)} have no unit and share the y axis of figure "
                f"{overlay.figure_id!r} with unit {known[0]!r}: assumed compatible, no conversion performed"
            )
            diagnostics.append(GraphDiagnostic(code=UNIT_UNKNOWN, severity="info", message=message, series_ids=unknown))
    return tuple(diagnostics)


def _series_y_labels(series: tuple[SeriesPlan, ...], spec: GraphSpec) -> dict[str, str]:
    """The derived ``label (unit)`` of every series; an explicit ``SeriesSpec.unit`` is shown as declared."""
    selections = _selection_by_series(spec, series)
    labels: dict[str, str] = {}
    for entry in series:
        selection = selections.get(entry.series_id)
        declared = entry.unit if selection is not None and selection.unit is not None else None
        labels[entry.series_id] = _axis_label(entry.y_name, spec.label_style, declared)
    return labels


def _overlay_y_label(overlay: _Overlay, y_labels: Mapping[str, str]) -> str:
    """Derived overlay label: one ``label (unit)`` per unit, the first series' label otherwise."""
    if overlay.mixed:
        units = dict.fromkeys(entry.unit for entry in overlay.series if entry.unit is not None)
        parts = (y_labels[_unit_representative(overlay.series, unit).series_id] for unit in units)
        return _LABEL_JOINER.join(dict.fromkeys(parts))
    if overlay.unit is not None:
        return y_labels[_unit_representative(overlay.series, overlay.unit).series_id]
    # The v1 rule: the first series names a single-unit overlay.
    return y_labels[overlay.series[0].series_id]


def _unit_representative(series: tuple[SeriesPlan, ...], unit: str | None) -> SeriesPlan:
    """The first series carrying ``unit`` (unknown-unit members never name a group)."""
    return next(entry for entry in series if entry.unit == unit)


def _layout_figures(series: tuple[SeriesPlan, ...], layout: str) -> tuple[bool, tuple[SeriesPlan, ...]]:
    """Return whether the layout has an overlay figure and which series get their own figure."""
    with_overlay = layout in ("auto", "overlay", "both")
    with_individual = layout in ("individual", "both") or (layout == "auto" and len(series) > 1)
    return with_overlay, series if with_individual else ()


def _stem_candidates(overlays: tuple[_Overlay, ...], individuals: tuple[SeriesPlan, ...], base_name: str) -> list[tuple[str, str]]:
    """Candidate stems in figure order.

    The single overlay stem is the sanitized base name; a split overlay is
    ``{base}_{unit slug}``; individual stems follow the v1 rule.
    """
    candidates: list[tuple[str, str]] = []
    for overlay in overlays:
        if overlay.unit is None:
            candidates.append((overlay.figure_id, sanitize_stem(base_name) or DEFAULT_BASE_STEM))
        else:
            candidates.append((overlay.figure_id, series_stem(base_name, None, overlay.unit)))
    for entry in individuals:
        # The v1 stem uses the humanized series prefix; keep it byte-identical.
        humanized_series, _, _ = parse_header(entry.y_name)
        candidates.append((entry.series_id, series_stem(base_name, humanized_series, entry.y_name)))
    return candidates


def _overlay_figure(overlay: _Overlay, spec: GraphSpec, stem: str, y_labels: Mapping[str, str]) -> FigurePlan:
    first = overlay.series[0]
    return FigurePlan(
        figure_id=overlay.figure_id,
        kind="overlay",
        series_ids=tuple(entry.series_id for entry in overlay.series),
        title=spec.title,
        x_label=spec.x_axis.label if spec.x_axis.label is not None else _axis_label(first.x_name, spec.label_style),
        y_label=spec.y_axis.label if spec.y_axis.label is not None else _overlay_y_label(overlay, y_labels),
        stem=stem,
    )


def _individual_figure(entry: SeriesPlan, spec: GraphSpec, stem: str, y_labels: Mapping[str, str]) -> FigurePlan:
    # Unlike the v1 facade (first column's label everywhere), an individual
    # figure is labelled after its own columns.
    return FigurePlan(
        figure_id=entry.series_id,
        kind="individual",
        series_ids=(entry.series_id,),
        title=_individual_title(spec.title, entry.label),
        x_label=spec.x_axis.label if spec.x_axis.label is not None else _axis_label(entry.x_name, spec.label_style),
        y_label=spec.y_axis.label if spec.y_axis.label is not None else y_labels[entry.series_id],
        stem=stem,
    )


def _legend_scopes(figures: Sequence[FigurePlan], series: Sequence[SeriesPlan]) -> tuple[tuple[str, ...], ...]:
    """Series sharing one legend: each overlay figure, or every series when there is none."""
    scopes = tuple(figure.series_ids for figure in figures if figure.kind == "overlay")
    return scopes or (tuple(entry.series_id for entry in series),)


def _assign_legend_roles(series: tuple[SeriesPlan, ...], scopes: tuple[tuple[str, ...], ...]) -> tuple[SeriesPlan, ...]:
    """A series owns its label's legend entry when it is the first drawing series with that label in its scope."""
    by_id = {entry.series_id: entry for entry in series}
    owns: dict[str, bool] = {}
    for scope in scopes:
        seen: set[str] = set()
        for series_id in scope:
            entry = by_id[series_id]
            owns[series_id] = _draws(entry) and entry.label not in seen
            if owns[series_id]:
                seen.add(entry.label)
    return tuple(dataclasses.replace(entry, show_in_legend=owns.get(entry.series_id, entry.show_in_legend)) for entry in series)


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

