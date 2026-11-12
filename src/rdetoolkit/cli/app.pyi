"""Type stubs for rdetoolkit.cli.app module."""
from __future__ import annotations

import pathlib
from typing import Any, Optional, Union

import click
import typer
from typer.core import TyperCommand, TyperGroup

from rdetoolkit.cli._help import CommandHelp
from rdetoolkit.cli.new_cmd import DEFAULT_EXCEL_INVOICE_TEMPLATE as DEFAULT_EXCEL_INVOICE_TEMPLATE
from rdetoolkit.cli.new_cmd import validate_json_file as validate_json_file

ROOT_HELP: CommandHelp
INIT_HELP: CommandHelp
PLOT_HELP: CommandHelp
CSV2GRAPH_HELP: CommandHelp
RUN_HELP: CommandHelp
PACKAGE_HELP: CommandHelp
AGENT_GUIDE_HELP: CommandHelp
VERSION_HELP: CommandHelp
GEN_CONFIG_HELP: CommandHelp
GEN_INVOICE_HELP: CommandHelp
MAKE_EXCELINVOICE_HELP: CommandHelp
ARTIFACT_HELP: CommandHelp

app: typer.Typer
new_app: typer.Typer
validate_app: typer.Typer
report_app: typer.Typer
nodes_app: typer.Typer
flows_app: typer.Typer
skeletons_app: typer.Typer
formats_app: typer.Typer
repro_app: typer.Typer
migrate_app: typer.Typer

class _WorkflowOrderedGroup(TyperGroup):
    def list_commands(self, ctx: click.Context) -> list[str]: ...

class _DeprecatedCommand(TyperCommand):
    replacement: str
    def invoke(self, ctx: click.Context) -> Any: ...

def validate_json_file(value: pathlib.Path) -> pathlib.Path: ...
def parse_column(col: str) -> Union[int, str]: ...
def init(
    template: Optional[pathlib.Path] = None,
    entry_point: Optional[pathlib.Path] = None,
    modules: Optional[pathlib.Path] = None,
    tasksupport: Optional[pathlib.Path] = None,
    inputdata: Optional[pathlib.Path] = None,
    other: Optional[list[pathlib.Path]] = None,
) -> None: ...
def plot(
    csv_path: pathlib.Path,
    output_dir: Optional[pathlib.Path] = None,
    main_image_dir: Optional[pathlib.Path] = None,
    html_output_dir: Optional[pathlib.Path] = None,
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
def run(
    target: Optional[str] = None,
    legacy: bool = False,
    validate_only: bool = False,
    config: Optional[pathlib.Path] = None,
) -> None: ...
def package(
    source_dir: pathlib.Path,
    output: Optional[pathlib.Path] = None,
    exclude: Optional[list[str]] = None,
) -> None: ...
def agent_guide(detailed: bool = False) -> None: ...
def version() -> None: ...
def gen_config(
    output_dir: Optional[pathlib.Path] = None,
    template_name: str = "minimal",
    overwrite: bool = False,
    lang: str = "en",
) -> None: ...
def artifact(
    source_dir: pathlib.Path,
    output_archive: Optional[pathlib.Path] = None,
    exclude: Optional[list[str]] = None,
) -> None: ...
def gen_invoice(
    schema_path: pathlib.Path,
    output_path: Optional[pathlib.Path] = None,
    fill_defaults: bool = True,
    required_only: bool = False,
    output_format: str = "pretty",
) -> None: ...
def make_excelinvoice(
    invoice_schema_json_path: pathlib.Path,
    output_path: Optional[pathlib.Path] = None,
    mode: str = "file",
) -> None: ...
def csv2graph(
    csv_path: pathlib.Path,
    output_dir: Optional[pathlib.Path] = None,
    main_image_dir: Optional[pathlib.Path] = None,
    html_output_dir: Optional[pathlib.Path] = None,
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
