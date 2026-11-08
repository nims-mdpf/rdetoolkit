"""Run interruption (3004) must survive library-owned failure tolerance (RC1 F01).

Review ``interrogate_v2.0.0rc1`` F01: the SIGTERM handler raises
``RdeExecutionError(3004)``, but the optional thumbnail stage
(``except Exception: return``) and the optional description stage
(``contextlib.suppress(Exception)``) swallowed it, so an interrupted run was
finalized as ``success`` without ``job.failed``. The audit of the other broad
catches reachable during a run (raw copy, tile-output validation, pre/post
validation, repr capture, annotation resolution) is pinned here as well.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-RC1-F01-EP-001 | real SIGTERM | inside the thumbnail stage | failed / 3004 / job.failed |
| TC-RC1-F01-EP-002 | real SIGTERM | inside the description updater | failed / 3004 / job.failed |
| TC-RC1-F01-EP-003 | real SIGTERM | inside the raw copy | 3004, not the 3001 copy wrapper (published as 3005 by the raw-stage guard) |
| TC-RC1-F01-EP-004 | real SIGTERM | inside a node-input repr capture | failed / 3004 |
| TC-RC1-F01-EP-005 | real SIGTERM | inside the flow-output repr capture | failed / 3004 |
| TC-RC1-F01-EP-006 | real SIGTERM | inside pre_validate | 3004, not the 4003 validation wrapper |
| TC-RC1-F01-EP-007 | real SIGTERM | inside post_validate | 3004, not the 4003 validation wrapper |
| TC-RC1-F01-EP-008 | 3004 raised | inside a precompleted-tile validation | 3004 propagates, not 4003 |
| TC-RC1-F01-EP-009 | 3004 raised | inside each annotation resolver | 3004 propagates |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-RC1-F01-NEG-001 | ordinary failure | RuntimeError in the thumbnail stage | success, no job.failed |
| TC-RC1-F01-NEG-002 | ordinary failure | RuntimeError in the description updater | success, no job.failed |
| TC-RC1-F01-NEG-003 | same class, other code | RdeExecutionError(3001) in thumbnails | tolerated (returns None) |
| TC-RC1-F01-NEG-004 | same class, other code | RdeExecutionError(3001) in description | tolerated (returns None) |
| TC-RC1-F01-NEG-005 | ordinary failure | OSError in the raw copy | 3001 wrapper unchanged |
| TC-RC1-F01-NEG-006 | ordinary failure | repr raising ValueError | repr_head None, run succeeds |
| TC-RC1-F01-NEG-007 | ordinary failure | unresolvable annotation | resolvers still return {} |
| TC-RC1-F01-BV-001 | predicate | 3004 / 3001 / other RdeError with 3004 / plain error | only RdeExecutionError 3004 |
| TC-RC1-F01-BV-001b | single source | every tolerant module | uses ``rdetoolkit._interrupt.is_run_interrupted`` itself |
| TC-RC1-F01-BV-001c | single source | AST scan of the package | exactly one definition |

The event-log helpers (``report/events.py``) are tabled further down.
"""

from __future__ import annotations

import ast
import importlib
import json
import os
import signal
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit import _interrupt as interrupt_module
from rdetoolkit import flow, node
from rdetoolkit.core import calllog, injection
from rdetoolkit.core import node as node_module
from rdetoolkit.domain.artifacts import ImageArtifactService, RawArtifactService
from rdetoolkit.domain.invoice_service import INVOICE_STEP_DESCRIPTION, InvoiceService
from rdetoolkit.errors import ERROR_CATALOG, RdeError, RdeExecutionError, RdeValidationError
from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner import executor as executor_module
from rdetoolkit.runner import lifecycle as lifecycle_module
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.templates import base as template_base
from rdetoolkit.types import RdeConfig

_RUN_INTERRUPTED = 3004


def _interrupt_error() -> RdeExecutionError:
    error_def = ERROR_CATALOG[_RUN_INTERRUPTED]
    error_cls: Any = RdeExecutionError
    return error_cls(code=_RUN_INTERRUPTED, name=error_def.name, message=error_def.message_template)


def _ordinary_rde_error() -> RdeExecutionError:
    error_def = ERROR_CATALOG[3001]
    error_cls: Any = RdeExecutionError
    return error_cls(code=3001, name=error_def.name, message="ordinary")


