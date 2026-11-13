"""Typer CLI application for rdetoolkit.

Commands follow ``rdetoolkit <noun> <verb>`` and are grouped in the root
``--help`` by workflow phase (issue #616). Every command's help states its
inputs, outputs, examples, and exit codes; see :mod:`rdetoolkit.cli._help`.
The v1 command names (``gen-config``, ``gen-invoice``, ``make-excelinvoice``,
``csv2graph``, ``artifact``) still work in v2.0.x: they run the same code as
their replacements and print a deprecation warning first.
"""

# Avoid postponed evaluation so Typer can read Annotated metadata (minimum supported: Python 3.10).

import functools
import hashlib
import importlib.util
import inspect
import os
import sys
import warnings
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Annotated, Any, ParamSpec, cast

import typer
from typer.core import TyperCommand, TyperGroup

from rdetoolkit.cli._help import (
    EXIT_CLICK_USAGE,
    EXIT_OK,
    PANEL_DEPRECATED,
    PANEL_GENERATE,
    PANEL_INFO,
    PANEL_INSPECT,
    PANEL_MIGRATE,
    PANEL_PACKAGE,
    PANEL_RUN,
    PANEL_SCAFFOLD,
    PANEL_VALIDATE,
    CommandHelp,
    deprecation_message,
)
from rdetoolkit.cli._v2_common import import_project_module
# DEFAULT_EXCEL_INVOICE_TEMPLATE and validate_json_file are re-exported: they
# were importable from this module before the ``new`` group existed.
from rdetoolkit.cli.new_cmd import (  # noqa: F401
    DEFAULT_EXCEL_INVOICE_TEMPLATE,
    EXCELINVOICE_HELP,
    INVOICE_HELP,
    generate_config,
    new_excelinvoice,
    new_invoice,
    validate_json_file,
)

ROOT_HELP = CommandHelp(
    summary="Build, run, and package RDE (Research Data Express) structured-processing programs.",
    details=(
        "Commands are `rdetoolkit <noun> <verb>` and are grouped below by workflow phase. "
        "A typical project runs `init` -> `new config` -> `validate all` -> `run` -> `package`. "
        "Every command's `--help` lists its inputs, outputs, examples, and exit codes."
    ),
    examples=(
        "rdetoolkit init",
        "rdetoolkit validate all",
        "rdetoolkit run modules.processing:pipeline",
        "rdetoolkit report show data/logs/run_report_<id>.json",
        "rdetoolkit package -s container -o rde_submission.zip",
    ),
    exit_codes=(
        EXIT_OK,
        (1, "the command or the run failed"),
        (2, "`run`: partial (some tiles failed); other commands: invalid command line or, for `validate`, a usage error"),
        (3, "invalid input to a v2 command (bad reference, unreadable file, lint violations)"),
    ),
    see_also=("rdetoolkit agent-guide",),
)

#: Root command order: the root ``--help`` prints panels in the order their
#: first command appears, so this order is the workflow order.
_COMMAND_ORDER = (
    "init",
    "new",
    "plot",
    "validate",
    "run",
    "report",
    "nodes",
    "flows",
    "skeletons",
    "formats",
    "package",
    "repro",
    "migrate",
    "agent-guide",
    "version",
)


class _WorkflowOrderedGroup(TyperGroup):
    """Root group that lists commands in :data:`_COMMAND_ORDER`, then the rest."""

    # ``ctx`` comes from ``click`` (typer < 0.26) or from typer's vendored
    # ``typer._click`` (typer >= 0.26); ``Any`` matches both base signatures (#740).
    def list_commands(self, ctx: Any) -> list[str]:
        names = super().list_commands(ctx)
        rank = {name: index for index, name in enumerate(_COMMAND_ORDER)}
        return sorted(names, key=lambda name: rank.get(name, len(rank)))


app = typer.Typer(
    name="rdetoolkit",
    cls=_WorkflowOrderedGroup,
    help=ROOT_HELP.render(),
    no_args_is_help=True,
    rich_markup_mode="markdown",
)

#: Exit status for a run whose report is ``failed`` (Design §9.3).
_FAILED_EXIT_CODE = 1


