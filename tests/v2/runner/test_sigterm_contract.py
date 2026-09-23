"""SIGTERM lifecycle contract tests (TC-E0-001..003).

Design authority: Design §6.3 and §7.2; Phase E Session E0.

EP table:
    TC-E0-001 | SIGTERM during a tile | interrupted run | failed artifacts use 3004
    TC-E0-002 | ordinary completed run | installed handler | original handler restored

BV table:
    TC-E0-003 | run outside main thread | signal API unavailable | run remains usable
    TC-E-REVIEW-F1-001 | SIGTERM during run-id creation | handler not active yet | run succeeds
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

from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import RdeConfig


def _successful_report() -> RunReport:
    return RunReport(
        run_id="unit-run",
        status="success",
        flow_id="tests.stub_flow",
        mode="multidatatile",
        started_at="2026-07-11T00:00:00",
        duration_ms=1.0,
        config_digest="sha256:test",
        iterations=[],
        warnings=[],
        error=None,
    )


def _runner_without_io(tmp_path: Path) -> Runner:
    _write_validation_fixture(tmp_path)
    runner = Runner(root=tmp_path, event_sink=MemoryEventSink(), run_id_factory=lambda: "unit-run")
    runner.load_config = lambda overrides=None: RdeConfig()  # type: ignore[method-assign]
    runner.resolve_mode = lambda config: ModeKind.multidatatile  # type: ignore[method-assign]
    runner.iterate = lambda flow_fn, mode, config: _successful_report()  # type: ignore[method-assign]
    runner.finalize = lambda report, config: None  # type: ignore[method-assign]
    return runner


def _write_validation_fixture(root: Path) -> None:
    (root / "invoice").mkdir(parents=True, exist_ok=True)
    (root / "tasksupport").mkdir(parents=True, exist_ok=True)
    (root / "invoice" / "invoice.json").write_text(
        json.dumps(
            {
                "datasetId": "sigterm-fixture",
                "basic": {
                    "dateSubmitted": "2026-07-20",
                    "dataOwnerId": "0" * 56,
                    "dataName": "sigterm-fixture",
                },
            },
        ),
        encoding="utf-8",
    )
    (root / "tasksupport" / "invoice.schema.json").write_text(
        json.dumps({"properties": {}}),
        encoding="utf-8",
    )


class TestSigtermIntegration:
    def test_sigterm_finalizes_failed_run__tc_e0_001(self, tmp_path: Path) -> None:
        """TC-E0-001: SIGTERM produces the complete catalogued failure contract."""
        # Given: a subprocess running a multi-tile flow whose second tile sleeps
        script = textwrap.dedent(
            """
            import time
            import sysconfig
            import json
            from pathlib import Path

            import rdetoolkit
            rdetoolkit.__path__.append(str(Path(sysconfig.get_paths()["purelib"]) / "rdetoolkit"))

            from rdetoolkit import flow
            from rdetoolkit.report.events import FileEventSink
            from rdetoolkit.runner.lifecycle import Runner
            from rdetoolkit.runner.mode_resolver import ModeKind
            from rdetoolkit.types import InputPaths

            root = Path.cwd()
            inputdata = root / "inputdata"
            inputdata.mkdir()
            (inputdata / "a.txt").write_text("a", encoding="utf-8")
            (inputdata / "b.txt").write_text("b", encoding="utf-8")
            (root / "unpacked").mkdir()
            (root / "invoice").mkdir()
            (root / "tasksupport").mkdir()
            (root / "invoice" / "invoice.json").write_text(json.dumps({
                "datasetId": "sigterm-fixture",
                "basic": {
                    "dateSubmitted": "2026-07-20",
                    "dataOwnerId": "0" * 56,
                    "dataName": "sigterm-fixture",
                },
            }), encoding="utf-8")
            (root / "tasksupport" / "invoice.schema.json").write_text(
                json.dumps({"properties": {}}),
                encoding="utf-8",
            )
            sentinel = root / "tile-1-complete"

            class MultiTileRunner(Runner):
                def resolve_mode(self, config):
                    return ModeKind.multidatatile

            @flow
            def pipeline(paths: InputPaths) -> None:
                if not sentinel.exists():
                    sentinel.write_text("complete", encoding="utf-8")
                    return
                time.sleep(30)

            sink = FileEventSink(root / "logs")
            runner = MultiTileRunner(
                root=root,
                inputdata_path=inputdata,
                unpacked_dir_path=root / "unpacked",
                event_sink=sink,
                run_id_factory=lambda: "sigterm-run",
            )
            runner.run(pipeline)
            """,
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parents[3] / "src")
        proc = subprocess.Popen([sys.executable, "-c", script], cwd=tmp_path, env=env)
        sentinel = tmp_path / "tile-1-complete"
        deadline = time.monotonic() + 15
        while not sentinel.exists() and proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert sentinel.exists(), "child did not complete its first tile"

        # When: the parent sends SIGTERM while the second tile is executing
        time.sleep(0.25)
        proc.send_signal(signal.SIGTERM)
        return_code = proc.wait(timeout=10)

        # Then: shutdown is orderly and all persisted failure artifacts agree
        assert return_code == 0
        # The child root is alias-flat, so it IS the data root (ruling #1).
        report_path = tmp_path / "logs" / "run_report_sigterm-run.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["status"] == "failed"
        assert report["error"]["code"] == 3004
        assert report["error"]["name"] == "RunInterrupted"
        assert "Remediation:" in report["error"]["message"]
        job_failed = (tmp_path / "job.failed").read_text(encoding="utf-8")
        assert "ErrorCode=3004\n" in job_failed
        events_path = tmp_path / "logs" / "events_sigterm-run.jsonl"
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
        assert any(
            event.get("name") == "run.completed" and event.get("payload") == {"status": "failed"}
            for event in events
        )


class TestSigtermHandlerScope:
    def test_sigterm_before_failure_state_exists_uses_previous_handler__tc_e_review_f1_001(
        self,
        tmp_path: Path,
    ) -> None:
        """TC-E-REVIEW-F1-001: startup completes before Runner installs its handler."""
        # Given: a harmless previous handler and a run-id factory that delivers SIGTERM
        original = signal.getsignal(signal.SIGTERM)
        received: list[int] = []
        signal.signal(signal.SIGTERM, lambda signum, frame: received.append(signum))
        runner = _runner_without_io(tmp_path)

        def interrupting_factory() -> str:
            os.kill(os.getpid(), signal.SIGTERM)
            return "unit-run"

        runner._run_id_factory = interrupting_factory
        try:
            # When: the signal arrives while the run id is being created
            report = runner.run(lambda: None)
        finally:
            signal.signal(signal.SIGTERM, original)

        # Then: the previous handler receives it and the ordinary run completes
        assert received == [signal.SIGTERM]
        assert report.status == "success"

    def test_run_restores_previous_handler__tc_e0_002(self, tmp_path: Path) -> None:
        """TC-E0-002: Runner.run restores the process SIGTERM handler."""
        # Given: the process SIGTERM handler before an ordinary run
        original = signal.getsignal(signal.SIGTERM)
        runner = _runner_without_io(tmp_path)

        # When: the run completes
        runner.run(lambda: None)

        # Then: the exact original handler is restored
        assert signal.getsignal(signal.SIGTERM) is original

    def test_run_outside_main_thread_skips_handler__tc_e0_003(self, tmp_path: Path) -> None:
        """TC-E0-003: signal installation unavailability does not fail a run."""
        # Given: a Runner invoked from a non-main Python thread
        runner = _runner_without_io(tmp_path)
        reports: list[RunReport] = []
        failures: list[BaseException] = []

        def invoke() -> None:
            try:
                reports.append(runner.run(lambda: None))
            except BaseException as exc:  # noqa: BLE001
                failures.append(exc)

        thread = threading.Thread(target=invoke)

        # When: the run executes to completion outside the main thread
        thread.start()
        thread.join(timeout=5)

        # Then: signal.signal's ValueError is skipped and normal behavior remains
        assert not thread.is_alive()
        assert failures == []
        assert [report.status for report in reports] == ["success"]
