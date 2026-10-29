"""Event-log I/O never changes a run's outcome (Session K4-F3).

PR #550 re-review found three places where an event-log failure rewrote the
run's verdict:

* R1 -- ``run_tile`` emitted ``node.*`` / ``iteration.completed`` inside the
  user-exception handler, so an emit failure replaced a node's
  ``StructuredError(42)`` with a 3001 and dropped the call log.
* R2 -- ``event_sink.open()`` sat before the shutdown boundary and
  ``FileEventSink.open()`` wrote its header unprotected, so a header ENOSPC
  leaked the handle and raised a raw ``OSError``.
* R3 -- the primary-error-preserving branch wrote to stderr unprotected, so a
  failing stderr masked the primary 5001.

Contract (contracts.md §K4 F3): the event log is diagnostics. Its I/O failures
never change ``RunReport.status``, ``job.failed``, the return value or the
propagated exception. The single exception is the F2 end-of-run shutdown
(``run.completed`` / close failing with no primary error in flight -> 5001
after the report and ``job.failed`` are persisted), which is unchanged.

EP table:

| TC-ID          | Partition                                                     | Expected                                                                  |
|----------------|---------------------------------------------------------------|---------------------------------------------------------------------------|
| TC-K4F3-EP-001 | node raises StructuredError(42), node.failed emit raises      | report failed with code 42 + original message, node_calls kept, job.failed 42, one stderr line |
| TC-K4F3-EP-002 | node succeeds, node.completed emit raises                     | report success with node_calls, one stderr line, file stops growing       |
| TC-K4F3-EP-003 | TileExecutor built on a failing raw sink, node raises 42      | failed result with code 42 (executor wraps its sink)                     |
| TC-K4F3-EP-004 | events file cannot be created (a directory occupies its path) | run success, report persisted, no events file, one stderr line            |
| TC-K4F3-EP-005 | logs directory for the events file cannot be created          | run success, report persisted, no events file, one stderr line            |
| TC-K4F3-EP-006 | header write fails during open (Runner)                       | handle closed (_file is None), run success, one stderr line               |
| TC-K4F3-EP-007 | FileEventSink.open, header write fails                        | error re-raised, handle closed, _file is None                             |
| TC-K4F3-EP-008 | _RunScopedFileEventSink.open, inner open fails                | error re-raised, inner sink released                                      |
| TC-K4F3-EP-009 | finalizer OSError + fsync fails + stderr fails                | caller gets the finalizer's 5001                                          |
| TC-K4F3-EP-010 | EP-001 with a failing stderr                                  | report failed with code 42, job.failed 42 (notice and "iteration(s) failed" lost) |
| TC-K4F3-EP-011 | W1002 truncation with a failing stderr                        | warning still recorded in the file, emit does not raise                   |
| TC-K4F3-EP-012 | best-effort sink, inner emit raises RunInterrupted (3004)     | the interruption propagates (never swallowed)                             |
| TC-K4F3-EP-013 | best-effort sink, inner open raises RunInterrupted (3004)     | the interruption propagates (never swallowed)                             |
| TC-K4F3-EP-014 | W1001 mode override with a failing stderr (validate-only)     | run success (no 1002), W1001 still recorded in the events file            |
| TC-K4F3-EP-015 | W1001 mode override with a sink that fails on warning events   | run success (no 1002); resolve_mode emits through the best-effort wrapper |

BV table:

| TC-ID          | Boundary                                                      | Expected                                                                  |
|----------------|---------------------------------------------------------------|---------------------------------------------------------------------------|
| TC-K4F3-BV-001 | _best_effort_stderr, write raises                             | returns None, no raise                                                    |
| TC-K4F3-BV-002 | _best_effort_stderr on a stream whose flush raises            | text written, returns None (the helper never forces a flush)              |
| TC-K4F3-BV-003 | best-effort sink, second emit after a failure (same run)      | inner emit not called again, still one stderr line                       |
| TC-K4F3-BV-004 | best-effort sink, emit for a different run after a failure    | inner emit called again (the mute is run-scoped)                          |
| TC-K4F3-BV-005 | same Runner, first open fails, second run healthy             | second run writes a complete events file                                  |
| TC-K4F3-BV-006 | FileEventSink.open, header write raises KeyboardInterrupt     | KeyboardInterrupt propagates, handle closed                               |
| TC-K4F3-BV-007 | best-effort sink wrapped twice                                | TileExecutor reuses an existing best-effort sink (no double wrap)         |
| TC-K4F3-BV-008 | best-effort sink close after a failed open                    | inner close not called                                                    |
"""

