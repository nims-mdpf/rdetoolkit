"""Render coordination utilities for managing plot rendering workflows.

This module provides functions for coordinating the rendering process across
multiple strategies (overlay, individual) and collecting their results into
unified collections for further processing or file output.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rdetoolkit.graph.models import (
    MatplotlibArtifact,
    PlotMode,
    RenderCollections,
    RenderResult,
)
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer
from rdetoolkit.graph.strategies.all_graphs import OverlayStrategy
from rdetoolkit.graph.strategies.individual import IndividualStrategy

if TYPE_CHECKING:
    import pandas as pd

    from rdetoolkit.graph.models import PlotConfig


def collect_render_results(
    df: pd.DataFrame,
    config: PlotConfig,
    plot_mode: PlotMode,
) -> RenderCollections:
    """Render graphs according to the selected strategy.

    Coordinates the execution of appropriate rendering strategies based on the
    plot mode and configuration. Delegates rendering to OverlayStrategy and/or
    IndividualStrategy as needed.

    Args:
        df: Input DataFrame containing data to plot
        config: Plot configuration specifying rendering parameters
        plot_mode: Rendering mode (overlay or individual)

    Returns:
        RenderCollections containing overlay and individual render results

    Examples:
        >>> from rdetoolkit.graph.models import PlotMode, PlotConfig
        >>> import pandas as pd
        >>> df = pd.DataFrame({"x": [1, 2, 3], "y": [1, 4, 9]})
        >>> config = PlotConfig(mode=PlotMode.OVERLAY)
        >>> results = collect_render_results(df, config, PlotMode.OVERLAY)
        >>> len(results.overlay) > 0
        True
    """
    renderer = MatplotlibRenderer()
    overlay_results: list[RenderResult] = []
    individual_results: list[RenderResult] = []

    if plot_mode == PlotMode.OVERLAY:
        overlay_results = OverlayStrategy(renderer).render(df, config)
        if not config.output.no_individual:
            individual_output = IndividualStrategy(renderer).render(df, config)
            if individual_output is not None:
                individual_results = individual_output
    else:
        individual_output = IndividualStrategy(renderer).render(df, config)
        if individual_output is not None:
            individual_results = individual_output

    return RenderCollections(
        overlay=overlay_results,
        individual=individual_results,
    )


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
