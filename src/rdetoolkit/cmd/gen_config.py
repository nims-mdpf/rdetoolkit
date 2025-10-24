from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import click

from rdetoolkit.rdelogger import get_logger

CONFIG_FILE_NAME = "rdeconfig.yaml"
TEMPLATE_CHOICES = (
    "minimal",
    "full",
    "multitile",
    "rdeformat",
    "smarttable",
    "interactive",
)
LANG_CHOICES = ("en", "ja")

STATIC_TEMPLATES: dict[str, str] = {
    "minimal": (
        "system:\n"
        "  save_raw: false\n"
        "  save_nonshared_raw: true\n"
        "  magic_variable: false\n"
        "  save_thumbnail_image: true\n"
        "  extended_mode: null\n\n"
        "traceback: # custom traceback settings\n"
        "  enabled: false\n"
    ),
    "full": (
        "system:\n"
        "  save_raw: false\n"
        "  save_nonshared_raw: true\n"
        "  magic_variable: false\n"
        "  save_thumbnail_image: true\n"
        "  extended_mode: null\n\n"
        "multidata_tile:\n"
        "  ignore_errors: false\n\n"
        "traceback: # custom traceback settings\n"
        "  enabled: false\n"
    ),
    "multitile": (
        "system:\n"
        "  save_raw: false\n"
        "  save_nonshared_raw: true\n"
        "  magic_variable: false\n"
        "  save_thumbnail_image: true\n"
        "  extended_mode: \"MultiDataTile\"\n\n"
        "multidata_tile:\n"
        "  ignore_errors: false\n\n"
        "traceback: # custom traceback settings\n"
        "  enabled: false\n"
    ),
    "rdeformat": (
        "system:\n"
        "  save_raw: false\n"
        "  save_nonshared_raw: true\n"
        "  magic_variable: false\n"
        "  save_thumbnail_image: true\n"
        "  extended_mode: \"rdeformat\"\n\n"
        "traceback: # custom traceback settings\n"
        "  enabled: false\n"
    ),
    "smarttable": (
        "system:\n"
        "  save_raw: false\n"
        "  save_nonshared_raw: true\n"
        "  magic_variable: false\n"
        "  save_thumbnail_image: true\n"
        "  extended_mode: null\n\n"
        "smarttable:\n"
        "  save_table_file: true\n\n"
        "traceback: # custom traceback settings\n"
        "  enabled: false\n"
    ),
}

PROMPTS: dict[str, dict[str, str]] = {
    "en": {
        "save_raw": "Save raw data to shared raw directory?",
        "save_nonshared_raw": "Save data to nonshared_raw directory?",
        "magic_variable": "Enable magic_variable expansion?",
        "save_thumbnail_image": "Save thumbnail images automatically?",
        "extended_mode": "Select extended mode",
        "multidata_tile_ignore_errors": "Ignore errors during MultiDataTile processing?",
        "smarttable_save_table_file": "Save SmartTable source files?",
        "traceback_enabled": "Enable compact traceback formatting?",
    },
    "ja": {
        "save_raw": "生データをrawディレクトリに保存しますか?",
        "save_nonshared_raw": "データをnonshared_rawディレクトリに保存しますか?",
        "magic_variable": "magic_variable機能を有効にしますか?",
        "save_thumbnail_image": "サムネイル画像を自動保存しますか?",
        "extended_mode": "extended_modeを選択してください",
        "multidata_tile_ignore_errors": "MultiDataTile処理でエラーを無視しますか?",
        "smarttable_save_table_file": "SmartTableの元ファイルを保存しますか?",
        "traceback_enabled": "コンパクトトレースバックを有効にしますか?",
    },
}


