"""In-flight node invocations are observable before the node returns (#689, GA-07).

``node.started`` / ``node.completed`` / ``node.failed`` are replayed from the
call log after the flow returns or raises, so a process that dies inside a
long-running node left no trace of the node it was running. Each invocation
now emits an additive ``node.invocation_started`` event at call entry -- right
before the body runs -- and a correlated ``node.invocation_finished`` event
when the body returns or raises. Both carry a run-unique ``invocation_id``
that is *not* drawn from the call-log ``seq``: ``seq`` / ``call_id`` stay
allocated at append time in post-order, exactly as before.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-GA689-EP-001 | blocking node | body waits on a primitive | flushed ``invocation_started`` on disk before release |
| TC-GA689-EP-002 | completed | body returns | ``finished`` outcome completed, ``call_id`` of the record |
| TC-GA689-EP-003 | raised | body raises | ``finished`` outcome failed + error_type; ``node.failed`` kept |
| TC-GA689-EP-004 | return mismatch | strict, wrong return type | ``finished`` failed with the executed call's id |
| TC-GA689-EP-005 | nested | outer calls inner | pre-order starts, parent link, post-order seq unchanged |
| TC-GA689-EP-006 | multi tile | Runner, 2 tiles | unique ids across tiles, per-tile ``iteration_index`` |
| TC-GA689-EP-007 | factories | event constructors | schema_version "1", payload keys |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-GA689-EV-010 | rejection | strict argument mismatch | no invocation events (body never ran) |
| TC-GA689-EV-011 | no listener | standalone recorder | records unchanged, ids still unique |
| TC-GA689-EV-012 | listener fails | listener raises | node outcome/record unchanged, listener muted |
| TC-GA689-EV-013 | interruption | listener raises 3004 | interruption propagates |
| TC-GA689-EV-014 | sink fails | Runner, sink raises on in-flight | run succeeds, one stderr notice |
| TC-GA689-EV-015 | log cap | tiny cap | W1002 once; run/iteration outline kept |
| TC-GA689-EV-016 | BaseException | KeyboardInterrupt in body | ``started`` unmatched, no record |
| TC-GA689-EV-017 | SIGKILL | process killed mid-node | last on-disk node event is the unmatched start |
| TC-GA689-EV-018 | seq | invocation ids vs seq | sequence counter not consumed by invocations |
| TC-GA689-EV-019 | factories | empty ids / bad outcome | ValueError |
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.core.calllog import CallLogRecorder, CallSequence, NodeCallRecord, NodeInvocation
from rdetoolkit.core.context import RunContext
from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.errors import ERROR_CATALOG, RdeExecutionError
from rdetoolkit.report.events import Event, FileEventSink, MemoryEventSink
from rdetoolkit.runner.execute import InvocationEventEmitter, TileExecutionError, run_tile
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths, IterationInfo, RdeConfig
from tests.v2.contract.fixtures import _generate

_STARTED = "node.invocation_started"
_FINISHED = "node.invocation_finished"


@node(id="tests.v2.core.ga689.ok")
def ok_node() -> int:
    return 1


@node(id="tests.v2.core.ga689.boom")
def boom_node() -> None:
    msg = "ga689 boom"
    raise ValueError(msg)


@node(id="tests.v2.core.ga689.bad_return")
def bad_return_node() -> int:
    return "not an int"  # type: ignore[return-value]


@node(id="tests.v2.core.ga689.takes_int")
def takes_int(count: int) -> int:
    return count


@node(id="tests.v2.core.ga689.inner")
def inner_node() -> int:
    return 2


@node(id="tests.v2.core.ga689.outer")
def outer_node() -> int:
    return inner_node() + 1


@node(id="tests.v2.core.ga689.interrupted")
def interrupted_node() -> None:
    raise KeyboardInterrupt


class _Recording:
    """Listener double that keeps every notification in order."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, NodeInvocation, NodeCallRecord | None]] = []

    def invocation_started(self, invocation: NodeInvocation) -> None:
        self.calls.append(("started", invocation, None))

    def invocation_finished(self, invocation: NodeInvocation, record: NodeCallRecord) -> None:
        self.calls.append(("finished", invocation, record))


