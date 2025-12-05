"""Equivalence Partitioning Table
| API                        | Input/State Partition                                  | Rationale                            | Expected Outcome                              | Test ID        |
| -------------------------- | ------------------------------------------------------ | ------------------------------------ | --------------------------------------------- | -------------- |
| InitCommand.invoke         | All CLI template paths provided in empty workspace     | Verify CLI-only flow with persistence | Files copied from CLI templates; config saved | TC-EP-001      |
| InitTemplateLoader.load    | `other` list contains empty string                     | Invalid path input                   | Raises InitTemplateError                      | TC-EP-002      |
| InitTemplateLoader.load    | `other` path points to non-existent file or directory  | Missing template asset               | Raises InitTemplateError                      | TC-EP-003      |

Boundary Value Table
| API                     | Boundary                                 | Rationale                      | Expected Outcome             | Test ID   |
| ----------------------- | ---------------------------------------- | ------------------------------ | ---------------------------- | --------- |
| InitTemplateLoader.load | `other` entry is empty string            | Lower boundary for path string | Raises InitTemplateError     | TC-BV-001 |
| InitTemplateLoader.load | `other` entry references missing target  | Non-existent path boundary     | Raises InitTemplateError     | TC-BV-002 |
| InitCommand.invoke      | No config files exist in working folder  | Boundary for config persistence| pyproject.toml is created    | TC-BV-003 |

Test execution (local env):
- pytest -q --maxfail=1 --cov=rdetoolkit --cov-branch --cov-report=term-missing --cov-report=html
- tox
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from rdetoolkit.cmd.command import InitCommand, InitTemplateConfig, InitTemplateError, InitTemplateLoader


def test_init_command_applies_cli_templates__tc_ep_001(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: CLI templates for every supported target in a fresh workspace
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    templates_dir = workspace / "templates"
    templates_dir.mkdir()

    entry_template = templates_dir / "custom_main.py"
    entry_template.write_text("print('custom')\n", encoding="utf-8")

    modules_template = templates_dir / "modules"
    modules_template.mkdir()
    (modules_template / "mod.py").write_text("print('mod')\n", encoding="utf-8")

    tasksupport_template = templates_dir / "tasksupport"
    tasksupport_template.mkdir()
    (tasksupport_template / "metadata-def.json").write_text("{}", encoding="utf-8")

    inputdata_template = templates_dir / "inputdata"
    inputdata_template.mkdir()
    (inputdata_template / "data.txt").write_text("data\n", encoding="utf-8")

    other_file = templates_dir / "extra.txt"
    other_file.write_text("extra\n", encoding="utf-8")
    other_dir = templates_dir / "extras"
    other_dir.mkdir()
    (other_dir / "nested.txt").write_text("nested\n", encoding="utf-8")

    cli_templates = InitTemplateConfig(
        entry_point=entry_template,
        modules=modules_template,
        tasksupport=tasksupport_template,
        inputdata=inputdata_template,
        other=[other_file, other_dir],
    )
    cmd = InitCommand(template_path=None, cli_template_config=cli_templates)

    # When: invoking init with CLI-provided templates
    cmd.invoke()

    # Then: files are copied from templates and persisted config is created
    assert (workspace / "container" / "main.py").read_text(encoding="utf-8") == "print('custom')\n"
    assert (workspace / "container" / "modules" / "mod.py").read_text(encoding="utf-8") == "print('mod')\n"
    assert (workspace / "container" / "data" / "tasksupport" / "metadata-def.json").read_text(encoding="utf-8") == "{}"
    assert (workspace / "templates" / "tasksupport" / "metadata-def.json").read_text(encoding="utf-8") == "{}"
    assert (workspace / "container" / "data" / "inputdata" / "data.txt").read_text(encoding="utf-8") == "data\n"
    assert (workspace / "input" / "inputdata" / "data.txt").read_text(encoding="utf-8") == "data\n"
    assert (workspace / "container" / "extra.txt").read_text(encoding="utf-8") == "extra\n"
    assert (workspace / "container" / "extras" / "nested.txt").read_text(encoding="utf-8") == "nested\n"

    pyproject = tomllib.loads((workspace / "pyproject.toml").read_text(encoding="utf-8"))
    init_section = pyproject["tool"]["rdetoolkit"]["init"]
    assert init_section["entry_point"] == "templates/custom_main.py"
    assert init_section["modules"] == "templates/modules"
    assert init_section["tasksupport"] == "templates/tasksupport"
    assert init_section["inputdata"] == "templates/inputdata"
    assert init_section["other"] == ["templates/extra.txt", "templates/extras"]


def test_init_template_loader_rejects_empty_other_entry__tc_ep_002(tmp_path: Path) -> None:
    # Given: a pyproject template config containing an empty entry in the 'other' list
    config = tmp_path / "pyproject.toml"
    config.write_text('[tool.rdetoolkit.init]\nother = [""]\n', encoding="utf-8")
    loader = InitTemplateLoader(config)

    # When: loading the template configuration
    # Then: it rejects the empty path with an InitTemplateError
    with pytest.raises(InitTemplateError) as excinfo:
        loader.load()
    assert "non-empty string" in str(excinfo.value)


def test_init_template_loader_rejects_missing_other_path__tc_ep_003(tmp_path: Path) -> None:
    # Given: a pyproject template config pointing to a missing path inside 'other'
    config = tmp_path / "pyproject.toml"
    config.write_text('[tool.rdetoolkit.init]\nother = ["missing.txt"]\n', encoding="utf-8")
    loader = InitTemplateLoader(config)

    # When: loading the template configuration
    # Then: it raises InitTemplateError because the path does not exist
    with pytest.raises(InitTemplateError) as excinfo:
        loader.load()
    assert "does not exist" in str(excinfo.value)
