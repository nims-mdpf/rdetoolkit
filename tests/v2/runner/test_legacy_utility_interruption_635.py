"""Legacy v1 utilities must not translate the run interruption (issue #635).

The Runner's SIGTERM handler raises ``RdeExecutionError(3004)``. Several v1
utilities that a run calls (or that a v1 callback may call) caught every
``Exception`` and re-raised it as ``StructuredError`` / ``ValueError`` /
``DataRetrievalError``, or swallowed it. The original type and code were lost,
so the Runner could no longer recognize the run as interrupted.

Each case below injects the interruption *inside* the utility's own ``try``
body (through the dependency the utility really calls) and checks that the
same object propagates; the paired negative case checks that an ordinary
failure keeps its v1 translation and exception chaining.

EP table (interruption passes through unchanged):
| TC | Utility | Injection point | Expected |
|----|---------|-----------------|----------|
| TC-635-EP-001 | ``SmartTableFile.read_table`` | ``pd.read_csv`` | same 3004 object |
| TC-635-EP-002 | ``SmartTableFile.generate_row_csvs_with_file_mapping`` | ``pd.DataFrame`` | same 3004 object |
| TC-635-EP-003 | ``fileops.readf_json`` | ``detect_encoding`` | same 3004 object |
| TC-635-EP-004 | ``fileops.readf_json`` | ``json.load`` | same 3004 object |
| TC-635-EP-005 | ``SystemFilesCleaner.clean_directory`` | ``Path.unlink`` | same 3004 object (not logged and skipped) |
| TC-635-EP-006 | ``SystemFilesCleaner.clean_directory`` | ``shutil.rmtree`` | same 3004 object |
| TC-635-EP-007 | ``catch_exception_with_message`` | decorated body | same 3004 object |
| TC-635-EP-008 | ``img2thumb.resize_image`` | ``resize_image_aspect_ratio`` | same 3004 object |
| TC-635-EP-009 | ``ExcelInvoiceFile.save`` | ``DataFrame.to_excel`` | same 3004 object |
| TC-635-EP-010 | ``invoice_generator._load_and_validate_schema`` | ``readf_json`` / model | same 3004 object |
| TC-635-EP-011 | ``Meta`` value-to-str conversion | ``__str__`` | same 3004 object (not ``""``) |
| TC-635-EP-012 | ``SpecificTermRegistry.search`` | polars filter | same 3004 object |
| TC-635-EP-013 | ``result.try_result`` | wrapped body | same 3004 object (not ``Failure``) |
| TC-635-EP-014 | ``workflows.check_files_result`` | input checker | same 3004 object (not ``Failure``) |

Integration table (real SIGTERM through the Runner, ``continue`` policy):
| TC | Mode / stage | Injection point | Expected |
|----|--------------|-----------------|----------|
| TC-635-INT-001 | smarttable / input parse (``read_table``) | ``pd.read_excel`` | failed / 3004 / ``job.failed`` ErrorCode=3004 |
| TC-635-INT-002 | smarttable / row-CSV generation | ``pd.DataFrame`` | failed / 3004 / ``job.failed`` ErrorCode=3004 |
| TC-635-INT-003 | invoice / JSON read (``readf_json``) | ``detect_encoding`` | failed / 3004 / ``job.failed`` ErrorCode=3004 |
| TC-635-INT-004 | invoice / thumbnail stage (decorated converter) | ``shutil.copy`` | failed / 3004 / ``job.failed`` ErrorCode=3004 |

Negative table (v1 behaviour unchanged):
| TC | Utility | Input | Expected |
|----|---------|-------|----------|
| TC-635-NEG-001 | ``read_table`` | ``RuntimeError`` | ``StructuredError`` "Failed to read SmartTable file", ``__cause__`` kept |
| TC-635-NEG-002 | ``generate_row_csvs_with_file_mapping`` | ``RuntimeError`` | ``StructuredError`` "Failed to generate CSV files", ``__cause__`` kept |
| TC-635-NEG-003 | ``readf_json`` | malformed JSON | ``StructuredError`` "An error occurred while processing the file", ``__cause__`` kept |
| TC-635-NEG-004 | ``readf_json`` / ``read_table`` | ``RdeExecutionError(3001)`` | still translated (only 3004 passes) |
| TC-635-NEG-005 | ``clean_directory`` | ``OSError`` | logged and skipped |
| TC-635-NEG-006 | ``catch_exception_with_message`` | ``RuntimeError`` | ``StructuredError`` with the decorator code |
| TC-635-NEG-007 | ``try_result`` | ``RuntimeError`` | ``Failure`` |
| TC-635-NEG-008 | invoice run / ``readf_json`` | malformed invoice.json | not 3004 (ordinary failure) |
"""