class _RaisingListener:
    """Listener that raises on every notification."""

    def __init__(self, error: Exception) -> None:
        self.error = error
        self.attempts = 0

    def invocation_started(self, invocation: NodeInvocation) -> None:
        self.attempts += 1
        raise self.error

    def invocation_finished(self, invocation: NodeInvocation, record: NodeCallRecord) -> None:
        self.attempts += 1
        raise self.error


def _context(tmp_path: Path, index: int = 0) -> RunContext:
    return RunContext(
        paths=InputPaths(inputdata=tmp_path / "inputdata", invoice=tmp_path / "invoice", tasksupport=tmp_path / "tasksupport"),
        out=None,
        config=RdeConfig(),
        invoice=None,
        iteration=IterationInfo(index=index, total=1, mode="invoice"),
    )


def _node_events(sink: MemoryEventSink) -> list[Event]:
    return [event for event in sink.events if event.name.startswith("node.")]


def _file_events(path: Path) -> list[dict[str, Any]]:
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [line for line in lines if "name" in line]


# --------------------------------------------------------------------------- EP


def test_blocking_node_is_on_disk_before_its_body_finishes__tc_ga689_ep_001(tmp_path: Path) -> None:
    """TC-GA689-EP-001: the start line is flushed while the body still blocks."""
    # Given: a node blocked on an Event and a file sink
    entered = threading.Event()
    release = threading.Event()

    @node(id="tests.v2.core.ga689.blocking")
    def blocking() -> None:
        entered.set()
        assert release.wait(30)

    @flow
    def blocking_flow(iteration: IterationInfo) -> None:
        _ = iteration
        blocking()

    sink = FileEventSink(tmp_path / "logs")
    sink.open("run-689")
    outcome: dict[str, Any] = {}

    def _target() -> None:
        outcome["result"] = run_tile(
            blocking_flow, _context(tmp_path), event_sink=sink, run_id="run-689", config=RdeConfig(), emit_iteration_events=False,
        )

    worker = threading.Thread(target=_target)
    worker.start()
    try:
        # When: the body is running and has not returned
        assert entered.wait(30)
        assert sink.path is not None
        in_flight = _file_events(sink.path)
    finally:
        release.set()
        worker.join(30)
    sink.close()

    # Then: exactly the in-flight start is visible -- no replayed node events yet
    assert [event["name"] for event in in_flight] == [_STARTED]
    assert in_flight[0]["node_id"] == "tests.v2.core.ga689.blocking"
    assert in_flight[0]["payload"] == {"invocation_id": "inv-1", "iteration_index": 0, "parent_invocation_id": None}

    # And: after release the start is matched and the classic events follow
    names = [event["name"] for event in _file_events(sink.path)]
    assert names == [_STARTED, _FINISHED, "node.started", "node.completed"]
    assert outcome["result"].status == "completed"


def test_completed_invocation_is_correlated_to_its_call__tc_ga689_ep_002(tmp_path: Path) -> None:
    """TC-GA689-EP-002: the finish names the outcome and the record's call_id."""

    @flow
    def ok_flow(iteration: IterationInfo) -> None:
        _ = iteration
        ok_node()

    sink = MemoryEventSink()
    result = run_tile(ok_flow, _context(tmp_path), event_sink=sink, run_id="r", config=RdeConfig())

    started, finished, classic_started, classic_completed = _node_events(sink)
    [record] = result.call_records
    assert started.name == _STARTED
    assert finished.name == _FINISHED
    assert finished.node_id == started.node_id == record.node_id
    assert finished.payload["invocation_id"] == started.payload["invocation_id"]
    assert finished.payload["outcome"] == "completed"
    assert finished.payload["call_id"] == record.call_id == "tests.v2.core.ga689.ok#1"
    assert finished.payload["duration_ms"] == record.duration_ms
    assert "error_type" not in finished.payload
    # The replayed events are unchanged by the additive pair.
    assert (classic_started.name, classic_started.payload) == ("node.started", {"call_id": record.call_id})
    assert classic_completed.name == "node.completed"


