"""Typer CLI application scaffold for rdetoolkit."""

# Avoid postponed evaluation so Typer can read Annotated metadata (minimum supported: Python 3.10).

import hashlib
import importlib
import importlib.util
import inspect
import os
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Annotated, cast

import typer

app = typer.Typer(
    name="rdetoolkit",
    help="CLI generates template projects for RDE structured programs.",
    no_args_is_help=True,
)

DEFAULT_EXCEL_INVOICE_TEMPLATE = "template_excel_invoice.xlsx"

#: Exit status for a run whose report is ``failed`` (Design §9.3).
_FAILED_EXIT_CODE = 1


def validate_json_file(value: Path) -> Path:
    """Validate that the provided file is a properly formatted JSON file.

    This function performs two validations:
    1. Checks if the file has a .json extension
    2. Attempts to parse the file content as JSON

    Args:
        value: The path to the file to validate

    Returns:
        The validated file path

    Raises:
        typer.BadParameter: If the file is not a .json file or contains invalid JSON
    """
    import json

    if value.suffix != ".json":
        msg = "The schema file must be a JSON file."
        raise typer.BadParameter(msg)

    try:
        with open(value) as f:
            json.load(f)
    except json.JSONDecodeError as e:
        msg = "The schema file must be a valid JSON file."
        raise typer.BadParameter(msg) from e

    return value


def parse_column(col: str) -> int | str:
    """Parse column specification as int or string."""
    try:
        return int(col)
    except ValueError:
        return col


def _parse_run_target(target: str) -> tuple[str, str]:
    expected_parts = 2
    if "::" not in target:
        emsg = "TARGET must be 'module_or_file::attr' (e.g., process::main)."
        raise typer.BadParameter(emsg)
    parts = target.split("::")
    if len(parts) != expected_parts or not parts[0] or not parts[1]:
        emsg = "TARGET must be 'module_or_file::attr' (e.g., process::main)."
        raise typer.BadParameter(emsg)
    return parts[0], parts[1]


def _looks_like_file(value: str) -> bool:
    if value.endswith(".py"):
        return True
    if value.startswith((".", "/", "~")):
        return True
    if os.sep in value:
        return True
    return os.altsep is not None and os.altsep in value


def _load_module_from_file(path: Path) -> ModuleType:
    if not path.exists() or not path.is_file():
        emsg = f"File not found: {path}"
        raise typer.BadParameter(emsg)
    resolved_path = path.expanduser().resolve()
    module_hash = hashlib.sha256(str(resolved_path).encode()).hexdigest()
    module_name = f"_rdetoolkit_run_{path.stem}_{module_hash}"
    spec = importlib.util.spec_from_file_location(module_name, resolved_path)
    if spec is None or spec.loader is None:
        emsg = f"Unable to load module from file: {path}"
        raise typer.BadParameter(emsg)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_target_module(module_or_file: str) -> ModuleType:
    if _looks_like_file(module_or_file):
        path = Path(module_or_file).expanduser()
        return _load_module_from_file(path)
    try:
        return importlib.import_module(module_or_file)
    except Exception as exc:
        emsg = f"Failed to import module: {module_or_file}"
        raise typer.BadParameter(emsg) from exc


def _resolve_target_attr(module: ModuleType, attr: str) -> object:
    target: object = module
    for part in attr.split("."):
        if not hasattr(target, part):
            emsg = f"Attribute not found: {attr}"
            raise typer.BadParameter(emsg)
        target = getattr(target, part)
    return target


def _validate_target_function(func: object) -> Callable[..., object]:
    if inspect.isclass(func):
        emsg = "Classes are not allowed. Please specify a function."
        raise typer.BadParameter(emsg)
    if not inspect.isfunction(func):
        emsg = "Only functions are allowed. Please specify a function."
        raise typer.BadParameter(emsg)
    signature = inspect.signature(func)
    try:
        signature.bind(1, 2)
    except (TypeError, ValueError) as exc:
        emsg = "Target function cannot be called with two positional arguments."
        raise typer.BadParameter(emsg) from exc
    return cast(Callable[..., object], func)


