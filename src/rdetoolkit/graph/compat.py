"""Legacy ``PlotConfig`` to ``PlotPlan`` adapter (GE-06).

The legacy renderer methods (``render_overlay``, ``render_individual``,
``render_html``) take a ``(DataFrame, PlotConfig)`` pair. Instead of interpreting the
column specs themselves, they turn that pair into the same ``PlotPlan`` the spec API
uses and draw the plan. Column positions, x/y pairing, direction padding, direction
filters and colours, legend roles and colour indices are therefore resolved exactly
once, by ``build_plot_plan``.

Only the labels stay backend specific (ruling C-12): v1 pinned humanized legend labels
on the Matplotlib path and un-humanized ones on the Plotly path, so each legacy
adapter passes its own label function. The spec API has a single label rule.

One legacy call (``collect_render_results`` or a legacy strategy) runs inside
``legacy_call()``: its figures share one plan per backend and the IC-6 mixed-unit
warning is emitted once, when an overlay figure is actually produced. Outside such a
call nothing is reused, so a frame changed in place between two direct ``render_*``
calls is planned again.

Dual-axis plotting is not supported (GE-12): ``reject_dual_axis`` turns a legacy
configuration that asks for a secondary y axis into a typed error before any figure
is planned, so no legacy entry point can silently draw it on a single axis.
"""

from __future__ import annotations

import dataclasses
import warnings
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pandas as pd

from rdetoolkit.graph.exceptions import GraphUserWarning, PlotRequestError
from rdetoolkit.graph.models import AxisConfig, DirectionConfig, PlotConfig, PlotMode
from rdetoolkit.graph.plan import UNIT_MISMATCH, FigurePlan, PlotPlan, build_plot_plan
from rdetoolkit.graph.spec import AxisSpec, ColumnRef, GraphSpec, LegendSpec, Origin, SeriesSpec, StyleSpec
from rdetoolkit.graph.textutils import parse_header, titleize

__all__ = [
    "DUAL_AXIS_UNSUPPORTED",
    "AxisLabelFunction",
    "LabelFunction",
    "legacy_mpl_axis_label",
    "legacy_mpl_label",
    "legacy_plotly_axis_label",
    "legacy_plotly_label",
    "dual_axis_unsupported_error",
    "individual_plan",
    "legacy_call",
    "legacy_plan",
    "mixes_units",
    "plan_from_config",
    "reject_dual_axis",
    "warn_mixed_overlay",
]

LabelFunction = Callable[[str, bool], str]
"""``(raw_header, humanize) -> legend label``."""

AxisLabelFunction = Callable[[AxisConfig, str], str]
"""``(axis_config, default_label) -> final axis label``."""

_DEFAULT_BASE_NAME = "plot"

DUAL_AXIS_UNSUPPORTED = "dual_axis_unsupported"
"""``PlotRequestError.reason`` of every dual-axis rejection."""

_DUAL_AXIS_MESSAGE = (
    "Dual-axis plotting (PlotMode.DUAL_AXIS / PlotConfig.y2_axis) is not supported in rdetoolkit 2.0; "
    "nothing was drawn or written. Plot series with different units separately instead: "
    "render_graph with GraphSpec(unit_policy='split') draws one overlay per unit, "
    "csv2graph / plot_from_dataframe with mode='individual' draw one figure per series, "
    "or build a Matplotlib figure with Axes.twinx() yourself and save it with the save_figure node."
)


def dual_axis_unsupported_error() -> PlotRequestError:
    """Build the error raised for every dual-axis request.

    Returns:
        A ``PlotRequestError`` with ``reason="dual_axis_unsupported"`` whose message
        names the supported alternatives.
    """
    return PlotRequestError(_DUAL_AXIS_MESSAGE, reason=DUAL_AXIS_UNSUPPORTED)


