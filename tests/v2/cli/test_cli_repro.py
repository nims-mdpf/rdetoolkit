"""Tests for ``rdetoolkit repro export``/``repro import`` (Session E2,
TC-CLI-REPRO-*).

Written before implementation (TDD Red phase). Target: make all tests pass
in codex-worker Green phase. Authority: local/develop/v2/tasks/session_e2.md
Conflicts #3/#5/#6, Known Traps 2/3/5.

Binding API-shape pin: ``rdetoolkit repro export <run_report.json> --output
<archive path>`` and ``rdetoolkit repro import <archive> <target dir>`` are
subcommands of the ``repro`` typer group (Design §10). ``--output`` is
always passed explicitly by this file's tests (its default-naming
convention, if any, is Codex's implementation choice per Conflict #6 and is
therefore not asserted here). Source data directory derivation (Conflict
#3): ``Path(run_report).resolve().parent.parent`` must contain
``inputdata/``, ``invoice/``, ``tasksupport/`` -- missing any is a usage
error (exit 3). Archive format is stdlib ``zipfile`` (Conflict #6, verified
independently by ``session_e2.md``'s own negative-guard grep, not re-checked
here). Exit codes: 0 = success: 3 = usage error (missing source dirs,
corrupt/missing archive, conflicting import target); never 1 or 2
(Conflict #5).

Reuses Session E1's ``tests/v2/cli/fixtures/run_flows.py`` (read-only,
unmodified) via a real ``run --flow`` invocation to produce a genuine
on-disk ``RunReport`` + sibling ``data/{inputdata,invoice,tasksupport}``
tree (golden principle) for the export source. The round-trip test
(TC-CLI-REPRO-EP-003) additionally creates an empty ``data/temp`` scratch
directory in the reconstructed target before re-running --  ``data/temp``
is ``workflows.run(flow=...)``'s hardcoded unpacked-dir scratch space (Known
Trap 3, session_e1.md), not a genuine input artifact, so recreating it as an
empty directory before re-running is ordinary environment preparation, not
a weakening of the round-trip acceptance criterion (which concerns
``inputdata``/``invoice``/``tasksupport``/config/call-log reproduction, per
Conflict #6).

Review EP/BV table:
    TC-E-REVIEW-F4-001 | empty required root | ZIP round trip | root recreated
    TC-E-REVIEW-F4-002 | empty nested directory | ZIP round trip | child recreated
"""

from __future__ import annotations

import json
import os
import zipfile
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
    "schema_version": "1",
    "run_id": "repro-orphan-fixture-run",
    "status": "success",
    "flow_id": "pkg.mod:pipeline",
    "mode": "invoice",
    "started_at": "2026-01-01T00:00:00Z",
    "duration_ms": 12.3,
    "config_digest": "sha256:abcdef",
    "iterations": [],
    "warnings": [],
    "error": None,
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


def _collect_data_paths(root: Path, *, exclude_dirnames: tuple[str, ...] = ("logs", "temp")) -> set[str]:
    """Collect ``data/**`` relative file paths, excluding run-specific
    scratch/log content (``logs/`` carries a run_id-named report + iteration
    detail files that legitimately differ between two separate runs;
    ``temp/`` is scratch space, not a reproducible artifact)."""
    data_root = root / "data"
    if not data_root.is_dir():
        return set()
    paths: set[str] = set()
    for path in data_root.rglob("*"):
        if path.is_dir():
            continue
        relative = path.relative_to(data_root)
        if relative.parts and relative.parts[0] in exclude_dirnames:
            continue
        paths.add(relative.as_posix())
    return paths


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def isolated_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _run_success_flow_and_get_report_path(cli_runner: CliRunner, root: Path) -> Path:
    _build_data_fixture(root)
    result = cli_runner.invoke(app, ["run", "--flow", f"{FIXTURE_MODULE}:success_pipeline"])
    assert result.exit_code == 0, f"fixture flow run must succeed: {result.output}"
    report_data = json.loads(result.output)
    return root / "data" / "logs" / f"run_report_{report_data['run_id']}.json"


class TestReproExport:
    """TC-CLI-REPRO-EP-001: export against a real run's report + sibling
    data/ tree produces an archive."""

    def test_export_produces_an_archive_file__tc_cli_repro_ep_001(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
        tmp_path: Path,
    ) -> None:
        report_path = _run_success_flow_and_get_report_path(cli_runner, isolated_root)
        archive_path = tmp_path / "export.zip"

        result = cli_runner.invoke(app, ["repro", "export", str(report_path), "--output", str(archive_path)])

        assert result.exit_code == 0
        assert archive_path.is_file()
        assert zipfile.is_zipfile(archive_path)


