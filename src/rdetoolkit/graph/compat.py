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
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Sequence
from enum import Enum
from typing import Any

import pandas as pd

from rdetoolkit.graph.models import AxisConfig, DirectionConfig, PlotConfig
from rdetoolkit.graph.plan import PlotPlan, build_plot_plan
from rdetoolkit.graph.spec import AxisSpec, ColumnRef, GraphSpec, LegendSpec, Origin, SeriesSpec
from rdetoolkit.graph.textutils import parse_header, titleize

__all__ = [
    "AxisLabelFunction",
    "LabelFunction",
    "legacy_mpl_axis_label",
    "legacy_mpl_label",
    "legacy_plotly_axis_label",
    "legacy_plotly_label",
    "plan_from_config",
]

LabelFunction = Callable[[str, bool], str]
"""``(raw_header, humanize) -> legend label``."""

AxisLabelFunction = Callable[[AxisConfig, str], str]
"""``(axis_config, default_label) -> final axis label``."""

_DEFAULT_BASE_NAME = "plot"


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
        PlotRequestError: For a column reference that matches no or several columns.
        TypeError: For a column reference that is neither ``int`` nor ``str``.
    """
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
        y_axis=_axis_spec(config.y_axis, axis_label_of(config.y_axis, "Y")),
        legend=_legend_spec(config),
        direction_filter=_direction_filter(config.direction),
        direction_colors=_direction_colors(config.direction),
        label_style="raw",
        unit_policy="warn",
    )
    plan = build_plot_plan(df, spec, base_name=_base_name(config))
    labels = [label_of(entry.y_name, bool(config.humanize)) for entry in plan.series]
    relabelled = plan.with_labels(labels)
    # The labels follow the legacy header rule, so they are derived, not caller-given.
    origins: dict[str, Origin] = dict(relabelled.origins)
    origins.update({f"series[{entry.series_id}].label": "derived" for entry in relabelled.series})
    return dataclasses.replace(relabelled, origins=origins)


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


def _axis_spec(axis: AxisConfig, label: str) -> AxisSpec:
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
