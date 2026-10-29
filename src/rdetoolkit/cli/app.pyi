"""Type stubs for rdetoolkit.cli.app module."""
from __future__ import annotations

import pathlib
from typing import Literal, Optional, Union

import typer

app: typer.Typer
nodes_app: typer.Typer
flows_app: typer.Typer
templates_app: typer.Typer
formats_app: typer.Typer
graph_app: typer.Typer
report_app: typer.Typer
repro_app: typer.Typer
migrate_app: typer.Typer

def validate_json_file(value: pathlib.Path) -> pathlib.Path: ...
def parse_column(col: str) -> Union[int, str]: ...
def init(
    template: pathlib.Optional[Path] = None,
    processing_template: Optional[str] = None,
    template_modules: Optional[list[str]] = None,
    force: bool = False,
    entry_point: pathlib.Optional[Path] = None,
    modules: pathlib.Optional[Path] = None,
    tasksupport: pathlib.Optional[Path] = None,
    inputdata: pathlib.Optional[Path] = None,
    other: Optional[list[pathlib.Path]] = None,
) -> None: ...
def version() -> None: ...
def run(
    target: Optional[str] = None,
    flow: Optional[str] = None,
    validate_only: bool = False,
    config: Optional[pathlib.Path] = None,
) -> None: ...
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
def gen_invoice(
    schema_path: pathlib.Path,
    output_path: pathlib.Optional[Path] = None,
    fill_defaults: bool = True,
    required_only: bool = False,
    output_format: Literal["pretty", "compact"] = "pretty",
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
    legend_policy: str = "legacy",
    legend_outside_threshold: int = 8,
    legend_bottom_threshold: int = 21,
    legend_ncol: Optional[int] = None,
    x_tick_format: str = "auto",
    y_tick_format: str = "auto",
) -> None: ...
def agent_guide(detailed: bool = False) -> None: ...