def reject_dual_axis(config: PlotConfig, plot_mode: PlotMode | None = None) -> None:
    """Reject a legacy configuration that asks for a secondary y axis.

    Args:
        config: The legacy configuration; ``config.mode`` equal to
            ``PlotMode.DUAL_AXIS`` (also as the plain string) or any ``y2_axis``
            requests a secondary axis.
        plot_mode: The mode the caller renders with, when it is passed separately
            from ``config`` (``collect_render_results``).

    Raises:
        PlotRequestError: ``reason="dual_axis_unsupported"`` for a dual-axis request.
    """
    # Equality, not identity: PlotMode is a str enum and dataclasses do not coerce
    # a plain "dual_axis" string assigned to ``mode``.
    if PlotMode.DUAL_AXIS in (config.mode, plot_mode) or config.y2_axis is not None:
        raise dual_axis_unsupported_error()


def legacy_mpl_label(header: str, humanize: bool) -> str:
    """The v1 Matplotlib legend label of a header.

    Args:
        header: Raw column header.
        humanize: ``PlotConfig.humanize``.

    Returns:
        The humanized series prefix, else the humanized label part, else the header;
        title-cased again when ``humanize`` is set.
    """
    parsed_series, parsed_label, _ = parse_header(header)
    label = parsed_series or parsed_label or header
    return titleize(label) if humanize else label


def legacy_plotly_label(header: str, humanize: bool) -> str:
    """The v1 Plotly legend label of a header (humanized only on request).

    Args:
        header: Raw column header.
        humanize: ``PlotConfig.humanize``.

    Returns:
        The series prefix, else the label part, else the header (title-cased when
        ``humanize`` is set and nothing was parsed).
    """
    parsed_series, parsed_label, _ = parse_header(header, humanize=humanize)
    label = parsed_series or parsed_label or header
    if humanize and label == header:
        return titleize(label)
    return label


def legacy_mpl_axis_label(axis: AxisConfig, default_label: str) -> str:
    """The v1 Matplotlib axis label: the label with its unit composed in once.

    Args:
        axis: The legacy axis configuration.
        default_label: Label used when ``axis.label`` is empty.

    Returns:
        ``"label (unit)"``, or the label alone when there is no unit or the label
        already carries it.
    """
    label = axis.label or default_label
    unit = axis.unit
    if not unit or f"({unit})" in label:
        return label
    return f"{label} ({unit})"


def legacy_plotly_axis_label(axis: AxisConfig, default_label: str) -> str:
    """The v1 Plotly axis title: the label as given (no unit composition).

    Args:
        axis: The legacy axis configuration.
        default_label: Title used when ``axis.label`` is empty.

    Returns:
        ``axis.label`` or ``default_label``.
    """
    return axis.label or default_label


def plan_from_config(
    df: pd.DataFrame,
    config: PlotConfig,
    *,
    label_of: LabelFunction,
    axis_label_of: AxisLabelFunction = legacy_mpl_axis_label,
) -> PlotPlan:
    """Build the plan of a legacy ``(DataFrame, PlotConfig)`` pair.

    The plan always has the ``"both"`` layout (the overlay figure first, then one
    individual figure per series) so every legacy adapter finds its figure in it.
    File stems in the plan are not used by the legacy strategies, which keep naming
    their files themselves.

    The y label follows v1 unless the overlay mixes units: every figure uses the
    configured (or derived first-column) y label. Only a mixed-unit overlay (IC-6)
    gets the joined label and individual figures labelled after their own column.
    Planning never warns; ``warn_mixed_overlay`` warns when an overlay is produced.

    Args:
        df: The data frame.
        config: The legacy configuration (integer positions or exact labels).
        label_of: Legend label rule of the calling backend (``legacy_mpl_label`` or
            ``legacy_plotly_label``).
        axis_label_of: Axis label rule of the calling backend.

    Returns:
        The resolved plan; legacy labels have the origin ``"derived"``.

    Raises:
        ValueError: If ``x_col`` or ``y_cols`` is missing ("must be specified"), the
            x and y counts cannot be paired ("must be equal"), there are more
            direction columns than y columns ("cannot exceed"), or nothing is
            selected ("at least one y column").
        PlotRequestError: For a column reference that matches no or several columns,
            or an invalid ``config.style`` (``reason="invalid_figure_size"`` /
            ``"invalid_rc_param"``).
        PlotRequestError: ``reason="dual_axis_unsupported"`` for a configuration with
            ``PlotMode.DUAL_AXIS`` or a ``y2_axis`` (checked first).
        TypeError: For a column reference that is neither ``int`` nor ``str``.
    """
    plan = _planned(df, config, label_of, axis_label_of)
    return _legacy_y_labels(plan, config, axis_label_of, mixed=mixes_units(plan))


