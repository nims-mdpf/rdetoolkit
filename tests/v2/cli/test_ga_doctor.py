"""GA #697: gap closure for ``rdetoolkit doctor`` (shipped in #743 / #668).

Doctor already covers inputs, config, mode, invoice/schema/metadata
definitions, the Runner validate-only preflight and ``--ref`` flow checks
(``tests/v2/cli/test_cli_doctor.py`` D01-D20). #697 adds what was missing:

- ``--strict``: warnings fail (exit 1), as in ``validate all --strict``;
- a "no target files" policy consistent with ``validate all --require-files``:
  required targets (``inputdata/``, invoice, schema) always fail when absent,
  and an ``inputdata/`` without any file is the warning ``NoInputFiles``
  (fatal under ``--strict``);
- an explicit static-only statement: JSON ``flow_executed: false`` and a text
  line saying the flow was not executed;
- ``--module NAME`` (repeatable): imports the module and folds the existing
  ``nodes lint`` findings into the report (check ``nodes.lint``).

EP table:

| ID | Partition | Expected |
|---|---|---|
| G01 | clean project, text / json | exit 0, static statement, ``flow_executed`` false |
| G02 | clean project + ``--ref`` | statement still present, flow not executed |
| G03 | warning only (no metadata-def), with / without ``--strict`` | exit 0 / exit 1 |
| G04 | clean project + ``--strict`` | exit 0 |
| G05 | ``inputdata/`` empty or only empty sub-directories | ``NoInputFiles`` warning, exit 0 / strict 1 |
| G06 | ``inputdata/`` with a nested file | no ``NoInputFiles`` |
| G07 | required target missing | error exit 1 even without ``--strict`` |
| G08 | invalid ``execution.type_check`` / unknown config key | 1002, exit 1 |
| G09 | ``--module`` with duplicate node id | 2001 in ``nodes.lint``, exit 1 |
| G10 | ``--module`` with missing annotation | ``MissingTypeAnnotation``, exit 1, text output safe |
| G11 | ``--module`` import failure | ``ModuleImportFailed``, exit 1 (not 3) |
| G12 | ``--module`` clean | ``nodes.lint`` passed, exit 0 |
| G13 | no ``--module`` / ``--ref`` | user module never imported |
| G14 | ``--module`` + ``--strict`` | project tree byte-identical, no bytecode |
| G15 | invalid ``--format`` / unknown option | exit 3 / click usage 2 |
| G16 | existing commands | ``validate all``, ``nodes lint``, ``run --validate-only`` still available |
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli import nodes_cmd
from rdetoolkit.cli.app import app

runner = CliRunner()
STATIC_NOTE = "the flow was not executed"


def _project(root: Path) -> Path:
    data = root / "data"
    for name in ("inputdata", "invoice", "tasksupport"):
        (data / name).mkdir(parents=True, exist_ok=True)
    (data / "inputdata" / "sample.txt").write_text("sample", encoding="utf-8")
    (data / "invoice" / "invoice.json").write_text(json.dumps({
        "datasetId": "dataset", "basic": {
            "dateSubmitted": "2026-11-12", "dataOwnerId": "0" * 56, "dataName": "example",
        },
    }), encoding="utf-8")
    (data / "tasksupport" / "invoice.schema.json").write_text('{"properties": {}}', encoding="utf-8")
    (data / "tasksupport" / "metadata-def.json").write_text("{}", encoding="utf-8")
    return data


def _json(root: Path, *args: str):
    return runner.invoke(app, ["doctor", str(root), "--format", "json", *args])


def _snapshot(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def _names(payload: dict) -> list[str]:
    return [item["name"] for item in payload["diagnostics"]]


@pytest.fixture
def scoped_lint(monkeypatch: pytest.MonkeyPatch):
    """Limit the lint registries to nodes defined by this test's modules.

    The registry is process-global, so nodes registered by other tests would
    otherwise appear as findings here.
    """
    from rdetoolkit.templates import registry as templates

    prefixes: list[str] = []
    original_nodes = nodes_cmd.registry.list_nodes
    monkeypatch.setattr(
        nodes_cmd.registry,
        "list_nodes",
        lambda: tuple(spec for spec in original_nodes() if spec.source_location.split(":")[0] in prefixes),
    )
    monkeypatch.setattr(nodes_cmd.registry, "list_flows", lambda: ())
    monkeypatch.setattr(nodes_cmd.registry, "find_unstable_node_ids", lambda: ())
    monkeypatch.setattr(templates, "list_concrete_templates", lambda: ())
    return prefixes


def _module(root: Path, name: str, body: str, prefixes: list[str] | None = None) -> str:
    (root / f"{name}.py").write_text(body, encoding="utf-8")
    if prefixes is not None:
        prefixes.append(name)
    return name


class TestStaticStatement:
    """G01/G02: doctor never claims the flow passes."""

    def test_json_states_flow_not_executed__g01(self, tmp_path: Path) -> None:
        # Given: a clean project
        _project(tmp_path)
        # When: doctor runs with JSON output
        result = _json(tmp_path)
        # Then: it passes and states the flow was not executed
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["flow_executed"] is False
        assert payload["strict"] is False
        assert payload["status"] == "passed"

    def test_text_states_static_checks_only__g01(self, tmp_path: Path) -> None:
        # Given: a clean project
        _project(tmp_path)
        # When: doctor runs with text output
        result = runner.invoke(app, ["doctor", str(tmp_path)])
        # Then: the summary line is followed by the static-only statement
        assert result.exit_code == 0, result.output
        assert STATIC_NOTE in result.stdout
        assert "static" in result.stdout.lower()
        assert "all processing passes" not in result.stdout.lower()

    def test_ref_still_not_executed__g02(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Given: a clean project and a flow whose body leaves a sentinel
        _project(tmp_path)
        sentinel = tmp_path / "executed"
        _module(tmp_path, "ga697_ref_flow", f"from pathlib import Path\ndef main(): Path({str(sentinel)!r}).write_text('x')\n")
        monkeypatch.syspath_prepend(str(tmp_path))
        # When: doctor checks the flow in both formats
        as_json = _json(tmp_path, "--ref", "ga697_ref_flow:main")
        as_text = runner.invoke(app, ["doctor", str(tmp_path), "--ref", "ga697_ref_flow:main"])
        # Then: the statement holds and the body never ran
        assert json.loads(as_json.stdout)["flow_executed"] is False
        assert STATIC_NOTE in as_text.stdout
        assert not sentinel.exists()


class TestStrict:
    """G03/G04: --strict makes warnings fatal."""

    def test_warning_exit_0_without_strict_and_1_with__g03(self, tmp_path: Path) -> None:
        # Given: a project whose only finding is a warning (no metadata-def.json)
        data = _project(tmp_path)
        (data / "tasksupport" / "metadata-def.json").unlink()
        # When: doctor runs with and without --strict
        lenient = _json(tmp_path)
        strict = _json(tmp_path, "--strict")
        # Then: only --strict fails; the envelope status is the same warning
        assert lenient.exit_code == 0, lenient.output
        assert strict.exit_code == 1, strict.output
        assert json.loads(lenient.stdout)["status"] == json.loads(strict.stdout)["status"] == "warning"
        assert json.loads(strict.stdout)["strict"] is True

    def test_strict_text_warning_exits_1__g03(self, tmp_path: Path) -> None:
        # Given: a warning-only project
        data = _project(tmp_path)
        (data / "tasksupport" / "metadata-def.json").unlink()
        # When: doctor runs in text mode with --strict
        result = runner.invoke(app, ["doctor", str(tmp_path), "--strict"])
        # Then: it fails
        assert result.exit_code == 1, result.output
        assert "MetadataDefinitionMissing" in result.stdout or "metadata.definition.exists" in result.stdout

    def test_clean_project_strict_exits_0__g04(self, tmp_path: Path) -> None:
        # Given/When: a clean project under --strict
        _project(tmp_path)
        result = _json(tmp_path, "--strict")
        # Then: it passes
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["status"] == "passed"


class TestNoTargetFiles:
    """G05..G07: the no-target-files policy."""

    @pytest.mark.parametrize("nested_dir", [False, True])
    def test_empty_inputdata_is_warning__g05(self, tmp_path: Path, nested_dir: bool) -> None:
        # Given: inputdata/ without any file (optionally with an empty sub-directory)
        data = _project(tmp_path)
        (data / "inputdata" / "sample.txt").unlink()
        if nested_dir:
            (data / "inputdata" / "empty").mkdir()
        # When: doctor runs with and without --strict
        lenient = _json(tmp_path)
        strict = _json(tmp_path, "--strict")
        # Then: a NoInputFiles warning is reported; only --strict fails
        payload = json.loads(lenient.stdout)
        finding = next(item for item in payload["diagnostics"] if item["name"] == "NoInputFiles")
        assert finding["severity"] == "warning"
        assert finding["code"] is None
        assert finding["check_id"] == "inputs.files"
        assert finding["location"] == {"path": "data/inputdata"}
        assert lenient.exit_code == 0, lenient.output
        assert strict.exit_code == 1, strict.output

    def test_nested_input_file_counts__g06(self, tmp_path: Path) -> None:
        # Given: the only input file sits in a sub-directory
        data = _project(tmp_path)
        (data / "inputdata" / "sample.txt").unlink()
        (data / "inputdata" / "sub").mkdir()
        (data / "inputdata" / "sub" / "x.txt").write_text("x", encoding="utf-8")
        # When: doctor runs
        result = _json(tmp_path, "--strict")
        # Then: there is no NoInputFiles warning
        payload = json.loads(result.stdout)
        assert "NoInputFiles" not in _names(payload)
        assert {"check_id": "inputs.files", "status": "passed", "path": "data/inputdata"} in payload["checks"]

    @pytest.mark.parametrize("relative", ["inputdata", "invoice/invoice.json", "tasksupport/invoice.schema.json"])
    def test_missing_required_target_fails_without_strict__g07(self, tmp_path: Path, relative: str) -> None:
        # Given: a required target is absent
        import shutil

        data = _project(tmp_path)
        target = data / relative
        shutil.rmtree(target) if target.is_dir() else target.unlink()
        # When: doctor runs without --strict
        result = _json(tmp_path)
        # Then: it fails (required targets never degrade to a warning)
        assert result.exit_code == 1, result.output
        assert "NoInputFiles" not in _names(json.loads(result.stdout))


class TestConfigFindings:
    """G08: config problems are attributed to config.effective with 1002."""

    @pytest.mark.parametrize("config", ["execution:\n  type_check: strcit\n", "unknown_key: 1\n"])
    def test_invalid_config_is_1002__g08(self, tmp_path: Path, config: str) -> None:
        # Given: a project whose rdeconfig.yaml is invalid
        _project(tmp_path)
        (tmp_path / "rdeconfig.yaml").write_text(config, encoding="utf-8")
        # When: doctor runs
        result = _json(tmp_path)
        # Then: the config finding carries 1002 and the file is not echoed
        assert result.exit_code == 1, result.output
        payload = json.loads(result.stdout)
        finding = next(item for item in payload["diagnostics"] if item["check_id"] == "config.effective")
        assert finding["code"] == 1002
        assert "strcit" not in result.stdout


class TestModuleLint:
    """G09..G13: --module folds nodes lint findings into doctor."""

    def test_duplicate_node_id_is_2001__g09(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scoped_lint: list[str],
    ) -> None:
        # Given: a module registering one node id twice
        _project(tmp_path)
        name = _module(
            tmp_path, "ga697_duplicate_nodes",
            "from rdetoolkit import node\n"
            "@node(id='ga697_dup')\ndef a(x: int) -> int: return x\n"
            "@node(id='ga697_dup')\ndef b(x: int) -> int: return x\n",
            scoped_lint,
        )
        monkeypatch.chdir(tmp_path)
        # When: doctor imports it with --module
        result = _json(tmp_path, "--module", name)
        # Then: the registry error is a nodes.lint finding with code 2001
        assert result.exit_code == 1, result.output
        payload = json.loads(result.stdout)
        finding = next(item for item in payload["diagnostics"] if item["check_id"] == "nodes.lint")
        assert finding["code"] == 2001
        assert finding["severity"] == "error"
        assert {"check_id": "nodes.lint", "status": "error"} in payload["checks"]

    @pytest.mark.parametrize("output_format", ["json", "text"])
    def test_missing_annotation_is_reported__g10(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scoped_lint: list[str], output_format: str,
    ) -> None:
        # Given: a module whose node lacks a parameter annotation
        _project(tmp_path)
        name = _module(
            tmp_path, f"ga697_unannotated_{output_format}",
            f"from rdetoolkit import node\n@node(id='ga697_unannotated_{output_format}')\ndef a(x): return x\n",
            scoped_lint,
        )
        monkeypatch.chdir(tmp_path)
        # When: doctor lints it
        result = runner.invoke(app, ["doctor", str(tmp_path), "--format", output_format, "--module", name])
        # Then: the lint finding is reported (text output does not need a file path)
        assert result.exit_code == 1, result.output
        assert "MissingTypeAnnotation" in result.stdout or "nodes.lint" in result.stdout
        if output_format == "json":
            assert "MissingTypeAnnotation" in _names(json.loads(result.stdout))

    def test_module_import_failure_is_finding__g11(self, tmp_path: Path, scoped_lint: list[str]) -> None:
        # Given: a module name that cannot be imported
        _project(tmp_path)
        # When: doctor is asked to lint it
        result = _json(tmp_path, "--module", "ga697_no_such_module")
        # Then: it is a doctor violation (exit 1), not a usage error
        assert result.exit_code == 1, result.output
        assert "ModuleImportFailed" in _names(json.loads(result.stdout))

    def test_clean_module_passes__g12(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scoped_lint: list[str],
    ) -> None:
        # Given: a module with one annotated node
        _project(tmp_path)
        name = _module(
            tmp_path, "ga697_clean_nodes",
            "from rdetoolkit import node\n@node(id='ga697_clean')\ndef a(x: int) -> int: return x\n",
            scoped_lint,
        )
        monkeypatch.chdir(tmp_path)
        # When: doctor lints it
        result = _json(tmp_path, "--module", name)
        # Then: the lint check passed
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert {"check_id": "nodes.lint", "status": "passed"} in payload["checks"]

    def test_module_not_imported_without_option__g13(self, tmp_path: Path) -> None:
        # Given: a project-local module with an import-time side effect
        _project(tmp_path)
        sentinel = tmp_path / "imported"
        _module(tmp_path, "ga697_side_effect", f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('x')\n")
        # When: doctor runs without --module / --ref
        result = _json(tmp_path)
        # Then: the module was never imported and no lint check ran
        assert result.exit_code == 0, result.output
        assert not sentinel.exists()
        assert "ga697_side_effect" not in sys.modules
        assert all(check["check_id"] != "nodes.lint" for check in json.loads(result.stdout)["checks"])

    def test_module_and_strict_keep_project_unchanged__g14(
        self, tmp_path: Path, scoped_lint: list[str],
    ) -> None:
        # Given: a project with a clean module next to it
        _project(tmp_path)
        name = _module(
            tmp_path, "ga697_readonly_nodes",
            "from rdetoolkit import node\n@node(id='ga697_readonly')\ndef a(x: int) -> int: return x\n",
            scoped_lint,
        )
        before = _snapshot(tmp_path)
        # When: doctor runs with --module and --strict in both formats
        _json(tmp_path, "--module", name, "--strict")
        runner.invoke(app, ["doctor", str(tmp_path), "--module", name, "--strict"])
        # Then: nothing was written, not even bytecode
        assert _snapshot(tmp_path) == before
        assert not (tmp_path / "__pycache__").exists()


class TestUsageAndCompatibility:
    """G15/G16: exit conventions and existing commands."""

    def test_invalid_format_exits_3__g15(self, tmp_path: Path) -> None:
        # Given/When: an unsupported format
        _project(tmp_path)
        result = runner.invoke(app, ["doctor", str(tmp_path), "--format", "yaml", "--strict"])
        # Then: usage error 3
        assert result.exit_code == 3

    def test_unknown_option_is_click_usage__g15(self, tmp_path: Path) -> None:
        # Given/When: an option doctor does not have
        result = runner.invoke(app, ["doctor", str(tmp_path), "--flow", "x:y"])
        # Then: click usage error 2 (the shipped option is --ref; no alias is added)
        assert result.exit_code == 2

    def test_help_lists_new_options__g15(self) -> None:
        # Given/When: doctor help
        result = runner.invoke(app, ["doctor", "--help"])
        # Then: --strict and --module are documented next to --ref
        assert result.exit_code == 0
        for option in ("--strict", "--module", "--ref"):
            assert option in result.output

    @pytest.mark.parametrize(
        "args,option",
        [
            (["validate", "all", "--help"], "--strict"),
            (["nodes", "lint", "--help"], "--module"),
            (["run", "--help"], "--validate-only"),
        ],
    )
    def test_existing_commands_unchanged__g16(self, args: list[str], option: str) -> None:
        # Given/When: the help of each pre-existing check command
        result = runner.invoke(app, args)
        # Then: it is still available with its option
        assert result.exit_code == 0
        assert option in result.output