def _send_sigterm(*_args: Any, **_kwargs: Any) -> None:
    os.kill(os.getpid(), signal.SIGTERM)


@pytest.fixture
def sigterm_guard() -> Iterator[list[int]]:
    """Keep a stray SIGTERM from killing pytest; the Runner installs its own handler."""
    received: list[int] = []
    previous = signal.signal(signal.SIGTERM, lambda signum, _frame: received.append(signum))
    try:
        yield received
    finally:
        signal.signal(signal.SIGTERM, previous)


def _seed(root: Path) -> Path:
    for name in ("inputdata", "invoice", "tasksupport"):
        (root / name).mkdir()
    (root / "inputdata" / "a.txt").write_text("a", encoding="utf-8")
    invoice = {
        "datasetId": "rc1-f01",
        "basic": {"dateSubmitted": "2026-11-08", "dataOwnerId": "0" * 56, "dataName": "rc1-f01"},
    }
    (root / "invoice" / "invoice.json").write_text(json.dumps(invoice), encoding="utf-8")
    (root / "tasksupport" / "invoice.schema.json").write_text(json.dumps({"properties": {}}), encoding="utf-8")
    return root


@flow(id="tests.v2.runner.rc1_f01.noop")
def _noop_flow() -> None:
    """Do nothing; the stage under test is library-owned."""


def _run(root: Path, target: Callable[..., Any] = _noop_flow, **config: Any) -> RunReport:
    return Runner(root=root, event_sink=MemoryEventSink()).run(target, **config)


def _assert_interrupted(report: RunReport, root: Path) -> None:
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == _RUN_INTERRUPTED
    assert (root / "job.failed").exists()


def _counting(action: Callable[..., None]) -> tuple[Callable[..., None], list[int]]:
    calls: list[int] = []

    def wrapped(*args: Any, **kwargs: Any) -> None:
        calls.append(1)
        action(*args, **kwargs)

    return wrapped, calls


def _raise_runtime(*_args: Any, **_kwargs: Any) -> None:
    msg = "converter broke"
    raise RuntimeError(msg)


_THUMBNAIL_CONFIG = {"system": {"save_thumbnail_image": True, "feature_description": False}}
_DESCRIPTION_CONFIG = {"system": {"save_thumbnail_image": False, "feature_description": True}}