class _DeprecatedCommand(TyperCommand):
    """A v1 command name kept as an alias: warns on stderr, then runs normally.

    Typer passes no per-command payload to a command class, so
    :func:`_deprecated` makes one subclass per replacement.
    """

    replacement: str = ""

    def invoke(self, ctx: Any) -> Any:
        typer.echo(deprecation_message(f"rdetoolkit {self.name}", self.replacement), err=True)
        return super().invoke(ctx)


def _deprecated(replacement: str) -> type[TyperCommand]:
    """Return a command class whose invocation warns that ``replacement`` replaces it."""
    return type("DeprecatedCommand", (_DeprecatedCommand,), {"replacement": replacement})


def parse_column(col: str) -> int | str:
    """Parse column specification as int or string."""
    try:
        return int(col)
    except ValueError:
        return col


_LEGACY_TARGET_FORMAT = "TARGET must be 'module_or_file::attr' (e.g., process::main)."


def _parse_run_target(target: str) -> tuple[str, str]:
    expected_parts = 2
    if "::" not in target:
        raise typer.BadParameter(_LEGACY_TARGET_FORMAT)
    parts = target.split("::")
    if len(parts) != expected_parts or not parts[0] or not parts[1]:
        raise typer.BadParameter(_LEGACY_TARGET_FORMAT)
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
        return import_project_module(module_or_file)
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


# --------------------------------------------------------------------------
# Scaffold
# --------------------------------------------------------------------------

INIT_HELP = CommandHelp(
    summary="Create the project scaffold for an RDE structured program in the current directory.",
    inputs=(
        "`--template PATH`: a `pyproject.toml` or `rdeconfig.yaml` with a `[tool.rdetoolkit.init]` / `init:` "
        "section, or a directory that holds one. It names template files to copy.",
        "`--entry-point`, `--modules`, `--tasksupport`, `--inputdata`, `--other`: the same template paths given "
        "directly; they override the template config.",
    ),
    outputs=(
        "Creates `container/` (`main.py`, `modules/`, `requirements.txt`, `Dockerfile`, and `data/` with "
        "`inputdata/`, `invoice/invoice.json`, `tasksupport/{invoice.schema.json,metadata-def.json}`), "
        "`input/` (`inputdata/`, `invoice/invoice.json`), and `template/tasksupport/`.",
        "Existing files are kept (printed as `Skip: ... already exists.`); nothing is overwritten.",
    ),
    examples=(
        "rdetoolkit init",
        "rdetoolkit init --template pyproject.toml",
        "rdetoolkit init --entry-point my_main.py --modules my_modules/",
    ),
    exit_codes=(EXIT_OK, (1, "a file could not be created or the template config is invalid"), EXIT_CLICK_USAGE),
    see_also=("rdetoolkit new config", "rdetoolkit validate all", "rdetoolkit new processing"),
)


@app.command("init", help=INIT_HELP.render(), short_help=INIT_HELP.summary, rich_help_panel=PANEL_SCAFFOLD)
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
    entry_point: Annotated[
        Path | None,
        typer.Option("--entry-point", help="Template file copied to container/main.py.", exists=True, file_okay=True, dir_okay=False, resolve_path=True),
    ] = None,
    modules: Annotated[
        Path | None,
        typer.Option("--modules", help="Template file or directory copied under container/modules/.", exists=True, file_okay=True, dir_okay=True, resolve_path=True),
    ] = None,
    tasksupport: Annotated[
        Path | None,
        typer.Option("--tasksupport", help="Template file or directory copied under tasksupport locations.", exists=True, file_okay=True, dir_okay=True, resolve_path=True),
    ] = None,
    inputdata: Annotated[
        Path | None,
        typer.Option("--inputdata", help="Template directory copied under inputdata locations.", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    ] = None,
    other: Annotated[
        list[Path] | None,
        typer.Option("--other", help="Additional templates copied under container/ (repeatable).", exists=True, file_okay=True, dir_okay=True, resolve_path=True),
    ] = None,
) -> None:
    """Output files needed to build RDE structured programs."""
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