def _planned(df: pd.DataFrame, config: PlotConfig, label_of: LabelFunction, axis_label_of: AxisLabelFunction) -> PlotPlan:
    """Plan a legacy pair with the planner's per-figure y labels (before the v1 label rule)."""
    reject_dual_axis(config)
    x_refs, y_refs, direction_refs = _paired_columns(config)
    series = tuple(
        SeriesSpec(y=y_ref, x=x_ref, direction=direction_ref)
        for x_ref, y_ref, direction_ref in zip(x_refs, y_refs, direction_refs, strict=True)
    )
    spec = GraphSpec(
        series=series,
        layout="both",
        title=config.title,
        x_axis=_axis_spec(config.x_axis, axis_label_of(config.x_axis, "X")),
        y_axis=_axis_spec(config.y_axis, _y_axis_label(config.y_axis, axis_label_of)),
        legend=_legend_spec(config),
        direction_filter=_direction_filter(config.direction),
        direction_colors=_direction_colors(config.direction),
        # Legend labels are replaced by ``label_of`` below; the style only shapes a
        # derived y label, which then matches the facade's ``_format_axis_label``.
        label_style="humanized",
        # Mixed units on the legacy overlay are shared with a joined y label, never
        # rejected (the legacy signatures cannot gain a policy switch). The warning is
        # not raised while planning: only a produced overlay warns (warn_mixed_overlay).
        unit_policy="allow",
        # No style means the legacy look: the plan resolves it to the house defaults.
        style=StyleSpec() if config.style is None else config.style,
    )
    plan = build_plot_plan(df, spec, base_name=_base_name(config))
    labels = [label_of(entry.y_name, bool(config.humanize)) for entry in plan.series]
    relabelled = plan.with_labels(labels)
    # The labels follow the legacy header rule, so they are derived, not caller-given.
    origins: dict[str, Origin] = dict(relabelled.origins)
    origins.update({f"series[{entry.series_id}].label": "derived" for entry in relabelled.series})
    return dataclasses.replace(relabelled, origins=origins)


def mixes_units(plan: PlotPlan) -> bool:
    """Whether the plan's overlay shares one y axis between different units (IC-6).

    Args:
        plan: A legacy plan.

    Returns:
        True when the plan records a ``unit_mismatch`` diagnostic.
    """
    return any(item.code == UNIT_MISMATCH for item in plan.diagnostics)


def _legacy_y_labels(plan: PlotPlan, config: PlotConfig, axis_label_of: AxisLabelFunction, *, mixed: bool) -> PlotPlan:
    """Apply the v1 y label to every figure unless the overlay mixes units (IC-6)."""
    if mixed or config.y_axis.label_origin != "derived":
        # An explicit label already reached every figure through the spec.
        return plan
    label = axis_label_of(config.y_axis, "Y")
    figures = tuple(dataclasses.replace(figure, y_label=label) for figure in plan.figures)
    return dataclasses.replace(plan, figures=figures)


@dataclass
class _LegacyCall:
    """State of one legacy call: the plans built so far and whether it already warned."""

    plans: list[tuple[pd.DataFrame, PlotConfig, LabelFunction, AxisLabelFunction, PlotPlan]] = field(default_factory=list)
    warned: bool = False


_LEGACY_CALL: ContextVar[_LegacyCall | None] = ContextVar("rdetoolkit_graph_legacy_call", default=None)


@contextmanager
def legacy_call() -> Iterator[None]:
    """Scope one legacy call; nested scopes join the outermost one.

    Inside the scope ``legacy_plan`` reuses the plan of an identical ``(df, config)``
    pair and ``warn_mixed_overlay`` warns at most once. Nothing outlives the scope.

    Yields:
        Nothing.
    """
    if _LEGACY_CALL.get() is not None:
        yield
        return
    token = _LEGACY_CALL.set(_LegacyCall())
    try:
        yield
    finally:
        _LEGACY_CALL.reset(token)


