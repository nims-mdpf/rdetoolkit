import pandas as pd
from _typeshed import Incomplete as Incomplete
from typing import Any, Protocol

from rdetoolkit.graph.models import PlotConfig as PlotConfig, RenderResult as RenderResult
from rdetoolkit.graph.renderers.base import BaseRenderer as BaseRenderer, GraphRenderer

class LegacyHtmlRenderer(Protocol):
    def render_html(self, df: pd.DataFrame, config: PlotConfig) -> Any: ...

def legacy_adapter(renderer: GraphRenderer, method: str) -> Any: ...
def builtin_html_renderer() -> LegacyHtmlRenderer: ...

class OverlayStrategy:
    renderer: Incomplete
    html_renderer: LegacyHtmlRenderer | None
    def __init__(self, renderer: BaseRenderer, *, html_renderer: LegacyHtmlRenderer | None = None) -> None: ...
    def render(self, df: pd.DataFrame, config: PlotConfig) -> list[RenderResult]: ...
