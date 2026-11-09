"""Mode-owned per-tile steps must not swallow the run interruption (RC1 F01 N1/N2).

Independent audit of RC1-INT-CORE (PASS WITH NOTES): two v1-derived mode steps
the Runner calls during a run wrapped the SIGTERM handler's
``RdeExecutionError(3004)`` like an ordinary failure, so under
``on_iteration_error: continue`` the interrupted tile became a per-tile
failure, the remaining tiles ran, the run ended ``partial`` and no
``job.failed`` was written:

* N1 ``modes/smarttable.py`` ``SmartTableInvoiceBuilder.build``: re-wrapped
  as ``StructuredError`` (code 1).
* N2 ``modes/rdeformat.py`` ``_copy_one``: wrapped as 3001, then attributed
  to the raw stage as 3005.

Each case materializes the frozen-corpus input of its mode (≥ 2 tiles) and
delivers a real SIGTERM inside the first tile's step.

EP table:
| TC | Mode / stage | Input | Expected |
|----|--------------|-------|----------|
| TC-RC1-N1-EP-001 | smarttable / tile invoice build | real SIGTERM in tile 0 | failed / 3004 / job.failed, later tiles not built |
| TC-RC1-N2-EP-001 | rdeformat / raw copy | real SIGTERM in tile 0 | failed / 3004 / job.failed, later tiles not copied |

Negative table (behaviour unchanged):
| TC | Mode / stage | Input | Expected |
|----|--------------|-------|----------|
| TC-RC1-N1-NEG-001 | smarttable / tile invoice build | RuntimeError in tile 0 | tile 0 failed code 1 (v1 wrapper text), others complete, partial, no job.failed |
| TC-RC1-N2-NEG-001 | rdeformat / raw copy | OSError in tile 0 | tile 0 failed 3005, others complete, partial, no job.failed |
| TC-RC1-N1-NEG-002 | smarttable / build wrapper | RdeExecutionError(3001) | still wrapped as StructuredError (only 3004 passes) |
| TC-RC1-N2-NEG-002 | rdeformat / ``_copy_one`` | RdeExecutionError(3001) | still wrapped as 3001 copy failure |
"""

from __future__ import annotations

import importlib
import os
import shutil
import signal
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit import flow
from rdetoolkit.errors import ERROR_CATALOG, RdeExecutionError
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.lifecycle import Runner
from tests.v2.contract.fixtures import _generate

_RUN_INTERRUPTED = 3004
_CONTINUE = {"execution": {"on_iteration_error": "continue"}}


@flow(id="tests.v2.modes.rc1_n1_n2.noop")
def _noop_flow() -> None:
    """Do nothing; the stage under test is mode-owned."""


@pytest.fixture
def sigterm_guard() -> Iterator[list[int]]:
    """Keep a stray SIGTERM from killing pytest; the Runner installs its own handler."""
    received: list[int] = []
    previous = signal.signal(signal.SIGTERM, lambda signum, _frame: received.append(signum))
    try:
        yield received
    finally:
        signal.signal(signal.SIGTERM, previous)


def _send_sigterm() -> None:
    os.kill(os.getpid(), signal.SIGTERM)


def _ordinary_rde_error() -> RdeExecutionError:
    error_cls: Any = RdeExecutionError
    return error_cls(code=3001, name=ERROR_CATALOG[3001].name, message="ordinary")


def _materialize(mode: str, tmp_path: Path) -> Path:
    root = tmp_path / mode
    _generate.materialize_sut_case(mode, root)
    return root / "data"


def _run(data: Path, **config: Any) -> RunReport:
    return Runner(root=data, event_sink=MemoryEventSink()).run(_noop_flow, **_CONTINUE, **config)


def _statuses(report: RunReport) -> list[tuple[Any, Any]]:
    return [(item.get("status"), (item.get("error") or {}).get("code")) for item in report.iterations]


def _first_call_does(action: Callable[[], None], original: Callable[..., Any]) -> tuple[Callable[..., Any], list[int]]:
    """Wrap ``original`` so that only its first call runs ``action`` first."""
    calls: list[int] = []

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        if len(calls) == 1:
            action()
        return original(*args, **kwargs)

    return wrapped, calls


def _raise(error: BaseException) -> Callable[[], None]:
    def action() -> None:
        raise error

    return action


def _live(module_name: str) -> Any:
    """Return a mode module as it is now.

    TC-EP-I5-003 reloads every mode module, which rebinds its classes, so the
    patched names are resolved when the test runs, never at import time.
    """
    return importlib.import_module(f"rdetoolkit.modes.{module_name}")


class _ShutilProxy:
    """Module-local ``shutil`` stand-in for ``modes.rdeformat`` (never global)."""

    def __init__(self, copy: Callable[..., Any]) -> None:
        self.copy = copy

    def __getattr__(self, name: str) -> Any:
        return getattr(shutil, name)


def _patch_rdeformat_copy(monkeypatch: pytest.MonkeyPatch, action: Callable[[], None]) -> list[int]:
    copy, calls = _first_call_does(action, shutil.copy)
    monkeypatch.setattr(_live("rdeformat"), "shutil", _ShutilProxy(copy))
    return calls


