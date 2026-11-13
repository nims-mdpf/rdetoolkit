"""The v1 entry writes v1.7.1's stderr traceback for failures outside a tile too.

#584 restored the traceback for a failing callback (a tile failure). A run
that failed before or after the tiles -- invoice schema validation, mode
resolution, output validation -- still wrote the right ``job.failed`` and exit
1, but only the one-line notice on stderr, where v1.7.1 printed the traceback
of the error ``job.failed`` reports. The Runner now records that run-level
exception in a context the v1 entry opens, and the entry formats it with the
same v1 formatter.

EP / BV table:

| TC-ID         | Class    | Input                                                        | Expected                                               |
|---------------|----------|--------------------------------------------------------------|--------------------------------------------------------|
| TC-F03D1-001  | EP inval | invoice.json violates invoice.schema.json, nothing configured | python-form traceback naming the error; exit 1         |
| TC-F03D1-002  | EP inval | the same, ``Config`` compact                                  | compact block only                                     |
| TC-F03D1-003  | EP inval | the same                                                     | traceback before the final notice; job.failed unchanged |
| TC-F03D1-004  | EP valid | v2 entry ``run(flow=...)`` with the same invalid invoice      | no traceback (v2 entry unchanged)                      |
| TC-F03D1-010  | EP valid | run error without ``call_id`` + a recorded run failure        | the run failure                                        |
| TC-F03D1-011  | EP valid | tile error (``call_id``) + both kinds recorded                | the tile failure (tile rule unchanged)                 |
| TC-F03D1-012  | BV       | tile error, no tile capture, a run failure recorded           | ``None`` (never paired across kinds)                   |
| TC-F03D1-013  | BV       | run error without ``call_id``, nothing recorded               | ``None``                                               |
| TC-F03D1-020  | EP valid | Runner validation fails inside ``capture_run_failures``       | that exception is recorded; report still returned      |
| TC-F03D1-021  | EP valid | the same run outside any capture                              | report returned, nothing recorded, no error            |
| TC-F03D1-022  | BV       | nested captures                                               | inner records only its own; outer restored after       |
| TC-F03D1-023  | EP valid | successful run inside a capture                               | nothing recorded                                       |
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit import flow, workflows
from rdetoolkit.api.request import LegacyCallbackTarget, RunRequest
from rdetoolkit.models.config import Config, TracebackSettings
from rdetoolkit.runner.invoker import capture_run_failures, record_run_failure
from rdetoolkit.runner.lifecycle import Runner

_PY_FULL = "Traceback (most recent call last):"
_PY_SIMPLIFIED = "Traceback (simplified message):"
_COMPACT_OPEN = "<STACKTRACE>"
_COMPACT_CLOSE = "</STACKTRACE>"
_FAILURE_NOTICE = "rdetoolkit: the structured process failed; see data/job.failed for the error code"


@pytest.fixture(autouse=True)
def _no_trace_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRACE_VERBOSE", raising=False)
    monkeypatch.delenv("TRACE_FORMAT", raising=False)


def _seed(data_root: Path, *, valid_invoice: bool) -> None:
    """Create an invoice-mode tree whose invoice.json does or does not satisfy the schema."""
    for dirname in ("inputdata", "invoice", "tasksupport"):
        (data_root / dirname).mkdir(parents=True, exist_ok=True)
    (data_root / "inputdata" / "sample.txt").write_text("input", encoding="utf-8")
    basic: dict[str, Any] = {"dateSubmitted": "2026-11-11", "dataOwnerId": "0" * 56, "dataName": "f03d1"}
    invoice = {"datasetId": "f03d1-dataset", "basic": basic, "custom": {"temperature": 1 if valid_invoice else "hot"}}
    (data_root / "invoice" / "invoice.json").write_text(json.dumps(invoice), encoding="utf-8")
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://rde.nims.go.jp/rde/dataset-templates/f03d1/invoice.schema.json",
        "type": "object",
        "required": ["custom"],
        "properties": {
            "custom": {
                "type": "object",
                "label": {"ja": "固有情報", "en": "Custom"},
                "required": ["temperature"],
                "properties": {
                    "temperature": {"label": {"ja": "温度", "en": "Temperature"}, "type": "number"},
                },
            },
        },
    }
    (data_root / "tasksupport" / "invoice.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    (data_root / "tasksupport" / "metadata-def.json").write_text('{"constant": {}, "variable": []}', encoding="utf-8")


@pytest.fixture
def invalid_project(tmp_path: Path) -> Path:
    """A project whose invoice.json violates its schema."""
    _seed(tmp_path / "data", valid_invoice=False)
    return tmp_path


@pytest.fixture
def valid_project(tmp_path: Path) -> Path:
    """A project whose invoice.json satisfies its schema."""
    _seed(tmp_path / "data", valid_invoice=True)
    return tmp_path


def _callback(srcpaths: object, resource_paths: object) -> None:
    del srcpaths, resource_paths


def _run_v1(project: Path, monkeypatch: pytest.MonkeyPatch, config: Any) -> int:
    monkeypatch.chdir(project)
    try:
        workflows.run(custom_dataset_function=_callback, config=config)
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


def _job_failed(project: Path) -> str:
    return (project / "data" / "job.failed").read_text(encoding="utf-8")


def _job_failed_message(project: Path) -> str:
    lines = dict(line.split("=", 1) for line in _job_failed(project).splitlines() if "=" in line)
    return lines["ErrorMessage"]


# ---------------------------------------------------------------------------
# v1 entry: stderr carries the traceback of the error job.failed reports
# ---------------------------------------------------------------------------


def test_invalid_invoice_prints_python_traceback__tc_f03d1_001(
    invalid_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-F03D1-001: a run-level validation failure writes v1's python-form traceback."""
    # Given: an invoice that violates the schema, nothing configured
    capsys.readouterr()
    # When: the v1 entry runs
    code = _run_v1(invalid_project, monkeypatch, None)
    err = capsys.readouterr().err
    # Then: exit 1 and the traceback of the error job.failed reports
    assert code == 1
    assert _PY_FULL in err
    assert _PY_SIMPLIFIED in err
    assert "temperature" in err
    assert "ErrorCode=" in _job_failed(invalid_project)


