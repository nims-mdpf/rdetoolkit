from dataclasses import dataclass
import pandas as pd
from rdetoolkit.graph.models import PlotConfig as PlotConfig
from rdetoolkit.graph.plan import FigurePlan, PlotData, PlotPlan
from typing import Any, Final, Protocol, runtime_checkable

FIGURE_KINDS: Final[frozenset[str]]

class BaseRenderer(Protocol):
    def render_overlay(self, df: pd.DataFrame, config: PlotConfig) -> Any: ...
    def render_individual(
        self,
        df: pd.DataFrame,
        config: PlotConfig,
        y_col_index: int,
        series_position: int | None = ...,
    ) -> Any: ...

@dataclass(frozen=True, slots=True)
class RendererCapabilities:
    renderer_id: str
    formats: frozenset[str]
    figure_kinds: frozenset[str]
    requires: tuple[str, ...] = ()
    install_hint: str = ""
    applies_rc_params: bool = False
    def supports(self, fmt: str, kind: str) -> bool: ...
    def __post_init__(self) -> None: ...

@runtime_checkable
class GraphRenderer(Protocol):
    @property
    def capabilities(self) -> RendererCapabilities: ...
    def render(self, plan: PlotPlan, figure: FigurePlan, data: PlotData) -> Any: ...
    def export(self, handle: Any, fmt: str, *, dpi: int) -> bytes: ...
    def close(self, handle: Any) -> None: ...
