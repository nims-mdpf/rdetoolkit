"""Cross-command CLI exit-code contract test (Session E2.6, TC-CLI-EXIT-*).

Written before implementation (TDD Red phase). Target: make all tests pass
in codex-worker Green phase. Authority: local/develop/v2/tasks/session_e2.md
Conflict #5 (the core rule this file exists to pin), Design.md v2.1 §9.3.

This file pins, in one place, the full v2 CLI exit-code contract across
every v2 subcommand family:

- ``run --flow``: 0 = RunReport.status == "success"; 1 = "failed";
  2 = "partial"; 3 = usage error (E1 regression pin, re-asserted here).
- ``nodes lint``: 0 = zero violations; 3 = one or more violations
  (E1 regression pin, re-asserted here).
- ``graph`` / ``report show`` / ``repro export`` / ``repro import`` /
  ``migrate check``: **0 or 3 only** -- 1 and 2 are reserved exclusively for
  ``run --flow``'s ``RunReport.status`` mapping (Conflict #5, the new
  negative guard TC-CLI-EXIT-003 exists to add).

Per Design §9.3, these CLI exit codes are an **independent contract** from
``job.failed``'s int catalog error codes (see
``TestExitCodesIndependentFromJobFailedCatalog`` below) -- a CLI exit code
of 1 does not correspond to any particular int code, and an int code (e.g.
3001) is never itself used as a process exit status.

Reuses Session E1's ``tests/v2/cli/fixtures/run_flows.py`` (read-only,
unmodified). All fixture-building helpers are duplicated inline per this
test suite's established self-containment convention (see
``tests/v2/cli/test_cli_run.py``'s module docstring).
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from rdetoolkit.cli.app import app

FIXTURE_MODULE = "tests.v2.cli.fixtures.run_flows"

_SEED_INVOICE_JSON: dict = {
    "datasetId": "seed-dataset",
    "basic": {
        "dateSubmitted": "2026-07-12",
        "dataOwnerId": "0" * 56,
        "dataName": "seed",
    },
}


def _build_data_fixture(root: Path, *, input_files: dict[str, str] | None = None) -> None:
    inputdata = root / "data" / "inputdata"
    inputdata.mkdir(parents=True)
    resolved_input_files = {"test_single.txt": "dummy"} if input_files is None else input_files
    for name, content in resolved_input_files.items():
        (inputdata / name).write_text(content, encoding="utf-8")
    (root / "data" / "invoice").mkdir(parents=True)
    (root / "data" / "invoice" / "invoice.json").write_text(json.dumps(_SEED_INVOICE_JSON), encoding="utf-8")
    (root / "data" / "tasksupport").mkdir(parents=True)
    (root / "data" / "tasksupport" / "invoice.schema.json").write_text(json.dumps({"properties": {}}), encoding="utf-8")
    (root / "data" / "tasksupport" / "metadata-def.json").write_text(
        json.dumps({"constant": {}, "variable": []}),
        encoding="utf-8",
    )
    (root / "data" / "temp").mkdir(parents=True)


def _write_rdeconfig(root: Path, data: dict) -> None:
    (root / "rdeconfig.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def isolated_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestRunFlowExitCodeRegressionPin:
    """TC-CLI-EXIT-001: run --flow's 0/1/2/3 mapping (E1 regression pin)."""

    def test_success_exits_0__tc_cli_exit_001_success(self, cli_runner: CliRunner, isolated_root: Path) -> None:
        _build_data_fixture(isolated_root)
        result = cli_runner.invoke(app, ["run", "--flow", f"{FIXTURE_MODULE}:success_pipeline"])
        assert result.exit_code == 0

    def test_failed_exits_1__tc_cli_exit_001_failed(self, cli_runner: CliRunner, isolated_root: Path) -> None:
        _build_data_fixture(isolated_root)
        result = cli_runner.invoke(app, ["run", "--flow", f"{FIXTURE_MODULE}:failing_pipeline"])
        assert result.exit_code == 1

    def test_partial_exits_2__tc_cli_exit_001_partial(self, cli_runner: CliRunner, isolated_root: Path) -> None:
        _build_data_fixture(isolated_root, input_files={"a.txt": "a", "b.txt": "b"})
        _write_rdeconfig(isolated_root, {"system": {"extended_mode": "MultiDataTile"}})
        result = cli_runner.invoke(app, ["run", "--flow", f"{FIXTURE_MODULE}:second_tile_fails_pipeline"])
        assert result.exit_code == 2

    def test_usage_error_exits_3__tc_cli_exit_001_usage_error(self, cli_runner: CliRunner, isolated_root: Path) -> None:
        result = cli_runner.invoke(app, ["run", "--flow", "tests.v2.cli.fixtures.totally_nonexistent_module:pipeline"])
        assert result.exit_code == 3


def _run_isolated_lint(register_snippet: str) -> subprocess.CompletedProcess[str]:
    """Subprocess-isolated ``nodes lint`` invocation (duplicated from
    ``test_cli_nodes.py``'s identically-purposed helper -- the shared
    module-level registry persists for the whole pytest process, so a
    zero-violation assertion is only meaningful in a fresh interpreter)."""
    script = textwrap.dedent(
        f"""
        import sys
        from rdetoolkit.core.node import node
        from rdetoolkit.core.flow import flow
        from rdetoolkit.types import InputPaths
        {textwrap.indent(textwrap.dedent(register_snippet), "        ")}
        from rdetoolkit.cli.app import app
        from typer.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(app, ["nodes", "lint"])
        sys.stdout.write(result.output)
        sys.exit(result.exit_code)
        """,
    )
    return subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60, check=False)