def legacy_plan(
    df: pd.DataFrame,
    config: PlotConfig,
    *,
    label_of: LabelFunction,
    axis_label_of: AxisLabelFunction = legacy_mpl_axis_label,
) -> PlotPlan:
    """``plan_from_config``, shared by the figures of one ``legacy_call``.

    The same frame and config objects inside one call give the same plan; outside a
    call every invocation plans again (the frame may have changed in place).

    Args:
        df: The data frame.
        config: The legacy configuration.
        label_of: Legend label rule of the calling backend.
        axis_label_of: Axis label rule of the calling backend.

    Returns:
        The plan.
    """
    scope = _LEGACY_CALL.get()
    if scope is None:
        return plan_from_config(df, config, label_of=label_of, axis_label_of=axis_label_of)
    for frame, known, known_label_of, known_axis_label_of, plan in scope.plans:
        if frame is df and known is config and known_label_of is label_of and known_axis_label_of is axis_label_of:
            return plan
    plan = plan_from_config(df, config, label_of=label_of, axis_label_of=axis_label_of)
    scope.plans.append((df, config, label_of, axis_label_of, plan))
    return plan


def warn_mixed_overlay(plan: PlotPlan) -> None:
    """Warn that a produced overlay figure shares its y axis between units (IC-6).

    Called by the legacy adapters after an overlay figure was drawn; inside a
    ``legacy_call`` the warning is emitted once for the whole call.

    Args:
        plan: The legacy plan of the drawn overlay.

    Warns:
        GraphUserWarning: When the overlay mixes units.
    """
    diagnostic = next((item for item in plan.diagnostics if item.code == UNIT_MISMATCH), None)
    if diagnostic is None:
        return
    scope = _LEGACY_CALL.get()
    if scope is not None:
        if scope.warned:
            return
        scope.warned = True
    warnings.warn(diagnostic.message, GraphUserWarning, stacklevel=3)


def individual_plan(
    df: pd.DataFrame,
    config: PlotConfig,
    y_col_index: int,
    series_position: int | None,
    *,
    label_of: LabelFunction,
    axis_label_of: AxisLabelFunction = legacy_mpl_axis_label,
) -> tuple[PlotPlan, FigurePlan]:
    """Plan the figure of a legacy ``render_individual`` call with the v1 semantics.

    A column planned at ``series_position`` (or, without a position, anywhere) uses
    the call's plan. Any other column is drawn as v1 did: against the x column of the
    position (the first x column when the position is beyond the x list) and the
    direction column of the position (none beyond the direction list).

    Args:
        df: The data frame.
        config: The legacy configuration (``x_col`` and ``y_cols`` required).
        y_col_index: Column position of the y values.
        series_position: Position within ``config.y_cols``; ``None`` means 0 for a
            column that is not planned.
        label_of: Legend label rule of the calling backend.
        axis_label_of: Axis label rule of the calling backend.

    Returns:
        The plan and its individual figure for the column.

    Raises:
        ValueError: If ``x_col`` or ``y_cols`` is missing, or as ``plan_from_config``.
        PlotRequestError: ``reason="unknown_column"`` for a column the frame lacks.
    """
    plan = legacy_plan(df, config, label_of=label_of, axis_label_of=axis_label_of)
    figure = _planned_individual(plan, y_col_index, series_position)
    if figure is not None:
        return plan, figure
    single = _single_series_config(config, y_col_index, 0 if series_position is None else series_position)
    substitute = _legacy_y_labels(_planned(df, single, label_of, axis_label_of), single, axis_label_of, mixed=mixes_units(plan))
    return substitute, next(item for item in substitute.figures if item.kind == "individual")


