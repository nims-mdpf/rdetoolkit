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


def _figure_bytes(fig: plt.Figure, filename: str, *, dpi: float = _DPI) -> bytes:
    suffix = Path(filename).suffix.lower().lstrip(".") or "png"
    image_format = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
    buffer = BytesIO()
    fig.savefig(buffer, format=image_format, dpi=dpi, bbox_inches="tight")
    return buffer.getvalue()


@node(tags=["builtin", "plot"], version="2.0.0", idempotent=True)
def plot_lines(
    df: pd.DataFrame, out: OutputContext, filename: str, *, x: str | None = None,
    y: str | Sequence[str] | None = None, pairs: Sequence[tuple[str, str]] | None = None,
    title: str | None = None, xlabel: str | None = None, ylabel: str | None = None,
    yscale: str = "linear", legend: bool = True, figsize: tuple[float, float] | None = None,
    dpi: float = _DPI, kind: OutputKind = "main_image",
) -> Path:
    """Plot selected columns or independent x/y pairs.

    The scientific-plot defaults are a headless Agg renderer, 150 DPI, and
    10-point axis labels. Output is canonical under ``out.main_image``, as in
    ``retired/outputcontext_save_methods_v20.py::save_graph``.

    Args:
        df: Data frame whose columns become line series.
        out: Output resource context.
        filename: Simple raster-image filename.
        x: Horizontal coordinate column; omitted to use the index.
        y: Measurement column or columns; omitted to use columns other than x.
        pairs: Independent x/y column pairs, mutually exclusive with x and y.
        title: Optional plot title.
        xlabel: Optional horizontal axis label.
        ylabel: Optional vertical axis label.
        yscale: Matplotlib vertical axis scale.
        legend: Whether to show series labels.
        figsize: Figure dimensions in inches.
        dpi: Raster resolution in dots per inch.
        kind: Output directory kind.

    Returns:
        Path to the rendered plot.

    Raises:
        ValueError: If the data frame has no columns.
    """
    if df.shape[1] == 0:
        msg = "plot_lines requires at least one data column"
        raise ValueError(msg)
    selections = _line_selections(df, x=x, y=y, pairs=pairs)
    x_label, y_label = _line_labels(df, x, selections, xlabel, ylabel)
    fig, ax = plt.subplots(figsize=figsize)
    try:
        for x_column, y_column in selections:
            ax.plot(df.index if x_column is None else df[x_column], df[y_column], label=str(y_column))
        ax.set_xlabel(x_label, fontsize=_FONT_SIZE)
        ax.set_ylabel(y_label, fontsize=_FONT_SIZE)
        ax.set(title=title or "", yscale=yscale)
        if legend:
            ax.legend()
        return out.write_bytes(kind, filename, _figure_bytes(fig, filename, dpi=dpi))
    finally:
        plt.close(fig)


def _line_selections(df: pd.DataFrame, *, x: str | None, y: str | Sequence[str] | None, pairs: Sequence[tuple[str, str]] | None) -> list[tuple[str | None, str]]:
    if pairs is not None:
        if x is not None or y is not None:
            msg = "Specify either pairs or x/y column selection"
            raise ValueError(msg)
        selections: list[tuple[str | None, str]] = list(pairs)
    else:
        selections = [(x, column) for column in _line_columns(df, x, y)]
    if not selections:
        msg = "plot_lines requires at least one measurement series"
        raise ValueError(msg)
    return selections


def _line_columns(df: pd.DataFrame, x: str | None, y: str | Sequence[str] | None) -> list[str]:
    if y is None:
        return [column for column in df.columns if column != x]
    return [y] if isinstance(y, str) else list(y)


def _line_labels(df: pd.DataFrame, x: str | None, selections: Sequence[tuple[str | None, str]], xlabel: str | None, ylabel: str | None) -> tuple[str, str]:
    default_x = str(x if x is not None else df.index.name or "index")
    default_y = ", ".join(str(column) for _, column in selections)
    return xlabel if xlabel is not None else default_x, ylabel if ylabel is not None else default_y


@node(tags=["builtin", "plot"], version="2.0.0", idempotent=True)
def save_figure(fig: plt.Figure, out: OutputContext, filename: str, *, kind: OutputKind = "main_image", dpi: float = _DPI) -> Path:
    """Save a caller-owned matplotlib figure without closing it.

    Args:
        fig: Figure created and managed by the caller.
        out: Output resource context.
        filename: Simple image filename, whose suffix selects the format.
        kind: Output directory kind.
        dpi: Raster resolution in dots per inch.

    Returns:
        Path to the rendered figure.
    """
    return out.write_bytes(kind, filename, _figure_bytes(fig, filename, dpi=dpi))


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
