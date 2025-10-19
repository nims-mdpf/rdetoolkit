import pandas as pd
from rdetoolkit.graph.models import PlotConfig as PlotConfig

class DualAxisStrategy:
    def render(self, df: pd.DataFrame, config: PlotConfig) -> list[None]: ...
