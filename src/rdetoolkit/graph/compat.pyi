from collections.abc import Callable
from contextlib import AbstractContextManager

import pandas as pd

from rdetoolkit.graph.exceptions import PlotRequestError
from rdetoolkit.graph.models import AxisConfig, PlotConfig, PlotMode
from rdetoolkit.graph.plan import FigurePlan, PlotPlan

__all__ = [
    "DUAL_AXIS_UNSUPPORTED",
    "AxisLabelFunction",
    "LabelFunction",
    "legacy_mpl_axis_label",
    "legacy_mpl_label",
    "legacy_plotly_axis_label",
    "legacy_plotly_label",
    "dual_axis_unsupported_error",
    "individual_plan",
    "legacy_call",
    "legacy_plan",
    "mixes_units",
    "plan_from_config",
    "reject_dual_axis",
    "warn_mixed_overlay",
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
def mixes_units(plan: PlotPlan) -> bool: ...
def legacy_call() -> AbstractContextManager[None]: ...
def legacy_plan(
    df: pd.DataFrame,
    config: PlotConfig,
    *,
    label_of: LabelFunction,
    axis_label_of: AxisLabelFunction = ...,
) -> PlotPlan: ...
def warn_mixed_overlay(plan: PlotPlan) -> None: ...
def individual_plan(
    df: pd.DataFrame,
    config: PlotConfig,
    y_col_index: int,
    series_position: int | None,
    *,
    label_of: LabelFunction,
    axis_label_of: AxisLabelFunction = ...,
) -> tuple[PlotPlan, FigurePlan]: ...
