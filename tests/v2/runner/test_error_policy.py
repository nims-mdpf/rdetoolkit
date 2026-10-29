"""Tests for rdetoolkit v2 Runner on_iteration_error policy (Session D2, TC-POLICY-001..005).

Written before implementation (TDD Red phase).
Target: make all tests pass in codex-worker Green phase.

Design authority: local/develop/v2/Design.md v2.1 §7.2 (error policy: "never
create an implicit partial success").
Session authority: local/develop/v2/tasks/session_d2.md Conflict #6 — policy
branching (continue/fail_fast) lives in the ``Runner.iterate()`` loop (or a
helper it calls), never inside ``runner/execute.py``'s ``run_tile``, because
D1's ``run_tile`` deliberately propagates tile exceptions without catching
them.

Pinned contract (Design §7.2 + session_d2.md D2.1/D2.2):
    on_iteration_error="continue" (default): failed tiles are skipped, the
        loop continues to the next tile.
        - all tiles succeed  -> RunReport.status == "success"
        - some tiles fail    -> RunReport.status == "partial", with the
          failed-tile count surfaced in both RunReport's leading summary
          (warnings) and on stderr.
        - all tiles fail     -> RunReport.status == "failed"
    on_iteration_error="fail_fast": the loop stops at the first failure;
        later tiles' run_tile is never invoked -> RunReport.status == "failed".

Note: TC-POLICY-001 (all-success) and TC-POLICY-005's no-op case are
expected to already pass today (Runner.iterate() already returns
status="success" unconditionally when nothing raises) -- they are anchors,
not RED. TC-POLICY-002/003/004 require an unhandled ValueError to propagate
out of the real flow today (no try/except exists yet in the loop), so they
fail with an uncaught exception rather than a clean assertion failure; that
is the expected and correct Red-phase failure mode for this session.
"""
from __future__ import annotations

import json
from pathlib import Path

from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import IterationInfo, RdeConfig


def _build_multidatatile_root(tmp_path: Path, file_count: int) -> Path:
    """Build a minimal v2 Runner root with ``file_count`` loose input files.

    Each loose file becomes its own multidatatile tile (D1 iterator
    behavior, verified by ``test_lifecycle.py``'s real-dispatch test).
    """
    root = tmp_path / "run_root"
    (root / "inputdata").mkdir(parents=True)
    for i in range(file_count):
        (root / "inputdata" / f"file_{i}.txt").write_text(f"data-{i}", encoding="utf-8")
    (root / "unpacked").mkdir()
    (root / "invoice").mkdir()
    (root / "tasksupport").mkdir()
    _write_validation_fixture(root)
    return root


def _write_validation_fixture(root: Path) -> None:
    (root / "invoice").mkdir(exist_ok=True)
    (root / "tasksupport").mkdir(exist_ok=True)
    (root / "invoice" / "invoice.json").write_text(
        json.dumps(
            {
                "datasetId": "policy-fixture",
                "basic": {
                    "dateSubmitted": "2026-07-20",
                    "dataOwnerId": "0" * 56,
                    "dataName": "policy-fixture",
                },
            },
        ),
        encoding="utf-8",
    )
    (root / "tasksupport" / "invoice.schema.json").write_text(
        json.dumps({"properties": {}}),
        encoding="utf-8",
    )


def _make_runner(root: Path) -> Runner:
    return Runner(root=root, inputdata_path=root / "inputdata", unpacked_dir_path=root / "unpacked")


