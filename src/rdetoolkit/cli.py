from __future__ import annotations

import json
import pathlib
from typing import Literal

import click

from rdetoolkit.cmd.archive import CreateArtifactCommand
from rdetoolkit.cmd.command import InitCommand, VersionCommand
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


def _validation_json_file(ctx: click.Context, param: click.Parameter, value: pathlib.Path) -> pathlib.Path:
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


@click.command(help="Generate an Excel invoice based on the provided schema and save it to the specified output path.")
@click.argument(
    "invoice_schema_json_path",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True, path_type=pathlib.Path),
    callback=_validation_json_file,
    metavar="<invoice.shcema.json file path>",
)
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(exists=False, dir_okay=False, resolve_path=True, path_type=pathlib.Path),
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
def make_excelinvoice(invoice_schema_json_path: pathlib.Path, output_path: pathlib.Path, mode: Literal["file", "folder"]) -> None:
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


cli.add_command(init)
cli.add_command(version)
cli.add_command(make_excelinvoice)
cli.add_command(artifact)
