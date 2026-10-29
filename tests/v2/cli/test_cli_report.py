"""Tests for ``rdetoolkit report show`` (Session E2, TC-CLI-REPORT-*).

Written before implementation (TDD Red phase). Target: make all tests pass
in codex-worker Green phase. Authority: local/develop/v2/tasks/session_e2.md
Conflicts #5/#7, Known Traps 5/8.

Binding API-shape pin: ``rdetoolkit report show <run_report.json>`` is a
subcommand of the ``report`` typer group (Design §10: ``report show
<run_report.json>``). Exit 0 on a successful *display* regardless of the
underlying run's ``status`` (Conflict #5 -- ``report show`` on a
``status="failed"`` run is still a successful display, never exit 1); exit 3
on a missing/malformed path. ``schema_version`` != the current known value
("2") is a WARNING, not a failure -- the command still displays as much as
it can and exits 0.

Reuses Session E1's ``tests/v2/cli/fixtures/run_flows.py`` (read-only,
unmodified) via real ``run --flow`` invocations to produce genuine
``RunReport`` files on disk (golden principle) for the success/failed
display cases. Only the malformed-JSON and unknown-schema_version cases are
hand-written, since those test rejection/tolerance of invalid or unexpected
input by construction.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
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

_VALID_REPORT_TEMPLATE: dict = {
    "schema_version": "2",
    "run_id": "report-show-fixture-run",
    "status": "success",
    "flow_id": "pkg.mod:pipeline",
    "mode": "invoice",
    "started_at": "2026-01-01T00:00:00Z",
    "duration_ms": 12.3,
    "config_digest": "sha256:abcdef",
    "iterations": [{"index": 0, "datatile_id": "0", "status": "success", "node_calls": [], "error": None}],
    "warnings": [],
    "error": None,
}


def _build_data_fixture(root: Path) -> None:
    # Idempotent (exist_ok=True): helpers may build the same root twice in one test.
    inputdata = root / "data" / "inputdata"
    inputdata.mkdir(parents=True, exist_ok=True)
    (inputdata / "test_single.txt").write_text("dummy", encoding="utf-8")
    (root / "data" / "invoice").mkdir(parents=True, exist_ok=True)
    (root / "data" / "invoice" / "invoice.json").write_text(json.dumps(_SEED_INVOICE_JSON), encoding="utf-8")
    (root / "data" / "tasksupport").mkdir(parents=True, exist_ok=True)
    (root / "data" / "tasksupport" / "invoice.schema.json").write_text(json.dumps({"properties": {}}), encoding="utf-8")
    (root / "data" / "tasksupport" / "metadata-def.json").write_text(
        json.dumps({"constant": {}, "variable": []}),
        encoding="utf-8",
    )
    (root / "data" / "temp").mkdir(parents=True, exist_ok=True)


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def isolated_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _run_flow_and_get_report_path(cli_runner: CliRunner, root: Path, flow_name: str) -> tuple[Path, int]:
    _build_data_fixture(root)
    result = cli_runner.invoke(app, ["run", "--flow", f"{FIXTURE_MODULE}:{flow_name}"])
    # E1's run --flow echoes the RunReport JSON first; failing runs may append
    # diagnostic lines after it — parse only the leading JSON document.
    report_data, _ = json.JSONDecoder().raw_decode(result.output.lstrip())
    report_path = root / "data" / "logs" / f"run_report_{report_data['run_id']}.json"
    return report_path, result.exit_code


class TestReportShowSuccess:
    """TC-CLI-REPORT-EP-001/003: a success-status report displays cleanly
    with no schema warning."""

    def test_success_report_shows_status_run_id_and_iterations__tc_cli_report_ep_001(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        report_path, run_exit = _run_flow_and_get_report_path(cli_runner, isolated_root, "success_pipeline")
        assert run_exit == 0

        result = cli_runner.invoke(app, ["report", "show", str(report_path)])

        assert result.exit_code == 0
        report_data = json.loads(report_path.read_text(encoding="utf-8"))
        assert report_data["run_id"] in result.output
        assert "success" in result.output.lower()

    def test_known_schema_version_emits_no_warning__tc_cli_report_ep_003(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        report_path, run_exit = _run_flow_and_get_report_path(cli_runner, isolated_root, "success_pipeline")
        assert run_exit == 0

        result = cli_runner.invoke(app, ["report", "show", str(report_path)])

        assert result.exit_code == 0
        assert "warn" not in result.output.lower()


class TestReportShowFailed:
    """TC-CLI-REPORT-EP-002: a failed-status report still displays
    successfully (exit 0, Conflict #5), showing the failing call_id and
    error info."""

    def test_failed_report_exits_0_and_shows_failing_call_id_and_error__tc_cli_report_ep_002(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        report_path, run_exit = _run_flow_and_get_report_path(cli_runner, isolated_root, "failing_pipeline")
        assert run_exit == 1, "sanity check: the fixture flow itself must fail"

        report_data = json.loads(report_path.read_text(encoding="utf-8"))
        assert report_data["status"] == "failed"
        failing_call_ids = [
            call["call_id"]
            for iteration in report_data["iterations"]
            for call in iteration.get("node_calls", [])
            if call["status"] == "failed"
        ]

        result = cli_runner.invoke(app, ["report", "show", str(report_path)])

        assert result.exit_code == 0, "report show succeeds at displaying even a failed run (Conflict #5)"
        assert "failed" in result.output.lower()
        if failing_call_ids:
            assert failing_call_ids[0] in result.output


class TestReportShowUnknownSchemaVersion:
    """TC-CLI-REPORT-EP-004: an unrecognized schema_version warns but still
    displays and exits 0."""

    def test_unknown_schema_version_warns_but_still_displays__tc_cli_report_ep_004(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        report = {**_VALID_REPORT_TEMPLATE, "schema_version": "99"}
        report_path = isolated_root / "unknown_schema_report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")

        result = cli_runner.invoke(app, ["report", "show", str(report_path)])

        assert result.exit_code == 0
        combined = result.output.lower()
        assert "warn" in combined
        assert report["run_id"] in result.output


class TestReportShowUsageErrors:
    """TC-CLI-REPORT-BV-001/002: bad path / malformed JSON."""

    def test_nonexistent_path_exits_3__tc_cli_report_bv_001(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        result = cli_runner.invoke(app, ["report", "show", str(isolated_root / "does_not_exist.json")])

        assert result.exit_code == 3

    def test_malformed_json_missing_required_fields_exits_3__tc_cli_report_bv_002(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        bad_report = isolated_root / "bad_report.json"
        bad_report.write_text(json.dumps({"schema_version": "1"}), encoding="utf-8")

        result = cli_runner.invoke(app, ["report", "show", str(bad_report)])

        assert result.exit_code == 3


class TestReportShowNeverPartialOrFailedExitCode:
    """TC-CLI-REPORT-EP-005 (Conflict #5 negative guard)."""

    def test_report_show_never_exits_1_or_2__tc_cli_report_ep_005(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        success_path, _ = _run_flow_and_get_report_path(cli_runner, isolated_root, "success_pipeline")
        failed_path, _ = _run_flow_and_get_report_path(cli_runner, isolated_root, "failing_pipeline")
        bad_report = isolated_root / "bad_report.json"
        bad_report.write_text(json.dumps({"schema_version": "1"}), encoding="utf-8")

        invocations = [
            ["report", "show", str(success_path)],
            ["report", "show", str(failed_path)],
            ["report", "show", str(isolated_root / "does_not_exist.json")],
            ["report", "show", str(bad_report)],
        ]

        for args in invocations:
            result = cli_runner.invoke(app, args)
            assert result.exit_code not in (1, 2), f"{args} exited {result.exit_code}, forbidden by Conflict #5"
