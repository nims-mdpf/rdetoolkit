"""Tests for the gen-config CLI command.

Equivalence Partitioning Table
| API | Input/State Partition | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `rdetoolkit.cli.gen_config` | Initial creation and subsequent overwrite confirmation accepted | Valid path covering fresh and confirmed overwrite | File generated/replaced with minimal template | TC-EP-001 |
| `rdetoolkit.cli.gen_config` | `--template full` on clean directory | Validate alternate static template content | YAML matches full template | TC-EP-002 |
| `rdetoolkit.cli.gen_config` | `--template interactive --lang ja --overwrite` | Ensure forced overwrite skips prompt and respects locale | Interactive run succeeds without overwrite prompt | TC-EP-003 |
| `rdetoolkit.cli.gen_config` | Existing file, no overwrite flag, user declines | Validate abort path when confirmation denied | Command aborts and file unchanged | TC-EP-004 |
| `rdetoolkit.cli.gen_config` | Filesystem write failure | Simulate external dependency error | ClickException raised with failure message | TC-EP-005 |
| `rdetoolkit.cli.gen_config` | Non-interactive template with `--lang ja` | Enforce option exclusivity rules | CLI exits with parameter error | TC-EP-006 |

Boundary Value Table
| API | Boundary | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `rdetoolkit.cli.gen_config` | File already exists, user confirms overwrite | Upper boundary of confirmation handling | YAML regenerated after `[y]` input | TC-BV-001 |
| `rdetoolkit.cli.gen_config` | File already exists, user declines overwrite | Lower boundary of confirmation handling | Command aborts | TC-BV-002 |
| `rdetoolkit.cli.gen_config` | `--overwrite` flag provided | Boundary on bypassing confirmation | No overwrite prompt shown | TC-BV-003 |
| `rdetoolkit.cli.gen_config` | `--lang` with static templates | Option validity boundary | Parameter error emitted | TC-BV-004 |
"""

from __future__ import annotations

from pathlib import Path
import textwrap

import click
from click.testing import CliRunner
import pytest

from rdetoolkit.cli import gen_config
from rdetoolkit.cmd.gen_config import CONFIG_FILE_NAME, STATIC_TEMPLATES


@pytest.fixture()
def cli_runner() -> CliRunner:
    """Provide a reusable CliRunner fixture."""
    return CliRunner()


def test_gen_config_minimal_template(cli_runner: CliRunner, tmp_path: Path) -> None:
    """TC-EP-001 / TC-BV-001"""
    # Given: a clean output directory with no config file
    output_dir = tmp_path / "minimal"
    # When: running gen-config with default (minimal) template
    result = cli_runner.invoke(gen_config, [str(output_dir)])
    # Then: command succeeds and writes the minimal template
    assert result.exit_code == 0
    config_path = output_dir / CONFIG_FILE_NAME
    assert config_path.exists()
    assert config_path.read_text(encoding="utf-8") == STATIC_TEMPLATES["minimal"]

    # When: invoking again without --overwrite and confirming overwrite
    second_result = cli_runner.invoke(gen_config, [str(output_dir)], input="y\n")
    # Then: overwrite prompt appears and file regenerated
    assert second_result.exit_code == 0
    prompt_fragment = f"{config_path.resolve()} exists. Overwrite? [y/N]:"
    assert prompt_fragment in second_result.output
    assert config_path.read_text(encoding="utf-8") == STATIC_TEMPLATES["minimal"]


def test_gen_config_full_template(cli_runner: CliRunner, tmp_path: Path) -> None:
    """TC-EP-002"""
    # Given: a clean output directory and explicit template selection
    output_dir = tmp_path / "full"
    # When: generating the full template
    result = cli_runner.invoke(gen_config, [str(output_dir), "--template", "full"])
    # Then: command succeeds with full template content
    assert result.exit_code == 0
    config_path = output_dir / CONFIG_FILE_NAME
    assert config_path.exists()
    assert config_path.read_text(encoding="utf-8") == STATIC_TEMPLATES["full"]


