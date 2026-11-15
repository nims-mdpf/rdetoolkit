from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from matplotlib.figure import Figure

from rdetoolkit.graph.config import PlotConfigBuilder as PlotConfigBuilder
from rdetoolkit.graph.io.file_writer import FileWriter as FileWriter
from rdetoolkit.graph.io.path_validator import PathValidator as PathValidator
from rdetoolkit.graph.models import (
    AxisConfig as AxisConfig,
    DirectionConfig as DirectionConfig,
    LegendConfig as LegendConfig,
    MatplotlibArtifact as MatplotlibArtifact,
    NormalizedColumns as NormalizedColumns,
    OutputConfig as OutputConfig,
    PlotConfig as PlotConfig,
    PlotMode as PlotMode,
    RenderCollections as RenderCollections,
    RenderResult as RenderResult,
)
from rdetoolkit.graph.normalizers import ColumnNormalizer
from rdetoolkit.graph.strategies.render_coordinator import (
    build_matplotlib_artifacts as build_matplotlib_artifacts,
    collect_render_results as collect_render_results,
)

_LegendPolicy = Literal["legacy", "auto", "inside", "outside_right", "outside_bottom", "hide"]
_TickFormat = Literal["auto", "plain", "sci", "eng"]
_ColumnSpec = int | str | list[int | str] | None

def _parse_headers(df: pd.DataFrame) -> list[tuple[str | None, str, str | None]]: ...
def _format_axis_label(column_name: Any, parsed: tuple[str | None, str, str | None] | None) -> str: ...
def _normalize_y_specs(y_cols: _ColumnSpec) -> Sequence[int | str] | None: ...
def _normalize_columns(df: pd.DataFrame, x_col: _ColumnSpec, y_cols: _ColumnSpec, direction_cols: _ColumnSpec) -> NormalizedColumns: ...
def _column_positions(df: pd.DataFrame, normalizer: ColumnNormalizer, spec: int | str | Sequence[int | str]) -> list[int]: ...
def _column_position(df: pd.DataFrame, normalizer: ColumnNormalizer, spec: int | str) -> int: ...
def _pair_x_positions(x_positions: list[int], y_positions: list[int]) -> list[int]: ...
def _direction_positions(
    df: pd.DataFrame,
    normalizer: ColumnNormalizer,
    direction_cols: int | str | Sequence[int | str | None] | None,
    y_count: int,
) -> list[int | None]: ...
def _resolve_plot_mode(mode: Literal["overlay", "individual"]) -> PlotMode: ...
def _resolve_no_individual_flag(*, requested: bool | None, plot_mode: PlotMode, normalized: NormalizedColumns) -> bool: ...
def _build_plot_config(
    *,
    plot_mode: PlotMode,
    normalized: NormalizedColumns,
    direction_config: DirectionConfig,
    display_title: str | None,
    x_label: str | None,
    y_label: str | None,
    logx: bool,
    logy: bool,
    x_tick_format: _TickFormat = "auto",
    y_tick_format: _TickFormat = "auto",
    xlim: tuple[float | None, float | None] | None,
    ylim: tuple[float | None, float | None] | None,
    grid: bool,
    invert_x: bool,
    invert_y: bool,
    legend_info: str | None,
    legend_loc: str | int | None,
    max_legend_items: int | None,
    legend_policy: _LegendPolicy = "legacy",
    legend_outside_threshold: int = 8,
    legend_bottom_threshold: int | None = 21,
    legend_ncol: int | None = None,
    formats: list[str],
    no_individual: bool,
    return_fig: bool,
    base_filename: str,
    main_image_dir_path: Path | None,
) -> PlotConfig: ...
def _save_render_results(
    collections: RenderCollections,
    output_dir_path: Path,
    main_image_dir_path: Path | None,
    html_output_dir_path: Path | None = None,
) -> None: ...
def csv2graph(
    csv_path: str | Path,
    output_dir: str | Path | None = None,
    main_image_dir: str | Path | None = None,
    html_output_dir: str | Path | None = None,
    csv_format: Literal["standard", "transpose", "noheader"] | str = "standard",
    logy: bool = False,
    logx: bool = False,
    html: bool = False,
    mode: Literal["overlay", "individual"] = "overlay",
    x_col: _ColumnSpec = None,
    y_cols: _ColumnSpec = None,
    direction_cols: _ColumnSpec = None,
    direction_filter: list[str] | None = None,
    direction_colors: dict[str, str] | None = None,
    title: str | None = None,
    legend_info: str | None = None,
    legend_loc: str | int | None = None,
    xlim: tuple[float | None, float | None] | None = None,
    ylim: tuple[float | None, float | None] | None = None,
    grid: bool = False,
    invert_x: bool = False,
    invert_y: bool = False,
    no_individual: bool | None = None,
    max_legend_items: int | None = None,
    legend_policy: _LegendPolicy = "legacy",
    legend_outside_threshold: int = 8,
    legend_bottom_threshold: int | None = 21,
    legend_ncol: int | None = None,
    *,
    x_tick_format: _TickFormat = "auto",
    y_tick_format: _TickFormat = "auto",
) -> None: ...
def plot_from_dataframe(
    df: pd.DataFrame,
    output_dir: str | Path,
    main_image_dir: str | Path | None = None,
    html_output_dir: str | Path | None = None,
    logy: bool = False,
    logx: bool = False,
    html: bool = False,
    mode: Literal["overlay", "individual"] = "overlay",
    x_col: _ColumnSpec = None,
    y_cols: _ColumnSpec = None,
    direction_cols: _ColumnSpec = None,
    direction_filter: list[str] | None = None,
    direction_colors: dict[str, str] | None = None,
    title: str | None = None,
    name: str | None = None,
    x_label: str | None = None,
    y_label: str | None = None,
    legend_info: str | None = None,
    legend_loc: str | int | None = None,
    xlim: tuple[float | None, float | None] | None = None,
    ylim: tuple[float | None, float | None] | None = None,
    grid: bool = False,
    invert_x: bool = False,
    invert_y: bool = False,
    no_individual: bool | None = None,
    max_legend_items: int | None = None,
    return_fig: bool = False,
    *,
    legend_policy: _LegendPolicy = "legacy",
    legend_outside_threshold: int = 8,
    legend_bottom_threshold: int | None = 21,
    legend_ncol: int | None = None,
    x_tick_format: _TickFormat = "auto",
    y_tick_format: _TickFormat = "auto",
) -> list[Any] | None: ...
def _collect_owned(df: pd.DataFrame, config: PlotConfig, plot_mode: PlotMode) -> RenderCollections: ...
def _hand_over(collections: RenderCollections) -> list[MatplotlibArtifact]: ...
def _matplotlib_figures(results: Sequence[RenderResult]) -> list[Figure]: ...
def _close_figures(results: Sequence[RenderResult]) -> None: ...