def test_invalid_invoice_compact_traceback__tc_f03d1_002(
    invalid_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-F03D1-002: the configured v1 format applies to run-level failures as well."""
    # Given: the compact format configured on the v1 Config
    config = Config(traceback=TracebackSettings(enabled=True, format="compact"))
    capsys.readouterr()
    # When
    code = _run_v1(invalid_project, monkeypatch, config)
    err = capsys.readouterr().err
    # Then: only the compact block
    assert code == 1
    assert _COMPACT_OPEN in err
    assert _COMPACT_CLOSE in err
    assert _PY_FULL not in err


def test_traceback_precedes_notice_and_job_failed_is_unchanged__tc_f03d1_003(
    invalid_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-F03D1-003: the notice stays last and job.failed is not affected by the traceback."""
    # Given / When: the failing run, with the traceback formatter disabled to get the baseline job.failed
    monkeypatch.setattr(workflows, "_write_v1_failure_traceback", lambda failure, config_source: None)
    _run_v1(invalid_project, monkeypatch, None)
    baseline = _job_failed(invalid_project)
    monkeypatch.undo()
    (invalid_project / "data" / "job.failed").unlink()
    capsys.readouterr()
    code = _run_v1(invalid_project, monkeypatch, None)
    err = capsys.readouterr().err
    # Then: same job.failed, the traceback before the notice, the notice last
    assert code == 1
    assert _job_failed(invalid_project) == baseline
    assert err.index(_PY_FULL) < err.index(_FAILURE_NOTICE)
    assert err.rstrip().endswith(_FAILURE_NOTICE)
    assert _job_failed_message(invalid_project).split(" Remediation:")[0][:40] in err


@flow
def _noop_flow() -> None:
    return None


def test_v2_entry_prints_no_traceback__tc_f03d1_004(
    invalid_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-F03D1-004: the v2 flow entry keeps reporting through the RunReport only."""
    # Given: the same invalid invoice
    monkeypatch.chdir(invalid_project)
    capsys.readouterr()
    # When: the v2 entry runs
    report = workflows.run(flow=_noop_flow)
    err = capsys.readouterr().err
    # Then: the run failed and no traceback was written
    assert report.status == "failed"
    assert _PY_FULL not in err
    assert _COMPACT_OPEN not in err


# ---------------------------------------------------------------------------
# Selection: which captured exception is formatted
# ---------------------------------------------------------------------------

_RUN_ERROR: dict[str, Any] = {"code": 4001, "name": "InvoiceSchemaInvalid", "message": "m"}
_TILE_ERROR: dict[str, Any] = {"code": 3001, "name": "NodeExecutionFailed", "message": "m", "call_id": "unknown"}


def test_run_error_selects_run_failure__tc_f03d1_010() -> None:
    """TC-F03D1-010: a run-level error is paired with the recorded run-level exception."""
    run_failure = ValueError("run level")
    selected = workflows._v1_failure_exception(_RUN_ERROR, [], [run_failure])
    assert selected is run_failure


def test_tile_error_keeps_tile_rule__tc_f03d1_011() -> None:
    """TC-F03D1-011: a tile error still selects the tile failure, not the run-level wrapper."""
    tile_failure = ValueError("tile")
    selected = workflows._v1_failure_exception(_TILE_ERROR, [tile_failure], [RuntimeError("wrapper")])
    assert selected is tile_failure


def test_tile_error_never_takes_run_failure__tc_f03d1_012() -> None:
    """TC-F03D1-012: a tile error without a captured tile exception selects nothing."""
    selected = workflows._v1_failure_exception(_TILE_ERROR, [], [RuntimeError("wrapper")])
    assert selected is None


def test_run_error_without_record_selects_nothing__tc_f03d1_013() -> None:
    """TC-F03D1-013: nothing recorded means nothing to format."""
    selected = workflows._v1_failure_exception(_RUN_ERROR, [], [])
    assert selected is None


# ---------------------------------------------------------------------------
# Runner seam: capture_run_failures
# ---------------------------------------------------------------------------


def _runner_request(project: Path) -> tuple[Runner, RunRequest]:
    data_root = project / "data"
    runner = Runner(root=project, inputdata_path=data_root / "inputdata", unpacked_dir_path=data_root / "temp")
    request = RunRequest(root=project, target=LegacyCallbackTarget(function=_callback), config_source=Config())
    return runner, request


def test_runner_records_pre_validation_failure__tc_f03d1_020(invalid_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-F03D1-020: the exception behind a run-level failure is recorded, the report still returned."""
    monkeypatch.chdir(invalid_project)
    runner, request = _runner_request(invalid_project)
    with capture_run_failures() as failures:
        report = runner.run(request)
    assert report.status == "failed"
    assert report.error is not None
    assert "call_id" not in report.error
    assert len(failures) == 1
    assert isinstance(failures[0], Exception)


def test_no_capture_records_nothing__tc_f03d1_021(invalid_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-F03D1-021: without a capture the Runner behaves exactly as before."""
    monkeypatch.chdir(invalid_project)
    runner, request = _runner_request(invalid_project)
    report = runner.run(request)
    assert report.status == "failed"
    record_run_failure(ValueError("outside any capture"))


def test_nested_captures__tc_f03d1_022() -> None:
    """TC-F03D1-022: the innermost capture records; the outer one is restored after it."""
    with capture_run_failures() as outer:
        with capture_run_failures() as inner:
            record_run_failure(ValueError("inner"))
        record_run_failure(ValueError("outer"))
    assert [str(exc) for exc in inner] == ["inner"]
    assert [str(exc) for exc in outer] == ["outer"]


def test_successful_run_records_nothing__tc_f03d1_023(valid_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-F03D1-023: a run that succeeds leaves the capture empty."""
    monkeypatch.chdir(valid_project)
    runner, request = _runner_request(valid_project)
    with capture_run_failures() as failures:
        report = runner.run(request)
    assert report.status == "success", report.error
    assert failures == []
