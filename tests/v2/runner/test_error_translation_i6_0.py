"""Unified flow error translation for Session I6-0 (Design §6.3).

A v1 ``StructuredError`` carries ``(emsg, ecode)`` — not ``(message, code)`` —
and the RDE platform contract is that those two values reach ``job.failed``
verbatim. The scope is every ``StructuredError`` that reaches a translator,
whether it came from user code or from the framework's own v1-derived helpers,
because v1 ``catch_exception_with_message`` publishes both alike. Catalog
substitution stays reserved for failures that are not ``StructuredError``;
validation keeps 4001/4002/4003 because those steps raise
``RdeValidationError`` rather than letting the underlying exception through.

Equivalence partitions (EP):

| Path | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``TileExecutor.execute`` | invoker raises ``StructuredError`` | ``(ecode, emsg)`` verbatim | TC-EP-I60-101 |
| ``TileExecutor.execute`` | flow raises ``StructuredError`` (``TileExecutionError`` cause) | ``(ecode, emsg)`` verbatim | TC-EP-I60-102 |
| ``TileExecutor.execute`` | invoker raises ``RdeError`` | error keeps its own catalog code | TC-EP-I60-103 |
| ``TileExecutor.execute`` | invoker raises a plain exception | 3001 ``NodeExecutionFailed`` | TC-EP-I60-104 |
| ``TileExecutor.execute`` | node raises ``StructuredError`` | recorder ``call_id`` is preserved | TC-EP-I60-105 |
| ``Runner.run`` | lifecycle step raises ``StructuredError`` | ``(ecode, emsg)`` verbatim | TC-EP-I60-111 |
| ``Runner.run`` | lifecycle step raises ``RdeError`` | error keeps its own catalog code | TC-EP-I60-112 |
| ``Runner.run`` | lifecycle step raises a plain exception | 1002 catalogued | TC-EP-I60-113 |
| ``Runner.run`` | framework raises ``StructuredError`` | verbatim, matches frozen v1 | TC-EP-I60-114 |
| ``Runner.run`` | passthrough failure | persisted report keeps schema "2" | TC-EP-I60-131 |
| ``finalize`` | passthrough record with an off-catalog code | code written verbatim | TC-EP-I60-121 |
| ``finalize`` | framework record with an off-catalog code | substituted with 3001 | TC-EP-I60-122 |
| ``finalize`` | framework record with a catalog code | code written verbatim | TC-EP-I60-123 |

Boundary values (BV):

| Path | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| ``TileExecutor.execute`` | ``StructuredError`` default ``ecode=1`` | off-catalog code 1 survives | TC-BV-I60-101 |
| ``TileExecutor.execute`` | ``StructuredError`` with empty ``emsg`` | non-empty message, no raw placeholder | TC-BV-I60-102 |
| ``TileExecutor.execute`` | ``StructuredError`` with a non-int ``ecode`` | falls back to 3001 | TC-BV-I60-103 |
| ``finalize`` | passthrough record without a message | code kept, no ``KeyError`` | TC-BV-I60-104 |
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.api.request import FlowTarget
from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.errors import ERROR_CATALOG, RdeValidationError
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.execute import ExecutionResult, TileExecutionError
from rdetoolkit.runner.executor import TileExecutor
from rdetoolkit.runner.finalize import finalize
from rdetoolkit.runner.invoker import FlowInvoker
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.paths import resolve_tile_paths
from rdetoolkit.runner.planner import ExecutionPlan, TilePlan
from rdetoolkit.types import InputPaths, IterationInfo, OutputContext, RdeConfig
from tests.v2.contract.fixtures import _generate

_USER_MESSAGE = "Contract callback failed. Remediation: inspect the fixture callback."
_USER_CODE = 999
_NODE_EXECUTION_FAILED_CODE = 3001
_CONFIG_ERROR_CODE = 1002
_INVOICE_SCHEMA_CODE = 4001


_FAILING_NODE_ID = "i6_0_failing_node"


@node(id=_FAILING_NODE_ID)
def _failing_node() -> None:
    """Raise the v1 public error from inside a recorded node call."""
    raise StructuredError(_USER_MESSAGE, ecode=_USER_CODE)


@flow
def _structured_error_flow() -> None:
    """Let the node failure propagate through the real run_tile wrapper."""
    _failing_node()


class _RaisingInvoker:
    """Raise one fixed exception instead of executing a tile."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def invoke(self, *args: object, **kwargs: object) -> ExecutionResult:
        raise self._error


