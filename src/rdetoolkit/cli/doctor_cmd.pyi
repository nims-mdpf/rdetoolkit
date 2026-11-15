from pathlib import Path

from rdetoolkit.cli._help import CommandHelp

DOCTOR_HELP: CommandHelp
STATIC_ONLY_NOTE: str

def doctor(
    project_dir: Path | None = None,
    ref: str | None = None,
    output_format: str = "text",
    modules: list[str] | None = None,
    strict: bool = False,
) -> None: ...