def _load_target_function(target: str) -> Callable[..., object]:
    module_or_file, attr = _parse_run_target(target)
    module = _load_target_module(module_or_file)
    func = _resolve_target_attr(module, attr)
    return _validate_target_function(func)


@app.command()
def init(
    template: Annotated[
        Path | None,
        typer.Option(
            "--template",
            help="Template config path or directory containing pyproject.toml/rdeconfig.",
            exists=True,
            file_okay=True,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = None,
    processing_template: Annotated[
        str | None,
        typer.Option("--processing-template", help="Registered ProcessingTemplate skeleton name."),
    ] = None,
    template_modules: Annotated[
        list[str] | None,
        typer.Option("--module", help="Import a template provider module; repeatable."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite existing processing-template output files."),
    ] = False,
    entry_point: Annotated[
        Path | None,
        typer.Option(
            "--entry-point",
            help="Template file copied to container/main.py.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            resolve_path=True,
        ),
    ] = None,
    modules: Annotated[
        Path | None,
        typer.Option(
            "--modules",
            help="Template file or directory copied under container/modules/.",
            exists=True,
            file_okay=True,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = None,
    tasksupport: Annotated[
        Path | None,
        typer.Option(
            "--tasksupport",
            help="Template file or directory copied under tasksupport locations.",
            exists=True,
            file_okay=True,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = None,
    inputdata: Annotated[
        Path | None,
        typer.Option(
            "--inputdata",
            help="Template directory copied under inputdata locations.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = None,
    other: Annotated[
        list[Path] | None,
        typer.Option(
            "--other",
            help="Additional templates copied under container/ (repeatable).",
            exists=True,
            file_okay=True,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = None,
) -> None:
    """Output files needed to build RDE structured programs."""
    if processing_template is not None:
        from rdetoolkit.cli.templates_cmd import generate_processing_template

        generate_processing_template(processing_template, template_modules or [], Path.cwd(), force=force)
        return

    # Lazy import to minimize startup cost
    from rdetoolkit.cmd.command import InitCommand, InitTemplateConfig

    cli_template_config = None
    if any((entry_point, modules, tasksupport, inputdata, other)):
        cli_template_config = InitTemplateConfig(
            entry_point=entry_point,
            modules=modules,
            tasksupport=tasksupport,
            inputdata=inputdata,
            other=other,
        )

    cmd = InitCommand(template_path=template, cli_template_config=cli_template_config)
    cmd.invoke()


@app.command()
def version() -> None:
    """Command to display version."""
    # Lazy import to minimize startup cost
    from rdetoolkit.cmd.command import VersionCommand

    cmd = VersionCommand()
    cmd.invoke()


@app.command()
def run(
    target: Annotated[str | None, typer.Argument(metavar="<module_or_file::attr>")] = None,
    flow: Annotated[str | None, typer.Option("--flow", help="Dotted v2 flow reference (pkg.mod:callable).")] = None,
    validate_only: Annotated[bool, typer.Option("--validate-only", help="Validate config and mode without calling the flow.")] = False,
    config: Annotated[Path | None, typer.Option("--config", help="YAML configuration overrides.")] = None,
) -> None:
    """Run rdetoolkit workflows with a user-defined dataset function."""
    from rdetoolkit.cli.run_cmd import legacy_exit_code, run_flow, usage_error

    if (target is None) == (flow is None):
        usage_error("Provide exactly one of TARGET or --flow")
    if validate_only and flow is None:
        usage_error("--validate-only requires --flow")
    if config is not None and flow is None:
        usage_error("--config requires --flow")
    if flow is not None:
        run_flow(flow, validate_only_requested=validate_only, config_path=config)
        return
    func = _load_target_function(cast(str, target))
    from rdetoolkit import cli as cli_module

    try:
        # Looked up on the module object at call time, never bound at import
        # time: the v2 CLI tests spy on ``rdetoolkit.workflows.run`` itself.
        workflow_run = cast(Callable[..., str], cli_module.workflows.run)
        result = workflow_run(custom_dataset_function=func)
    except SystemExit as exc:
        # The v1 Python contract for a failed run is ``sys.exit(1)``, and
        # ``SystemExit`` is a BaseException -- it would sail straight through the
        # handler below and surface as a traceback. Design §9.3 wants one
        # uniform CLI code for every ``run`` form, so it is mapped here
        # (Session J2 ruling #3).
        raise typer.Exit(code=_FAILED_EXIT_CODE if exc.code else 0) from exc
    except Exception as exc:
        typer.echo("An error occurred while running the workflow.", err=True)
        raise typer.Exit(code=_FAILED_EXIT_CODE) from exc
    if result is not None:
        typer.echo(result)
    # A partial run returns normally from the v1 API (process status 0 by the
    # v1 contract) but is exit code 2 for every ``run`` CLI form.
    exit_code = legacy_exit_code(result)
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command("gen-config")
def gen_config(
    output_dir: Annotated[
        Path | None,
        typer.Argument(
            help="Target directory for rdeconfig.yaml",
            exists=False,
            file_okay=False,
            resolve_path=True,
        ),
    ] = None,
    template_name: Annotated[
        str,
        typer.Option(
            "--template",
            help="Template style for rdeconfig.yaml.",
            case_sensitive=False,
        ),
    ] = "minimal",
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            help="Allow replacing an existing rdeconfig.yaml.",
        ),
    ] = False,
    lang: Annotated[
        str,
        typer.Option(
            "--lang",
            help="Prompt language (interactive template only).",
            case_sensitive=False,
        ),
    ] = "en",
) -> None:
    """Generate an rdeconfig.yaml template in the target directory."""
    # Lazy imports
    from typing import Literal, cast
    import typer
    from rdetoolkit.cmd.gen_config import (
        GenerateConfigCommand,
        TEMPLATE_CHOICES,
        LANG_CHOICES,
    )

    template_key = template_name.lower()
    lang_key = lang.lower()

    # Validate template choice
    if template_key not in TEMPLATE_CHOICES:
        msg = f"Invalid template: {template_name}. Choose from {list(TEMPLATE_CHOICES)}"
        raise typer.BadParameter(
            msg,
            param_hint="--template",
        )

    # Validate lang choice
    if lang_key not in LANG_CHOICES:
        msg = f"Invalid language: {lang}. Choose from {list(LANG_CHOICES)}"
        raise typer.BadParameter(
            msg,
            param_hint="--lang",
        )

    # Validate lang is only used with interactive template
    if template_key != "interactive" and lang_key != "en":
        msg = "--lang is only available when --template=interactive"
        raise typer.BadParameter(
            msg,
            param_hint="--lang",
        )

    target_dir = output_dir if output_dir is not None else Path.cwd()

    command = GenerateConfigCommand(
        output_dir=target_dir,
        template=cast(
            Literal["minimal", "full", "multitile", "rdeformat", "smarttable", "interactive"],
            template_key,
        ),
        overwrite=overwrite,
        lang=cast(Literal["en", "ja"], lang_key if template_key == "interactive" else "en"),
    )
    command.invoke()


@app.command()
def artifact(
    source_dir: Annotated[
        Path,
        typer.Option(
            "--source-dir",
            "-s",
            help="The source directory to compress and scan.",
            exists=True,
            file_okay=False,
            resolve_path=True,
        ),
    ],
    output_archive: Annotated[
        Path | None,
        typer.Option(
            "--output-archive",
            "-o",
            help="Output archive file (e.g. rde_template.zip).",
            exists=False,
        ),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude",
            "-e",
            help="Exclude directory names. Defaults to 'venv' and 'site-packages'.",
        ),
    ] = None,
) -> None:
    """Create an artifact (.zip) for submission to RDE by archiving the specified source directory, excluding specified files or directories."""
    # Lazy imports
    from rdetoolkit.cmd.archive import CreateArtifactCommand

    cmd = CreateArtifactCommand(
        source_dir,
        output_archive_path=output_archive,
        exclude_patterns=exclude,
    )
    cmd.invoke()


@app.command("make-excelinvoice")
def make_excelinvoice(
    invoice_schema_json_path: Annotated[
        Path,
        typer.Argument(
            help="Path to invoice.schema.json file",
            exists=True,
            dir_okay=False,
            resolve_path=True,
        ),
    ],
    output_path: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help=f"Path to ExcelInvoice file output (default: ./{DEFAULT_EXCEL_INVOICE_TEMPLATE})",
            exists=False,
            dir_okay=False,
            resolve_path=True,
        ),
    ] = None,
    mode: Annotated[
        str,
        typer.Option(
            "-m",
            "--mode",
            help="Select the registration mode: 'file' or 'folder' (default: file)",
            case_sensitive=False,
        ),
    ] = "file",
) -> None:
    """Generate an Excel invoice based on the provided schema and save it to the specified output path."""
    # Lazy imports
    from typing import Literal, cast

    from rdetoolkit.cmd.gen_excelinvoice import GenerateExcelInvoiceCommand

    # Validate JSON file
    validated_path = validate_json_file(invoice_schema_json_path)

    # Set default output path if not provided
    final_output_path = output_path if output_path is not None else Path.cwd() / DEFAULT_EXCEL_INVOICE_TEMPLATE

    # Validate mode
    if mode.lower() not in ["file", "folder"]:
        msg = "Mode must be 'file' or 'folder'"
        raise typer.BadParameter(
            msg,
            param_hint="--mode",
        )

    cmd = GenerateExcelInvoiceCommand(
        validated_path,
        final_output_path,
        cast(Literal["file", "folder"], mode.lower()),
    )
    cmd.invoke()


def _run_generate_invoice(
    schema_path: Annotated[
        Path,
        typer.Argument(
            help="Path to invoice.schema.json file",
            exists=True,
            dir_okay=False,
            resolve_path=True,
        ),
    ],
    output_path: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help="Path to output invoice.json file (default: ./invoice.json)",
            exists=False,
            dir_okay=False,
            resolve_path=True,
        ),
    ] = None,
    fill_defaults: Annotated[
        bool,
        typer.Option(
            "--fill-defaults/--no-fill-defaults",
            help="Fill type-based default values (default: enabled)",
        ),
    ] = True,
    required_only: Annotated[
        bool,
        typer.Option(
            "--required-only",
            help="Include only required fields (default: disabled)",
        ),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            help="Output JSON format: 'pretty' or 'compact' (default: pretty)",
            case_sensitive=False,
        ),
    ] = "pretty",
) -> None:
    """Generate invoice.json from invoice.schema.json.

    Creates a valid invoice.json file based on the structure and requirements
    defined in the provided invoice.schema.json file.

    Examples:
        rdetoolkit gen-invoice invoice.schema.json

        rdetoolkit gen-invoice invoice.schema.json -o output/invoice.json

        rdetoolkit gen-invoice invoice.schema.json --required-only --no-fill-defaults

        rdetoolkit gen-invoice invoice.schema.json --format compact
    """
    # Lazy imports
    from typing import Literal, cast
    from rdetoolkit.cmd.gen_invoice import GenerateInvoiceCommand

    # Set default output path
    final_output_path = output_path if output_path is not None else Path.cwd() / "invoice.json"

    # Validate JSON file
    validated_schema_path = validate_json_file(schema_path)

    # Validate format
    format_lower = output_format.lower()
    if format_lower not in ["pretty", "compact"]:
        msg = "Format must be 'pretty' or 'compact'"
        raise typer.BadParameter(msg, param_hint="--format")

    # Create and invoke command
    cmd = GenerateInvoiceCommand(
        schema_path=validated_schema_path,
        output_path=final_output_path,
        fill_defaults=fill_defaults,
        required_only=required_only,
        output_format=cast(Literal["pretty", "compact"], format_lower),
    )
    cmd.invoke()


@app.command("gen-invoice", help="Generate invoice.json from invoice.schema.json.")
def gen_invoice(
    schema_path: Annotated[
        Path,
        typer.Argument(
            help="Path to invoice.schema.json file",
            exists=True,
            dir_okay=False,
            resolve_path=True,
        ),
    ],
    output_path: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help="Path to output invoice.json file (default: ./invoice.json)",
            exists=False,
            dir_okay=False,
            resolve_path=True,
        ),
    ] = None,
    fill_defaults: Annotated[
        bool,
        typer.Option(
            "--fill-defaults/--no-fill-defaults",
            help="Fill type-based default values (default: enabled)",
        ),
    ] = True,
    required_only: Annotated[
        bool,
        typer.Option(
            "--required-only",
            help="Include only required fields (default: disabled)",
        ),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            help="Output JSON format: 'pretty' or 'compact' (default: pretty)",
            case_sensitive=False,
        ),
    ] = "pretty",
) -> None:
    """Generate invoice.json from invoice.schema.json."""
    _run_generate_invoice(
        schema_path=schema_path,
        output_path=output_path,
        fill_defaults=fill_defaults,
        required_only=required_only,
        output_format=output_format,
    )