def test_raised_exception_emits_failed_finish_and_keeps_node_failed__tc_ga689_ep_003(tmp_path: Path) -> None:
    """TC-GA689-EP-003: a raising body is a failed finish, plus node.failed."""

    @flow
    def boom_flow(iteration: IterationInfo) -> None:
        _ = iteration
        boom_node()

    sink = MemoryEventSink()
    with pytest.raises(TileExecutionError) as raised:
        run_tile(boom_flow, _context(tmp_path), event_sink=sink, run_id="r", config=RdeConfig())

    [record] = raised.value.result.call_records
    names = [event.name for event in _node_events(sink)]
    assert names == [_STARTED, _FINISHED, "node.started", "node.failed"]
    finished = _node_events(sink)[1]
    assert finished.payload["outcome"] == "failed"
    assert finished.payload["error_type"] == "ValueError"
    assert finished.payload["call_id"] == record.call_id
    assert record.status == "failed"


def test_return_type_error_is_attributable__tc_ga689_ep_004(tmp_path: Path) -> None:
    """TC-GA689-EP-004: a strict return mismatch finishes failed on the executed call."""

    @flow
    def bad_flow(iteration: IterationInfo) -> None:
        _ = iteration
        bad_return_node()

    config = RdeConfig.model_validate({"execution": {"type_check": "strict"}})
    sink = MemoryEventSink()
    with pytest.raises(TileExecutionError) as raised:
        run_tile(bad_flow, _context(tmp_path), event_sink=sink, run_id="r", config=config)

    [record] = raised.value.result.call_records
    finished = next(event for event in sink.events if event.name == _FINISHED)
    assert finished.payload["outcome"] == "failed"
    assert finished.payload["error_type"] == "RdeExecutionError"
    assert finished.payload["call_id"] == record.call_id == "tests.v2.core.ga689.bad_return#1"
    assert raised.value.code == 3002


def test_nested_calls_have_unique_ids_and_unchanged_seq__tc_ga689_ep_005() -> None:
    """TC-GA689-EP-005: starts are pre-order, seq stays post-order."""
    listener = _Recording()
    with CallLogRecorder(invocation_listener=listener) as recorder:
        outer_node()

    kinds = [(kind, invocation.node_id) for kind, invocation, _ in listener.calls]
    assert kinds == [
        ("started", "tests.v2.core.ga689.outer"),
        ("started", "tests.v2.core.ga689.inner"),
        ("finished", "tests.v2.core.ga689.inner"),
        ("finished", "tests.v2.core.ga689.outer"),
    ]
    outer_inv = listener.calls[0][1]
    inner_inv = listener.calls[1][1]
    assert (outer_inv.invocation_id, inner_inv.invocation_id) == ("inv-1", "inv-2")
    assert outer_inv.parent_invocation_id is None
    assert inner_inv.parent_invocation_id == outer_inv.invocation_id
    # The call log keeps its post-order seq: inner appends first.
    assert [(record.node_id, record.seq) for record in recorder.records] == [
        ("tests.v2.core.ga689.inner", 1),
        ("tests.v2.core.ga689.outer", 2),
    ]
    # Each finish is correlated to the record of the same call.
    assert listener.calls[2][2] is recorder.records[0]
    assert listener.calls[3][2] is recorder.records[1]


@flow
def two_calls_flow(paths: InputPaths) -> None:
    _ = paths
    ok_node()
    outer_node()