# --------------------------------------------------------------------------
# Generate: ``new`` group and ``plot``
# --------------------------------------------------------------------------


def _register_new_commands() -> typer.Typer:
    from rdetoolkit.cli.new_cmd import app as new_app_local

    app.add_typer(new_app_local, name="new", rich_help_panel=PANEL_GENERATE)
    return new_app_local


new_app = _register_new_commands()

PLOT_HELP = CommandHelp(
    summary="Draw graphs (PNG, optionally interactive HTML) from a CSV file.",
    inputs=(
        "`CSV_PATH`: a CSV file. `--csv-format standard` (header row, default), `transpose` (series in rows), or `noheader`.",
        "`--x-col` / `--y-cols`: columns by 0-based index or header name (repeatable); by default the first column is x.",
    ),
    outputs=(
        "Writes one overlay PNG plus one PNG per series into `-o/--output-dir` (default: the CSV's directory). "
        "`--mode individual` writes per-series PNGs only; a single-series overlay skips per-series PNGs unless `--individual`.",
        "`--main-image-dir` sends the overlay to another directory; `--html` also writes interactive HTML into "
        "`--html-output-dir` (default: the CSV's directory). Existing files with the same names are overwritten.",
    ),
    examples=(
        "rdetoolkit plot data/structured/sample.csv",
        "rdetoolkit plot sample.csv -o data/other_image --title 'XRD pattern'",
        "rdetoolkit plot sample.csv --x-col 0 --y-cols 1 --y-cols 2 --logy --html",
    ),
    exit_codes=(EXIT_OK, (1, "the CSV could not be read or plotted"), EXIT_CLICK_USAGE),
    see_also=("rdetoolkit run", "rdetoolkit package"),
)

CSV2GRAPH_HELP = CommandHelp(
    summary="Generate graphs from CSV files (deprecated alias of `rdetoolkit plot`).",
    details="Runs `rdetoolkit plot` with the same options after a deprecation warning; removed in v2.1.",
    examples=("rdetoolkit plot data/structured/sample.csv", "rdetoolkit csv2graph data/structured/sample.csv"),
    exit_codes=PLOT_HELP.exit_codes,
    see_also=("rdetoolkit plot",),
)


@app.command("plot", help=PLOT_HELP.render(), short_help=PLOT_HELP.summary, rich_help_panel=PANEL_GENERATE)
def plot(
    csv_path: Annotated[Path, typer.Argument(metavar="CSV_PATH", help="Path to CSV file", exists=False, dir_okay=False)],
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
    legend_policy: Annotated[
        str,
        typer.Option(
            "--legend-policy",
            help="Legend placement policy: legacy, auto, inside, outside_right, outside_bottom, hide",
        ),
    ] = "legacy",
    legend_outside_threshold: Annotated[
        int,
        typer.Option("--legend-outside-threshold", help="Item-count threshold for 'auto' placement (default: 8)"),
    ] = 8,
    legend_bottom_threshold: Annotated[
        int,
        typer.Option(
            "--legend-bottom-threshold",
            help="Item count at or above which 'auto' places the legend below the graph (default: 21; 0 or less disables)",
        ),
    ] = 21,
    legend_ncol: Annotated[
        int | None,
        typer.Option("--legend-ncol", help="Number of legend columns for 'outside_bottom' placement"),
    ] = None,
    x_tick_format: Annotated[str, typer.Option("--x-tick-format", help="X-axis tick label format: auto, plain, sci, or eng")] = "auto",
    y_tick_format: Annotated[str, typer.Option("--y-tick-format", help="Y-axis tick label format: auto, plain, sci, or eng")] = "auto",
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

    # Validate legend_policy
    valid_legend_policies = [
        "legacy", "auto", "inside", "outside_right", "outside_bottom", "hide",
    ]
    if legend_policy not in valid_legend_policies:
        msg = f"Invalid legend-policy: {legend_policy}. Choose from {valid_legend_policies}"
        raise typer.BadParameter(
            msg,
            param_hint="--legend-policy",
        )
    # Validate x_tick_format
    if x_tick_format not in ["auto", "plain", "sci", "eng"]:
        msg = f"Invalid x-tick-format: {x_tick_format}. Choose from ['auto', 'plain', 'sci', 'eng']"
        raise typer.BadParameter(msg, param_hint="--x-tick-format")

    # Validate y_tick_format
    if y_tick_format not in ["auto", "plain", "sci", "eng"]:
        msg = f"Invalid y-tick-format: {y_tick_format}. Choose from ['auto', 'plain', 'sci', 'eng']"
        raise typer.BadParameter(msg, param_hint="--y-tick-format")

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
        legend_policy=cast(
            Literal["legacy", "auto", "inside", "outside_right", "outside_bottom", "hide"],
            legend_policy,
        ),
        legend_outside_threshold=legend_outside_threshold,
        legend_bottom_threshold=legend_bottom_threshold if legend_bottom_threshold > 0 else None,
        legend_ncol=legend_ncol,
        x_tick_format=cast(Literal["auto", "plain", "sci", "eng"], x_tick_format),
        y_tick_format=cast(Literal["auto", "plain", "sci", "eng"], y_tick_format),
    )
    cmd.invoke()


