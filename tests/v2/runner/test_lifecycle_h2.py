"""Session H2 Runner lifecycle completion tests.

Equivalence partitions (EP):

| API | Partition | Rationale | Expected | Test ID |
| --- | --- | --- | --- | --- |
| ``Runner.run`` | fake planner + flow target | mode-independent lifecycle seam | all six public steps and injected collaborators run in order | TC-EP-H2-001 |
| ``Runner.pre_validate`` | missing source artifact | invalid input structure | failed report and ``job.failed`` use code 4003 before flow execution | TC-EP-H2-002 |
| ``Runner.post_validate`` | invalid completed invoice | invalid final artifact | failed report and ``job.failed`` use code 4001 | TC-EP-H2-003 |
| ``Runner.post_validate`` | invalid completed metadata | invalid optional artifact | metadata failure is wrapped with code 4002 | TC-EP-H2-004 |
| ``Runner.run`` | finalizer raises I/O error | persistence boundary failure | raise RdeInternalError(5001), do not replace success report | TC-EP-HR-F5-001 |

Boundary values (BV):

| API | Boundary | Rationale | Expected | Test ID |
| --- | --- | --- | --- | --- |
| ``Runner.post_validate`` | one completed and one failed iteration | smallest mixed result | only the completed tile is validated | TC-BV-H2-001 |
| ``Runner.post_validate`` | metadata absent | v1 optional metadata boundary | metadata validation is skipped | TC-BV-H2-002 |
| ``Runner.run`` | first finalize call fails | exactly-once boundary | finalizer call count remains one | TC-BV-HR-F5-001 |
"""

from __future__ import annotations

import json
import signal
from collections.abc import Callable
from dataclasses import fields
from pathlib import Path
from typing import Any
from unittest.mock import ANY

import pytest

from rdetoolkit.api.request import RunRequest
from rdetoolkit.exceptions import MetadataValidationError
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.paths import resolve_tile_paths
from rdetoolkit.types import InputPaths, IterationInfo, OutputContext, RdeConfig


_SEED_INVOICE = {
    "datasetId": "seed-dataset",
    "basic": {
        "dateSubmitted": "2026-07-20",
        "dataOwnerId": "0" * 56,
        "dataName": "seed",
    },
}


def _write_valid_input(root: Path) -> Path:
    data_root = root / "data"
    (data_root / "inputdata").mkdir(parents=True)
    (data_root / "invoice").mkdir()
    (data_root / "tasksupport").mkdir()
    (data_root / "unpacked").mkdir()
    (data_root / "inputdata" / "sample.txt").write_text("sample", encoding="utf-8")
    (data_root / "invoice" / "invoice.json").write_text(
        json.dumps(_SEED_INVOICE),
        encoding="utf-8",
    )
    (data_root / "tasksupport" / "invoice.schema.json").write_text(
        json.dumps({"properties": {}}),
        encoding="utf-8",
    )
    return data_root


def _report(*, status: str = "success", iterations: list[dict[str, Any]] | None = None) -> RunReport:
    return RunReport(
        run_id="h2-run",
        status=status,
        flow_id="tests.h2_flow",
        mode="invoice",
        started_at="2026-07-20T00:00:00",
        duration_ms=0.0,
        config_digest="sha256:test",
        iterations=[] if iterations is None else iterations,
        warnings=[],
    )


class _FakePlanner:
    """Return a single explicit tile without consulting a mode implementation."""

    def __init__(self, data_root: Path) -> None:
        self.data_root = data_root
        self.calls: list[tuple[RunRequest, RdeConfig, ModeKind]] = []

    def create(
        self,
        request: RunRequest,
        *,
        config: RdeConfig,
        mode: ModeKind,
        data_root: Path,
    ) -> Any:
        from rdetoolkit.runner.planner import ExecutionPlan, TilePlan

        self.calls.append((request, config, mode))
        resource_paths = resolve_tile_paths(self.data_root, 0)
        for field in fields(resource_paths):
            Path(getattr(resource_paths, field.name)).mkdir(parents=True, exist_ok=True)
        out = OutputContext.from_resource_paths(resource_paths)
        paths = InputPaths(
            inputdata=self.data_root / "inputdata",
            invoice=self.data_root / "invoice",
            tasksupport=self.data_root / "tasksupport",
            raw=self.data_root / "inputdata" / "sample.txt",
            rawfiles=(self.data_root / "inputdata" / "sample.txt",),
        )
        tile = TilePlan(
            iteration=IterationInfo(index=0, total=1, mode=mode.value),
            paths=paths,
            out=out,
            invoice=None,
        )
        return ExecutionPlan(
            run_id="h2-run",
            target=request.target,
            mode=mode,
            config=config,
            root=request.root,
            error_policy=config.execution.on_iteration_error,
            tiles=(tile,),
            data_root=data_root,
            invoice_source=data_root / "invoice" / "invoice.json",
        )


