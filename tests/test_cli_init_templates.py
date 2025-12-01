"""Test design tables for rdetoolkit init template support.

Equivalence Partitioning Table
| API | Input/State Partition | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `rdetoolkit.cli.init` | pyproject template file passed explicitly | Validate happy-path template expansion | Custom files copied into container/templates/input folders | `TC-EP-INIT-001` |
| `rdetoolkit.cli.init` | `--template .` with relative template paths | Boundary for directory lookup and relative resolution | Current directory pyproject drives template copy | `TC-EP-INIT-002` |
| `rdetoolkit.cli.init` | Unsupported template file extension | Invalid type rejection | Command aborts with helpful error | `TC-EP-INIT-003` |
| `rdetoolkit.cli.init` | pyproject lacks `[tool.rdetoolkit.init]` | Invalid configuration shape | Command aborts describing missing section | `TC-EP-INIT-004` |
| `rdetoolkit.cli.init` | Entry-point path missing on disk | Boundary on template existence | Command aborts with missing-path error | `TC-EP-INIT-005` |
| `rdetoolkit.cli.init` | Filesystem copy raises `PermissionError` | External dependency failure | Command aborts with generic failure guidance | `TC-EP-INIT-006` |

Boundary Value Table
| API | Boundary | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `rdetoolkit.cli.init` | `--template .` selects project pyproject | Directory lookup boundary | Local pyproject drives template application | `TC-BV-INIT-001` |
| `rdetoolkit.cli.init` | Missing template artifact | Path existence boundary | Command aborts before copying | `TC-BV-INIT-002` |
| `rdetoolkit.cli.init` | Copy operation failure | External dependency boundary | Error surfaced and init aborted | `TC-BV-INIT-003` |

Execution Commands
- Direct: `pytest -q tests/test_cli_init_templates.py --cov=rdetoolkit --cov-branch`
- Via tox: `tox -q`
"""

from __future__ import annotations

from pathlib import Path
import textwrap

from click.testing import CliRunner
import pytest

from rdetoolkit.cli import init


@pytest.fixture()
def cli_runner() -> CliRunner:
    """Provide a reusable CLI runner."""
    return CliRunner()


def _prepare_template_repo(repo_root: Path, *, modules_as_file: bool = False, tasksupport_is_file: bool = False) -> dict[str, Path]:
    """Create a sample template payload and return component paths."""
    payload_root = repo_root / "payload"
    payload_root.mkdir(parents=True, exist_ok=True)

    entry_template = payload_root / "custom_main.py"
    entry_template.write_text("print('template main')\n", encoding="utf-8")

    if modules_as_file:
        modules_template = payload_root / "single_module.py"
        modules_template.write_text("VALUE = 42\n", encoding="utf-8")
    else:
        modules_template = payload_root / "modules"
        modules_template.mkdir(parents=True, exist_ok=True)
        (modules_template / "__init__.py").write_text("INIT_FLAG = True\n", encoding="utf-8")
        (modules_template / "workflow.py").write_text("def run():\n    return 'ok'\n", encoding="utf-8")

    if tasksupport_is_file:
        tasksupport_template = payload_root / "tasksupport.json"
        tasksupport_template.write_text('{"schema": "custom"}\n', encoding="utf-8")
    else:
        tasksupport_template = payload_root / "tasksupport"
        tasksupport_template.mkdir(parents=True, exist_ok=True)
        (tasksupport_template / "custom.schema.json").write_text("{}", encoding="utf-8")

    inputdata_template = payload_root / "inputdata"
    inputdata_template.mkdir(parents=True, exist_ok=True)
    (inputdata_template / "README.txt").write_text("prepared payload\n", encoding="utf-8")

    return {
        "entry": entry_template,
        "modules": modules_template,
        "tasksupport": tasksupport_template,
        "inputdata": inputdata_template,
    }


def _write_pyproject(path: Path, *, entry: Path, modules: Path, tasksupport: Path, inputdata: Path) -> None:
    """Helper to write a pyproject template stanza with relative paths."""
    base_dir = path.parent.resolve()
    entry_rel = entry.resolve().relative_to(base_dir)
    modules_rel = modules.resolve().relative_to(base_dir)
    tasksupport_rel = tasksupport.resolve().relative_to(base_dir)
    inputdata_rel = inputdata.resolve().relative_to(base_dir)
    content = textwrap.dedent(
        f"""
        [tool.rdetoolkit.init]
        entry_point = "{entry_rel.as_posix()}"
        modules = "{modules_rel.as_posix()}"
        tasksupport = "{tasksupport_rel.as_posix()}"
        inputdata = "{inputdata_rel.as_posix()}"
        """
    ).strip()
    path.write_text(content + "\n", encoding="utf-8")


