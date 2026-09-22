"""ModeHandler raw-artifact strategy seam for Session I6-1 (ruling #5).

RDEFormat copies raw inputs by path component instead of by tile
(``processing/processors/files.py::RDEFormatFileCopier``), so raw publication
cannot stay hard-wired to one generic service. This session installs the seam
and keeps the generic behavior; Session I6-A implements the RDEFormat strategy
behind it.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-I6-1-EP-030 | seam used | handler returning a strategy | raw files land where the strategy puts them |
| TC-I6-1-EP-031 | default | the five built-in handlers | only RDEFormat returns a strategy (I6-A) |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-I6-1-EV-032 | no seam | handler returning ``None`` | the generic service publishes raw |
| TC-I6-1-EV-033 | no member | handler without the optional member | the generic service publishes raw |
| TC-I6-1-EV-034 | strategy fails | strategy raising ``OSError`` | run fails as ``ArtifactPublicationFailed`` (3005) |
| TC-I6-1-EV-035 | interruption | strategy raising ``RunInterrupted`` | 3004 propagates instead of becoming 3005 |
| TC-I6-1-EV-036 | installation | handler registered before Runner construction | the caller's handler survives |
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.core.flow import flow
from rdetoolkit.errors import ERROR_CATALOG, RdeExecutionError
from rdetoolkit.modes.install import install_default_handlers
from rdetoolkit.modes.invoice import InvoiceModeHandler
from rdetoolkit.modes.protocol import PlanningContext
from rdetoolkit.modes.registry import clear, handler_for, register
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.planner import ExecutionPlan, TilePlan, create_common_tiles
from rdetoolkit.types import InputPaths
from tests.v2.contract.fixtures import _generate

_ARTIFACT_PUBLICATION_FAILED = 3005
_RUN_INTERRUPTED = 3004


@flow
def _noop_flow(paths: InputPaths) -> None:
    """Consume the tile without writing anything."""
    assert paths.inputdata.is_dir()


class _AttachmentStrategy:
    """Publish raw inputs into ``attachment/`` instead of ``raw/``."""

    def copy(
        self,
        source_files: tuple[Path, ...],
        *,
        raw_dir: Path,
        nonshared_raw_dir: Path,
        config: Any,
        smarttable: bool = False,
        data_root: Path,
    ) -> None:
        """Redirect every raw input to the tile attachment directory."""
        _ = (nonshared_raw_dir, config, smarttable, data_root)
        destination = raw_dir.parent / "attachment"
        destination.mkdir(parents=True, exist_ok=True)
        for source in source_files:
            (destination / source.name).write_bytes(source.read_bytes())


class _FailingStrategy:
    """Fail publication the way a full disk would."""

    def copy(self, source_files: tuple[Path, ...], **kwargs: Any) -> None:
        """Raise a real I/O error instead of publishing."""
        _ = (source_files, kwargs)
        msg = "no space left on device"
        raise OSError(msg)


class _InterruptingStrategy:
    """Raise the Runner's own termination error from inside publication."""

    def copy(self, source_files: tuple[Path, ...], **kwargs: Any) -> None:
        """Simulate a SIGTERM arriving while artifacts are published."""
        _ = (source_files, kwargs)
        error_def = ERROR_CATALOG[_RUN_INTERRUPTED]
        error_cls: Any = RdeExecutionError
        raise error_cls(code=_RUN_INTERRUPTED, name=error_def.name, message=error_def.message_template)


class _StrategyHandler:
    """Invoice handler that installs a mode-specific raw strategy."""

    kind = ModeKind.invoice

    def __init__(self, strategy: Any) -> None:
        self._strategy = strategy

    def create_tiles(self, context: PlanningContext) -> Iterable[TilePlan]:
        """Delegate tile creation to the shared body."""
        return create_common_tiles(self.kind, context)

    def raw_copy_strategy(self, plan: ExecutionPlan) -> Any:
        """Return this handler's strategy."""
        _ = plan
        return self._strategy


class _SeamlessHandler:
    """Invoice handler that predates the seam and never declares it."""

    kind = ModeKind.invoice

    def create_tiles(self, context: PlanningContext) -> Iterable[TilePlan]:
        """Delegate tile creation to the shared body."""
        return create_common_tiles(self.kind, context)


@pytest.fixture
def restore_handlers() -> Iterator[None]:
    """Reinstall the production handlers after a test replaces one.

    The registry is cleared first: ``install_default_handlers`` deliberately
    keeps an already-registered handler (TC-I6-1-EV-036), so reinstalling
    alone would leak this test's handler into the rest of the session.
    """
    try:
        yield
    finally:
        clear()
        install_default_handlers()


def _run(root: Path, monkeypatch: pytest.MonkeyPatch, handler: Any = None) -> Any:
    """Run one invoice tile, optionally after replacing the invoice handler.

    Registering after the Runner exists is a convenience, not a requirement:
    ``install_default_handlers`` only fills modes that have no handler yet, so
    a handler registered beforehand survives construction (TC-I6-1-EV-036).
    """
    monkeypatch.chdir(root)
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
    )
    if handler is not None:
        register(ModeKind.invoice, handler)
    return runner.run(_noop_flow, system={"extended_mode": "invoice", "save_raw": True})


def _prepare(tmp_path: Path) -> Path:
    root = tmp_path / "invoice"
    _generate.materialize_sut_case("invoice", root)
    return root


def _names(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir())


