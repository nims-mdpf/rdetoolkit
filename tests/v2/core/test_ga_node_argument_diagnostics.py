"""A rejected node argument is attributed to its node without a fake call (#688, GA-04).

``CallLogRecorder.call_node`` checks arguments *before* it records a call,
and the call log holds executed calls only. A strict-mode argument mismatch
therefore left no ``NodeCallRecord``: the run error's ``call_id`` read
``unknown`` and the node / parameter were only inside the message text. The
rejection now carries a machine-readable detail (node, parameter, expected
annotation, actual type *name*, iteration), the Runner turns it into a
``node_argument_validation`` diagnostic in the sidecar and an additive
``node.argument_rejected`` event -- while the call log, ``seq`` and
``call_id`` stay exactly as before.

EP table:
| TC | Mode | Call | Expected |
|----|------|------|----------|
| TC-GA688-EP-001 | strict | positional ``int`` given ``str`` | 3002 with detail node/parameter/types/iteration; no record |
| TC-GA688-EP-002 | strict | keyword | same, parameter by name |
| TC-GA688-EP-003 | strict | ``*args`` element | parameter ``values`` |
| TC-GA688-EP-004 | strict | ``**kwargs`` value | parameter ``options`` |
| TC-GA688-EP-005 | strict, Runner | flow calls a node wrongly | sidecar ``node_argument_validation`` + event, iteration 0, no call |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-GA688-EV-010 | nested | outer runs ok inner, then rejects | inner/outer keep seq 1/2; only executed calls recorded |
| TC-GA688-EV-011 | no value repr | secret string rejected | secret in no detail, message, diagnostic or event |
| TC-GA688-EV-012 | counter | rejection between two calls | the next executed call gets the next seq (no gap) |
| TC-GA688-EV-013 | warn | wrong type | UserWarning, body runs, completed record, no rejection |
| TC-GA688-EV-014 | off | wrong type | no check, body runs |
| TC-GA688-EV-015 | return mismatch | strict, wrong return | failed record of the executed call; not a rejection |
| TC-GA688-EV-016 | shallow | ``list[int]`` given ``["a"]`` | accepted (origin check only) |
| TC-GA688-EV-017 | annotation text | ``str | None`` / ``pathlib.Path`` | readable names, never values |
| TC-GA688-EV-018 | Runner return mismatch | strict | ``node_execution`` with the executed call's id |
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.core.calllog import CallLogRecorder, CallSequence
from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.errors import RdeExecutionError
from rdetoolkit.report.failure import NODE_ARGUMENT_REJECTION, failure_diagnostic, node_argument_rejection
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths
from tests.v2.contract.fixtures import _generate

SECRET = "TOPSECRET-688-value"


@node(id="tests.v2.core.ga688.takes_int")
def takes_int(count: int) -> int:
    return count


@node(id="tests.v2.core.ga688.takes_optional")
def takes_optional(label: str | None) -> None:
    _ = label


@node(id="tests.v2.core.ga688.takes_path")
def takes_path(where: Path) -> None:
    _ = where


@node(id="tests.v2.core.ga688.total")
def total(*values: int) -> int:
    return sum(values)


@node(id="tests.v2.core.ga688.options")
def options(**options: int) -> int:
    return len(options)


@node(id="tests.v2.core.ga688.list_int")
def takes_list(items: list[int]) -> int:
    return len(items)


@node(id="tests.v2.core.ga688.bad_return")
def bad_return() -> int:
    return "not an int"  # type: ignore[return-value]


@node(id="tests.v2.core.ga688.ok_inner")
def ok_inner() -> int:
    return 1


@node(id="tests.v2.core.ga688.outer")
def outer() -> int:
    ok_inner()
    return takes_int("wrong")  # type: ignore[arg-type]


_BODY_RAN: list[str] = []


@node(id="tests.v2.core.ga688.records_body")
def records_body(count: int) -> None:
    _ = count
    _BODY_RAN.append("ran")


@flow
def rejecting_flow(paths: InputPaths) -> None:
    _ = paths
    takes_int("not a number")  # type: ignore[arg-type]


@flow
def secret_rejecting_flow(paths: InputPaths) -> None:
    _ = paths
    takes_int(SECRET)  # type: ignore[arg-type]


@flow
def bad_return_flow(paths: InputPaths) -> None:
    _ = paths
    bad_return()


def _rejected(fn: Any, *args: Any, iteration_index: int = 0, **kwargs: Any) -> tuple[RdeExecutionError, CallLogRecorder]:
    recorder = CallLogRecorder(type_check="strict", iteration_index=iteration_index)
    with pytest.raises(RdeExecutionError) as raised, recorder:
        fn(*args, **kwargs)
    return raised.value, recorder


def _run_strict(tmp_path: Path, flow_fn: Any, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, RunReport]:
    root = tmp_path / "invoice"
    _generate.materialize_sut_case("invoice", root)
    monkeypatch.chdir(root)
    report = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
    ).run(flow_fn, execution={"type_check": "strict", "on_iteration_error": "fail_fast"})
    return root, report


def _sidecar_diagnostic(root: Path, report: RunReport) -> dict[str, Any]:
    document = json.loads((root / "data" / "logs" / f"diagnostics_{report.run_id}.json").read_text(encoding="utf-8"))
    [diagnostic] = document["diagnostics"]
    return diagnostic


def _events(root: Path, report: RunReport) -> list[dict[str, Any]]:
    path = root / "data" / "logs" / f"events_{report.run_id}.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    # The first line is the ``run.meta`` header, which is not an event.
    return [record for record in records if "name" in record]


def test_strict_positional_rejection_carries_detail__tc_ga688_ep_001() -> None:
    """TC-GA688-EP-001: the rejection names node, parameter, types and tile."""
    # Given / When: a strict call with a str for an int parameter in tile 3
    error, recorder = _rejected(takes_int, "seven", iteration_index=3)

    # Then: the catalogued 3002 is unchanged and carries a structured detail
    assert error.code == 3002
    assert error.message == "Node argument type mismatch for tests.v2.core.ga688.takes_int.count"
    assert error.detail == {
        "kind": NODE_ARGUMENT_REJECTION,
        "node_id": "tests.v2.core.ga688.takes_int",
        "parameter": "count",
        "expected_type": "int",
        "actual_type": "str",
        "iteration_index": 3,
    }
    assert node_argument_rejection(error) == error.detail

    # And: the body never ran, so nothing was recorded
    assert recorder.records == ()


def test_strict_keyword_rejection__tc_ga688_ep_002() -> None:
    """TC-GA688-EP-002: a keyword argument is attributed by name."""
    error, recorder = _rejected(takes_int, count=2.5)

    assert error.detail is not None
    assert error.detail["parameter"] == "count"
    assert error.detail["actual_type"] == "float"
    assert recorder.records == ()


def test_strict_var_positional_rejection__tc_ga688_ep_003() -> None:
    """TC-GA688-EP-003: ``*values: int`` reports the variadic parameter."""
    error, _ = _rejected(total, 1, "x")

    assert error.detail is not None
    assert error.detail["parameter"] == "values"
    assert error.detail["expected_type"] == "int"
    assert error.detail["actual_type"] == "str"


def test_strict_var_keyword_rejection__tc_ga688_ep_004() -> None:
    """TC-GA688-EP-004: ``**options: int`` reports the variadic keyword parameter."""
    error, _ = _rejected(options, a=1, b="x")

    assert error.detail is not None
    assert error.detail["parameter"] == "options"
    assert error.detail["actual_type"] == "str"


def test_runner_reports_the_rejection_without_a_call__tc_ga688_ep_005(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-GA688-EP-005: the sidecar and event log attribute the rejected node."""
    # Given / When: a strict run whose flow passes a str to an int parameter
    root, report = _run_strict(tmp_path, rejecting_flow, monkeypatch)

    # Then: the run failed with 3002 and no executed call was invented
    assert report.status == "failed"
    assert report.error is not None and report.error["code"] == 3002
    assert report.iterations[0]["node_calls"] == []

    # And: the diagnostic attributes node, parameter, types and tile
    diagnostic = _sidecar_diagnostic(root, report)
    assert diagnostic["phase"] == "node_argument_validation"
    assert diagnostic["node_id"] == "tests.v2.core.ga688.takes_int"
    assert diagnostic["parameter"] == "count"
    assert diagnostic["expected_type"] == "int"
    assert diagnostic["actual_type"] == "str"
    assert diagnostic["iteration_index"] == 0
    assert diagnostic["call_id"] is None
    assert diagnostic["location"]["function"] == "rejecting_flow"

    # And: one additive event says so, with no node.started for the node
    events = _events(root, report)
    rejected = [event for event in events if event["name"] == "node.argument_rejected"]
    assert len(rejected) == 1
    assert rejected[0]["node_id"] == "tests.v2.core.ga688.takes_int"
    assert rejected[0]["payload"] == {
        "iteration_index": 0,
        "parameter": "count",
        "expected_type": "int",
        "actual_type": "str",
    }
    assert not [event for event in events if event["name"] == "node.started"]