def test_multiple_tiles_get_run_unique_ids__tc_ga689_ep_006(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA689-EP-006: ids stay unique across the tiles of one Runner run."""
    root = tmp_path / "multi"
    _generate.materialize_sut_case("multidatatile", root)
    monkeypatch.chdir(root)
    sink = MemoryEventSink()
    report = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
        event_sink=sink,
    ).run(two_calls_flow, system={"extended_mode": "MultiDataTile"})

    assert report.status == "success"
    starts = [event for event in sink.events if event.name == _STARTED]
    finishes = [event for event in sink.events if event.name == _FINISHED]
    tiles = len(report.iterations)
    assert tiles >= 2
    assert len(starts) == len(finishes) == 3 * tiles
    ids = [event.payload["invocation_id"] for event in starts]
    assert len(set(ids)) == len(ids)
    assert {event.payload["invocation_id"] for event in finishes} == set(ids)
    assert sorted({event.payload["iteration_index"] for event in starts}) == list(range(tiles))
    # Every finish names a call_id the run report knows.
    reported = {call["call_id"] for iteration in report.iterations for call in iteration["node_calls"]}
    assert {event.payload["call_id"] for event in finishes} == reported


def test_event_factories_shape__tc_ga689_ep_007() -> None:
    """TC-GA689-EP-007: the additive events follow the v1 event schema."""
    started = Event.node_invocation_started(run_id="r", node_id="n", invocation_id="inv-3", iteration_index=2, parent_invocation_id="inv-1")
    finished = Event.node_invocation_finished(
        run_id="r", node_id="n", invocation_id="inv-3", iteration_index=2, outcome="failed", call_id="n#4", duration_ms=1.5, error_type="KeyError",
    )

    assert started.to_dict() == {
        "schema_version": "1",
        "run_id": "r",
        "name": _STARTED,
        "timestamp": started.timestamp,
        "node_id": "n",
        "payload": {"invocation_id": "inv-3", "iteration_index": 2, "parent_invocation_id": "inv-1"},
    }
    assert finished.payload == {
        "invocation_id": "inv-3",
        "iteration_index": 2,
        "outcome": "failed",
        "call_id": "n#4",
        "duration_ms": 1.5,
        "error_type": "KeyError",
    }
    completed = Event.node_invocation_finished(
        run_id="r", node_id="n", invocation_id="inv-3", iteration_index=2, outcome="completed", call_id="n#4", duration_ms=0.0,
    )
    assert "error_type" not in completed.payload


# ------------------------------------------------------------------ negative / BV


def test_argument_rejection_emits_no_invocation__tc_ga689_ev_010() -> None:
    """TC-GA689-EV-010: a rejected call never ran, so it is not an invocation."""
    listener = _Recording()
    with pytest.raises(RdeExecutionError) as raised, CallLogRecorder(type_check="strict", invocation_listener=listener) as recorder:
        takes_int("x")  # type: ignore[arg-type]

    assert raised.value.code == 3002
    assert listener.calls == []
    assert recorder.records == ()


def test_recorder_without_listener_is_unchanged__tc_ga689_ev_011() -> None:
    """TC-GA689-EV-011: no listener means no dependency and the same records."""
    with CallLogRecorder() as recorder:
        outer_node()
        ok_node()

    assert [record.call_id for record in recorder.records] == [
        "tests.v2.core.ga689.inner#1",
        "tests.v2.core.ga689.outer#2",
        "tests.v2.core.ga689.ok#3",
    ]


def test_failing_listener_never_changes_the_node_outcome__tc_ga689_ev_012() -> None:
    """TC-GA689-EV-012: a broken listener is muted; the call still records."""
    listener = _RaisingListener(OSError("disk full"))
    with CallLogRecorder(invocation_listener=listener) as recorder:
        assert ok_node() == 1
        assert ok_node() == 1
    with pytest.raises(ValueError, match="ga689 boom"), CallLogRecorder(invocation_listener=_RaisingListener(OSError("x"))) as failing:
        boom_node()

    # Then: one attempt, then muted for the rest of that recorder
    assert listener.attempts == 1
    assert [record.status for record in recorder.records] == ["completed", "completed"]
    assert [record.status for record in failing.records] == ["failed"]


def test_run_interruption_from_listener_propagates__tc_ga689_ev_013() -> None:
    """TC-GA689-EV-013: the 3004 run interruption is never swallowed."""
    error_def = ERROR_CATALOG[3004]
    interruption = RdeExecutionError(code=3004, name=error_def.name, message=error_def.message_template)
    with pytest.raises(RdeExecutionError) as raised, CallLogRecorder(invocation_listener=_RaisingListener(interruption)):
        ok_node()

    assert raised.value.code == 3004


class _FailOnInFlightSink(MemoryEventSink):
    """Sink whose in-flight writes fail, as a full disk would."""

    def emit(self, event: Event) -> None:
        if event.name in (_STARTED, _FINISHED):
            msg = "no space left on device"
            raise OSError(msg)
        super().emit(event)


@flow
def ok_flow_for_runner(paths: InputPaths) -> None:
    _ = paths
    ok_node()


def test_sink_failure_keeps_best_effort_behavior__tc_ga689_ev_014(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-GA689-EV-014: an event-log failure neither fails the run nor the node."""
    root = tmp_path / "invoice"
    _generate.materialize_sut_case("invoice", root)
    monkeypatch.chdir(root)
    sink = _FailOnInFlightSink()
    report = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
        event_sink=sink,
    ).run(ok_flow_for_runner)

    assert report.status == "success"
    assert [call["call_id"] for call in report.iterations[0]["node_calls"]] == ["tests.v2.core.ga689.ok#1"]
    assert capsys.readouterr().err.count("event log write failed") == 1


