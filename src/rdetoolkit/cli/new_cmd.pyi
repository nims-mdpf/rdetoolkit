from pathlib import Path

import typer

from rdetoolkit.cli._help import CommandHelp

DEFAULT_EXCEL_INVOICE_TEMPLATE: str
NEW_HELP: CommandHelp
CONFIG_HELP: CommandHelp
INVOICE_HELP: CommandHelp
EXCELINVOICE_HELP: CommandHelp
PROCESSING_HELP: CommandHelp
app: typer.Typer

def validate_json_file(value: Path) -> Path: ...
def generate_config(output_dir: Path | None, *, preset: str, force: bool, lang: str, preset_option: str = "--preset") -> None: ...
def new_config(output_dir: Path | None = None, preset: str = "minimal", force: bool = False, lang: str = "en") -> None: ...
def generate_invoice(schema_path: Path, output_path: Path | None, *, fill_defaults: bool, required_only: bool, output_format: str) -> None: ...
def new_invoice(
    schema_path: Path,
    output_path: Path | None = None,
    fill_defaults: bool = True,
    required_only: bool = False,
    output_format: str = "pretty",
) -> None: ...
def generate_excelinvoice(schema_path: Path, output_path: Path | None, *, mode: str) -> None: ...
def new_excelinvoice(schema_path: Path, output_path: Path | None = None, mode: str = "file") -> None: ...
def new_processing(skeleton: str, modules: list[str] | None = None, output_dir: Path | None = None, force: bool = False) -> None: ...