def test_gen_config_interactive_overwrite_and_lang(cli_runner: CliRunner, tmp_path: Path) -> None:
    """TC-EP-003 / TC-BV-003"""
    # Given: an existing rdeconfig.yaml that should be replaced interactively
    output_dir = tmp_path / "interactive"
    config_path = output_dir / CONFIG_FILE_NAME
    output_dir.mkdir(parents=True)
    config_path.write_text("outdated", encoding="utf-8")
    interactive_answers = "\n".join([
        "y",  # save_raw
        "n",  # save_nonshared_raw
        "y",  # magic_variable
        "n",  # save_thumbnail_image
        "MultiDataTile",  # extended_mode
        "y",  # multidata ignore_errors
        "y",  # smarttable save_table_file
        "n",  # traceback enabled
        "",  # ensure trailing newline for click processing
    ])
    # When: running the interactive template with Japanese prompts
    result = cli_runner.invoke(
        gen_config,
        [
            str(output_dir),
            "--template",
            "interactive",
            "--lang",
            "ja",
            "--overwrite",
        ],
        input=interactive_answers,
    )
    # Then: command exits successfully and overwrites the file
    assert result.exit_code == 0
    assert "Overwrite?" not in result.output
    expected = textwrap.dedent(
        """
        system:
          save_raw: true
          save_nonshared_raw: false
          magic_variable: true
          save_thumbnail_image: false
          extended_mode: "MultiDataTile"

        multidata_tile:
          ignore_errors: true

        smarttable:
          save_table_file: true

        traceback: # custom traceback settings
          enabled: false
        """
    ).lstrip("\n")
    assert config_path.read_text(encoding="utf-8") == expected


def test_gen_config_overwrite_denied(cli_runner: CliRunner, tmp_path: Path) -> None:
    """TC-EP-004 / TC-BV-002"""
    # Given: an existing file without the overwrite flag
    output_dir = tmp_path / "deny"
    config_path = output_dir / CONFIG_FILE_NAME
    output_dir.mkdir(parents=True)
    config_path.write_text("keep", encoding="utf-8")
    # When: user denies the overwrite confirmation
    result = cli_runner.invoke(gen_config, [str(output_dir)], input="n\n")
    # Then: command aborts without modifying the file
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "Aborted" in result.output
    assert config_path.read_text(encoding="utf-8") == "keep"


def test_gen_config_missing_write_permission(
    cli_runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-EP-005"""
    # Given: a directory that triggers a permission error during write
    output_dir = tmp_path / "locked"
    output_dir.mkdir(parents=True)
    target_path = output_dir / CONFIG_FILE_NAME

    def fake_write_text(self: Path, data: str, encoding: str = "utf-8", errors: str | None = None) -> int:
        raise PermissionError("permission denied")

    monkeypatch.setattr("rdetoolkit.cmd.gen_config.Path.write_text", fake_write_text)
    # When: invoking gen-config which attempts to write the file
    result = cli_runner.invoke(gen_config, [str(output_dir)])

    # Then: command surfaces a ClickException about the write failure
    assert result.exit_code != 0
    assert "Failed to write config file" in result.output
    assert not target_path.exists()


def test_gen_config_invalid_lang_combination(cli_runner: CliRunner, tmp_path: Path) -> None:
    """TC-EP-006 / TC-BV-004"""
    # Given: a non-interactive invocation that incorrectly supplies --lang ja
    output_dir = tmp_path / "lang"
    # When: running gen-config with invalid option combination
    result = cli_runner.invoke(gen_config, [str(output_dir), "--lang", "ja"])
    # Then: Click rejects the arguments with a parameter error
    assert result.exit_code == 2
    assert isinstance(result.exception, SystemExit)
    assert "--lang is only available" in result.output
