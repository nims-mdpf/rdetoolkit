"""Headless scientific plotting nodes for rdetoolkit v2.

``plot_lines`` and ``plot_scatter`` are thin adapters over the Graph Engine: the
planner (``build_plot_plan``) resolves columns, pairs, frames and series labels,
``validate_axis_limits`` checks the axis limits and ``draw_series`` draws every
planned series. The nodes keep their own presentation (title, scales, grid,
legend, label font size, default axis labels) and plain Matplotlib defaults: none
of the csv2graph house style is applied. ``save_figure`` and ``save_html_figure``
save caller-owned figures.
"""

from __future__ import annotations

import re
import hashlib
import importlib
from pathlib import Path
from typing import Any
from collections.abc import Sequence

import matplotlib as mpl

mpl.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402

from rdetoolkit.core.node import node  # noqa: E402
from rdetoolkit.graph.plan import PlotData, PlotPlan, build_plot_plan, column_position  # noqa: E402
from rdetoolkit.graph.renderers.mpl_runtime import draw_series, export_figure  # noqa: E402
from rdetoolkit.graph.spec import GraphSpec, SeriesSpec  # noqa: E402
from rdetoolkit.graph.validation import validate_axis_limits  # noqa: E402
from rdetoolkit.types import OutputContext, OutputKind  # noqa: E402

_DPI = 150
_FONT_SIZE = 10
_PAIR_WITH_LABEL = 3
_DIV_ID_UNSAFE = re.compile(r"[^A-Za-z0-9_-]+")
_DIV_ID_DIGEST_LEN = 8
_PLOTLY_MISSING = 'save_html_figure requires plotly, which is not installed; install it with: pip install "rdetoolkit[plotly]"'
_NO_SERIES = "plot_lines requires at least one measurement series"

#: A line-series pair: x column, y column and an optional legend label.
LinePair = tuple[str, str] | tuple[str, str, str]
#: Axis range ``(lower, upper)``; a ``None`` bound keeps matplotlib's automatic limit.
AxisLimits = tuple[float | None, float | None]


def _figure_bytes(
    fig: plt.Figure, filename: str, *, dpi: float = _DPI, bbox_inches: str | None = "tight", pad_inches: float | None = None,
) -> bytes:
    suffix = Path(filename).suffix.lower().lstrip(".") or "png"
    image_format = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
    # ``None`` defers to matplotlib's own savefig defaults (rcParams), which is
    # exactly what a v1 ``fig.savefig(path)`` call used.
    return export_figure(fig, image_format, dpi=dpi, bbox_inches=bbox_inches, pad_inches=pad_inches)


