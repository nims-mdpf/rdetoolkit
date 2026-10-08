"""The v1 callback entry point is recorded as a flow (Session J1, ruling #2).

Authority: ``local/develop/v2/tasks/session_j1.md`` ruling #2, ``PhaseJ_prompts.md``
§Phase J 契約裁定 #5(b)(c)(d), ADR-023 decision 5, Design.md §3.4 addendum.

``LegacyCallbackInvoker.invoke`` now runs the user callback inside the same
``CallLogRecorder`` context ``run_tile`` builds for a ``@flow``, with the
callback's own flow_id pushed on the flow stack. Consequences pinned here:

* ``@node`` calls made *by the callback* are recorded, with
  ``parent_flow == callback_flow_id(callback)``.
* ``node.started`` / ``node.completed`` / ``node.failed`` are emitted for them
  exactly once, on success **and** on failure.
* ``ExecutionResult.call_records`` carries them, and a failure raises
  ``TileExecutionError`` carrying the same records — losing the call log on the
  failing tile was the pre-J1 behaviour (trap #2).
* The original exception stays reachable through ``__cause__``, which is what
  the executor's ``StructuredError`` passthrough (§I6-0) depends on.
* Non-``@node`` work inside the callback is structurally invisible; the callback
  return value stays ignored, so ``outputs`` is always empty.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``invoke`` | callback calling one ``@node`` | 1 record, node.started+completed | TC-J1-CBP-EP-001 |
| ``invoke`` | callback calling two ``@node``s | 2 records, seq 1 then 2 | TC-J1-CBP-EP-002 |
| ``invoke`` | callback calling no ``@node`` | completed, empty call log, no node events | TC-J1-CBP-EP-003 |
| ``invoke`` | every record's ``parent_flow`` | the callback's flow_id | TC-J1-CBP-EP-004 |
| ``invoke`` | recorder configuration | taken from the run config, not defaults | TC-J1-CBP-EP-005 |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| ``invoke`` | ``@node`` inside the callback raises | TileExecutionError keeps the failed record | TC-J1-CBP-BV-001 |
| ``invoke`` | callback raises ``StructuredError`` | ecode reachable via ``__cause__``, records kept | TC-J1-CBP-BV-002 |
| ``invoke`` | callback raises after a successful node | the completed record survives the failure | TC-J1-CBP-BV-003 |
| ``invoke`` | ``function=None`` | completed, empty log, sentinel flow_id, no events | TC-J1-CBP-BV-004 |
| ``invoke`` | node events emitted once | no duplicate node.* on either path | TC-J1-CBP-BV-005 |
| ``invoke`` | flow stack after the call | restored, so the next tile cannot inherit it | TC-J1-CBP-BV-006 |
| ``invoke`` | ``@node`` called outside the invoker | unrecorded (proves the context is what records) | TC-J1-CBP-BV-007 |
| ``invoke`` | interruption (3004) inside the callback | still classified as an interruption at the tile boundary | TC-J1-CBP-BV-008 |
| ``invoke`` | event vocabulary | no name outside §8.1's node set | TC-J1-CBP-BV-009 |

Divergence table — the one *published* value J1 changes (audit Finding 1):

| API | Case | Expected | Test ID |
| --- | --- | --- | --- |
| ``Runner.run`` (callback) | callback raises a non-``StructuredError`` | ``job.failed`` / ``RunReport.error`` / ``to_legacy_statuses()`` all carry E3001 and the catalogue message, which contains the original text | TC-J1-CBP-EV-010 |
| v1 vs v2 | same fixture, same plain-raising callback | measured divergence: v1 ``ErrorCode=999`` + ``Unexpected error in Invoice mode: boom``; v2 ``ErrorCode=3001`` + catalogue text; both contain ``boom`` | TC-J1-CBP-EV-011 |
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.api.request import LegacyCallbackTarget, RunRequest
from rdetoolkit.compat.v1.callback import (
    NO_CALLBACK_FLOW_ID,
    LegacyCallbackInvoker,
    callback_flow_id,
)
from rdetoolkit.core.context import RunContext
from rdetoolkit.core.flow import current_flow_id
from rdetoolkit.core.node import node
from rdetoolkit.errors import ERROR_CATALOG, RdeExecutionError
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.report.events import Event, MemoryEventSink
from rdetoolkit.runner.execute import TileExecutionError
from rdetoolkit.runner.finalize import PASSTHROUGH_ERROR_NAME
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.paths import resolve_tile_paths
from rdetoolkit.runner.planner import TileMaterial
from rdetoolkit.types import (
    InputPaths,
    IterationInfo,
    OutputContext,
    RdeConfig,
    V2ExecutionSettings,
    V2RecordingSettings,
)
from tests.v2.contract.fixtures import _generate

_RUN_INTERRUPTED_CODE = 3004
_USER_ERROR_CODE = 999
_STRUCTURED_MESSAGE = "callback said no"


@node(id="tests.j1.cb_probe")
def _cb_probe(label: str) -> str:
    """Recorded work a v1 callback delegates to a ``@node``."""
    return label.upper()


@node(id="tests.j1.cb_boom")
def _cb_boom() -> None:
    """A ``@node`` that fails inside a v1 callback."""
    msg = "node inside callback exploded"
    raise ValueError(msg)


def _context(tmp_path: Path, *, config: RdeConfig | None = None) -> RunContext:
    data_root = tmp_path / "data"
    rawfile = data_root / "inputdata" / "sample.txt"
    rawfile.parent.mkdir(parents=True, exist_ok=True)
    rawfile.write_text("raw\n", encoding="utf-8")
    return RunContext(
        paths=InputPaths(
            inputdata=data_root / "inputdata",
            invoice=data_root / "invoice",
            tasksupport=data_root / "tasksupport",
            raw=rawfile,
            rawfiles=(rawfile,),
        ),
        out=OutputContext.from_resource_paths(resolve_tile_paths(data_root, 0)),
        config=config or RdeConfig(),
        iteration=IterationInfo(index=0, total=1, mode="invoice"),
    )


def _invoke(
    callback: Any,
    context: RunContext,
    *,
    sink: MemoryEventSink | None = None,
) -> Any:
    assert context.paths is not None
    sink = sink if sink is not None else MemoryEventSink()
    return LegacyCallbackInvoker().invoke(
        LegacyCallbackTarget(function=callback),
        context,
        event_sink=sink,
        run_id="j1-run",
        config=context.config or RdeConfig(),
        material=TileMaterial(invoice_source=context.paths.invoice / "invoice.json"),
    )


def _names(sink: MemoryEventSink) -> list[str]:
    return [event.name for event in sink.events]


def _callback_one_node(srcpaths: object, resource_paths: object) -> None:
    del srcpaths, resource_paths
    _cb_probe("a")


def _callback_two_nodes(srcpaths: object, resource_paths: object) -> None:
    del srcpaths, resource_paths
    _cb_probe("a")
    _cb_probe("b")


def _callback_no_node(srcpaths: object, resource_paths: object) -> None:
    del srcpaths, resource_paths


def _callback_failing_node(srcpaths: object, resource_paths: object) -> None:
    del srcpaths, resource_paths
    _cb_boom()


def _callback_structured_error(srcpaths: object, resource_paths: object) -> None:
    del srcpaths, resource_paths
    raise StructuredError(_STRUCTURED_MESSAGE, ecode=_USER_ERROR_CODE)


def _callback_node_then_raise(srcpaths: object, resource_paths: object) -> None:
    del srcpaths, resource_paths
    _cb_probe("a")
    raise StructuredError(_STRUCTURED_MESSAGE, ecode=_USER_ERROR_CODE)


def _callback_interrupted(srcpaths: object, resource_paths: object) -> None:
    del srcpaths, resource_paths
    error_def = ERROR_CATALOG[_RUN_INTERRUPTED_CODE]
    error_cls: Any = RdeExecutionError
    raise error_cls(
        code=_RUN_INTERRUPTED_CODE,
        name=error_def.name,
        message=error_def.message_template,
    )


def test_one_node_call_is_recorded_and_bridged__tc_j1_cbp_ep_001(tmp_path: Path) -> None:
    """TC-J1-CBP-EP-001: the callback's single ``@node`` becomes one record + two events."""
    # Given: a v1 callback that delegates its work to one @node
    sink = MemoryEventSink()

    # When: the unified adapter invokes it for one tile
    result = _invoke(_callback_one_node, _context(tmp_path), sink=sink)

    # Then: the call log carries exactly that call, with the tile's index
    assert result.status == "completed"
    assert [record.node_id for record in result.call_records] == ["tests.j1.cb_probe"]
    assert result.call_records[0].iteration_index == 0
    assert result.call_records[0].status == "completed"

    # And: it was bridged to node events, and nothing else was emitted
    assert _names(sink) == ["node.started", "node.completed"]
    assert {event.node_id for event in sink.events} == {"tests.j1.cb_probe"}

    # And: the callback's own return value is never an output (v1 ignores it)
    assert result.outputs == ()