class TestNodesLintExitCodeRegressionPin:
    """TC-CLI-EXIT-002: nodes lint's 0/3 mapping (E1 regression pin)."""

    def test_clean_registry_exits_0__tc_cli_exit_002_clean(self) -> None:
        register_snippet = """
            @node(id="isolated_exitcodes_clean_node")
            def clean_node(paths: InputPaths) -> None:
                return None
        """

        proc = _run_isolated_lint(register_snippet)

        assert proc.returncode == 0, proc.stdout + proc.stderr

    def test_violating_registry_exits_3__tc_cli_exit_002_violation(self, cli_runner: CliRunner) -> None:
        from rdetoolkit.core.node import node
        from rdetoolkit.types import InputPaths

        @node
        def _exit_codes_violation_node(x) -> None:  # noqa: ANN001
            return None

        result = cli_runner.invoke(app, ["nodes", "lint"])

        assert result.exit_code == 3


class TestReportingCommandsExitCodeContract:
    """TC-CLI-EXIT-003: graph/report show/repro export/repro import/migrate
    check exit only 0 or 3 -- never 1 or 2 (Conflict #5's core negative
    guard, the reason this test file exists)."""

    def _real_report_path(self, cli_runner: CliRunner, root: Path) -> Path:
        _build_data_fixture(root)
        result = cli_runner.invoke(app, ["run", "--flow", f"{FIXTURE_MODULE}:success_pipeline"])
        assert result.exit_code == 0
        report_data = json.loads(result.output)
        return root / "data" / "logs" / f"run_report_{report_data['run_id']}.json"

    def test_graph_success_and_usage_error_stay_in_0_or_3__tc_cli_exit_003_graph(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        report_path = self._real_report_path(cli_runner, isolated_root)

        success = cli_runner.invoke(app, ["graph", str(report_path)])
        usage_error = cli_runner.invoke(app, ["graph", str(isolated_root / "nope.json")])

        assert success.exit_code == 0
        assert usage_error.exit_code == 3

    def test_report_show_success_and_usage_error_stay_in_0_or_3__tc_cli_exit_003_report(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        report_path = self._real_report_path(cli_runner, isolated_root)

        success = cli_runner.invoke(app, ["report", "show", str(report_path)])
        usage_error = cli_runner.invoke(app, ["report", "show", str(isolated_root / "nope.json")])

        assert success.exit_code == 0
        assert usage_error.exit_code == 3

    def test_repro_export_success_and_usage_error_stay_in_0_or_3__tc_cli_exit_003_repro_export(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
        tmp_path: Path,
    ) -> None:
        report_path = self._real_report_path(cli_runner, isolated_root)
        archive_path = tmp_path / "exit_codes_export.zip"

        success = cli_runner.invoke(app, ["repro", "export", str(report_path), "--output", str(archive_path)])
        usage_error = cli_runner.invoke(
            app,
            ["repro", "export", str(isolated_root / "nope.json"), "--output", str(tmp_path / "nope.zip")],
        )

        assert success.exit_code == 0
        assert usage_error.exit_code == 3

    def test_repro_import_success_and_usage_error_stay_in_0_or_3__tc_cli_exit_003_repro_import(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
        tmp_path: Path,
    ) -> None:
        report_path = self._real_report_path(cli_runner, isolated_root)
        archive_path = tmp_path / "exit_codes_import.zip"
        export_result = cli_runner.invoke(app, ["repro", "export", str(report_path), "--output", str(archive_path)])
        assert export_result.exit_code == 0

        success = cli_runner.invoke(app, ["repro", "import", str(archive_path), str(tmp_path / "exit_codes_target")])
        usage_error = cli_runner.invoke(
            app,
            ["repro", "import", str(tmp_path / "does_not_exist.zip"), str(tmp_path / "exit_codes_target_2")],
        )

        assert success.exit_code == 0
        assert usage_error.exit_code == 3

    def test_migrate_check_success_and_usage_error_stay_in_0_or_3__tc_cli_exit_003_migrate(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        clean_fixture = tmp_path / "clean_exit_codes.py"
        clean_fixture.write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")

        success = cli_runner.invoke(app, ["migrate", "check", str(clean_fixture)])
        usage_error = cli_runner.invoke(app, ["migrate", "check", str(tmp_path / "does_not_exist")])

        assert success.exit_code == 0
        assert usage_error.exit_code == 3


class TestExitCodesIndependentFromJobFailedCatalog:
    """TC-CLI-EXIT-004: documents (Design §9.3's explicit requirement) that
    v2 CLI exit codes (0/1/2/3) are an independent contract from
    job.failed's int catalog error codes (e.g. 3001, 3004, ...) -- a CLI
    exit code is never itself an int catalog code, and vice versa. This is
    intentionally a documentation-only assertion (no runtime behavior to
    exercise beyond the fact that exit codes stay within {0, 1, 2, 3}
    everywhere else in this file), per the TDD-ENFORCER TEST MANIFEST's own
    "pick the lighter-weight option" instruction.
    """

    def test_exit_code_contract_is_independent_of_job_failed_int_catalog__tc_cli_exit_004(self) -> None:
        """CLI process exit codes (0/1/2/3, Design §9.3) and job.failed's
        ErrorCode= int catalog values (e.g. 3001 InternalInvariantViolation-
        family codes, see rdetoolkit.errors.ERROR_CATALOG) are two
        independent contracts: a failed run's job.failed file carries a
        4-digit int catalog code, while the CLI process that triggered it
        exits with the small, fixed value 1 -- the two numbers are never
        the same value by contract, and no code in this session maps one to
        the other.
        """
