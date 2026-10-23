"""End-of-run event-log shutdown is an exception boundary (Session K4-F2).

PR #550 review finding F2: ``FileEventSink.close`` flushed, fsynced and closed
in sequence, so a flush/fsync failure left the handle open; and the Runner
called ``emit(run_completed)`` + ``close()`` from a ``finally`` outside every
translation boundary, so an fsync ``OSError`` replaced a successful run's
return value with an untranslated exception and masked a failing finalizer's
primary ``RdeInternalError(5001)``.

Contract (contracts.md §K4, rulings #1-#3):

* ``close`` always closes: the handle is closed and released even when flush or
  fsync raises; the failure is re-raised after closing; a second close is a
  no-op. ``_RunScopedFileEventSink`` releases its inner sink the same way.
* The Runner maps an event-log shutdown failure to ``RdeInternalError`` 5001
  (an ``RdeError`` passes through unchanged, as for ``_finalize_error``) when
  no primary exception is propagating. Finalization has already completed on
  that path, so the report / ``job.failed`` stay as written and nothing more is
  written (same rule as TC-EP-HR-F5-001).
* When a primary exception is already propagating, the shutdown failure is
  recorded as one stderr line and never masks the primary exception.

EP table:

| TC-ID          | Partition                                              | Expected                                                              |
|----------------|--------------------------------------------------------|-----------------------------------------------------------------------|
| TC-K4F2-EP-001 | success run, os.fsync raises OSError(EIO)              | RdeInternalError 5001 ("event log"), handle closed, report success, no job.failed |
| TC-K4F2-EP-002 | finalizer raises OSError + os.fsync raises             | caller gets the finalizer's 5001, one stderr line, handle closed      |
| TC-K4F2-EP-003 | failed run (iterate raises) + os.fsync raises          | RdeInternalError 5001, job.failed as written by finalize              |
| TC-K4F2-EP-004 | success run, emit(run.completed) raises                | RdeInternalError 5001, handle still closed                            |
| TC-K4F2-EP-005 | injected sink close raises an RdeError                 | that RdeError propagates unchanged                                    |
| TC-K4F2-EP-006 | FileEventSink.close, flush raises                      | file closed, _file is None, the flush error is re-raised              |
| TC-K4F2-EP-007 | FileEventSink.close, os.fsync raises                   | file closed, _file is None, the fsync error is re-raised              |
| TC-K4F2-EP-008 | _RunScopedFileEventSink.close, inner close raises      | inner sink released, error re-raised                                  |
| TC-K4F2-EP-009 | success run, healthy sink                              | report returned, events file ends with run.completed, handle closed   |

BV table:

| TC-ID          | Boundary                                               | Expected                                                              |
|----------------|--------------------------------------------------------|-----------------------------------------------------------------------|
| TC-K4F2-BV-001 | FileEventSink.close called twice after a failing close | second close is a no-op (no raise, no fsync)                          |
| TC-K4F2-BV-002 | FileEventSink.close on a never-opened sink             | no-op                                                                 |
| TC-K4F2-BV-003 | _RunScopedFileEventSink.close twice after a failure    | second close is a no-op                                               |
| TC-K4F2-BV-004 | primary exception is an RdeError (finalize 5001) and the sink close fails | exactly one stderr line, primary preserved |
| TC-K4F2-BV-005 | primary is a BaseException before any report exists, sink close fails | KeyboardInterrupt propagates, no run.completed, one stderr line, handle closed |
"""

from __future__ import annotations

import errno
import json
import os
from pathlib import Path
from typing import Any, TextIO

import pytest

from rdetoolkit.errors import RdeExecutionError, RdeInternalError
from rdetoolkit.report.events import Event, FileEventSink, MemoryEventSink
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner import lifecycle
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import RdeConfig


def _report(*, status: str = "success") -> RunReport:
    return RunReport(
        run_id="k4f2-run",
        status=status,
        flow_id="tests.k4f2_flow",
        mode="invoice",
        started_at="2026-10-19T00:00:00",
        duration_ms=0.0,
        config_digest="sha256:test",
        iterations=[],
        warnings=[],
    )