def test_two_node_calls_keep_their_order__tc_j1_cbp_ep_002(tmp_path: Path) -> None:
    """TC-J1-CBP-EP-002: seq is the call order inside the callback."""
    # Given / When: a callback calling the same @node twice
    sink = MemoryEventSink()
    result = _invoke(_callback_two_nodes, _context(tmp_path), sink=sink)

    # Then: both calls are recorded in order with distinct call ids
    assert [record.seq for record in result.call_records] == [1, 2]
    assert [record.call_id for record in result.call_records] == [
        "tests.j1.cb_probe#1",
        "tests.j1.cb_probe#2",
    ]

    # And: each recorded call produced its own event pair
    assert _names(sink) == ["node.started", "node.completed", "node.started", "node.completed"]


def test_callback_without_nodes_records_nothing__tc_j1_cbp_ep_003(tmp_path: Path) -> None:
    """TC-J1-CBP-EP-003: non-``@node`` work stays structurally invisible."""
    # Given / When: a callback that does work the recorder cannot see
    sink = MemoryEventSink()
    result = _invoke(_callback_no_node, _context(tmp_path), sink=sink)

    # Then: the tile completes with an empty call log and no node events
    assert result.status == "completed"
    assert result.call_records == ()
    assert sink.events == []


def test_every_record_carries_the_callback_flow_id__tc_j1_cbp_ep_004(tmp_path: Path) -> None:
    """TC-J1-CBP-EP-004: the ``parent_flow == flow_id`` invariant holds here."""
    # Given: the flow_id the report will carry for this callback target
    expected = callback_flow_id(_callback_two_nodes)

    # When: invoking the callback
    result = _invoke(_callback_two_nodes, _context(tmp_path))

    # Then: every record names that flow as its parent
    assert [record.parent_flow for record in result.call_records] == [expected, expected]