class TestOnIterationErrorContinueAllSuccess:
    """TC-POLICY-001: continue policy, all tiles succeed -> status='success'."""

    def test_all_success_yields_status_success__tc_policy_001(self, tmp_path: Path, monkeypatch) -> None:
        """TC-POLICY-001 (anchor): every tile succeeding must yield status='success'."""
        root = _build_multidatatile_root(tmp_path, 3)
        monkeypatch.chdir(root)

        calls: list[int] = []

        @node
        def _record(iteration: IterationInfo) -> None:
            calls.append(iteration.index)

        @flow
        def _ok_flow(iteration: IterationInfo) -> None:
            _record(iteration)

        runner = _make_runner(root)
        runner.run_id = "test-policy-001"
        config = RdeConfig(execution={"on_iteration_error": "continue"})

        report = runner.iterate(_ok_flow, ModeKind.multidatatile, config)

        assert report.status == "success"
        assert calls == [0, 1, 2]

    def test_default_policy_is_continue__tc_policy_001b(self) -> None:
        """TC-POLICY-001b (anchor, regression guard): default on_iteration_error is 'continue'."""
        assert RdeConfig().execution.on_iteration_error == "continue"


class TestOnIterationErrorContinuePartialAndAllFailed:
    """TC-POLICY-002/003: continue policy under partial and total failure."""

    def test_some_failed_yields_status_partial_with_failed_count_surfaced__tc_policy_002(
        self,
        tmp_path: Path,
        monkeypatch,
        capsys,
    ) -> None:
        """TC-POLICY-002: 1 of 3 tiles fails -> status='partial'; the loop
        must not skip the remaining tiles, and the failed-tile count must be
        surfaced in both RunReport's leading summary (warnings) and stderr
        (Design §7.2 'never create an implicit partial success').
        """
        root = _build_multidatatile_root(tmp_path, 3)
        monkeypatch.chdir(root)

        calls: list[int] = []

        @node
        def _maybe_fail(iteration: IterationInfo) -> None:
            calls.append(iteration.index)
            if iteration.index == 1:
                msg = "tile 1 boom"
                raise ValueError(msg)

        @flow
        def _flaky_flow(iteration: IterationInfo) -> None:
            _maybe_fail(iteration)

        runner = _make_runner(root)
        runner.run_id = "test-policy-002"
        config = RdeConfig(execution={"on_iteration_error": "continue"})

        report = runner.iterate(_flaky_flow, ModeKind.multidatatile, config)
        captured = capsys.readouterr()

        assert report.status == "partial"
        assert calls == [0, 1, 2], "continue policy must not skip tiles after a failure"
        assert len(report.iterations) == 3
        assert report.iterations[0]["status"] == "completed"
        assert report.iterations[1]["status"] == "failed"
        assert report.iterations[2]["status"] == "completed"

        summary_text = " ".join(str(w) for w in report.warnings)
        assert "1" in summary_text and "fail" in summary_text.lower(), (
            "failed-tile count must be surfaced in RunReport's leading summary (warnings)"
        )
        assert "1" in captured.err and "fail" in captured.err.lower(), (
            "failed-tile count must also be surfaced on stderr"
        )

    def test_all_failed_yields_status_failed__tc_policy_003(self, tmp_path: Path, monkeypatch) -> None:
        """TC-POLICY-003: every tile failing -> status='failed'."""
        root = _build_multidatatile_root(tmp_path, 2)
        monkeypatch.chdir(root)

        @node
        def _always_fail(iteration: IterationInfo) -> None:
            msg = f"tile {iteration.index} boom"
            raise ValueError(msg)

        @flow
        def _all_fail_flow(iteration: IterationInfo) -> None:
            _always_fail(iteration)

        runner = _make_runner(root)
        runner.run_id = "test-policy-003"
        config = RdeConfig(execution={"on_iteration_error": "continue"})

        report = runner.iterate(_all_fail_flow, ModeKind.multidatatile, config)

        assert report.status == "failed"
        assert len(report.iterations) == 2
        assert all(entry["status"] == "failed" for entry in report.iterations)