def _tile(tmp_path: Path) -> TilePlan:
    rawfile = tmp_path / "inputdata" / "sample-0.txt"
    return TilePlan(
        iteration=IterationInfo(index=0, total=1, mode="invoice"),
        paths=InputPaths(
            inputdata=rawfile.parent,
            invoice=tmp_path / "invoice",
            tasksupport=tmp_path / "tasksupport",
            raw=rawfile,
            rawfiles=(rawfile,),
        ),
        out=OutputContext.from_resource_paths(resolve_tile_paths(tmp_path / "data", 0)),
        invoice=None,
    )


def _plan(tmp_path: Path, tile: TilePlan, target: FlowTarget | None = None) -> ExecutionPlan:
    return ExecutionPlan(
        run_id="i6-0-errors",
        target=target or FlowTarget(function=lambda: None),
        mode=ModeKind.invoice,
        config=RdeConfig(),
        root=tmp_path,
        data_root=tmp_path,
        invoice_source=tmp_path / "data" / "invoice" / "invoice.json",
        error_policy="continue",
        tiles=(tile,),
    )


def _execute_with(tmp_path: Path, error: Exception) -> ExecutionResult:
    tile = _tile(tmp_path)
    executor = TileExecutor(
        event_sink=MemoryEventSink(),
        flow_invoker=_RaisingInvoker(error),  # type: ignore[arg-type]
    )
    return executor.execute(_plan(tmp_path, tile), tile)


def _tile_execution_error(cause: Exception) -> TileExecutionError:
    """Build the wrapper ``run_tile`` raises, preserving ``__cause__``."""
    failed = ExecutionResult(
        iteration_index=0,
        status="failed",
        call_records=(),
        outputs=(),
        error={
            "code": _NODE_EXECUTION_FAILED_CODE,
            "name": ERROR_CATALOG[_NODE_EXECUTION_FAILED_CODE].name,
            "message": f"Node execution failed for call unknown: {cause}",
            "call_id": "unknown",
        },
    )
    try:
        raise TileExecutionError(failed, cause) from cause
    except TileExecutionError as wrapper:
        return wrapper


def _make_report(*, error: dict[str, Any] | None) -> RunReport:
    return RunReport(
        run_id="run-i6-0",
        status="failed",
        flow_id="tests.v2.runner.test_error_translation_i6_0.stub",
        mode="invoice",
        started_at="2026-09-07T00:00:00",
        duration_ms=1.0,
        config_digest="sha256:deadbeef",
        iterations=[],
        warnings=[],
        error=error,
    )


class _FailingStepRunner(Runner):
    """Raise a fixed exception from ``pre_validate`` to exercise the run-level path."""

    def __init__(self, *, error: Exception, **kwargs: Any) -> None:
        self._error = error
        super().__init__(**kwargs)

    def load_config(self, source: object | None = None) -> RdeConfig:
        return RdeConfig()

    def resolve_mode(self, config: RdeConfig) -> ModeKind:
        return ModeKind.invoice

    def pre_validate(self, config: RdeConfig) -> None:
        raise self._error


def _run_failing_lifecycle(
    tmp_path: Path,
    error: Exception,
    monkeypatch: pytest.MonkeyPatch,
) -> RunReport:
    # write_job_errorlog_file resolves its target cwd-relative, so the run must
    # own the working directory to keep the repository tree clean.
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    runner = _FailingStepRunner(error=error, root=tmp_path)
    return runner.run(lambda: None)