def test_recorder_uses_the_run_configuration__tc_j1_cbp_ep_005(tmp_path: Path) -> None:
    """TC-J1-CBP-EP-005: the adapter builds the recorder like ``run_tile`` does.

    ``provenance.repr_head`` defaults to ``on``, so an adapter that ignored the
    effective config would still capture repr heads.
    """
    # Given: a run that disabled repr capture
    config = RdeConfig(provenance=V2RecordingSettings(repr_head="off"))

    # When: invoking a callback that calls one @node
    result = _invoke(_callback_one_node, _context(tmp_path, config=config), sink=None)

    # Then: the record honours the run's provenance setting
    record = result.call_records[0]
    assert record.inputs["label"].repr_head is None
    assert record.inputs["label"].type_name == "str"

    # And: the default configuration still captures it, so the seat is discriminating
    enabled = _invoke(_callback_one_node, _context(tmp_path / "on"))
    assert enabled.call_records[0].inputs["label"].repr_head == "'a'"


def test_failing_node_keeps_its_record_on_the_error__tc_j1_cbp_bv_001(tmp_path: Path) -> None:
    """TC-J1-CBP-BV-001: a failing tile must not lose its call log (trap #2)."""
    # Given: a callback whose @node raises
    sink = MemoryEventSink()

    # When / Then: the adapter raises the shared tile failure carrying the records
    with pytest.raises(TileExecutionError) as exc_info:
        _invoke(_callback_failing_node, _context(tmp_path), sink=sink)

    failed = exc_info.value.result
    assert failed.status == "failed"
    assert [record.node_id for record in failed.call_records] == ["tests.j1.cb_boom"]
    assert failed.call_records[0].status == "failed"
    assert failed.error is not None
    assert failed.error["call_id"] == "tests.j1.cb_boom#1"
    assert failed.stacktrace is not None

    # And: the failure was bridged as node.failed, never node.completed
    assert _names(sink) == ["node.started", "node.failed"]

    # And: the user exception stays reachable for the executor's translation
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_structured_error_survives_the_wrapper__tc_j1_cbp_bv_002(tmp_path: Path) -> None:
    """TC-J1-CBP-BV-002: the I6-0 passthrough contract still applies.

    The executor recovers a ``StructuredError`` from ``TileExecutionError.__cause__``
    (``_with_user_error``), so wrapping must preserve the cause and its ecode.
    """
    # Given / When: a callback raising the v1 user error
    with pytest.raises(TileExecutionError) as exc_info:
        _invoke(_callback_structured_error, _context(tmp_path))

    # Then: the cause is the untouched StructuredError with its ecode
    cause = exc_info.value.__cause__
    assert isinstance(cause, StructuredError)
    assert cause.ecode == _USER_ERROR_CODE
    assert cause.emsg == _STRUCTURED_MESSAGE

    # And: the wrapper itself carries the framework's 3001 classification, which
    # the executor then replaces with the passthrough record
    from rdetoolkit.runner.finalize import structured_error_record  # noqa: PLC0415

    passthrough = structured_error_record(cause)
    assert passthrough == {
        "code": _USER_ERROR_CODE,
        "name": PASSTHROUGH_ERROR_NAME,
        "message": _STRUCTURED_MESSAGE,
    }


