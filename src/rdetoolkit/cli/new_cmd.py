"""``rdetoolkit new``: generate one project file (or file set) per command.

Every command here writes files and prints what it wrote. The functions named
``generate_*`` hold the behaviour so the deprecated v1 commands
(``gen-config``, ``gen-invoice``, ``make-excelinvoice``) in
:mod:`rdetoolkit.cli.app` run exactly the same code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal, cast

import typer

from rdetoolkit.cli._help import (
    EXIT_CLICK_USAGE,
    EXIT_OK,
    EXIT_V1_FAILED,
    CommandHelp,
)

DEFAULT_EXCEL_INVOICE_TEMPLATE = "template_excel_invoice.xlsx"

NEW_HELP = CommandHelp(
    summary="Generate project files: rdeconfig.yaml, invoice.json, an ExcelInvoice, or processing code.",
    details="Each subcommand writes one kind of file. Run `rdetoolkit new <kind> --help` for its inputs and outputs.",
    examples=(
        "rdetoolkit new config",
        "rdetoolkit new invoice data/tasksupport/invoice.schema.json",
        "rdetoolkit new excelinvoice data/tasksupport/invoice.schema.json",
        "rdetoolkit new processing XrdTemplate --module modules.skeletons",
    ),
    exit_codes=(EXIT_OK, EXIT_V1_FAILED, EXIT_CLICK_USAGE, (3, "invalid input (`new processing` only)")),
    see_also=("rdetoolkit init", "rdetoolkit validate all", "rdetoolkit skeletons list"),
)

app = typer.Typer(help=NEW_HELP.render(), short_help=NEW_HELP.summary, no_args_is_help=True)


def validate_json_file(value: Path) -> Path:
    """Check that ``value`` is a ``.json`` file holding valid JSON.

    Args:
        value: Path given on the command line.

    Returns:
        The same path.

    Raises:
        typer.BadParameter: The suffix is not ``.json`` or the content does
            not parse.
    """
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


# --------------------------------------------------------------------------
# new config
# --------------------------------------------------------------------------


def generate_config(
    output_dir: Path | None,
    *,
    preset: str,
    force: bool,
    lang: str,
    preset_option: str = "--preset",
) -> None:
    """Write ``rdeconfig.yaml`` from a preset into ``output_dir``.

    Args:
        output_dir: Target directory; the current directory when ``None``.
        preset: Preset name (see ``TEMPLATE_CHOICES``), case-insensitive.
        force: Replace an existing file without asking.
        lang: Prompt language for the ``interactive`` preset.
        preset_option: Option name quoted in error messages (the deprecated
            ``gen-config`` spells it ``--template``).
    """
    from rdetoolkit.cmd.gen_config import LANG_CHOICES, TEMPLATE_CHOICES, GenerateConfigCommand

    preset_key = preset.lower()
    lang_key = lang.lower()
    if preset_key not in TEMPLATE_CHOICES:
        msg = f"Invalid {preset_option.lstrip('-')}: {preset}. Choose from {list(TEMPLATE_CHOICES)}"
        raise typer.BadParameter(msg, param_hint=preset_option)
    if lang_key not in LANG_CHOICES:
        msg = f"Invalid language: {lang}. Choose from {list(LANG_CHOICES)}"
        raise typer.BadParameter(msg, param_hint="--lang")
    if preset_key != "interactive" and lang_key != "en":
        msg = f"--lang is only available when {preset_option}=interactive"
        raise typer.BadParameter(msg, param_hint="--lang")
    command = GenerateConfigCommand(
        output_dir=output_dir if output_dir is not None else Path.cwd(),
        template=cast(Literal["minimal", "full", "multitile", "rdeformat", "smarttable", "interactive"], preset_key),
        overwrite=force,
        lang=cast(Literal["en", "ja"], lang_key if preset_key == "interactive" else "en"),
    )
    command.invoke()


CONFIG_HELP = CommandHelp(
    summary="Generate rdeconfig.yaml from a preset.",
    inputs=(
        "`--preset`: `minimal` (default), `full`, `multitile`, `rdeformat`, `smarttable`, or `interactive` "
        "(asks questions; `--lang en|ja` sets the prompt language).",
    ),
    outputs=(
        "Writes `rdeconfig.yaml` into `-o DIR` (default: the current directory); the directory is created if needed.",
        "An existing `rdeconfig.yaml` is kept unless you confirm the prompt or pass `--force`.",
    ),
    examples=(
        "rdetoolkit new config",
        "rdetoolkit new config --preset multitile -o container/data/tasksupport",
        "rdetoolkit new config --preset interactive --lang ja --force",
    ),
    exit_codes=(EXIT_OK, (1, "writing failed, or you declined to overwrite"), EXIT_CLICK_USAGE),
    see_also=("rdetoolkit init", "rdetoolkit validate all", "rdetoolkit run"),
)


@app.command("config", help=CONFIG_HELP.render(), short_help=CONFIG_HELP.summary)
def new_config(
    output_dir: Annotated[
        Path | None,
        typer.Option("-o", "--output", help="Directory that receives rdeconfig.yaml (default: current directory).", file_okay=False, resolve_path=True),
    ] = None,
    preset: Annotated[str, typer.Option("--preset", help="Preset to start from.", case_sensitive=False)] = "minimal",
    force: Annotated[bool, typer.Option("--force", help="Replace an existing rdeconfig.yaml without asking.")] = False,
    lang: Annotated[str, typer.Option("--lang", help="Prompt language for --preset interactive: en or ja.", case_sensitive=False)] = "en",
) -> None:
    """Generate rdeconfig.yaml from a preset."""
    generate_config(output_dir, preset=preset, force=force, lang=lang)


# --------------------------------------------------------------------------
# new invoice
# --------------------------------------------------------------------------


def generate_invoice(
    schema_path: Path,
    output_path: Path | None,
    *,
    fill_defaults: bool,
    required_only: bool,
    output_format: str,
) -> None:
    """Write ``invoice.json`` that satisfies ``schema_path``.

    Args:
        schema_path: ``invoice.schema.json`` to read.
        output_path: Destination file; ``./invoice.json`` when ``None``.
        fill_defaults: Fill type-based default values.
        required_only: Emit only required fields.
        output_format: ``pretty`` or ``compact``, case-insensitive.
    """
    from rdetoolkit.cmd.gen_invoice import GenerateInvoiceCommand

    final_output_path = output_path if output_path is not None else Path.cwd() / "invoice.json"
    validated_schema_path = validate_json_file(schema_path)
    format_lower = output_format.lower()
    if format_lower not in ["pretty", "compact"]:
        msg = "Format must be 'pretty' or 'compact'"
        raise typer.BadParameter(msg, param_hint="--format")
    GenerateInvoiceCommand(
        schema_path=validated_schema_path,
        output_path=final_output_path,
        fill_defaults=fill_defaults,
        required_only=required_only,
        output_format=cast(Literal["pretty", "compact"], format_lower),
    ).invoke()


INVOICE_HELP = CommandHelp(
    summary="Generate invoice.json from invoice.schema.json.",
    inputs=("`SCHEMA`: path to an `invoice.schema.json` file (must be valid JSON).",),
    outputs=(
        "Writes `-o FILE` (default: `./invoice.json`); parent directories are created and an existing file is overwritten.",
        "`--format pretty` (default) indents with 4 spaces; `--format compact` writes one line.",
    ),
    examples=(
        "rdetoolkit new invoice data/tasksupport/invoice.schema.json",
        "rdetoolkit new invoice invoice.schema.json -o data/invoice/invoice.json",
        "rdetoolkit new invoice invoice.schema.json --required-only",
        "rdetoolkit new invoice invoice.schema.json --format compact",
    ),
    exit_codes=(EXIT_OK, (1, "the schema could not be read or the invoice could not be written"), EXIT_CLICK_USAGE),
    see_also=("rdetoolkit validate invoice", "rdetoolkit new excelinvoice"),
)

_SCHEMA_ARGUMENT = typer.Argument(
    metavar="SCHEMA",
    help="Path to invoice.schema.json.",
    exists=True,
    dir_okay=False,
    resolve_path=True,
)


@app.command("invoice", help=INVOICE_HELP.render(), short_help=INVOICE_HELP.summary)
def new_invoice(
    schema_path: Annotated[Path, _SCHEMA_ARGUMENT],
    output_path: Annotated[
        Path | None,
        typer.Option("-o", "--output", help="Destination invoice.json (default: ./invoice.json).", dir_okay=False, resolve_path=True),
    ] = None,
    fill_defaults: Annotated[bool, typer.Option("--fill-defaults/--no-fill-defaults", help="Fill type-based default values.")] = True,
    required_only: Annotated[bool, typer.Option("--required-only", help="Include only required fields.")] = False,
    output_format: Annotated[str, typer.Option("--format", help="JSON layout: pretty or compact.", case_sensitive=False)] = "pretty",
) -> None:
    """Generate invoice.json from invoice.schema.json."""
    generate_invoice(
        schema_path,
        output_path,
        fill_defaults=fill_defaults,
        required_only=required_only,
        output_format=output_format,
    )


# --------------------------------------------------------------------------
# new excelinvoice
# --------------------------------------------------------------------------


def generate_excelinvoice(schema_path: Path, output_path: Path | None, *, mode: str) -> None:
    """Write an ExcelInvoice workbook for ``schema_path``.

    Args:
        schema_path: ``invoice.schema.json`` to read.
        output_path: Destination ``*_excel_invoice.xlsx``; the default
            template name in the current directory when ``None``.
        mode: ``file`` or ``folder`` registration mode, case-insensitive.
    """
    from rdetoolkit.cmd.gen_excelinvoice import GenerateExcelInvoiceCommand

    validated_path = validate_json_file(schema_path)
    final_output_path = output_path if output_path is not None else Path.cwd() / DEFAULT_EXCEL_INVOICE_TEMPLATE
    if mode.lower() not in ["file", "folder"]:
        msg = "Mode must be 'file' or 'folder'"
        raise typer.BadParameter(msg, param_hint="--mode")
    GenerateExcelInvoiceCommand(
        validated_path,
        final_output_path,
        cast(Literal["file", "folder"], mode.lower()),
    ).invoke()


EXCELINVOICE_HELP = CommandHelp(
    summary="Generate an ExcelInvoice workbook (*_excel_invoice.xlsx) from invoice.schema.json.",
    inputs=(
        "`SCHEMA`: path to an `invoice.schema.json` file (must be valid JSON).",
        "`--mode file` (default) registers one row per file; `--mode folder` one row per folder.",
    ),
    outputs=(
        f"Writes `-o FILE` (default: `./{DEFAULT_EXCEL_INVOICE_TEMPLATE}`); the name must end with `_excel_invoice.xlsx`. "
        "An existing file is overwritten.",
    ),
    examples=(
        "rdetoolkit new excelinvoice data/tasksupport/invoice.schema.json",
        "rdetoolkit new excelinvoice schema.json -o b_excel_invoice.xlsx -m folder",
    ),
    exit_codes=(EXIT_OK, (1, "the schema is invalid, the file name is wrong, or writing failed"), EXIT_CLICK_USAGE),
    see_also=("rdetoolkit new invoice", "rdetoolkit run"),
)


@app.command("excelinvoice", help=EXCELINVOICE_HELP.render(), short_help=EXCELINVOICE_HELP.summary)
def new_excelinvoice(
    schema_path: Annotated[Path, _SCHEMA_ARGUMENT],
    output_path: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help=f"Destination workbook (default: ./{DEFAULT_EXCEL_INVOICE_TEMPLATE}).",
            dir_okay=False,
            resolve_path=True,
        ),
    ] = None,
    mode: Annotated[str, typer.Option("-m", "--mode", help="Registration mode: file or folder.", case_sensitive=False)] = "file",
) -> None:
    """Generate an ExcelInvoice workbook from invoice.schema.json."""
    generate_excelinvoice(schema_path, output_path, mode=mode)


# --------------------------------------------------------------------------
# new processing
# --------------------------------------------------------------------------

PROCESSING_HELP = CommandHelp(
    summary="Generate processing.py, main.py, and a sample test from a registered processing skeleton.",
    inputs=(
        "`SKELETON`: a skeleton id or unambiguous class name as printed by `rdetoolkit skeletons list`.",
        "`--module`: import a module that declares skeletons before the lookup (repeatable). Without it, "
        "skeletons are found in `*.py` files of the current directory, its `modules/` package, and installed plugins.",
    ),
    outputs=(
        "Writes `processing.py`, `main.py`, and `tests/test_processing.py` under `-o DIR` (default: the current directory).",
        "Refuses (exit 3) when any of them exists, unless `--force` is given.",
    ),
    examples=(
        "rdetoolkit new processing XrdTemplate --module modules.skeletons",
        "rdetoolkit new processing XrdTemplate -o container --force",
    ),
    exit_codes=(EXIT_OK, EXIT_CLICK_USAGE, (3, "unknown skeleton, module import failure, or an output file already exists")),
    see_also=("rdetoolkit skeletons list", "rdetoolkit skeletons show", "rdetoolkit run"),
)


@app.command("processing", help=PROCESSING_HELP.render(), short_help=PROCESSING_HELP.summary)
def new_processing(
    skeleton: Annotated[str, typer.Argument(metavar="SKELETON", help="Skeleton id or class name.")],
    modules: Annotated[
        list[str] | None,
        typer.Option("--module", help="Import a module that declares skeletons; repeatable."),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option("-o", "--output", help="Directory that receives the generated files (default: current directory).", file_okay=False),
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Overwrite existing generated files.")] = False,
) -> None:
    """Generate processing code from a registered processing skeleton."""
    from rdetoolkit.cli.templates_cmd import generate_processing_template

    generate_processing_template(skeleton, modules or [], output_dir if output_dir is not None else Path.cwd(), force=force)
