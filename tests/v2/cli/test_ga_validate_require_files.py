"""GA #696: ``validate all --require-files`` fails when nothing was validated.

``validate all`` exits 0 when it finds no standard RDE file. That is right for
interactive discovery but lets CI report success after validating nothing
(wrong path, empty checkout). ``--require-files`` turns "nothing validated"
into a validation failure (exit 1, symbolic type ``no_target_files``) that
lists the searched locations. Without the flag the legacy behaviour is kept.

EP table:

| Partition | Flags | Format | Expected | Test ID |
|---|---|---|---|---|
| empty project dir | --require-files | text | exit 1, ``no_target_files``, searched paths | TC-696-EP-001 |
| empty project dir | --require-files | json | exit 1, JSON array entry ``no_target_files`` | TC-696-EP-002 |
| empty project dir | (none) | text/json | exit 0, legacy message | TC-696-EP-003 |
| empty project dir | --strict only | text | exit 0 (strict = warnings only) | TC-696-EP-003 |
| init project (valid) | --require-files [--strict] | text/json | exit 0 | TC-696-EP-004 |
| invalid invoice payload | --require-files | text/json | exit 1, real errors, no ``no_target_files`` | TC-696-EP-005 |
| v1 ``templates/`` layout, files present | --require-files | text | warning only, exit 0 / ``--strict`` exit 1 | TC-696-EP-006 |
| v1 ``templates/`` layout, no files | --require-files | json | exit 1, legacy dir in searched paths | TC-696-EP-007 |
| data-root layout (``data/tasksupport``) | --require-files | text | exit 1, remediation points to project root / doctor | TC-696-EP-008 |
| missing project dir | --require-files | text | usage error exit 2 naming the path | TC-696-EP-009 |
| relative ``.`` alias / default cwd | --require-files | text | same result as absolute path | TC-696-EP-010 |
| any of the above | --require-files | any | no file is created in the tree | TC-696-EP-011 |
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app

NO_TARGETS = "no_target_files"
SEARCHED = (
    "container/data/tasksupport/",
    "template/tasksupport/",
    "input/invoice/",
    "input/metadata/",
)


_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _invoke(*args: str):
    return CliRunner().invoke(app, ["validate", "all", *args])


def _snapshot(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def _dirs(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_dir())


def _init_project(root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(root)
    result = CliRunner().invoke(app, ["init"])
    assert result.exit_code == 0, result.output
    return root


def _no_target_entries(payload: list[dict]) -> list[dict]:
    return [error for entry in payload for error in entry["errors"] if error["type"] == NO_TARGETS]


class TestRequireFilesEmptyProject:
    """TC-696-EP-001..003: zero matches."""

    def test_text_require_files_exits_1_with_searched_paths__tc_696_ep_001(self, tmp_path: Path) -> None:
        # Given: an existing directory without any RDE file
        # When: validating with --require-files
        result = _invoke(str(tmp_path), "--require-files")
        # Then: it is a validation failure naming the symbolic type and searched paths
        assert result.exit_code == 1, result.output
        assert NO_TARGETS in result.output
        for searched in SEARCHED:
            assert searched in result.output
        assert "Remediation:" in result.output

    def test_text_require_files_with_strict_exits_1__tc_696_ep_001(self, tmp_path: Path) -> None:
        # Given/When: the recommended CI form on an empty directory
        result = _invoke(str(tmp_path), "--strict", "--require-files")
        # Then: it fails
        assert result.exit_code == 1, result.output
        assert NO_TARGETS in result.output

    def test_quiet_still_reports_no_targets__tc_696_ep_001(self, tmp_path: Path) -> None:
        # Given/When: --quiet suppresses warnings only
        result = _invoke(str(tmp_path), "--require-files", "--quiet")
        # Then: the error (not a warning) is still printed
        assert result.exit_code == 1, result.output
        assert NO_TARGETS in result.output

    def test_json_require_files_exits_1_with_stable_entry__tc_696_ep_002(self, tmp_path: Path) -> None:
        # Given: an empty directory
        # When: validating with JSON output
        result = _invoke(str(tmp_path), "--require-files", "--format", "json")
        # Then: stdout is one JSON array with a single invalid no-target entry
        assert result.exit_code == 1, result.output
        payload = json.loads(result.stdout)
        assert isinstance(payload, list)
        assert len(payload) == 1
        entry = payload[0]
        assert entry["valid"] is False
        assert entry["warnings"] == []
        errors = _no_target_entries(payload)
        assert len(errors) == 1
        assert errors[0]["field"] == ""
        for searched in SEARCHED:
            assert searched in errors[0]["message"]

    @pytest.mark.parametrize("extra", [[], ["--strict"], ["--format", "json"], ["--no-strict"]])
    def test_without_flag_keeps_exit_0__tc_696_ep_003(self, tmp_path: Path, extra: list[str]) -> None:
        # Given: an empty directory
        # When: validating without --require-files
        result = _invoke(str(tmp_path), *extra)
        # Then: the legacy discovery behaviour is unchanged
        assert result.exit_code == 0, result.output
        assert "No standard RDE files found in project directory." in result.output
        assert NO_TARGETS not in result.output

    @pytest.mark.parametrize("quiet", [False, True])
    def test_without_flag_quiet_controls_locations__tc_696_ep_003(self, tmp_path: Path, quiet: bool) -> None:
        # Given: an empty directory
        # When: validating without --require-files, with or without --quiet
        result = _invoke(str(tmp_path), *(["--quiet"] if quiet else []))
        # Then: the legacy expected-locations list is printed only without --quiet
        assert result.exit_code == 0, result.output
        assert ("Expected file locations:" in result.output) is not quiet


class TestRequireFilesWithFiles:
    """TC-696-EP-004..006: at least one recognized file."""

    @pytest.mark.parametrize("extra", [[], ["--strict"], ["--format", "json"]])
    def test_valid_init_project_passes__tc_696_ep_004(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        extra: list[str],
    ) -> None:
        # Given: a fresh init project
        root = _init_project(tmp_path / "project", monkeypatch)
        # When: validating with --require-files
        result = _invoke(str(root), "--require-files", *extra)
        # Then: it passes and reports no no-target error
        assert result.exit_code == 0, result.output
        assert NO_TARGETS not in result.output

    @pytest.mark.parametrize("output_format", ["text", "json"])
    def test_invalid_invoice_payload_fails__tc_696_ep_005(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        output_format: str,
    ) -> None:
        # Given: an init project whose invoice violates its schema
        root = _init_project(tmp_path / "project", monkeypatch)
        (root / "input" / "invoice" / "invoice.json").write_text(json.dumps({"basic": {}}), encoding="utf-8")
        # When: validating with --require-files
        result = _invoke(str(root), "--require-files", "--format", output_format)
        # Then: the real validation failure is reported (files were found)
        assert result.exit_code == 1, result.output
        assert NO_TARGETS not in result.output
        if output_format == "json":
            payload = json.loads(result.stdout)
            assert any(not entry["valid"] for entry in payload)

    def test_legacy_layout_warning_fails_only_with_strict__tc_696_ep_006(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Given: a v1 project (templates/ instead of template/) with schemas
        root = _init_project(tmp_path / "project", monkeypatch)
        (root / "template").rename(root / "templates")
        # When: validating with --require-files, with and without --strict
        lenient = _invoke(str(root), "--require-files")
        strict = _invoke(str(root), "--require-files", "--strict")
        # Then: files were validated, so only --strict turns the warning into a failure
        assert lenient.exit_code == 0, lenient.output
        assert strict.exit_code == 1, strict.output
        assert NO_TARGETS not in lenient.output + strict.output

    def test_legacy_empty_layout_counts_as_nothing_validated__tc_696_ep_007(self, tmp_path: Path) -> None:
        # Given: an empty v1 templates/tasksupport/ (a deprecation notice, but no file)
        (tmp_path / "templates" / "tasksupport").mkdir(parents=True)
        # When: validating with --require-files
        result = _invoke(str(tmp_path), "--require-files", "--format", "json")
        # Then: the deprecation notice is not counted as a validated file
        assert result.exit_code == 1, result.output
        payload = json.loads(result.stdout)
        errors = _no_target_entries(payload)
        assert len(errors) == 1
        assert "templates/tasksupport/" in errors[0]["message"]
        assert any(warning["type"] == "deprecated_layout" for entry in payload for warning in entry["warnings"])

    def test_legacy_empty_layout_without_flag_unchanged__tc_696_ep_007(self, tmp_path: Path) -> None:
        # Given: an empty v1 templates/tasksupport/
        (tmp_path / "templates" / "tasksupport").mkdir(parents=True)
        # When: validating without --require-files
        result = _invoke(str(tmp_path))
        # Then: the existing behaviour (notice, exit 0) is unchanged
        assert result.exit_code == 0, result.output
        assert NO_TARGETS not in result.output


class TestRequireFilesPathMessages:
    """TC-696-EP-008..011: layout variants, aliases, missing root, read-only."""

    def test_data_root_layout_is_actionable__tc_696_ep_008(self, tmp_path: Path) -> None:
        # Given: a Runner data root (data/tasksupport, data/invoice) instead of an init project
        data = tmp_path / "data"
        (data / "tasksupport").mkdir(parents=True)
        (data / "tasksupport" / "invoice.schema.json").write_text('{"properties": {}}', encoding="utf-8")
        (data / "invoice").mkdir()
        (data / "invoice" / "invoice.json").write_text("{}", encoding="utf-8")
        # When: validate all is pointed at the data root
        result = _invoke(str(data), "--require-files")
        # Then: it fails and tells the user where it looked and what to do
        assert result.exit_code == 1, result.output
        assert NO_TARGETS in result.output
        assert "rdetoolkit doctor" in result.output
        assert "rdetoolkit init" in result.output

    def test_missing_project_dir_is_usage_error__tc_696_ep_009(self, tmp_path: Path) -> None:
        # Given: a project directory that does not exist
        missing = tmp_path / "does-not-exist"
        # When: validating with --require-files
        result = _invoke(str(missing), "--require-files")
        # Then: it is a usage error naming the path (unchanged contract, exit 2)
        assert result.exit_code == 2, result.output
        # Rich wraps long paths inside its error box at any terminal width and
        # colours each wrapped line when it detects CI (GITHUB_ACTIONS), so compare
        # with ANSI escapes, box drawing and whitespace removed.
        plain = _ANSI_ESCAPE.sub("", result.output)
        flattened = "".join(ch for ch in plain if not ch.isspace() and ch not in "│╭╮╰╯─")
        assert "does-not-exist" in flattened
        assert not missing.exists()

    @pytest.mark.parametrize("form", ["dot", "default"])
    def test_relative_alias_matches_absolute__tc_696_ep_010(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        form: str,
    ) -> None:
        # Given: an empty directory as the current directory
        monkeypatch.chdir(tmp_path)
        args = ["."] if form == "dot" else []
        # When: validating via "." or the default project directory
        aliased = _invoke(*args, "--require-files", "--format", "json")
        absolute = _invoke(str(tmp_path), "--require-files", "--format", "json")
        # Then: both resolve to the same failure
        assert aliased.exit_code == absolute.exit_code == 1
        assert json.loads(aliased.stdout) == json.loads(absolute.stdout)

    @pytest.mark.parametrize("layout", ["empty", "data-root", "legacy-empty"])
    def test_require_files_creates_nothing__tc_696_ep_011(self, tmp_path: Path, layout: str) -> None:
        # Given: a tree in one of the failing layouts
        if layout == "data-root":
            (tmp_path / "data" / "tasksupport").mkdir(parents=True)
        elif layout == "legacy-empty":
            (tmp_path / "templates" / "tasksupport").mkdir(parents=True)
        files_before, dirs_before = _snapshot(tmp_path), _dirs(tmp_path)
        # When: validating with --require-files in both formats
        for output_format in ("text", "json"):
            _invoke(str(tmp_path), "--require-files", "--format", output_format)
        # Then: no file or directory was created or changed
        assert _snapshot(tmp_path) == files_before
        assert _dirs(tmp_path) == dirs_before


def test_help_documents_require_files() -> None:
    """The option is listed in ``validate all --help``."""
    # Given/When: the help text is rendered
    result = CliRunner().invoke(app, ["validate", "all", "--help"])
    # Then: the flag is documented
    assert result.exit_code == 0
    assert "--require-files" in result.output