class _SpyFileEventSink(FileEventSink):
    """Remember every instance and the handle it opened, for post-run checks."""

    instances: list[_SpyFileEventSink] = []

    def open(self, run_id: str) -> None:
        super().open(run_id)
        self.opened_file: TextIO | None = self._file
        _SpyFileEventSink.instances.append(self)


class _FailingFinalizer:
    def __init__(self) -> None:
        self.reports: list[RunReport] = []

    def finalize(self, report: RunReport, config: RdeConfig) -> None:
        self.reports.append(report)
        msg = "disk full"
        raise OSError(msg)


def _eio(fd: int) -> None:
    raise OSError(errno.EIO, "injected fsync failure")


def _runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    iterate: Any,
    **kwargs: Any,
) -> Runner:
    _SpyFileEventSink.instances = []
    monkeypatch.setattr(lifecycle, "FileEventSink", _SpyFileEventSink)
    runner = Runner(root=tmp_path, run_id_factory=lambda: "k4f2-run", **kwargs)
    monkeypatch.setattr(runner, "load_config", lambda source: RdeConfig())
    monkeypatch.setattr(runner, "resolve_mode", lambda config: ModeKind.invoice)
    monkeypatch.setattr(runner, "pre_validate", lambda config: None)
    monkeypatch.setattr(runner, "iterate", iterate)
    monkeypatch.setattr(runner, "post_validate", lambda config, report: None)
    return runner


def _only_sink() -> _SpyFileEventSink:
    assert len(_SpyFileEventSink.instances) == 1
    return _SpyFileEventSink.instances[0]


def _assert_released(sink: _SpyFileEventSink) -> None:
    assert sink._file is None
    assert sink.opened_file is not None
    assert sink.opened_file.closed


# --- Runner boundary ---------------------------------------------------------


