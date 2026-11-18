from typing import Any

import pandas as pd
import plotly.graph_objs as go

from rdetoolkit.graph.models import PlotConfig as PlotConfig
from rdetoolkit.graph.plan import FigurePlan, PlotData, PlotPlan
from rdetoolkit.graph.renderers.base import RendererCapabilities

DEFAULT_PLOTLY_COLORS: list[str]

class PlotlyRenderer:
    @property
    def capabilities(self) -> RendererCapabilities: ...
    def export(self, handle: Any, fmt: str, *, dpi: int) -> bytes: ...
    def close(self, handle: Any) -> None: ...
    def render_html(self, df: pd.DataFrame, config: PlotConfig) -> go.Figure: ...
    def render(self, plan: PlotPlan, figure: FigurePlan, data: PlotData) -> go.Figure: ...