@node(tags=["builtin", "plot"], version="2.0.0", idempotent=True)
def plot_lines(
    df: pd.DataFrame | Sequence[pd.DataFrame], out: OutputContext, filename: str, *, x: str | None = None,
    y: str | Sequence[str] | None = None, pairs: Sequence[LinePair] | None = None,
    labels: Sequence[str] | None = None,
    title: str | None = None, xlabel: str | None = None, ylabel: str | None = None,
    xscale: str = "linear", yscale: str = "linear", xlim: AxisLimits | None = None, ylim: AxisLimits | None = None,
    legend: bool = True, grid: bool = False,
    label_fontsize: float | str | None = None, figsize: tuple[float, float] | None = None,
    dpi: float = _DPI, bbox_inches: str | None = "tight", pad_inches: float | None = None,
    kind: OutputKind = "main_image",
) -> Path:
    """Plot selected columns or independent x/y pairs of one or more frames.

    The scientific-plot defaults are a headless Agg renderer, 150 DPI and a
    tight bounding box. Axis-label font sizes follow matplotlib rcParams
    unless ``label_fontsize`` is given. Output is canonical under
    ``out.main_image``, as in
    ``retired/outputcontext_save_methods_v20.py::save_graph``. Columns are
    resolved by the Graph Engine planner, so a column is addressed by its
    exact label and a label carried by several columns is ambiguous.

    Args:
        df: Data frame whose columns become line series, or a sequence of
            frames drawn in one image. The selection (x and y, or pairs)
            applies to each frame, so frames keep their own x values and
            length; the series follow frame order, then selection order.
        out: Output resource context.
        filename: Simple raster-image filename.
        x: Horizontal coordinate column; omitted to use the index.
        y: Measurement column or columns; omitted to use columns other than x.
        pairs: Independent ``(x, y)`` or ``(x, y, label)`` column pairs,
            mutually exclusive with x and y. A pair without a label is
            labelled with its y column.
        labels: Legend label of each series, in series order (across all
            frames). Defaults to the y column names. Cannot be combined with
            labelled pairs.
        title: Optional plot title.
        xlabel: Optional horizontal axis label. Defaults to the x column, or
            the index name (``index`` when unnamed) without an x column.
        ylabel: Optional vertical axis label. Defaults to the y column
            names, each named once.
        xscale: Matplotlib horizontal axis scale.
        yscale: Matplotlib vertical axis scale.
        xlim: Horizontal axis range ``(lower, upper)``, applied after the
            scale; a None bound keeps the automatic limit, so ``(0, None)``
            starts the axis at 0. None keeps both automatic. Reversed bounds
            invert the axis.
        ylim: Vertical axis range, with the same rules as ``xlim``.
        legend: Whether to show series labels.
        grid: Whether to draw the major grid lines.
        label_fontsize: Axis-label font size; None follows rcParams
            ``axes.labelsize``.
        figsize: Figure dimensions in inches.
        dpi: Raster resolution in dots per inch.
        bbox_inches: Passed to ``Figure.savefig``; None writes the whole
            canvas like a plain v1 ``fig.savefig(path)``.
        pad_inches: Padding around a tight bounding box; None uses rcParams
            ``savefig.pad_inches``.
        kind: Output directory kind.

    Returns:
        Path to the rendered plot.

    Raises:
        PlotRequestError: ``reason="unknown_column"`` or ``"ambiguous_column"``
            for a column matching no or several columns, and
            ``reason="invalid_axis_limits"`` for a non-finite bound, equal
            bounds or a bound ``<= 0`` on a ``"log"`` axis; raised before any
            figure exists. It is a ``ValueError``.
        ValueError: If no frame is given, a frame has no columns or
            contributes no series, or the series, pairs or labels are
            inconsistent.
    """
    frames = _frames(df)
    plan, selected = _line_plan(frames, x=x, y=y, pairs=pairs, labels=labels)
    limits = (_checked_limits(xlim, xscale, "x"), _checked_limits(ylim, yscale, "y"))
    x_label, y_label = _axis_labels(plan, frames[0], x=x, xlabel=xlabel, ylabel=ylabel)
    data = PlotData(frames=selected)
    # Deliberately a pyplot figure (closed below), not the engine's pyplot-free
    # new_figure: node contracts observe ``figure.number`` of the drawn axes.
    fig, ax = plt.subplots(figsize=figsize)
    try:
        for series in plan.series:
            draw_series(ax, plan, series, data, label=series.label)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        # ``set_xlabel(fontsize=None)`` would reset the label to ``font.size``,
        # so the size is only touched when given, keeping rcParams otherwise.
        if label_fontsize is not None:
            ax.xaxis.label.set_fontsize(label_fontsize)
            ax.yaxis.label.set_fontsize(label_fontsize)
        ax.set(title=title or "", xscale=xscale, yscale=yscale)
        _apply_limits(ax, *limits)
        if grid:
            ax.grid(True)
        if legend:
            ax.legend()
        return out.write_bytes(kind, filename, _figure_bytes(fig, filename, dpi=dpi, bbox_inches=bbox_inches, pad_inches=pad_inches))
    finally:
        plt.close(fig)


