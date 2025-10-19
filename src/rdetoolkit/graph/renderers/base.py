from __future__ import annotations

from typing import Any, Protocol

import pandas as pd

from rdetoolkit.graph.models import PlotConfig


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
