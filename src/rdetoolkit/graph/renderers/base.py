"""Renderer protocols.

``BaseRenderer`` is the legacy ``(df, config)`` adapter protocol the strategies call.
``GraphRenderer`` is the plan-consuming protocol of the spec API (GE-07): a renderer
declares what it produces in ``RendererCapabilities`` so the engine can select one and
reject unsupported requests before any output file is touched.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Protocol, runtime_checkable

import pandas as pd

from rdetoolkit.graph.models import PlotConfig

if TYPE_CHECKING:
    from rdetoolkit.graph.plan import FigurePlan, PlotData, PlotPlan

#: Figure kinds a ``PlotPlan`` can contain.
FIGURE_KINDS: Final = frozenset({"overlay", "individual"})


class BaseRenderer(Protocol):
    """Protocol for renderer classes.

    Renderers are responsible for HOW to render (actual drawing logic).
    Strategies decide WHAT to render (workflow orchestration).

    Design separation:
        - Strategy: Workflow orchestration, file naming, output control
        - Renderer: Pure rendering logic, returns Figure objects only
        - I/O layer: File saving
    """

    def render_overlay(self, df: pd.DataFrame, config: PlotConfig) -> Any:
        """Render all data series on a single graph.

        Args:
            df: DataFrame containing plot data
            config: Plot configuration

        Returns:
            matplotlib.figure.Figure or plotly.graph_objs.Figure
        """
        ...

    def render_individual(
        self,
        df: pd.DataFrame,
        config: PlotConfig,
        y_col_index: int,
        series_position: int | None = None,
    ) -> Any:
        """Render individual graph for a single series.

        Args:
            df: DataFrame containing plot data
            config: Plot configuration
            y_col_index: Index of y column to render
            series_position: Position of the series in the original specification
                              (used when x columns are provided per-series)

        Returns:
            matplotlib.figure.Figure
        """
        ...


@dataclass(frozen=True, slots=True)
class RendererCapabilities:
    """What a renderer can produce, declared up front.

    Attributes:
        renderer_id: Stable id, recorded on every artifact the renderer produces.
        formats: Output formats ``export`` accepts (lower-cased on construction).
        figure_kinds: Figure kinds ``render`` accepts: ``"overlay"`` and/or ``"individual"``.
        requires: Importable module names the renderer needs (optional dependencies).
        install_hint: What to run when a required module is missing.
        applies_rc_params: Whether ``StyleSpec.rc_params`` (Matplotlib rcParams) affect
            the output; when false and rcParams were set explicitly, the engine reports a
            ``style_ignored`` diagnostic on the renderer's artifacts.
    """

    renderer_id: str
    formats: frozenset[str]
    figure_kinds: frozenset[str]
    requires: tuple[str, ...] = ()
    install_hint: str = ""
    applies_rc_params: bool = False

    def __post_init__(self) -> None:
        """Validate the declaration and normalize format names.

        Raises:
            ValueError: For an empty id, no formats or an empty format name, no figure
                kinds or an unknown kind, or ``requires`` that is not a tuple of
                non-empty module names.
        """
        if not isinstance(self.renderer_id, str) or not self.renderer_id:
            msg = f"renderer_id must be a non-empty string, got {self.renderer_id!r}"
            raise ValueError(msg)
        object.__setattr__(self, "formats", _formats(self.formats))
        kinds = frozenset(self.figure_kinds)
        if not kinds or not kinds <= FIGURE_KINDS:
            msg = f"figure_kinds must be a non-empty subset of {sorted(FIGURE_KINDS)}, got {sorted(kinds)}"
            raise ValueError(msg)
        object.__setattr__(self, "figure_kinds", kinds)
        if not isinstance(self.requires, tuple) or not all(isinstance(name, str) and name for name in self.requires):
            msg = f"requires must be a tuple of non-empty module names, got {self.requires!r}"
            raise ValueError(msg)

    def supports(self, fmt: str, kind: str) -> bool:
        """Return whether ``fmt`` (case-insensitive) is produced for figures of ``kind``.

        Args:
            fmt: Output format, for example ``"png"``.
            kind: ``"overlay"`` or ``"individual"``.
        """
        return fmt.lower() in self.formats and kind in self.figure_kinds


def _formats(formats: Iterable[str]) -> frozenset[str]:
    normalized = frozenset(fmt.lower() if isinstance(fmt, str) else fmt for fmt in formats)
    if not normalized or not all(isinstance(fmt, str) and fmt for fmt in normalized):
        msg = f"formats must be a non-empty set of non-empty strings, got {sorted(map(str, normalized))}"
        raise ValueError(msg)
    return normalized


@runtime_checkable
class GraphRenderer(Protocol):
    """A renderer of planned figures (spec API).

    Instances are created per registry and a registry per graph operation, so a
    renderer may keep per-operation state but never process-global state.
    """

    @property
    def capabilities(self) -> RendererCapabilities:
        """The formats, figure kinds and optional dependencies of this renderer."""
        ...

    def render(self, plan: PlotPlan, figure: FigurePlan, data: PlotData) -> Any:
        """Draw one planned figure and return a self-contained handle.

        Args:
            plan: The executed plan (columns, labels, colours, style).
            figure: One of ``plan.figures``, of a kind the renderer declares.
            data: The frames the plan was built from.

        Returns:
            A handle ``export`` turns into the same bytes whatever the ambient global
            state; handed to the caller as is when no output is requested.
        """
        ...

    def export(self, handle: Any, fmt: str, *, dpi: int) -> bytes:
        """Serialize a rendered handle.

        Args:
            handle: A value returned by ``render``.
            fmt: One of the declared formats.
            dpi: Raster resolution (ignored by non-raster formats).

        Returns:
            The artifact content.
        """
        ...

    def close(self, handle: Any) -> None:
        """Release a handle the caller will never receive (after export or on failure)."""
        ...
