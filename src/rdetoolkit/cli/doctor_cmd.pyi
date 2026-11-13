from pathlib import Path

from rdetoolkit.cli._help import CommandHelp

DOCTOR_HELP: CommandHelp

def doctor(
    project_dir: Path | None = None,
    ref: str | None = None,
    output_format: str = "text",
) -> None: ...
