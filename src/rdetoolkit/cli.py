from __future__ import annotations

import json
import pathlib
from typing import Literal, cast

import click

from rdetoolkit.cmd.archive import CreateArtifactCommand
from rdetoolkit.cmd.command import InitCommand, VersionCommand
from rdetoolkit.cmd.csv2graph import Csv2GraphCommand
from rdetoolkit.cmd.gen_config import (
    GenerateConfigCommand,
    TEMPLATE_CHOICES,
    LANG_CHOICES,
)
from rdetoolkit.cmd.gen_excelinvoice import GenerateExcelInvoiceCommand


@click.group()
def cli() -> None:
    """CLI generates template projects for RDE structured programs."""


@click.command()
def init() -> None:
    """Output files needed to build RDE structured programs."""
    cmd = InitCommand()
    cmd.invoke()


@click.command()
def version() -> None:
    """Command to display version."""
    cmd = VersionCommand()
    cmd.invoke()


def _validation_json_file(
    ctx: click.Context,
    param: click.Parameter,
    value: pathlib.Path,
) -> pathlib.Path:
    """Validates that the provided file is a properly formatted JSON file.

    This function performs two validations:
    1. Checks if the file has a .json extension
    2. Attempts to parse the file content as JSON

    Args:
        ctx: Click context
        param: Click parameter
        value (pathlib.Path): The path to the file to validate

    Returns:
        pathlib.Path: The validated file path

    Raises:
        click.BadParameter: If the file is not a .json file or contains invalid JSON
    """
    if value.suffix != '.json':
        emsg = "The schema file must be a JSON file."
        raise click.BadParameter(emsg)

    try:
        with open(value) as f:
            json.load(f)
    except json.JSONDecodeError as e:
        emsg = "The schema file must be a valid JSON file."
        raise click.BadParameter(emsg) from e

    return value


@click.command(
    help="Generate an Excel invoice based on the provided schema and save it to the specified output path.",
)
@click.argument(
    "invoice_schema_json_path",
    type=click.Path(
        exists=True,
        dir_okay=False,
        resolve_path=True,
        path_type=pathlib.Path,
    ),
    callback=_validation_json_file,
    metavar="<invoice.schema.json file path>",
)
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(
        exists=False,
        dir_okay=False,
        resolve_path=True,
        path_type=pathlib.Path,
    ),
    default=pathlib.Path.cwd() / "template_excel_invoice.xlsx",
    metavar="<path to ExcelInvoice file output>",
    help="Path to ExcelInvoice file output (default: ./excel_invoice.xlsx)",
)
@click.option(
    "-m",
    "--mode",
    type=click.Choice(["file", "folder"], case_sensitive=False),
    default="file",
    help="=select the registration mode: 'file' or 'folder' (default: file)",
    metavar="<filemode or foldermode>",
)
def make_excelinvoice(
    invoice_schema_json_path: pathlib.Path,
    output_path: pathlib.Path, mode: Literal["file", "folder"],
) -> None:
    """Generate an Excel invoice based on the provided schema and save it to the specified output path.

    Args:
        invoice_schema_json_path (pathlib.Path): The path to the JSON file containing the invoice schema.
        output_path (pathlib.Path): The path where the generated Excel invoice will be saved.
        mode (Literal["file", "folder"]): The mode indicating whether the output is a single file or a folder.

    Returns:
        None
    """
    cmd = GenerateExcelInvoiceCommand(invoice_schema_json_path, output_path, mode)
    cmd.invoke()


@click.command(help="Create an artifact (.zip) for submission to RDE by archiving the specified source directory, excluding specified files or directories.")
@click.option("--source-dir", "-s", required=True, type=click.Path(exists=True, file_okay=False), help="The source directory to compress and scan.")
@click.option("--output-archive", "-o", required=False, default=None, type=click.Path(), help="Output archive file (e.g. rde_template.zip).")
@click.option("--exclude", "-e", multiple=True, default=None, help="Exclude directory names. Defaults to 'venv' and 'site-packages'.")
def artifact(source_dir: str, output_archive: pathlib.Path | None, exclude: list[str] | None) -> None:
    """Create an artifact (.zip) for submission to RDE by archiving the specified source directory, excluding specified files or directories.

    Args:
        source_dir (str): The path to the source directory to be archived.
        output_archive (str | None): The path where the output archive file will be created. Defaults to None.
        exclude (list[str] | None): A list of file or directory patterns to exclude from the archive. Defaults to None.

    Returns:
        None
    """
    cmd = CreateArtifactCommand(
        pathlib.Path(source_dir),
        output_archive_path=(pathlib.Path(output_archive) if output_archive else None),
        exclude_patterns=exclude,
    )
    cmd.invoke()