def test_records_before_the_failure_survive__tc_j1_cbp_bv_003(tmp_path: Path) -> None:
    """TC-J1-CBP-BV-003: the callback's completed nodes stay in the failed result."""
    # Given / When: a callback that fails after one successful @node
    sink = MemoryEventSink()
    with pytest.raises(TileExecutionError) as exc_info:
        _invoke(_callback_node_then_raise, _context(tmp_path), sink=sink)

    # Then: the completed record is still there
    records = exc_info.value.result.call_records
    assert [(record.node_id, record.status) for record in records] == [
        ("tests.j1.cb_probe", "completed"),
    ]

    # And: the failure was attributed to the callback, not to that node
    assert exc_info.value.result.error is not None
    assert exc_info.value.result.error["call_id"] == "unknown"
    assert _names(sink) == ["node.started", "node.completed"]


def test_absent_callback_reports_the_sentinel_flow__tc_j1_cbp_bv_004(tmp_path: Path) -> None:
    """TC-J1-CBP-BV-004: a callback-free v1 run stays an empty completed tile."""
    # Given / When: the v1 "no custom_dataset_function" boundary
    sink = MemoryEventSink()
    result = _invoke(None, _context(tmp_path), sink=sink)

    # Then: nothing is recorded and nothing is emitted
    assert result.status == "completed"
    assert result.call_records == ()
    assert result.outputs == ()
    assert sink.events == []

    # And: the flow_id such a run reports is the dotted sentinel
    assert callback_flow_id(None) == NO_CALLBACK_FLOW_ID


@pytest.mark.parametrize(
    ("callback", "expected"),
    [
        pytest.param(_callback_two_nodes, 2, id="success"),
        pytest.param(_callback_failing_node, 1, id="failure"),
    ],
)
def test_node_events_are_emitted_exactly_once__tc_j1_cbp_bv_005(
    tmp_path: Path,
    callback: Any,
    expected: int,
) -> None:
    """TC-J1-CBP-BV-005: one bridge call per outcome, never both (trap #3)."""
    # Given: a callback that succeeds or fails
    sink = MemoryEventSink()

    # When: invoking it, tolerating the failure path
    try:
        _invoke(callback, _context(tmp_path), sink=sink)
    except TileExecutionError:
        pass

    # Then: each recorded call produced exactly one started event
    assert _names(sink).count("node.started") == expected
    assert len(sink.events) == expected * 2


def test_flow_stack_is_restored_after_the_tile__tc_j1_cbp_bv_006(tmp_path: Path) -> None:
    """TC-J1-CBP-BV-006: tile N+1 cannot inherit tile N's pushed flow id."""
    # Given: no active flow before the tile
    assert current_flow_id() is None

    # When: invoking a callback that succeeds and one that fails
    _invoke(_callback_one_node, _context(tmp_path / "ok"))
    assert current_flow_id() is None
    with pytest.raises(TileExecutionError):
        _invoke(_callback_failing_node, _context(tmp_path / "ng"))

    # Then: the stack is empty again after both outcomes
    assert current_flow_id() is None


