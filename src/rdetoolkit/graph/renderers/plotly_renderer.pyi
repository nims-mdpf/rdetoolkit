import pandas as pd
import plotly.graph_objs as go
from rdetoolkit.graph.models import PlotConfig as PlotConfig

class PlotlyRenderer:
    def render_html(self, df: pd.DataFrame, config: PlotConfig) -> go.Figure: ...
