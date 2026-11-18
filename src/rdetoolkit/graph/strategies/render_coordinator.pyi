"""Type stubs for render_coordinator module."""

from __future__ import annotations

import pandas as pd

from rdetoolkit.graph.models import (
    MatplotlibArtifact,
    PlotConfig,
    PlotMode,
    RenderCollections,
)
from rdetoolkit.graph.renderers.registry import RendererRegistry

def collect_render_results(
    df: pd.DataFrame,
    config: PlotConfig,
    plot_mode: PlotMode,
    *,
    renderers: RendererRegistry | None = None,
) -> RenderCollections: ...

def build_matplotlib_artifacts(
    collections: RenderCollections,
) -> list[MatplotlibArtifact]: ...