class GenerateConfigCommand:
    """Create rdeconfig.yaml files from predefined templates."""

    def __init__(
        self,
        output_dir: Path,
        template: Literal[
            "minimal",
            "full",
            "multitile",
            "rdeformat",
            "smarttable",
            "interactive",
        ],
        overwrite: bool,
        lang: Literal["en", "ja"],
    ) -> None:
        self.output_dir = output_dir
        self.template = template
        self.overwrite = overwrite
        self.lang = lang
        self.logger = get_logger(__name__)

    def invoke(self) -> None:
        """Generate the configuration file at the resolved output path.

        Ensures the output directory exists, optionally prompts before overwriting an
        existing file, renders the configuration template, writes it to disk, and logs
        the operation. Raises a `click.ClickException` if the directory creation or
        file write fails, and raises `click.Abort` if the user declines to overwrite.
        """
        output_dir = self.output_dir.resolve()
        output_path = output_dir / CONFIG_FILE_NAME

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            emsg = f"Failed to create output directory: {output_dir}"
            raise click.ClickException(emsg) from exc

        if (
            output_path.exists()
            and not self.overwrite
            and not self._confirm_overwrite(output_path)
        ):
            raise click.Abort

        content = self._render_template()

        try:
            output_path.write_text(content, encoding="utf-8")
        except OSError as exc:
            emsg = f"Failed to write config file: {output_path}"
            raise click.ClickException(emsg) from exc

        self.logger.info("Generated rdeconfig.yaml at %s", output_path)
        if self.logger.isEnabledFor(logging.INFO):
            click.echo(
                click.style(f"Generated rdeconfig.yaml at {output_path}", fg="green"),
            )

    def _confirm_overwrite(self, output_path: Path) -> bool:
        prompt = f"{output_path.resolve()} exists. Overwrite?"
        return click.confirm(prompt, default=False, show_default=True)

    def _render_template(self) -> str:
        if self.template == "interactive":
            return self._render_interactive()
        template = STATIC_TEMPLATES.get(self.template)
        if template is None:
            msg = f"Unknown template: {self.template}"
            raise click.ClickException(msg)
        return template

    def _render_interactive(self) -> str:
        prompts = PROMPTS[self.lang]
        save_raw = click.confirm(
            prompts["save_raw"], default=False, show_default=True,
        )
        save_nonshared_raw = click.confirm(
            prompts["save_nonshared_raw"], default=True, show_default=True,
        )
        magic_variable = click.confirm(
            prompts["magic_variable"], default=False, show_default=True,
        )
        save_thumbnail_image = click.confirm(
            prompts["save_thumbnail_image"], default=True, show_default=True,
        )
        extended_mode_choice = click.prompt(
            prompts["extended_mode"],
            type=click.Choice(
                ["none", "MultiDataTile", "rdeformat"],
                case_sensitive=False,
            ),
            default="none",
            show_default=True,
            show_choices=True,
        )
        extended_mode = (
            None
            if extended_mode_choice.lower() == "none"
            else extended_mode_choice
        )
        ignore_errors = click.confirm(
            prompts["multidata_tile_ignore_errors"],
            default=False,
            show_default=True,
        )
        save_table_file = click.confirm(
            prompts["smarttable_save_table_file"],
            default=False,
            show_default=True,
        )
        traceback_enabled = click.confirm(
            prompts["traceback_enabled"],
            default=False,
            show_default=True,
        )

        lines: list[str] = [
            "system:",
            f"  save_raw: {self._bool_to_yaml(save_raw)}",
            f"  save_nonshared_raw: {self._bool_to_yaml(save_nonshared_raw)}",
            f"  magic_variable: {self._bool_to_yaml(magic_variable)}",
            f"  save_thumbnail_image: {self._bool_to_yaml(save_thumbnail_image)}",
            f"  extended_mode: {self._extended_mode_to_yaml(extended_mode)}",
        ]

        lines.extend(
            [
                "",
                "multidata_tile:",
                f"  ignore_errors: {self._bool_to_yaml(ignore_errors)}",
            ],
        )

        lines.extend(
            [
                "",
                "smarttable:",
                f"  save_table_file: {self._bool_to_yaml(save_table_file)}",
            ],
        )

        lines.extend(
            [
                "",
                "traceback: # custom traceback settings",
                f"  enabled: {self._bool_to_yaml(traceback_enabled)}",
                "",
            ],
        )

        return "\n".join(lines).rstrip("\n") + "\n"

    @staticmethod
    def _bool_to_yaml(value: bool) -> str:
        return "true" if value else "false"

    @staticmethod
    def _extended_mode_to_yaml(value: str | None) -> str:
        if value is None:
            return "null"
        return f'"{value}"'