# --------------------------------------------------------------------------
# Validate
# --------------------------------------------------------------------------


def _register_validate_commands() -> typer.Typer:
    """Register validate subcommands."""
    from rdetoolkit.cli.validate import app as validate_app_local

    app.add_typer(validate_app_local, name="validate", rich_help_panel=PANEL_VALIDATE)
    return validate_app_local


validate_app = _register_validate_commands()


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------

RUN_HELP = CommandHelp(
    summary="Run structured processing: a v2 flow (`pkg.mod:callable`) or, with `--legacy`, a v1 dataset function.",
    details=(
        "Run it from the project root: the Runner reads `data/inputdata`, `data/invoice`, and `data/tasksupport`, "
        "finds `rdeconfig.yaml`, and processes every tile."
    ),
    inputs=(
        "`REF` (v2): `pkg.mod:callable` naming a flow function or a ProcessingTemplate subclass; the current directory is importable.",
        "`REF` with `--legacy` (v1): `module_or_file::attr` naming `def f(srcpaths, resource_paths)`, as passed to "
        "`workflows.run(custom_dataset_function=...)`. The `::` form without `--legacy` still works in v2.0.x; "
        "`--legacy` becomes required in v2.1.",
        "`--config FILE` (v2 only): YAML overrides merged over the discovered rdeconfig.yaml.",
        "`--validate-only` (v2 only): check the config, mode, and invoice without calling the flow. "
        "A flow `prepare=` hook still runs and may modify `inputdata/`.",
    ),
    outputs=(
        "Writes the RDE output tree under `data/` (`structured/`, `meta/`, `raw/`, images, `logs/`, and `job.failed` on failure).",
        "v2: prints the run report JSON and saves it as `data/logs/run_report_<run_id>.json`. "
        "`--validate-only` prints `Validation succeeded` and writes no outputs (a `prepare=` hook may still modify `inputdata/`). "
        "v1: prints the legacy status JSON.",
    ),
    examples=(
        "rdetoolkit run modules.processing:pipeline",
        "rdetoolkit run modules.processing:pipeline --config overrides.yaml",
        "rdetoolkit run modules.processing:pipeline --validate-only",
        "rdetoolkit run --legacy main.py::dataset",
    ),
    exit_codes=(
        (0, "every tile succeeded (or `--validate-only` passed)"),
        (1, "the run failed (or validation failed)"),
        (2, "partial: some tiles failed (also used by the parser for an unknown option)"),
        (3, "invalid REF, a flow or legacy TARGET that cannot be loaded, unreadable `--config`, or options that do not apply to `--legacy`"),
    ),
    see_also=("rdetoolkit validate all", "rdetoolkit report show", "rdetoolkit report trace", "rdetoolkit package"),
)