class TestOptionalStagesReraiseInterruption:
    def test_sigterm_in_thumbnail_stage_fails_the_run__tc_rc1_f01_ep_001(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sigterm_guard: list[int]
    ) -> None:
        # Given: the thumbnail converter receives a real SIGTERM while it runs
        root = _seed(tmp_path)
        converter, calls = _counting(_send_sigterm)
        monkeypatch.setattr("rdetoolkit.domain.artifacts.img2thumb.copy_images_to_thumbnail", converter)

        # When: the run reaches the optional thumbnail stage
        report = _run(root, **_THUMBNAIL_CONFIG)

        # Then: the interruption is the run's outcome, not a tolerated failure
        assert calls == [1]
        _assert_interrupted(report, root)
        assert sigterm_guard == []

    def test_sigterm_in_description_stage_fails_the_run__tc_rc1_f01_ep_002(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sigterm_guard: list[int]
    ) -> None:
        # Given: the description updater receives a real SIGTERM while it runs
        root = _seed(tmp_path)
        updater, calls = _counting(_send_sigterm)
        monkeypatch.setattr("rdetoolkit.domain.invoice_service.update_description_with_features", updater)

        # When: the run reaches the optional description stage
        report = _run(root, **_DESCRIPTION_CONFIG)

        # Then: the interruption is the run's outcome
        assert calls == [1]
        _assert_interrupted(report, root)
        assert sigterm_guard == []

    def test_ordinary_thumbnail_failure_stays_tolerated__tc_rc1_f01_neg_001(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Given: the thumbnail converter fails in an ordinary way
        root = _seed(tmp_path)
        converter, calls = _counting(_raise_runtime)
        monkeypatch.setattr("rdetoolkit.domain.artifacts.img2thumb.copy_images_to_thumbnail", converter)

        # When: the run reaches the thumbnail stage
        report = _run(root, **_THUMBNAIL_CONFIG)

        # Then: v1 failure tolerance is unchanged
        assert calls == [1]
        assert report.status == "success"
        assert report.error is None
        assert not (root / "job.failed").exists()

    def test_ordinary_description_failure_stays_tolerated__tc_rc1_f01_neg_002(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Given: the description updater fails in an ordinary way
        root = _seed(tmp_path)
        updater, calls = _counting(_raise_runtime)
        monkeypatch.setattr("rdetoolkit.domain.invoice_service.update_description_with_features", updater)

        # When: the run reaches the description stage
        report = _run(root, **_DESCRIPTION_CONFIG)

        # Then: v1 failure tolerance is unchanged
        assert calls == [1]
        assert report.status == "success"
        assert not (root / "job.failed").exists()

    def test_other_execution_error_code_in_thumbnails_is_tolerated__tc_rc1_f01_neg_003(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Given: the converter raises an RdeExecutionError that is not 3004
        def converter(*_args: Any, **_kwargs: Any) -> None:
            raise _ordinary_rde_error()

        monkeypatch.setattr("rdetoolkit.domain.artifacts.img2thumb.copy_images_to_thumbnail", converter)
        config = RdeConfig(system={"save_thumbnail_image": True})

        # When / Then: the service swallows it (only the code decides)
        assert ImageArtifactService().generate(main_image_dir=tmp_path, thumbnail_dir=tmp_path, config=config) is None

    def test_interrupt_in_thumbnails_propagates_unchanged__tc_rc1_f01_ep_001b(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Given: the converter raises the Runner's interruption error itself
        interrupt = _interrupt_error()

        def converter(*_args: Any, **_kwargs: Any) -> None:
            raise interrupt

        monkeypatch.setattr("rdetoolkit.domain.artifacts.img2thumb.copy_images_to_thumbnail", converter)
        config = RdeConfig(system={"save_thumbnail_image": True})

        # When / Then: the very same exception object propagates
        with pytest.raises(RdeExecutionError) as exc_info:
            ImageArtifactService().generate(main_image_dir=tmp_path, thumbnail_dir=tmp_path, config=config)
        assert exc_info.value is interrupt

    def test_other_execution_error_code_in_description_is_tolerated__tc_rc1_f01_neg_004(self) -> None:
        # Given: a description updater raising an RdeExecutionError that is not 3004
        def updater() -> None:
            raise _ordinary_rde_error()

        config = RdeConfig(system={"feature_description": True})

        # When / Then: the step returns normally
        assert (
            InvoiceService().apply_step(
                INVOICE_STEP_DESCRIPTION, config=config, dataset_paths=_FakeDatasetPaths(), feature_updater=updater
            )
            is None
        )

    def test_interrupt_in_description_propagates_unchanged__tc_rc1_f01_ep_002b(self) -> None:
        # Given: a description updater raising the interruption error
        interrupt = _interrupt_error()

        def updater() -> None:
            raise interrupt

        config = RdeConfig(system={"feature_description": True})

        # When / Then: it propagates unchanged
        with pytest.raises(RdeExecutionError) as exc_info:
            InvoiceService().apply_step(
                INVOICE_STEP_DESCRIPTION, config=config, dataset_paths=_FakeDatasetPaths(), feature_updater=updater
            )
        assert exc_info.value is interrupt


class _FakeOutputPaths:
    invoice = Path("unused")


class _FakeDatasetPaths:
    """Only ``output_paths.invoice`` is read before the description step."""

    output_paths = _FakeOutputPaths()


class TestAuditedCatchesReraiseInterruption:
    def test_sigterm_in_raw_copy_keeps_code_3004__tc_rc1_f01_ep_003(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sigterm_guard: list[int]
    ) -> None:
        # Given: a real SIGTERM arrives while raw inputs are copied
        root = _seed(tmp_path)
        copier, calls = _counting(_send_sigterm)
        monkeypatch.setattr("rdetoolkit.domain.artifacts.shutil.copy2", copier)

        # When: the run publishes raw/
        report = _run(root, system={"save_raw": True})

        # Then: the copy wrapper does not turn the interruption into 3001,
        # which the raw-stage guard would publish as 3005
        assert calls == [1]
        _assert_interrupted(report, root)
        assert sigterm_guard == []

    def test_ordinary_raw_copy_failure_keeps_the_3001_wrapper__tc_rc1_f01_neg_005(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Given: shutil.copy2 fails with an ordinary OSError
        source = tmp_path / "a.txt"
        source.write_text("a", encoding="utf-8")

        def copier(*_args: Any, **_kwargs: Any) -> None:
            raise OSError("disk full")

        monkeypatch.setattr("rdetoolkit.domain.artifacts.shutil.copy2", copier)

        # When / Then: the catalogued 3001 wrapper is unchanged
        with pytest.raises(RdeExecutionError) as exc_info:
            RawArtifactService().copy(
                (source,),
                raw_dir=tmp_path / "raw",
                nonshared_raw_dir=tmp_path / "nonshared_raw",
                config=RdeConfig(system={"save_raw": True}),
            )
        assert exc_info.value.code == 3001

    def test_sigterm_in_node_input_repr_fails_the_run__tc_rc1_f01_ep_004(self, tmp_path: Path, sigterm_guard: list[int]) -> None:
        # Given: a node input whose repr receives a real SIGTERM while captured
        root = _seed(tmp_path)
        value = _SigtermOnRepr()

        @node(id="tests.v2.runner.rc1_f01.consume")
        def consume(item: object) -> None:
            _ = item

        @flow(id="tests.v2.runner.rc1_f01.repr_input")
        def repr_input_flow() -> None:
            consume(value)

        # When: the call log captures repr heads (provenance.repr_head: on)
        report = _run(root, repr_input_flow, provenance={"repr_head": "on"})

        # Then: the interruption is not swallowed as "no repr"
        assert value.calls == 1
        _assert_interrupted(report, root)
        assert sigterm_guard == []

    def test_sigterm_in_flow_output_repr_fails_the_run__tc_rc1_f01_ep_005(self, tmp_path: Path, sigterm_guard: list[int]) -> None:
        # Given: a flow returning a value whose repr receives a real SIGTERM
        root = _seed(tmp_path)
        value = _SigtermOnRepr()

        @flow(id="tests.v2.runner.rc1_f01.repr_output")
        def repr_output_flow() -> object:
            return value

        # When: the tile summarizes the flow outputs
        report = _run(root, repr_output_flow, provenance={"repr_head": "on"})

        # Then: the interruption is the outcome
        assert value.calls == 1
        _assert_interrupted(report, root)
        assert sigterm_guard == []

    def test_ordinary_repr_failure_is_still_tolerated__tc_rc1_f01_neg_006(self) -> None:
        # Given: a value whose repr raises an ordinary error
        class BrokenRepr:
            def __repr__(self) -> str:
                raise ValueError("no repr")

        # When / Then: both capture helpers still fall back to None
        assert calllog._safe_repr_head(BrokenRepr(), enabled=True, length=10) is None
        from rdetoolkit.runner import execute

        assert execute._safe_repr_head(BrokenRepr(), enabled=True, length=10) is None

    def test_sigterm_in_pre_validate_keeps_code_3004__tc_rc1_f01_ep_006(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sigterm_guard: list[int]
    ) -> None:
        # Given: a real SIGTERM arrives during the invoice pre-validation
        root = _seed(tmp_path)
        validator, calls = _counting(_send_sigterm)
        monkeypatch.setattr("rdetoolkit.runner.lifecycle.invoice_validate", validator)

        # When: the run validates its invoice before iterating
        report = _run(root)

        # Then: the validation wrapper does not turn it into 4003
        assert calls == [1]
        _assert_interrupted(report, root)
        assert sigterm_guard == []

    def test_sigterm_in_post_validate_keeps_code_3004__tc_rc1_f01_ep_007(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sigterm_guard: list[int]
    ) -> None:
        # Given: a real SIGTERM arrives during the post-iteration tile validation
        root = _seed(tmp_path)
        validator, calls = _counting(_send_sigterm)
        monkeypatch.setattr("rdetoolkit.runner.lifecycle.validate_tile_outputs", validator)

        # When: the run validates the completed tile
        report = _run(root)

        # Then: the validation wrapper does not turn it into 4003
        assert calls == [1]
        _assert_interrupted(report, root)
        assert sigterm_guard == []

    def test_interrupt_in_precompleted_validation_propagates__tc_rc1_f01_ep_008(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Given: the precompleted-tile validation raises the interruption error
        interrupt = _interrupt_error()

        def validator(**_kwargs: Any) -> None:
            raise interrupt

        monkeypatch.setattr(executor_module, "validate_tile_outputs", validator)
        tile: Any = _FakeTile()

        # When / Then: the interruption propagates instead of becoming 4003
        with pytest.raises(RdeExecutionError) as exc_info:
            executor_module._validate_precompleted_tile(tile)
        assert exc_info.value is interrupt

    def test_ordinary_precompleted_validation_failure_is_wrapped__tc_rc1_f01_neg_005b(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Given: the precompleted-tile validation fails in an ordinary way
        def validator(**_kwargs: Any) -> None:
            raise OSError("missing")

        monkeypatch.setattr(executor_module, "validate_tile_outputs", validator)
        tile: Any = _FakeTile()

        # When / Then: the catalogued validation wrapper is unchanged
        with pytest.raises(RdeValidationError) as exc_info:
            executor_module._validate_precompleted_tile(tile)
        assert exc_info.value.code == 4003


class _FakeTileDirs:
    invoice = Path("invoice")
    meta = Path("meta")
    tasksupport = Path("tasksupport")


class _FakeTile:
    out = _FakeTileDirs()
    paths = _FakeTileDirs()


class _SigtermOnRepr:
    """Deliver one real SIGTERM from inside ``repr``."""

    def __init__(self) -> None:
        self.calls = 0

    def __repr__(self) -> str:
        self.calls += 1
        if self.calls == 1:
            _send_sigterm()
        return "sigterm-on-repr"


_RESOLVERS: tuple[tuple[str, Callable[[Callable[..., Any]], dict[str, Any]]], ...] = (
    ("core.calllog", calllog.CallLogRecorder._resolve_hints),
    ("core.node", node_module._resolve_type_hints),
    ("core.injection", injection._resolve_type_hints),
    ("templates.base", template_base._resolved_hints),
)


class TestAnnotationResolversReraiseInterruption:
    @pytest.mark.parametrize(("label", "resolver"), _RESOLVERS, ids=[label for label, _ in _RESOLVERS])
    def test_interrupt_during_resolution_propagates__tc_rc1_f01_ep_009(
        self, label: str, resolver: Callable[[Callable[..., Any]], dict[str, Any]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Given: typing.get_type_hints is interrupted while it evaluates annotations
        interrupt = _interrupt_error()

        def interrupted(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise interrupt

        monkeypatch.setattr("typing.get_type_hints", interrupted)

        # When / Then: the resolver does not swallow it as "no hints"
        with pytest.raises(RdeExecutionError) as exc_info:
            resolver(_unresolvable)
        assert exc_info.value is interrupt, label

    @pytest.mark.parametrize(("label", "resolver"), _RESOLVERS, ids=[label for label, _ in _RESOLVERS])
    def test_unresolvable_annotation_still_resolves_to_empty__tc_rc1_f01_neg_007(
        self, label: str, resolver: Callable[[Callable[..., Any]], dict[str, Any]]
    ) -> None:
        # Given: a function whose string annotation names an undefined type
        # When / Then: the ordinary NameError is still tolerated
        assert resolver(_unresolvable) == {}, label


def _unresolvable(value: UndefinedRc1Type) -> None:  # type: ignore[name-defined]  # noqa: F821
    _ = value


#: Every module whose failure tolerance must let the interruption through.
#: Operator ruling (B), 2026-11-09: exactly one predicate exists, in the
#: shared kernel, and each of these modules uses that very function object.
_PREDICATE_USERS = (
    "rdetoolkit.core.calllog",
    "rdetoolkit.core.injection",
    "rdetoolkit.core.node",
    "rdetoolkit.templates.base",
    "rdetoolkit.domain.artifacts",
    "rdetoolkit.domain.invoice_service",
    "rdetoolkit.report.events",
    "rdetoolkit.runner.execute",
    "rdetoolkit.runner.executor",
    "rdetoolkit.runner.lifecycle",
    "rdetoolkit.modes.rdeformat",
    "rdetoolkit.modes.smarttable",
)

_SRC_ROOT = Path(interrupt_module.__file__).parent


class TestInterruptPredicate:
    def test_only_execution_error_3004_is_an_interruption__tc_rc1_f01_bv_001(self) -> None:
        # Given: the boundary values around the interruption identity
        predicate = interrupt_module.is_run_interrupted
        other_class: Any = RdeValidationError
        same_code_other_class = other_class(code=_RUN_INTERRUPTED, name="x", message="x")
        plain_rde: Any = RdeError

        # When / Then: only RdeExecutionError carrying 3004 qualifies
        assert predicate(_interrupt_error()) is True
        assert predicate(_ordinary_rde_error()) is False
        assert predicate(same_code_other_class) is False
        assert predicate(plain_rde(code=_RUN_INTERRUPTED, name="x", message="x")) is False
        assert predicate(RuntimeError("x")) is False
        assert predicate(KeyboardInterrupt()) is False

    @pytest.mark.parametrize("module_name", _PREDICATE_USERS)
    def test_every_user_shares_the_one_predicate__tc_rc1_f01_bv_001b(self, module_name: str) -> None:
        # Given: a module that tolerates failures during a run
        module = importlib.import_module(module_name)

        # When / Then: it uses the shared-kernel function object itself
        assert module.is_run_interrupted is interrupt_module.is_run_interrupted
        assert not hasattr(module, "_is_run_interrupted")

    def test_no_other_definition_exists_in_the_package__tc_rc1_f01_bv_001c(self) -> None:
        # Given: every source module of the installed package
        definitions: list[str] = []
        for path in sorted(_SRC_ROOT.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for item in ast.walk(tree):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and "run_interrupted" in item.name:
                    if item.name != "_raise_run_interrupted":
                        definitions.append(f"{path.relative_to(_SRC_ROOT).as_posix()}::{item.name}")

        # When / Then: the predicate is defined exactly once, in rdetoolkit/_interrupt.py
        assert definitions == ["_interrupt.py::is_run_interrupted"]


# --------------------------------------------------------------------------
# report/events.py (operator ruling 2026-11-09, (B)): the best-effort stderr
# writer and the header-failure close path tolerated every exception, so a
# SIGTERM landing inside them was swallowed.
#
# EP / BV / negative table:
# | TC | Class | Input | Expected |
# |----|-------|-------|----------|
# | TC-RC1-F01-EP-010 | real SIGTERM | inside the W1001 stderr write of a run | failed / 3004 / job.failed |
# | TC-RC1-F01-EP-011 | 3004 raised | inside ``_best_effort_stderr``'s write | same object propagates |
# | TC-RC1-F01-EP-012 | real handler | SIGTERM inside the header-failure close | 3004 propagates (not the header OSError) |
# | TC-RC1-F01-EP-013 | Runner guard | same, through ``_BestEffortEventSink.open`` | 3004 propagates, sink not muted |
# | TC-RC1-F01-NEG-008 | ordinary failure | OSError from stderr.write | swallowed, returns None |
# | TC-RC1-F01-NEG-009 | ordinary failure | OSError from the close after a header failure | header OSError re-raised, handle released |
# | TC-RC1-F01-NEG-010 | other code | RdeExecutionError(3001) from stderr.write | swallowed |
# --------------------------------------------------------------------------


class _Writer:
    """``sys.stderr`` double whose ``write`` runs one action."""

    def __init__(self, action: Callable[[str], None]) -> None:
        self.action = action
        self.calls: list[str] = []

    def write(self, message: str) -> int:
        self.calls.append(message)
        self.action(message)
        return len(message)

    def flush(self) -> None:
        """Nothing is buffered."""


class _HeaderFailingHandle:
    """File handle whose header write fails and whose close runs one action."""

    def __init__(self, on_close: Callable[[], None]) -> None:
        self.on_close = on_close
        self.closed_calls = 0

    def write(self, _line: str) -> int:
        msg = "No space left on device"
        raise OSError(msg)

    def flush(self) -> None:
        """Never reached: the write fails first."""

    def close(self) -> None:
        self.closed_calls += 1
        self.on_close()


@pytest.fixture
def real_interrupt_handler() -> Iterator[None]:
    """Install the Runner's own SIGTERM handler outside a run, then restore."""
    previous = signal.signal(signal.SIGTERM, lifecycle_module._raise_run_interrupted)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def _header_failing_sink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, on_close: Callable[[], None]) -> tuple[Any, _HeaderFailingHandle]:
    from rdetoolkit.report.events import FileEventSink  # noqa: PLC0415

    handle = _HeaderFailingHandle(on_close)
    original_open = Path.open
    events_dir = tmp_path / "logs"

    def fake_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self.parent == events_dir:
            return handle
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fake_open)
    return FileEventSink(events_dir), handle


class TestEventLogHelpersReraiseInterruption:
    def test_sigterm_in_w1001_stderr_write_fails_the_run__tc_rc1_f01_ep_010(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sigterm_guard: list[int]
    ) -> None:
        # Given: an explicit MultiDataTile mode over a SmartTable input, so the
        # run publishes W1001 on stderr, and that write receives a real SIGTERM
        root = _seed(tmp_path)
        (root / "inputdata" / "a.txt").unlink()
        (root / "inputdata" / "smarttable_data.xlsx").touch()
        writer = _Writer(lambda message: _send_sigterm() if "ModeOverriddenByFileDetection" in message else None)
        monkeypatch.setattr("sys.stderr", writer)

        # When: the run resolves its mode
        report = _run(root, system={"extended_mode": "MultiDataTile"})

        # Then: the interruption is the run's outcome, not a lost notice
        assert any("ModeOverriddenByFileDetection" in message for message in writer.calls)
        _assert_interrupted(report, root)
        assert sigterm_guard == []

    def test_interrupt_in_stderr_write_propagates_unchanged__tc_rc1_f01_ep_011(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Given: a stderr whose write raises the interruption error
        from rdetoolkit.report.events import _best_effort_stderr  # noqa: PLC0415

        interrupt = _interrupt_error()

        def raise_interrupt(_message: str) -> None:
            raise interrupt

        monkeypatch.setattr("sys.stderr", _Writer(raise_interrupt))

        # When / Then: the very same exception object propagates
        with pytest.raises(RdeExecutionError) as exc_info:
            _best_effort_stderr("notice\n")
        assert exc_info.value is interrupt

    @pytest.mark.parametrize(
        "error",
        [OSError("closed"), ValueError("I/O operation on closed file"), _ordinary_rde_error()],
        ids=["oserror", "valueerror", "execution-error-3001"],
    )
    def test_ordinary_stderr_failure_is_still_swallowed__tc_rc1_f01_neg_008_010(
        self, error: Exception, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Given: a stderr failing in an ordinary way
        from rdetoolkit.report.events import _best_effort_stderr  # noqa: PLC0415

        def raise_error(_message: str) -> None:
            raise error

        writer = _Writer(raise_error)
        monkeypatch.setattr("sys.stderr", writer)

        # When / Then: the notice is dropped and nothing propagates
        assert _best_effort_stderr("notice\n") is None
        assert writer.calls == ["notice\n"]

    def test_sigterm_in_header_failure_close_propagates__tc_rc1_f01_ep_012(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, real_interrupt_handler: None
    ) -> None:
        # Given: the header write fails (ENOSPC) and the release of the handle
        # receives a real SIGTERM handled by the Runner's own handler
        sink, handle = _header_failing_sink(tmp_path, monkeypatch, _send_sigterm)

        # When / Then: the interruption wins over the header OSError
        with pytest.raises(RdeExecutionError) as exc_info:
            sink.open("rc1-f01-close")
        assert exc_info.value.code == _RUN_INTERRUPTED
        assert isinstance(exc_info.value.__context__, OSError)
        assert handle.closed_calls == 1
        assert sink._file is None

    def test_interrupt_in_close_passes_the_runner_guard__tc_rc1_f01_ep_013(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Given: the same close path raising the interruption, behind the
        # Runner's best-effort guard
        interrupt = _interrupt_error()

        def raise_interrupt() -> None:
            raise interrupt

        sink, _ = _header_failing_sink(tmp_path, monkeypatch, raise_interrupt)
        guard = executor_module._BestEffortEventSink(sink)

        # When / Then: the guard does not mute it as "no event log"
        with pytest.raises(RdeExecutionError) as exc_info:
            guard.open("rc1-f01-guard")
        assert exc_info.value is interrupt
        assert guard._muted_run_id is None

    def test_ordinary_close_failure_keeps_the_header_error__tc_rc1_f01_neg_009(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Given: the close after a failed header write fails in an ordinary way
        def raise_oserror() -> None:
            msg = "flush failed again"
            raise OSError(msg)

        sink, handle = _header_failing_sink(tmp_path, monkeypatch, raise_oserror)

        # When / Then: the header error is the one reported, the handle is released
        with pytest.raises(OSError, match="No space left on device"):
            sink.open("rc1-f01-close-ordinary")
        assert handle.closed_calls == 1
        assert sink._file is None
