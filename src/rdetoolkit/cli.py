from __future__ import annotations

import importlib
import importlib.util
import inspect
import json
import os
import pathlib
import sys
from collections.abc import Callable
from types import ModuleType
from typing import Literal, cast

import click
from click.core import ParameterSource

TEMPLATE_CHOICES = (
    "minimal",
    "full",
    "multitile",
    "rdeformat",
    "smarttable",
    "interactive",
)
LANG_CHOICES = ("en", "ja")


class _LazyModuleProxy:
    def __init__(self, module_name: str) -> None:
        self._module_name = module_name
        self._module: ModuleType | None = None

    def _load(self) -> ModuleType:
        if self._module is None:
            self._module = importlib.import_module(self._module_name)
        return self._module

    def __getattr__(self, name: str) -> object:
        module = self._load()
        return getattr(module, name)

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"_module_name", "_module"}:
            object.__setattr__(self, name, value)
            return
        module = self._load()
        setattr(module, name, value)

    def __repr__(self) -> str:
        return f"<LazyModuleProxy {self._module_name}>"


workflows = _LazyModuleProxy("rdetoolkit.workflows")


@click.group()
def cli() -> None:
    """CLI generates template projects for RDE structured programs."""


def _parse_run_target(target: str) -> tuple[str, str]:
    if "::" not in target:
        emsg = "TARGET must be 'module_or_file::attr' (e.g., process::main)."
        raise click.ClickException(emsg)
    parts = target.split("::")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        emsg = "TARGET must be 'module_or_file::attr' (e.g., process::main)."
        raise click.ClickException(emsg)
    return parts[0], parts[1]


def _looks_like_file(value: str) -> bool:
    if value.endswith(".py"):
        return True
    if value.startswith((".", "/", "~")):
        return True
    if os.sep in value:
        return True
    return os.altsep is not None and os.altsep in value


def _load_module_from_file(path: pathlib.Path) -> ModuleType:
    if not path.exists() or not path.is_file():
        emsg = f"File not found: {path}"
        raise click.ClickException(emsg)
    module_name = f"_rdetoolkit_run_{path.stem}_{abs(hash(path))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        emsg = f"Unable to load module from file: {path}"
        raise click.ClickException(emsg)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_target_module(module_or_file: str) -> ModuleType:
    if _looks_like_file(module_or_file):
        path = pathlib.Path(module_or_file).expanduser()
        return _load_module_from_file(path)
    try:
        return importlib.import_module(module_or_file)
    except Exception as exc:
        emsg = f"Failed to import module: {module_or_file}"
        raise click.ClickException(emsg) from exc


def _resolve_target_attr(module: ModuleType, attr: str) -> object:
    target: object = module
    for part in attr.split("."):
        if not hasattr(target, part):
            emsg = f"Attribute not found: {attr}"
            raise click.ClickException(emsg)
        target = getattr(target, part)
    return target


def _validate_target_function(func: Callable[..., object]) -> None:
    if inspect.isclass(func):
        emsg = "Classes are not allowed. Please specify a function."
        raise click.ClickException(emsg)
    if not inspect.isfunction(func):
        emsg = "Only functions are allowed. Please specify a function."
        raise click.ClickException(emsg)
    try:
        inspect.signature(func).bind(1, 2)
    except (TypeError, ValueError) as exc:
        emsg = "The function cannot be called with two positional arguments."
        raise click.ClickException(emsg) from exc


def _load_target_function(target: str) -> Callable[..., object]:
    module_or_file, attr = _parse_run_target(target)
    module = _load_target_module(module_or_file)
    func = _resolve_target_attr(module, attr)
    _validate_target_function(func)
    return func