def test_nested_rejection_keeps_executed_sequence__tc_ga688_ev_010() -> None:
    """TC-GA688-EV-010: executed calls keep their seq; the rejected one adds none."""
    # Given / When: outer runs ok_inner (executed) then rejects takes_int
    error, recorder = _rejected(outer)

    # Then: the rejection is takes_int's, and only the executed calls are logged
    assert error.detail is not None
    assert error.detail["node_id"] == "tests.v2.core.ga688.takes_int"
    assert [(record.node_id, record.seq, record.status) for record in recorder.records] == [
        ("tests.v2.core.ga688.ok_inner", 1, "completed"),
        ("tests.v2.core.ga688.outer", 2, "failed"),
    ]
    assert [record.call_id for record in recorder.records] == [
        "tests.v2.core.ga688.ok_inner#1",
        "tests.v2.core.ga688.outer#2",
    ]


def test_no_value_repr_anywhere__tc_ga688_ev_011(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA688-EV-011: the rejected value never appears, only its type name."""
    error, _ = _rejected(takes_int, SECRET)
    assert SECRET not in json.dumps(error.detail)
    assert SECRET not in str(error)
    assert SECRET not in json.dumps(failure_diagnostic(error, phase="node_argument_validation").to_dict())

    root, report = _run_strict(tmp_path, secret_rejecting_flow, monkeypatch)
    assert SECRET not in (root / "data" / "logs" / f"diagnostics_{report.run_id}.json").read_text(encoding="utf-8")
    assert SECRET not in (root / "data" / "logs" / f"events_{report.run_id}.jsonl").read_text(encoding="utf-8")


def test_rejection_consumes_no_sequence_number__tc_ga688_ev_012() -> None:
    """TC-GA688-EV-012: a strict argument failure does not count as an executed call."""
    sequence = CallSequence()
    recorder = CallLogRecorder(type_check="strict", sequence=sequence)
    with recorder:
        ok_inner()
        with pytest.raises(RdeExecutionError):
            takes_int("x")  # type: ignore[arg-type]
        ok_inner()

    assert [record.seq for record in recorder.records] == [1, 2]
    assert sequence.next() == 3


def test_warn_mode_warns_and_runs__tc_ga688_ev_013() -> None:
    """TC-GA688-EV-013: warn stays a warning and execution continues."""
    _BODY_RAN.clear()
    with warnings.catch_warnings(record=True) as caught, CallLogRecorder(type_check="warn") as recorder:
        warnings.simplefilter("always")
        records_body("x")  # type: ignore[arg-type]

    assert any("Node argument type mismatch" in str(item.message) for item in caught)
    assert _BODY_RAN == ["ran"]
    assert [record.status for record in recorder.records] == ["completed"]


def test_off_mode_does_not_check__tc_ga688_ev_014() -> None:
    """TC-GA688-EV-014: off keeps today's behavior (no check at all)."""
    _BODY_RAN.clear()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with CallLogRecorder(type_check="off") as recorder:
            records_body("x")  # type: ignore[arg-type]

    assert _BODY_RAN == ["ran"]
    assert [record.status for record in recorder.records] == ["completed"]


def test_return_mismatch_stays_on_the_executed_call__tc_ga688_ev_015() -> None:
    """TC-GA688-EV-015: a return mismatch is a failed executed call, not a rejection."""
    error, recorder = _rejected(bad_return)

    assert error.code == 3002
    assert node_argument_rejection(error) is None
    assert [(record.node_id, record.status) for record in recorder.records] == [
        ("tests.v2.core.ga688.bad_return", "failed"),
    ]


def test_shallow_generic_checking_is_unchanged__tc_ga688_ev_016() -> None:
    """TC-GA688-EV-016: ``list[int]`` checks the origin only; elements are not promised."""
    with CallLogRecorder(type_check="strict") as recorder:
        assert takes_list(["a", "b"]) == 2  # type: ignore[list-item]

    assert [record.status for record in recorder.records] == ["completed"]
    error, _ = _rejected(takes_list, {"a": 1})
    assert error.detail is not None
    assert error.detail["expected_type"] == "list[int]"
    assert error.detail["actual_type"] == "dict"


def test_annotation_text_is_readable__tc_ga688_ev_017() -> None:
    """TC-GA688-EV-017: unions and classes render as type text, values as type names."""
    optional_error, _ = _rejected(takes_optional, 5)
    path_error, _ = _rejected(takes_path, "relative/name")

    assert optional_error.detail is not None
    assert optional_error.detail["expected_type"] == "str | None"
    assert optional_error.detail["actual_type"] == "int"
    assert path_error.detail is not None
    assert path_error.detail["expected_type"] == "pathlib.Path"
    assert path_error.detail["actual_type"] == "str"


def test_annotation_without_text_falls_back_to_its_type_name() -> None:
    """An annotation object whose ``str()`` raises is named by its class, never failing the check."""
    from rdetoolkit.core import calllog  # noqa: PLC0415

    class Opaque:
        def __str__(self) -> str:
            raise RuntimeError("no text")

    assert calllog._annotation_text(Opaque()) == "Opaque"  # noqa: SLF001
    assert len(calllog._annotation_text("x" * 500)) == 200  # noqa: SLF001


def test_runner_return_mismatch_is_node_execution__tc_ga688_ev_018(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-GA688-EV-018: a return mismatch keeps the executed call's id."""
    root, report = _run_strict(tmp_path, bad_return_flow, monkeypatch)

    diagnostic = _sidecar_diagnostic(root, report)
    assert diagnostic["phase"] == "node_execution"
    assert diagnostic["node_id"] == "tests.v2.core.ga688.bad_return"
    assert diagnostic["call_id"] == "tests.v2.core.ga688.bad_return#1"
    assert diagnostic["parameter"] is None
    assert [call["status"] for call in report.iterations[0]["node_calls"]] == ["failed"]
    assert not [event for event in _events(root, report) if event["name"] == "node.argument_rejected"]