class TestExecutorErrorTranslation:
    """The tile boundary owns the primary error record for one iteration."""

    def test_user_structured_error_passes_ecode_and_emsg_through__tc_ep_i60_101(
        self,
        tmp_path: Path,
    ) -> None:
        """TC-EP-I60-101: a raised StructuredError keeps its ecode and emsg verbatim."""
        # Given: an invoker raising the v1 public StructuredError with ecode 999
        error = StructuredError(_USER_MESSAGE, ecode=_USER_CODE)

        # When: the executor normalizes the tile failure
        result = _execute_with(tmp_path, error)

        # Then: the error record carries the user's own code and message
        assert result.status == "failed"
        assert result.error is not None
        assert result.error["code"] == _USER_CODE
        assert result.error["message"] == _USER_MESSAGE
        assert result.error["name"] == "StructuredError"

    def test_flow_structured_error_survives_tile_wrapping__tc_ep_i60_102(
        self,
        tmp_path: Path,
    ) -> None:
        """TC-EP-I60-102: the run_tile 3001 wrapper must not hide the user's ecode."""
        # Given: the catalogued wrapper run_tile raises around a user StructuredError
        cause = StructuredError(_USER_MESSAGE, ecode=_USER_CODE)
        wrapper = _tile_execution_error(cause)

        # When: the executor normalizes that wrapped failure
        result = _execute_with(tmp_path, wrapper)

        # Then: the wrapper's 3001 is replaced by the user's verbatim values
        assert result.error is not None
        assert result.error["code"] == _USER_CODE
        assert result.error["message"] == _USER_MESSAGE

    def test_rde_error_keeps_its_own_catalog_code__tc_ep_i60_103(self, tmp_path: Path) -> None:
        """TC-EP-I60-103: framework RdeError codes are never rewritten as user codes."""
        # Given: an invoker raising a catalogued validation error
        error_cls: Any = RdeValidationError
        error = error_cls(code=_INVOICE_SCHEMA_CODE, name="InvoiceSchemaInvalid", message="schema invalid")

        # When: the executor normalizes the tile failure
        result = _execute_with(tmp_path, error)

        # Then: the catalog code and name survive untouched
        assert result.error is not None
        assert result.error["code"] == _INVOICE_SCHEMA_CODE
        assert result.error["name"] == "InvoiceSchemaInvalid"

    def test_plain_exception_still_maps_to_node_execution_failed__tc_ep_i60_104(
        self,
        tmp_path: Path,
    ) -> None:
        """TC-EP-I60-104: non-StructuredError framework exceptions stay 3001."""
        # Given: an invoker raising an exception with no RDE error contract
        error = RuntimeError("boom")

        # When: the executor normalizes the tile failure
        result = _execute_with(tmp_path, error)

        # Then: the default catalog code applies
        assert result.error is not None
        assert result.error["code"] == _NODE_EXECUTION_FAILED_CODE
        assert result.error["name"] == ERROR_CATALOG[_NODE_EXECUTION_FAILED_CODE].name

    def test_default_structured_ecode_one_survives__tc_bv_i60_101(self, tmp_path: Path) -> None:
        """TC-BV-I60-101: the StructuredError default ecode=1 is off-catalog yet kept."""
        # Given: a StructuredError raised without an explicit ecode
        error = StructuredError("Failed to generate invoice file for data 0")

        # When: the executor normalizes the tile failure
        result = _execute_with(tmp_path, error)

        # Then: the v1 default code 1 is preserved rather than catalogued
        assert 1 not in ERROR_CATALOG
        assert result.error is not None
        assert result.error["code"] == 1

    def test_empty_structured_message_gets_a_usable_message__tc_bv_i60_102(
        self,
        tmp_path: Path,
    ) -> None:
        """TC-BV-I60-102: an empty emsg must not produce an empty job.failed line."""
        # Given: a StructuredError carrying no message at all
        error = StructuredError("", ecode=_USER_CODE)

        # When: the executor normalizes the tile failure
        result = _execute_with(tmp_path, error)

        # Then: a non-empty message without unexpanded template placeholders results
        assert result.error is not None
        message = result.error["message"]
        assert message
        assert "{" not in message and "}" not in message

    def test_non_int_structured_ecode_falls_back_to_catalog__tc_bv_i60_103(
        self,
        tmp_path: Path,
    ) -> None:
        """TC-BV-I60-103: job.failed requires an int code, so a bad ecode is replaced."""
        # Given: a StructuredError whose ecode violates the int contract
        error = StructuredError(_USER_MESSAGE, ecode="not-an-int")  # type: ignore[arg-type]

        # When: the executor normalizes the tile failure
        result = _execute_with(tmp_path, error)

        # Then: the default catalog code protects the int-only job.failed contract
        assert result.error is not None
        assert result.error["code"] == _NODE_EXECUTION_FAILED_CODE

    def test_passthrough_keeps_the_recorder_call_id__tc_ep_i60_105(
        self,
        tmp_path: Path,
    ) -> None:
        """TC-EP-I60-105: replacing the catalogued code must not drop call context."""
        # Given: a real flow whose node raises a StructuredError, so the tile
        # result carries the recorder's own call_id alongside the 3001 wrapper
        tile = _tile(tmp_path)
        executor = TileExecutor(event_sink=MemoryEventSink(), flow_invoker=FlowInvoker())
        plan = _plan(tmp_path, tile, target=FlowTarget(function=_structured_error_flow))

        # When: the executor normalizes that wrapped failure
        result = executor.execute(plan, tile)

        # Then: the passthrough replaces only the catalogued fields
        assert result.error is not None
        assert result.error["code"] == _USER_CODE
        assert result.error["message"] == _USER_MESSAGE
        assert result.error["call_id"].startswith(_FAILING_NODE_ID)
        # The 3001 remediation described NodeExecutionFailed, which is no longer
        # the reported error, so it must not survive the replacement.
        assert "remediation" not in result.error