@click.command(help="Generate graphs from CSV files.")
@click.argument("csv_path", type=click.Path(exists=False, dir_okay=False, path_type=pathlib.Path))
@click.option("--output-dir", "-o", type=click.Path(path_type=pathlib.Path), help="Output directory for plots")
@click.option("--main-image-dir", type=click.Path(path_type=pathlib.Path), help="Directory for combined plot outputs")
@click.option("--csv-format", type=click.Choice(["standard", "transpose", "noheader"]), default="standard", help="CSV format type")
@click.option("--logy", is_flag=True, help="Use log scale for Y axis")
@click.option("--logx", is_flag=True, help="Use log scale for X axis")
@click.option("--html", is_flag=True, help="Generate interactive HTML output")
@click.option("--mode", type=click.Choice(["overlay", "individual"]), default="overlay", help="Plotting mode")
@click.option("--x-col", multiple=True, help="X-axis column(s) - index or name")
@click.option("--y-cols", multiple=True, help="Y-axis column(s) - index or name")
@click.option("--direction-cols", multiple=True, help="Direction column(s)")
@click.option("--direction-filter", multiple=True, help="Filter direction values")
@click.option("--direction-colors", multiple=True, help="Direction colors (format: dir=color)")
@click.option("--title", help="Plot title")
@click.option("--legend-info", help="Additional legend information")
@click.option("--legend-loc", help="Legend location")
@click.option("--xlim", nargs=2, type=float, help="X-axis limits (min max)")
@click.option("--ylim", nargs=2, type=float, help="Y-axis limits (min max)")
@click.option("--grid", is_flag=True, help="Show grid")
@click.option("--invert-x", is_flag=True, help="Invert x-axis")
@click.option("--invert-y", is_flag=True, help="Invert y-axis")
@click.option("--no-individual", is_flag=True, help="Skip individual plots")
@click.option("--max-legend-items", type=int, help="Maximum legend items")
def csv2graph(
    csv_path: pathlib.Path,
    output_dir: pathlib.Path | None,
    main_image_dir: pathlib.Path | None,
    csv_format: Literal["standard", "transpose", "noheader"],
    logy: bool,
    logx: bool,
    html: bool,
    mode: Literal["overlay", "individual"],
    x_col: tuple[str, ...],
    y_cols: tuple[str, ...],
    direction_cols: tuple[str, ...],
    direction_filter: tuple[str, ...],
    direction_colors: tuple[str, ...],
    title: str | None,
    legend_info: str | None,
    legend_loc: str | None,
    xlim: tuple[float, float] | None,
    ylim: tuple[float, float] | None,
    grid: bool,
    invert_x: bool,
    invert_y: bool,
    no_individual: bool,
    max_legend_items: int | None,
) -> None:
    """Generate graphs from CSV files.

    Args:
        csv_path: Path to CSV file
        output_dir: Output directory
        main_image_dir: Directory for combined plot outputs
        csv_format: CSV format type
        logy: Log scale for Y
        logx: Log scale for X
        html: HTML output
        mode: Plot mode
        x_col: X columns
        y_cols: Y columns
        direction_cols: Direction columns
        direction_filter: Direction filter
        direction_colors: Direction colors
        title: Plot title
        legend_info: Legend info
        legend_loc: Legend location
        xlim: X limits
        ylim: Y limits
        grid: Show grid
        invert_x: Invert X
        invert_y: Invert Y
        no_individual: Skip individual
        max_legend_items: Max legend items
    """
    # Parse column specifications
    def parse_col(col: str) -> int | str:
        try:
            return int(col)
        except ValueError:
            return col

    parsed_x_col = [parse_col(c) for c in x_col] if x_col else None
    parsed_y_cols = [parse_col(c) for c in y_cols] if y_cols else None
    parsed_direction_cols = (
        [parse_col(c) for c in direction_cols]
        if direction_cols else None
    )
    parsed_direction_filter = list(direction_filter) if direction_filter else None

    # Parse direction colors
    parsed_direction_colors = None
    if direction_colors:
        parsed_direction_colors = {}
        for color_spec in direction_colors:
            if "=" in color_spec:
                direction, color = color_spec.split("=", 1)
                parsed_direction_colors[direction.strip()] = color.strip()

    cmd = Csv2GraphCommand(
        csv_path=csv_path,
        output_dir=output_dir,
        main_image_dir=main_image_dir,
        csv_format=csv_format,
        logy=logy,
        logx=logx,
        html=html,
        mode=mode,
        x_col=parsed_x_col,
        y_cols=parsed_y_cols,
        direction_cols=parsed_direction_cols,
        direction_filter=parsed_direction_filter,
        direction_colors=parsed_direction_colors,
        title=title,
        legend_info=legend_info,
        legend_loc=legend_loc,
        xlim=xlim,
        ylim=ylim,
        grid=grid,
        invert_x=invert_x,
        invert_y=invert_y,
        no_individual=no_individual,
        max_legend_items=max_legend_items,
    )
    cmd.invoke()


@click.command(help="Generate an rdeconfig.yaml template in the target directory.")
@click.argument(
    "output_dir",
    type=click.Path(file_okay=False, resolve_path=True, path_type=pathlib.Path),
    required=False,
)
@click.option(
    "--template",
    "template_name",
    type=click.Choice(list(TEMPLATE_CHOICES), case_sensitive=False),
    default="minimal",
    show_default=True,
    help="Template style for rdeconfig.yaml.",
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Allow replacing an existing rdeconfig.yaml.",
)
@click.option(
    "--lang",
    type=click.Choice(list(LANG_CHOICES), case_sensitive=False),
    default="en",
    show_default=True,
    help="Prompt language (interactive template only).",
)
def gen_config(
    output_dir: pathlib.Path | None,
    template_name: str,
    overwrite: bool,
    lang: str,
) -> None:
    """Generate rdeconfig.yaml from templates."""
    template_key = template_name.lower()
    lang_key = lang.lower()

    if template_key != "interactive" and lang_key != "en":
        error_message = "--lang is only available when --template=interactive"
        raise click.BadParameter(
            error_message,
            param_hint="--lang",
        )

    target_dir = output_dir if output_dir is not None else pathlib.Path.cwd()

    command = GenerateConfigCommand(
        output_dir=target_dir,
        template=cast(
            Literal[
                "minimal",
                "full",
                "multitile",
                "rdeformat",
                "smarttable",
                "interactive",
            ],
            template_key,
        ),
        overwrite=overwrite,
        lang=cast(
            Literal["en", "ja"],
            lang_key if template_key == "interactive" else "en",
        ),
    )
    command.invoke()


cli.add_command(init)
cli.add_command(version)
cli.add_command(make_excelinvoice)
cli.add_command(artifact)
cli.add_command(csv2graph)
cli.add_command(gen_config)