@app.command()
def csv2graph(
    csv_path: Annotated[Path, typer.Argument(help="Path to CSV file", exists=False, dir_okay=False)],
    output_dir: Annotated[Path | None, typer.Option("--output-dir", "-o", help="Output directory for plots")] = None,
    main_image_dir: Annotated[Path | None, typer.Option("--main-image-dir", help="Directory for combined plot outputs")] = None,
    html_output_dir: Annotated[Path | None, typer.Option("--html-output-dir", help="Directory for HTML outputs (defaults to the CSV directory)")] = None,
    csv_format: Annotated[str, typer.Option("--csv-format", help="CSV format type")] = "standard",
    logy: Annotated[bool, typer.Option("--logy", help="Use log scale for Y axis")] = False,
    logx: Annotated[bool, typer.Option("--logx", help="Use log scale for X axis")] = False,
    html: Annotated[bool, typer.Option("--html", help="Generate interactive HTML output")] = False,
    mode: Annotated[str, typer.Option("--mode", help="Plotting mode")] = "overlay",
    x_col: Annotated[list[str] | None, typer.Option("--x-col", help="X-axis column(s) - index or name")] = None,
    y_cols: Annotated[list[str] | None, typer.Option("--y-cols", help="Y-axis column(s) - index or name")] = None,
    direction_cols: Annotated[list[str] | None, typer.Option("--direction-cols", help="Direction column(s)")] = None,
    direction_filter: Annotated[list[str] | None, typer.Option("--direction-filter", help="Filter direction values")] = None,
    direction_colors: Annotated[list[str] | None, typer.Option("--direction-colors", help="Direction colors (format: dir=color)")] = None,
    title: Annotated[str | None, typer.Option("--title", help="Plot title")] = None,
    legend_info: Annotated[str | None, typer.Option("--legend-info", help="Additional legend information")] = None,
    legend_loc: Annotated[str | None, typer.Option("--legend-loc", help="Legend location")] = None,
    xlim: Annotated[tuple[float, float] | None, typer.Option("--xlim", help="X-axis limits (min max)")] = None,
    ylim: Annotated[tuple[float, float] | None, typer.Option("--ylim", help="Y-axis limits (min max)")] = None,
    grid: Annotated[bool, typer.Option("--grid", help="Show grid")] = False,
    invert_x: Annotated[bool, typer.Option("--invert-x", help="Invert x-axis")] = False,
    invert_y: Annotated[bool, typer.Option("--invert-y", help="Invert y-axis")] = False,
    no_individual: Annotated[bool | None, typer.Option("--no-individual/--individual", help="Skip individual plots; defaults to auto for single-series overlay.")] = None,
    max_legend_items: Annotated[int | None, typer.Option("--max-legend-items", help="Maximum legend items")] = None,
) -> None:
    """Generate graphs from CSV files."""
    # Lazy imports
    from typing import Literal, cast
    from rdetoolkit.cmd.csv2graph import Csv2GraphCommand

    # Validate csv_format
    if csv_format not in ["standard", "transpose", "noheader"]:
        msg = f"Invalid csv-format: {csv_format}. Choose from ['standard', 'transpose', 'noheader']"
        raise typer.BadParameter(
            msg,
            param_hint="--csv-format",
        )

    # Validate mode
    if mode not in ["overlay", "individual"]:
        msg = f"Invalid mode: {mode}. Choose from ['overlay', 'individual']"
        raise typer.BadParameter(
            msg,
            param_hint="--mode",
        )

    # Parse column specifications
    parsed_x_col = [parse_column(c) for c in x_col] if x_col else None
    parsed_y_cols = [parse_column(c) for c in y_cols] if y_cols else None
    parsed_direction_cols = [parse_column(c) for c in direction_cols] if direction_cols else None
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
        html_output_dir=html_output_dir,
        csv_format=cast(Literal["standard", "transpose", "noheader"], csv_format),
        logy=logy,
        logx=logx,
        html=html,
        mode=cast(Literal["overlay", "individual"], mode),
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