@app.command("run", help=RUN_HELP.render(), short_help=RUN_HELP.summary, rich_help_panel=PANEL_RUN)
def run(
    target: Annotated[
        str | None,
        typer.Argument(metavar="REF", help="Flow reference pkg.mod:callable, or module_or_file::attr with --legacy."),
    ] = None,
    legacy: Annotated[bool, typer.Option("--legacy", help="Run a v1 dataset function given as module_or_file::attr.")] = False,
    validate_only: Annotated[bool, typer.Option("--validate-only", help="Validate config, mode, and invoice without calling the flow. A flow prepare= hook still runs and may modify inputdata.")] = False,
    config: Annotated[Path | None, typer.Option("--config", help="YAML configuration overrides (v2 flows only).")] = None,
) -> None:
    """Run a v2 flow or a v1 dataset function."""
    from rdetoolkit.cli.run_cmd import run_flow, usage_error

    if target is None:
        usage_error(
            "Missing REF.\n"
            "Remediation: pass a flow reference such as 'rdetoolkit run modules.processing:pipeline', "
            "or 'rdetoolkit run --legacy main.py::dataset' for a v1 dataset function.",
        )
    if legacy or "::" in target:
        if "::" not in target:
            usage_error(
                f"Invalid legacy TARGET '{target}': {_LEGACY_TARGET_FORMAT}\n"
                "Remediation: name the file or module and the function, e.g. 'rdetoolkit run --legacy main.py::dataset', "
                "or drop --legacy to run a v2 flow 'pkg.mod:callable'.",
            )
        if validate_only or config is not None:
            option = "--validate-only" if validate_only else "--config"
            usage_error(
                f"{option} applies only to v2 flows, not to the legacy form 'module_or_file::attr'.\n"
                "Remediation: drop the option, or run a v2 flow with 'rdetoolkit run pkg.mod:callable'.",
            )
        _run_legacy(target)
        return
    if ":" not in target:
        usage_error(
            f"Invalid REF '{target}': a v2 flow is 'pkg.mod:callable'; for a v1 dataset function, "
            f"{_LEGACY_TARGET_FORMAT}\n"
            "Remediation: use 'rdetoolkit run modules.processing:pipeline' or 'rdetoolkit run --legacy main.py::dataset'.",
        )
    run_flow(target, validate_only_requested=validate_only, config_path=config)


def _run_legacy(target: str) -> None:
    """Run ``workflows.run(custom_dataset_function=...)`` for a ``module_or_file::attr`` target."""
    from rdetoolkit.cli.run_cmd import legacy_exit_code, usage_error

    try:
        func = _load_target_function(target)
    except typer.BadParameter as exc:
        # Exit 3 like every other ``run`` usage error: Click's own code for a
        # BadParameter (2) would read as "partial" (Design §9.3).
        usage_error(
            f"{exc.message}\n"
            "Remediation: check that the file or module exists and that the attribute names a "
            "function taking (srcpaths, resource_paths).",
        )
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


# --------------------------------------------------------------------------
# Inspect
# --------------------------------------------------------------------------


def _register_inspect_commands() -> tuple[typer.Typer, typer.Typer, typer.Typer, typer.Typer, typer.Typer]:
    """Register the run-report and registry inspection groups."""
    from rdetoolkit.cli.flows_cmd import app as flows_app_local
    from rdetoolkit.cli.formats_cmd import app as formats_app_local
    from rdetoolkit.cli.nodes_cmd import app as nodes_app_local
    from rdetoolkit.cli.report_cmd import app as report_app_local
    from rdetoolkit.cli.templates_cmd import app as skeletons_app_local

    app.add_typer(report_app_local, name="report", rich_help_panel=PANEL_INSPECT)
    app.add_typer(nodes_app_local, name="nodes", rich_help_panel=PANEL_INSPECT)
    app.add_typer(flows_app_local, name="flows", rich_help_panel=PANEL_INSPECT)
    app.add_typer(skeletons_app_local, name="skeletons", rich_help_panel=PANEL_INSPECT)
    app.add_typer(formats_app_local, name="formats", rich_help_panel=PANEL_INSPECT)
    return report_app_local, nodes_app_local, flows_app_local, skeletons_app_local, formats_app_local


report_app, nodes_app, flows_app, skeletons_app, formats_app = _register_inspect_commands()


# --------------------------------------------------------------------------
# Package
# --------------------------------------------------------------------------

