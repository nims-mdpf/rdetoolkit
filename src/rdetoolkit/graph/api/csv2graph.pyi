import pandas as pd
from dataclasses import dataclass
from pathlib import Path
from rdetoolkit.graph.config import PlotConfigBuilder as PlotConfigBuilder
from rdetoolkit.graph.io.file_writer import FileWriter as FileWriter
from rdetoolkit.graph.io.path_validator import PathValidator as PathValidator
from rdetoolkit.graph.models import AxisConfig as AxisConfig, DirectionConfig as DirectionConfig, LegendConfig as LegendConfig, OutputConfig as OutputConfig, PlotConfig as PlotConfig, PlotMode as PlotMode, RenderResult as RenderResult
from rdetoolkit.graph.normalizers import validate_column_specs as validate_column_specs
from rdetoolkit.graph.parsers.parser_factory import ParserFactory as ParserFactory
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer as MatplotlibRenderer
from rdetoolkit.graph.strategies.all_graphs import OverlayStrategy as OverlayStrategy
from rdetoolkit.graph.strategies.individual import IndividualStrategy as IndividualStrategy
from rdetoolkit.graph.textutils import parse_header as parse_header
from typing import Any, Literal

@dataclass(frozen=True)
class MatplotlibArtifact:
    filename: str
    figure: Any
    metadata: dict[str, Any] | None = ...

@dataclass(frozen=True)
class NormalizedColumns:
    x_col: int | list[int]
    y_cols: list[int]
    direction_cols: list[int | str | None]
    derived_x_label: str
    derived_y_label: str

@dataclass(frozen=True)
class RenderCollections:
    overlay: list[RenderResult]
    individual: list[RenderResult]
    def all_results(self) -> list[RenderResult]: ...

def csv2graph(csv_path: str | Path, output_dir: str | Path | None = None, main_image_dir: str | Path | None = None, csv_format: Literal['standard', 'transpose', 'noheader'] = 'standard', logy: bool = False, logx: bool = False, html: bool = False, mode: Literal['overlay', 'individual'] = 'overlay', x_col: int | str | list[int | str] | None = None, y_cols: int | str | list[int | str] | None = None, direction_cols: int | str | list[int | str] | None = None, direction_filter: list[str] | None = None, direction_colors: dict[str, str] | None = None, title: str | None = None, legend_info: str | None = None, legend_loc: str | int | None = None, xlim: tuple[float | None, float | None] | None = None, ylim: tuple[float | None, float | None] | None = None, grid: bool = False, invert_x: bool = False, invert_y: bool = False, no_individual: bool = False, max_legend_items: int | None = None) -> None: ...
def plot_from_dataframe(df: pd.DataFrame, output_dir: str | Path, main_image_dir: str | Path | None = None, logy: bool = False, logx: bool = False, html: bool = False, mode: Literal['overlay', 'individual'] = 'overlay', x_col: int | str | list[int | str] | None = None, y_cols: int | str | list[int | str] | None = None, direction_cols: int | str | list[int | str] | None = None, direction_filter: list[str] | None = None, direction_colors: dict[str, str] | None = None, title: str | None = None, name: str | None = None, x_label: str | None = None, y_label: str | None = None, legend_info: str | None = None, legend_loc: str | int | None = None, xlim: tuple[float | None, float | None] | None = None, ylim: tuple[float | None, float | None] | None = None, grid: bool = False, invert_x: bool = False, invert_y: bool = False, no_individual: bool = False, max_legend_items: int | None = None, return_fig: bool = False) -> list[Any] | None: ...
