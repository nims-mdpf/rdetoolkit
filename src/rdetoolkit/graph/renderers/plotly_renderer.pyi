import pandas as pd
import plotly.graph_objs as go

from rdetoolkit.graph.models import PlotConfig as PlotConfig
from rdetoolkit.graph.plan import FigurePlan, PlotData, PlotPlan

DEFAULT_PLOTLY_COLORS: list[str]

class PlotlyRenderer:
    def render_html(self, df: pd.DataFrame, config: PlotConfig) -> go.Figure: ...
    def render(self, plan: PlotPlan, figure: FigurePlan, data: PlotData) -> go.Figure: ...
