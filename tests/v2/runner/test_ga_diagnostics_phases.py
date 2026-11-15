"""Phase-aware failure diagnostics in a versioned sidecar (#686, GA-02).

A failed run's report says *that* it failed and with which code; for
configuration, pre/post validation and some tile-preparation failures it had
no source location and no traceback, and the v2 entry deliberately prints no
traceback. Every Runner failure now produces a ``FailureDiagnostic`` in
``<data_root>/logs/diagnostics_<run_id>.json``: phase, code, exception chain,
the originating source location and the tile / node / artifact it belongs
to. The RunReport v2 shape, ``job.failed`` and the published codes are
unchanged; the sidecar never decides the outcome.

EP table (one row per lifecycle phase):
| TC | Phase | Induced failure | Expected |
|----|-------|-----------------|----------|
| TC-GA686-EP-001 | config_load | invalid ``execution.on_iteration_error`` | 1002, location outside the translator |
| TC-GA686-EP-002 | config_load | PermissionError reading config | 1002, PermissionError in the chain, location in its raiser |
| TC-GA686-EP-003 | mode_resolution | ``prepare=`` raises | 3001, location = the prepare function |
| TC-GA686-EP-004 | pre_validate | invoice.json missing | 4003, artifact ``invoice/invoice.json`` |
| TC-GA686-EP-005 | pre_validate | invoice violates schema | 4001, artifact ``invoice/invoice.json`` |
| TC-GA686-EP-006 | tile_prepare | planner raises | 3001, location in the raiser |
| TC-GA686-EP-007 | tile_prepare | flow parameter cannot be injected | E2003, iteration 0, no node |
| TC-GA686-EP-008 | node_execution | node raises | 3001, node_id, call_id, location = the raise line |
| TC-GA686-EP-009 | artifact_publish | raw copy raises PermissionError | 3005, PermissionError, location outside the stage guard |
| TC-GA686-EP-010 | post_validate | node writes invalid metadata | 4002, iteration 0, ``meta/metadata.json``, iterations kept |
| TC-GA686-EP-011 | finalize | finalizer raises OSError | 5001 raised, sidecar names ``finalize`` |
| TC-GA686-EP-012 | artifact_publish | the tile record write raises after the executor returned | phase ``artifact_publish`` (completed and failed tile) |
| TC-GA686-EP-013 | after the tile loop | report assembly raises before post-validation | phase ``post_validate``, never ``tile_prepare`` |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-GA686-EV-020 | explicit cause | ``raise A from B`` in a node | causes[0] relation ``cause``, type B |
| TC-GA686-EV-021 | implicit context | raise inside ``except`` | causes[0] relation ``context`` |
| TC-GA686-EV-022 | StructuredError | ecode 42 | report/job.failed 42 unchanged, category ``structured_error`` |
| TC-GA686-EV-023 | ProcessingError | user error | 3007 unchanged |
| TC-GA686-EV-024 | interruption | node raises the 3004 interruption | 3004 kept, phase ``node_execution`` |
| TC-GA686-EV-025 | sidecar write fails | writer raises OSError | failed report + job.failed unchanged, stderr says unavailable, no file |
| TC-GA686-EV-026 | success | clean run | no sidecar |
| TC-GA686-EV-027 | privacy | secret in locals, argument and env | absent from the sidecar; frames are file/line/function only |
| TC-GA686-EV-028 | document | any failure | schema_version "1", format, run_id, run_status; RunReport stays "2" |
| TC-GA686-EV-029 | partial | one tile of two fails under continue | sidecar with the tile diagnostic, run_status partial |
| TC-GA686-EV-030 | v1 callback | callback raises | node_execution, location = the callback |
| TC-GA686-EV-031 | no exception | ``failure_diagnostic(None)`` | exception/location ``None``, never invented |
| TC-GA686-EV-032 | bounds | deep recursion, long message, long chain, cycle | frames/message/chain capped and flagged; cycle terminates |
| TC-GA686-EV-033 | cap | many failed tiles | run-level diagnostic always kept, ``truncated`` set |
| TC-GA686-EV-034 | finalize + sidecar fail | both raise | the finalize error (5001) reaches the caller |
| TC-GA686-EV-035 | privacy | frame in a file outside the project and sys.path | ``<external>/<name>`` with line/function, no absolute path |
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.errors import ERROR_CATALOG, ProcessingError, RdeError, RdeExecutionError, RdeInternalError
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.report import failure as failure_module
from rdetoolkit.report.failure import (
    FAILURE_DIAGNOSTICS_FORMAT,
    FAILURE_DIAGNOSTICS_SCHEMA_VERSION,
    FAILURE_PHASES,
    MAX_CHAIN,
    MAX_DIAGNOSTICS,
    MAX_FRAMES,
    MAX_MESSAGE_LENGTH,
    FailureDiagnostic,
    diagnostics_document,
    failure_diagnostic,
)
from rdetoolkit.report.run_report import RUN_REPORT_SCHEMA_VERSION, RunReport
from rdetoolkit.runner.aggregator import RunAggregator
from rdetoolkit.runner.execute import ExecutionResult
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths, IterationInfo, OutputContext
from tests.v2.contract.fixtures import _generate

THIS_FILE = Path(__file__).name
SECRET = "TOPSECRET-686-value"
INVALID_METADATA = '{"constant": "not-a-mapping", "variable": 3}'


# --- nodes and flows -------------------------------------------------------


@node
def raising_node(paths: InputPaths) -> None:
    _ = paths
    raise ValueError("node body failed")  # the diagnosed source line


@node
def chained_node(paths: InputPaths) -> None:
    _ = paths
    try:
        {}["missing"]
    except KeyError as exc:
        raise RuntimeError("wrapped") from exc


@node
def context_node(paths: InputPaths) -> None:
    _ = paths
    try:
        {}["missing"]
    except KeyError:
        raise RuntimeError("raised while handling")  # noqa: B904 -- the implicit context is the point


@node
def structured_node(paths: InputPaths) -> None:
    _ = paths
    raise StructuredError("v1 says no", ecode=42)


@node
def processing_node(paths: InputPaths) -> None:
    _ = paths
    raise ProcessingError("cannot read the sample", remediation="Re-export the file.")


@node
def interrupting_node(paths: InputPaths) -> None:
    _ = paths
    definition = ERROR_CATALOG[3004]
    error_cls: Any = RdeExecutionError
    raise error_cls(code=3004, name=definition.name, message=definition.message_template)


@node
def secret_node(token: str) -> None:
    local_secret = f"{SECRET}-local"
    _ = local_secret
    raise ValueError("failure without the value")


@node
def write_invalid_metadata(out: OutputContext) -> None:
    out.meta.mkdir(parents=True, exist_ok=True)
    (out.meta / "metadata.json").write_text(INVALID_METADATA, encoding="utf-8")


@node
def fail_tile_one(iteration: IterationInfo) -> None:
    if iteration.index == 1:
        raise RuntimeError("tile 1 fails")


@node
def quiet_node(paths: InputPaths) -> int:
    return len(paths.rawfiles)


@flow
def raising_flow(paths: InputPaths) -> None:
    raising_node(paths)


@flow
def chained_flow(paths: InputPaths) -> None:
    chained_node(paths)


@flow
def context_flow(paths: InputPaths) -> None:
    context_node(paths)


@flow
def structured_flow(paths: InputPaths) -> None:
    structured_node(paths)


@flow
def processing_flow(paths: InputPaths) -> None:
    processing_node(paths)


@flow
def interrupting_flow(paths: InputPaths) -> None:
    interrupting_node(paths)


@flow
def secret_flow(paths: InputPaths) -> None:
    _ = paths
    secret_node(f"{SECRET}-argument")


@flow
def invalid_metadata_flow(out: OutputContext) -> None:
    write_invalid_metadata(out)


@flow
def second_tile_fails_flow(iteration: IterationInfo) -> None:
    fail_tile_one(iteration)


@flow
def quiet_flow(paths: InputPaths) -> None:
    quiet_node(paths)


#: Helpers loaded at test time from files outside the project and sys.path.
_EXTERNAL: dict[str, Any] = {}


@node
def external_node(paths: InputPaths) -> None:
    """Call the helper loaded from outside the project."""
    _ = paths
    _EXTERNAL["explode"]()


@flow
def external_flow(paths: InputPaths) -> None:
    """Run the node whose failure starts in an external file."""
    external_node(paths)


@flow
def uninjectable_flow(threshold: int) -> None:
    _ = threshold


def _failing_prepare(inputdata: Path, config: Any) -> None:
    _ = (inputdata, config)
    raise ValueError("prepare failed")


@flow(prepare=_failing_prepare)
def prepared_flow(paths: InputPaths) -> None:
    _ = paths


def _raising_callback(srcpaths: Any, resource_paths: Any) -> None:
    _ = (srcpaths, resource_paths)
    raise RuntimeError("callback failed")


# --- helpers ---------------------------------------------------------------


def _materialize(tmp_path: Path, mode: str = "invoice") -> Path:
    root = tmp_path / mode
    _generate.materialize_sut_case(mode, root)
    return root


def _runner(root: Path, **kwargs: Any) -> Runner:
    return Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
        **kwargs,
    )


def _run(root: Path, flow_fn: Any, monkeypatch: pytest.MonkeyPatch, **overrides: Any) -> RunReport:
    monkeypatch.chdir(root)
    return _runner(root).run(flow_fn, **overrides)


def _sidecar_path(root: Path, run_id: str) -> Path:
    return root / "data" / "logs" / f"diagnostics_{run_id}.json"


def _sidecar(root: Path, report: RunReport) -> dict[str, Any]:
    return json.loads(_sidecar_path(root, report.run_id).read_text(encoding="utf-8"))


def _only(root: Path, report: RunReport) -> dict[str, Any]:
    diagnostics = _sidecar(root, report)["diagnostics"]
    assert len(diagnostics) == 1, diagnostics
    return diagnostics[0]


def _job_failed_code(root: Path) -> str:
    return (root / "data" / "job.failed").read_text(encoding="utf-8").splitlines()[0]


def _assert_located_in_this_file(diagnostic: dict[str, Any], function: str) -> None:
    location = diagnostic["location"]
    assert location is not None
    assert location["file"].endswith(THIS_FILE), location
    assert location["function"].endswith(function), location
    assert isinstance(location["line"], int) and location["line"] > 0


def _cause_types(diagnostic: dict[str, Any]) -> list[str]:
    return [cause["type"] for cause in diagnostic["causes"]]


# --- EP: one row per phase -------------------------------------------------


def test_phase_vocabulary_is_the_canonical_list() -> None:
    """The phase list is the #686 AC vocabulary plus #688's argument validation."""
    assert FAILURE_PHASES == (
        "config_load",
        "mode_resolution",
        "pre_validate",
        "tile_prepare",
        "node_execution",
        "node_argument_validation",
        "artifact_publish",
        "post_validate",
        "finalize",
    )


