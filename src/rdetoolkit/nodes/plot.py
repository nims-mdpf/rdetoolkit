"""Headless scientific plotting nodes for rdetoolkit v2."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from rdetoolkit.core.node import node  # noqa: E402
from rdetoolkit.types import OutputContext  # noqa: E402

_DPI = 150
_FONT_SIZE = 10


def _figure_bytes(fig: plt.Figure, filename: str) -> bytes:
    suffix = Path(filename).suffix.lower().lstrip(".") or "png"
    image_format = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
    buffer = BytesIO()
    fig.savefig(buffer, format=image_format, dpi=_DPI, bbox_inches="tight")
    return buffer.getvalue()


@node(tags=["builtin", "plot"], version="2.0.0", idempotent=True)
def plot_lines(df: pd.DataFrame, out: OutputContext, filename: str) -> Path:
    """Plot every data-frame column against its index.

    The scientific-plot defaults are a headless Agg renderer, 150 DPI, and
    10-point axis labels. Output is canonical under ``out.main_image``, as in
    ``retired/outputcontext_save_methods_v20.py::save_graph``.

    Args:
        df: Data frame whose columns become line series.
        out: Output resource context.
        filename: Simple raster-image filename.

    Returns:
        Path to the rendered plot.

    Raises:
        ValueError: If the data frame has no columns.
    """
    if df.shape[1] == 0:
        msg = "plot_lines requires at least one data column"
        raise ValueError(msg)
    fig, ax = plt.subplots()
    try:
        for column in df.columns:
            ax.plot(df.index, df[column], label=str(column))
        ax.set_xlabel(str(df.index.name or "index"), fontsize=_FONT_SIZE)
        ax.set_ylabel(", ".join(str(column) for column in df.columns), fontsize=_FONT_SIZE)
        ax.legend()
        return out.write_bytes("main_image", filename, _figure_bytes(fig, filename))
    finally:
        plt.close(fig)


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
