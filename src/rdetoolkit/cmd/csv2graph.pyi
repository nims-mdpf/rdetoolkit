import pathlib
from _typeshed import Incomplete
from rdetoolkit.rdelogger import get_logger as get_logger
from typing import Literal

logger: Incomplete

class Csv2GraphCommand:
    csv_path: Incomplete
    output_dir: Incomplete
    main_image_dir: Incomplete
    csv_format: Incomplete
    logy: Incomplete
    logx: Incomplete
    html: Incomplete
    mode: Incomplete
    x_col: Incomplete
    y_cols: Incomplete
    direction_cols: Incomplete
    direction_filter: Incomplete
    direction_colors: Incomplete
    title: Incomplete
    legend_info: Incomplete
    legend_loc: Incomplete
    xlim: Incomplete
    ylim: Incomplete
    grid: Incomplete
    invert_x: Incomplete
    invert_y: Incomplete
    no_individual: Incomplete
    max_legend_items: Incomplete
    def __init__(self, csv_path: pathlib.Path, output_dir: pathlib.Path | None = None, main_image_dir: pathlib.Path | None = None, csv_format: Literal['standard', 'transpose', 'noheader'] = 'standard', logy: bool = False, logx: bool = False, html: bool = False, mode: Literal['overlay', 'individual'] = 'overlay', x_col: list[int | str] | None = None, y_cols: list[int | str] | None = None, direction_cols: list[int | str] | None = None, direction_filter: list[str] | None = None, direction_colors: dict[str, str] | None = None, title: str | None = None, legend_info: str | None = None, legend_loc: str | None = None, xlim: tuple[float, float] | None = None, ylim: tuple[float, float] | None = None, grid: bool = False, invert_x: bool = False, invert_y: bool = False, no_individual: bool = False, max_legend_items: int | None = None) -> None: ...
    def invoke(self) -> None: ...
