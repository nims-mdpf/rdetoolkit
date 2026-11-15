from collections.abc import Callable

import pandas as pd

from rdetoolkit.graph.exceptions import PlotRequestError
from rdetoolkit.graph.models import AxisConfig, PlotConfig, PlotMode
from rdetoolkit.graph.plan import PlotPlan

__all__ = [
    "DUAL_AXIS_UNSUPPORTED",
    "AxisLabelFunction",
    "LabelFunction",
    "legacy_mpl_axis_label",
    "legacy_mpl_label",
    "legacy_plotly_axis_label",
    "legacy_plotly_label",
    "dual_axis_unsupported_error",
    "plan_from_config",
    "reject_dual_axis",
]

LabelFunction = Callable[[str, bool], str]
AxisLabelFunction = Callable[[AxisConfig, str], str]

DUAL_AXIS_UNSUPPORTED: str

def dual_axis_unsupported_error() -> PlotRequestError: ...
def reject_dual_axis(config: PlotConfig, plot_mode: PlotMode | None = None) -> None: ...

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