from __future__ import annotations

import json
import os
import shutil
import signal
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit import fileops, flow, img2thumb, invoice_generator, workflows
from rdetoolkit.errors import ERROR_CATALOG, RdeExecutionError, catch_exception_with_message
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.impl import compressed_controller
from rdetoolkit.impl.compressed_controller import SystemFilesCleaner
from rdetoolkit.invoicefile import _excelinvoice, _smarttable
from rdetoolkit.invoicefile._excelinvoice import ExcelInvoiceFile
from rdetoolkit.invoicefile._smarttable import SmartTableFile
from rdetoolkit.models import invoice as invoice_models
from rdetoolkit.rde2util import Meta
from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.result import Failure, try_result
from rdetoolkit.runner.lifecycle import Runner
from tests.v2.contract.fixtures import _generate

_RUN_INTERRUPTED = 3004
_CONTINUE = {"execution": {"on_iteration_error": "continue"}}


def _interrupt_error() -> RdeExecutionError:
    error_def = ERROR_CATALOG[_RUN_INTERRUPTED]
    error_cls: Any = RdeExecutionError
    return error_cls(code=_RUN_INTERRUPTED, name=error_def.name, message=error_def.message_template)


def _ordinary_rde_error() -> RdeExecutionError:
    error_cls: Any = RdeExecutionError
    return error_cls(code=3001, name=ERROR_CATALOG[3001].name, message="ordinary")


def _raising(error: BaseException) -> Callable[..., Any]:
    def raise_(*_args: Any, **_kwargs: Any) -> Any:
        raise error

    return raise_


def _send_sigterm() -> None:
    os.kill(os.getpid(), signal.SIGTERM)


def _first_call_does(action: Callable[[], None], original: Callable[..., Any]) -> tuple[Callable[..., Any], list[int]]:
    """Wrap ``original`` so that only its first call runs ``action`` first."""
    calls: list[int] = []

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        if len(calls) == 1:
            action()
        return original(*args, **kwargs)

    return wrapped, calls


@pytest.fixture
def sigterm_guard() -> Iterator[list[int]]:
    """Keep a stray SIGTERM from killing pytest; the Runner installs its own handler."""
    received: list[int] = []
    previous = signal.signal(signal.SIGTERM, lambda signum, _frame: received.append(signum))
    try:
        yield received
    finally:
        signal.signal(signal.SIGTERM, previous)


class _ModuleProxy:
    """Module-local stand-in that overrides some attributes of a real module."""

    def __init__(self, real: Any, **overrides: Any) -> None:
        self._real = real
        self.__dict__.update(overrides)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


def _patch_smarttable_pandas(monkeypatch: pytest.MonkeyPatch, **overrides: Any) -> None:
    pd = _smarttable._ensure_pandas()
    monkeypatch.setattr(_smarttable, "_ensure_pandas", lambda: _ModuleProxy(pd, **overrides))