PACKAGE_HELP = CommandHelp(
    summary="Create the RDE submission archive (.zip) from a source directory, with a scan report.",
    inputs=(
        "`-s/--source-dir DIR`: the directory to archive, usually `container/` (required).",
        "`-e/--exclude NAME`: directory names to leave out (repeatable; default: `.*`, `venv`, `.venv`, `site-packages`).",
    ),
    outputs=(
        "Writes the zip given by `-o/--output` (default: `<YYYYMMDD>_<id>_rde_artifact.zip` next to the source directory); "
        "the name must end with `.zip` and an existing file is replaced.",
        "Writes a Markdown report next to the zip (same name, `.md`) listing the Dockerfile and requirements.txt "
        "checks, external-connection references, and code-security findings.",
    ),
    examples=(
        "rdetoolkit package -s container",
        "rdetoolkit package -s container -o rde_submission.zip",
        "rdetoolkit package -s container -o rde_submission.zip -e tests -e .venv",
    ),
    exit_codes=(EXIT_OK, (1, "the output name is not .zip, or archiving or the report failed"), EXIT_CLICK_USAGE),
    see_also=("rdetoolkit run", "rdetoolkit validate all"),
)

_SOURCE_DIR_OPTION = typer.Option(
    "--source-dir",
    "-s",
    help="The source directory to compress and scan.",
    exists=True,
    file_okay=False,
    resolve_path=True,
)
_EXCLUDE_OPTION = typer.Option(
    "--exclude",
    "-e",
    help="Exclude directory names. Defaults to '.*', 'venv', '.venv', and 'site-packages'.",
)


def _create_package(source_dir: Path, output: Path | None, exclude: list[str] | None) -> None:
    from rdetoolkit.cmd.archive import CreateArtifactCommand

    CreateArtifactCommand(source_dir, output_archive_path=output, exclude_patterns=exclude).invoke()


@app.command("package", help=PACKAGE_HELP.render(), short_help=PACKAGE_HELP.summary, rich_help_panel=PANEL_PACKAGE)
def package(
    source_dir: Annotated[Path, _SOURCE_DIR_OPTION],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Output archive file (e.g. rde_submission.zip).")] = None,
    exclude: Annotated[list[str] | None, _EXCLUDE_OPTION] = None,
) -> None:
    """Create the RDE submission archive from a source directory."""
    _create_package(source_dir, output, exclude)


def _register_package_commands() -> typer.Typer:
    from rdetoolkit.cli.repro_cmd import app as repro_app_local

    app.add_typer(repro_app_local, name="repro", rich_help_panel=PANEL_PACKAGE)
    return repro_app_local


repro_app = _register_package_commands()


# --------------------------------------------------------------------------
# Migrate
# --------------------------------------------------------------------------


def _register_migrate_commands() -> typer.Typer:
    from rdetoolkit.cli.migrate_cmd import app as migrate_app_local

    app.add_typer(migrate_app_local, name="migrate", rich_help_panel=PANEL_MIGRATE)
    return migrate_app_local


migrate_app = _register_migrate_commands()


# --------------------------------------------------------------------------
# Info
# --------------------------------------------------------------------------

AGENT_GUIDE_HELP = CommandHelp(
    summary="Display agent guide for AI coding assistants: the rdetoolkit workflow and API as Markdown.",
    details="The summary guide covers the common workflow; `--detailed` adds advanced patterns and the API reference.",
    outputs=("Prints Markdown to stdout. Writes no files; redirect to save it.",),
    examples=("rdetoolkit agent-guide", "rdetoolkit agent-guide --detailed > AGENT_GUIDE.md"),
    exit_codes=(EXIT_OK, (1, "the packaged guide file is missing or unreadable"), EXIT_CLICK_USAGE),
    see_also=("rdetoolkit --help",),
)


@app.command("agent-guide", help=AGENT_GUIDE_HELP.render(), short_help=AGENT_GUIDE_HELP.summary, rich_help_panel=PANEL_INFO)
def agent_guide(
    detailed: Annotated[
        bool,
        typer.Option(
            "--detailed",
            help="Show detailed guide with advanced patterns and full API reference.",
        ),
    ] = False,
) -> None:
    """Display agent guide for AI coding assistants."""
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


