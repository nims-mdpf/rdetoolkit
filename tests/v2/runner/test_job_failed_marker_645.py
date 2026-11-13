"""v2 ``job.failed`` finalization owns its destination (issue #645).

The v2 finalizer resolves ``data_root`` once and writes ``data_root/job.failed``
through the internal marker primitive. It must never reach the deprecated
``StorageDir.get_datadir`` that v1's public ``write_job_errorlog_file`` uses for
its legacy filename resolution, and v1 direct callers keep that legacy
location and the exact file bytes.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| _write_job_failed_marker | ASCII message | exact UTF-8 marker bytes | TC-645-EP-001 |
| _write_job_failed_marker | non-ASCII message | UTF-8 encoded bytes, platform line endings | TC-645-EP-002 |
| finalize | ordinary catalog failure, custom root | ``custom_root/job.failed`` bytes | TC-645-EP-003 |
| finalize | v1 StructuredError passthrough | user ecode/emsg bytes verbatim | TC-645-EP-004 |
| finalize | failed, get_datadir raising, warnings as errors | marker written, no warning | TC-645-EP-005 |
| finalize | success | no job.failed | TC-645-EP-006 |
| Runner.run | validate-only, pre_validate fails | no job.failed, report written | TC-645-EP-007 |
| Runner.run | validate-only, success | no job.failed | TC-645-EP-008 |
| write_job_errorlog_file | default filename | ``data/job.failed`` (cwd), same bytes | TC-645-EP-009 |
| write_job_errorlog_file | custom filename | ``data/<filename>`` (cwd), same bytes | TC-645-EP-010 |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| finalize | data_root does not exist yet | parent created, marker written | TC-645-BV-001 |
| finalize | cwd differs from data_root | nothing written below cwd | TC-645-BV-002 |
| _write_job_failed_marker | existing marker | overwritten, not appended | TC-645-BV-003 |
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.api.request import build_run_request
from rdetoolkit.errors import _write_job_failed_marker, write_job_errorlog_file
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.rde2util import StorageDir
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.finalize import finalize, structured_error_record
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import RdeConfig


def _report(status: str, *, error: dict[str, Any] | None = None, run_id: str = "run-645") -> RunReport:
    return RunReport(
        run_id=run_id,
        status=status,
        flow_id="tests.v2.runner.test_job_failed_marker_645.stub",
        mode="invoice",
        started_at="2026-11-13T00:00:00",
        duration_ms=1.0,
        config_digest="sha256:deadbeef",
        iterations=[],
        warnings=[],
        error=error,
    )


def _marker_bytes(code: int, message: str) -> bytes:
    """The bytes v1's text-mode writer produces on this platform (CRLF on Windows)."""
    return f"ErrorCode={code}{os.linesep}ErrorMessage={message}{os.linesep}".encode()


def _forbid_get_datadir(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_args: object, **_kwargs: object) -> str:
        msg = "v2 finalization must not resolve the v1 data directory"
        raise AssertionError(msg)

    monkeypatch.setattr(StorageDir, "get_datadir", classmethod(_raise))


class TestMarkerPrimitive:
    """The explicit-path primitive writes the exact RDE marker format."""

    def test_ascii_marker_bytes__tc_645_ep_001(self, tmp_path: Path) -> None:
        """TC-645-EP-001: an ASCII message yields the exact marker bytes."""
        target = tmp_path / "job.failed"

        _write_job_failed_marker(target, 3001, "boom")

        assert target.read_bytes() == _marker_bytes(3001, "boom")

    def test_non_ascii_marker_is_utf8__tc_645_ep_002(self, tmp_path: Path) -> None:
        """TC-645-EP-002: a non-ASCII message is encoded as UTF-8."""
        target = tmp_path / "job.failed"

        _write_job_failed_marker(target, 21, "読み込み失敗: 試料")

        assert target.read_bytes() == _marker_bytes(21, "読み込み失敗: 試料")

    def test_existing_marker_is_overwritten__tc_645_bv_003(self, tmp_path: Path) -> None:
        """TC-645-BV-003: a stale marker is replaced, not appended to."""
        target = tmp_path / "job.failed"
        target.write_text("stale content that is longer than the new marker\n", encoding="utf-8")

        _write_job_failed_marker(target, 7, "new")

        assert target.read_bytes() == _marker_bytes(7, "new")