from __future__ import annotations

import errno
import io
import json
import os
import sys
from pathlib import Path
from typing import Any, TextIO

import pandas as pd
import pytest
import yaml

from rdetoolkit.api.request import FlowTarget, build_run_request
from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.errors import ERROR_CATALOG, RdeExecutionError, RdeInternalError
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.report import events as events_module
from rdetoolkit.report.events import Event, FileEventSink, MemoryEventSink, _best_effort_stderr
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner import lifecycle
from rdetoolkit.runner.executor import TileExecutor, _BestEffortEventSink
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import IterationInfo, RdeConfig
from tests.v2.runner.test_error_translation_i6_0 import _plan, _tile

_USER_CODE = 42
_USER_MESSAGE = "K4-F3 user failure. Remediation: fix the input."
_EVENT_LOG_NOTICE = "event log"

_INVOICE: dict[str, Any] = {
    "datasetId": "k4f3-dataset",
    "basic": {"dateSubmitted": "2026-10-19", "dataOwnerId": "0" * 56, "dataName": "k4f3"},
}


@node(id="k4f3_failing_node")
def _failing_node(iteration: IterationInfo) -> None:
    raise StructuredError(_USER_MESSAGE, ecode=_USER_CODE)


@node(id="k4f3_ok_node")
def _ok_node(iteration: IterationInfo) -> int:
    return iteration.index


@flow
def _failing_flow(iteration: IterationInfo) -> None:
    _failing_node(iteration)


@flow
def _ok_flow(iteration: IterationInfo) -> None:
    _ok_node(iteration)


def _build_tree(data_root: Path) -> None:
    (data_root / "inputdata").mkdir(parents=True)
    (data_root / "inputdata" / "file_0.txt").write_text("data-0", encoding="utf-8")
    (data_root / "invoice").mkdir(parents=True)
    (data_root / "invoice" / "invoice.json").write_text(json.dumps(_INVOICE), encoding="utf-8")
    (data_root / "tasksupport").mkdir(parents=True)
    (data_root / "tasksupport" / "invoice.schema.json").write_text(json.dumps({"properties": {}}), encoding="utf-8")
    (data_root / "tasksupport" / "metadata-def.json").write_text(json.dumps({"constant": {}, "variable": []}), encoding="utf-8")
    (data_root / "temp").mkdir(parents=True)


def _full_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_id: str, **kwargs: Any) -> Runner:
    _build_tree(tmp_path / "data")
    # job.failed is written cwd-relative (v1 StorageDir), so the run owns cwd.
    monkeypatch.chdir(tmp_path)
    data_root = tmp_path / "data"
    return Runner(
        root=tmp_path,
        inputdata_path=data_root / "inputdata",
        unpacked_dir_path=data_root / "temp",
        run_id_factory=lambda: run_id,
        **kwargs,
    )


def _failing_emit_sink(fail_on: str) -> type[FileEventSink]:
    """Return a FileEventSink class whose ``emit`` fails for one event name."""

    class _Sink(FileEventSink):
        instances: list[FileEventSink] = []

        def open(self, run_id: str) -> None:
            super().open(run_id)
            _Sink.instances.append(self)

        def emit(self, event: Event) -> None:
            if event.name == fail_on:
                raise OSError(errno.ENOSPC, f"injected {fail_on} failure")
            super().emit(event)

    return _Sink


def _notices(err: str) -> list[str]:
    return [line for line in err.splitlines() if _EVENT_LOG_NOTICE in line]


def _lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class _BrokenStream(io.StringIO):
    """A stderr double whose every write fails like a full disk."""

    def write(self, text: str) -> int:
        raise OSError(errno.ENOSPC, "injected stderr failure")


class _FlushBrokenStream(io.StringIO):
    def flush(self) -> None:
        raise OSError(errno.EIO, "injected stderr flush failure")