VERSION_HELP = CommandHelp(
    summary="Print the installed rdetoolkit version.",
    outputs=("Prints the version string. Writes no files.",),
    examples=("rdetoolkit version", "python -m rdetoolkit version"),
    exit_codes=(EXIT_OK,),
)


@app.command("version", help=VERSION_HELP.render(), short_help=VERSION_HELP.summary, rich_help_panel=PANEL_INFO)
def version() -> None:
    """Command to display version."""
    # Lazy import to minimize startup cost
    from rdetoolkit.cmd.command import VersionCommand

    cmd = VersionCommand()
    cmd.invoke()


# --------------------------------------------------------------------------
# Deprecated v1 names (removed in v2.1)
# --------------------------------------------------------------------------

GEN_CONFIG_HELP = CommandHelp(
    summary="Generate an rdeconfig.yaml template in the target directory (deprecated alias of `rdetoolkit new config`).",
    details=(
        "Option names differ from `new config`: `OUTPUT_DIR` is positional here (`-o` there), "
        "`--template` is `--preset`, and `--overwrite` is `--force`. Removed in v2.1."
    ),
    examples=("rdetoolkit new config --preset full -o container/data/tasksupport", "rdetoolkit gen-config container/data/tasksupport --template full"),
    exit_codes=(EXIT_OK, (1, "writing failed, or you declined to overwrite"), EXIT_CLICK_USAGE),
    see_also=("rdetoolkit new config",),
)


@app.command(
    "gen-config",
    cls=_deprecated("rdetoolkit new config"),
    help=GEN_CONFIG_HELP.render(),
    short_help="Use `rdetoolkit new config`.",
    rich_help_panel=PANEL_DEPRECATED,
)
def _gen_config_alias(
    output_dir: Annotated[
        Path | None,
        typer.Argument(help="Target directory for rdeconfig.yaml", exists=False, file_okay=False, resolve_path=True),
    ] = None,
    template_name: Annotated[str, typer.Option("--template", help="Template style for rdeconfig.yaml.", case_sensitive=False)] = "minimal",
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Allow replacing an existing rdeconfig.yaml.")] = False,
    lang: Annotated[str, typer.Option("--lang", help="Prompt language (interactive template only).", case_sensitive=False)] = "en",
) -> None:
    """Generate an rdeconfig.yaml template in the target directory."""
    generate_config(output_dir, preset=template_name, force=overwrite, lang=lang, preset_option="--template")


GEN_INVOICE_HELP = CommandHelp(
    summary="Generate invoice.json from invoice.schema.json (deprecated alias of `rdetoolkit new invoice`).",
    details="Same arguments and options as `rdetoolkit new invoice`. Removed in v2.1.",
    examples=("rdetoolkit new invoice invoice.schema.json -o invoice.json", "rdetoolkit gen-invoice invoice.schema.json -o invoice.json"),
    exit_codes=INVOICE_HELP.exit_codes,
    see_also=("rdetoolkit new invoice",),
)

app.command(
    "gen-invoice",
    cls=_deprecated("rdetoolkit new invoice"),
    help=GEN_INVOICE_HELP.render(),
    short_help="Use `rdetoolkit new invoice`.",
    rich_help_panel=PANEL_DEPRECATED,
)(new_invoice)

MAKE_EXCELINVOICE_HELP = CommandHelp(
    summary=(
        "Generate an Excel invoice based on the provided schema and save it to the specified output path "
        "(deprecated alias of `rdetoolkit new excelinvoice`)."
    ),
    details="Same arguments and options as `rdetoolkit new excelinvoice`. Removed in v2.1.",
    examples=(
        "rdetoolkit new excelinvoice invoice.schema.json -o a_excel_invoice.xlsx",
        "rdetoolkit make-excelinvoice invoice.schema.json -o a_excel_invoice.xlsx",
    ),
    exit_codes=EXCELINVOICE_HELP.exit_codes,
    see_also=("rdetoolkit new excelinvoice",),
)