def _patch_smarttable_build(monkeypatch: pytest.MonkeyPatch, action: Callable[[], None]) -> list[int]:
    builder_cls = _live("smarttable").SmartTableInvoiceBuilder
    build, calls = _first_call_does(action, builder_cls._build)
    monkeypatch.setattr(builder_cls, "_build", build)
    return calls


def _assert_interrupted_and_stopped(report: RunReport, data: Path, calls: list[int]) -> None:
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == _RUN_INTERRUPTED
    assert (data / "job.failed").exists()
    # The run stops at the interruption: no later tile reaches the stage.
    assert calls == [1]


class TestSmartTableBuildInterruption:
    def test_sigterm_in_tile_invoice_build_stops_the_run__tc_rc1_n1_ep_001(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sigterm_guard: list[int]
    ) -> None:
        # Given: a multi-row SmartTable input, and a real SIGTERM inside the
        # first tile's invoice build, under the continue policy
        data = _materialize("smarttable", tmp_path)
        calls = _patch_smarttable_build(monkeypatch, _send_sigterm)

        # When: the run iterates its tiles
        report = _run(data)

        # Then: the interruption is the run's outcome, not a per-tile failure
        _assert_interrupted_and_stopped(report, data, calls)
        assert sigterm_guard == []

    def test_ordinary_build_failure_stays_a_tile_failure__tc_rc1_n1_neg_001(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Given: the first tile's invoice build fails in an ordinary way
        data = _materialize("smarttable", tmp_path)
        calls = _patch_smarttable_build(monkeypatch, _raise(RuntimeError("row broke")))

        # When
        report = _run(data)

        # Then: v1 tile-failure semantics are unchanged
        assert len(calls) == len(report.iterations) >= 2
        statuses = _statuses(report)
        assert statuses[0] == ("failed", 1)
        assert all(status == ("completed", None) for status in statuses[1:])
        assert "Failed to initialize invoice from SmartTable: row broke" in report.iterations[0]["error"]["message"]
        assert report.status == "partial"
        assert not (data / "job.failed").exists()

    def test_other_execution_error_is_still_wrapped__tc_rc1_n1_neg_002(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Given: the private build raising an RdeExecutionError that is not 3004
        builder_cls = _live("smarttable").SmartTableInvoiceBuilder

        def build(self: Any, **_kwargs: Any) -> None:
            raise _ordinary_rde_error()

        monkeypatch.setattr(builder_cls, "_build", build)

        # When / Then: the public wrapper keeps v1's StructuredError wrapping
        with pytest.raises(StructuredError, match=r"^Failed to initialize invoice from SmartTable: .*ordinary$"):
            builder_cls().build(
                rowfile=tmp_path / "r.csv",
                invoice_org=tmp_path / "i.json",
                invoice_schema_path=tmp_path / "s.json",
                dist_path=tmp_path / "d.json",
                metadata_def_path=tmp_path / "m.json",
                metadata_path=tmp_path / "md.json",
            )


class TestRdeFormatCopyInterruption:
    def test_sigterm_in_raw_copy_stops_the_run__tc_rc1_n2_ep_001(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sigterm_guard: list[int]
    ) -> None:
        # Given: a multi-tile RDEFormat input, and a real SIGTERM inside the
        # first tile's raw copy, under the continue policy
        data = _materialize("rdeformat", tmp_path)
        calls = _patch_rdeformat_copy(monkeypatch, _send_sigterm)

        # When
        report = _run(data, system={"extended_mode": "rdeformat"})

        # Then: not a 3001/3005 tile failure -- the run stops with 3004
        _assert_interrupted_and_stopped(report, data, calls)
        assert sigterm_guard == []

    def test_ordinary_copy_failure_stays_a_tile_failure__tc_rc1_n2_neg_001(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Given: the first raw copy fails in an ordinary way
        data = _materialize("rdeformat", tmp_path)
        _patch_rdeformat_copy(monkeypatch, _raise(OSError("disk full")))

        # When
        report = _run(data, system={"extended_mode": "rdeformat"})

        # Then: the 3001 copy failure is still attributed to the raw stage (3005)
        statuses = _statuses(report)
        assert len(statuses) >= 2
        assert statuses[0] == ("failed", 3005)
        assert all(status == ("completed", None) for status in statuses[1:])
        assert report.status == "partial"
        assert not (data / "job.failed").exists()

    def test_other_execution_error_is_still_wrapped__tc_rc1_n2_neg_002(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Given: a copy raising an RdeExecutionError that is not 3004
        source = tmp_path / "a.txt"
        source.write_text("a", encoding="utf-8")
        _patch_rdeformat_copy(monkeypatch, _raise(_ordinary_rde_error()))

        # When / Then: _copy_one keeps its catalogued 3001 copy failure
        with pytest.raises(RdeExecutionError) as exc_info:
            _live("rdeformat")._copy_one(source, tmp_path)
        assert exc_info.value.code == 3001
        assert "Failed to copy" in str(exc_info.value)
