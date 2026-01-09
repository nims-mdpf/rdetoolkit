"""Type stubs for rdetoolkit.cli.app module."""
from __future__ import annotations

import pathlib
from typing import Literal, Optional, Union

import typer

app: typer.Typer

def validate_json_file(value: pathlib.Path) -> pathlib.Path: ...
def parse_column(col: str) -> Union[int, str]: ...
def init(
    template: pathlib.Optional[Path] = None,
    entry_point: pathlib.Optional[Path] = None,
    modules: pathlib.Optional[Path] = None,
    tasksupport: pathlib.Optional[Path] = None,
    inputdata: pathlib.Optional[Path] = None,
    other: Optional[list[pathlib.Path]] = None,
) -> None: ...
def version() -> None: ...
def run(target: str) -> None: ...
def gen_config(
    output_dir: pathlib.Optional[Path] = None,
    template_name: str = "minimal",
    overwrite: bool = False,
    lang: str = "en",
) -> None: ...
def artifact(
    source_dir: pathlib.Path,
    output_archive: pathlib.Optional[Path] = None,
    exclude: Optional[list[str]] = None,
) -> None: ...
def make_excelinvoice(
    invoice_schema_json_path: pathlib.Path,
    output_path: pathlib.Optional[Path] = None,
    mode: str = "file",
) -> None: ...
def csv2graph(
    csv_path: pathlib.Path,
    output_dir: pathlib.Optional[Path] = None,
    main_image_dir: pathlib.Optional[Path] = None,
    html_output_dir: pathlib.Optional[Path] = None,
    csv_format: str = "standard",
    logy: bool = False,
    logx: bool = False,
    html: bool = False,
    mode: str = "overlay",
    x_col: Optional[list[str]] = None,
    y_cols: Optional[list[str]] = None,
    direction_cols: Optional[list[str]] = None,
    direction_filter: Optional[list[str]] = None,
    direction_colors: Optional[list[str]] = None,
    title: Optional[str] = None,
    legend_info: Optional[str] = None,
    legend_loc: Optional[str] = None,
    xlim: Optional[tuple[float, float]] = None,
    ylim: Optional[tuple[float, float]] = None,
    grid: bool = False,
    invert_x: bool = False,
    invert_y: bool = False,
    no_individual: Optional[bool] = None,
    max_legend_items: Optional[int] = None,
) -> None: ...