def _planned_individual(plan: PlotPlan, y_col_index: int, series_position: int | None) -> FigurePlan | None:
    """The planned individual figure of the column at the position, if the plan has one."""
    if series_position is None:
        entry = next((item for item in plan.series if item.y_index == y_col_index), None)
    elif 0 <= series_position < len(plan.series) and plan.series[series_position].y_index == y_col_index:
        entry = plan.series[series_position]
    else:
        entry = None
    if entry is None:
        return None
    return next(item for item in plan.figures if item.kind == "individual" and item.figure_id == entry.series_id)


def _single_series_config(config: PlotConfig, y_col_index: int, position: int) -> PlotConfig:
    """The one-series config v1 drew for an unplanned column at ``position``."""
    x_col = config.x_col
    if isinstance(x_col, list):
        x_col = x_col[position] if position < len(x_col) else x_col[0]
    count = len(config.y_cols or [])
    directions = _padded_directions(config.direction_cols, count)
    direction = directions[position] if position < count else None
    return dataclasses.replace(
        config, x_col=x_col, y_cols=[y_col_index], direction_cols=None if direction is None else [direction],
    )


def _paired_columns(
    config: PlotConfig,
) -> tuple[list[ColumnRef], list[ColumnRef], list[ColumnRef | None]]:
    """Pair the legacy x, y and direction specs one entry per series."""
    if config.x_col is None or config.y_cols is None:
        msg = "x_col and y_cols must be specified in PlotConfig"
        raise ValueError(msg)
    x_refs: list[ColumnRef] = list(config.x_col) if isinstance(config.x_col, list) else [config.x_col]
    y_refs: list[ColumnRef] = list(config.y_cols)
    if len(x_refs) == 1:
        x_refs = x_refs * len(y_refs)
    elif len(x_refs) != len(y_refs):
        msg = (
            f"x_col length ({len(x_refs)}) and y_cols length ({len(y_refs)}) "
            "must be equal or x_col must be a single column"
        )
        raise ValueError(msg)
    return x_refs, y_refs, _padded_directions(config.direction_cols, len(y_refs))


def _padded_directions(direction_cols: Sequence[ColumnRef | None] | None, count: int) -> list[ColumnRef | None]:
    """One direction spec per series: shorter lists are padded with ``None``."""
    refs: list[ColumnRef | None] = list(direction_cols or [])
    if len(refs) > count:
        msg = f"direction_cols length ({len(refs)}) cannot exceed number of y columns ({count})"
        raise ValueError(msg)
    return refs + [None] * (count - len(refs))


def _y_axis_label(axis: AxisConfig, axis_label_of: AxisLabelFunction) -> str | None:
    """``None`` lets the planner derive the y label per figure from its series' units (GE-11)."""
    if axis.label_origin == "derived":
        return None
    return axis_label_of(axis, "Y")


def _axis_spec(axis: AxisConfig, label: str | None) -> AxisSpec:
    return AxisSpec(
        label=label,
        scale=axis.scale,
        limits=axis.lim,
        grid=axis.grid,
        invert=axis.invert,
        tick_format=axis.tick_format,
    )


def _legend_spec(config: PlotConfig) -> LegendSpec:
    legend = config.legend
    return LegendSpec(
        max_items=legend.max_items,
        info=legend.info,
        loc=legend.loc,
        policy=legend.policy,
        outside_threshold=legend.outside_threshold,
        bottom_threshold=legend.bottom_threshold,
        ncol=legend.ncol,
    )


def _direction_value(value: Any) -> str:
    """Normalize a direction key the way the plan normalizes direction cells."""
    return str(value.value) if isinstance(value, Enum) else str(value)


def _direction_filter(direction: DirectionConfig) -> tuple[str, ...]:
    values: list[str] = []
    for value in direction.filters or []:
        if value is None:
            continue
        normalized = _direction_value(value)
        if normalized not in values:
            values.append(normalized)
    return tuple(values)


def _direction_colors(direction: DirectionConfig) -> dict[str, str]:
    """Colours apply only when the caller opted in (``use_custom_colors``)."""
    if not getattr(direction, "use_custom_colors", False):
        return {}
    return {_direction_value(key): color for key, color in direction.colors.items()}


def _base_name(config: PlotConfig) -> str:
    return str(config.output.base_name or config.title or _DEFAULT_BASE_NAME)