def _frames(df: pd.DataFrame | Sequence[pd.DataFrame]) -> list[pd.DataFrame]:
    frames = [df] if isinstance(df, pd.DataFrame) else list(df)
    if not frames:
        msg = "plot_lines requires at least one data frame"
        raise ValueError(msg)
    if any(frame.shape[1] == 0 for frame in frames):
        msg = "plot_lines requires at least one data column"
        raise ValueError(msg)
    return frames


def _line_plan(
    frames: list[pd.DataFrame], *, x: str | None, y: str | Sequence[str] | None,
    pairs: Sequence[LinePair] | None, labels: Sequence[str] | None,
) -> tuple[PlotPlan, tuple[pd.DataFrame, ...]]:
    selection = _line_request(x=x, y=y, pairs=pairs)
    # Node columns are labels (as in v1 frame indexing), while a GraphSpec ``int`` is a
    # position: every frame is reduced to its selected columns, in selection order,
    # so the spec addresses positions that mean the same thing in every frame.
    selected = tuple(_select_columns(frame, x, selection) for frame in frames)
    series, x_ref = _positional_series(selection, has_x=x is not None)
    # The spec forbids an explicit x together with x_default="index".
    # The caller names every series explicitly, so a mixed-unit selection is deliberate.
    common: dict[str, Any] = {"series": series, "layout": "overlay", "label_style": "raw", "unit_policy": "allow"}
    spec = GraphSpec(x=x_ref, **common) if x_ref is not None else GraphSpec(x_default="index", **common)
    plan = build_plot_plan(selected, spec)
    # The engine skips a frame without default series; the node never did.
    if {entry.frame for entry in plan.series} != set(range(len(frames))):
        raise ValueError(_NO_SERIES)
    return (plan if labels is None else _relabelled(plan, labels, pairs)), selected


#: One requested series: x label (None: the node-level x or the index), y label, legend label.
_Request = tuple[Any, Any, str | None]


def _line_request(*, x: Any, y: Any, pairs: Sequence[LinePair] | None) -> tuple[_Request, ...] | None:
    """Return the requested series, or None for the default (every column except x)."""
    if pairs is not None:
        if x is not None or y is not None:
            msg = "Specify either pairs or x/y column selection"
            raise ValueError(msg)
        selection = tuple(_pair_request(pair) for pair in pairs)
    elif y is None:
        return None
    else:
        selection = tuple((None, column, None) for column in ([y] if isinstance(y, str) or not isinstance(y, Sequence) else y))
    # An empty selection must not fall back to the planner's "every column" default.
    if not selection:
        raise ValueError(_NO_SERIES)
    return selection


def _pair_request(pair: Sequence[str]) -> _Request:
    if len(pair) == _PAIR_WITH_LABEL:
        return pair[0], pair[1], pair[2]
    if len(pair) == _PAIR_WITH_LABEL - 1:
        return pair[0], pair[1], None
    msg = f"plot_lines pairs must be (x, y) or (x, y, label), got {len(pair)} items"
    raise ValueError(msg)


def _select_columns(frame: pd.DataFrame, x: Any, selection: tuple[_Request, ...] | None) -> pd.DataFrame:
    """Reorder ``frame`` to the selected columns: [x], then each selection's (x,) y."""
    x_positions = [] if x is None else [column_position(frame, x, "x")]
    if selection is None:
        rest = [position for position in range(frame.shape[1]) if position not in x_positions]
        return frame.iloc[:, x_positions + rest]
    order = list(x_positions)
    for pair_x, column, _ in selection:
        if pair_x is not None:
            order.append(column_position(frame, pair_x, "x"))
        order.append(column_position(frame, column, "y"))
    return frame.iloc[:, order]