# --- R1: best-effort emit ----------------------------------------------------


def test_node_failed_emit_failure_keeps_user_error__tc_k4f3_ep_001(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-K4F3-EP-001: the user's StructuredError(42) survives a node.failed write failure."""
    # Given: a flow whose node raises StructuredError(42) and an events file that refuses node.failed
    sink_cls = _failing_emit_sink("node.failed")
    monkeypatch.setattr(lifecycle, "FileEventSink", sink_cls)
    runner = _full_runner(tmp_path, monkeypatch, "k4f3-ep-001")

    # When: running
    report = runner.run(_failing_flow)

    # Then: the verdict is the user's error, with its call log, and one stderr notice
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == _USER_CODE
    assert _USER_MESSAGE in report.error["message"]
    assert report.iterations[0]["node_calls"]
    job_failed = (tmp_path / "data" / "job.failed").read_text(encoding="utf-8")
    assert f"ErrorCode={_USER_CODE}" in job_failed
    assert _USER_MESSAGE in job_failed
    notices = _notices(capsys.readouterr().err)
    assert len(notices) == 1
    assert "injected node.failed failure" in notices[0]


def test_success_emit_failure_keeps_success_and_stops_the_log__tc_k4f3_ep_002_bv_003(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-K4F3-EP-002 / BV-003: a write failure on the success path mutes the log, not the run."""
    # Given: a successful flow and an events file that refuses node.completed
    sink_cls = _failing_emit_sink("node.completed")
    monkeypatch.setattr(lifecycle, "FileEventSink", sink_cls)
    runner = _full_runner(tmp_path, monkeypatch, "k4f3-ep-002")

    # When: running
    report = runner.run(_ok_flow)

    # Then: success with node_calls, one stderr line, and nothing written after the failure
    assert report.status == "success"
    assert report.iterations[0]["node_calls"]
    assert not (tmp_path / "data" / "job.failed").exists()
    assert len(_notices(capsys.readouterr().err)) == 1
    names = [line.get("name") for line in _lines(tmp_path / "data" / "logs" / "events_k4f3-ep-002.jsonl")[1:]]
    assert names[-1] == "node.started"
    assert "iteration.completed" not in names
    assert "run.completed" not in names


class _RaisingSink(MemoryEventSink):
    def __init__(self, error: BaseException, *, fail_on: str | None = None) -> None:
        super().__init__()
        self._error = error
        self._fail_on = fail_on
        self.emit_calls = 0
        self.close_calls = 0

    def emit(self, event: Event) -> None:
        self.emit_calls += 1
        if self._fail_on is None or event.name == self._fail_on:
            raise self._error
        super().emit(event)

    def close(self) -> None:
        self.close_calls += 1
        super().close()


def test_executor_wraps_a_raw_failing_sink__tc_k4f3_ep_003(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-K4F3-EP-003: an executor built on a raw sink still keeps the user's error."""
    # Given: a TileExecutor on a sink whose every emit fails, and a node raising StructuredError(42)
    sink = _RaisingSink(OSError(errno.ENOSPC, "injected raw sink failure"))
    executor = TileExecutor(event_sink=sink)
    tile = _tile(tmp_path)
    plan = _plan(tmp_path, tile, target=FlowTarget(function=_failing_flow))

    # When: executing the tile
    result = executor.execute(plan, tile)

    # Then: the failed result carries the user's code and the call log
    assert result.status == "failed"
    assert result.error is not None
    assert result.error["code"] == _USER_CODE
    assert result.call_records
    assert len(_notices(capsys.readouterr().err)) == 1


def test_executor_does_not_double_wrap__tc_k4f3_bv_007() -> None:
    """TC-K4F3-BV-007: an already best-effort sink is used as is."""
    # Given: a best-effort sink
    safe = _BestEffortEventSink(MemoryEventSink())

    # When: building an executor on it
    executor = TileExecutor(event_sink=safe)

    # Then: the executor holds that very sink
    assert executor._event_sink is safe


def test_best_effort_mute_is_run_scoped__tc_k4f3_bv_004(capsys: pytest.CaptureFixture[str]) -> None:
    """TC-K4F3-BV-004: a failure mutes its own run only."""
    # Given: a best-effort sink whose inner sink fails once on run "a"
    sink = _RaisingSink(OSError("boom"), fail_on="run.started")
    safe = _BestEffortEventSink(sink)
    safe.emit(Event.run_started(run_id="a"))
    safe.emit(Event.iteration_started(run_id="a", index=0))
    calls_after_a = sink.emit_calls

    # When: an event of another run arrives
    safe.emit(Event.iteration_started(run_id="b", index=0))

    # Then: run "a" was muted after the failure, run "b" is written
    assert calls_after_a == 1
    assert sink.emit_calls == 2
    assert [event.run_id for event in sink.events] == ["b"]
    assert len(_notices(capsys.readouterr().err)) == 1


def test_run_interrupted_from_emit_propagates__tc_k4f3_ep_012() -> None:
    """TC-K4F3-EP-012: a SIGTERM interruption raised inside a write is not swallowed."""
    # Given: an inner sink whose emit raises the catalogued interruption
    interrupted = RdeExecutionError(code=3004, name=ERROR_CATALOG[3004].name, message="interrupted")
    safe = _BestEffortEventSink(_RaisingSink(interrupted))

    # When / Then: the interruption reaches the caller
    with pytest.raises(RdeExecutionError) as exc_info:
        safe.emit(Event.run_started(run_id="a"))
    assert exc_info.value is interrupted


class _OpenFailingSink(MemoryEventSink):
    def __init__(self, error: BaseException) -> None:
        super().__init__()
        self._error = error
        self.close_calls = 0

    def open(self, run_id: str) -> None:
        raise self._error

    def close(self) -> None:
        self.close_calls += 1
        super().close()


def test_run_interrupted_from_open_propagates__tc_k4f3_ep_013() -> None:
    """TC-K4F3-EP-013: an interruption during open is not turned into "no event log"."""
    # Given: an inner sink whose open raises the catalogued interruption
    interrupted = RdeExecutionError(code=3004, name=ERROR_CATALOG[3004].name, message="interrupted")
    safe = _BestEffortEventSink(_OpenFailingSink(interrupted))

    # When / Then: the interruption reaches the caller
    with pytest.raises(RdeExecutionError) as exc_info:
        safe.open("a")
    assert exc_info.value is interrupted


def test_close_after_failed_open_skips_inner_close__tc_k4f3_bv_008(capsys: pytest.CaptureFixture[str]) -> None:
    """TC-K4F3-BV-008: there is nothing to close for a run whose log never opened."""
    # Given: a best-effort sink whose open failed
    inner = _OpenFailingSink(OSError("cannot open"))
    safe = _BestEffortEventSink(inner)
    safe.open("a")

    # When: the run emits and then closes
    safe.emit(Event.run_started(run_id="a"))
    safe.emit_final(Event.run_completed(run_id="a", status="success"))
    safe.close()

    # Then: no write and no close reached the inner sink; one notice
    assert inner.events == []
    assert inner.close_calls == 0
    assert len(_notices(capsys.readouterr().err)) == 1


# --- R2: open --------------------------------------------------------------------


def test_events_file_creation_failure_does_not_stop_the_run__tc_k4f3_ep_004(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-K4F3-EP-004: a directory where the events file should be is "no event log"."""
    # Given: the events file path is occupied by a directory
    runner = _full_runner(tmp_path, monkeypatch, "k4f3-ep-004")
    blocked = tmp_path / "data" / "logs" / "events_k4f3-ep-004.jsonl"
    blocked.mkdir(parents=True)

    # When: running
    report = runner.run(_ok_flow)

    # Then: the run completes and is reported; no events file; one stderr line
    assert report.status == "success"
    persisted = json.loads((tmp_path / "data" / "logs" / "run_report_k4f3-ep-004.json").read_text(encoding="utf-8"))
    assert persisted["status"] == "success"
    assert blocked.is_dir()
    assert not (tmp_path / "data" / "job.failed").exists()
    assert len(_notices(capsys.readouterr().err)) == 1


def test_events_dir_creation_failure_does_not_stop_the_run__tc_k4f3_ep_005(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-K4F3-EP-005: an uncreatable events directory is "no event log" too."""

    # Given: a FileEventSink whose directory is blocked by a regular file
    class _BlockedDirSink(FileEventSink):
        def __init__(self, logs_dir: Path, **kwargs: Any) -> None:
            blocker = logs_dir / "blocked"
            blocker.parent.mkdir(parents=True, exist_ok=True)
            blocker.write_text("not a directory", encoding="utf-8")
            super().__init__(blocker / "events", **kwargs)

    monkeypatch.setattr(lifecycle, "FileEventSink", _BlockedDirSink)
    runner = _full_runner(tmp_path, monkeypatch, "k4f3-ep-005")

    # When: running a failing flow (so job.failed is exercised too)
    report = runner.run(_failing_flow)

    # Then: the user's error is the verdict; no events file anywhere; one stderr line
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == _USER_CODE
    assert f"ErrorCode={_USER_CODE}" in (tmp_path / "data" / "job.failed").read_text(encoding="utf-8")
    assert sorted((tmp_path / "data" / "logs").rglob("events_*.jsonl")) == []
    assert len(_notices(capsys.readouterr().err)) == 1


def _fail_first_write(monkeypatch: pytest.MonkeyPatch, error: BaseException) -> list[TextIO]:
    """Make the first ``_write_encoded`` (the header) fail; return opened handles."""
    original = FileEventSink._write_encoded
    state = {"failed": False}
    handles: list[TextIO] = []

    def _write(self: FileEventSink, line: str) -> None:
        if not state["failed"]:
            state["failed"] = True
            assert self._file is not None
            handles.append(self._file)
            raise error
        original(self, line)

    monkeypatch.setattr(FileEventSink, "_write_encoded", _write)
    return handles


def test_header_failure_in_a_run_closes_and_continues__tc_k4f3_ep_006(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-K4F3-EP-006: an ENOSPC on the header closes the handle and the run goes on."""
    # Given: a Runner whose events header write fails once
    sinks: list[FileEventSink] = []

    class _Spy(FileEventSink):
        def __init__(self, logs_dir: Path, **kwargs: Any) -> None:
            super().__init__(logs_dir, **kwargs)
            sinks.append(self)

    monkeypatch.setattr(lifecycle, "FileEventSink", _Spy)
    handles = _fail_first_write(monkeypatch, OSError(errno.ENOSPC, "injected header failure"))
    runner = _full_runner(tmp_path, monkeypatch, "k4f3-ep-006")

    # When: running
    report = runner.run(_ok_flow)

    # Then: the handle was closed, the run succeeded, one stderr line
    assert report.status == "success"
    assert len(sinks) == 1
    assert sinks[0]._file is None
    assert handles[0].closed
    notices = _notices(capsys.readouterr().err)
    assert len(notices) == 1
    assert "injected header failure" in notices[0]


def test_file_sink_open_header_failure_closes_and_reraises__tc_k4f3_ep_007(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K4F3-EP-007: FileEventSink.open leaves no handle behind on header failure."""
    # Given: a sink whose header write fails
    handles = _fail_first_write(monkeypatch, OSError(errno.ENOSPC, "injected header failure"))
    sink = FileEventSink(tmp_path)

    # When: opening
    with pytest.raises(OSError, match="injected header failure"):
        sink.open("k4f3-ep-007")

    # Then: handle closed and released; close is a no-op
    assert sink._file is None
    assert handles[0].closed
    sink.close()


def test_file_sink_open_header_interrupt_closes__tc_k4f3_bv_006(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K4F3-BV-006: a KeyboardInterrupt during the header still releases the handle."""
    # Given: a header write interrupted by a BaseException
    handles = _fail_first_write(monkeypatch, KeyboardInterrupt())
    sink = FileEventSink(tmp_path)

    # When / Then: the interrupt propagates and the handle is closed
    with pytest.raises(KeyboardInterrupt):
        sink.open("k4f3-bv-006")
    assert sink._file is None
    assert handles[0].closed


def test_run_scoped_sink_releases_inner_on_open_failure__tc_k4f3_ep_008(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K4F3-EP-008: the run-scoped sink forgets an inner sink that failed to open."""
    # Given: a run-scoped sink whose header write fails
    _fail_first_write(monkeypatch, OSError(errno.ENOSPC, "injected header failure"))
    scoped = lifecycle._RunScopedFileEventSink(lambda: tmp_path / "logs")

    # When: opening
    with pytest.raises(OSError, match="injected header failure"):
        scoped.open("k4f3-ep-008")

    # Then: no inner sink is kept, so later emits and close are no-ops
    assert scoped._sink is None
    scoped.emit(Event.run_started(run_id="k4f3-ep-008"))
    scoped.close()


def test_second_run_after_failed_open_is_recorded__tc_k4f3_bv_005(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K4F3-BV-005: "no event log" lasts one run; the next run records normally."""
    # Given: one Runner whose first events header write fails
    _fail_first_write(monkeypatch, OSError(errno.ENOSPC, "injected header failure"))
    run_ids = iter(["k4f3-bv-005-a", "k4f3-bv-005-b"])
    runner = _full_runner(tmp_path, monkeypatch, "unused")
    runner._run_id_factory = lambda: next(run_ids)

    # When: running twice
    first = runner.run(_ok_flow)
    second = runner.run(_ok_flow)

    # Then: both succeed and the second run's log is complete
    assert first.status == "success"
    assert second.status == "success"
    names = [line.get("name") for line in _lines(tmp_path / "data" / "logs" / "events_k4f3-bv-005-b.jsonl")[1:]]
    assert names[0] == "run.started"
    assert names[-1] == "run.completed"


# --- R3: best-effort stderr ----------------------------------------------------


def test_best_effort_stderr_swallows_write_failure__tc_k4f3_bv_001(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-K4F3-BV-001: a failing stderr write is swallowed."""
    # Given: a stderr whose write fails
    monkeypatch.setattr(sys, "stderr", _BrokenStream())

    # When / Then: the helper returns normally
    assert _best_effort_stderr("message\n") is None


def test_best_effort_stderr_swallows_flush_failure__tc_k4f3_bv_002(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-K4F3-BV-002: a stream whose flush fails is harmless (no forced flush)."""
    # Given: a stderr whose flush fails
    stream = _FlushBrokenStream()
    monkeypatch.setattr(sys, "stderr", stream)

    # When: writing
    result = _best_effort_stderr("message\n")

    # Then: the text was written and no error escaped
    assert result is None
    assert stream.getvalue() == "message\n"


class _FailingFinalizer:
    def finalize(self, report: RunReport, config: RdeConfig) -> None:
        msg = "disk full"
        raise OSError(msg)


def _eio(fd: int) -> None:
    raise OSError(errno.EIO, "injected fsync failure")


def test_finalize_error_survives_fsync_and_stderr_failure__tc_k4f3_ep_009(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K4F3-EP-009: extends TC-K4F2-EP-002 with a failing stderr."""
    # Given: a failing finalizer, a failing fsync and a failing stderr
    runner = Runner(root=tmp_path, run_id_factory=lambda: "k4f3-ep-009", finalizer=_FailingFinalizer())
    monkeypatch.setattr(runner, "load_config", lambda source: RdeConfig())
    monkeypatch.setattr(runner, "resolve_mode", lambda config: ModeKind.invoice)
    monkeypatch.setattr(runner, "pre_validate", lambda config: None)
    monkeypatch.setattr(
        runner,
        "iterate",
        lambda target, mode, config: RunReport(
            run_id="k4f3-ep-009",
            status="success",
            flow_id="tests.k4f3",
            mode="invoice",
            started_at="2026-10-19T00:00:00",
            duration_ms=0.0,
            config_digest="sha256:test",
            iterations=[],
            warnings=[],
        ),
    )
    monkeypatch.setattr(os, "fsync", _eio)
    monkeypatch.setattr(sys, "stderr", _BrokenStream())

    # When: both end-of-run steps fail and stderr is unusable
    with pytest.raises(RdeInternalError) as exc_info:
        runner.run(lambda: None)

    # Then: the caller receives the finalizer's 5001
    assert exc_info.value.code == 5001
    assert "disk full" in exc_info.value.message
    assert _EVENT_LOG_NOTICE not in exc_info.value.message


def test_emit_failure_with_failing_stderr_keeps_user_error__tc_k4f3_ep_010(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K4F3-EP-010: neither the notice nor "iteration(s) failed" can change the verdict."""
    # Given: node.failed cannot be written and stderr is unusable
    monkeypatch.setattr(lifecycle, "FileEventSink", _failing_emit_sink("node.failed"))
    runner = _full_runner(tmp_path, monkeypatch, "k4f3-ep-010")
    monkeypatch.setattr(sys, "stderr", _BrokenStream())

    # When: running the failing flow
    report = runner.run(_failing_flow)

    # Then: the verdict is still the user's error
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == _USER_CODE
    assert f"ErrorCode={_USER_CODE}" in (tmp_path / "data" / "job.failed").read_text(encoding="utf-8")


def test_w1002_with_failing_stderr_still_records__tc_k4f3_ep_011(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K4F3-EP-011: the truncation notice is best-effort; the warning event is not lost."""
    # Given: a tiny cap and an unusable stderr
    sink = FileEventSink(tmp_path, max_bytes=1)
    sink.open("k4f3-ep-011")
    monkeypatch.setattr(sys, "stderr", _BrokenStream())

    # When: a node event exceeds the cap
    sink.emit(Event.node_started(run_id="k4f3-ep-011", node_id="n", call_id="c"))
    sink.close()

    # Then: the W1002 warning is in the file
    assert sink.path is not None
    lines = _lines(sink.path)
    assert lines[-1]["name"] == "warning"
    assert lines[-1]["payload"]["code"] == events_module._EVENTS_TRUNCATED_CODE


def test_w1001_with_failing_stderr_keeps_the_run__tc_k4f3_ep_014(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K4F3-EP-014: the W1001 stderr notice cannot turn a run into a 1002 failure."""
    # Given: a declared invoice mode that an ExcelInvoice input overrides, and an unusable stderr
    runner = _full_runner(tmp_path, monkeypatch, "k4f3-ep-014")
    with pd.ExcelWriter(tmp_path / "data" / "inputdata" / "sample_excel_invoice.xlsx") as writer:
        pd.DataFrame([["invoiceList_format_id"], [""]]).to_excel(writer, sheet_name="invoice_form", index=False, header=False)
    (tmp_path / "rdeconfig.yaml").write_text(yaml.safe_dump({"system": {"extended_mode": "invoice"}}), encoding="utf-8")
    request = build_run_request(flow=_ok_flow, custom_dataset_function=None, config=None, root=tmp_path, validate_only=True)
    monkeypatch.setattr(sys, "stderr", _BrokenStream())

    # When: validating
    report = runner.run(request)

    # Then: the pre-flight succeeds and the W1001 event is on disk
    assert report.status == "success"
    assert report.error is None
    lines = _lines(tmp_path / "data" / "logs" / "events_k4f3-ep-014.jsonl")
    warnings = [line for line in lines if line.get("name") == "warning" and line["payload"]["code"] == 1001]
    assert len(warnings) == 1



def test_w1001_event_emit_failure_keeps_the_run__tc_k4f3_ep_015(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K4F3-EP-015: the W1001 event is emitted through the best-effort wrapper.

    ``resolve_mode`` receives ``Runner._events``; if it ever reverts to the raw
    sink, a failing warning emit turns a valid run into a 1002 failure (the
    mutation the K4-F3 audit found unpinned).
    """
    # Given: a declared invoice mode overridden by an ExcelInvoice input, and a sink that fails on warnings
    sink = _RaisingSink(OSError(28, "warning emit failed"), fail_on="warning")
    runner = _full_runner(tmp_path, monkeypatch, "k4f3-ep-015", event_sink=sink)
    with pd.ExcelWriter(tmp_path / "data" / "inputdata" / "sample_excel_invoice.xlsx") as writer:
        pd.DataFrame([["invoiceList_format_id"], [""]]).to_excel(writer, sheet_name="invoice_form", index=False, header=False)
    (tmp_path / "rdeconfig.yaml").write_text(yaml.safe_dump({"system": {"extended_mode": "invoice"}}), encoding="utf-8")
    request = build_run_request(flow=_ok_flow, custom_dataset_function=None, config=None, root=tmp_path, validate_only=True)

    # When: validating
    report = runner.run(request)

    # Then: the W1001 emit failure is absorbed and the pre-flight still succeeds
    assert report.status == "success"
    assert report.error is None
    assert runner.event_sink is sink
