import pandas as pd
from matplotlib.figure import Figure

from rdetoolkit.graph.models import PlotConfig as PlotConfig
from rdetoolkit.graph.plan import FigurePlan, PlotData, PlotPlan

class MatplotlibRenderer:
    def __init__(self) -> None: ...
    def render(self, plan: PlotPlan, figure: FigurePlan, data: PlotData) -> Figure: ...
    def render_overlay(self, df: pd.DataFrame, config: PlotConfig) -> Figure: ...
    def render_individual(
        self,
        df: pd.DataFrame,
        config: PlotConfig,
        y_col_index: int,
        series_position: int | None = ...,
    ) -> Figure: ...