def test_direct_run_tile_with_failing_sink_keeps_the_record__tc_ga689_ev_014b(tmp_path: Path) -> None:
    """TC-GA689-EV-014b: without the Runner guard the node still completes."""
    sink = _FailOnInFlightSink()

    @flow
    def ok_flow(iteration: IterationInfo) -> None:
        _ = iteration
        ok_node()

    result = run_tile(ok_flow, _context(tmp_path), event_sink=sink, run_id="r", config=RdeConfig(), emit_iteration_events=False)

    assert result.status == "completed"
    assert [record.status for record in result.call_records] == ["completed"]
    assert [event.name for event in sink.events] == ["node.started", "node.completed"]


def test_log_cap_keeps_warning_and_outline__tc_ga689_ev_015(tmp_path: Path) -> None:
    """TC-GA689-EV-015: in-flight events obey the node-level cap."""
    sink = FileEventSink(tmp_path / "logs", max_bytes=1)
    sink.open("run-cap")
    sink.emit(Event.run_started(run_id="run-cap"))
    sink.emit(Event.iteration_started(run_id="run-cap", index=0))

    @flow
    def ok_flow(iteration: IterationInfo) -> None:
        _ = iteration
        ok_node()
        ok_node()

    run_tile(ok_flow, _context(tmp_path), event_sink=sink, run_id="run-cap", config=RdeConfig(), emit_iteration_events=False)
    sink.emit(Event.iteration_completed(run_id="run-cap", index=0))
    sink.emit(Event.run_completed(run_id="run-cap", status="success"))
    sink.close()

    assert sink.path is not None
    events = _file_events(sink.path)
    assert [event["name"] for event in events] == ["run.started", "iteration.started", "warning", "iteration.completed", "run.completed"]
    assert events[2]["payload"]["code"] == 1002


def test_base_exception_leaves_an_unmatched_start__tc_ga689_ev_016() -> None:
    """TC-GA689-EV-016: an abrupt BaseException has a start and no finish."""
    listener = _Recording()
    recorder = CallLogRecorder(invocation_listener=listener)
    with pytest.raises(KeyboardInterrupt), recorder:
        interrupted_node()

    assert [kind for kind, _, _ in listener.calls] == ["started"]
    assert recorder.records == ()
    # The parent stack is unwound, so a later call is top-level again.
    with recorder:
        ok_node()
    assert listener.calls[1][1].parent_invocation_id is None
    assert listener.calls[1][1].invocation_id == "inv-2"


_KILL_SCRIPT = textwrap.dedent(
    """
    import sys, time
    from pathlib import Path
    from rdetoolkit.core.context import RunContext
    from rdetoolkit.core.flow import flow
    from rdetoolkit.core.node import node
    from rdetoolkit.report.events import Event, FileEventSink
    from rdetoolkit.runner.execute import run_tile
    from rdetoolkit.types import IterationInfo, RdeConfig

    logs, marker = Path(sys.argv[1]), Path(sys.argv[2])

    @node(id="ga689.quick")
    def quick() -> int:
        return 1

    @node(id="ga689.long_running")
    def long_running() -> None:
        marker.write_text("entered", encoding="utf-8")
        time.sleep(120)

    @flow
    def pipeline(iteration: IterationInfo) -> None:
        quick()
        long_running()

    sink = FileEventSink(logs)
    sink.open("run-kill")
    sink.emit(Event.run_started(run_id="run-kill"))
    context = RunContext(paths=None, out=None, config=RdeConfig(), invoice=None,
                         iteration=IterationInfo(index=0, total=1, mode="invoice"))
    run_tile(pipeline, context, event_sink=sink, run_id="run-kill", config=RdeConfig())
    """,
)