@click.command()
@click.option(
    "--template",
    "template_path",
    type=click.Path(
        exists=True,
        dir_okay=True,
        file_okay=True,
        resolve_path=True,
        path_type=pathlib.Path,
    ),
    help="Optional template configuration (pyproject.toml or rdeconfig.yaml) used to seed generated files.",
)
@click.option(
    "--entry-point",
    "entry_point_template",
    type=click.Path(
        exists=True,
        dir_okay=False,
        file_okay=True,
        resolve_path=True,
        path_type=pathlib.Path,
    ),
    help="Path to a template main.py used instead of the default entry point.",
)
@click.option(
    "--modules",
    "modules_template",
    type=click.Path(
        exists=True,
        dir_okay=True,
        file_okay=True,
        resolve_path=True,
        path_type=pathlib.Path,
    ),
    help="Path to a template file or directory copied into container/modules.",
)
@click.option(
    "--tasksupport",
    "tasksupport_template",
    type=click.Path(
        exists=True,
        dir_okay=True,
        file_okay=True,
        resolve_path=True,
        path_type=pathlib.Path,
    ),
    help="Path to a template file or directory copied into tasksupport folders.",
)
@click.option(
    "--inputdata",
    "inputdata_template",
    type=click.Path(
        exists=True,
        dir_okay=True,
        file_okay=False,
        resolve_path=True,
        path_type=pathlib.Path,
    ),
    help="Path to a template directory copied into container/data/inputdata and input/inputdata.",
)
@click.option(
    "--other",
    "other_templates",
    multiple=True,
    type=click.Path(
        exists=True,
        dir_okay=True,
        file_okay=True,
        resolve_path=True,
        path_type=pathlib.Path,
    ),
    help="Additional template files or directories copied under container/ (can be passed multiple times).",
)
def init(
    template_path: pathlib.Path | None,
    entry_point_template: pathlib.Path | None,
    modules_template: pathlib.Path | None,
    tasksupport_template: pathlib.Path | None,
    inputdata_template: pathlib.Path | None,
    other_templates: tuple[pathlib.Path, ...],
) -> None:
    """Output files needed to build RDE structured programs."""
    from rdetoolkit.cmd.command import InitCommand, InitTemplateConfig

    cli_templates = InitTemplateConfig(
        entry_point=entry_point_template,
        modules=modules_template,
        tasksupport=tasksupport_template,
        inputdata=inputdata_template,
        other=list(other_templates) if other_templates else None,
    )
    cli_template_config = cli_templates if cli_templates.has_templates() else None
    cmd = InitCommand(template_path=template_path, cli_template_config=cli_template_config)
    cmd.invoke()


@click.command()
def version() -> None:
    """Command to display version."""
    from rdetoolkit.cmd.command import VersionCommand

    cmd = VersionCommand()
    cmd.invoke()


@click.command()
@click.argument("target", metavar="<module_or_file::attr>")
def run(target: str) -> None:
    """Run rdetoolkit workflows with a user-defined dataset function."""
    func = _load_target_function(target)
    try:
        result = workflows.run(custom_dataset_function=func)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    if result is not None:
        click.echo(result)


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
    from rdetoolkit.cmd.gen_excelinvoice import GenerateExcelInvoiceCommand

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
    from rdetoolkit.cmd.archive import CreateArtifactCommand

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
@click.option(
    "--html-output-dir",
    type=click.Path(path_type=pathlib.Path),
    help="Directory for HTML outputs (defaults to the CSV directory)",
)
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
@click.option(
    "--no-individual/--individual",
    "no_individual",
    default=None,
    help="Skip individual plots; defaults to auto for single-series overlay.",
)
@click.option("--max-legend-items", type=int, help="Maximum legend items")
@click.pass_context
def csv2graph(
    ctx: click.Context,
    csv_path: pathlib.Path,
    output_dir: pathlib.Path | None,
    main_image_dir: pathlib.Path | None,
    html_output_dir: pathlib.Path | None,
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
    no_individual: bool | None,
    max_legend_items: int | None,
) -> None:
    """Generate graphs from CSV files.

    Args:
        ctx: Click context for parameter-source inspection
        csv_path: Path to CSV file
        output_dir: Output directory
        main_image_dir: Directory for combined plot outputs
        html_output_dir: Directory for HTML outputs
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
        no_individual: Skip individual (None enables auto-detection)
        max_legend_items: Max legend items
    """
    from rdetoolkit.cmd.csv2graph import Csv2GraphCommand

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

    parameter_source = ctx.get_parameter_source("no_individual")
    resolved_no_individual: bool | None
    resolved_no_individual = (
        None if parameter_source == ParameterSource.DEFAULT else no_individual
    )

    cmd = Csv2GraphCommand(
        csv_path=csv_path,
        output_dir=output_dir,
        main_image_dir=main_image_dir,
        html_output_dir=html_output_dir,
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
        no_individual=resolved_no_individual,
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
    from rdetoolkit.cmd.gen_config import GenerateConfigCommand

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
cli.add_command(run)
cli.add_command(make_excelinvoice)
cli.add_command(artifact)
cli.add_command(csv2graph)
cli.add_command(gen_config)
