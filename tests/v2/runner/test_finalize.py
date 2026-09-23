"""Tests for rdetoolkit v2 runner finalize (TC-FIN-001..007).

Written before implementation (TDD Red phase).
Target: make all tests pass in codex-worker Green phase.

Design authority: local/develop/v2/Design.md §6.3 (job.failed), §13.1, §13.3
Session authority: local/develop/v2/tasks/session_b2.md (B2.4/B2.5/B2.6)

Contract exercised here:
    finalize(report: RunReport, config: RdeConfig, *, data_root: Path) -> None
      - status == "failed"  -> calls rdetoolkit.errors.write_job_errorlog_file
                                with an int ERROR_CATALOG code and a message;
                                v1 owns the "ErrorCode=/ErrorMessage=" format.
      - status in {"success", "partial"} -> job.failed is NOT written.
      - Regardless of status, RunReport is persisted as JSON below
        ``data_root/logs/run_report_{run_id}.json``. The data root is decided
        once by the Runner (Session I-REVIEW-A ruling #1); finalize never
        re-resolves one of its own.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| Runner.finalize | root differs from cwd | report is written below root | TC-H0-ROOT-EP-001 |
| finalize | the Runner-resolved data root | report is written below ``data_root/logs`` | TC-EP-HR2-B-001 |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| Runner.finalize | one successful report | exactly one root-relative report | TC-H0-ROOT-BV-001 |
| Runner.finalize | one failed report and root != cwd | job.failed is written below root | TC-HR-F1-BV-001 |
| finalize | flat root | no nested ``root/data/logs`` is created | TC-BV-HR2-B-001 |

``write_job_errorlog_file`` itself is v1 public surface and MUST NOT be
reimplemented by finalize.py; finalize.py only calls it.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rdetoolkit.errors import ERROR_CATALOG
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.types import RdeConfig

# Target import — fails until implementation exists (expected in Red phase):
from rdetoolkit.runner.finalize import finalize

_NODE_EXECUTION_FAILED_CODE = 3001  # ERROR_CATALOG[3001].name == "NodeExecutionFailed"


def _make_report(status: str, *, error: dict[str, object] | None = None, run_id: str = "run-0001") -> RunReport:
    return RunReport(
        run_id=run_id,
        status=status,
        flow_id="tests.v2.runner.test_finalize.stub_flow",
        mode="invoice",
        started_at="2026-07-06T00:00:00",
        duration_ms=1.0,
        config_digest="sha256:deadbeef",
        iterations=[],
        warnings=[],
        error=error,
    )


@pytest.fixture()
def _cwd_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Chdir into a fresh tmp_path with a pre-created ``data/`` directory.

    ``write_job_errorlog_file`` resolves its target via
    ``StorageDir.get_datadir(False)``, which is always cwd-relative "data" and
    does not create the directory itself.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    return tmp_path / "data"


class TestFinalizeWritesJobFailedOnFailure:
    """TC-FIN-001: status=failed writes job.failed."""

    def test_failed_status_writes_job_failed(self, _cwd_data_dir: Path) -> None:
        """job.failed must exist under data/ after finalize() on a failed report."""
        report = _make_report("failed", error={"code": _NODE_EXECUTION_FAILED_CODE, "message": "boom"})

        finalize(report, RdeConfig(), data_root=_cwd_data_dir)

        assert (_cwd_data_dir / "job.failed").exists()


class TestFinalizeSkipsJobFailedOnSuccessOrPartial:
    """TC-FIN-002 / TC-FIN-003: success/partial must not write job.failed."""

    def test_success_status_does_not_write_job_failed(self, _cwd_data_dir: Path) -> None:
        """job.failed must be absent after finalize() on a successful report."""
        report = _make_report("success")

        finalize(report, RdeConfig(), data_root=_cwd_data_dir)

        assert not (_cwd_data_dir / "job.failed").exists()

    def test_partial_status_does_not_write_job_failed(self, _cwd_data_dir: Path) -> None:
        """job.failed must be absent after finalize() on a partial report."""
        report = _make_report("partial")

        finalize(report, RdeConfig(), data_root=_cwd_data_dir)

        assert not (_cwd_data_dir / "job.failed").exists()


class TestFinalizeJobFailedFormat:
    """TC-FIN-004 / TC-FIN-005: job.failed content matches the v1 format with an int code."""

    def test_job_failed_content_matches_v1_format_with_int_code(self, _cwd_data_dir: Path) -> None:
        """Content must be exactly 'ErrorCode=<int>\\nErrorMessage=<msg>\\n'."""
        report = _make_report(
            "failed",
            error={"code": _NODE_EXECUTION_FAILED_CODE, "message": "node execution failed for call c-1"},
        )

        finalize(report, RdeConfig(), data_root=_cwd_data_dir)

        content = (_cwd_data_dir / "job.failed").read_text(encoding="utf_8")
        assert content == f"ErrorCode={_NODE_EXECUTION_FAILED_CODE}\nErrorMessage=node execution failed for call c-1\n"
        # The code line must carry an int literal, never a catalog string name.
        code_line = content.splitlines()[0]
        assert code_line == f"ErrorCode={_NODE_EXECUTION_FAILED_CODE}"
        assert ERROR_CATALOG[_NODE_EXECUTION_FAILED_CODE].name not in code_line


class TestFinalizeSingleResponsibility:
    """TC-FIN-006: finalize is the sole, exactly-once caller of write_job_errorlog_file."""

    def test_finalize_calls_write_job_errorlog_file_exactly_once(
        self, _cwd_data_dir: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """finalize must delegate to write_job_errorlog_file exactly once, with the int code."""
        mock_write = MagicMock()
        monkeypatch.setattr("rdetoolkit.runner.finalize.write_job_errorlog_file", mock_write)
        report = _make_report("failed", error={"code": _NODE_EXECUTION_FAILED_CODE, "message": "boom"})

        finalize(report, RdeConfig(), data_root=_cwd_data_dir)

        mock_write.assert_called_once_with(
            _NODE_EXECUTION_FAILED_CODE,
            "boom",
            filename=str((_cwd_data_dir / "job.failed").resolve()),
        )

    def test_finalize_does_not_call_write_job_errorlog_file_on_success(
        self, _cwd_data_dir: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """finalize must not invoke write_job_errorlog_file at all for a successful report."""
        mock_write = MagicMock()
        monkeypatch.setattr("rdetoolkit.runner.finalize.write_job_errorlog_file", mock_write)
        report = _make_report("success")

        finalize(report, RdeConfig(), data_root=_cwd_data_dir)

        mock_write.assert_not_called()


class TestFinalizePersistsRunReport:
    """TC-FIN-007: RunReport JSON is saved to logs/run_report_{run_id}.json regardless of status."""

    def test_run_report_json_saved_on_failure(self, _cwd_data_dir: Path) -> None:
        """A logs/run_report_{run_id}.json file must exist after a failed run is finalized."""
        report = _make_report("failed", error={"code": _NODE_EXECUTION_FAILED_CODE, "message": "boom"}, run_id="run-fail-1")

        finalize(report, RdeConfig(), data_root=_cwd_data_dir)

        report_path = _cwd_data_dir / "logs" / "run_report_run-fail-1.json"
        assert report_path.exists()
        saved = json.loads(report_path.read_text(encoding="utf-8"))
        assert saved["run_id"] == "run-fail-1"
        assert saved["status"] == "failed"

    def test_run_report_json_saved_on_success(self, _cwd_data_dir: Path) -> None:
        """A logs/run_report_{run_id}.json file must exist after a successful run is finalized too."""
        report = _make_report("success", run_id="run-ok-1")

        finalize(report, RdeConfig(), data_root=_cwd_data_dir)

        report_path = _cwd_data_dir / "logs" / "run_report_run-ok-1.json"
        assert report_path.exists()
        saved = json.loads(report_path.read_text(encoding="utf-8"))
        assert saved["run_id"] == "run-ok-1"
        assert saved["status"] == "success"

    def test_flat_data_root_does_not_create_nested_data__tc_ep_bv_hr2_b_001(
        self,
        tmp_path: Path,
    ) -> None:
        """TC-EP/BV-HR2-B-001: a flat data root owns its report logs directly."""
        # Given: a root that is already the canonical flat data directory
        data_root = tmp_path / "data"
        data_root.mkdir()
        report = _make_report("success", run_id="flat-root")

        # When: finalizing the report against that flat root
        finalize(report, RdeConfig(), data_root=data_root)

        # Then: the report is under root/logs and no second data layer exists
        assert (data_root / "logs" / "run_report_flat-root.json").exists()
        assert not (data_root / "data" / "logs").exists()


class TestReviewFollowUps:
    """PR #504 review pins: production finalize wiring and placeholder-safe fallback."""

    def test_base_runner_finalize_writes_artifacts(self, tmp_path: Path, monkeypatch) -> None:
        """Runner.finalize (production path, not a testing subclass) persists for real."""
        from rdetoolkit.runner.lifecycle import Runner
        from rdetoolkit.types import RdeConfig

        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()
        report = _make_report(status="failed", error={"code": 3001, "message": "boom"})

        Runner().finalize(report, RdeConfig())

        assert (tmp_path / "data" / "logs" / f"run_report_{report.run_id}.json").exists()
        assert (tmp_path / "data" / "job.failed").read_text(encoding="utf-8").startswith("ErrorCode=3001")

    def test_fallback_message_contains_no_raw_placeholders(self, tmp_path: Path, monkeypatch) -> None:
        """job.failed must never contain unexpanded {placeholder} template text."""
        from rdetoolkit.runner.finalize import finalize
        from rdetoolkit.types import RdeConfig

        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()
        report = _make_report(status="failed", error={"code": 3001})  # no message

        finalize(report, RdeConfig(), data_root=tmp_path / "data")

        content = (tmp_path / "data" / "job.failed").read_text(encoding="utf-8")
        assert "{" not in content and "}" not in content, content

    def test_runner_finalize_uses_root_when_cwd_differs__tc_h0_root_ep_001_bv_001(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-H0-ROOT-EP-001/BV-001: report storage derives from Runner.root."""
        from rdetoolkit.runner.lifecycle import Runner

        # Given: a Runner root and an unrelated process working directory
        run_root = tmp_path / "run-root"
        caller = tmp_path / "caller"
        run_root.mkdir()
        caller.mkdir()
        monkeypatch.chdir(caller)
        report = _make_report(status="success", run_id="root-relative")

        # When: the production Runner finalizes one successful report
        Runner(root=run_root).finalize(report, RdeConfig())

        # Then: the report is persisted only below the Runner root
        expected = run_root / "data" / "logs" / "run_report_root-relative.json"
        assert expected.exists()
        assert not (caller / "data" / "logs" / expected.name).exists()

    def test_failed_runner_finalize_uses_root_when_cwd_differs__tc_hr_f1_bv_001(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-HR-F1-BV-001: failed marker belongs to Runner.root, not cwd."""
        # Given: a failed report, a Runner root, and an unrelated cwd
        from rdetoolkit.runner.lifecycle import Runner

        run_root = tmp_path / "run-root"
        caller = tmp_path / "caller"
        run_root.mkdir()
        caller.mkdir()
        monkeypatch.chdir(caller)
        report = _make_report(status="failed", error={"code": 3001, "message": "boom"})

        # When: the production Runner finalizes the failed report
        Runner(root=run_root).finalize(report, RdeConfig())

        # Then: only the absolute root-owned marker is created
        failure_path = run_root / "data" / "job.failed"
        assert failure_path.read_text(encoding="utf-8") == "ErrorCode=3001\nErrorMessage=boom\n"
        assert not (caller / "data" / "job.failed").exists()
