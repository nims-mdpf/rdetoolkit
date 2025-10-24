from __future__ import annotations

from pathlib import Path
from typing import Literal

from logging import Logger

CONFIG_FILE_NAME: str
TEMPLATE_CHOICES: tuple[str, ...]
LANG_CHOICES: tuple[str, ...]
STATIC_TEMPLATES: dict[str, str]
PROMPTS: dict[str, dict[str, str]]

class GenerateConfigCommand:
    output_dir: Path
    template: Literal["minimal", "full", "multitile", "rdeformat", "smarttable", "interactive"]
    overwrite: bool
    lang: Literal["en", "ja"]
    logger: Logger

    def __init__(
        self,
        output_dir: Path,
        template: Literal["minimal", "full", "multitile", "rdeformat", "smarttable", "interactive"],
        overwrite: bool,
        lang: Literal["en", "ja"],
    ) -> None: ...

    def invoke(self) -> None: ...
    def _confirm_overwrite(self, output_path: Path) -> bool: ...
    def _render_template(self) -> str: ...
    def _render_interactive(self) -> str: ...

    @staticmethod
    def _bool_to_yaml(value: bool) -> str: ...

    @staticmethod
    def _extended_mode_to_yaml(value: str | None) -> str: ...