class _RecordingFinalizer:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def finalize(self, report: RunReport, config: RdeConfig) -> None:
        self.calls.append("finalizer")


class _FailingFinalizer:
    def __init__(self) -> None:
        self.reports: list[RunReport] = []

    def finalize(self, report: RunReport, config: RdeConfig) -> None:
        self.reports.append(report)
        raise OSError("disk full")


class _RecordingRunner(Runner):
    def __init__(self, *, calls: list[str], **kwargs: Any) -> None:
        self._calls = calls
        super().__init__(**kwargs)

    def load_config(self, source: object | None = None) -> RdeConfig:
        self._calls.append("load_config")
        return RdeConfig()

    def resolve_mode(self, config: RdeConfig) -> ModeKind:
        self._calls.append("resolve_mode")
        return ModeKind.invoice

    def pre_validate(self, config: RdeConfig) -> None:
        self._calls.append("pre_validate")
        super().pre_validate(config)

    def iterate(
        self,
        flow_fn: Callable[..., Any],
        mode: ModeKind,
        config: RdeConfig,
    ) -> RunReport:
        self._calls.append("iterate")
        return super().iterate(flow_fn, mode, config)

    def post_validate(self, config: RdeConfig, report: RunReport) -> None:
        self._calls.append("post_validate")
        super().post_validate(config, report)

    def finalize(self, report: RunReport, config: RdeConfig) -> None:
        self._calls.append("finalize")
        super().finalize(report, config)