def _positional_series(selection: tuple[_Request, ...] | None, *, has_x: bool) -> tuple[tuple[SeriesSpec, ...], int | None]:
    """Series specs addressing the columns laid out by ``_select_columns``, and the x position."""
    x_ref = 0 if has_x else None
    if selection is None:
        return (), x_ref
    series: list[SeriesSpec] = []
    position = 1 if has_x else 0
    for pair_x, _, label in selection:
        pair_ref = None
        if pair_x is not None:
            pair_ref, position = position, position + 1
        series.append(SeriesSpec(x=pair_ref, y=position, label=label))
        position += 1
    return tuple(series), x_ref


def _relabelled(plan: PlotPlan, labels: Sequence[str], pairs: Sequence[LinePair] | None) -> PlotPlan:
    if pairs is not None and any(len(pair) == _PAIR_WITH_LABEL for pair in pairs):
        msg = "Specify series labels either in pairs or with labels=, not both"
        raise ValueError(msg)
    if len(labels) != len(plan.series):
        msg = f"plot_lines got {len(labels)} labels for {len(plan.series)} series"
        raise ValueError(msg)
    return plan.with_labels(labels)


def _axis_labels(plan: PlotPlan, first: pd.DataFrame, *, x: str | None, xlabel: str | None, ylabel: str | None) -> tuple[str, str]:
    # Node presentation rule over the resolved plan (the plan's overlay label
    # names only the first series): the x column, else the first frame's index
    # name (also for pairs); every distinct y column once.
    default_x = plan.series[0].x_name if x is not None else str(first.index.name or "index")
    default_y = ", ".join(dict.fromkeys(entry.y_name for entry in plan.series))
    return xlabel if xlabel is not None else default_x, ylabel if ylabel is not None else default_y


def _checked_limits(limits: AxisLimits | None, scale: str, axis: str) -> AxisLimits | None:
    # Any Matplotlib scale name is accepted; only "log" has the bound > 0 rule.
    return validate_axis_limits(limits, scale="log" if scale == "log" else "linear", axis=axis)


def _apply_limits(ax: Axes, xlim: AxisLimits | None, ylim: AxisLimits | None) -> None:
    # Limits follow the scale so they are not re-derived by a scale change.
    if xlim is not None:
        ax.set_xlim(*xlim)
    if ylim is not None:
        ax.set_ylim(*ylim)


@node(tags=["builtin", "plot"], version="2.0.0", idempotent=True)
def save_figure(
    fig: plt.Figure, out: OutputContext, filename: str, *, kind: OutputKind = "main_image", dpi: float = _DPI,
    bbox_inches: str | None = "tight", pad_inches: float | None = None,
) -> Path:
    """Save a caller-owned matplotlib figure without closing it.

    The bounding-box options are passed to ``Figure.savefig`` unchanged, so a
    v1 ``fig.savefig(path)`` is reproduced with ``bbox_inches=None`` and
    ``savefig(path, bbox_inches="tight", pad_inches=0)`` with those values.

    Args:
        fig: Figure created and managed by the caller.
        out: Output resource context.
        filename: Simple image filename, whose suffix selects the format.
        kind: Output directory kind.
        dpi: Raster resolution in dots per inch.
        bbox_inches: Bounding box; None writes the whole canvas.
        pad_inches: Padding around a tight bounding box; None uses rcParams
            ``savefig.pad_inches``.

    Returns:
        Path to the rendered figure.
    """
    return out.write_bytes(kind, filename, _figure_bytes(fig, filename, dpi=dpi, bbox_inches=bbox_inches, pad_inches=pad_inches))


