import pandas as pd
from _typeshed import Incomplete as Incomplete
from rdetoolkit.graph.models import PlotConfig as PlotConfig, RenderResult as RenderResult
from rdetoolkit.graph.renderers.base import BaseRenderer as BaseRenderer
from typing import Final

DEFAULT_IMAGE_FORMAT: Final = "png"

class IndividualStrategy:
    renderer: Incomplete
    def __init__(self, renderer: BaseRenderer) -> None: ...
    def render(self, df: pd.DataFrame, config: PlotConfig) -> list[RenderResult] | None: ...
