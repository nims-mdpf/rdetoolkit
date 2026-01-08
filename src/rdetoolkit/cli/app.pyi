"""Type stubs for rdetoolkit.cli.app module."""
from __future__ import annotations

import pathlib
from typing import Literal

import typer

app: typer.Typer

def validate_json_file(value: pathlib.Path) -> pathlib.Path: ...
def parse_column(col: str) -> int | str: ...
def init() -> None: ...
def version() -> None: ...
def gen_config(
    output_dir: pathlib.Path | None = None,
    template_name: str = "minimal",
    overwrite: bool = False,
    lang: str = "en",
) -> None: ...
def artifact(
    source_dir: pathlib.Path,
    output_archive: pathlib.Path | None = None,
    exclude: list[str] | None = None,
) -> None: ...
def make_excelinvoice(
    invoice_schema_json_path: pathlib.Path,
    output_path: pathlib.Path | None = None,
    mode: str = "file",
) -> None: ...
def csv2graph(
    csv_path: pathlib.Path,
    output_dir: pathlib.Path | None = None,
    main_image_dir: pathlib.Path | None = None,
    html_output_dir: pathlib.Path | None = None,
    csv_format: str = "standard",
    logy: bool = False,
    logx: bool = False,
    html: bool = False,
    mode: str = "overlay",
    x_col: list[str] | None = None,
    y_cols: list[str] | None = None,
    direction_cols: list[str] | None = None,
    direction_filter: list[str] | None = None,
    direction_colors: list[str] | None = None,
    title: str | None = None,
    legend_info: str | None = None,
    legend_loc: str | None = None,
    xlim: tuple[float, float] | None = None,
    ylim: tuple[float, float] | None = None,
    grid: bool = False,
    invert_x: bool = False,
    invert_y: bool = False,
    no_individual: bool | None = None,
    max_legend_items: int | None = None,
) -> None: ...
