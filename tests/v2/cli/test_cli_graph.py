"""Tests for ``rdetoolkit graph`` (Session E2, TC-CLI-GRAPH-*).

Written before implementation (TDD Red phase). Target: make all tests pass
in codex-worker Green phase. Authority: local/develop/v2/tasks/session_e2.md
Conflicts #1/#2/#5, Known Traps 1/6/7.

Binding API-shape pin: ``rdetoolkit graph <run_report.json> [--format
mermaid|html|json]`` is a **bare top-level command** (no subcommand verb,
per Design §10's CLI tree: ``graph <run_report.json> [--format ...]`` has no
sibling verb, unlike ``report show``/``repro export``/``migrate check``).
Default ``--format`` is ``"json"`` (this file's documented choice, per
TC-CLI-GRAPH-EP-004). Exit codes: 0 = rendered successfully; 3 = missing/
malformed ``run_report.json`` path or an unrecognized ``--format`` value.
1 and 2 are never produced (Conflict #5).

Reuses Session E1's ``tests/v2/cli/fixtures/run_flows.py`` (read-only,
unmodified) and its ``_build_data_fixture``/``FIXTURE_MODULE`` conventions
(duplicated inline here per this test suite's established
"no cross-file test helper imports" self-containment rule -- see
``tests/v2/cli/test_cli_run.py``'s and ``tests/v2/e2e/test_run_flow.py``'s
module docstrings) to produce a REAL ``RunReport`` on disk at
``data/logs/run_report_<run_id>.json`` via an actual ``rdetoolkit run
--flow`` invocation -- never a hand-written report file for the success
paths (golden principle). Only the BV-002 malformed-JSON case is
hand-written, since it is testing rejection of invalid input by
construction.
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


def _build_data_fixture(root: Path) -> None:
    inputdata = root / "data" / "inputdata"
    inputdata.mkdir(parents=True)
    (inputdata / "test_single.txt").write_text("dummy", encoding="utf-8")
    (root / "data" / "invoice").mkdir(parents=True)
    (root / "data" / "invoice" / "invoice.json").write_text(json.dumps(_SEED_INVOICE_JSON), encoding="utf-8")
    (root / "data" / "tasksupport").mkdir(parents=True)
    (root / "data" / "tasksupport" / "invoice.schema.json").write_text(json.dumps({"properties": {}}), encoding="utf-8")
    (root / "data" / "tasksupport" / "metadata-def.json").write_text(
        json.dumps({"constant": {}, "variable": []}),
        encoding="utf-8",
    )
    (root / "data" / "temp").mkdir(parents=True)


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def isolated_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _run_success_flow_and_get_report_path(cli_runner: CliRunner, root: Path) -> Path:
    """Execute a real ``run --flow`` invocation and return the path finalize.py
    writes it to (``data/logs/run_report_<run_id>.json``, per
    ``runner/finalize.py::_write_run_report``)."""
    _build_data_fixture(root)
    result = cli_runner.invoke(app, ["run", "--flow", f"{FIXTURE_MODULE}:success_pipeline"])
    assert result.exit_code == 0, f"fixture flow run must succeed: {result.output}"
    report_data = json.loads(result.output)
    return root / "data" / "logs" / f"run_report_{report_data['run_id']}.json"


class TestGraphFormats:
    """TC-CLI-GRAPH-EP-001..004: each supported --format renders 0, plus the
    default-format case."""

    def test_format_json_exits_0_with_call_sequence_json__tc_cli_graph_ep_001(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        report_path = _run_success_flow_and_get_report_path(cli_runner, isolated_root)

        result = cli_runner.invoke(app, ["graph", str(report_path), "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "Call Sequence" in data["title"]

    def test_format_mermaid_exits_0_with_call_sequence_block__tc_cli_graph_ep_002(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        report_path = _run_success_flow_and_get_report_path(cli_runner, isolated_root)

        result = cli_runner.invoke(app, ["graph", str(report_path), "--format", "mermaid"])

        assert result.exit_code == 0
        assert "Call Sequence" in result.output
        assert "flowchart" in result.output or "sequenceDiagram" in result.output

    def test_format_html_exits_0_self_contained__tc_cli_graph_ep_003(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        report_path = _run_success_flow_and_get_report_path(cli_runner, isolated_root)

        result = cli_runner.invoke(app, ["graph", str(report_path), "--format", "html"])

        assert result.exit_code == 0
        assert "Call Sequence" in result.output
        lowered = result.output.lower()
        assert 'src="http' not in lowered
        assert 'href="http' not in lowered

    def test_no_format_defaults_to_json__tc_cli_graph_ep_004(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        report_path = _run_success_flow_and_get_report_path(cli_runner, isolated_root)

        result = cli_runner.invoke(app, ["graph", str(report_path)])

        assert result.exit_code == 0
        data = json.loads(result.output)  # default format is documented as "json"
        assert "Call Sequence" in data["title"]


class TestGraphUsageErrors:
    """TC-CLI-GRAPH-BV-001..003: bad path / malformed JSON / bad --format."""

    def test_nonexistent_path_exits_3__tc_cli_graph_bv_001(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        result = cli_runner.invoke(app, ["graph", str(isolated_root / "does_not_exist.json")])

        assert result.exit_code == 3

    def test_malformed_run_report_json_exits_3__tc_cli_graph_bv_002(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        bad_report = isolated_root / "bad_report.json"
        bad_report.write_text(json.dumps({"not": "a valid run report"}), encoding="utf-8")

        result = cli_runner.invoke(app, ["graph", str(bad_report)])

        assert result.exit_code == 3

    def test_unrecognized_format_exits_3__tc_cli_graph_bv_003(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        report_path = _run_success_flow_and_get_report_path(cli_runner, isolated_root)

        result = cli_runner.invoke(app, ["graph", str(report_path), "--format", "svg"])

        assert result.exit_code == 3


class TestGraphNeverPartialOrFailedExitCode:
    """TC-CLI-GRAPH-EP-005 (Conflict #5 negative guard): graph never exits 1
    or 2, regardless of input."""

    def test_graph_never_exits_1_or_2__tc_cli_graph_ep_005(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
    ) -> None:
        report_path = _run_success_flow_and_get_report_path(cli_runner, isolated_root)
        bad_report = isolated_root / "bad_report.json"
        bad_report.write_text(json.dumps({"not": "a valid run report"}), encoding="utf-8")

        invocations = [
            ["graph", str(report_path), "--format", "json"],
            ["graph", str(report_path), "--format", "mermaid"],
            ["graph", str(report_path), "--format", "html"],
            ["graph", str(isolated_root / "does_not_exist.json")],
            ["graph", str(bad_report)],
            ["graph", str(report_path), "--format", "svg"],
        ]

        for args in invocations:
            result = cli_runner.invoke(app, args)
            assert result.exit_code not in (1, 2), f"{args} exited {result.exit_code}, forbidden by Conflict #5"
