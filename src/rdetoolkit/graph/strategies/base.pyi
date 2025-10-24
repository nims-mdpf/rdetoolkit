import pandas as pd
from rdetoolkit.graph.models import PlotConfig as PlotConfig
from typing import Any, Protocol

class PlotStrategy(Protocol):
    def render(self, df: pd.DataFrame, config: PlotConfig) -> list[Any]: ...
