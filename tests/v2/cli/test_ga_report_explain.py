"""``rdetoolkit report explain``: why a run failed, from its report and sidecar (#687, GA-03).

``report show`` prints a status and failed call ids; the developer still had
to open the failure diagnostics file (#686), the iteration details and the
event log to learn the phase, the exception and the source line. ``report
explain`` joins them for one run, found next to the report by its run id.

EP table:
| TC | Case | Expected |
|----|------|----------|
| TC-GA687-EP-001 | one failed node | node_execution, node, call_id, ValueError at this file's raise line, reason, remediation |
| TC-GA687-EP-002 | pre-validation error, no node | pre_validate 4001, artifact invoice/invoice.json, no node / call |
| TC-GA687-EP-003 | post-validation after a successful node | post_validate 4002, meta/metadata.json, calls kept |
| TC-GA687-EP-004 | every tile fails | one explanation per tile, in tile order |
| TC-GA687-EP-005 | partial run | "partial" wording, only the failed tile explained |
| TC-GA687-EP-006 | run without recorded calls | call_id none, never "unknown" |
| TC-GA687-EP-007 | successful run | no cause, status passed, sidecar absence not flagged |
| TC-GA687-EP-008 | --iteration | only that tile |
| TC-GA687-EP-009 | --full-traceback | frames listed (text and JSON); absent by default |
| TC-GA687-EP-010 | relocated / alias-flat report | sidecar found next to the report, not under cwd |
| TC-GA687-EP-011 | caught node failure | explained from the report |

BV / negative table:
| TC | Case | Expected |
|----|------|----------|
| TC-GA687-EV-020 | sidecar missing (historic report) | fallback from the report + unavailable notice |
| TC-GA687-EV-021 | sidecar of another run | mismatched, not used |
| TC-GA687-EV-022 | corrupt / unsupported / bad phase sidecar | flagged, not used |
| TC-GA687-EV-023 | malformed report | exit 3; JSON: one envelope on stdout only |
| TC-GA687-EV-024 | unknown --format | exit 3 |
| TC-GA687-EV-025 | --iteration not in report | exit 3, IterationNotInReport |
| TC-GA687-EV-026 | unsafe ids / absolute paths / control chars | JSON redacts, text escapes |
| TC-GA687-EV-027 | JSON privacy | no exception message in the JSON |
| TC-GA687-EV-028 | read-only | report directory unchanged byte for byte |
| TC-GA687-EV-029 | truncated sidecar flag | evidence flag truncated |
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.report.explanation import IterationNotInReportError, explain_report
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths, IterationInfo, OutputContext
from tests.v2.contract.fixtures import _generate

MESSAGE = "ga687 raw failure text"
INVALID_METADATA = '{"constant": "not-a-mapping", "variable": 3}'
_THIS_FILE = Path(__file__).name


def _raise_line() -> int:
    lines = Path(__file__).read_text(encoding="utf-8").splitlines()
    return next(number for number, line in enumerate(lines, start=1) if line.strip().endswith("# GA687-RAISE"))


@node(id="tests.v2.cli.ga687.boom")
def boom(paths: InputPaths) -> None:
    _ = paths
    raise ValueError(MESSAGE)  # GA687-RAISE


@node(id="tests.v2.cli.ga687.ok")
def ok_node(paths: InputPaths) -> int:
    return len(paths.rawfiles)


@node(id="tests.v2.cli.ga687.write_invalid_metadata")
def write_invalid_metadata(out: OutputContext) -> None:
    out.meta.mkdir(parents=True, exist_ok=True)
    (out.meta / "metadata.json").write_text(INVALID_METADATA, encoding="utf-8")


@node(id="tests.v2.cli.ga687.fail_tile")
def fail_tile(iteration: IterationInfo, *, only: int | None) -> None:
    if only is None or iteration.index == only:
        msg = f"tile {iteration.index} fails"
        raise RuntimeError(msg)


@flow
def boom_flow(paths: InputPaths) -> None:
    boom(paths)


@flow
def ok_flow(paths: InputPaths) -> None:
    ok_node(paths)


@flow
def invalid_metadata_flow(paths: InputPaths, out: OutputContext) -> None:
    ok_node(paths)
    write_invalid_metadata(out)


@flow
def every_tile_fails_flow(iteration: IterationInfo) -> None:
    fail_tile(iteration, only=None)


@flow
def second_tile_fails_flow(iteration: IterationInfo) -> None:
    fail_tile(iteration, only=1)


@flow
def no_node_flow(paths: InputPaths) -> None:
    _ = paths
    msg = "flow body failed before any node"
    raise KeyError(msg)


@flow
def caught_failure_flow(paths: InputPaths) -> None:
    with contextlib.suppress(ValueError):
        boom(paths)


def _run(tmp_path: Path, flow_fn: Any, monkeypatch: pytest.MonkeyPatch, *, mode: str = "invoice", **overrides: Any) -> tuple[Path, RunReport]:
    root = tmp_path / mode
    _generate.materialize_sut_case(mode, root)
    monkeypatch.chdir(root)
    if mode == "multidatatile":
        overrides.setdefault("system", {"extended_mode": "MultiDataTile"})
    report = Runner(root=root, inputdata_path=root / "data" / "inputdata", unpacked_dir_path=root / "data" / "temp").run(flow_fn, **overrides)
    return root / "data" / "logs" / f"run_report_{report.run_id}.json", report


def _explain(path: Path, *args: str) -> Any:
    return CliRunner().invoke(app, ["report", "explain", str(path), *args])


def _json(path: Path, *args: str) -> dict[str, Any]:
    result = _explain(path, "--format", "json", *args)
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def _sidecar(path: Path, report: RunReport) -> Path:
    return path.parent / f"diagnostics_{report.run_id}.json"


# --------------------------------------------------------------------------- EP


def test_one_failed_node__tc_ga687_ep_001(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA687-EP-001: the failing node is named with phase, exception and source line."""
    # Given: a run whose only node raised
    path, report = _run(tmp_path, boom_flow, monkeypatch)

    # When: explaining it as JSON and as text
    document = _json(path)
    text = _explain(path)

    # Then: the structured fields pin the failure
    assert document["command"] == "report explain"
    assert document["schema_version"] == "1"
    assert document["format"] == "rdetoolkit.diagnostics"
    assert (document["run_id"], document["run_status"], document["mode"]) == (report.run_id, "failed", "invoice")
    assert document["diagnostics_available"] is True
    assert document["evidence"]["diagnostics"] == {"path": f"diagnostics_{report.run_id}.json", "state": "verified", "flags": []}
    [item] = document["explanations"]
    assert item["source"] == "diagnostics"
    assert item["phase"] == "node_execution"
    assert item["iteration_index"] == 0
    assert item["node_id"] == "tests.v2.cli.ga687.boom"
    assert item["call_id"] == "tests.v2.cli.ga687.boom#1"
    assert item["code"] == 3001
    assert item["name"] == "NodeExecutionFailed"
    assert item["remediation"]
    assert item["exception"]["type"] == "ValueError"
    assert item["location"]["file"].endswith(_THIS_FILE)
    assert item["location"]["line"] == _raise_line()
    assert item["location"]["function"] == "boom"
    assert item["redacted"] == []
    assert "frames" not in item["exception"]
    assert document["status"] == "failed"
    assert [finding["subject"] for finding in document["diagnostics"] if finding["severity"] == "error"] == ["tests.v2.cli.ga687.boom#1"]

    # And: the text says the same in words, with the recorded reason
    assert text.exit_code == 0, text.output
    out = text.stdout
    assert f"run_id: {report.run_id}" in out
    assert "status: failed (1 of 1 iterations failed)" in out
    assert "phase: node_execution" in out
    assert "node: tests.v2.cli.ga687.boom" in out
    assert "call_id: tests.v2.cli.ga687.boom#1" in out
    assert "error: 3001 NodeExecutionFailed" in out
    assert "exception: ValueError" in out
    assert f"{_THIS_FILE}:{_raise_line()} in boom" in out
    assert f"reason: ValueError: {MESSAGE}" in out
    assert "remediation: " in out
    assert f"diagnostics_{report.run_id}.json (verified)" in out
    assert "iteration 0 detail: " in out
    assert "traceback" not in out