def test_node_outside_the_adapter_is_not_recorded__tc_j1_cbp_bv_007() -> None:
    """TC-J1-CBP-BV-007: the recorder context is what records, nothing else.

    This is the pre-J1 behaviour the CB-OBS seats must be able to detect: the
    same ``@node``, called without an active recorder, is a plain function call.
    """
    # Given: no active recorder and no active flow
    assert current_flow_id() is None

    # When: calling the @node directly
    actual = _cb_probe("a")

    # Then: it executed transparently and recorded nothing observable
    assert actual == "A"


def test_interruption_is_still_an_interruption__tc_j1_cbp_bv_008(tmp_path: Path) -> None:
    """TC-J1-CBP-BV-008: wrapping must not hide a 3004 from the tile boundary.

    ``TileExecutor`` re-raises an interruption instead of turning it into a
    failed tile, and it recognises it by ``RdeExecutionError.code == 3004``. The
    wrapper adopts the cause's catalog code, so the classification survives —
    exactly as it does for a ``@flow`` through ``run_tile``.
    """
    # Given / When: a callback interrupted by SIGTERM's raiser
    with pytest.raises(TileExecutionError) as exc_info:
        _invoke(_callback_interrupted, _context(tmp_path))

    # Then: the wrapper carries the interruption code, not the generic 3001
    assert exc_info.value.code == _RUN_INTERRUPTED_CODE
    assert isinstance(exc_info.value.__cause__, RdeExecutionError)


def test_event_factory_vocabulary_is_unchanged__tc_j1_cbp_bv_009(tmp_path: Path) -> None:
    """TC-J1-CBP-BV-009: the callback path introduces no new event name (§8.1)."""
    # Given: the closed §8.1 node vocabulary
    allowed = {"node.started", "node.completed", "node.failed"}

    # When: exercising both callback outcomes
    sink = MemoryEventSink()
    _invoke(_callback_two_nodes, _context(tmp_path / "ok"), sink=sink)
    with pytest.raises(TileExecutionError):
        _invoke(_callback_failing_node, _context(tmp_path / "ng"), sink=sink)

    # Then: every emitted name comes from the existing factories
    assert set(_names(sink)) <= allowed
    assert all(isinstance(event, Event) for event in sink.events)


# --------------------------------------------------------------------------
# The plain-exception failure report (audit Finding 1)
#
# A callback that raises something other than ``StructuredError`` is the one case
# where J1 changed a *published* value. It is unified with the flow path on
# purpose, it matches neither pre-J1 v2 nor v1, and no frozen cell covered it --
# so it is pinned here on both sides: the v2 contract, and the measured v1
# divergence.
# --------------------------------------------------------------------------

_PLAIN_FAILURE_MESSAGE = "boom"

#: v1's own wrapper for a callback exception that is not a ``StructuredError``.
#: ``workflows._process_mode``'s outer ``except Exception`` re-raises it as
#: ``StructuredError(f"Unexpected error in {mode} mode: {exc}", 999)``
#: (workflows.py:400-401) -- the ``Processing failed in ... mode`` branch at
#: :399 is for a pipeline that *returns* a failed status without raising, which
#: the invoice pipeline does not do for a raising callback.
_V1_PLAIN_FAILURE_CODE = "ErrorCode=999"
_V2_PLAIN_FAILURE_CODE = "ErrorCode=3001"

_V1_PLAIN_ORACLE_WORKER = """
import json, os, sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, os.getcwd())
from rdetoolkit.workflows import _run_legacy as v1_run
from tests.v2.contract.fixtures import _generate


def boom(srcpaths, resource_paths):
    raise ValueError("boom")


os.chdir(root)
exit_code = 0
try:
    v1_run(custom_dataset_function=boom, config=_generate.oracle_config("invoice"))
except SystemExit as error:
    exit_code = int(error.code or 0)

job_failed = root / "data" / "job.failed"
text = job_failed.read_text(encoding="utf-8") if job_failed.exists() else None
(root / ".plain_failure_observation.json").write_text(
    json.dumps({"exit_code": exit_code, "job_failed_text": text}),
    encoding="utf-8",
)
"""


def _callback_plain_error(srcpaths: object, resource_paths: object) -> None:
    """Fail with an ordinary exception, the way a buggy v1 callback does."""
    del srcpaths, resource_paths
    raise ValueError(_PLAIN_FAILURE_MESSAGE)