def test_fake_planner_runs_full_lifecycle_and_runner_owns_signal__tc_ep_h2_001(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-EP-H2-001: a fake planner reaches every lifecycle step and collaborator."""
    # Given: valid input, a mode-free fake planner, and an injected finalizer
    data_root = _write_valid_input(tmp_path)
    calls: list[str] = []
    planner = _FakePlanner(data_root)
    finalizer = _RecordingFinalizer(calls)
    signal_calls: list[tuple[int, Any]] = []
    previous = signal.getsignal(signal.SIGTERM)
    monkeypatch.setattr(signal, "signal", lambda number, handler: signal_calls.append((number, handler)))
    flow_calls: list[str] = []

    def _flow() -> None:
        flow_calls.append("flow")

    runner = _RecordingRunner(
        calls=calls,
        root=tmp_path,
        inputdata_path=data_root / "inputdata",
        unpacked_dir_path=data_root / "unpacked",
        planner=planner,
        finalizer=finalizer,
        run_id_factory=lambda: "h2-run",
    )

    # When: the complete Runner lifecycle executes
    report = runner.run(_flow)

    # Then: public steps remain ordered, injected seams execute, and only Runner touches SIGTERM
    assert report.status == "success"
    assert flow_calls == ["flow"]
    assert len(planner.calls) == 1
    assert calls == [
        "load_config",
        "resolve_mode",
        "pre_validate",
        "iterate",
        "post_validate",
        "finalize",
        "finalizer",
    ]
    assert signal_calls == [(signal.SIGTERM, ANY), (signal.SIGTERM, previous)]


def test_finalize_io_failure_is_catalogued_and_not_retried__tc_ep_hr_f5_001(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-EP/BV-HR-F5-001: finalization is an exactly-once exception boundary."""
    # Given: a successful business lifecycle and a finalizer that fails on its first call
    from rdetoolkit.errors import RdeInternalError

    finalizer = _FailingFinalizer()
    runner = Runner(root=tmp_path, finalizer=finalizer, run_id_factory=lambda: "h2-finalize-failure")
    success_report = _report()
    monkeypatch.setattr(runner, "load_config", lambda source: RdeConfig())
    monkeypatch.setattr(runner, "resolve_mode", lambda config: ModeKind.invoice)
    monkeypatch.setattr(runner, "pre_validate", lambda config: None)
    monkeypatch.setattr(runner, "iterate", lambda flow_fn, mode, config: success_report)
    monkeypatch.setattr(runner, "post_validate", lambda config, report: None)

    # When: persistence raises an ordinary I/O exception
    with pytest.raises(RdeInternalError) as exc_info:
        runner.run(lambda: None)

    # Then: it is catalogued as internal I/O context and never retried with a failed report
    assert exc_info.value.code == 5001
    assert "disk full" in exc_info.value.message
    assert finalizer.reports == [success_report]
    assert finalizer.reports[0].status == "success"


def test_missing_input_artifact_fails_before_flow_with_4003__tc_ep_h2_002(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-EP-H2-002: missing source structure is catalogued before invocation."""
    # Given: a data root with input files but no source invoice or schema
    data_root = tmp_path / "data"
    (data_root / "inputdata").mkdir(parents=True)
    (data_root / "inputdata" / "sample.txt").write_text("sample", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    flow_calls: list[str] = []
    runner = Runner(
        root=tmp_path,
        inputdata_path=data_root / "inputdata",
        unpacked_dir_path=data_root / "unpacked",
        run_id_factory=lambda: "h2-missing",
    )
    monkeypatch.setattr(runner, "resolve_mode", lambda config: ModeKind.invoice)

    # When: the full lifecycle reaches pre-validation
    report = runner.run(lambda: flow_calls.append("flow"))

    # Then: invocation is skipped and the failure artifact uses InputValidationFailed
    assert flow_calls == []
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == 4003
    assert "invoice.json" in report.error["message"]
    # The 4003 template already prefixes the path; the reason must be the bare
    # path, never a second sentence that double-formats the message.
    assert "does not exist:" not in report.error["message"]
    assert "ErrorCode=4003" in (data_root / "job.failed").read_text(encoding="utf-8")


def test_invalid_completed_invoice_fails_run_with_4001__tc_ep_h2_003(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-EP-H2-003: run-level output sweep maps invoice failure to code 4001."""
    # Given: valid source input and a fake tile whose flow corrupts its final invoice
    data_root = _write_valid_input(tmp_path)
    monkeypatch.chdir(tmp_path)
    planner = _FakePlanner(data_root)
    runner = Runner(
        root=tmp_path,
        inputdata_path=data_root / "inputdata",
        unpacked_dir_path=data_root / "unpacked",
        planner=planner,
        run_id_factory=lambda: "h2-invalid-output",
    )
    monkeypatch.setattr(runner, "resolve_mode", lambda config: ModeKind.invoice)

    def _corrupt_invoice(out: OutputContext) -> None:
        (out.invoice / "invoice.json").write_text("{}", encoding="utf-8")

    # When: post-validation checks the completed tile
    report = runner.run(_corrupt_invoice)

    # Then: the intentional run-level semantic is failed with the catalogued invoice code
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == 4001
    assert "ErrorCode=4001" in (data_root / "job.failed").read_text(encoding="utf-8")


def test_invalid_metadata_is_wrapped_with_4002__tc_ep_h2_004(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-EP-H2-004: an existing invalid metadata artifact maps to code 4002."""
    # Given: one completed tile with a metadata file and a failing v1 validator
    data_root = _write_valid_input(tmp_path)
    metadata_path = data_root / "meta" / "metadata.json"
    metadata_path.parent.mkdir()
    metadata_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "rdetoolkit.domain.validation.metadata_validate",
        lambda path: (_ for _ in ()).throw(MetadataValidationError("invalid metadata")),
    )
    runner = Runner(root=tmp_path)

    # When: the post-run sweep reaches metadata validation
    with pytest.raises(Exception) as captured:
        runner.post_validate(RdeConfig(), _report(iterations=[{"index": 0, "status": "completed"}]))

    # Then: the public error carries the catalogued metadata-validation code
    assert getattr(captured.value, "code", None) == 4002


def test_post_validate_checks_completed_only_and_skips_absent_metadata__tc_bv_h2_001_002(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-BV-H2-001/002: failed tiles and absent metadata are excluded."""
    # Given: the smallest mixed report, with artifacts present only for the completed tile
    data_root = _write_valid_input(tmp_path)
    invoice_calls: list[tuple[Path, Path]] = []
    metadata_calls: list[Path] = []
    monkeypatch.setattr(
        "rdetoolkit.domain.validation.invoice_validate",
        lambda path, schema: invoice_calls.append((Path(path), Path(schema))),
    )
    monkeypatch.setattr(
        "rdetoolkit.domain.validation.metadata_validate",
        lambda path: metadata_calls.append(Path(path)),
    )
    runner = Runner(root=tmp_path)
    report = _report(
        iterations=[
            {"index": 0, "status": "completed"},
            {"index": 1, "status": "failed"},
        ],
    )

    # When: post-validation sweeps the primary iteration results
    runner.post_validate(RdeConfig(), report)

    # Then: only tile zero's invoice is checked and missing metadata is a v1-compatible skip
    assert invoice_calls == [
        (
            data_root / "invoice" / "invoice.json",
            data_root / "tasksupport" / "invoice.schema.json",
        ),
    ]
    assert metadata_calls == []