def test_success_run_fsync_failure_is_5001_and_report_stays_success__tc_k4f2_ep_001(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K4F2-EP-001: an end-of-run fsync failure is a catalogued internal I/O error."""
    # Given: a successful lifecycle whose event-log fsync fails with EIO
    runner = _runner(tmp_path, monkeypatch, iterate=lambda target, mode, config: _report())
    monkeypatch.setattr(os, "fsync", _eio)

    # When: the run reaches the end-of-run event-log shutdown
    with pytest.raises(RdeInternalError) as exc_info:
        runner.run(lambda: None)

    # Then: 5001 naming the event log, handle closed, success report kept, no job.failed
    assert exc_info.value.code == 5001
    assert "event log" in exc_info.value.message
    assert isinstance(exc_info.value.__cause__, OSError)
    _assert_released(_only_sink())
    persisted = json.loads((runner.data_root / "logs" / "run_report_k4f2-run.json").read_text(encoding="utf-8"))
    assert persisted["status"] == "success"
    assert not (runner.data_root / "job.failed").exists()


def test_finalizer_failure_is_not_masked_by_fsync_failure__tc_k4f2_ep_002(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-K4F2-EP-002 / BV-004: the primary finalize error survives a sink failure."""
    # Given: a finalizer that fails with OSError and an event-log fsync that also fails
    finalizer = _FailingFinalizer()
    runner = _runner(tmp_path, monkeypatch, iterate=lambda target, mode, config: _report(), finalizer=finalizer)
    monkeypatch.setattr(os, "fsync", _eio)

    # When: both end-of-run steps fail
    with pytest.raises(RdeInternalError) as exc_info:
        runner.run(lambda: None)

    # Then: the caller receives the finalizer's 5001; the sink failure is one stderr line
    assert exc_info.value.code == 5001
    assert "disk full" in exc_info.value.message
    assert "event log" not in exc_info.value.message
    assert len(finalizer.reports) == 1
    stderr_lines = [line for line in capsys.readouterr().err.splitlines() if "event log" in line]
    assert len(stderr_lines) == 1
    assert "injected fsync failure" in stderr_lines[0]
    _assert_released(_only_sink())


def test_failed_run_fsync_failure_is_5001_and_job_failed_kept__tc_k4f2_ep_003(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K4F2-EP-003: a failed run's artifacts stay as finalize wrote them."""

    # Given: an iteration that raises (failed report) and an event-log fsync that fails
    def _boom(target: Any, mode: Any, config: Any) -> RunReport:
        msg = "boom"
        raise RuntimeError(msg)

    runner = _runner(tmp_path, monkeypatch, iterate=_boom)
    monkeypatch.setattr(os, "fsync", _eio)

    # When: the failed run reaches the event-log shutdown
    with pytest.raises(RdeInternalError) as exc_info:
        runner.run(lambda: None)

    # Then: 5001 is raised, the failed report and job.failed are as finalize wrote them
    assert exc_info.value.code == 5001
    assert "event log" in exc_info.value.message
    persisted = json.loads((runner.data_root / "logs" / "run_report_k4f2-run.json").read_text(encoding="utf-8"))
    assert persisted["status"] == "failed"
    job_failed = (runner.data_root / "job.failed").read_text(encoding="utf-8")
    assert "boom" in job_failed
    _assert_released(_only_sink())


def test_run_completed_emit_failure_is_5001_and_still_closes__tc_k4f2_ep_004(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K4F2-EP-004: a failing final emit cannot leave the handle open."""
    # Given: a successful lifecycle whose run.completed write fails
    runner = _runner(tmp_path, monkeypatch, iterate=lambda target, mode, config: _report())
    original_emit = _SpyFileEventSink.emit

    def _emit(self: _SpyFileEventSink, event: Event) -> None:
        if event.name == "run.completed":
            raise OSError(errno.ENOSPC, "no space for run.completed")
        original_emit(self, event)

    monkeypatch.setattr(_SpyFileEventSink, "emit", _emit)

    # When: the run reaches the end-of-run shutdown
    with pytest.raises(RdeInternalError) as exc_info:
        runner.run(lambda: None)

    # Then: 5001 is raised and the event log was still closed
    assert exc_info.value.code == 5001
    assert "no space for run.completed" in exc_info.value.message
    _assert_released(_only_sink())


class _RdeErrorClosingSink(MemoryEventSink):
    def __init__(self, error: Exception) -> None:
        super().__init__()
        self._error = error

    def close(self) -> None:
        super().close()
        raise self._error


def test_rde_error_from_sink_close_passes_through__tc_k4f2_ep_005(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K4F2-EP-005: an already-catalogued error is not re-wrapped as 5001."""
    # Given: an injected sink whose close raises a catalogued interruption error
    error = RdeExecutionError(code=3004, name="RunInterrupted", message="interrupted during close")
    sink = _RdeErrorClosingSink(error)
    runner = _runner(tmp_path, monkeypatch, iterate=lambda target, mode, config: _report(), event_sink=sink)

    # When: the successful run closes the sink
    with pytest.raises(RdeExecutionError) as exc_info:
        runner.run(lambda: None)

    # Then: the very same error object reaches the caller
    assert exc_info.value is error
    assert exc_info.value.code == 3004


def test_healthy_run_returns_report_and_closes__tc_k4f2_ep_009(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K4F2-EP-009: the healthy path is unchanged."""
    # Given: a successful lifecycle with the default event sink
    runner = _runner(tmp_path, monkeypatch, iterate=lambda target, mode, config: _report())

    # When: the run completes
    report = runner.run(lambda: None)

    # Then: the report is returned, the log ends with run.completed and is closed
    assert report.status == "success"
    sink = _only_sink()
    _assert_released(sink)
    assert sink.path is not None
    last = json.loads(sink.path.read_text(encoding="utf-8").splitlines()[-1])
    assert last["name"] == "run.completed"


def test_base_exception_without_report_is_not_masked__tc_k4f2_bv_005(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-K4F2-BV-005: no report yet, a BaseException unwinding, and a failing close."""

    # Given: an iteration interrupted by a BaseException and an fsync that fails
    def _interrupt(target: Any, mode: Any, config: Any) -> RunReport:
        raise KeyboardInterrupt

    runner = _runner(tmp_path, monkeypatch, iterate=_interrupt)
    monkeypatch.setattr(os, "fsync", _eio)

    # When: the run unwinds through the shutdown boundary
    with pytest.raises(KeyboardInterrupt):
        runner.run(lambda: None)

    # Then: the interruption reaches the caller, no run.completed, one stderr line, closed
    sink = _only_sink()
    _assert_released(sink)
    assert sink.path is not None
    names = [json.loads(line).get("name") for line in sink.path.read_text(encoding="utf-8").splitlines()]
    assert "run.completed" not in names
    stderr_lines = [line for line in capsys.readouterr().err.splitlines() if "event log" in line]
    assert len(stderr_lines) == 1


# --- FileEventSink.close -----------------------------------------------------


class _FlushFailingFile:
    """A handle double whose flush fails; records whether it was closed."""

    def __init__(self) -> None:
        self.closed = False

    def flush(self) -> None:
        raise OSError(errno.EIO, "injected flush failure")

    def fileno(self) -> int:  # pragma: no cover - flush fails first
        raise AssertionError

    def close(self) -> None:
        self.closed = True


def test_file_sink_close_closes_when_flush_fails__tc_k4f2_ep_006(tmp_path: Path) -> None:
    """TC-K4F2-EP-006: a flush failure is re-raised only after the handle is closed."""
    # Given: an opened sink whose handle fails to flush
    sink = FileEventSink(tmp_path)
    sink.open("k4f2-flush")
    real_file = sink._file
    assert real_file is not None
    real_file.close()
    double = _FlushFailingFile()
    sink._file = double  # type: ignore[assignment]

    # When: the sink is closed
    with pytest.raises(OSError, match="injected flush failure"):
        sink.close()

    # Then: the handle was closed and released
    assert double.closed
    assert sink._file is None


def test_file_sink_close_closes_when_fsync_fails_and_second_close_is_noop__tc_k4f2_ep_007_bv_001(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K4F2-EP-007 / BV-001: fsync failure closes, re-raises, and close stays idempotent."""
    # Given: an opened sink and an fsync that fails
    sink = FileEventSink(tmp_path)
    sink.open("k4f2-fsync")
    handle = sink._file
    assert handle is not None
    calls: list[int] = []

    def _failing_fsync(fd: int) -> None:
        calls.append(fd)
        _eio(fd)

    monkeypatch.setattr(os, "fsync", _failing_fsync)

    # When: the sink is closed twice
    with pytest.raises(OSError, match="injected fsync failure") as exc_info:
        sink.close()
    sink.close()

    # Then: the first close closed the handle and re-raised; the second did nothing
    assert exc_info.value.errno == errno.EIO
    assert handle.closed
    assert sink._file is None
    assert len(calls) == 1


def test_file_sink_close_never_opened_is_noop__tc_k4f2_bv_002(tmp_path: Path) -> None:
    """TC-K4F2-BV-002: closing a never-opened sink is a no-op."""
    # Given: a sink that was never opened
    sink = FileEventSink(tmp_path)

    # When / Then: close neither raises nor creates a file
    sink.close()
    assert sink._file is None
    assert list(tmp_path.iterdir()) == []


# --- _RunScopedFileEventSink.close ------------------------------------------


def test_run_scoped_sink_releases_inner_sink_on_failure__tc_k4f2_ep_008_bv_003(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K4F2-EP-008 / BV-003: the run-scoped sink is released even when close fails."""
    # Given: an opened run-scoped sink whose fsync fails
    scoped = lifecycle._RunScopedFileEventSink(lambda: tmp_path / "logs")
    scoped.open("k4f2-scoped")
    inner = scoped._sink
    assert inner is not None
    handle = inner._file
    assert handle is not None
    monkeypatch.setattr(os, "fsync", _eio)

    # When: it is closed twice
    with pytest.raises(OSError, match="injected fsync failure"):
        scoped.close()
    # The inner sink is released by the finally, before the second (no-op) close.
    assert scoped._sink is None
    scoped.close()

    # Then: inner sink released and its handle closed; the second close was a no-op
    assert scoped._sink is None
    assert inner._file is None
    assert handle.closed
