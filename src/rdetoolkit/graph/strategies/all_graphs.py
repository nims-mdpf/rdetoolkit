from __future__ import annotations

import pandas as pd

from rdetoolkit.graph.models import PlotConfig, RenderResult
from rdetoolkit.graph.renderers.base import BaseRenderer
from rdetoolkit.graph.renderers.plotly_renderer import PlotlyRenderer
from rdetoolkit.graph.textutils import sanitize_filename


class OverlayStrategy:
    """Overlay all data series on a single graph.

    This strategy overlays all y-columns on a single figure with:
        - Direction-based coloring (if direction_cols specified)
        - Series-based coloring (default)
        - Legend with max_items control
        - Optional HTML output (Plotly)

    Workflow:
        1. Delegate matplotlib rendering to renderer.render_overlay()
        2. Optionally create HTML figure via PlotlyRenderer.render_html()
        3. Return list of RenderResult objects

    Example:
        >>> from rdetoolkit.graph.renderers import MatplotlibRenderer
        >>> renderer = MatplotlibRenderer()
        >>> strategy = OverlayStrategy(renderer)
        >>> results = strategy.render(df, config)
    """

    def __init__(self, renderer: BaseRenderer) -> None:
        """Initialize strategy with renderer.

        Args:
            renderer: Renderer instance (e.g., MatplotlibRenderer)
        """
        self.renderer = renderer

    def render(self, df: pd.DataFrame, config: PlotConfig) -> list[RenderResult]:
        """Execute overlay plotting strategy.

        Args:
            df: DataFrame containing plot data
            config: Plot configuration from PlotConfigBuilder

        Returns:
            List of RenderResult objects (PNG and optionally HTML)
        """
        requested_formats = config.output.formats or ["png"]
        normalized_formats: list[str] = []
        seen_formats: set[str] = set()
        for fmt in requested_formats:
            fmt_lower = fmt.lower()
            if fmt_lower not in seen_formats:
                normalized_formats.append(fmt_lower)
                seen_formats.add(fmt_lower)

        base_title = config.title if config.title else (config.output.base_name or "plot")
        filename_root = config.output.base_name or base_title
        base_filename = sanitize_filename(filename_root) or "plot"

        results: list[RenderResult] = []

        needs_matplotlib = (
            config.output.return_fig
            or any(fmt != "html" for fmt in normalized_formats)
        )
        figure = None
        if needs_matplotlib:
            figure = self.renderer.render_overlay(df, config)
            for fmt in normalized_formats:
                if fmt == "html":
                    continue
                filename = f"{base_filename}.{fmt}"
                results.append(RenderResult(
                    figure=figure,
                    filename=filename,
                    format=fmt,
                ))

        if "html" in seen_formats:
            plotly_renderer = PlotlyRenderer()
            html_fig = plotly_renderer.render_html(df, config)
            html_filename = f"{base_filename}.html"
            results.append(RenderResult(
                figure=html_fig,
                filename=html_filename,
                format="html",
            ))

        return results