class TestLifecycleErrorTranslation:
    """A run-level failure record follows the same translation rule."""

    def test_user_structured_error_passes_through__tc_ep_i60_111(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-EP-I60-111: a StructuredError escaping a lifecycle step keeps ecode/emsg."""
        # Given: a Runner whose pre_validate raises the v1 public StructuredError
        error = StructuredError(_USER_MESSAGE, ecode=_USER_CODE)

        # When: running the lifecycle to its failed report
        report = _run_failing_lifecycle(tmp_path, error, monkeypatch)

        # Then: the run-level record is the user's own code and message
        assert report.status == "failed"
        assert report.error is not None
        assert report.error["code"] == _USER_CODE
        assert report.error["message"] == _USER_MESSAGE

    def test_rde_error_keeps_its_own_catalog_code__tc_ep_i60_112(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-EP-I60-112: catalogued validation failures are not rewritten."""
        # Given: a Runner whose pre_validate raises a catalogued validation error
        error_cls: Any = RdeValidationError
        error = error_cls(code=_INVOICE_SCHEMA_CODE, name="InvoiceSchemaInvalid", message="schema invalid")

        # When: running the lifecycle to its failed report
        report = _run_failing_lifecycle(tmp_path, error, monkeypatch)

        # Then: the catalog code survives
        assert report.error is not None
        assert report.error["code"] == _INVOICE_SCHEMA_CODE

    def test_plain_exception_is_catalogued__tc_ep_i60_113(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-EP-I60-113: a plain exception keeps the existing 1002 lifecycle mapping."""
        # Given: a Runner whose pre_validate raises an uncatalogued exception
        error = RuntimeError("boom")

        # When: running the lifecycle to its failed report
        report = _run_failing_lifecycle(tmp_path, error, monkeypatch)

        # Then: the config-error catalog entry still applies
        assert report.error is not None
        assert report.error["code"] == _CONFIG_ERROR_CODE

    def test_framework_structured_error_bypasses_the_1002_mapping__tc_ep_i60_114(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-EP-I60-114: an internally raised StructuredError is published verbatim.

        The passthrough scope is every ``StructuredError``, not only user code:
        v1's ``catch_exception_with_message`` writes internally raised ones to
        ``job.failed`` too. This case drives a real, unmocked framework route --
        ``ExcelInvoiceFile.read`` rejecting a workbook with no invoice-list
        sheet -- and compares against the frozen v1 observation of that exact
        input, so the expectation is the oracle rather than a restatement.
        """
        # Given: the committed zero-row ExcelInvoice input and its frozen v1 output
        root = tmp_path / "excelinvoice"
        _generate._materialize_oracle_case("excelinvoice", root, zero_rows=True)
        expected = json.loads(
            (_generate.EXPECTED_ROOT / "excelinvoice" / "zero_rows.json").read_text(encoding="utf-8"),
        )["observed"]
        assert expected["job_failed_text"].startswith("ErrorCode=1\n")
        monkeypatch.chdir(root)
        runner = Runner(
            root=root,
            inputdata_path=root / "data" / "inputdata",
            unpacked_dir_path=root / "data" / "unpacked",
        )

        # When: the planner reads that workbook through the production path
        report = runner.run(lambda: None)

        # Then: the framework's own ecode/emsg reach job.failed unchanged
        assert report.status == "failed"
        assert report.error is not None
        assert report.error["name"] == "StructuredError"
        assert report.error["code"] != _CONFIG_ERROR_CODE
        job_failed = _generate.normalize_snapshot(
            (root / "data" / "job.failed").read_text(encoding="utf-8"),
            roots=(root,),
        )
        assert job_failed == expected["job_failed_text"]


class TestFinalizeHonorsPassthroughCodes:
    """finalize must not squash a passthrough code back to the catalog default."""

    def test_passthrough_code_reaches_job_failed__tc_ep_i60_121(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-EP-I60-121: an off-catalog user code is written verbatim."""
        # Given: a failed report carrying a user StructuredError record
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()
        report = _make_report(
            error={"code": _USER_CODE, "name": "StructuredError", "message": _USER_MESSAGE},
        )

        # When: finalizing that report
        finalize(report, RdeConfig(), data_root=tmp_path / "data")

        # Then: job.failed reproduces the v1 code and message exactly
        content = (tmp_path / "data" / "job.failed").read_text(encoding="utf-8")
        assert content == f"ErrorCode={_USER_CODE}\nErrorMessage={_USER_MESSAGE}\n"

    def test_framework_off_catalog_code_is_still_substituted__tc_ep_i60_122(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-EP-I60-122: an unknown framework code keeps the 3001 safety net."""
        # Given: a failed report whose framework code is not in the catalog
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()
        report = _make_report(error={"code": 8888, "name": "MysteryFailure", "message": "boom"})

        # When: finalizing that report
        finalize(report, RdeConfig(), data_root=tmp_path / "data")

        # Then: the catalog default replaces the unknown code
        content = (tmp_path / "data" / "job.failed").read_text(encoding="utf-8")
        assert content.startswith(f"ErrorCode={_NODE_EXECUTION_FAILED_CODE}\n")

    def test_catalog_code_is_unchanged__tc_ep_i60_123(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-EP-I60-123: catalogued framework codes remain byte-identical."""
        # Given: a failed report with a catalogued validation code
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()
        report = _make_report(
            error={"code": _INVOICE_SCHEMA_CODE, "name": "InvoiceSchemaInvalid", "message": "schema invalid"},
        )

        # When: finalizing that report
        finalize(report, RdeConfig(), data_root=tmp_path / "data")

        # Then: the declared code is written unchanged
        content = (tmp_path / "data" / "job.failed").read_text(encoding="utf-8")
        assert content == f"ErrorCode={_INVOICE_SCHEMA_CODE}\nErrorMessage=schema invalid\n"

    def test_passthrough_without_message_stays_writable__tc_bv_i60_104(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-BV-I60-104: an off-catalog code with no message must not raise KeyError."""
        # Given: a passthrough record whose message is missing
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()
        report = _make_report(error={"code": _USER_CODE, "name": "StructuredError"})

        # When: finalizing that report
        finalize(report, RdeConfig(), data_root=tmp_path / "data")

        # Then: the user code survives with a placeholder-free message
        content = (tmp_path / "data" / "job.failed").read_text(encoding="utf-8")
        assert content.startswith(f"ErrorCode={_USER_CODE}\n")
        assert "{" not in content and "}" not in content


def test_run_report_json_preserves_passthrough_error__tc_ep_i60_131(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-EP-I60-131: the persisted RunReport records the same verbatim values."""
    # Given: a lifecycle failing with a user StructuredError
    error = StructuredError(_USER_MESSAGE, ecode=_USER_CODE)

    # When: the run finalizes and writes its report
    report = _run_failing_lifecycle(tmp_path, error, monkeypatch)

    # Then: the serialized report shows the user code without a schema bump
    saved = json.loads((tmp_path / "data" / "logs" / f"run_report_{report.run_id}.json").read_text(encoding="utf-8"))
    assert saved["schema_version"] == "2"
    assert saved["error"]["code"] == _USER_CODE
    assert saved["error"]["message"] == _USER_MESSAGE