def test_mode_strategy_changes_raw_placement__tc_i6_1_ep_030(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    restore_handlers: None,
) -> None:
    """TC-I6-1-EP-030: a handler-provided strategy owns raw publication."""
    # Given: an invoice handler that publishes raw inputs to attachment/
    _ = restore_handlers
    root = _prepare(tmp_path)

    # When: running with the raw gate enabled
    report = _run(root, monkeypatch, _StrategyHandler(_AttachmentStrategy()))

    # Then: the strategy's placement replaced the generic one
    assert report.status == "success"
    assert _names(root / "data" / "attachment") == ["invoice_input.txt"]
    assert _names(root / "data" / "raw") == []


def test_builtin_handlers_install_no_strategy__tc_i6_1_ep_031() -> None:
    """TC-I6-1-EP-031: only RDEFormat overrides raw publication.

    Session I6-A filled the seam for RDEFormat (ruling #1), so the invariant is
    no longer "nobody uses it" but the sharper "exactly one mode uses it": every
    other built-in handler must still resolve to ``RawArtifactService``.
    """
    # Given: the production handler set
    from rdetoolkit.modes.excelinvoice import ExcelInvoiceModeHandler
    from rdetoolkit.modes.multidatatile import MultiDataTileModeHandler
    from rdetoolkit.modes.rdeformat import RdeFormatModeHandler, RdeFormatRawCopyStrategy
    from rdetoolkit.modes.smarttable import SmartTableModeHandler

    generic_handlers = (
        InvoiceModeHandler(),
        ExcelInvoiceModeHandler(),
        MultiDataTileModeHandler(),
        SmartTableModeHandler(),
    )

    # When/Then: four of the five built-in handlers keep the generic service
    for handler in generic_handlers:
        assert handler.raw_copy_strategy(None) is None  # type: ignore[arg-type]

    # And: RDEFormat is the single mode whose v1 copier is component-based
    assert isinstance(
        RdeFormatModeHandler().raw_copy_strategy(None),  # type: ignore[arg-type]
        RdeFormatRawCopyStrategy,
    )


def test_handler_returning_none_uses_the_generic_service__tc_i6_1_ev_032(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    restore_handlers: None,
) -> None:
    """TC-I6-1-EV-032: an explicit ``None`` keeps the generic raw service."""
    # Given: a handler that declares the seam but declines it
    _ = restore_handlers
    root = _prepare(tmp_path)

    # When: running with the raw gate enabled
    report = _run(root, monkeypatch, _StrategyHandler(None))

    # Then: the generic service published the raw copy
    assert report.status == "success"
    assert _names(root / "data" / "raw") == ["invoice_input.txt"]


def test_handler_without_the_member_uses_the_generic_service__tc_i6_1_ev_033(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    restore_handlers: None,
) -> None:
    """TC-I6-1-EV-033: the seam is optional, so an older handler still works."""
    # Given: a handler that never heard of the seam
    _ = restore_handlers
    root = _prepare(tmp_path)

    # When: running with the raw gate enabled
    report = _run(root, monkeypatch, _SeamlessHandler())

    # Then: the generic service published the raw copy
    assert report.status == "success"
    assert _names(root / "data" / "raw") == ["invoice_input.txt"]


def test_strategy_failure_is_a_framework_error__tc_i6_1_ev_034(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    restore_handlers: None,
) -> None:
    """TC-I6-1-EV-034: a failing strategy is attributed to the output stage."""
    # Given: a strategy that fails the way a full disk would
    _ = restore_handlers
    root = _prepare(tmp_path)

    # When: running with the raw gate enabled
    report = _run(root, monkeypatch, _StrategyHandler(_FailingStrategy()))

    # Then: the run fails as a publication error, not as a node error
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == _ARTIFACT_PUBLICATION_FAILED
    job_failed = (root / "data" / "job.failed").read_text(encoding="utf-8")
    assert job_failed.splitlines()[0] == f"ErrorCode={_ARTIFACT_PUBLICATION_FAILED}"
    assert json.loads((root / "data" / "invoice" / "invoice.json").read_text(encoding="utf-8"))


def test_run_interruption_is_not_masked_by_publication__tc_i6_1_ev_035(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    restore_handlers: None,
) -> None:
    """TC-I6-1-EV-035: a termination signal during publication stays 3004."""
    # Given: a strategy that raises the Runner's termination error
    _ = restore_handlers
    root = _prepare(tmp_path)

    # When: running with the raw gate enabled
    report = _run(root, monkeypatch, _StrategyHandler(_InterruptingStrategy()))

    # Then: the interruption keeps its own code instead of being republished
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == _RUN_INTERRUPTED
    assert report.error["code"] != _ARTIFACT_PUBLICATION_FAILED


def test_runner_construction_keeps_a_registered_handler__tc_i6_1_ev_036(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    restore_handlers: None,
) -> None:
    """TC-I6-1-EV-036: installing the built-ins never displaces a caller's handler."""
    # Given: a handler registered before any Runner exists
    _ = restore_handlers
    root = _prepare(tmp_path)
    handler = _StrategyHandler(_AttachmentStrategy())
    register(ModeKind.invoice, handler)

    # When: constructing a Runner, which installs the built-in handlers
    monkeypatch.chdir(root)
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
    )
    report = runner.run(_noop_flow, system={"extended_mode": "invoice", "save_raw": True})

    # Then: the caller's handler is still registered and still owns publication
    assert handler_for(ModeKind.invoice) is handler
    assert report.status == "success"
    assert _names(root / "data" / "attachment") == ["invoice_input.txt"]