def test_config_load_invalid_value__tc_ga686_ep_001(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EP-001: an invalid config value is a config_load failure."""
    # Given: an invalid error policy
    root = _materialize(tmp_path)

    # When: running
    report = _run(root, quiet_flow, monkeypatch, execution={"on_iteration_error": "bogus"})

    # Then: 1002, attributed to config_load, located outside the lifecycle translator
    diagnostic = _only(root, report)
    assert report.error is not None and report.error["code"] == 1002
    assert diagnostic["phase"] == "config_load"
    assert diagnostic["code"] == 1002
    assert diagnostic["category"] == "config"
    assert diagnostic["iteration_index"] is None
    assert diagnostic["location"] is not None
    assert not diagnostic["location"]["file"].endswith("runner/lifecycle.py")
    assert "ValidationError" in " ".join(_cause_types(diagnostic))


def test_config_load_permission_error__tc_ga686_ep_002(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EP-002: a permission failure reading config is located at its raiser."""

    # Given: a config loader that cannot read its files
    def denied(*_args: Any, **_kwargs: Any) -> Any:
        raise PermissionError("rdeconfig.yaml: permission denied")

    root = _materialize(tmp_path)
    monkeypatch.setattr("rdetoolkit.runner.lifecycle.load_config_from_root", denied)

    # When: running
    report = _run(root, quiet_flow, monkeypatch)

    # Then: the catalogued 1002 keeps the PermissionError and its source line
    diagnostic = _only(root, report)
    assert diagnostic["phase"] == "config_load"
    assert diagnostic["code"] == 1002
    assert diagnostic["exception"]["type"] == "PermissionError"
    _assert_located_in_this_file(diagnostic, "denied")


def test_mode_resolution_prepare_failure__tc_ga686_ep_003(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EP-003: ``prepare=`` runs within mode resolution."""
    # Given / When: a flow whose input preparation raises
    root = _materialize(tmp_path)
    report = _run(root, prepared_flow, monkeypatch)

    # Then: 3001 in mode_resolution, located in the preparation function
    diagnostic = _only(root, report)
    assert report.error is not None and report.error["code"] == 3001
    assert diagnostic["phase"] == "mode_resolution"
    assert diagnostic["causes"][0]["type"] == "ValueError"
    _assert_located_in_this_file(diagnostic, "_failing_prepare")


def test_mode_resolution_resolver_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failure inside mode resolution itself is not reported as config_load."""

    def unresolvable(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("cannot decide the mode")

    root = _materialize(tmp_path)
    monkeypatch.setattr("rdetoolkit.runner.lifecycle.resolve_mode_from_paths", unresolvable)

    report = _run(root, quiet_flow, monkeypatch)

    diagnostic = _only(root, report)
    assert diagnostic["phase"] == "mode_resolution"
    assert report.error is not None and diagnostic["code"] == report.error["code"]
    _assert_located_in_this_file(diagnostic, "unresolvable")


def test_pre_validate_missing_invoice__tc_ga686_ep_004(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EP-004: a missing file is pre_validate with the artifact named."""
    # Given: the source invoice is missing
    root = _materialize(tmp_path)
    (root / "data" / "invoice" / "invoice.json").unlink()

    # When: running
    report = _run(root, quiet_flow, monkeypatch)

    # Then: 4003, pre_validate, data-root-relative artifact path
    diagnostic = _only(root, report)
    assert diagnostic["phase"] == "pre_validate"
    assert diagnostic["code"] == 4003
    assert diagnostic["category"] == "validation"
    assert diagnostic["artifact_path"] == "invoice/invoice.json"
    assert _job_failed_code(root) == "ErrorCode=4003"


def test_pre_validate_invalid_invoice__tc_ga686_ep_005(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EP-005: a schema-invalid source invoice is pre_validate 4001."""
    root = _materialize(tmp_path)
    _generate._invalidate_invoice(root)  # noqa: SLF001 -- the generator owns the defect

    report = _run(root, quiet_flow, monkeypatch)

    diagnostic = _only(root, report)
    assert diagnostic["phase"] == "pre_validate"
    assert diagnostic["code"] == 4001
    assert diagnostic["artifact_path"] == "invoice/invoice.json"
    assert diagnostic["location"] is not None
    assert diagnostic["location"]["function"] != "pre_validate"


def test_tile_prepare_planner_failure__tc_ga686_ep_006(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EP-006: a failure while planning tiles is tile_prepare."""

    def broken_plan(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("cannot list inputdata")

    root = _materialize(tmp_path)
    monkeypatch.setattr("rdetoolkit.runner.planner.RunPlanner.create", broken_plan)

    report = _run(root, quiet_flow, monkeypatch)

    diagnostic = _only(root, report)
    assert report.error is not None and report.error["code"] == 3001
    assert diagnostic["phase"] == "tile_prepare"
    assert diagnostic["causes"][0]["type"] == "OSError"
    _assert_located_in_this_file(diagnostic, "broken_plan")


def test_tile_prepare_injection_failure__tc_ga686_ep_007(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EP-007: a flow that cannot be called for a tile fails in tile_prepare."""
    root = _materialize(tmp_path)

    report = _run(root, uninjectable_flow, monkeypatch, execution={"on_iteration_error": "fail_fast"})

    diagnostic = _only(root, report)
    assert report.status == "failed"
    assert diagnostic["phase"] == "tile_prepare"
    assert diagnostic["code"] == report.iterations[0]["error"]["code"]
    assert diagnostic["iteration_index"] == 0
    assert diagnostic["node_id"] is None
    assert diagnostic["call_id"] is None


def test_node_execution_failure__tc_ga686_ep_008(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EP-008: a node failure names node, call and the raising line."""
    root = _materialize(tmp_path)

    report = _run(root, raising_flow, monkeypatch)

    diagnostic = _only(root, report)
    assert diagnostic["phase"] == "node_execution"
    assert diagnostic["code"] == 3001
    assert diagnostic["category"] == "execution"
    assert diagnostic["iteration_index"] == 0
    assert diagnostic["node_id"] == raising_node.__node_spec__.id
    assert diagnostic["call_id"] == report.iterations[0]["error"]["call_id"]
    assert diagnostic["exception"]["type"] == "ValueError"
    assert diagnostic["exception"]["message"] == "node body failed"
    _assert_located_in_this_file(diagnostic, "raising_node")
    # The location is the raise statement, not the framework's call_node.
    source = Path(__file__).read_text(encoding="utf-8").splitlines()
    assert "the diagnosed source line" in source[diagnostic["location"]["line"] - 1]


def test_artifact_publish_failure__tc_ga686_ep_009(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EP-009: a raw copy failure is artifact_publish at its source."""

    def denied_copy(*_args: Any, **_kwargs: Any) -> None:
        raise PermissionError("raw/: permission denied")

    root = _materialize(tmp_path)
    monkeypatch.setattr("rdetoolkit.domain.artifacts.RawArtifactService.copy", denied_copy)

    report = _run(root, quiet_flow, monkeypatch, execution={"on_iteration_error": "fail_fast"})

    diagnostic = _only(root, report)
    assert report.status == "failed"
    assert diagnostic["phase"] == "artifact_publish"
    assert diagnostic["code"] == 3005
    assert diagnostic["exception"]["type"] == "PermissionError"
    assert diagnostic["iteration_index"] == 0
    _assert_located_in_this_file(diagnostic, "denied_copy")


def test_post_validate_failure__tc_ga686_ep_010(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EP-010: post_validate keeps its result (#685) and its diagnostic."""
    root = _materialize(tmp_path)

    report = _run(root, invalid_metadata_flow, monkeypatch)

    diagnostic = _only(root, report)
    assert report.status == "failed"
    assert report.iterations, "GA-01: the executed tile is kept"
    assert diagnostic["phase"] == "post_validate"
    assert diagnostic["code"] == 4002
    assert diagnostic["iteration_index"] == 0
    assert diagnostic["artifact_path"] == "meta/metadata.json"
    assert diagnostic["location"] is not None
    assert not diagnostic["location"]["file"].endswith("runner/lifecycle.py")
    assert "MetadataValidationError" in " ".join(_cause_types(diagnostic))


class _FailingFinalizer:
    def finalize(self, report: RunReport, config: Any) -> None:
        _ = (report, config)
        raise OSError("disk full while finalizing")


def test_finalize_failure__tc_ga686_ep_011(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EP-011: a finalize failure is still 5001 and is diagnosed."""
    root = _materialize(tmp_path)
    monkeypatch.chdir(root)
    runner = _runner(root, finalizer=_FailingFinalizer(), run_id_factory=lambda: "ga686-finalize")

    with pytest.raises(RdeInternalError) as raised:
        runner.run(quiet_flow)

    assert raised.value.code == 5001
    document = json.loads(_sidecar_path(root, "ga686-finalize").read_text(encoding="utf-8"))
    [diagnostic] = document["diagnostics"]
    assert diagnostic["phase"] == "finalize"
    assert diagnostic["code"] == 5001
    assert diagnostic["exception"]["type"] == "OSError"
    assert document["run_status"] == "success"


# --- BV / negative ----------------------------------------------------------


def test_explicit_cause_is_kept__tc_ga686_ev_020(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EV-020: ``raise ... from`` keeps the cause."""
    root = _materialize(tmp_path)
    report = _run(root, chained_flow, monkeypatch)

    diagnostic = _only(root, report)
    assert diagnostic["exception"]["type"] == "RuntimeError"
    assert diagnostic["causes"][0]["relation"] == "cause"
    assert diagnostic["causes"][0]["type"] == "KeyError"
    # The deepest exception decides the location: the failed lookup.
    _assert_located_in_this_file(diagnostic, "chained_node")


def test_implicit_context_is_kept__tc_ga686_ev_021(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EV-021: an exception raised while handling another keeps the context."""
    root = _materialize(tmp_path)
    report = _run(root, context_flow, monkeypatch)

    diagnostic = _only(root, report)
    assert diagnostic["causes"][0]["relation"] == "context"
    assert diagnostic["causes"][0]["type"] == "KeyError"


def test_structured_error_code_passes_through__tc_ga686_ev_022(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EV-022: ``ecode``/``emsg`` reach report and job.failed unchanged."""
    root = _materialize(tmp_path)
    report = _run(root, structured_flow, monkeypatch, execution={"on_iteration_error": "fail_fast"})

    diagnostic = _only(root, report)
    assert report.error is not None and report.error["code"] == 42
    assert report.error["message"] == "v1 says no"
    assert _job_failed_code(root) == "ErrorCode=42"
    assert diagnostic["code"] == 42
    assert diagnostic["category"] == "structured_error"
    assert diagnostic["exception"]["type"] == "rdetoolkit.exceptions.StructuredError"


def test_processing_error_code_passes_through__tc_ga686_ev_023(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EV-023: a ProcessingError keeps 3007."""
    root = _materialize(tmp_path)
    report = _run(root, processing_flow, monkeypatch, execution={"on_iteration_error": "fail_fast"})

    diagnostic = _only(root, report)
    assert report.error is not None and report.error["code"] == 3007
    assert _job_failed_code(root) == "ErrorCode=3007"
    assert diagnostic["code"] == 3007
    assert diagnostic["phase"] == "node_execution"


def test_interruption_keeps_3004__tc_ga686_ev_024(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EV-024: the process-interruption code is not rewritten."""
    root = _materialize(tmp_path)
    report = _run(root, interrupting_flow, monkeypatch)

    diagnostic = _only(root, report)
    assert report.error is not None and report.error["code"] == 3004
    assert _job_failed_code(root) == "ErrorCode=3004"
    assert diagnostic["code"] == 3004
    assert diagnostic["phase"] == "node_execution"


def test_sidecar_write_failure_changes_nothing__tc_ga686_ev_025(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-GA686-EV-025: a failing sidecar write never replaces the outcome."""

    def broken_writer(*_args: Any, **_kwargs: Any) -> Path:
        raise OSError("logs/: read-only file system")

    root = _materialize(tmp_path)
    monkeypatch.setattr("rdetoolkit.runner.lifecycle.write_failure_diagnostics", broken_writer)

    report = _run(root, raising_flow, monkeypatch)

    assert report.status == "failed"
    assert report.error is not None and report.error["code"] == 3001
    assert report.exit_code == 1
    assert _job_failed_code(root) == "ErrorCode=3001"
    assert not _sidecar_path(root, report.run_id).exists()
    assert "unavailable" in capsys.readouterr().err


def test_success_writes_no_sidecar__tc_ga686_ev_026(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EV-026: nothing failed, nothing is diagnosed."""
    root = _materialize(tmp_path)
    report = _run(root, quiet_flow, monkeypatch)

    assert report.status == "success"
    assert not _sidecar_path(root, report.run_id).exists()


def test_no_locals_arguments_or_environment__tc_ga686_ev_027(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EV-027: the default sidecar carries no values, only locations."""
    root = _materialize(tmp_path)
    monkeypatch.setenv("RDETOOLKIT_GA686_SECRET", f"{SECRET}-env")

    report = _run(root, secret_flow, monkeypatch, provenance={"repr_head": "on"})

    text = _sidecar_path(root, report.run_id).read_text(encoding="utf-8")
    assert SECRET not in text
    diagnostic = _only(root, report)
    for summary in [diagnostic["exception"], *diagnostic["causes"]]:
        assert summary["frames"], summary
        assert all(set(frame) == {"file", "line", "function"} for frame in summary["frames"])
    assert set(diagnostic["location"]) == {"file", "line", "function"}


@pytest.mark.parametrize(
    ("flow_fn", "phases"),
    [
        pytest.param(quiet_flow, ["artifact_publish"], id="completed-tile"),
        pytest.param(raising_flow, ["node_execution", "artifact_publish"], id="failed-tile"),
    ],
)
def test_iteration_record_failure_is_artifact_publish__tc_ga686_ep_012(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    flow_fn: Any,
    phases: list[str],
) -> None:
    """TC-GA686-EP-012: persisting a tile's record after the executor returned is ``artifact_publish``."""

    # Given: the per-tile record cannot be written
    def broken_record(self: RunAggregator, result: ExecutionResult) -> None:
        _ = (self, result)
        msg = "logs/iterations: no space left on device"
        raise OSError(msg)

    root = _materialize(tmp_path)
    monkeypatch.setattr(RunAggregator, "record", broken_record)

    # When: running
    report = _run(root, flow_fn, monkeypatch)

    # Then: the run fails and the escape is attributed to artifact_publish, not node_execution
    assert report.status == "failed"
    diagnostics = _sidecar(root, report)["diagnostics"]
    assert [diagnostic["phase"] for diagnostic in diagnostics] == phases
    assert "OSError" in [diagnostics[-1]["exception"]["type"], *_cause_types(diagnostics[-1])]


def test_phase_after_the_tile_loop_is_post_validate__tc_ga686_ep_013(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EP-013: once the tile loop ended, a failure is no longer ``tile_prepare``."""

    # Given: building the report after the last tile fails
    def broken_build(self: RunAggregator, **_kwargs: Any) -> RunReport:
        _ = self
        msg = "report assembly failed"
        raise RuntimeError(msg)

    root = _materialize(tmp_path)
    monkeypatch.setattr(RunAggregator, "build_report", broken_build)

    # When: running
    report = _run(root, quiet_flow, monkeypatch)

    # Then: the failure belongs to the next real phase
    assert report.status == "failed"
    diagnostic = _only(root, report)
    assert diagnostic["phase"] == "post_validate"


def test_external_frame_is_not_an_absolute_path__tc_ga686_ev_035(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EV-035: a frame outside the project and sys.path is ``<external>/<name>``."""
    # Given: a helper loaded from a file outside the project root and every sys.path entry
    module_path = tmp_path / "external-ga686" / "ext_helpers.py"
    module_path.parent.mkdir()
    module_path.write_text("def explode():\n    raise ValueError('external helper failed')\n", encoding="utf-8")
    spec = importlib.util.spec_from_file_location("ext_helpers_ga686", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setitem(_EXTERNAL, "explode", module.explode)
    root = _materialize(tmp_path)
    monkeypatch.chdir(root)
    assert not any(module_path.resolve().is_relative_to(Path(entry or ".").resolve()) for entry in sys.path)

    # When: a node calls it
    report = _run(root, external_flow, monkeypatch)

    # Then: the frame keeps its line and function, never the absolute path
    text = _sidecar_path(root, report.run_id).read_text(encoding="utf-8")
    assert str(module_path.parent) not in text
    assert str(module_path.parent.resolve()) not in text
    diagnostic = _only(root, report)
    frames = diagnostic["exception"]["frames"]
    assert {"file": "<external>/ext_helpers.py", "line": 2, "function": "explode"} in frames
    assert all(not frame["file"].startswith("/") for frame in frames), frames


def test_document_shape__tc_ga686_ev_028(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EV-028: the sidecar is versioned on its own; the report is still v2."""
    root = _materialize(tmp_path)
    report = _run(root, raising_flow, monkeypatch)

    document = _sidecar(root, report)
    assert document["schema_version"] == FAILURE_DIAGNOSTICS_SCHEMA_VERSION == "1"
    assert document["format"] == FAILURE_DIAGNOSTICS_FORMAT == "rdetoolkit.failure-diagnostics"
    assert document["producer"]["name"] == "rdetoolkit"
    assert document["run_id"] == report.run_id
    assert document["run_status"] == "failed"
    assert document["truncated"] is False
    assert set(document) == {"schema_version", "format", "producer", "run_id", "run_status", "diagnostics", "truncated"}
    persisted = json.loads((root / "data" / "logs" / f"run_report_{report.run_id}.json").read_text(encoding="utf-8"))
    assert persisted["schema_version"] == RUN_REPORT_SCHEMA_VERSION == "2"
    assert set(persisted) == set(report.to_dict())
    assert all("diagnostic" not in iteration for iteration in persisted["iterations"])


def test_partial_run_diagnoses_its_failed_tile__tc_ga686_ev_029(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EV-029: a partial run has a sidecar for the failed tile only."""
    root = _materialize(tmp_path, "multidatatile")
    report = _run(
        root,
        second_tile_fails_flow,
        monkeypatch,
        system={"extended_mode": "MultiDataTile"},
        execution={"on_iteration_error": "continue"},
    )

    document = _sidecar(root, report)
    assert report.status == "partial"
    assert document["run_status"] == "partial"
    [diagnostic] = document["diagnostics"]
    assert diagnostic["iteration_index"] == 1
    assert diagnostic["node_id"] == fail_tile_one.__node_spec__.id


def test_v1_callback_failure_is_diagnosed__tc_ga686_ev_030(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GA686-EV-030: the legacy callback target gets the same diagnostic."""
    from rdetoolkit.api.request import LegacyCallbackTarget, RunRequest  # noqa: PLC0415

    root = _materialize(tmp_path)
    monkeypatch.chdir(root)
    report = _runner(root).run(
        RunRequest(
            root=root,
            target=LegacyCallbackTarget(function=_raising_callback),
            config_source=_generate.oracle_config("invoice"),
        ),
    )

    diagnostic = _only(root, report)
    assert report.status == "failed"
    assert diagnostic["phase"] == "node_execution"
    assert diagnostic["exception"]["type"] == "RuntimeError"
    _assert_located_in_this_file(diagnostic, "_raising_callback")


def test_no_exception_is_not_invented__tc_ga686_ev_031() -> None:
    """TC-GA686-EV-031: missing information stays missing."""
    diagnostic = failure_diagnostic(None, phase="finalize", error=None)

    assert diagnostic.exception is None
    assert diagnostic.causes == ()
    assert diagnostic.location is None
    assert diagnostic.code is None
    assert diagnostic.category == "unknown"
    assert diagnostic.to_dict()["location"] is None


def _recurse(depth: int) -> None:
    if depth == 0:
        raise RecursionError("deep")
    _recurse(depth - 1)


def test_frames_message_and_chain_are_bounded__tc_ga686_ev_032() -> None:
    """TC-GA686-EV-032: every unbounded input is capped and flagged."""
    # Given: a deep stack
    try:
        _recurse(MAX_FRAMES + 10)
    except RecursionError as exc:
        deep = failure_diagnostic(exc, phase="node_execution")
    assert deep.exception is not None
    assert len(deep.exception.frames) == MAX_FRAMES
    assert deep.exception.frames_truncated is True
    assert deep.exception.frames[-1].function == "_recurse"

    # Given: a very long message
    long = failure_diagnostic(ValueError("x" * (MAX_MESSAGE_LENGTH * 3)), phase="node_execution")
    assert long.exception is not None
    assert long.exception.message.startswith("x" * MAX_MESSAGE_LENGTH)
    assert len(long.exception.message) < MAX_MESSAGE_LENGTH + 20

    # Given: a chain longer than the cap
    head: BaseException = ValueError("0")
    for index in range(1, MAX_CHAIN + 5):
        nxt = ValueError(str(index))
        nxt.__cause__ = head
        head = nxt
    chained = failure_diagnostic(head, phase="node_execution")
    assert len(chained.causes) == MAX_CHAIN - 1
    assert chained.causes_truncated is True

    # Given: a cyclic chain
    first, second = ValueError("a"), ValueError("b")
    first.__cause__ = second
    second.__cause__ = first
    cyclic = failure_diagnostic(first, phase="node_execution")
    assert [cause.message for cause in cyclic.causes] == ["b"]


def test_document_caps_diagnostics() -> None:
    """The document keeps at most MAX_DIAGNOSTICS entries and says so."""
    entries = [failure_diagnostic(None, phase="node_execution", iteration_index=index) for index in range(MAX_DIAGNOSTICS + 1)]

    document = diagnostics_document(entries, run_id="r", run_status="failed")

    assert len(document["diagnostics"]) == MAX_DIAGNOSTICS
    assert document["truncated"] is True
    assert diagnostics_document(entries[:1], run_id="r", run_status="failed")["truncated"] is False


def test_tile_cap_leaves_room_for_the_run_diagnostic__tc_ga686_ev_033(tmp_path: Path) -> None:
    """TC-GA686-EV-033: tile diagnostics never crowd out the run-level one."""
    runner = Runner(root=tmp_path)
    tile = ExecutionResult(
        iteration_index=0,
        status="failed",
        call_records=(),
        outputs=(),
        diagnostic=failure_diagnostic(None, phase="node_execution"),
    )
    for _ in range(MAX_DIAGNOSTICS + 5):
        runner._record_tile_diagnostic(tile)  # noqa: SLF001 -- the cap is a Runner invariant
    runner._record_tile_diagnostic(ExecutionResult(iteration_index=1, status="completed", call_records=(), outputs=()))  # noqa: SLF001
    runner._record_diagnostic(ValueError("run"), phase="post_validate", error=None)  # noqa: SLF001
    runner._record_diagnostic(OSError("final"), phase="finalize", error=None)  # noqa: SLF001

    kept: list[FailureDiagnostic] = runner._diagnostics  # noqa: SLF001
    assert len(kept) == MAX_DIAGNOSTICS
    assert [item.phase for item in kept[-2:]] == ["post_validate", "finalize"]
    assert runner._diagnostics_dropped is True  # noqa: SLF001


def test_finalize_and_sidecar_failure_keep_the_finalize_error__tc_ga686_ev_034(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-GA686-EV-034: when both fail, the caller sees the finalize error."""

    def broken_writer(*_args: Any, **_kwargs: Any) -> Path:
        definition = ERROR_CATALOG[3004]
        error_cls: Any = RdeExecutionError
        raise error_cls(code=3004, name=definition.name, message="interrupted while writing")

    root = _materialize(tmp_path)
    monkeypatch.chdir(root)
    monkeypatch.setattr("rdetoolkit.runner.lifecycle.write_failure_diagnostics", broken_writer)
    runner = _runner(root, finalizer=_FailingFinalizer())

    with pytest.raises(RdeError) as raised:
        runner.run(quiet_flow)

    assert raised.value.code == 5001
    assert "unavailable" in capsys.readouterr().err


def test_interruption_while_writing_after_success_propagates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An interruption during the sidecar write after a decided outcome stops the run (3004)."""

    def interrupted_writer(*_args: Any, **_kwargs: Any) -> Path:
        definition = ERROR_CATALOG[3004]
        error_cls: Any = RdeExecutionError
        raise error_cls(code=3004, name=definition.name, message="interrupted while writing")

    root = _materialize(tmp_path)
    monkeypatch.setattr("rdetoolkit.runner.lifecycle.write_failure_diagnostics", interrupted_writer)

    with pytest.raises(RdeError) as raised:
        _run(root, raising_flow, monkeypatch)

    assert raised.value.code == 3004


def test_broken_diagnosis_never_changes_the_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A defect while building a diagnostic is a stderr notice, not a new failure."""

    def broken_builder(*_args: Any, **_kwargs: Any) -> FailureDiagnostic:
        raise TypeError("diagnostic builder defect")

    root = _materialize(tmp_path)
    monkeypatch.setattr("rdetoolkit.runner.lifecycle.failure_diagnostic", broken_builder)
    monkeypatch.setattr("rdetoolkit.runner.executor.failure_diagnostic", broken_builder)
    (root / "data" / "invoice" / "invoice.json").unlink()

    report = _run(root, quiet_flow, monkeypatch)

    assert report.status == "failed"
    assert report.error is not None and report.error["code"] == 4003
    assert not _sidecar_path(root, report.run_id).exists()
    assert "could not be diagnosed" in capsys.readouterr().err


def test_broken_tile_diagnosis_never_changes_the_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The tile executor applies the same guard to node failures."""

    def broken_builder(*_args: Any, **_kwargs: Any) -> FailureDiagnostic:
        raise TypeError("diagnostic builder defect")

    root = _materialize(tmp_path)
    monkeypatch.setattr("rdetoolkit.runner.executor.failure_diagnostic", broken_builder)

    report = _run(root, raising_flow, monkeypatch)

    assert report.status == "failed"
    assert report.error is not None and report.error["code"] == 3001
    assert not _sidecar_path(root, report.run_id).exists()
    assert "could not be diagnosed" in capsys.readouterr().err


def test_unprintable_exception_message_is_marked() -> None:
    """A ``__str__`` that raises is reported as unavailable."""

    class Unprintable(Exception):
        def __str__(self) -> str:
            raise RuntimeError("no str")

    diagnostic = failure_diagnostic(Unprintable(), phase="node_execution")

    assert diagnostic.exception is not None
    assert "message unavailable" in diagnostic.exception.message


def test_display_paths_are_relative(tmp_path: Path) -> None:
    """Frame paths are project-relative, else relative to their sys.path entry."""
    project_file = tmp_path / "pkg" / "mod.py"
    assert failure_module._display_path(str(project_file), tmp_path) == "pkg/mod.py"  # noqa: SLF001
    assert failure_module._display_path("<string>", tmp_path) == "<string>"  # noqa: SLF001
    assert failure_module._display_path(failure_module.__file__, None) == "rdetoolkit/report/failure.py"  # noqa: SLF001
    outside = "/nonexistent-ga686/abs/file.py"
    assert failure_module._display_path(outside, None) == "<external>/file.py"  # noqa: SLF001


def test_pseudo_files_are_library_frames_and_unresolvable_paths_are_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    """``<frozen ...>`` never wins the location; a path that cannot resolve is kept as given."""
    assert failure_module._is_library("<frozen importlib._bootstrap>") is True  # noqa: SLF001

    def unresolvable(self: Path, strict: bool = False) -> Path:
        _ = (self, strict)
        raise OSError("loop")

    monkeypatch.setattr(Path, "resolve", unresolvable)
    assert failure_module._resolve("some/where.py") == Path("some/where.py")  # noqa: SLF001


def _interrupt() -> RdeExecutionError:
    definition = ERROR_CATALOG[3004]
    error_cls: Any = RdeExecutionError
    error: RdeExecutionError = error_cls(code=3004, name=definition.name, message=definition.message_template)
    return error


def test_interruption_while_diagnosing_propagates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Diagnosing swallows defects, never the run interruption (3004)."""
    from rdetoolkit.runner import executor as executor_module  # noqa: PLC0415

    def interrupted(*_args: Any, **_kwargs: Any) -> FailureDiagnostic:
        raise _interrupt()

    monkeypatch.setattr("rdetoolkit.runner.lifecycle.failure_diagnostic", interrupted)
    with pytest.raises(RdeExecutionError) as run_level:
        Runner(root=tmp_path)._record_diagnostic(ValueError("x"), phase="finalize", error=None)  # noqa: SLF001
    assert run_level.value.code == 3004

    with pytest.raises(RdeExecutionError) as tile_level:
        executor_module._guarded_diagnostic(interrupted)  # noqa: SLF001
    assert tile_level.value.code == 3004


def test_validated_artifact_outside_the_data_root_is_named_only(tmp_path: Path) -> None:
    """An artifact path that is not below the data root is reduced to its file name."""
    from types import SimpleNamespace  # noqa: PLC0415

    from rdetoolkit.runner import executor as executor_module  # noqa: PLC0415

    elsewhere = tmp_path / "elsewhere"
    tile: Any = SimpleNamespace(out=SimpleNamespace(meta=elsewhere / "meta", invoice=elsewhere / "invoice"))
    plan: Any = SimpleNamespace(data_root=tmp_path / "data")

    assert executor_module._validated_artifact(plan, tile, {"code": 4002}) == "metadata.json"  # noqa: SLF001
    assert executor_module._validated_artifact(plan, tile, {"code": 4001}) == "invoice.json"  # noqa: SLF001