def _smarttable_file(tmp_path: Path) -> Path:
    path = tmp_path / "smarttable_case.csv"
    path.write_text("Data name,Input\nbasic/dataName,inputdata1\nrow-a,a.txt\nrow-b,b.txt\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# SmartTableFile
# --------------------------------------------------------------------------


class TestSmartTableFile:
    def test_interrupt_in_read_table_propagates__tc_635_ep_001(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Given: the CSV reader is interrupted while the table is read
        interrupt = _interrupt_error()
        _patch_smarttable_pandas(monkeypatch, read_csv=_raising(interrupt))

        # When / Then: the same interruption object leaves read_table
        with pytest.raises(RdeExecutionError) as exc_info:
            SmartTableFile(_smarttable_file(tmp_path)).read_table()
        assert exc_info.value is interrupt

    def test_interrupt_in_row_csv_generation_propagates__tc_635_ep_002(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Given: a readable table, and an interruption while a row CSV is built
        table = SmartTableFile(_smarttable_file(tmp_path))
        table.read_table()
        interrupt = _interrupt_error()
        _patch_smarttable_pandas(monkeypatch, DataFrame=_raising(interrupt))

        # When / Then
        with pytest.raises(RdeExecutionError) as exc_info:
            table.generate_row_csvs_with_file_mapping(tmp_path / "out", [tmp_path / "a.txt", tmp_path / "b.txt"])
        assert exc_info.value is interrupt

    def test_ordinary_read_failure_keeps_v1_translation__tc_635_neg_001(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Given: the CSV reader fails in an ordinary way
        cause = RuntimeError("parser broke")
        _patch_smarttable_pandas(monkeypatch, read_csv=_raising(cause))

        # When / Then: v1's StructuredError wrapping and chaining are unchanged
        with pytest.raises(StructuredError, match=r"^Failed to read SmartTable file .*: parser broke$") as exc_info:
            SmartTableFile(_smarttable_file(tmp_path)).read_table()
        assert exc_info.value.__cause__ is cause

    def test_ordinary_generation_failure_keeps_v1_translation__tc_635_neg_002(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Given: building a row CSV fails in an ordinary way
        table = SmartTableFile(_smarttable_file(tmp_path))
        table.read_table()
        cause = RuntimeError("row broke")
        _patch_smarttable_pandas(monkeypatch, DataFrame=_raising(cause))

        # When / Then
        with pytest.raises(StructuredError, match=r"^Failed to generate CSV files with file mapping: row broke$") as exc_info:
            table.generate_row_csvs_with_file_mapping(tmp_path / "out", [tmp_path / "a.txt", tmp_path / "b.txt"])
        assert exc_info.value.__cause__ is cause

    def test_other_execution_error_is_still_wrapped__tc_635_neg_004a(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Given: the reader raises an RdeExecutionError that is not 3004
        _patch_smarttable_pandas(monkeypatch, read_csv=_raising(_ordinary_rde_error()))

        # When / Then: only the interruption passes through
        with pytest.raises(StructuredError, match=r"^Failed to read SmartTable file "):
            SmartTableFile(_smarttable_file(tmp_path)).read_table()


# --------------------------------------------------------------------------
# fileops.readf_json
# --------------------------------------------------------------------------


class _JsonProxy:
    def __init__(self, load: Callable[..., Any]) -> None:
        self.load = load

    def __getattr__(self, name: str) -> Any:
        return getattr(json, name)


class TestReadfJson:
    def test_interrupt_in_encoding_detection_propagates__tc_635_ep_003(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Given: encoding detection is interrupted
        path = tmp_path / "a.json"
        path.write_text("{}", encoding="utf-8")
        interrupt = _interrupt_error()
        monkeypatch.setattr(fileops, "detect_encoding", _raising(interrupt))

        # When / Then
        with pytest.raises(RdeExecutionError) as exc_info:
            fileops.readf_json(path)
        assert exc_info.value is interrupt

    def test_interrupt_in_json_load_propagates__tc_635_ep_004(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Given: JSON decoding is interrupted
        path = tmp_path / "a.json"
        path.write_text("{}", encoding="utf-8")
        interrupt = _interrupt_error()
        monkeypatch.setattr(fileops, "json", _JsonProxy(_raising(interrupt)))

        # When / Then
        with pytest.raises(RdeExecutionError) as exc_info:
            fileops.readf_json(str(path))
        assert exc_info.value is interrupt

    def test_malformed_json_keeps_v1_translation__tc_635_neg_003(self, tmp_path: Path) -> None:
        # Given: a file that is not JSON
        path = tmp_path / "a.json"
        path.write_text("{not json", encoding="utf-8")

        # When / Then: v1's StructuredError and chaining are unchanged
        with pytest.raises(StructuredError, match=r"^An error occurred while processing the file: ") as exc_info:
            fileops.readf_json(path)
        assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)

    def test_other_execution_error_is_still_wrapped__tc_635_neg_004b(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Given: encoding detection raising an RdeExecutionError that is not 3004
        path = tmp_path / "a.json"
        path.write_text("{}", encoding="utf-8")
        cause = _ordinary_rde_error()
        monkeypatch.setattr(fileops, "detect_encoding", _raising(cause))

        # When / Then
        with pytest.raises(StructuredError) as exc_info:
            fileops.readf_json(path)
        assert exc_info.value.__cause__ is cause


# --------------------------------------------------------------------------
# SystemFilesCleaner.clean_directory (best-effort removal)
# --------------------------------------------------------------------------


def _junk_tree(tmp_path: Path) -> Path:
    root = tmp_path / "extracted"
    (root / "__MACOSX").mkdir(parents=True)
    (root / ".DS_Store").write_text("x", encoding="utf-8")
    return root


class TestSystemFilesCleaner:
    def test_interrupt_in_file_removal_propagates__tc_635_ep_005(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Given: removing a system file is interrupted
        root = _junk_tree(tmp_path)
        interrupt = _interrupt_error()
        monkeypatch.setattr(Path, "unlink", _raising(interrupt))

        # When / Then: the interruption is not logged and skipped
        with pytest.raises(RdeExecutionError) as exc_info:
            SystemFilesCleaner().clean_directory(root)
        assert exc_info.value is interrupt

    def test_interrupt_in_directory_removal_propagates__tc_635_ep_006(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Given: removing a system directory is interrupted
        root = _junk_tree(tmp_path)
        interrupt = _interrupt_error()
        monkeypatch.setattr(compressed_controller, "shutil", _ModuleProxy(shutil, rmtree=_raising(interrupt)))

        # When / Then
        with pytest.raises(RdeExecutionError) as exc_info:
            SystemFilesCleaner().clean_directory(root)
        assert exc_info.value is interrupt

    def test_ordinary_removal_failure_stays_best_effort__tc_635_neg_005(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Given: every removal fails in an ordinary way
        root = _junk_tree(tmp_path)
        monkeypatch.setattr(Path, "unlink", _raising(OSError("busy")))
        monkeypatch.setattr(compressed_controller, "shutil", _ModuleProxy(shutil, rmtree=_raising(OSError("busy"))))

        # When / Then: failures are skipped, nothing is reported as removed
        assert SystemFilesCleaner().clean_directory(root) == []


# --------------------------------------------------------------------------
# errors.catch_exception_with_message / img2thumb
# --------------------------------------------------------------------------


class TestCatchExceptionWithMessage:
    def test_interrupt_in_decorated_body_propagates__tc_635_ep_007(self) -> None:
        # Given: a decorated function interrupted while it runs
        interrupt = _interrupt_error()
        decorated = catch_exception_with_message(error_message="failed", error_code=50)(_raising(interrupt))

        # When / Then: not re-raised as StructuredError(50)
        with pytest.raises(RdeExecutionError) as exc_info:
            decorated()
        assert exc_info.value is interrupt

    def test_ordinary_failure_keeps_v1_translation__tc_635_neg_006(self) -> None:
        # Given: a decorated function failing in an ordinary way
        cause = RuntimeError("broke")
        decorated = catch_exception_with_message(error_message="failed", error_code=50)(_raising(cause))

        # When / Then
        with pytest.raises(StructuredError) as exc_info:
            decorated()
        assert exc_info.value.ecode == 50
        assert exc_info.value.__cause__ is cause

    def test_interrupt_in_resize_propagates__tc_635_ep_008(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Given: the image resize is interrupted
        interrupt = _interrupt_error()
        monkeypatch.setattr(img2thumb, "resize_image_aspect_ratio", _raising(interrupt))

        # When / Then
        with pytest.raises(RdeExecutionError) as exc_info:
            img2thumb.resize_image(tmp_path / "a.png")
        assert exc_info.value is interrupt


# --------------------------------------------------------------------------
# Remaining v1 utilities with broad translation
# --------------------------------------------------------------------------


class _RaisingFrame:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    def to_excel(self, *_args: Any, **_kwargs: Any) -> None:
        raise self.error


class _Unprintable:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    def __str__(self) -> str:
        raise self.error


class TestOtherV1Utilities:
    def test_interrupt_in_excel_invoice_save_propagates__tc_635_ep_009(self, tmp_path: Path) -> None:
        # Given: writing the workbook is interrupted
        interrupt = _interrupt_error()
        excel_invoice = object.__new__(ExcelInvoiceFile)

        # When / Then
        with pytest.raises(RdeExecutionError) as exc_info:
            excel_invoice.save(tmp_path / "x.xlsx", invoice=_RaisingFrame(interrupt))  # type: ignore[arg-type]
        assert exc_info.value is interrupt
        assert _excelinvoice.StructuredError is StructuredError

    @pytest.mark.parametrize("stage", ["read", "validate"])
    def test_interrupt_in_schema_loading_propagates__tc_635_ep_010(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str) -> None:
        # Given: reading or validating the schema is interrupted
        path = tmp_path / "invoice.schema.json"
        path.write_text("{}", encoding="utf-8")
        interrupt = _interrupt_error()
        if stage == "read":
            monkeypatch.setattr(invoice_generator, "readf_json", _raising(interrupt))
        else:
            monkeypatch.setattr("rdetoolkit.models.invoice_schema.InvoiceSchemaJson", _raising(interrupt))

        # When / Then: not re-raised as ValueError
        with pytest.raises(RdeExecutionError) as exc_info:
            invoice_generator._load_and_validate_schema(path)
        assert exc_info.value is interrupt

    def test_interrupt_in_meta_str_conversion_propagates__tc_635_ep_011(self) -> None:
        # Given: a metadata value whose str() is interrupted
        interrupt = _interrupt_error()
        meta = object.__new__(Meta)

        # When / Then: not replaced by ""
        with pytest.raises(RdeExecutionError) as exc_info:
            meta._Meta__convert_to_str(_Unprintable(interrupt))  # type: ignore[attr-defined]
        assert exc_info.value is interrupt

    def test_interrupt_in_term_search_propagates__tc_635_ep_012(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Given: the term search is interrupted inside its query
        interrupt = _interrupt_error()
        registry = object.__new__(invoice_models.SpecificTermRegistry)
        monkeypatch.setattr(invoice_models, "_ensure_polars", _raising(interrupt))

        # When / Then: not re-raised as DataRetrievalError
        with pytest.raises(RdeExecutionError) as exc_info:
            registry.search(["term_id"], ["x"], ["key_name"])
        assert exc_info.value is interrupt

    def test_interrupt_is_not_a_result_failure__tc_635_ep_013(self) -> None:
        # Given: a try_result body interrupted while it runs
        interrupt = _interrupt_error()

        # When / Then: the interruption is raised, never returned as Failure
        with pytest.raises(RdeExecutionError) as exc_info:
            try_result(_raising(interrupt))()
        assert exc_info.value is interrupt

    def test_ordinary_failure_is_a_result_failure__tc_635_neg_007(self) -> None:
        # Given / When
        result = try_result(_raising(RuntimeError("broke")))()

        # Then
        assert isinstance(result, Failure)

    def test_interrupt_in_check_files_result_propagates__tc_635_ep_014(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Given: input classification interrupted while it runs
        interrupt = _interrupt_error()
        monkeypatch.setattr("rdetoolkit.domain.input_checker.selected_input_checker", _raising(interrupt))
        monkeypatch.setattr("rdetoolkit.rde2util.StorageDir.get_specific_outputdir", lambda *_a, **_k: Path("temp"))

        # When / Then: not returned as Failure(StructuredError(999))
        with pytest.raises(RdeExecutionError) as exc_info:
            workflows.check_files_result(object(), mode="invoice")  # type: ignore[arg-type]
        assert exc_info.value is interrupt


# --------------------------------------------------------------------------
# Integration: real SIGTERM through the Runner
# --------------------------------------------------------------------------


@flow(id="tests.v2.runner.issue635.noop")
def _noop_flow() -> None:
    """Do nothing; the stage under test is library-owned."""


def _run(data: Path, **config: Any) -> RunReport:
    return Runner(root=data, event_sink=MemoryEventSink()).run(_noop_flow, **_CONTINUE, **config)


def _materialize(mode: str, tmp_path: Path) -> Path:
    root = tmp_path / mode
    _generate.materialize_sut_case(mode, root)
    return root / "data"


def _assert_interrupted(report: RunReport, data: Path) -> None:
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == _RUN_INTERRUPTED
    assert (data / "job.failed").read_text(encoding="utf-8").startswith(f"ErrorCode={_RUN_INTERRUPTED}\n")


def _seed_invoice_run(root: Path) -> Path:
    for name in ("inputdata", "invoice", "tasksupport"):
        (root / name).mkdir(parents=True)
    (root / "inputdata" / "a.txt").write_text("a", encoding="utf-8")
    invoice = {
        "datasetId": "issue-635",
        "basic": {"dateSubmitted": "2026-11-13", "dataOwnerId": "0" * 56, "dataName": "issue-635"},
    }
    (root / "invoice" / "invoice.json").write_text(json.dumps(invoice), encoding="utf-8")
    (root / "tasksupport" / "invoice.schema.json").write_text(json.dumps({"properties": {}}), encoding="utf-8")
    return root


class TestRunnerKeepsInterruption:
    def test_sigterm_while_reading_smarttable__tc_635_int_001(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sigterm_guard: list[int]
    ) -> None:
        # Given: a SmartTable (.xlsx) run, and a real SIGTERM while the table is read
        data = _materialize("smarttable", tmp_path)
        pd = _smarttable._ensure_pandas()
        read_excel, calls = _first_call_does(_send_sigterm, pd.read_excel)
        _patch_smarttable_pandas(monkeypatch, read_excel=read_excel)

        # When
        report = _run(data)

        # Then: 3004 is the run's outcome and the marker records it
        assert calls
        _assert_interrupted(report, data)
        assert sigterm_guard == []

    def test_sigterm_while_generating_row_csvs__tc_635_int_002(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sigterm_guard: list[int]
    ) -> None:
        # Given: a SmartTable run, and a real SIGTERM while a row CSV is built
        data = _materialize("smarttable", tmp_path)
        pd = _smarttable._ensure_pandas()
        frame, calls = _first_call_does(_send_sigterm, pd.DataFrame)
        _patch_smarttable_pandas(monkeypatch, DataFrame=frame)

        # When
        report = _run(data)

        # Then
        assert calls
        _assert_interrupted(report, data)
        assert sigterm_guard == []

    def test_sigterm_while_reading_json__tc_635_int_003(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sigterm_guard: list[int]
    ) -> None:
        # Given: an invoice run, and a real SIGTERM inside the first readf_json
        data = _seed_invoice_run(tmp_path / "data")
        detect, calls = _first_call_does(_send_sigterm, fileops.detect_encoding)
        monkeypatch.setattr(fileops, "detect_encoding", detect)

        # When
        report = _run(data)

        # Then
        assert calls
        _assert_interrupted(report, data)
        assert sigterm_guard == []

    def test_sigterm_inside_decorated_thumbnail_converter__tc_635_int_004(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sigterm_guard: list[int]
    ) -> None:
        # Given: a main image, and a real SIGTERM inside the v1 converter's copy
        # (the converter itself runs, decorated by catch_exception_with_message)
        data = _seed_invoice_run(tmp_path / "data")
        (data / "main_image").mkdir()
        (data / "main_image" / "a.png").write_bytes(b"png")
        copy, calls = _first_call_does(_send_sigterm, shutil.copy)
        monkeypatch.setattr(img2thumb, "shutil", _ModuleProxy(shutil, copy=copy))

        # When
        report = _run(data, system={"save_thumbnail_image": True, "feature_description": False})

        # Then: the tolerant thumbnail stage sees 3004, not StructuredError(50)
        assert calls == [1]
        _assert_interrupted(report, data)
        assert sigterm_guard == []

    def test_malformed_invoice_is_not_an_interruption__tc_635_neg_008(self, tmp_path: Path) -> None:
        # Given: an invoice run whose invoice.json is not JSON
        data = _seed_invoice_run(tmp_path / "data")
        (data / "invoice" / "invoice.json").write_text("{not json", encoding="utf-8")

        # When
        report = _run(data)

        # Then: an ordinary failure keeps its own code
        assert report.status == "failed"
        assert report.error is not None
        assert report.error["code"] != _RUN_INTERRUPTED