class TestReproImport:
    """TC-CLI-REPRO-EP-002: import into a fresh target directory
    reconstructs data/{inputdata,invoice,tasksupport} matching the
    originally-exported content."""

    def test_import_reconstructs_matching_data_tree__tc_cli_repro_ep_002(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
        tmp_path: Path,
    ) -> None:
        report_path = _run_success_flow_and_get_report_path(cli_runner, isolated_root)
        archive_path = tmp_path / "export.zip"
        export_result = cli_runner.invoke(app, ["repro", "export", str(report_path), "--output", str(archive_path)])
        assert export_result.exit_code == 0

        target_dir = tmp_path / "import_target"
        result = cli_runner.invoke(app, ["repro", "import", str(archive_path), str(target_dir)])

        assert result.exit_code == 0
        assert (target_dir / "data" / "inputdata" / "test_single.txt").read_text(encoding="utf-8") == "dummy"
        imported_invoice = json.loads((target_dir / "data" / "invoice" / "invoice.json").read_text(encoding="utf-8"))
        assert imported_invoice == _SEED_INVOICE_JSON
        assert (target_dir / "data" / "tasksupport" / "invoice.schema.json").is_file()
        assert (target_dir / "data" / "tasksupport" / "metadata-def.json").is_file()

    def test_import_recreates_empty_required_and_nested_directories__tc_e_review_f4_001_002(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """TC-E-REVIEW-F4-001/002: archive directory entries preserve empty trees."""
        # Given: valid run inputs with an empty required root and empty nested directory
        root = tmp_path / "empty_source"
        logs = root / "data" / "logs"
        logs.mkdir(parents=True)
        report_path = logs / "run_report_empty.json"
        report_path.write_text(json.dumps(_VALID_REPORT_TEMPLATE), encoding="utf-8")
        (root / "data" / "inputdata").mkdir()
        (root / "data" / "invoice" / "empty-child").mkdir(parents=True)
        (root / "data" / "tasksupport").mkdir()
        archive_path = tmp_path / "empty.zip"

        # When: the inputs are exported and imported into a fresh target
        export_result = cli_runner.invoke(
            app,
            ["repro", "export", str(report_path), "--output", str(archive_path)],
        )
        target = tmp_path / "empty_target"
        import_result = cli_runner.invoke(app, ["repro", "import", str(archive_path), str(target)])

        # Then: both the empty required roots and empty descendant survive
        assert export_result.exit_code == 0, export_result.output
        assert import_result.exit_code == 0, import_result.output
        assert (target / "data" / "inputdata").is_dir()
        assert (target / "data" / "tasksupport").is_dir()
        assert (target / "data" / "invoice" / "empty-child").is_dir()


class TestReproRoundTrip:
    """TC-CLI-REPRO-EP-003 (E2.4 acceptance criterion): export -> import ->
    run --flow from the reconstructed directory reproduces an identical
    output directory tree to the original run's (excluding run-specific
    logs/ and scratch temp/, per this file's module docstring)."""

    def test_export_import_run_round_trip_reproduces_identical_tree__tc_cli_repro_ep_003(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
        tmp_path: Path,
    ) -> None:
        report_path = _run_success_flow_and_get_report_path(cli_runner, isolated_root)
        original_paths = _collect_data_paths(isolated_root)
        assert original_paths, "sanity check: the original run must have produced at least one data/ artifact"

        archive_path = tmp_path / "roundtrip.zip"
        export_result = cli_runner.invoke(app, ["repro", "export", str(report_path), "--output", str(archive_path)])
        assert export_result.exit_code == 0

        target_dir = tmp_path / "roundtrip_target"
        import_result = cli_runner.invoke(app, ["repro", "import", str(archive_path), str(target_dir)])
        assert import_result.exit_code == 0

        (target_dir / "data" / "temp").mkdir(parents=True, exist_ok=True)

        previous_cwd = Path.cwd()
        os.chdir(target_dir)
        try:
            rerun_result = cli_runner.invoke(app, ["run", "--flow", f"{FIXTURE_MODULE}:success_pipeline"])
        finally:
            os.chdir(previous_cwd)

        assert rerun_result.exit_code == 0, f"reconstructed environment must support a successful re-run: {rerun_result.output}"
        reconstructed_paths = _collect_data_paths(target_dir)
        assert reconstructed_paths == original_paths


class TestReproExportUsageErrors:
    """TC-CLI-REPRO-BV-001: missing sibling data/{inputdata,invoice,
    tasksupport} directories is a usage error naming the missing directory."""

    def test_export_missing_sibling_dirs_exits_3_names_missing_dir__tc_cli_repro_bv_001(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        orphan_root = tmp_path / "orphan"
        logs_dir = orphan_root / "data" / "logs"
        logs_dir.mkdir(parents=True)
        report_path = logs_dir / "run_report_orphan.json"
        report_path.write_text(json.dumps({**_VALID_REPORT_TEMPLATE, "run_id": "orphan"}), encoding="utf-8")
        archive_path = tmp_path / "orphan_export.zip"

        result = cli_runner.invoke(app, ["repro", "export", str(report_path), "--output", str(archive_path)])

        assert result.exit_code == 3
        combined = (result.output or "") + str(result.exception or "")
        assert any(name in combined.lower() for name in ("inputdata", "invoice", "tasksupport"))


class TestReproImportUsageErrors:
    """TC-CLI-REPRO-BV-002/003: corrupt/missing archive, conflicting import
    target."""

    def test_import_target_is_existing_file_exits_3__tc_pr513_c2(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """PR #513 Copilot C2: an existing-file target must be a usage error
        (exit 3), never an unhandled NotADirectoryError (exit 1)."""
        archive_path = tmp_path / "any.zip"
        archive_path.write_bytes(b"placeholder")
        file_target = tmp_path / "target_file.txt"
        file_target.write_text("occupied", encoding="utf-8")

        result = cli_runner.invoke(
            app,
            ["repro", "import", str(archive_path), str(file_target)],
        )

        assert result.exit_code == 3

    def test_import_nonexistent_archive_exits_3__tc_cli_repro_bv_002_missing(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        result = cli_runner.invoke(
            app,
            ["repro", "import", str(tmp_path / "does_not_exist.zip"), str(tmp_path / "target")],
        )

        assert result.exit_code == 3

    def test_import_corrupt_non_zip_archive_exits_3__tc_cli_repro_bv_002_corrupt(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        corrupt_archive = tmp_path / "corrupt.zip"
        corrupt_archive.write_text("this is not a zip file", encoding="utf-8")

        result = cli_runner.invoke(app, ["repro", "import", str(corrupt_archive), str(tmp_path / "target")])

        assert result.exit_code == 3

    def test_import_into_conflicting_target_exits_3__tc_cli_repro_bv_003(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
        tmp_path: Path,
    ) -> None:
        report_path = _run_success_flow_and_get_report_path(cli_runner, isolated_root)
        archive_path = tmp_path / "export.zip"
        export_result = cli_runner.invoke(app, ["repro", "export", str(report_path), "--output", str(archive_path)])
        assert export_result.exit_code == 0

        conflicting_target = tmp_path / "conflicting_target"
        (conflicting_target / "data" / "inputdata").mkdir(parents=True)
        (conflicting_target / "data" / "inputdata" / "preexisting.txt").write_text("pre-existing", encoding="utf-8")

        result = cli_runner.invoke(app, ["repro", "import", str(archive_path), str(conflicting_target)])

        assert result.exit_code == 3


class TestReproNeverPartialOrFailedExitCode:
    """TC-CLI-REPRO-EP-004 (Conflict #5 negative guard)."""

    def test_repro_never_exits_1_or_2__tc_cli_repro_ep_004(
        self,
        cli_runner: CliRunner,
        isolated_root: Path,
        tmp_path: Path,
    ) -> None:
        report_path = _run_success_flow_and_get_report_path(cli_runner, isolated_root)
        archive_path = tmp_path / "export.zip"
        corrupt_archive = tmp_path / "corrupt.zip"
        corrupt_archive.write_text("not a zip", encoding="utf-8")

        invocations = [
            ["repro", "export", str(report_path), "--output", str(archive_path)],
            ["repro", "export", str(tmp_path / "nope.json"), "--output", str(tmp_path / "nope.zip")],
            ["repro", "import", str(corrupt_archive), str(tmp_path / "target_neg")],
        ]

        for args in invocations:
            result = cli_runner.invoke(app, args)
            assert result.exit_code not in (1, 2), f"{args} exited {result.exit_code}, forbidden by Conflict #5"
