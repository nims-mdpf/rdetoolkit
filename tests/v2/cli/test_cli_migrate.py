"""Tests for ``rdetoolkit migrate check`` (Session E2, TC-CLI-MIGRATE-*).

Written before implementation (TDD Red phase). Target: make all tests pass
in codex-worker Green phase. Authority: local/develop/v2/tasks/session_e2.md
Conflict #4 (three AST detector categories, bounded "old handler class"
heuristic), Conflict #5 (usage-error vs diagnostic-outcome distinction),
Known Trap 4.

Binding API-shape pin: ``rdetoolkit migrate check <path>`` is a subcommand
of the ``migrate`` typer group (Design §10: ``migrate check [path] / apply
[path]`` -- this session implements ``check`` only, never ``apply``, Phase
F/R7). ``path`` may be a single ``.py`` file or a directory (recursively
scanned for ``*.py``). Exit codes: **always 0** for a successful scan
regardless of findings count (this is a diagnostic tool, not a failure
signal) -- a nonexistent ``path`` argument is the only usage error (exit 3,
Conflict #5). Never 1 or 2.

This file's documented resolution for TC-CLI-MIGRATE-BV-002 (a single-file
target with a Python syntax error): exit **0**, with the file reported as
unparseable in the output -- Conflict #5's usage-error/diagnostic-outcome
split reserves exit 3 for CLI-argument problems (a nonexistent path), not
for the *content* of an existing, readable file being invalid Python; a
syntax error is exactly the kind of "diagnostic outcome" the whole command
exists to report without failing.

All fixture ``.py`` files are written directly under ``tmp_path`` (never
imported as real modules -- ``migrate check`` only needs to AST-parse them,
it never executes them).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def _write(path: Path, source: str) -> Path:
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    return path


class TestMigrateCheckCustomDatasetFunction:
    """TC-CLI-MIGRATE-EP-001: custom_dataset_function keyword usage
    (detector category 1)."""

    def test_detects_custom_dataset_function_keyword__tc_cli_migrate_ep_001(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        fixture = _write(
            tmp_path / "legacy_entry.py",
            """
            from rdetoolkit import workflows


            def my_dataset_function(srcpaths, resource_paths):
                pass


            def main():
                workflows.run(custom_dataset_function=my_dataset_function)
            """,
        )

        result = cli_runner.invoke(app, ["migrate", "check", str(fixture)])

        assert result.exit_code == 0
        assert "custom_dataset_function" in result.output
        assert fixture.name in result.output


class TestMigrateCheckRdeOutputResourcePath:
    """TC-CLI-MIGRATE-EP-002: direct RdeOutputResourcePath reference
    (detector category 2)."""

    def test_detects_direct_rde_output_resource_path_reference__tc_cli_migrate_ep_002(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        fixture = _write(
            tmp_path / "legacy_types.py",
            """
            from rdetoolkit.models.rde2types import RdeOutputResourcePath


            def handler(srcpaths, resource_paths: RdeOutputResourcePath) -> None:
                pass
            """,
        )

        result = cli_runner.invoke(app, ["migrate", "check", str(fixture)])

        assert result.exit_code == 0
        assert "RdeOutputResourcePath" in result.output
        assert fixture.name in result.output


class TestMigrateCheckOldHandlerClass:
    """TC-CLI-MIGRATE-EP-003: the best-effort "old handler class" structural
    heuristic (detector category 3, Conflict #4)."""

    def test_detects_old_handler_class_heuristic__tc_cli_migrate_ep_003(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        fixture = _write(
            tmp_path / "legacy_handler.py",
            """
            class LegacyHandler:
                def process(self, srcpaths, resource_paths):
                    pass
            """,
        )

        result = cli_runner.invoke(app, ["migrate", "check", str(fixture)])

        assert result.exit_code == 0
        assert "LegacyHandler" in result.output


class TestMigrateCheckCleanFile:
    """TC-CLI-MIGRATE-EP-004: a file with zero v1 patterns still exits 0
    (explicitly confirming "always 0", not just "0 when something is
    found")."""

    def test_clean_file_exits_0_with_no_findings__tc_cli_migrate_ep_004(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        fixture = _write(
            tmp_path / "clean_v2_flow.py",
            """
            from rdetoolkit.core.flow import flow
            from rdetoolkit.core.node import node
            from rdetoolkit.types import InputPaths


            @node
            def do_something(paths: InputPaths) -> None:
                return None


            @flow
            def pipeline(paths: InputPaths) -> None:
                do_something(paths)
            """,
        )

        result = cli_runner.invoke(app, ["migrate", "check", str(fixture)])

        assert result.exit_code == 0


class TestMigrateCheckDirectoryRecursion:
    """TC-CLI-MIGRATE-EP-005: a directory target recursively scans .py
    files and aggregates findings across files."""

    def test_directory_target_recursively_aggregates_findings__tc_cli_migrate_ep_005(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        project_dir = tmp_path / "legacy_project"
        nested_dir = project_dir / "nested"
        nested_dir.mkdir(parents=True)
        _write(
            project_dir / "clean.py",
            """
            def add(a: int, b: int) -> int:
                return a + b
            """,
        )
        flagged = _write(
            nested_dir / "legacy_entry.py",
            """
            from rdetoolkit import workflows


            def my_dataset_function(srcpaths, resource_paths):
                pass


            def main():
                workflows.run(custom_dataset_function=my_dataset_function)
            """,
        )

        result = cli_runner.invoke(app, ["migrate", "check", str(project_dir)])

        assert result.exit_code == 0
        assert flagged.name in result.output
        assert "custom_dataset_function" in result.output


class TestMigrateCheckUsageErrors:
    """TC-CLI-MIGRATE-BV-001: a nonexistent path argument is a usage error
    (exit 3), distinct from a diagnostic outcome (Conflict #5)."""

    def test_nonexistent_path_exits_3__tc_cli_migrate_bv_001(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        result = cli_runner.invoke(app, ["migrate", "check", str(tmp_path / "does_not_exist")])

        assert result.exit_code == 3


class TestMigrateCheckSyntaxError:
    """TC-CLI-MIGRATE-BV-002: a syntax-error .py file does not crash the
    scan -- reported as unparseable, exit 0 (this file's documented
    resolution, see module docstring)."""

    def test_syntax_error_file_reported_unparseable_exits_0__tc_cli_migrate_bv_002(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        fixture = _write(
            tmp_path / "broken.py",
            """
            def broken(:
                pass
            """,
        )

        result = cli_runner.invoke(app, ["migrate", "check", str(fixture)])

        assert result.exit_code == 0
        combined = result.output.lower()
        assert fixture.name.lower() in combined
        assert any(marker in combined for marker in ("unparseable", "syntax", "parse error", "could not parse"))


class TestMigrateCheckNeverPartialOrFailedExitCode:
    """TC-CLI-MIGRATE-EP-006 (Conflict #5 negative guard)."""

    def test_migrate_check_never_exits_1_or_2__tc_cli_migrate_ep_006(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        flagged = _write(
            tmp_path / "flagged.py",
            """
            from rdetoolkit import workflows


            def my_dataset_function(srcpaths, resource_paths):
                pass


            def main():
                workflows.run(custom_dataset_function=my_dataset_function)
            """,
        )
        clean = _write(tmp_path / "clean.py", "def add(a: int, b: int) -> int:\n    return a + b\n")
        broken = _write(tmp_path / "broken2.py", "def broken(:\n    pass\n")

        invocations = [
            ["migrate", "check", str(flagged)],
            ["migrate", "check", str(clean)],
            ["migrate", "check", str(broken)],
            ["migrate", "check", str(tmp_path)],
            ["migrate", "check", str(tmp_path / "nope")],
        ]

        for args in invocations:
            result = cli_runner.invoke(app, args)
            assert result.exit_code not in (1, 2), f"{args} exited {result.exit_code}, forbidden by Conflict #5"
