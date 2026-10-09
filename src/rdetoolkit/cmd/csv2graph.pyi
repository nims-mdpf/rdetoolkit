import pathlib
from _typeshed import Incomplete
from rdetoolkit.rdelogger import get_logger as get_logger
from typing import Literal, Optional, Union

logger: Incomplete

class Csv2GraphCommand:
    csv_path: Incomplete
    output_dir: Incomplete
    main_image_dir: Incomplete
    html_output_dir: Incomplete
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
    legend_policy: Incomplete
    legend_outside_threshold: Incomplete
    legend_bottom_threshold: Incomplete
    legend_ncol: Incomplete
    x_tick_format: Incomplete
    y_tick_format: Incomplete
    def __init__(self, csv_path: pathlib.Path, output_dir: pathlib.Optional[Path] = None, main_image_dir: pathlib.Optional[Path] = None, html_output_dir: pathlib.Optional[Path] = None, csv_format: Literal['standard', 'transpose', 'noheader'] = 'standard', logy: bool = False, logx: bool = False, html: bool = False, mode: Literal['overlay', 'individual'] = 'overlay', x_col: Optional[list[Union[int, str]]] = None, y_cols: Optional[list[Union[int, str]]] = None, direction_cols: Optional[list[Union[int, str]]] = None, direction_filter: Optional[list[str]] = None, direction_colors: Optional[dict[str, str]] = None, title: Optional[str] = None, legend_info: Optional[str] = None, legend_loc: Optional[str] = None, xlim: Optional[tuple[float, float]] = None, ylim: Optional[tuple[float, float]] = None, grid: bool = False, invert_x: bool = False, invert_y: bool = False, no_individual: Optional[bool] = None, max_legend_items: Optional[int] = None, legend_policy: Literal['legacy', 'auto', 'inside', 'outside_right', 'outside_bottom', 'hide'] = 'legacy', legend_outside_threshold: int = 8, legend_bottom_threshold: Optional[int] = 21, legend_ncol: Optional[int] = None, x_tick_format: Literal['auto', 'plain', 'sci', 'eng'] = 'auto', y_tick_format: Literal['auto', 'plain', 'sci', 'eng'] = 'auto') -> None: ...
    def invoke(self) -> None: ...
