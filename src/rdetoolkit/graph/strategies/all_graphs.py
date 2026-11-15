from __future__ import annotations

from typing import Any, Protocol

import pandas as pd

from rdetoolkit.graph.models import PlotConfig, RenderResult
from rdetoolkit.graph.renderers.base import BaseRenderer, GraphRenderer
from rdetoolkit.graph.renderers.registry import builtin_renderers, check_requirements
from rdetoolkit.graph.naming import DEFAULT_BASE_STEM, sanitize_stem


class LegacyHtmlRenderer(Protocol):
    """The legacy HTML adapter the overlay strategy calls (``PlotlyRenderer`` provides it)."""

    def render_html(self, df: pd.DataFrame, config: PlotConfig) -> Any:
        """Render the overlay of ``df`` as an HTML-capable figure."""
        ...


def legacy_adapter(renderer: GraphRenderer, method: str) -> Any:
    """Return ``renderer`` if it offers the legacy ``(df, config)`` adapter ``method``.

    The legacy facade keeps calling ``render_overlay`` / ``render_individual`` /
    ``render_html`` (rulings C-05/C-06), so a registry renderer selected for it must
    provide that method; plan-only renderers are used through ``render_graph``.

    Args:
        renderer: A renderer selected from a registry.
        method: The adapter method name.

    Returns:
        The same renderer.

    Raises:
        TypeError: If the renderer lacks the method.
    """
    if not callable(getattr(renderer, method, None)):
        renderer_id = renderer.capabilities.renderer_id
        msg = (
            f"Renderer {renderer_id!r} does not implement {method}(df, config), which the legacy "
            "csv2graph path needs; inject plan-based renderers through render_graph(renderers=...)"
        )
        raise TypeError(msg)
    return renderer


def builtin_html_renderer() -> LegacyHtmlRenderer:
    """Select the HTML renderer of a new builtin registry and check its optional modules.

    Returns:
        The builtin overlay HTML renderer (Plotly).

    Raises:
        RendererUnavailableError: If Plotly is not installed.
    """
    renderer = builtin_renderers().for_format("html", "overlay")
    check_requirements(renderer)
    html_renderer: LegacyHtmlRenderer = legacy_adapter(renderer, "render_html")
    return html_renderer


class OverlayStrategy:
    """Overlay all data series on a single graph.

    This strategy overlays all y-columns on a single figure with:
        - Direction-based coloring (if direction_cols specified)
        - Series-based coloring (default)
        - Legend with max_items control
        - Optional HTML output (Plotly)

    Workflow:
        1. Resolve the HTML renderer (and its optional modules) before drawing anything
        2. Delegate matplotlib rendering to renderer.render_overlay()
        3. Optionally create the HTML figure via html_renderer.render_html()
        4. Return list of RenderResult objects

    Example:
        >>> from rdetoolkit.graph.renderers import MatplotlibRenderer
        >>> renderer = MatplotlibRenderer()
        >>> strategy = OverlayStrategy(renderer)
        >>> results = strategy.render(df, config)
    """

    def __init__(self, renderer: BaseRenderer, *, html_renderer: LegacyHtmlRenderer | None = None) -> None:
        """Initialize strategy with renderer.

        Args:
            renderer: Renderer instance (e.g., MatplotlibRenderer)
            html_renderer: Renderer of the HTML figure; ``None`` selects the builtin
                one (Plotly) when HTML is requested.
        """
        self.renderer = renderer
        self.html_renderer = html_renderer

    def render(self, df: pd.DataFrame, config: PlotConfig) -> list[RenderResult]:
        """Execute overlay plotting strategy.

        Args:
            df: DataFrame containing plot data
            config: Plot configuration from PlotConfigBuilder

        Returns:
            List of RenderResult objects (PNG and optionally HTML)

        Raises:
            RendererUnavailableError: If HTML is requested from the builtin renderer
                and Plotly is not installed (raised before anything is drawn).
        """
        normalized_formats = _normalized_formats(config)
        base_filename = _base_filename(config)
        results: list[RenderResult] = []
        html_renderer = self._resolve_html_renderer() if "html" in normalized_formats else None

        image_formats = [fmt for fmt in normalized_formats if fmt != "html"]
        if config.output.return_fig or image_formats:
            figure = self.renderer.render_overlay(df, config)
            results.extend(
                RenderResult(figure=figure, filename=f"{base_filename}.{fmt}", format=fmt) for fmt in image_formats
            )

        if html_renderer is not None:
            html_fig = html_renderer.render_html(df, config)
            results.append(RenderResult(figure=html_fig, filename=f"{base_filename}.html", format="html"))

        return results

    def _resolve_html_renderer(self) -> LegacyHtmlRenderer:
        if self.html_renderer is not None:
            return self.html_renderer
        return builtin_html_renderer()


def _normalized_formats(config: PlotConfig) -> list[str]:
    """Requested formats, lower-cased and de-duplicated in request order (default PNG)."""
    return list(dict.fromkeys(fmt.lower() for fmt in config.output.formats or ["png"]))


def _base_filename(config: PlotConfig) -> str:
    base_title = config.title if config.title else (config.output.base_name or "plot")
    filename_root = config.output.base_name or base_title
    # Same sanitizer as the individual stems, so ".." cannot reach the writer.
    return sanitize_stem(filename_root) or DEFAULT_BASE_STEM
