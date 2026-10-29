"""Atomic report writes and re-run hygiene (Session K3, rulings #3/#4).

Design authority: PhaseK_prompts ruling #6(b)/(c). The run report and every
``iteration_{i}.json`` are written to a same-directory temporary file and moved
into place with ``os.replace``: an interrupted write leaves the previous file
intact and no temporary behind. ``job.failed`` stays with v1's
``write_job_errorlog_file`` (contract). At the start of tile iteration the
Runner empties ``<data_root>/logs/iterations/`` so a shorter re-run never mixes
with a longer run's high indices; ``job.failed``, ``run_report_*`` and
``events_*`` are not touched.

EP table:

| TC-ID         | Partition                                      | Expected                                            |
|---------------|------------------------------------------------|-----------------------------------------------------|
| TC-K3-ATM-001 | atomic_write_text into a fresh path            | file holds the text, no temp left                   |
| TC-K3-ATM-002 | atomic_write_text over an existing file        | replaced content, no temp left                      |
| TC-K3-ATM-003 | os.replace raises                              | previous file intact, no temp left, error re-raised |
| TC-K3-ATM-004 | write raises half-way                          | previous file intact, no temp left, error re-raised |
| TC-K3-ATM-005 | write_run_report while os.replace fails        | previous report intact, no temp left                |
| TC-K3-ATM-006 | iteration json while os.replace fails          | previous iteration file intact, no temp left        |
| TC-K3-ATM-007 | failed run                                     | job.failed still written by write_job_errorlog_file |
| TC-K3-ATM-008 | interrupt (BaseException) during write         | temp removed, interrupt propagates                  |
| TC-K3-HYG-001 | re-run with fewer tiles                        | stale high-index iteration files removed            |
| TC-K3-HYG-002 | successful re-run after a failed run           | job.failed kept (v1 behaviour, documented)          |
| TC-K3-HYG-003 | re-run                                         | earlier run_report_* / events_* kept                |

BV table:

| TC-ID         | Boundary                                       | Expected                                            |
|---------------|------------------------------------------------|-----------------------------------------------------|
| TC-K3-HYG-BV1 | no logs/iterations directory yet               | iteration starts normally                           |
| TC-K3-HYG-BV2 | validate-only re-run                           | logs/iterations untouched (no tile is prepared)     |
| TC-K3-ATM-BV1 | empty text                                     | empty file, no temp left                            |
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.api.request import build_run_request
from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner import finalize as finalize_module
from rdetoolkit.runner.aggregator import RunAggregator
from rdetoolkit.runner.execute import ExecutionResult
from rdetoolkit.runner.finalize import atomic_write_text, finalize, write_run_report
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import IterationInfo, RdeConfig

_INVOICE: dict[str, Any] = {
    "datasetId": "k3-atomic",
    "basic": {"dateSubmitted": "2026-10-16", "dataOwnerId": "0" * 56, "dataName": "k3"},
}


def _report(run_id: str = "k3-atomic", *, status: str = "success", error: dict[str, Any] | None = None) -> RunReport:
    return RunReport(
        run_id=run_id,
        status=status,
        flow_id="tests.k3",
        mode="multidatatile",
        started_at="2026-10-16T00:00:00",
        duration_ms=1.0,
        config_digest="sha256:k3",
        iterations=[],
        warnings=[],
        error=error,
    )


def _leftovers(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir() if path.name.endswith(".tmp"))


def _failing_replace(*_: object) -> None:
    msg = "disk full"
    raise OSError(msg)


class TestAtomicWriteText:
    def test_fresh_path__tc_k3_atm_001(self, tmp_path: Path) -> None:
        """TC-K3-ATM-001: a new file appears with the full text."""
        # Given/When: writing to a path that does not exist
        target = tmp_path / "out.json"
        atomic_write_text(target, '{"a": 1}')
        # Then: content is complete and nothing else remains
        assert target.read_text(encoding="utf-8") == '{"a": 1}'
        assert sorted(path.name for path in tmp_path.iterdir()) == ["out.json"]

    def test_existing_file_replaced__tc_k3_atm_002(self, tmp_path: Path) -> None:
        """TC-K3-ATM-002: an existing file is replaced as a whole."""
        # Given: an existing file
        target = tmp_path / "out.json"
        target.write_text("old", encoding="utf-8")
        # When: writing new text
        atomic_write_text(target, "new")
        # Then: the new text replaced it
        assert target.read_text(encoding="utf-8") == "new"
        assert _leftovers(tmp_path) == []

    def test_empty_text__tc_k3_atm_bv1(self, tmp_path: Path) -> None:
        """TC-K3-ATM-BV1: empty content is a valid file."""
        # Given/When: writing an empty string
        target = tmp_path / "empty.json"
        atomic_write_text(target, "")
        # Then: an empty file exists
        assert target.read_bytes() == b""
        assert _leftovers(tmp_path) == []

    def test_replace_failure_keeps_previous__tc_k3_atm_003(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-K3-ATM-003: a failed rename never exposes a partial file."""
        # Given: an existing file and a failing os.replace
        target = tmp_path / "out.json"
        target.write_text("old", encoding="utf-8")
        monkeypatch.setattr(finalize_module.os, "replace", _failing_replace)
        # When/Then: the error propagates
        with pytest.raises(OSError, match="disk full"):
            atomic_write_text(target, "new")
        # And: the old file is intact and no temp is left
        assert target.read_text(encoding="utf-8") == "old"
        assert _leftovers(tmp_path) == []

    def test_write_failure_keeps_previous__tc_k3_atm_004(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-K3-ATM-004: a write interrupted half-way never reaches the target."""
        # Given: an existing file and a file handle that fails after half the text
        target = tmp_path / "out.json"
        target.write_text("old", encoding="utf-8")
        real_open = Path.open

        class _HalfWriter:
            def __init__(self, handle: Any) -> None:
                self._handle = handle

            def __enter__(self) -> Any:  # noqa: ANN401 - test double
                return self

            def __exit__(self, *exc: object) -> None:
                self._handle.close()

            def write(self, text: str) -> int:
                self._handle.write(text[: len(text) // 2])
                msg = "write interrupted"
                raise OSError(msg)

        def _open(self: Path, *args: Any, **kwargs: Any) -> Any:
            handle = real_open(self, *args, **kwargs)
            return _HalfWriter(handle) if self.name.endswith(".tmp") else handle

        monkeypatch.setattr(Path, "open", _open)
        # When/Then: the error propagates
        with pytest.raises(OSError, match="write interrupted"):
            atomic_write_text(target, "new content that is long")
        monkeypatch.undo()
        # And: the old content survived and the half-written temp is gone
        assert target.read_text(encoding="utf-8") == "old"
        assert _leftovers(tmp_path) == []

    def test_interrupt_removes_temp__tc_k3_atm_008(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-K3-ATM-008: a SIGTERM-style BaseException still cleans up."""
        # Given: an os.replace that is interrupted
        target = tmp_path / "out.json"

        def _interrupt(*_: object) -> None:
            raise KeyboardInterrupt

        monkeypatch.setattr(finalize_module.os, "replace", _interrupt)
        # When/Then: the interrupt propagates
        with pytest.raises(KeyboardInterrupt):
            atomic_write_text(target, "new")
        # And: neither the target nor a temp exists
        assert list(tmp_path.iterdir()) == []


class TestReportWritersAreAtomic:
    def test_run_report_keeps_previous_on_failure__tc_k3_atm_005(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-K3-ATM-005: write_run_report goes through the atomic writer."""
        # Given: a previously written report for the same run id
        write_run_report(_report(status="success"), data_root=tmp_path)
        logs = tmp_path / "logs"
        previous = (logs / "run_report_k3-atomic.json").read_text(encoding="utf-8")
        monkeypatch.setattr(finalize_module.os, "replace", _failing_replace)
        # When/Then: rewriting it fails at the rename
        with pytest.raises(OSError, match="disk full"):
            write_run_report(_report(status="failed"), data_root=tmp_path)
        # And: the previous report is intact and no temp remains
        assert (logs / "run_report_k3-atomic.json").read_text(encoding="utf-8") == previous
        assert _leftovers(logs) == []

    def test_iteration_file_keeps_previous_on_failure__tc_k3_atm_006(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-K3-ATM-006: iteration_{i}.json goes through the atomic writer."""
        # Given: an aggregator that already streamed tile 0
        aggregator = RunAggregator(
            run_id="k3",
            flow_id="tests.k3",
            mode="multidatatile",
            config_digest="sha256:k3",
            logs_dir=tmp_path / "logs",
        )
        aggregator.record(ExecutionResult(iteration_index=0, status="completed", call_records=(), outputs=()))
        iterations = tmp_path / "logs" / "iterations"
        previous = (iterations / "iteration_0.json").read_text(encoding="utf-8")
        monkeypatch.setattr(finalize_module.os, "replace", _failing_replace)
        # When/Then: re-recording tile 0 fails at the rename
        with pytest.raises(OSError, match="disk full"):
            aggregator.record(ExecutionResult(iteration_index=0, status="failed", call_records=(), outputs=()))
        # And: the earlier file is intact and no temp remains
        assert (iterations / "iteration_0.json").read_text(encoding="utf-8") == previous
        assert json.loads(previous)["status"] == "completed"
        assert _leftovers(iterations) == []

    def test_job_failed_stays_with_v1_writer__tc_k3_atm_007(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-K3-ATM-007: ``job.failed`` is v1's contract, not the atomic writer's."""
        # Given: spies on both writers
        v1_calls: list[tuple[int, str, str]] = []
        atomic_targets: list[str] = []
        real_atomic = finalize_module.atomic_write_text

        def _v1(code: int, message: str, *, filename: str) -> None:
            v1_calls.append((code, message, filename))

        def _atomic(path: Path, text: str) -> None:
            atomic_targets.append(path.name)
            real_atomic(path, text)

        monkeypatch.setattr(finalize_module, "write_job_errorlog_file", _v1)
        monkeypatch.setattr(finalize_module, "atomic_write_text", _atomic)
        # When: finalizing a failed run
        finalize(
            _report(status="failed", error={"code": 3001, "name": "NodeExecutionFailed", "message": "boom"}),
            RdeConfig(),
            data_root=tmp_path,
        )
        # Then: job.failed came from the v1 writer, the report from the atomic one
        assert v1_calls == [(3001, "boom", str((tmp_path / "job.failed").resolve()))]
        assert atomic_targets == ["run_report_k3-atomic.json"]


def _build_tree(root: Path, files: int) -> None:
    inputdata = root / "inputdata"
    if inputdata.exists():
        for path in sorted(inputdata.iterdir()):
            path.unlink()
    inputdata.mkdir(parents=True, exist_ok=True)
    for index in range(files):
        (inputdata / f"file_{index}.txt").write_text(f"data-{index}", encoding="utf-8")
    (root / "invoice").mkdir(exist_ok=True)
    (root / "invoice" / "invoice.json").write_text(json.dumps(_INVOICE), encoding="utf-8")
    (root / "tasksupport").mkdir(exist_ok=True)
    (root / "tasksupport" / "invoice.schema.json").write_text(json.dumps({"properties": {}}), encoding="utf-8")
    (root / "temp").mkdir(exist_ok=True)


@node(id="k3_hygiene_step")
def _hygiene_step(iteration: IterationInfo) -> int:
    return iteration.index


@flow
def _hygiene_flow(iteration: IterationInfo) -> None:
    _hygiene_step(iteration)


def _run(root: Path, run_id: str, **overrides: Any) -> RunReport:
    runner = Runner(
        root=root,
        inputdata_path=root / "inputdata",
        unpacked_dir_path=root / "temp",
        event_sink=MemoryEventSink(),
        run_id_factory=lambda: run_id,
    )
    return runner.run(_hygiene_flow, system={"extended_mode": "MultiDataTile"}, **overrides)


class TestRerunHygiene:
    def test_stale_high_indices_removed__tc_k3_hyg_001(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-K3-HYG-001: a 2-tile re-run leaves only iteration_0/1."""
        # Given: a first run with 4 tiles
        _build_tree(tmp_path, 4)
        monkeypatch.chdir(tmp_path)
        assert _run(tmp_path, "k3-hyg-a").status == "success"
        iterations = tmp_path / "logs" / "iterations"
        assert sorted(path.name for path in iterations.iterdir()) == [f"iteration_{i}.json" for i in range(4)]
        # When: re-running the same tree with 2 tiles
        _build_tree(tmp_path, 2)
        assert _run(tmp_path, "k3-hyg-b").status == "success"
        # Then: only this run's indices remain
        assert sorted(path.name for path in iterations.iterdir()) == ["iteration_0.json", "iteration_1.json"]

    def test_job_failed_survives_successful_rerun__tc_k3_hyg_002(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-K3-HYG-002: v1 never removed ``job.failed``; neither does K3."""
        # Given: a leftover job.failed from an earlier failed run
        _build_tree(tmp_path, 1)
        monkeypatch.chdir(tmp_path)
        (tmp_path / "job.failed").write_text("ErrorCode=3001\nErrorMessage=old\n", encoding="utf-8")
        # When: a successful re-run
        assert _run(tmp_path, "k3-hyg-002").status == "success"
        # Then: the marker is untouched
        assert (tmp_path / "job.failed").read_text(encoding="utf-8") == "ErrorCode=3001\nErrorMessage=old\n"

    def test_reports_and_events_accumulate__tc_k3_hyg_003(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-K3-HYG-003: run-scoped logs are kept across re-runs."""
        # Given: an earlier run's events file and report
        _build_tree(tmp_path, 1)
        monkeypatch.chdir(tmp_path)
        logs = tmp_path / "logs"
        logs.mkdir()
        (logs / "events_old.jsonl").write_text("{}\n", encoding="utf-8")
        _run(tmp_path, "k3-hyg-003a")
        # When: running again
        _run(tmp_path, "k3-hyg-003b")
        # Then: every run-scoped log is still there
        names = sorted(path.name for path in logs.iterdir() if path.is_file())
        assert names == ["events_old.jsonl", "run_report_k3-hyg-003a.json", "run_report_k3-hyg-003b.json"]

    def test_missing_iterations_dir__tc_k3_hyg_bv1(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-K3-HYG-BV1: nothing to clear on a first run."""
        # Given: a fresh tree without logs/
        _build_tree(tmp_path, 1)
        monkeypatch.chdir(tmp_path)
        assert not (tmp_path / "logs").exists()
        # When: running
        report = _run(tmp_path, "k3-hyg-bv1")
        # Then: the run succeeds and streams its one tile
        assert report.status == "success"
        assert (tmp_path / "logs" / "iterations" / "iteration_0.json").is_file()

    def test_validate_only_keeps_iterations__tc_k3_hyg_bv2(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-K3-HYG-BV2: a pre-flight check prepares no tile, so it clears nothing."""
        # Given: a completed 2-tile run
        _build_tree(tmp_path, 2)
        monkeypatch.chdir(tmp_path)
        _run(tmp_path, "k3-hyg-bv2a")
        iterations = tmp_path / "logs" / "iterations"
        before = sorted(path.name for path in iterations.iterdir())
        # When: validating only
        runner = Runner(
            root=tmp_path,
            inputdata_path=tmp_path / "inputdata",
            unpacked_dir_path=tmp_path / "temp",
            event_sink=MemoryEventSink(),
        )
        runner.run(
            build_run_request(
                flow=_hygiene_flow,
                custom_dataset_function=None,
                config={"system": {"extended_mode": "MultiDataTile"}},
                root=tmp_path,
                validate_only=True,
            ),
        )
        # Then: the previous run's iteration files are untouched
        assert sorted(path.name for path in iterations.iterdir()) == before