app.command(
    "make-excelinvoice",
    cls=_deprecated("rdetoolkit new excelinvoice"),
    help=MAKE_EXCELINVOICE_HELP.render(),
    short_help="Use `rdetoolkit new excelinvoice`.",
    rich_help_panel=PANEL_DEPRECATED,
)(new_excelinvoice)


def make_excelinvoice(invoice_schema_json_path: Path, output_path: Path | None = None, mode: str = "file") -> None:
    """Generate an ExcelInvoice workbook (deprecated v1 Python name of ``new_excelinvoice``; removed in v2.1).

    Keeps the v1.x keyword ``invoice_schema_json_path`` for code that calls
    this function directly and emits a DeprecationWarning. The CLI name
    ``make-excelinvoice`` is registered on :func:`new_excelinvoice` above and
    warns on stderr instead.
    """
    _warn_python_name("make_excelinvoice", "rdetoolkit.cli.new_cmd.new_excelinvoice()")
    new_excelinvoice(invoice_schema_json_path, output_path, mode=mode)

app.command(
    "csv2graph",
    cls=_deprecated("rdetoolkit plot"),
    help=CSV2GRAPH_HELP.render(),
    short_help="Use `rdetoolkit plot`.",
    rich_help_panel=PANEL_DEPRECATED,
)(plot)

ARTIFACT_HELP = CommandHelp(
    summary=(
        "Create an artifact (.zip) for submission to RDE by archiving the specified source directory "
        "(deprecated alias of `rdetoolkit package`)."
    ),
    details="`--output-archive` is `-o/--output` in `rdetoolkit package`. Removed in v2.1.",
    examples=("rdetoolkit package -s container -o rde_submission.zip", "rdetoolkit artifact -s container -o rde_submission.zip"),
    exit_codes=PACKAGE_HELP.exit_codes,
    see_also=("rdetoolkit package",),
)


@app.command(
    "artifact",
    cls=_deprecated("rdetoolkit package"),
    help=ARTIFACT_HELP.render(),
    short_help="Use `rdetoolkit package`.",
    rich_help_panel=PANEL_DEPRECATED,
)
def _artifact_alias(
    source_dir: Annotated[Path, _SOURCE_DIR_OPTION],
    output_archive: Annotated[Path | None, typer.Option("--output-archive", "-o", help="Output archive file (e.g. rde_template.zip).")] = None,
    exclude: Annotated[list[str] | None, _EXCLUDE_OPTION] = None,
) -> None:
    """Create an artifact (.zip) for submission to RDE."""
    _create_package(source_dir, output_archive, exclude)


# --------------------------------------------------------------------------
# v1 Python names (deprecated, removed in v2.1)
# --------------------------------------------------------------------------
#
# rdetoolkit 1.x exposed the CLI callbacks as importable functions. They stay
# callable with their v1 keyword arguments and emit a DeprecationWarning; the
# CLI aliases above are separate callbacks that warn on stderr instead, so a
# command line never gets both warnings.

_P = ParamSpec("_P")


def _warn_python_name(old: str, new: str) -> None:
    warnings.warn(
        f"rdetoolkit.cli.app.{old}() is deprecated and will be removed in rdetoolkit v2.1; use {new} instead.",
        DeprecationWarning,
        stacklevel=3,
    )


def _python_alias(command: Callable[_P, None], old: str, new: str) -> Callable[_P, None]:
    """Return ``command`` under its v1 name, warning once per call."""

    @functools.wraps(command)
    def alias(*args: _P.args, **kwargs: _P.kwargs) -> None:
        _warn_python_name(old, new)
        command(*args, **kwargs)

    alias.__name__ = alias.__qualname__ = old
    alias.__doc__ = f"Deprecated v1 Python name; use {new} instead. Removed in rdetoolkit v2.1."
    return alias


gen_config = _python_alias(_gen_config_alias, "gen_config", "rdetoolkit.cli.new_cmd.new_config()")
gen_invoice = _python_alias(new_invoice, "gen_invoice", "rdetoolkit.cli.new_cmd.new_invoice()")
csv2graph = _python_alias(plot, "csv2graph", "rdetoolkit.cli.app.plot()")
artifact = _python_alias(_artifact_alias, "artifact", "rdetoolkit.cli.app.package()")
