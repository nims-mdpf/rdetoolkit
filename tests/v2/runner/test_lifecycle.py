"""Tests for rdetoolkit v2 Runner lifecycle (TC-RUN-001..007).

Written before implementation (TDD Red phase).
Target: make all tests pass in codex-worker Green phase.

Design authority: local/develop/v2/Design.md §6.1
  6-step lifecycle: (1) load_config → (2) resolve_mode → (3) pre_validate
                 → (4) iterate → (5) post_validate → (6) finalize
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# Target import — fails until implementation exists (expected in Red phase):
# from rdetoolkit.runner.lifecycle import Runner
# from rdetoolkit.report.run_report import RunReport


class TestRunnerLifecycle:
    """Tests for Runner.run() 6-step lifecycle (Design §6.1)."""

    def test_run_steps_called_in_config_mode_prevalidate_iterate_postvalidate_finalize_order(self) -> None:
        """TC-RUN-001: Steps 1->2->3->4->5->6 are called in Design §6.1 order."""
        from rdetoolkit.report.run_report import RunReport
        from rdetoolkit.runner.lifecycle import Runner

        runner = Runner()
        call_log: list[str] = []
        mock_report = MagicMock(spec=RunReport)

        with (
            patch.object(
                runner,
                "load_config",
                side_effect=lambda *a, **kw: call_log.append("load_config") or MagicMock(),
            ),
            patch.object(
                runner,
                "resolve_mode",
                side_effect=lambda *a, **kw: call_log.append("resolve_mode") or MagicMock(),
            ),
            patch.object(
                runner,
                "pre_validate",
                side_effect=lambda *a, **kw: call_log.append("pre_validate"),
            ),
            patch.object(
                runner,
                "iterate",
                side_effect=lambda *a, **kw: call_log.append("iterate") or mock_report,
            ),
            patch.object(
                runner,
                "post_validate",
                side_effect=lambda *a, **kw: call_log.append("post_validate"),
            ),
            patch.object(
                runner,
                "finalize",
                side_effect=lambda *a, **kw: call_log.append("finalize"),
            ),
        ):
            runner.run(lambda: None)

        assert call_log == [
            "load_config",
            "resolve_mode",
            "pre_validate",
            "iterate",
            "post_validate",
            "finalize",
        ], f"Step order wrong: {call_log}"

    def test_run_calls_iterate_and_iterate_can_be_replaced_with_stub(self) -> None:
        """TC-RUN-002: iterate step is injectable — a replaced stub is called during run()."""
        from rdetoolkit.report.run_report import RunReport
        from rdetoolkit.runner.lifecycle import Runner

        runner = Runner()
        stub_called: list[bool] = []
        mock_report = MagicMock(spec=RunReport)

        def iterate_stub(*args: object, **kwargs: object) -> MagicMock:
            stub_called.append(True)
            return mock_report

        with (
            patch.object(runner, "load_config", return_value=MagicMock()),
            patch.object(runner, "resolve_mode", return_value=MagicMock()),
            patch.object(runner, "pre_validate"),
            patch.object(runner, "iterate", side_effect=iterate_stub),
            patch.object(runner, "post_validate"),
            patch.object(runner, "finalize"),
        ):
            runner.run(lambda: None)

        assert stub_called, "iterate stub must be called exactly once during Runner.run()"

    def test_run_returns_runreport_instance(self) -> None:
        """TC-RUN-003: Runner.run() returns a RunReport instance."""
        from rdetoolkit.report.run_report import RunReport
        from rdetoolkit.runner.lifecycle import Runner

        runner = Runner()
        real_report = RunReport(
            run_id="test-run-id",
            status="success",
            flow_id="test.flow",
            mode="invoice",
            started_at="2026-01-01T00:00:00",
            duration_ms=0.0,
            config_digest="sha256:test",
            iterations=[],
            warnings=[],
        )

        with (
            patch.object(runner, "load_config", return_value=MagicMock()),
            patch.object(runner, "resolve_mode", return_value=MagicMock()),
            patch.object(runner, "pre_validate"),
            patch.object(runner, "iterate", return_value=real_report),
            patch.object(runner, "post_validate"),
            patch.object(runner, "finalize"),
        ):
            result = runner.run(lambda: None)

        assert isinstance(result, RunReport), f"Runner.run() must return a RunReport instance, got {type(result)}"

    def test_run_load_config_is_called_before_resolve_mode(self) -> None:
        """TC-RUN-004: load_config (step 1) is called before resolve_mode (step 2)."""
        from rdetoolkit.report.run_report import RunReport
        from rdetoolkit.runner.lifecycle import Runner

        runner = Runner()
        call_log: list[str] = []
        mock_report = MagicMock(spec=RunReport)

        with (
            patch.object(
                runner,
                "load_config",
                side_effect=lambda *a, **kw: call_log.append("load_config") or MagicMock(),
            ),
            patch.object(
                runner,
                "resolve_mode",
                side_effect=lambda *a, **kw: call_log.append("resolve_mode") or MagicMock(),
            ),
            patch.object(
                runner,
                "pre_validate",
                side_effect=lambda *a, **kw: call_log.append("pre_validate"),
            ),
            patch.object(
                runner,
                "iterate",
                side_effect=lambda *a, **kw: call_log.append("iterate") or mock_report,
            ),
            patch.object(
                runner,
                "post_validate",
                side_effect=lambda *a, **kw: call_log.append("post_validate"),
            ),
            patch.object(
                runner,
                "finalize",
                side_effect=lambda *a, **kw: call_log.append("finalize"),
            ),
        ):
            runner.run(lambda: None)

        config_pos = call_log.index("load_config")
        mode_pos = call_log.index("resolve_mode")
        assert config_pos < mode_pos, f"load_config must precede resolve_mode; positions: load_config={config_pos}, resolve_mode={mode_pos}"

    def test_run_finalize_is_the_last_step_called(self) -> None:
        """TC-RUN-005: finalize (step 6) is always the last step in the lifecycle."""
        from rdetoolkit.report.run_report import RunReport
        from rdetoolkit.runner.lifecycle import Runner

        runner = Runner()
        call_log: list[str] = []
        mock_report = MagicMock(spec=RunReport)

        with (
            patch.object(
                runner,
                "load_config",
                side_effect=lambda *a, **kw: call_log.append("load_config") or MagicMock(),
            ),
            patch.object(
                runner,
                "resolve_mode",
                side_effect=lambda *a, **kw: call_log.append("resolve_mode") or MagicMock(),
            ),
            patch.object(
                runner,
                "pre_validate",
                side_effect=lambda *a, **kw: call_log.append("pre_validate"),
            ),
            patch.object(
                runner,
                "iterate",
                side_effect=lambda *a, **kw: call_log.append("iterate") or mock_report,
            ),
            patch.object(
                runner,
                "post_validate",
                side_effect=lambda *a, **kw: call_log.append("post_validate"),
            ),
            patch.object(
                runner,
                "finalize",
                side_effect=lambda *a, **kw: call_log.append("finalize"),
            ),
        ):
            runner.run(lambda: None)

        assert call_log[-1] == "finalize", f"finalize must be the last step, but step order was: {call_log}"

    def test_run_pre_validate_is_called_after_resolve_mode_and_before_iterate(self) -> None:
        """TC-RUN-006: pre_validate (step 3) is after resolve_mode and before iterate."""
        from rdetoolkit.report.run_report import RunReport
        from rdetoolkit.runner.lifecycle import Runner

        runner = Runner()
        call_log: list[str] = []
        mock_report = MagicMock(spec=RunReport)

        with (
            patch.object(
                runner,
                "load_config",
                side_effect=lambda *a, **kw: call_log.append("load_config") or MagicMock(),
            ),
            patch.object(
                runner,
                "resolve_mode",
                side_effect=lambda *a, **kw: call_log.append("resolve_mode") or MagicMock(),
            ),
            patch.object(
                runner,
                "pre_validate",
                side_effect=lambda *a, **kw: call_log.append("pre_validate"),
            ),
            patch.object(
                runner,
                "iterate",
                side_effect=lambda *a, **kw: call_log.append("iterate") or mock_report,
            ),
            patch.object(
                runner,
                "post_validate",
                side_effect=lambda *a, **kw: call_log.append("post_validate"),
            ),
            patch.object(
                runner,
                "finalize",
                side_effect=lambda *a, **kw: call_log.append("finalize"),
            ),
        ):
            runner.run(lambda: None)

        mode_pos = call_log.index("resolve_mode")
        prevalidate_pos = call_log.index("pre_validate")
        iterate_pos = call_log.index("iterate")
        assert mode_pos < prevalidate_pos < iterate_pos, f"pre_validate must follow resolve_mode and precede iterate; positions: resolve_mode={mode_pos}, pre_validate={prevalidate_pos}, iterate={iterate_pos}"

    def test_run_post_validate_is_called_after_iterate_and_before_finalize(self) -> None:
        """TC-RUN-007: post_validate (step 5) is after iterate and before finalize."""
        from rdetoolkit.report.run_report import RunReport
        from rdetoolkit.runner.lifecycle import Runner

        runner = Runner()
        call_log: list[str] = []
        mock_report = MagicMock(spec=RunReport)

        with (
            patch.object(
                runner,
                "load_config",
                side_effect=lambda *a, **kw: call_log.append("load_config") or MagicMock(),
            ),
            patch.object(
                runner,
                "resolve_mode",
                side_effect=lambda *a, **kw: call_log.append("resolve_mode") or MagicMock(),
            ),
            patch.object(
                runner,
                "pre_validate",
                side_effect=lambda *a, **kw: call_log.append("pre_validate"),
            ),
            patch.object(
                runner,
                "iterate",
                side_effect=lambda *a, **kw: call_log.append("iterate") or mock_report,
            ),
            patch.object(
                runner,
                "post_validate",
                side_effect=lambda *a, **kw: call_log.append("post_validate"),
            ),
            patch.object(
                runner,
                "finalize",
                side_effect=lambda *a, **kw: call_log.append("finalize"),
            ),
        ):
            runner.run(lambda: None)

        iterate_pos = call_log.index("iterate")
        postvalidate_pos = call_log.index("post_validate")
        finalize_pos = call_log.index("finalize")
        assert iterate_pos < postvalidate_pos < finalize_pos, f"post_validate must follow iterate and precede finalize; positions: iterate={iterate_pos}, post_validate={postvalidate_pos}, finalize={finalize_pos}"


class TestRunnerIterateRealDispatch:
    """TC-RUN-008 (Session D1): Runner.iterate() replaces the Phase B stub with a
    real dispatch through runner/iterator.py + runner/execute.py.

    Unlike the tests above (which all patch.object(runner, "iterate", ...) and
    therefore never exercise the real method body), this test calls the
    unpatched Runner.iterate() directly. Design authority:
    local/develop/v2/tasks/session_d1.md ("D1.8" / "runner/lifecycle.py").
    """

    def test_iterate_real_multidatatile_dispatches_flow_once_per_tile(
        self,
        tmp_path,
        monkeypatch,
    ) -> None:
        """Real iterate() over a 2-file multidatatile input calls the flow twice,
        returns a RunReport, and creates the step-4a output directories relative
        to cwd (Path("data") convention, per session_d1.md's lifecycle.py note)."""
        from rdetoolkit.core.flow import flow
        from rdetoolkit.core.node import node
        from rdetoolkit.report.run_report import RunReport
        from rdetoolkit.runner.lifecycle import Runner
        from rdetoolkit.runner.mode_resolver import ModeKind
        from rdetoolkit.types import InputPaths, RdeConfig

        root = tmp_path / "run_root"
        (root / "inputdata").mkdir(parents=True)
        (root / "inputdata" / "a.txt").write_text("a")
        (root / "inputdata" / "b.txt").write_text("b")
        (root / "unpacked").mkdir()
        (root / "invoice").mkdir()
        (root / "tasksupport").mkdir()

        calls: list[Path] = []

        @node
        def _record(paths: InputPaths) -> None:
            calls.append(paths.inputdata)
            return None

        @flow
        def _tile_flow(paths: InputPaths) -> None:
            _record(paths)

        monkeypatch.chdir(root)
        runner = Runner(root=root, inputdata_path=root / "inputdata", unpacked_dir_path=root / "unpacked")
        runner.run_id = "test-real-iterate"

        report = runner.iterate(_tile_flow, ModeKind.multidatatile, RdeConfig())

        assert isinstance(report, RunReport)
        assert len(calls) == 2, "flow must be called once per tile (2 loose input files)"
        # UPDATED (Session I-REVIEW-A ruling #1): this root is alias-flat -- it
        # directly owns inputdata/invoice/tasksupport -- so it IS the data root.
        # The previous expectation (outputs under root/data while the invoice
        # side read root/invoice) pinned the split this session removes.
        assert (root / "structured").is_dir()
        assert (root / "divided" / "0001" / "structured").is_dir()
        assert not (root / "data").exists()


class TestLifecycleInitializationFailure:
    """Review-response lifecycle failure contract (Design §6.3, §8.2)."""

    def test_missing_invoice_finalizes_failed_report__tc_d2r_f3(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-D2R-F3: missing invariant invoice still finalizes and completes the run."""
        from rdetoolkit.core.flow import flow
        from rdetoolkit.report.events import MemoryEventSink
        from rdetoolkit.report.run_report import RunReport
        from rdetoolkit.runner.lifecycle import Runner

        # Given: invoice-mode input with the required invariant invoice absent
        monkeypatch.chdir(tmp_path)
        inputdata = tmp_path / "data" / "inputdata"
        inputdata.mkdir(parents=True)
        (inputdata / "sample.txt").write_text("sample", encoding="utf-8")
        (tmp_path / "data" / "tasksupport").mkdir()
        sink = MemoryEventSink()
        runner = Runner(
            root=tmp_path,
            inputdata_path=inputdata,
            unpacked_dir_path=tmp_path / "data" / "temp",
            event_sink=sink,
            run_id_factory=lambda: "missing-invoice",
        )

        @flow
        def _pipeline() -> None:
            return None

        # When: executing the complete lifecycle
        report = runner.run(_pipeline)

        # Then: the catalogued failure is finalized and observably completed
        assert isinstance(report, RunReport)
        assert report.status == "failed"
        assert report.error is not None
        assert report.error["code"] == 4003
        assert report.error["name"] == "RequiredArtifactMissing"
        assert report.error["remediation"]
        assert "Remediation:" in report.error["message"]
        assert (tmp_path / "data" / "job.failed").exists()
        assert sink.events[-1].name == "run.completed"
        assert sink.events[-1].payload == {"status": "failed"}


class TestIterationPreparationEvents:
    """Review-response event boundary includes per-tile invoice preparation."""

    def test_invoice_preparation_failure_emits_event_pair__tc_d2r_f6(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-D2R-F6: preparation failure emits started then completed(failed)."""
        from rdetoolkit.report.events import MemoryEventSink
        from rdetoolkit.runner.lifecycle import Runner
        from rdetoolkit.runner.mode_resolver import ModeKind
        from rdetoolkit.types import InputPaths, IterationInfo, RdeConfig

        # Given: one excelinvoice tile whose invoice preparation fails
        monkeypatch.chdir(tmp_path)
        sink = MemoryEventSink()
        sink.open("tc-d2r-f6")
        info = IterationInfo(index=0, total=1, mode="excelinvoice")
        rawfile = tmp_path / "row.xlsx"
        rawfile.write_text("placeholder", encoding="utf-8")
        paths = InputPaths(
            inputdata=tmp_path,
            invoice=tmp_path / "invoice",
            tasksupport=tmp_path / "tasksupport",
            raw=rawfile,
            rawfiles=(rawfile,),
        )
        out = SimpleNamespace(invoice=tmp_path / "output" / "invoice")
        runner = Runner(root=tmp_path, event_sink=sink)
        runner.run_id = "tc-d2r-f6"
        monkeypatch.setattr(
            "rdetoolkit.runner.planner.iterate_tiles",
            lambda *args, **kwargs: iter(((info, paths, out),)),
        )

        def _fail_preparation(*args: object, **kwargs: object) -> None:
            msg = "invoice preparation failed"
            raise ValueError(msg)

        monkeypatch.setattr("rdetoolkit.runner.planner._tile_invoice", _fail_preparation)

        # When: iterating the tile
        report = runner.iterate(lambda: None, ModeKind.excelinvoice, RdeConfig())

        # Then: the full tile boundary is observable despite pre-flow failure
        iteration_events = [event for event in sink.events if event.name.startswith("iteration.")]
        assert [event.name for event in iteration_events] == ["iteration.started", "iteration.completed"]
        assert iteration_events[1].payload == {"iteration_index": 0, "status": "failed"}
        assert report.iterations[0]["status"] == "failed"


class TestExcelinvoiceSourceBackup:
    """Review-response path guard for the immutable Excel source."""

    def test_run_invoice_source_copies_flat_invoice_without_workbook__tc_d2r_f9(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-D2R-F9: flat Excel mode backs up by root-relative paths."""
        from rdetoolkit.domain.invoice_service import InvoiceService
        from rdetoolkit.runner.planner import _run_invoice_source
        from rdetoolkit.runner.mode_resolver import ModeKind

        # Given: a flat source invoice without an Excel workbook
        inputdata = tmp_path / "inputdata"
        invoice_dir = tmp_path / "invoice"
        inputdata.mkdir()
        invoice_dir.mkdir()
        source = {"datasetId": "flat-source", "basic": {"dataName": "original"}}
        (invoice_dir / "invoice.json").write_text(json.dumps(source), encoding="utf-8")
        expected = tmp_path / "temp" / "invoice_org.json"

        def _unexpected_legacy_backup(*args: object, **kwargs: object) -> Path:
            message = "flat Excel backup must not use the cwd-dependent v1 helper"
            raise AssertionError(message)

        monkeypatch.setattr("rdetoolkit.invoicefile.backup_invoice_json_files", _unexpected_legacy_backup)
        backup_calls: list[tuple[ModeKind, Path, Path, tuple[Path, ...]]] = []
        original_backup = InvoiceService.backup

        def _backup_spy(
            self: InvoiceService,
            mode: ModeKind,
            *,
            data_root: Path,
            inputdata_path: Path,
            rawfiles: tuple[Path, ...] = (),
        ) -> Path:
            backup_calls.append((mode, data_root, inputdata_path, rawfiles))
            return original_backup(
                self,
                mode,
                data_root=data_root,
                inputdata_path=inputdata_path,
                rawfiles=rawfiles,
            )

        monkeypatch.setattr(InvoiceService, "backup", _backup_spy)

        # When: preparing the run-level Excel invoice source from another cwd
        caller = tmp_path / "caller"
        caller.mkdir()
        monkeypatch.chdir(caller)
        actual = _run_invoice_source(
            ModeKind.excelinvoice,
            data_root=tmp_path,
            inputdata_path=inputdata,
        )

        # Then: Runner creates and returns the explicit backup with exact content
        assert actual == expected
        assert json.loads(actual.read_text(encoding="utf-8")) == source
        assert backup_calls == [(ModeKind.excelinvoice, tmp_path, inputdata, ())]