class TestV2FinalizeMarker:
    """v2 finalize writes ``data_root/job.failed`` itself, never via v1 path resolution."""

    def test_ordinary_failure_custom_root_bytes__tc_645_ep_003_bv_001_bv_002(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-645-EP-003/BV-001/BV-002: the marker lands at a custom, not yet existing root; cwd stays empty."""
        caller = tmp_path / "caller"
        caller.mkdir()
        monkeypatch.chdir(caller)
        data_root = tmp_path / "custom_root"  # does not exist yet

        finalize(_report("failed", error={"code": 3001, "message": "boom"}), RdeConfig(), data_root=data_root)

        assert (data_root / "job.failed").read_bytes() == _marker_bytes(3001, "boom")
        assert not (caller / "data").exists()
        assert list(caller.iterdir()) == []

    def test_structured_error_passthrough_bytes__tc_645_ep_004(self, tmp_path: Path) -> None:
        """TC-645-EP-004: a v1 StructuredError's ecode/emsg reach the marker verbatim."""
        record = structured_error_record(StructuredError("ユーザー定義エラー", ecode=999))
        assert record is not None

        finalize(_report("failed", error=record), RdeConfig(), data_root=tmp_path)

        assert (tmp_path / "job.failed").read_bytes() == _marker_bytes(999, "ユーザー定義エラー")

    def test_failed_finalize_never_touches_get_datadir__tc_645_ep_005(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-645-EP-005: failed finalize never resolves get_datadir and emits no warning."""
        _forbid_get_datadir(monkeypatch)
        data_root = tmp_path / "custom_root"

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("error")
            finalize(_report("failed", error={"code": 3001, "message": "boom"}), RdeConfig(), data_root=data_root)

        assert caught == []
        assert (data_root / "job.failed").read_bytes() == _marker_bytes(3001, "boom")

    def test_success_writes_no_marker__tc_645_ep_006(self, tmp_path: Path) -> None:
        """TC-645-EP-006: a successful report writes the run report but no marker."""
        finalize(_report("success"), RdeConfig(), data_root=tmp_path)

        assert not (tmp_path / "job.failed").exists()
        assert (tmp_path / "logs" / "run_report_run-645.json").is_file()


class _PreValidateRunner(Runner):
    """Stop at ``pre_validate``; optionally fail there."""

    def __init__(self, *, error: Exception | None, **kwargs: Any) -> None:
        self._error = error
        super().__init__(**kwargs)

    def load_config(self, source: object | None = None) -> RdeConfig:
        return RdeConfig()

    def resolve_mode(self, config: RdeConfig) -> ModeKind:
        return ModeKind.invoice

    def pre_validate(self, config: RdeConfig) -> None:
        if self._error is not None:
            raise self._error


def _validate_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception | None) -> RunReport:
    (tmp_path / "data").mkdir()
    monkeypatch.chdir(tmp_path)
    _forbid_get_datadir(monkeypatch)
    request = build_run_request(
        flow=lambda: None,
        custom_dataset_function=None,
        config=None,
        root=tmp_path,
        validate_only=True,
    )
    return _PreValidateRunner(error=error, root=tmp_path).run(request)


class TestValidateOnlyWritesNoMarker:
    """A validate-only pre-flight never writes the job-failure marker."""

    def test_failed_validate_only__tc_645_ep_007(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-645-EP-007: a failed pre-flight writes the report but no marker."""
        report = _validate_only(tmp_path, monkeypatch, StructuredError("invalid input", ecode=50))

        assert report.status == "failed"
        assert not (tmp_path / "data" / "job.failed").exists()
        assert list((tmp_path / "data" / "logs").glob("run_report_*.json"))

    def test_successful_validate_only__tc_645_ep_008(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-645-EP-008: a successful pre-flight writes no marker."""
        report = _validate_only(tmp_path, monkeypatch, None)

        assert report.status == "success"
        assert not (tmp_path / "data" / "job.failed").exists()


class TestV1WriterKeepsLegacyLocation:
    """v1 ``write_job_errorlog_file`` still resolves cwd-relative ``data/``."""

    @pytest.fixture()
    def legacy_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """Chdir into tmp_path with a ``data/`` directory, as v1 callers run."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()
        return tmp_path

    def test_default_filename__tc_645_ep_009(self, legacy_cwd: Path) -> None:
        """TC-645-EP-009: the default filename lands at cwd-relative ``data/job.failed``."""
        with pytest.warns(DeprecationWarning, match="get_datadir is deprecated"):
            write_job_errorlog_file(404, "Not Found")

        assert (legacy_cwd / "data" / "job.failed").read_bytes() == _marker_bytes(404, "Not Found")

    def test_custom_filename__tc_645_ep_010(self, legacy_cwd: Path) -> None:
        """TC-645-EP-010: a custom filename lands at cwd-relative ``data/<filename>``."""
        with pytest.warns(DeprecationWarning, match="get_datadir is deprecated"):
            write_job_errorlog_file(999, "ユーザー定義エラー", filename="custom.failed")

        assert (legacy_cwd / "data" / "custom.failed").read_bytes() == _marker_bytes(999, "ユーザー定義エラー")
        assert not (legacy_cwd / "data" / "job.failed").exists()
