"""Headless scientific plotting nodes for rdetoolkit v2."""

from __future__ import annotations

import re
import hashlib
import importlib
from io import BytesIO
from pathlib import Path
from typing import Any
from collections.abc import Sequence

import matplotlib as mpl

mpl.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from rdetoolkit.core.node import node  # noqa: E402
from rdetoolkit.types import OutputContext, OutputKind  # noqa: E402

_DPI = 150
_FONT_SIZE = 10
_PAIR_WITH_LABEL = 3
_DIV_ID_UNSAFE = re.compile(r"[^A-Za-z0-9_-]+")
_DIV_ID_DIGEST_LEN = 8
_PLOTLY_MISSING = 'save_html_figure requires plotly, which is not installed; install it with: pip install "rdetoolkit[plotly]"'

#: A line-series pair: x column, y column and an optional legend label.
LinePair = tuple[str, str] | tuple[str, str, str]
#: Axis range ``(lower, upper)``; a ``None`` bound keeps matplotlib's automatic limit.
AxisLimits = tuple[float | None, float | None]


def _figure_bytes(
    fig: plt.Figure, filename: str, *, dpi: float = _DPI, bbox_inches: str | None = "tight", pad_inches: float | None = None,
) -> bytes:
    suffix = Path(filename).suffix.lower().lstrip(".") or "png"
    image_format = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
    buffer = BytesIO()
    # ``None`` defers to matplotlib's own savefig defaults (rcParams), which is
    # exactly what a v1 ``fig.savefig(path)`` call used.
    fig.savefig(buffer, format=image_format, dpi=dpi, bbox_inches=bbox_inches, pad_inches=pad_inches)
    return buffer.getvalue()


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
    ``retired/outputcontext_save_methods_v20.py::save_graph``.

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
        xlabel: Optional horizontal axis label.
        ylabel: Optional vertical axis label. Defaults to the y column
            names, each named once.
        xscale: Matplotlib horizontal axis scale.
        yscale: Matplotlib vertical axis scale.
        xlim: Horizontal axis range ``(lower, upper)``, applied after the
            scale; a None bound keeps the automatic limit, so ``(0, None)``
            starts the axis at 0. None keeps both automatic.
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
        ValueError: If no frame is given, a frame has no columns, or the
            series, pairs or labels are inconsistent.
    """
    frames = _frames(df)
    series = [(frame, selection) for frame in frames for selection in _line_selections(frame, x=x, y=y, pairs=pairs)]
    selections = [selection for _, selection in series]
    series_labels = _series_labels(selections, labels)
    x_label, y_label = _line_labels(frames[0], x, selections, xlabel, ylabel)
    fig, ax = plt.subplots(figsize=figsize)
    try:
        for (frame, (x_column, y_column, _)), label in zip(series, series_labels, strict=True):
            ax.plot(frame.index if x_column is None else frame[x_column], frame[y_column], label=label)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        # ``set_xlabel(fontsize=None)`` would reset the label to ``font.size``,
        # so the size is only touched when given, keeping rcParams otherwise.
        if label_fontsize is not None:
            ax.xaxis.label.set_fontsize(label_fontsize)
            ax.yaxis.label.set_fontsize(label_fontsize)
        ax.set(title=title or "", xscale=xscale, yscale=yscale)
        # Limits follow the scale so they are not re-derived by a scale change.
        if xlim is not None:
            ax.set_xlim(*xlim)
        if ylim is not None:
            ax.set_ylim(*ylim)
        if grid:
            ax.grid(True)
        if legend:
            ax.legend()
        return out.write_bytes(kind, filename, _figure_bytes(fig, filename, dpi=dpi, bbox_inches=bbox_inches, pad_inches=pad_inches))
    finally:
        plt.close(fig)


_Selection = tuple[str | None, str, str | None]


def _frames(df: pd.DataFrame | Sequence[pd.DataFrame]) -> list[pd.DataFrame]:
    frames = [df] if isinstance(df, pd.DataFrame) else list(df)
    if not frames:
        msg = "plot_lines requires at least one data frame"
        raise ValueError(msg)
    if any(frame.shape[1] == 0 for frame in frames):
        msg = "plot_lines requires at least one data column"
        raise ValueError(msg)
    return frames


def _line_selections(df: pd.DataFrame, *, x: str | None, y: str | Sequence[str] | None, pairs: Sequence[LinePair] | None) -> list[_Selection]:
    if pairs is not None:
        if x is not None or y is not None:
            msg = "Specify either pairs or x/y column selection"
            raise ValueError(msg)
        selections = [_pair_selection(pair) for pair in pairs]
    else:
        selections = [(x, column, None) for column in _line_columns(df, x, y)]
    if not selections:
        msg = "plot_lines requires at least one measurement series"
        raise ValueError(msg)
    return selections


def _pair_selection(pair: Sequence[str]) -> _Selection:
    if len(pair) == _PAIR_WITH_LABEL:
        return pair[0], pair[1], pair[2]
    if len(pair) == _PAIR_WITH_LABEL - 1:
        return pair[0], pair[1], None
    msg = f"plot_lines pairs must be (x, y) or (x, y, label), got {len(pair)} items"
    raise ValueError(msg)


def _series_labels(selections: Sequence[_Selection], labels: Sequence[str] | None) -> list[str]:
    if labels is None:
        return [str(y_column) if label is None else label for _, y_column, label in selections]
    if any(label is not None for _, _, label in selections):
        msg = "Specify series labels either in pairs or with labels=, not both"
        raise ValueError(msg)
    if len(labels) != len(selections):
        msg = f"plot_lines got {len(labels)} labels for {len(selections)} series"
        raise ValueError(msg)
    return [str(label) for label in labels]


def _line_columns(df: pd.DataFrame, x: str | None, y: str | Sequence[str] | None) -> list[str]:
    if y is None:
        return [column for column in df.columns if column != x]
    return [y] if isinstance(y, str) else list(y)


def _line_labels(df: pd.DataFrame, x: str | None, selections: Sequence[_Selection], xlabel: str | None, ylabel: str | None) -> tuple[str, str]:
    default_x = str(x if x is not None else df.index.name or "index")
    # dict.fromkeys names a y column once when several frames repeat it.
    default_y = ", ".join(dict.fromkeys(str(column) for _, column, _ in selections))
    return xlabel if xlabel is not None else default_x, ylabel if ylabel is not None else default_y


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
    10-point labels. Output is written under ``out.main_image``.

    Args:
        df: Source data frame.
        out: Output resource context.
        filename: Simple raster-image filename.
        x: Column used for horizontal coordinates and label.
        y: Column used for vertical coordinates and label.

    Returns:
        Path to the rendered plot.

    Raises:
        KeyError: If either named column is absent.
    """
    x_values = df[x]
    y_values = df[y]
    fig, ax = plt.subplots()
    try:
        ax.scatter(x_values, y_values)
        ax.set_xlabel(x, fontsize=_FONT_SIZE)
        ax.set_ylabel(y, fontsize=_FONT_SIZE)
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