@pytest.mark.skipif(sys.platform == "win32", reason="SIGKILL is POSIX-only")
def test_sigkill_leaves_the_last_observed_invocation__tc_ga689_ev_017(tmp_path: Path) -> None:
    """TC-GA689-EV-017: a killed process leaves its in-flight node on disk."""
    script = tmp_path / "kill_me.py"
    script.write_text(_KILL_SCRIPT, encoding="utf-8")
    logs, marker = tmp_path / "logs", tmp_path / "entered.txt"
    process = subprocess.Popen([sys.executable, str(script), str(logs), str(marker)])  # noqa: S603
    try:
        deadline = time.monotonic() + 60
        while not marker.exists():
            assert process.poll() is None, "worker exited before entering the node"
            assert time.monotonic() < deadline, "worker never entered the long-running node"
            time.sleep(0.05)
        # When: the process dies without any chance to clean up
        os.kill(process.pid, signal.SIGKILL)
        process.wait(30)
    finally:
        if process.poll() is None:
            process.kill()

    # Then: the quick node is matched; the long-running one is the unmatched start
    events = _file_events(logs / "events_run-kill.jsonl")
    node_events = [(event["name"], event["node_id"]) for event in events if event["name"].startswith("node.")]
    assert node_events == [
        (_STARTED, "ga689.quick"),
        (_FINISHED, "ga689.quick"),
        (_STARTED, "ga689.long_running"),
    ]
    assert process.returncode == -signal.SIGKILL


def test_invocations_do_not_consume_seq__tc_ga689_ev_018() -> None:
    """TC-GA689-EV-018: the invocation counter is separate from ``seq``."""
    sequence = CallSequence()
    listener = _Recording()
    with CallLogRecorder(sequence=sequence, invocation_listener=listener):
        outer_node()

    assert sequence.next() == 3
    assert sequence.next_invocation() == 3
    assert [invocation.invocation_id for kind, invocation, _ in listener.calls if kind == "started"] == ["inv-1", "inv-2"]


@pytest.mark.parametrize(
    ("factory", "kwargs"),
    [
        (Event.node_invocation_started, {"run_id": "", "node_id": "n", "invocation_id": "i", "iteration_index": 0}),
        (Event.node_invocation_started, {"run_id": "r", "node_id": "", "invocation_id": "i", "iteration_index": 0}),
        (Event.node_invocation_started, {"run_id": "r", "node_id": "n", "invocation_id": "", "iteration_index": 0}),
        (
            Event.node_invocation_finished,
            {"run_id": "r", "node_id": "n", "invocation_id": "", "iteration_index": 0, "outcome": "completed", "call_id": "c", "duration_ms": 0.0},
        ),
        (
            Event.node_invocation_finished,
            {"run_id": "r", "node_id": "n", "invocation_id": "i", "iteration_index": 0, "outcome": "completed", "call_id": "", "duration_ms": 0.0},
        ),
        (
            Event.node_invocation_finished,
            {"run_id": "r", "node_id": "n", "invocation_id": "i", "iteration_index": 0, "outcome": "skipped", "call_id": "c", "duration_ms": 0.0},
        ),
    ],
)
def test_factories_reject_invalid_fields__tc_ga689_ev_019(factory: Any, kwargs: dict[str, Any]) -> None:
    """TC-GA689-EV-019: required fields and the outcome vocabulary are enforced."""
    with pytest.raises(ValueError):
        factory(**kwargs)


def test_emitter_maps_recorder_notifications_to_events() -> None:
    """The Runner adapter turns notifications into the two event types."""
    sink = MemoryEventSink()
    emitter = InvocationEventEmitter(sink, run_id="r")
    with CallLogRecorder(invocation_listener=emitter):
        outer_node()

    assert [(event.name, event.node_id) for event in sink.events] == [
        (_STARTED, "tests.v2.core.ga689.outer"),
        (_STARTED, "tests.v2.core.ga689.inner"),
        (_FINISHED, "tests.v2.core.ga689.inner"),
        (_FINISHED, "tests.v2.core.ga689.outer"),
    ]
    assert sink.events[1].payload["parent_invocation_id"] == "inv-1"
    assert sink.events[3].payload["call_id"] == "tests.v2.core.ga689.outer#2"
