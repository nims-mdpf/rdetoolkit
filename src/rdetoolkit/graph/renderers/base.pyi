import pandas as pd
from rdetoolkit.graph.models import PlotConfig as PlotConfig
from typing import Any, Protocol

class BaseRenderer(Protocol):
    def render_overlay(self, df: pd.DataFrame, config: PlotConfig) -> Any: ...
    def render_individual(
        self,
        df: pd.DataFrame,
        config: PlotConfig,
        y_col_index: int,
        series_position: int | None = ...,
    ) -> Any: ...
