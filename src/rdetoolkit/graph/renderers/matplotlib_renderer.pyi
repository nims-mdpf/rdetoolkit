import pandas as pd
from matplotlib.figure import Figure
from rdetoolkit.graph.models import PlotConfig as PlotConfig

class MatplotlibRenderer:
    def render_overlay(self, df: pd.DataFrame, config: PlotConfig) -> Figure: ...
    def render_individual(
        self,
        df: pd.DataFrame,
        config: PlotConfig,
        y_col_index: int,
        series_position: int | None = ...,
    ) -> Figure: ...