@app.command()
def agent_guide(
    detailed: Annotated[
        bool,
        typer.Option(
            "--detailed",
            help="Show detailed guide with advanced patterns and full API reference.",
        ),
    ] = False,
) -> None:
    """Display agent guide for AI coding assistants.

    Shows documentation designed for AI coding agents (Claude Code, GitHub Copilot, etc.)
    to effectively use rdetoolkit. By default, displays a concise summary guide.
    Use --detailed for comprehensive documentation.

    Examples:
        # Show summary guide
        $ rdetoolkit agent-guide

        # Show detailed guide with advanced patterns
        $ rdetoolkit agent-guide --detailed
    """
    from rdetoolkit._agent import get_guide

    try:
        guide_content = get_guide(detailed=detailed)
        typer.echo(guide_content)
    except FileNotFoundError as e:
        typer.secho(f"Error: Guide file not found: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except OSError as e:
        typer.secho(f"Error: Failed to read guide file: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e


# Import validate commands module at end to avoid circular imports
def _register_validate_commands() -> typer.Typer:
    """Register validate subcommands."""
    from rdetoolkit.cli.validate import app as validate_app_local

    app.add_typer(validate_app_local, name="validate")
    return validate_app_local


validate_app = _register_validate_commands()


def _register_v2_inspection_commands() -> tuple[typer.Typer, typer.Typer, typer.Typer]:
    """Register v2 node and flow inspection subcommands."""
    from rdetoolkit.cli.flows_cmd import app as flows_app_local
    from rdetoolkit.cli.nodes_cmd import app as nodes_app_local
    from rdetoolkit.cli.templates_cmd import app as templates_app_local

    app.add_typer(nodes_app_local, name="nodes")
    app.add_typer(flows_app_local, name="flows")
    app.add_typer(templates_app_local, name="templates")
    return nodes_app_local, flows_app_local, templates_app_local


nodes_app, flows_app, templates_app = _register_v2_inspection_commands()


def _register_v2_format_commands() -> typer.Typer:
    """Register plugin format inspection subcommands."""
    from rdetoolkit.cli.formats_cmd import app as formats_app_local

    app.add_typer(formats_app_local, name="formats")
    return formats_app_local


formats_app = _register_v2_format_commands()


def _register_v2_reporting_commands() -> tuple[typer.Typer, typer.Typer, typer.Typer, typer.Typer]:
    """Register v2 reporting subcommands."""
    from rdetoolkit.cli.graph_cmd import app as graph_app_local
    from rdetoolkit.cli.migrate_cmd import app as migrate_app_local
    from rdetoolkit.cli.report_cmd import app as report_app_local
    from rdetoolkit.cli.repro_cmd import app as repro_app_local

    app.add_typer(graph_app_local, name="graph")
    app.add_typer(report_app_local, name="report")
    app.add_typer(repro_app_local, name="repro")
    app.add_typer(migrate_app_local, name="migrate")
    return graph_app_local, report_app_local, repro_app_local, migrate_app_local


graph_app, report_app, repro_app, migrate_app = _register_v2_reporting_commands()