def _run_callback_through_runner(root: Path, callback: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Run one v1 callback for a materialized invoice case through the Runner."""
    _generate.materialize_sut_case("invoice", root)
    monkeypatch.chdir(root)
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
    )
    return runner.run(
        RunRequest(
            root=root,
            target=LegacyCallbackTarget(function=callback),
            config_source=_generate.oracle_config("invoice"),
        ),
    )


def test_plain_exception_is_reported_as_e3001__tc_j1_cbp_ev_010(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-J1-CBP-EV-010: a non-StructuredError callback failure publishes E3001.

    This is the deliberate consequence of routing the callback failure through
    ``TileExecutionError``: ``_failed_error`` catalogues it as 3001 exactly as it
    does for a ``@flow``, so ``job.failed``, ``RunReport.error`` and
    ``to_legacy_statuses()`` all carry the catalog code and message instead of the
    bare ``str(exc)`` the pre-J1 executor branch produced. The original text
    survives inside the catalogue message, and ``call_id`` identifies where the
    failure happened.
    """
    # Given: a v1 callback raising an ordinary exception
    root = tmp_path / "v2"

    # When: running it through the unified Runner
    report = _run_callback_through_runner(root, _callback_plain_error, monkeypatch)

    # Then: the run failed with the catalogued node-execution error
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == 3001
    assert report.error["name"] == ERROR_CATALOG[3001].name
    assert report.error["call_id"] == "unknown"
    assert _PLAIN_FAILURE_MESSAGE in report.error["message"]

    # And: job.failed publishes that same code and message
    job_failed = (root / "data" / "job.failed").read_text(encoding="utf-8")
    assert job_failed.splitlines()[0] == _V2_PLAIN_FAILURE_CODE
    assert _PLAIN_FAILURE_MESSAGE in job_failed

    # And: the v1-compatibility projection agrees with it
    statuses = json.loads(report.to_legacy_statuses())["statuses"]
    assert [status["error_code"] for status in statuses] == [3001]
    assert _PLAIN_FAILURE_MESSAGE in statuses[0]["error_message"]
    assert statuses[0]["stacktrace"]


def test_plain_exception_divergence_from_v1_is_a_checked_contract__tc_j1_cbp_ev_011(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-J1-CBP-EV-011: the documented v1 divergence is measured, not assumed.

    ``contracts.md`` §J1-5 lists this as an intentional divergence. A claimed
    divergence that nothing measures is indistinguishable from drift, so this
    cell runs v1 itself -- in its own process, on the same fixture, with the same
    callback -- and asserts both sides of the difference.
    """
    # Given: the same invoice fixture and the same plain-raising callback
    v1_root = tmp_path / "v1"
    v2_root = tmp_path / "v2"
    _generate.materialize_sut_case("invoice", v1_root)
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _V1_PLAIN_ORACLE_WORKER, str(v1_root)],
        cwd=_generate.REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    observation_path = v1_root / ".plain_failure_observation.json"
    if not observation_path.exists():
        message = f"v1 plain-failure oracle failed: {completed.stderr[-1500:]}"
        raise RuntimeError(message)
    v1_observation = json.loads(observation_path.read_text(encoding="utf-8"))

    # When: running the same callback through the unified Runner
    report = _run_callback_through_runner(v2_root, _callback_plain_error, monkeypatch)
    v2_job_failed = (v2_root / "data" / "job.failed").read_text(encoding="utf-8")

    # Then: v1 wraps it as its own 999 with a mode-prefixed message
    v1_job_failed = v1_observation["job_failed_text"]
    assert v1_observation["exit_code"] == 1
    assert v1_job_failed.splitlines()[0] == _V1_PLAIN_FAILURE_CODE
    assert "Unexpected error in Invoice mode: boom" in v1_job_failed

    # And: v2 publishes the catalogued 3001 instead -- the documented divergence
    assert v2_job_failed.splitlines()[0] == _V2_PLAIN_FAILURE_CODE
    assert ERROR_CATALOG[3001].name == "NodeExecutionFailed"
    assert v2_job_failed.splitlines()[0] != v1_job_failed.splitlines()[0]

    # And: the user's own text survives on both sides, which is what an operator
    # reads first in either format
    assert _PLAIN_FAILURE_MESSAGE in v1_job_failed
    assert _PLAIN_FAILURE_MESSAGE in v2_job_failed

    # And: both runs fail; the divergence is in the report, not in the outcome
    assert report.status == "failed"