def test_pre_validation_error_without_node__tc_ga687_ep_002(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA687-EP-002: a pre-validation failure names no node and no call."""
    root = tmp_path / "invoice"
    _generate.materialize_sut_case("invoice", root)
    _generate._invalidate_invoice(root)  # noqa: SLF001 -- the generator owns the defect
    monkeypatch.chdir(root)
    report = Runner(root=root, inputdata_path=root / "data" / "inputdata", unpacked_dir_path=root / "data" / "temp").run(ok_flow)
    path = root / "data" / "logs" / f"run_report_{report.run_id}.json"

    document = _json(path)
    [item] = document["explanations"]
    assert item["phase"] == "pre_validate"
    assert item["code"] == 4001
    assert (item["node_id"], item["call_id"], item["iteration_index"]) == (None, None, None)
    assert item["artifact_path"] == "invoice/invoice.json"
    assert document["summary"]["node_calls"] == 0

    out = _explain(path).stdout
    assert "phase: pre_validate" in out
    assert "iteration: none (the failure belongs to the run)" in out
    assert "node: not recorded" in out
    assert "call_id: none (no executed node call is recorded for this failure)" in out
    assert "artifact: invoice/invoice.json" in out


def test_post_validation_after_successful_nodes__tc_ga687_ep_003(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA687-EP-003: invalid metadata after the nodes ran is post_validate, calls kept."""
    path, _ = _run(tmp_path, invalid_metadata_flow, monkeypatch)

    document = _json(path)
    [item] = document["explanations"]
    assert item["phase"] == "post_validate"
    assert item["code"] == 4002
    assert item["iteration_index"] == 0
    assert item["artifact_path"] == "meta/metadata.json"
    assert item["call_id"] is None
    assert document["summary"] == {"iterations": 1, "failed_iterations": 0, "node_calls": 2, "failed_node_calls": 0}
    assert any("MetadataValidationError" in (cause["type"] or "") for cause in item["causes"])
    assert "phase: post_validate" in _explain(path).stdout


def test_every_tile_fails__tc_ga687_ep_004(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA687-EP-004: one explanation per failing tile, in tile order."""
    path, report = _run(tmp_path, every_tile_fails_flow, monkeypatch, mode="multidatatile", execution={"on_iteration_error": "continue"})

    document = _json(path)
    tiles = len(report.iterations)
    assert tiles >= 2
    assert report.status == "failed"
    assert [item["iteration_index"] for item in document["explanations"]] == list(range(tiles))
    assert {item["phase"] for item in document["explanations"]} == {"node_execution"}
    assert len({item["call_id"] for item in document["explanations"]}) == tiles
    # The tile's input name is for the terminal only, never in the JSON envelope.
    assert all("datatile_id" not in item for item in document["explanations"])
    out = _explain(path).stdout
    datatile = report.iterations[0]["datatile_id"]
    assert f"iteration: 0 (input: {datatile})" in out
    assert datatile not in json.dumps(document["explanations"])
    assert f"status: failed ({tiles} of {tiles} iterations failed)" in out
    assert f"failure {tiles} of {tiles}" in out


def test_partial_run__tc_ga687_ep_005(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA687-EP-005: a partial run says so and explains only the failed tile."""
    path, report = _run(tmp_path, second_tile_fails_flow, monkeypatch, mode="multidatatile", execution={"on_iteration_error": "continue"})

    document = _json(path)
    assert document["run_status"] == "partial"
    assert [item["iteration_index"] for item in document["explanations"]] == [1]
    out = _explain(path).stdout
    assert f"status: partial (1 of {len(report.iterations)} iterations failed; the others completed)" in out
    assert "reason: RuntimeError: tile 1 fails" in out


def test_run_without_recorded_calls__tc_ga687_ep_006(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA687-EP-006: no call was recorded, so no call id -- never ``unknown``."""
    path, report = _run(tmp_path, no_node_flow, monkeypatch)

    document = _json(path)
    [item] = document["explanations"]
    assert report.iterations[0]["error"]["call_id"] == "unknown"
    assert item["call_id"] is None
    assert item["node_id"] is None
    assert item["exception"]["type"] == "KeyError"
    assert document["summary"]["node_calls"] == 0
    out = _explain(path).stdout
    assert "call_id: none (no executed node call is recorded for this failure)" in out
    assert "unknown" not in out


def test_successful_run_has_no_cause__tc_ga687_ep_007(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA687-EP-007: success is not explained by an invented cause."""
    path, report = _run(tmp_path, ok_flow, monkeypatch)

    document = _json(path)
    assert report.status == "success"
    assert document["explanations"] == []
    assert document["evidence"]["diagnostics"] == {"path": f"diagnostics_{report.run_id}.json", "state": "missing", "flags": []}
    assert all(finding["severity"] != "error" for finding in document["diagnostics"])
    assert document["status"] in {"passed", "warning"}
    out = _explain(path).stdout
    assert "status: success (1 iterations)" in out
    assert "No failure is recorded for this run; there is nothing to explain." in out
    assert "unavailable" not in out


def test_iteration_filter__tc_ga687_ep_008(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA687-EP-008: ``--iteration`` keeps only that tile."""
    path, _ = _run(tmp_path, every_tile_fails_flow, monkeypatch, mode="multidatatile", execution={"on_iteration_error": "continue"})

    document = _json(path, "--iteration", "1")
    assert [item["iteration_index"] for item in document["explanations"]] == [1]
    out = _explain(path, "--iteration", "1").stdout
    assert "failure 1 of 1" in out
    assert "iteration 1 detail" in out
    assert "iteration 0 detail" not in out


def test_full_traceback__tc_ga687_ep_009(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA687-EP-009: ``--full-traceback`` lists the recorded frames, opt-in only."""
    path, _ = _run(tmp_path, boom_flow, monkeypatch)

    document = _json(path, "--full-traceback")
    frames = document["explanations"][0]["exception"]["frames"]
    assert frames[-1]["function"] == "boom"
    assert frames[-1]["line"] == _raise_line()
    assert all(set(frame) == {"file", "line", "function"} for frame in frames)
    assert document["explanations"][0]["exception"]["frames_truncated"] is False

    out = _explain(path, "--full-traceback").stdout
    assert "traceback (file, line and function of each recorded frame, outermost first):" in out
    assert "    ValueError (primary)" in out
    assert f"{_THIS_FILE}:{_raise_line()} in boom" in out


def test_relocated_report_finds_its_sidecar__tc_ga687_ep_010(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA687-EP-010: files are found next to the report, never under ``<cwd>/data``."""
    path, report = _run(tmp_path, boom_flow, monkeypatch)
    elsewhere = tmp_path / "copied" / "flat"
    elsewhere.mkdir(parents=True)
    for name in (path.name, f"diagnostics_{report.run_id}.json", f"events_{report.run_id}.jsonl"):
        shutil.copy2(path.parent / name, elsewhere / name)
    shutil.copytree(path.parent / "iterations", elsewhere / "iterations")
    # The original run's data root is gone, and cwd is an unrelated directory.
    shutil.rmtree(path.parent.parent)
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)

    document = _json(elsewhere / path.name)
    assert document["diagnostics_available"] is True
    assert document["explanations"][0]["phase"] == "node_execution"
    assert document["evidence"]["iterations"][0]["iteration_detail"]["state"] == "verified"
    assert str(elsewhere / f"diagnostics_{report.run_id}.json") in _explain(elsewhere / path.name).stdout


def test_caught_node_failure_is_explained_from_the_report__tc_ga687_ep_011(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA687-EP-011: a node failure the flow caught is what the report records."""
    path, report = _run(tmp_path, caught_failure_flow, monkeypatch)

    document = _json(path)
    assert report.status == "success"
    [item] = document["explanations"]
    assert item["source"] == "report"
    assert item["call_id"] == "tests.v2.cli.ga687.boom#1"
    assert item["phase"] is None
    assert item["code"] is None
    assert "reason: not recorded" in _explain(path).stdout


# --------------------------------------------------------------------- negative


def test_missing_sidecar_falls_back_to_the_report__tc_ga687_ev_020(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA687-EV-020: a historic report still gets an explanation, marked unavailable."""
    path, report = _run(tmp_path, boom_flow, monkeypatch)
    _sidecar(path, report).unlink()

    document = _json(path)
    assert document["diagnostics_available"] is False
    assert document["evidence"]["diagnostics"]["state"] == "missing"
    assert document["evidence"]["diagnostics"]["flags"] == ["missing"]
    assert any(finding["name"] == "SupportingEvidenceMissing" and finding["subject"] == f"diagnostics_{report.run_id}.json" for finding in document["diagnostics"])
    [item] = document["explanations"]
    assert item["source"] == "report"
    assert item["phase"] is None
    assert item["exception"] is None
    assert item["call_id"] == "tests.v2.cli.ga687.boom#1"
    assert item["code"] == 3001

    out = _explain(path).stdout
    assert "failure diagnostics: unavailable (missing). Phase, exception and source location are not known" in out
    assert "phase: not recorded" in out
    assert "error: 3001 NodeExecutionFailed" in out
    assert MESSAGE in out  # the report's own message is the fallback reason


def test_missing_sidecar_run_level_failure__tc_ga687_ev_020b(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA687-EV-020b: a run-level failure without a sidecar uses the report's error."""
    root = tmp_path / "invoice"
    _generate.materialize_sut_case("invoice", root)
    _generate._invalidate_invoice(root)  # noqa: SLF001 -- the generator owns the defect
    monkeypatch.chdir(root)
    report = Runner(root=root, inputdata_path=root / "data" / "inputdata", unpacked_dir_path=root / "data" / "temp").run(ok_flow)
    path = root / "data" / "logs" / f"run_report_{report.run_id}.json"
    _sidecar(path, report).unlink()

    [item] = _json(path)["explanations"]
    assert (item["source"], item["code"], item["iteration_index"]) == ("report", 4001, None)
    assert report.error is not None
    assert f"reason: {report.error['message'].splitlines()[0]}" in _explain(path).stdout


@node(id="tests.v2.cli.ga687.takes_int")
def takes_int(count: int) -> int:
    return count


@flow
def rejecting_flow(paths: InputPaths) -> None:
    _ = paths
    takes_int("not a number")  # type: ignore[arg-type]


def test_argument_rejection_names_the_parameter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A strict-mode rejection (#688) is explained by parameter and type names."""
    path, _ = _run(tmp_path, rejecting_flow, monkeypatch, execution={"type_check": "strict"})

    [item] = _json(path)["explanations"]
    assert item["phase"] == "node_argument_validation"
    assert (item["node_id"], item["parameter"], item["expected_type"], item["actual_type"]) == ("tests.v2.cli.ga687.takes_int", "count", "int", "str")
    assert item["call_id"] is None
    assert "parameter: count (expected int, got str)" in _explain(path).stdout


def test_truncated_frames_are_marked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A frame list cut by the sidecar's cap says so in the full traceback."""
    path, report = _run(tmp_path, boom_flow, monkeypatch)
    sidecar = _sidecar(path, report)
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["diagnostics"][0]["exception"]["frames_truncated"] = True
    sidecar.write_text(json.dumps(data), encoding="utf-8")

    assert _json(path, "--full-traceback")["explanations"][0]["exception"]["frames_truncated"] is True
    assert "... outer frames were not recorded" in _explain(path, "--full-traceback").stdout


def test_sidecar_of_another_run_is_not_used__tc_ga687_ev_021(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA687-EV-021: a sidecar whose run id differs is mismatched evidence."""
    path, report = _run(tmp_path, boom_flow, monkeypatch)
    sidecar = _sidecar(path, report)
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["run_id"] = "another-run"
    sidecar.write_text(json.dumps(data), encoding="utf-8")

    document = _json(path)
    assert document["evidence"]["diagnostics"]["state"] == "mismatched"
    assert document["diagnostics_available"] is False
    assert document["explanations"][0]["source"] == "report"


@pytest.mark.parametrize(
    ("mutate", "state"),
    [
        (lambda data: "{", "corrupt"),
        (lambda data: json.dumps({**data, "schema_version": "99"}), "unsupported"),
        (lambda data: json.dumps({**data, "format": "something.else"}), "unsupported"),
        (lambda data: json.dumps([data]), "corrupt"),
        (lambda data: json.dumps({**data, "diagnostics": [{**data["diagnostics"][0], "phase": "teleport"}]}), "corrupt"),
        (lambda data: json.dumps({**data, "diagnostics": [{**data["diagnostics"][0], "location": {"file": 3}}]}), "corrupt"),
        (lambda data: json.dumps({**data, "diagnostics": [{**data["diagnostics"][0], "causes": [{"relation": "x"}]}]}), "corrupt"),
        (lambda data: json.dumps({**data, "diagnostics": [{**data["diagnostics"][0], "iteration_index": -1}]}), "corrupt"),
        (lambda data: json.dumps({**data, "diagnostics": "none"}), "corrupt"),
        (lambda data: b"\xff\xfe".decode("latin-1"), "corrupt"),
    ],
)
def test_unusable_sidecar_is_flagged__tc_ga687_ev_022(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutate: Any, state: str) -> None:
    """TC-GA687-EV-022: a damaged sidecar is reported and never trusted."""
    path, report = _run(tmp_path, boom_flow, monkeypatch)
    sidecar = _sidecar(path, report)
    sidecar.write_text(mutate(json.loads(sidecar.read_text(encoding="utf-8"))), encoding="utf-8")

    document = _json(path)
    assert document["evidence"]["diagnostics"]["state"] == state
    assert document["evidence"]["diagnostics"]["flags"] == [state]
    assert document["explanations"][0]["source"] == "report"


def test_truncated_sidecar_is_flagged__tc_ga687_ev_029(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA687-EV-029: a sidecar that dropped diagnostics says so; it is still used."""
    path, report = _run(tmp_path, boom_flow, monkeypatch)
    sidecar = _sidecar(path, report)
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    sidecar.write_text(json.dumps({**data, "truncated": True}), encoding="utf-8")

    document = _json(path)
    assert document["evidence"]["diagnostics"] == {"path": sidecar.name, "state": "verified", "flags": ["truncated"]}
    assert document["explanations"][0]["source"] == "diagnostics"


def test_oversized_sidecar_is_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A sidecar over the evidence cap is not read."""
    from rdetoolkit.report import explanation  # noqa: PLC0415

    path, _ = _run(tmp_path, boom_flow, monkeypatch)
    monkeypatch.setattr(explanation, "_MAX_SIDECAR_BYTES", 10)

    document = _json(path)
    assert document["evidence"]["diagnostics"]["state"] == "truncated"
    assert document["explanations"][0]["source"] == "report"


@pytest.mark.parametrize("contents", ["{", "[]", json.dumps({"schema_version": "1"}), json.dumps({"schema_version": "2", "run_id": "../x", "status": "failed"})])
def test_malformed_report__tc_ga687_ev_023(tmp_path: Path, contents: str) -> None:
    """TC-GA687-EV-023: an unreadable report exits 3; JSON stays one clean document."""
    path = tmp_path / "run_report_x.json"
    path.write_text(contents, encoding="utf-8")

    text = _explain(path)
    assert text.exit_code == 3
    assert text.stdout == ""
    assert "Unable to read a supported run report." in text.stderr

    as_json = _explain(path, "--format", "json")
    assert as_json.exit_code == 3
    document = json.loads(as_json.stdout)
    assert document["command"] == "report explain"
    assert [finding["name"] for finding in document["diagnostics"]] == ["ReportInputInvalid"]
    assert contents not in as_json.stdout or contents in ("{", "[]")


def test_missing_report_file(tmp_path: Path) -> None:
    """A path that does not exist is an input error, not a crash."""
    result = _explain(tmp_path / "run_report_missing.json")
    assert result.exit_code == 3
    assert "Unable to read a supported run report." in result.stderr


def test_unknown_format__tc_ga687_ev_024(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA687-EV-024: only text and json are formats."""
    path, _ = _run(tmp_path, boom_flow, monkeypatch)
    result = _explain(path, "--format", "yaml")
    assert result.exit_code == 3
    assert "--format text or --format json" in result.stderr


def test_iteration_not_in_report__tc_ga687_ev_025(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA687-EV-025: an unknown tile index is an input error."""
    path, _ = _run(tmp_path, boom_flow, monkeypatch)

    result = _explain(path, "--format", "json", "--iteration", "7")
    assert result.exit_code == 3
    assert [finding["name"] for finding in json.loads(result.stdout)["diagnostics"]] == ["IterationNotInReport"]
    text = _explain(path, "--iteration", "7")
    assert text.exit_code == 3
    assert "Iteration 7 is not recorded in the run report." in text.stderr
    with pytest.raises(IterationNotInReportError):
        explain_report(path, iteration=7)
    assert _explain(path, "--iteration", "-1").exit_code == 2


def test_unsafe_context_is_redacted_and_escaped__tc_ga687_ev_026(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA687-EV-026: values rdetoolkit could not have written are redacted in JSON, escaped in text."""
    path, report = _run(tmp_path, boom_flow, monkeypatch)
    sidecar = _sidecar(path, report)
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    entry = data["diagnostics"][0]
    entry["node_id"] = "../../etc/passwd"
    entry["call_id"] = "x y"
    entry["artifact_path"] = "/etc/shadow"
    entry["parameter"] = "a b"
    entry["expected_type"] = "int; rm -rf"
    entry["actual_type"] = "str"
    entry["location"] = {"file": "/home/someone/secret/project.py", "line": 3, "function": "f"}
    entry["exception"]["type"] = "Bad Type\x1b[31m"
    entry["exception"]["message"] = "colour \x1b[31mred\x07 line one\nline two"
    entry["exception"]["frames"] = [{"file": "../outside.py", "line": None, "function": "g(x)"}]
    entry["causes"] = []
    sidecar.write_text(json.dumps(data), encoding="utf-8")

    document = _json(path, "--full-traceback")
    # The edited call id no longer matches the report's failed call, so that
    # call is explained from the report as well -- never silently merged.
    item, from_report = document["explanations"]
    assert (item["source"], from_report["source"]) == ("diagnostics", "report")
    assert from_report["call_id"] == "tests.v2.cli.ga687.boom#1"
    assert item["node_id"] is None
    assert item["call_id"] is None
    assert item["artifact_path"] is None
    assert item["parameter"] is None
    assert item["expected_type"] is None
    assert item["actual_type"] == "str"
    assert item["location"] == {"file": None, "line": 3, "function": "f"}
    assert item["redacted"] == ["artifact_path", "call_id", "expected_type", "location", "node_id", "parameter"]
    assert item["exception"]["type"] is None
    assert item["exception"]["frames"] == [{"file": None, "line": None, "function": None}]
    raw = json.dumps(document)
    for leaked in ("/etc/passwd", "/home/someone", "rm -rf", "\x1b", "colour"):
        assert leaked not in raw

    out = _explain(path, "--full-traceback").stdout
    assert "node: <redacted>" in out
    assert "call_id: <redacted>" in out
    assert "\x1b" not in out
    assert "\x07" not in out
    assert "\\x1b[31mred\\x07 line one\n    line two" in out
    assert "../outside.py:? in g(x)" in out


def test_json_carries_no_exception_message__tc_ga687_ev_027(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA687-EV-027: the JSON follows the envelope rule -- no runtime text."""
    path, _ = _run(tmp_path, boom_flow, monkeypatch)
    result = _explain(path, "--format", "json", "--full-traceback")
    assert MESSAGE not in result.stdout
    assert result.stderr == ""


def test_explain_reads_only__tc_ga687_ev_028(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA687-EV-028: explaining writes nothing next to the report."""
    path, _ = _run(tmp_path, boom_flow, monkeypatch)

    def _digest() -> dict[str, str]:
        return {str(item.relative_to(path.parent)): hashlib.sha256(item.read_bytes()).hexdigest() for item in sorted(path.parent.rglob("*")) if item.is_file()}

    before = _digest()
    _explain(path)
    _explain(path, "--format", "json", "--full-traceback")
    assert _digest() == before


@pytest.mark.parametrize("flow_fn", [boom_flow, ok_flow])
def test_json_follows_the_published_envelope_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flow_fn: Any) -> None:
    """The explain document validates against docs/usage/diagnostics.schema.json, errors included."""
    import jsonschema  # noqa: PLC0415

    schema = json.loads((Path(__file__).resolve().parents[3] / "docs" / "usage" / "diagnostics.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    path, _ = _run(tmp_path, flow_fn, monkeypatch)
    validator.validate(_json(path, "--full-traceback"))
    broken = tmp_path / "run_report_broken.json"
    broken.write_text("{", encoding="utf-8")
    validator.validate(json.loads(_explain(broken, "--format", "json").stdout))


def test_existing_show_output_is_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``report show`` keeps its four-line shape (#687 AC: existing outputs unchanged)."""
    path, report = _run(tmp_path, boom_flow, monkeypatch)
    result = CliRunner().invoke(app, ["report", "show", str(path)])
    assert result.exit_code == 0
    lines = result.stdout.splitlines()
    assert lines[:4] == [f"run_id: {report.run_id}", "status: failed", "iterations: 1", "failed call_id: tests.v2.cli.ga687.boom#1"]
    assert lines[4].startswith("error: ")
    assert len(lines) == 5