@node(tags=["builtin", "plot"], version="2.0.0", idempotent=True)
def plot_scatter(df: pd.DataFrame, out: OutputContext, filename: str, x: str, y: str) -> Path:
    """Render a scatter plot for named x and y columns.

    The scientific-plot defaults are a headless Agg renderer, 150 DPI, and
    10-point labels. Output is written under ``out.main_image``. The columns
    are resolved by the Graph Engine planner.

    Args:
        df: Source data frame.
        out: Output resource context.
        filename: Simple raster-image filename.
        x: Column used for horizontal coordinates and label.
        y: Column used for vertical coordinates and label.

    Returns:
        Path to the rendered plot.

    Raises:
        PlotRequestError: ``reason="unknown_column"`` if either named column
            is absent, ``reason="ambiguous_column"`` if several columns carry
            the name; raised before any figure exists. It is a ``ValueError``.
    """
    # Labels, not positions (see _line_plan): x and y become positions 0 and 1.
    selected = df.iloc[:, [column_position(df, x, "x"), column_position(df, y, "y")]]
    spec = GraphSpec(
        x=0, series=(SeriesSpec(y=1),), mark="scatter", layout="overlay", label_style="raw", unit_policy="allow",
    )
    plan = build_plot_plan(selected, spec)
    figure = plan.figures[0]
    # A pyplot figure, closed below, for the same reason as in plot_lines.
    fig, ax = plt.subplots()
    try:
        draw_series(ax, plan, plan.series[0], PlotData(frames=(selected,)))
        ax.set_xlabel(figure.x_label, fontsize=_FONT_SIZE)
        ax.set_ylabel(figure.y_label, fontsize=_FONT_SIZE)
        return out.write_bytes("main_image", filename, _figure_bytes(fig, filename))
    finally:
        plt.close(fig)


@node(tags=["builtin", "plot"], version="2.0.0", idempotent=True)
def save_html_figure(
    fig: Any, out: OutputContext, filename: str, *, kind: OutputKind = "struct",
    include_plotlyjs: str | bool = "cdn", full_html: bool = True, div_id: str | None = None,
) -> Path:
    """Save a plotly figure as an interactive HTML file.

    The HTML is ``plotly.io.to_html`` output. Plotly gives the chart ``<div>``
    a random id, so the same figure would produce a different file on every
    run; this node derives a stable id from ``filename`` instead (``chart.html``
    becomes ``plotly-chart-<digest>``), making the artifact reproducible. plotly is
    imported only when the node runs, from the optional ``rdetoolkit[plotly]``
    extra.

    Args:
        fig: ``plotly.graph_objects.Figure``, or its dict form, created and
            managed by the caller.
        out: Output resource context.
        filename: Simple output filename, normally ending in ``.html``.
        kind: Output directory kind.
        include_plotlyjs: How plotly.js is included, as for
            ``plotly.io.to_html``: ``"cdn"`` references the CDN, True embeds
            the library, False omits it.
        full_html: Whether to write a complete HTML page; False writes only
            the ``<div>`` fragment.
        div_id: Id of the chart ``<div>``; None derives
            ``plotly-<stem>-<digest>`` from ``filename``: the stem with
            characters other than ASCII letters, digits, ``_`` and ``-``
            collapsed to ``-`` (``figure`` when nothing is left), then the
            first 8 hex digits of the SHA-256 of ``filename``, so different
            filenames give different ids.

    Returns:
        Path to the saved HTML file.

    Raises:
        ImportError: If plotly is not installed.
    """
    try:
        plotly_io = importlib.import_module("plotly.io")
    except ImportError as exc:
        raise ImportError(_PLOTLY_MISSING) from exc
    html: str = plotly_io.to_html(
        fig, include_plotlyjs=include_plotlyjs, full_html=full_html, div_id=div_id or _html_div_id(filename),
    )
    return out.write_bytes(kind, filename, html.encode("utf-8"))


def _html_div_id(filename: str) -> str:
    # The slug keeps the id readable but is lossy (``a b`` and ``a-b``, or any
    # two non-ASCII stems, collapse alike); the filename digest keeps ids of
    # different files distinct when their fragments share one page (#625).
    slug = _DIV_ID_UNSAFE.sub("-", Path(filename).stem).strip("-") or "figure"
    digest = hashlib.sha256(filename.encode("utf-8")).hexdigest()[:_DIV_ID_DIGEST_LEN]
    return f"plotly-{slug}-{digest}"
