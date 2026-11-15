"""Matplotlib runtime helpers: scoped style and pyplot-free figure ownership (GE-09).

Rendering must neither leave rcParams changed nor accumulate pyplot figures in long
batch jobs. Engine-owned figures are therefore plain ``Figure`` objects with an Agg
canvas (never registered with pyplot, so there is nothing to close), and every style
change is confined to ``matplotlib.rc_context``. Nothing here switches the backend.

Matplotlib resolves relative font sizes and the tight-layout pad when a figure is
drawn, so a figure built inside a style scope and saved outside it would look
different. ``detach_figure`` draws once inside the scope and freezes those values.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from io import BytesIO
from typing import Any, Final, cast

import matplotlib as mpl
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.axis import Axis
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.text import Text

__all__ = ["DEFAULT_EXPORT_DPI", "detach_figure", "export_figure", "new_figure", "style_scope"]

DEFAULT_EXPORT_DPI: Final = 300
"""Resolution of the legacy ``FileWriter`` and of ``OutputSpec.dpi`` by default."""

# Tick parameters a new Tick reads from rcParams when the axis has no explicit value.
# Ticks are created lazily while drawing, so these must be pinned before leaving a scope.
_TICK_RC_KEYS: Final = (
    ("direction", "{axis}tick.direction"),
    ("length", "{axis}tick.{which}.size"),
    ("width", "{axis}tick.{which}.width"),
    ("pad", "{axis}tick.{which}.pad"),
    ("color", "{axis}tick.color"),
    ("labelcolor", "{axis}tick.labelcolor"),
    ("labelsize", "{axis}tick.labelsize"),
    ("grid_color", "grid.color"),
    ("grid_alpha", "grid.alpha"),
    ("grid_linewidth", "grid.linewidth"),
    ("grid_linestyle", "grid.linestyle"),
)


def style_scope(rc: Mapping[str, Any] | None = None) -> AbstractContextManager[None]:
    """Return a context in which rcParams changes are undone on exit.

    Args:
        rc: rcParams applied on entry, over the ambient values; ``None`` applies nothing.

    Returns:
        A context manager restoring every rcParam (also when the block raises). The
        backend is left alone.
    """
    # rc_context's stub only accepts literal rcParams keys; keys arrive here as plain str.
    return mpl.rc_context(cast("Any", None if rc is None else dict(rc)))


def new_figure(figure_size: tuple[float, float] | None, *, tight_layout: bool = True) -> tuple[Figure, Axes]:
    """Create a single-axes figure that pyplot does not track.

    Args:
        figure_size: Size in inches; ``None`` uses ``rcParams["figure.figsize"]``.
        tight_layout: Use the tight layout engine, as the legacy renderer does.

    Returns:
        The figure (with an Agg canvas) and its axes. The caller owns both; dropping
        the last reference releases them, ``plt.close`` is not required.
    """
    fig = Figure(figsize=figure_size, tight_layout=tight_layout)
    FigureCanvasAgg(fig)
    return fig, fig.add_subplot()


def detach_figure(fig: Figure, *, dpi: float = DEFAULT_EXPORT_DPI) -> None:
    """Freeze draw-time style so the figure renders the same outside its style scope.

    Call inside the scope the figure was built in, before handing it to a caller.
    Tick parameters are pinned (tick density depends on the tick label size), the
    figure is drawn once at ``dpi`` (the tight layout is resolved in device pixels),
    relative font sizes are pinned and the layout engine is switched off. An export
    at ``dpi`` afterwards is then byte-identical to one made inside the scope.

    Args:
        fig: The figure to freeze; it stays fully drawable and editable.
        dpi: Resolution the caller is expected to save at (the legacy writer's 300).
    """
    for ax in fig.axes:
        for axis_name, axis in (("x", ax.xaxis), ("y", ax.yaxis)):
            _pin_tick_params(axis, axis_name)
    original_dpi = fig.dpi
    fig.set_dpi(dpi)
    try:
        fig.canvas.draw()
    finally:
        fig.set_dpi(original_dpi)
    for text in fig.findobj(Text):
        # Relative sizes such as "medium" resolve against the current font.size.
        text.set_fontsize(text.get_fontsize())
    fig.set_layout_engine("none")


def _pin_tick_params(axis: Axis, axis_name: str) -> None:
    """Copy the in-scope rcParams into the axis for every tick parameter not set explicitly."""
    for which in ("major", "minor"):
        explicit = axis.get_tick_params(which=which)
        missing = {
            key: _tick_rc_value(key, rc_key.format(axis=axis_name, which=which), axis_name)
            for key, rc_key in _TICK_RC_KEYS
            if key not in explicit
        }
        axis.set_tick_params(which=which, **missing)


def _tick_rc_value(key: str, rc_key: str, axis_name: str) -> Any:
    rc = cast("Mapping[str, Any]", mpl.rcParams)
    value = rc[rc_key]
    if key == "labelsize":
        return FontProperties(size=value).get_size_in_points()
    if key == "labelcolor" and value == "inherit":
        return rc[f"{axis_name}tick.color"]
    return value


def export_figure(
    fig: Figure,
    fmt: str,
    *,
    dpi: float,
    bbox_inches: str | None = "tight",
    pad_inches: float | None = None,
) -> bytes:
    """Encode a figure as image bytes, the way the legacy ``FileWriter`` saves it.

    Args:
        fig: The figure to export.
        fmt: A Matplotlib output format such as ``"png"``, ``"svg"`` or ``"pdf"``.
        dpi: Resolution in dots per inch.
        bbox_inches: ``"tight"`` (legacy default) or ``None`` for the full canvas.
        pad_inches: Padding around a tight bounding box; ``None`` uses rcParams.

    Returns:
        The encoded image.

    Raises:
        ValueError: If Matplotlib does not support ``fmt``.
    """
    buffer = BytesIO()
    fig.savefig(buffer, format=fmt, dpi=dpi, bbox_inches=bbox_inches, pad_inches=pad_inches)
    return buffer.getvalue()
