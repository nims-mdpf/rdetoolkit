"""Render coordination utilities for managing plot rendering workflows.

This module provides functions for coordinating the rendering process across
multiple strategies (overlay, individual) and collecting their results into
unified collections for further processing or file output.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rdetoolkit.graph import compat
from rdetoolkit.graph.exceptions import PlotRequestError
from rdetoolkit.graph.models import (
    MatplotlibArtifact,
    PlotMode,
    RenderCollections,
    RenderResult,
)
from rdetoolkit.graph.renderers.base import BaseRenderer
from rdetoolkit.graph.renderers.registry import RendererRegistry, builtin_renderers, check_requirements
from rdetoolkit.graph.strategies.all_graphs import LegacyHtmlRenderer, OverlayStrategy, legacy_adapter
from rdetoolkit.graph.strategies.individual import IndividualStrategy

if TYPE_CHECKING:
    import pandas as pd

    from rdetoolkit.graph.models import PlotConfig

_INDIVIDUAL_FORMAT = "png"  # IndividualStrategy writes PNG files


def collect_render_results(
    df: pd.DataFrame,
    config: PlotConfig,
    plot_mode: PlotMode,
    *,
    renderers: RendererRegistry | None = None,
) -> RenderCollections:
    """Render graphs according to the selected strategy.

    Coordinates the execution of appropriate rendering strategies based on the
    plot mode and configuration. Delegates rendering to OverlayStrategy and/or
    IndividualStrategy as needed.

    Args:
        df: Input DataFrame containing data to plot
        config: Plot configuration specifying rendering parameters
        plot_mode: Rendering mode (overlay or individual; ``PlotMode.DUAL_AXIS`` is
            not supported and raises)
        renderers: Registry the renderers are selected from by capability; ``None``
            uses a new ``builtin_renderers()`` registry for this call. Selected
            renderers must provide the legacy adapter methods.

    Returns:
        RenderCollections containing overlay and individual render results

    Raises:
        PlotRequestError: ``reason="dual_axis_unsupported"`` when ``plot_mode`` or
            ``config.mode`` is ``PlotMode.DUAL_AXIS`` or ``config.y2_axis`` is set
            (checked first; there is no fallback to other figures), or
            ``reason="no_figures"`` when individual mode is requested
            while ``config.output.no_individual`` disables individual plots.
        UnsupportedFormatError: If no renderer covers a requested format.
        RendererUnavailableError: If HTML is requested and the HTML renderer's
            optional dependency (Plotly) is missing; raised before anything is drawn.
        TypeError: If a selected renderer lacks the legacy adapter method.

    Examples:
        >>> from rdetoolkit.graph.models import PlotMode, PlotConfig
        >>> import pandas as pd
        >>> df = pd.DataFrame({"x": [1, 2, 3], "y": [1, 4, 9]})
        >>> config = PlotConfig(mode=PlotMode.OVERLAY)
        >>> results = collect_render_results(df, config, PlotMode.OVERLAY)
        >>> len(results.overlay) > 0
        True
    """
    # Before every other check: a dual-axis request must name its real cause, and
    # it must never degrade into individual figures as it did before v2.0.
    compat.reject_dual_axis(config, plot_mode)
    if plot_mode != PlotMode.OVERLAY and config.output.no_individual:
        # Individual-only rendering with individual plots disabled can produce
        # nothing; an empty result must not look like a successful run.
        msg = "mode='individual' with no_individual=True produces no figures"
        raise PlotRequestError(msg, reason="no_figures")
    registry = builtin_renderers() if renderers is None else renderers
    # Every renderer is selected and checked before the first figure is drawn.
    overlay = _overlay_strategy(registry, config) if plot_mode == PlotMode.OVERLAY else None
    individual = None if config.output.no_individual else IndividualStrategy(_legacy(registry, _INDIVIDUAL_FORMAT, "individual"))

    # One legacy call: the figures share one plan per backend and warn once (IC-6).
    with compat.legacy_call():
        overlay_results: list[RenderResult] = [] if overlay is None else overlay.render(df, config)
        # IndividualStrategy returns None only for no_individual, which built no strategy.
        individual_results: list[RenderResult] = [] if individual is None else individual.render(df, config) or []

    return RenderCollections(
        overlay=overlay_results,
        individual=individual_results,
    )


def _requested_formats(config: PlotConfig) -> list[str]:
    return [fmt.lower() for fmt in (config.output.formats or ["png"])]


def _overlay_strategy(registry: RendererRegistry, config: PlotConfig) -> OverlayStrategy:
    formats = _requested_formats(config)
    image_format = next((fmt for fmt in formats if fmt != "html"), "png")
    html_renderer: LegacyHtmlRenderer | None = None
    if "html" in formats:
        selected = registry.for_format("html", "overlay")
        check_requirements(selected)
        html_renderer = legacy_adapter(selected, "render_html")
    return OverlayStrategy(_legacy(registry, image_format, "overlay"), html_renderer=html_renderer)


def _legacy(registry: RendererRegistry, fmt: str, kind: str) -> BaseRenderer:
    method = "render_overlay" if kind == "overlay" else "render_individual"
    renderer: BaseRenderer = legacy_adapter(registry.for_format(fmt, kind), method)
    return renderer


def build_matplotlib_artifacts(
    collections: RenderCollections,
) -> list[MatplotlibArtifact]:
    """Convert render results into in-memory artifacts.

    Transforms RenderCollections into a list of MatplotlibArtifact objects
    suitable for in-memory use or programmatic access. Filters out HTML format
    results as they are not suitable for matplotlib artifact representation.

    Args:
        collections: Rendered results from overlay and individual strategies

    Returns:
        List of MatplotlibArtifact objects with metadata

    Examples:
        >>> from rdetoolkit.graph.models import RenderCollections, RenderResult
        >>> fig = object()  # Mock figure
        >>> collections = RenderCollections(
        ...     overlay=[RenderResult(fig, "overlay.png", "png")],
        ...     individual=[RenderResult(fig, "individual.png", "png")]
        ... )
        >>> artifacts = build_matplotlib_artifacts(collections)
        >>> len(artifacts)
        2
        >>> artifacts[0].filename
        'overlay.png'
    """
    artifacts: list[MatplotlibArtifact] = []
    for result in collections.all_results():
        if result.format.lower() == "html":
            continue
        metadata = {"format": result.format}
        artifacts.append(
            MatplotlibArtifact(
                filename=result.filename,
                figure=result.figure,
                metadata=metadata,
            ),
        )
    return artifacts
