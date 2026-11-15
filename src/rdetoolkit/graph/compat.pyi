from collections.abc import Callable

import pandas as pd

from rdetoolkit.graph.models import AxisConfig, PlotConfig
from rdetoolkit.graph.plan import PlotPlan

__all__ = [
    "AxisLabelFunction",
    "LabelFunction",
    "legacy_mpl_axis_label",
    "legacy_mpl_label",
    "legacy_plotly_axis_label",
    "legacy_plotly_label",
    "plan_from_config",
]

LabelFunction = Callable[[str, bool], str]
AxisLabelFunction = Callable[[AxisConfig, str], str]

def legacy_mpl_label(header: str, humanize: bool) -> str: ...
def legacy_plotly_label(header: str, humanize: bool) -> str: ...
def legacy_mpl_axis_label(axis: AxisConfig, default_label: str) -> str: ...
def legacy_plotly_axis_label(axis: AxisConfig, default_label: str) -> str: ...
def plan_from_config(
    df: pd.DataFrame,
    config: PlotConfig,
    *,
    label_of: LabelFunction,
    axis_label_of: AxisLabelFunction = ...,
) -> PlotPlan: ...
