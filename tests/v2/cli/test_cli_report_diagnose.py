"""Regression contract for report diagnosis (#669).

EP table:
| Partition | Expected | Test |
| --- | --- | --- |
| failed/partial primary reports | observed IDs, safe catalog guidance | test_failed_tiles |
| terminal failure without node | no invented call | test_terminal_failure |
| reused iteration directory | mismatch warning, no other-run records | test_consecutive_runs |
| absent/corrupt/legacy details | explicit evidence flags | test_detail_degradation |
| missing/corrupt/mismatched/truncated events | explicit evidence flags | test_events_degradation |
| invalid report/version | JSON error and exit 3 | test_invalid_report |
| analyzed failed report | exit 0; opt-in exit 1 | test_cli_exit_contract |
| malicious paths/data | no external artifact access or raw secrets | test_safe_paths |
BV table:
| Boundary | Expected | Test |
| --- | --- | --- |
| zero tiles | success diagnosis, no fabricated failures | test_zero_tiles |
| two failed tiles | both reported separately | test_failed_tiles |
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from rdetoolkit.core.calllog import NodeCallRecord, TypeSummary
from rdetoolkit.report.diagnosis import diagnose_report
from rdetoolkit.runner.aggregator import RunAggregator
from rdetoolkit.runner.execute import ExecutionResult

SECRET = "secret-password-do-not-emit"


def _record(index=0, node_id="node_a"):
    return NodeCallRecord(call_id=f"{node_id}#{index + 1}", node_id=node_id, parent_flow="flow", seq=index + 1,
                          iteration_index=index, started_at="2026-01-01T00:00:00Z", duration_ms=1, status="failed",
                          inputs={"token": TypeSummary("str", SECRET)}, outputs=(), error={"message": SECRET, "type": "RuntimeError"})


def _report(tmp_path, *, run_id="run_a", status="failed", count=1, node_id="node_a"):
    aggregator = RunAggregator(run_id=run_id, flow_id="flow", mode="invoice", config_digest="digest", logs_dir=tmp_path)
    for index in range(count):
        aggregator.record(ExecutionResult(iteration_index=index, status="failed", call_records=(_record(index, node_id),), outputs=(),
                                         error={"code": 3001, "name": "NodeExecutionFailed", "message": SECRET, "call_id": f"{node_id}#{index + 1}"}, stacktrace=SECRET))
    report = aggregator.build_report(status=status, started_at="2026-01-01T00:00:00Z", duration_ms=1)
    path = tmp_path / f"run_report_{run_id}.json"
    path.write_text(report.to_json(), encoding="utf-8")
    return path


@pytest.mark.parametrize("status", ["failed", "partial"])
def test_failed_tiles(tmp_path, status):
    # Given: two failed tiles recorded by the primary aggregator.
    path = _report(tmp_path, count=2, status=status)
    # When: diagnosing the report and its run-bound detail.
    result = diagnose_report(path)
    # Then: both calls are observed, catalogued, and no raw data escapes.
    assert result["schema_version"] == "1"
    assert result["run_status"] == status
    assert [item["iteration_index"] for item in result["failures"]] == [0, 1]
    assert [item["call_id"] for item in result["failures"]] == ["node_a#1", "node_a#2"]
    assert all(item["node_id"] == "node_a" and item["code"] == 3001 and item["remediation"] for item in result["failures"])
    assert all(item["iteration_detail"]["state"] == "verified" for item in result["evidence"]["iterations"])
    assert SECRET not in json.dumps(result)
    assert result == diagnose_report(path)


def test_zero_tiles(tmp_path):
    # Given: an empty successful run.
    path = _report(tmp_path, status="success", count=0)
    # When: diagnosing it.
    result = diagnose_report(path)
    # Then: no failures are invented.
    assert result["failures"] == []
    assert result["run_status"] == "success"


def test_terminal_failure(tmp_path):
    # Given: a non-node invoice validation failure.
    path = _report(tmp_path, count=0)
    data = json.loads(path.read_text())
    data["error"] = {"code": 4001, "name": "InvoiceSchemaInvalid", "message": SECRET}
    path.write_text(json.dumps(data))
    # When: diagnosing it.
    result = diagnose_report(path)
    # Then: no node or call is fabricated.
    assert len(result["failures"]) == 1
    assert result["failures"][0]["code"] == 4001
    assert result["failures"][0]["call_id"] is None
    assert result["failures"][0]["node_id"] is None
    assert SECRET not in json.dumps(result)


def test_consecutive_runs(tmp_path):
    # Given: two different primary runs reusing iteration_0.json.
    original = _report(tmp_path)
    _report(tmp_path, run_id="run_b", node_id="node_b")
    # When: inspecting the original report after the later run.
    result = diagnose_report(original)
    # Then: the reused detail is rejected and never falsely correlated.
    assert result["evidence"]["iterations"][0]["iteration_detail"]["state"] == "mismatched"
    assert result["failures"][0]["node_id"] == "node_a"
    assert "node_b" not in json.dumps(result)
    assert any(item["name"] == "SupportingEvidenceMismatched" for item in result["diagnostics"])


@pytest.mark.parametrize("variant, state", [("missing", "missing"), ("corrupt", "corrupt"), ("legacy", "unverified"), ("version", "unsupported"), ("wrong_index", "mismatched"), ("records", "corrupt")])
def test_detail_degradation(tmp_path, variant, state):
    # Given: absent, damaged, or unbound detail evidence.
    path = _report(tmp_path)
    detail = tmp_path / "iterations/iteration_0.json"
    payload = json.loads(detail.read_text())
    if variant == "missing":
        detail.unlink()
    elif variant == "corrupt":
        detail.write_text("{")
    else:
        if variant == "legacy":
            payload.pop("run_id", None)
            payload.pop("schema_version", None)
        if variant == "version":
            payload["schema_version"] = "99"
        if variant == "wrong_index":
            payload["iteration_index"] = 1
        if variant == "records":
            payload["call_records"] = ["invalid"]
        detail.write_text(json.dumps(payload))
    # When: diagnosing a still-valid report.
    result = diagnose_report(path)
    # Then: primary failures survive with an explicit supporting-evidence flag.
    assert result["evidence"]["iterations"][0]["iteration_detail"]["state"] == state
    assert result["failures"][0]["call_id"] == "node_a#1"


@pytest.mark.parametrize("variant, flag", [("missing", "missing"), ("corrupt", "corrupt"), ("mismatch", "mismatched"), ("version", "unsupported"), ("truncated", "truncated"), ("incomplete", "incomplete")])
def test_events_degradation(tmp_path, variant, flag):
    # Given: one event log with unavailable or damaged evidence.
    path = _report(tmp_path)
    events = tmp_path / "events_run_a.jsonl"
    records = [{"schema_version": "1", "type": "run.meta", "run_id": "run_a"},
               {"schema_version": "1", "run_id": "run_a", "name": "run.completed", "payload": {}}]
    if variant == "corrupt":
        events.write_text("{\n")
    elif variant != "missing":
        if variant == "mismatch":
            records[0]["run_id"] = "run_b"
        if variant == "version":
            records[0]["schema_version"] = "99"
        if variant == "truncated":
            records.insert(1, {"schema_version": "1", "run_id": "run_a", "name": "warning", "payload": {"code": 1002, "message": SECRET}})
        if variant == "incomplete":
            records.pop()
        events.write_text("\n".join(json.dumps(item) for item in records) + "\n")
    # When: reading diagnosis.
    result = diagnose_report(path)
    # Then: the condition is explicit and raw event messages are excluded.
    assert flag in result["evidence"]["events"]["flags"]
    assert SECRET not in json.dumps(result)


@pytest.mark.parametrize("variant", ["missing", "json", "list", "version", "status", "iterations", "index", "calls", "call", "error", "run_id"])
def test_invalid_report(tmp_path, variant):
    # Given: an invalid report or incompatible schema.
    path = _report(tmp_path)
    data = json.loads(path.read_text())
    if variant == "missing":
        path.unlink()
    elif variant == "json":
        path.write_text("{TOPSECRET")
    elif variant == "list":
        path.write_text("[]")
    else:
        changes = {"version": {"schema_version": "99"}, "status": {"status": "unknown"}, "iterations": {"iterations": {}},
                   "index": {"iterations": [{"index": -1, "status": "failed", "node_calls": []}]},
                   "calls": {"iterations": [{"index": 0, "status": "failed", "node_calls": {}}]},
                   "call": {"iterations": [{"index": 0, "status": "failed", "node_calls": ["bad"]}]},
                   "error": {"error": "bad"}, "run_id": {"run_id": "../outside"}}
        data.update(changes[variant])
        path.write_text(json.dumps(data))
    # When: invoking the machine CLI.
    result = CliRunner().invoke(app, ["report", "diagnose", str(path), "--json"])
    # Then: an unusable report is the v2 invalid-input status, unlike diagnosing a failed run.
    assert result.exit_code == 3
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"
    assert payload["diagnostics"][0]["name"] == "ReportInputInvalid"
    assert "TOPSECRET" not in result.stdout


def test_cli_exit_contract(tmp_path):
    # Given: a valid report of a failed run.
    path = _report(tmp_path)
    runner = CliRunner()
    # When: diagnosing it normally and with explicit failure propagation.
    ordinary = runner.invoke(app, ["report", "diagnose", str(path), "--json"])
    strict = runner.invoke(app, ["report", "diagnose", str(path), "--json", "--fail-on-error"])
    text = runner.invoke(app, ["report", "diagnose", str(path)])
    # Then: analysis success is independent from the run outcome.
    assert ordinary.exit_code == 0
    assert strict.exit_code == 1
    assert text.exit_code == 0
    assert json.loads(ordinary.stdout)["run_status"] == "failed"
    assert "node_a#1" in text.stdout
    assert SECRET not in text.stdout


def test_safe_paths(tmp_path):
    # Given: a report with path-like node IDs and a forged detail-only call.
    path = _report(tmp_path)
    detail = tmp_path / "iterations/iteration_0.json"
    payload = json.loads(detail.read_text())
    payload["call_records"].append({"call_id": "other#9", "node_id": SECRET, "status": "failed", "iteration_index": 0})
    detail.write_text(json.dumps(payload))
    # When: supporting detail disagrees with primary observed calls.
    result = diagnose_report(path)
    # Then: no additional primary failures are invented.
    assert len(result["failures"]) == 1
    assert SECRET not in json.dumps(result)


@pytest.mark.parametrize("error", [None, {}, {"code": True}, {"code": "3001", "message": SECRET}, {"code": 998877, "message": SECRET}, {"code": 3001, "name": "StructuredError", "message": SECRET}])
def test_safe_unknown_errors(error):
    # Given: untrusted error strings and off-catalog/passthrough codes.
    from rdetoolkit.report.diagnostics import safe_error
    # When: creating a safe diagnostic error.
    result = safe_error(error)
    # Then: only integer codes survive, with fixed safe guidance.
    assert result["name"] == "ExecutionError"
    assert result["remediation"]
    assert SECRET not in json.dumps(result)
    assert result["code"] is None or type(result["code"]) is int


def test_real_consecutive_runner_failures(tmp_path, monkeypatch):
    # Given: two actual flows fail in distinct nodes against the same data root.
    from rdetoolkit.core.flow import flow
    from rdetoolkit.core.node import node
    from rdetoolkit.runner.lifecycle import Runner
    from tests.v2.cli.test_cli_report import _build_data_fixture
    _build_data_fixture(tmp_path)
    monkeypatch.chdir(tmp_path)

    @node(id="diagnosis_actual_first_failure")
    def first() -> None:
        raise RuntimeError(SECRET)

    @node(id="diagnosis_actual_second_failure")
    def second() -> None:
        raise RuntimeError("different failure")

    @flow(id="diagnosis_actual_first_flow")
    def first_flow() -> None:
        first()

    @flow(id="diagnosis_actual_second_flow")
    def second_flow() -> None:
        second()

    # When: a later run replaces the iteration details of the original run.
    before = Runner(root=tmp_path, run_id_factory=lambda: "actual_first").run(first_flow)
    after = Runner(root=tmp_path, run_id_factory=lambda: "actual_second").run(second_flow)
    path = tmp_path / "data/logs/run_report_actual_first.json"
    result = diagnose_report(path)
    # Then: provenance rejects the new detail but retains only observed first-run IDs.
    assert before.status == after.status == "failed"
    assert result["failures"][0]["node_id"] == "diagnosis_actual_first_failure"
    assert result["evidence"]["iterations"][0]["iteration_detail"]["state"] == "mismatched"
    assert result["evidence"]["events"]["flags"] == []
    assert "diagnosis_actual_second_failure" not in json.dumps(result)
    assert SECRET not in json.dumps(result)


@pytest.mark.parametrize("field", ["truncated", "call_records_truncated", "removed"])
def test_truncated_call_records(tmp_path, field):
    # Given: run-bound detail explicitly or observably lacks some primary calls.
    path = _report(tmp_path)
    detail = tmp_path / "iterations/iteration_0.json"
    payload = json.loads(detail.read_text())
    if field == "removed":
        payload["call_records"] = []
    else:
        payload[field] = True
    detail.write_text(json.dumps(payload))
    # When: diagnosing it.
    result = diagnose_report(path)
    # Then: missing node evidence is explicit and no primary call disappears.
    assert "truncated" in result["evidence"]["iterations"][0]["iteration_detail"]["flags"]
    assert result["failures"][0]["node_id"] == "node_a"


@pytest.mark.parametrize("variant", ["large_detail", "large_events", "array_detail", "array_event", "bad_payload", "unreadable_events", "non_node_iteration"])
def test_evidence_boundaries(tmp_path, monkeypatch, variant):
    # Given: unsupported evidence shapes or a failed tile before any node executes.
    from rdetoolkit.report import diagnosis
    path = _report(tmp_path)
    detail = tmp_path / "iterations/iteration_0.json"
    events = tmp_path / "events_run_a.jsonl"
    if variant in {"large_detail", "large_events"}:
        monkeypatch.setattr(diagnosis, "_MAX_EVIDENCE_BYTES", 1)
        if variant == "large_events":
            events.write_text("{}")
    if variant == "array_detail":
        detail.write_text("[]")
    if variant == "array_event":
        events.write_text("[]\n")
    if variant == "bad_payload":
        events.write_text(json.dumps({"schema_version": "1", "run_id": "run_a", "name": "node.failed", "payload": []}) + "\n")
    if variant == "unreadable_events":
        events.mkdir()
    if variant == "non_node_iteration":
        data = json.loads(path.read_text())
        data["iterations"][0]["node_calls"] = []
        path.write_text(json.dumps(data))
    # When: collecting evidence flags.
    result = diagnose_report(path)
    # Then: it degrades gracefully, preserving primary execution facts.
    if variant == "large_detail":
        assert result["evidence"]["iterations"][0]["iteration_detail"]["state"] == "truncated"
    elif variant == "large_events":
        assert result["evidence"]["events"]["flags"] == ["truncated"]
    elif variant == "array_detail":
        assert result["evidence"]["iterations"][0]["iteration_detail"]["state"] == "corrupt"
    elif variant == "non_node_iteration":
        assert result["failures"][0]["node_id"] is None
    else:
        assert "corrupt" in result["evidence"]["events"]["flags"]


def test_unrelated_terminal_error_does_not_relabel_caught_node(tmp_path):
    # Given: one caught failed node and a separate later invoice error.
    path = _report(tmp_path)
    data = json.loads(path.read_text())
    data["iterations"][0]["error"] = {"code": 4001, "name": "InvoiceSchemaInvalid", "message": SECRET}
    path.write_text(json.dumps(data))
    # When: interpreting primary observed failures.
    result = diagnose_report(path)
    # Then: the caught node receives no unrelated catalog diagnosis.
    assert result["failures"][0]["node_id"] == "node_a"
    assert result["failures"][0]["code"] is None
    assert result["failures"][1]["node_id"] is None
    assert result["failures"][1]["code"] == 4001


def test_passthrough_code_collision_remains_uncatalogued(tmp_path):
    # Given: a legacy error number that overlaps with the v2 catalog.
    path = _report(tmp_path)
    data = json.loads(path.read_text())
    data["iterations"][0]["error"]["name"] = "StructuredError"
    path.write_text(json.dumps(data))
    # When: formatting diagnostics.
    result = diagnose_report(path)
    # Then: the code survives without a false catalog name/remediation.
    assert result["failures"][0]["code"] == 3001
    assert result["failures"][0]["name"] == "ExecutionError"
    assert next(item for item in result["diagnostics"] if item["severity"] == "error")["name"] == "ExecutionError"


@pytest.mark.parametrize("target", ["primary", "detail", "events"])
def test_deep_json_degrades_safely(tmp_path, target):
    # Given: syntactically nested JSON deeper than the parser's recursion limit.
    path = _report(tmp_path)
    destination = {"primary": path, "detail": tmp_path / "iterations/iteration_0.json", "events": tmp_path / "events_run_a.jsonl"}[target]
    destination.write_text("[" * 10000 + "0" + "]" * 10000)
    # When: using the public JSON CLI.
    result = CliRunner().invoke(app, ["report", "diagnose", str(path), "--json"])
    # Then: deep input cannot cause an unstructured traceback or lost report.
    payload = json.loads(result.stdout)
    assert result.exit_code == (3 if target == "primary" else 0)
    if target == "detail":
        assert payload["evidence"]["iterations"][0]["iteration_detail"]["state"] == "corrupt"
    if target == "events":
        assert "corrupt" in payload["evidence"]["events"]["flags"]


def test_failed_run_without_error_remains_failed_diagnosis(tmp_path):
    # Given: a failed report without a terminal error or any executed tile.
    path = _report(tmp_path, count=0)
    # When: diagnosing only observed run state.
    result = diagnose_report(path)
    # Then: the failed result stays explicit without inventing node details.
    assert result["status"] == "failed"
    assert result["failures"][0]["code"] is None
    assert result["failures"][0]["call_id"] is None


@pytest.mark.property
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(later_id=st.text(alphabet="abc012_-", min_size=1, max_size=20))
def test_generated_stale_run_never_correlates(tmp_path, later_id):
    # Given: arbitrary different run IDs reusing the same iteration directory.
    path = _report(tmp_path, run_id="original")
    _report(tmp_path, run_id=later_id, node_id="other_run_node")
    # When: diagnosing the earlier run.
    result = diagnose_report(path)
    # Then: run provenance is invariant under the later ID's spelling.
    assert result["evidence"]["iterations"][0]["iteration_detail"]["state"] == "mismatched"
    assert "other_run_node" not in json.dumps(result)


def test_published_report_schema(tmp_path):
    # Given: the published schema and local common-envelope dependency.
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    docs = Path(__file__).resolve().parents[3] / "docs/usage"
    schema = json.loads((docs / "diagnostics-report.schema.json").read_text())
    common = json.loads((docs / "diagnostics.schema.json").read_text())
    registry = Registry().with_resource("diagnostics.schema.json", Resource.from_contents(common))
    # When: diagnosing a failed run with verified primary IDs.
    result = diagnose_report(_report(tmp_path))
    # Then: the response validates without fetching any schema over the network.
    Draft202012Validator(schema, registry=registry).validate(result)
