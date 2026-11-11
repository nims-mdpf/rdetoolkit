"""Headless scientific plotting nodes for rdetoolkit v2."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
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

#: A line-series pair: x column, y column and an optional legend label.
LinePair = tuple[str, str] | tuple[str, str, str]


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
    df: pd.DataFrame, out: OutputContext, filename: str, *, x: str | None = None,
    y: str | Sequence[str] | None = None, pairs: Sequence[LinePair] | None = None,
    labels: Sequence[str] | None = None,
    title: str | None = None, xlabel: str | None = None, ylabel: str | None = None,
    yscale: str = "linear", legend: bool = True, grid: bool = False,
    label_fontsize: float | str | None = None, figsize: tuple[float, float] | None = None,
    dpi: float = _DPI, bbox_inches: str | None = "tight", pad_inches: float | None = None,
    kind: OutputKind = "main_image",
) -> Path:
    """Plot selected columns or independent x/y pairs.

    The scientific-plot defaults are a headless Agg renderer, 150 DPI and a
    tight bounding box. Axis-label font sizes follow matplotlib rcParams
    unless ``label_fontsize`` is given. Output is canonical under
    ``out.main_image``, as in
    ``retired/outputcontext_save_methods_v20.py::save_graph``.

    Args:
        df: Data frame whose columns become line series.
        out: Output resource context.
        filename: Simple raster-image filename.
        x: Horizontal coordinate column; omitted to use the index.
        y: Measurement column or columns; omitted to use columns other than x.
        pairs: Independent ``(x, y)`` or ``(x, y, label)`` column pairs,
            mutually exclusive with x and y. A pair without a label is
            labelled with its y column.
        labels: Legend label of each series, in series order. Defaults to the
            y column names. Cannot be combined with labelled pairs.
        title: Optional plot title.
        xlabel: Optional horizontal axis label.
        ylabel: Optional vertical axis label.
        yscale: Matplotlib vertical axis scale.
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
        ValueError: If the data frame has no columns, or the series, pairs or
            labels are inconsistent.
    """
    if df.shape[1] == 0:
        msg = "plot_lines requires at least one data column"
        raise ValueError(msg)
    selections = _line_selections(df, x=x, y=y, pairs=pairs)
    series_labels = _series_labels(selections, labels)
    x_label, y_label = _line_labels(df, x, selections, xlabel, ylabel)
    fig, ax = plt.subplots(figsize=figsize)
    try:
        for (x_column, y_column, _), label in zip(selections, series_labels, strict=True):
            ax.plot(df.index if x_column is None else df[x_column], df[y_column], label=label)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        # ``set_xlabel(fontsize=None)`` would reset the label to ``font.size``,
        # so the size is only touched when given, keeping rcParams otherwise.
        if label_fontsize is not None:
            ax.xaxis.label.set_fontsize(label_fontsize)
            ax.yaxis.label.set_fontsize(label_fontsize)
        ax.set(title=title or "", yscale=yscale)
        if grid:
            ax.grid(True)
        if legend:
            ax.legend()
        return out.write_bytes(kind, filename, _figure_bytes(fig, filename, dpi=dpi, bbox_inches=bbox_inches, pad_inches=pad_inches))
    finally:
        plt.close(fig)


_Selection = tuple[str | None, str, str | None]


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
    default_y = ", ".join(str(column) for _, column, _ in selections)
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
