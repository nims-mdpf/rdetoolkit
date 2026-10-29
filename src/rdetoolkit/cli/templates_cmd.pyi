from collections.abc import Sequence
from pathlib import Path

import typer

app: typer.Typer

def list_templates(as_json: bool = False, modules: list[str] | None = None) -> None: ...
def describe(template_id: str, as_json: bool = False, modules: list[str] | None = None) -> None: ...
def generate_processing_template(
    name: str, modules: Sequence[str], output_dir: Path, *, force: bool = False
) -> None: ...