def test_init_templates_apply_pyproject__tc_ep_init_001(cli_runner: CliRunner) -> None:
    """TC-EP-INIT-001"""
    with cli_runner.isolated_filesystem():
        # Given: a template repo with absolute pyproject path
        repo_root = Path("template_repo")
        repo_root.mkdir()
        payload = _prepare_template_repo(repo_root)
        pyproject_path = repo_root / "pyproject.toml"
        _write_pyproject(pyproject_path, **payload)

        # When: running init with --template pointing to the pyproject file
        result = cli_runner.invoke(init, ["--template", str(pyproject_path)])

        # Then: the CLI succeeds and copies every template artifact
        assert result.exit_code == 0
        main_path = Path("container/main.py")
        assert main_path.read_text(encoding="utf-8") == "print('template main')\n"
        module_init = Path("container/modules/__init__.py")
        assert module_init.exists()
        assert "INIT_FLAG" in module_init.read_text(encoding="utf-8")
        template_schema = Path("container/data/tasksupport/custom.schema.json")
        assert template_schema.exists()
        mirrored_schema = Path("templates/tasksupport/custom.schema.json")
        assert mirrored_schema.exists()
        input_marker = Path("input/inputdata/README.txt")
        assert input_marker.read_text(encoding="utf-8").strip() == "prepared payload"


def test_init_templates_use_dot_option__tc_ep_init_002(cli_runner: CliRunner) -> None:
    """TC-EP-INIT-002 / TC-BV-INIT-001"""
    with cli_runner.isolated_filesystem():
        # Given: a local pyproject.toml with relative template paths and file-based modules
        repo_root = Path(".").resolve()
        payload = _prepare_template_repo(repo_root, modules_as_file=True, tasksupport_is_file=True)
        pyproject_path = Path("pyproject.toml")
        _write_pyproject(pyproject_path, **payload)

        # When: executing init with --template .
        result = cli_runner.invoke(init, ["--template", "."])

        # Then: entry file and single module file are copied, along with mirrored tasksupport and inputdata
        assert result.exit_code == 0
        assert Path("container/main.py").read_text(encoding="utf-8").startswith("print('template main')")
        single_module = Path("container/modules/single_module.py")
        assert single_module.exists()
        assert "VALUE = 42" in single_module.read_text(encoding="utf-8")
        tasksupport_file = Path("container/data/tasksupport/tasksupport.json")
        assert tasksupport_file.exists()
        assert Path("templates/tasksupport/tasksupport.json").exists()
        assert Path("input/inputdata/README.txt").exists()


def test_init_templates_reject_txt__tc_ep_init_003(cli_runner: CliRunner) -> None:
    """TC-EP-INIT-003"""
    with cli_runner.isolated_filesystem():
        # Given: an unsupported template file extension
        Path("template.txt").write_text("noop", encoding="utf-8")

        # When: running init with the unsupported file
        result = cli_runner.invoke(init, ["--template", "template.txt"])

        # Then: command aborts with an error explaining the supported files
        assert result.exit_code != 0
        assert "--template expects one of" in result.output


def test_init_templates_missing_section__tc_ep_init_004(cli_runner: CliRunner) -> None:
    """TC-EP-INIT-004"""
    with cli_runner.isolated_filesystem():
        # Given: a pyproject.toml without [tool.rdetoolkit.init]
        Path("pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")

        # When: executing init with the incomplete config
        result = cli_runner.invoke(init, ["--template", "pyproject.toml"])

        # Then: the CLI aborts reporting the missing section
        assert result.exit_code != 0
        assert "section was not found" in result.output


def test_init_templates_missing_entry__tc_ep_init_005(cli_runner: CliRunner) -> None:
    """TC-EP-INIT-005 / TC-BV-INIT-002"""
    with cli_runner.isolated_filesystem():
        # Given: pyproject referencing a non-existent entry_point file
        content = textwrap.dedent(
            """
            [tool.rdetoolkit.init]
            entry_point = "missing.py"
            modules = "."
            tasksupport = "."
            inputdata = "."
            """
        )
        Path("pyproject.toml").write_text(content, encoding="utf-8")

        # When: running the init command
        result = cli_runner.invoke(init, ["--template", "pyproject.toml"])

        # Then: an error about the missing entry point path is emitted
        assert result.exit_code != 0
        assert "Template path for 'entry_point' does not exist" in result.output


def test_init_templates_copy_failure__tc_ep_init_006(cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-EP-INIT-006 / TC-BV-INIT-003"""
    with cli_runner.isolated_filesystem():
        # Given: a template setup where modules copy will raise a PermissionError
        repo_root = Path("template_repo")
        repo_root.mkdir()
        payload = _prepare_template_repo(repo_root)
        pyproject_path = repo_root / "pyproject.toml"
        _write_pyproject(pyproject_path, **payload)

        def failing_copytree(src: Path, dst: Path, dirs_exist_ok: bool = False) -> None:
            raise PermissionError("permission denied")

        monkeypatch.setattr("rdetoolkit.cmd.command.shutil.copytree", failing_copytree)

        # When: running init so that modules copy triggers
        result = cli_runner.invoke(init, ["--template", str(pyproject_path)])

        # Then: the command aborts with the generic failure guidance
        assert result.exit_code != 0
        assert "Failed to create files required for structured RDE programs." in result.output
