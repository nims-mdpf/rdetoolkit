from collections.abc import Mapping
from contextlib import AbstractContextManager
from typing import Any, Final

from matplotlib.axes import Axes
from matplotlib.figure import Figure

__all__ = ["DEFAULT_EXPORT_DPI", "detach_figure", "export_figure", "new_figure", "style_scope"]

DEFAULT_EXPORT_DPI: Final[int]

def style_scope(rc: Mapping[str, Any] | None = ...) -> AbstractContextManager[None]: ...
def new_figure(figure_size: tuple[float, float] | None, *, tight_layout: bool = ...) -> tuple[Figure, Axes]: ...
def detach_figure(fig: Figure, *, dpi: float = ...) -> None: ...
def export_figure(
    fig: Figure,
    fmt: str,
    *,
    dpi: float,
    bbox_inches: str | None = ...,
    pad_inches: float | None = ...,
) -> bytes: ...