class TestOnIterationErrorFailFast:
    """TC-POLICY-004: fail_fast stops at the first failure."""

    def test_fail_fast_stops_at_first_failure__tc_policy_004(self, tmp_path: Path, monkeypatch) -> None:
        """TC-POLICY-004: fail_fast must stop immediately -> status='failed';
        run_tile must never be invoked for tiles after the first failure.
        """
        root = _build_multidatatile_root(tmp_path, 3)
        monkeypatch.chdir(root)

        calls: list[int] = []

        @node
        def _fail_at_zero(iteration: IterationInfo) -> None:
            calls.append(iteration.index)
            if iteration.index == 0:
                msg = "tile 0 boom"
                raise ValueError(msg)

        @flow
        def _flaky_flow(iteration: IterationInfo) -> None:
            _fail_at_zero(iteration)

        runner = _make_runner(root)
        runner.run_id = "test-policy-004"
        config = RdeConfig(execution={"on_iteration_error": "fail_fast"})

        report = runner.iterate(_flaky_flow, ModeKind.multidatatile, config)

        assert report.status == "failed"
        assert calls == [0], "fail_fast must stop before calling run_tile for tiles 1/2"
        assert len(report.iterations) == 1
        assert report.iterations[0]["status"] == "failed"


class TestStatusStringContract:
    """TC-POLICY-005: RunReport.status string values are fixed ahead of Phase E's exit-code mapping."""

    def test_status_is_one_of_success_partial_failed__tc_policy_005(self, tmp_path: Path, monkeypatch) -> None:
        """TC-POLICY-005 (anchor): only 'success' | 'partial' | 'failed' are valid RunReport.status values."""
        root = _build_multidatatile_root(tmp_path, 1)
        monkeypatch.chdir(root)

        @flow
        def _noop_flow(iteration: IterationInfo) -> None:
            return None

        runner = _make_runner(root)
        runner.run_id = "test-policy-005"
        config = RdeConfig(execution={"on_iteration_error": "continue"})

        report = runner.iterate(_noop_flow, ModeKind.multidatatile, config)

        assert report.status in {"success", "partial", "failed"}


class TestFailFastNonZeroIndexRegression:
    """Audit follow-up (session_d2.md AUDIT POSTSCRIPT): fail_fast must classify
    the run as "failed" even when tiles completed before the failing one —
    "partial" exists only under the continue policy (Design §7.2, no implicit
    partial success). The original TC-POLICY-004 failed only at tile index 0,
    which masked this because completed_count==0 coincidentally yields "failed".
    """

    def test_fail_fast_failure_at_nonzero_index_is_failed_and_writes_job_failed(
        self, tmp_path, monkeypatch
    ) -> None:
        import pytest

        from rdetoolkit.runner.lifecycle import Runner
        from rdetoolkit.types import RdeConfig

        monkeypatch.chdir(tmp_path)
        inputdata = tmp_path / "data" / "inputdata"
        inputdata.mkdir(parents=True)
        (inputdata / "a.txt").write_text("a", encoding="utf-8")
        (inputdata / "b.txt").write_text("b", encoding="utf-8")
        (inputdata / "c.txt").write_text("c", encoding="utf-8")
        _write_validation_fixture(tmp_path / "data")

        calls: list[int] = []

        def flaky_flow() -> None:
            calls.append(len(calls))
            if len(calls) == 2:  # second tile (index 1) fails
                msg = "boom at tile 1"
                raise ValueError(msg)

        config = RdeConfig(
            system={"extended_mode": "MultiDataTile"},
            execution={"on_iteration_error": "fail_fast"},
        )
        runner = Runner(
            root=tmp_path / "data",
            inputdata_path=inputdata,
            unpacked_dir_path=tmp_path / "data" / "temp",
        )
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(runner, "load_config", lambda overrides=None: config)

            report = runner.run(flaky_flow)

        assert len(calls) == 2, "fail_fast must stop after the first failure"
        assert report.status == "failed", (
            f"fail_fast with a prior completed tile must be 'failed', got {report.status!r}"
        )
        job_failed = tmp_path / "data" / "job.failed"
        assert job_failed.exists(), "finalize must write job.failed for failed runs"
        assert job_failed.read_text(encoding="utf-8").startswith("ErrorCode=")
