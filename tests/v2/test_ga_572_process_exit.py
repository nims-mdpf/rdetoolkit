"""GA572 EP/BV: production scripts share the public report exit contract."""

from __future__ import annotations

import json
import re
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, final

import pytest

from rdetoolkit import flow, workflows
from rdetoolkit.cli.run_cmd import determine_exit_code
from rdetoolkit.errors import RdeConfigError
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.templates import ProcessingTemplate, slot
from rdetoolkit.types import IterationInfo
from tests.v2.report.test_run_report import _make_report
from tests.v2.runner.test_event_log_robustness_k4 import _build_tree


def _script(tmp_path: Path, outcome: str, body: str, *, plain_error: bool = False, policy: str = "continue") -> subprocess.CompletedProcess[str]:
    _build_tree(tmp_path / "data")
    (tmp_path / "data/inputdata/file_1.txt").write_text("second", encoding="utf-8")
    if outcome == "empty":
        for path in (tmp_path / "data/inputdata").iterdir():
            path.unlink()
    config = {"system": {"extended_mode": "MultiDataTile", "feature_description": False}, "execution": {"on_iteration_error": policy}}
    import yaml
    (tmp_path / "rdeconfig.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    error = "ValueError('boom')" if plain_error else "StructuredError('boom', 7)"
    (tmp_path / "processing.py").write_text(
        "from rdetoolkit import flow\nfrom rdetoolkit.exceptions import StructuredError\n"
        "from rdetoolkit.nodes import save_text\nfrom rdetoolkit.types import IterationInfo, OutputContext\n"
        "@flow\ndef pipeline(iteration: IterationInfo, out: OutputContext) -> None:\n"
        f"    if {outcome!r} == 'failed' or ({outcome!r} == 'partial' and iteration.index == 1):\n"
        f"        raise {error}\n"
        '    save_text("processed", out, "result.txt")\n', encoding="utf-8",
    )
    main = tmp_path / "main.py"
    main.write_text(body, encoding="utf-8")
    return subprocess.run([sys.executable, str(main)], cwd=tmp_path, capture_output=True, text=True, timeout=60, check=False)


@pytest.mark.parametrize("outcome, expected", [("success", 0), ("failed", 1), ("partial", 2), ("empty", 0)])
@pytest.mark.parametrize("plain_error", [False, True])
def test_production_main_exit_after_persistence__ga572_ep_1_neg_1_2_bv_1(tmp_path: Path, outcome: str, expected: int, plain_error: bool) -> None:
    """GA572-EP-1/NEG-1/NEG-2/BV-1: real python main.py reports its run outcome."""
    # Given: the production entry opts into failure exits
    body = "from rdetoolkit import workflows\nfrom processing import pipeline\nreport = workflows.run(flow=pipeline, exit_on_failure=True)\nprint('returned:' + report.status)\n"
    # When: a separate Python process completes real Runner execution
    result = _script(tmp_path, outcome, body, plain_error=plain_error)
    # Then: process status and already-persisted report agree, preserving user codes
    assert result.returncode == expected, result.stderr
    report = json.loads(next((tmp_path / "data/logs").glob("run_report_*.json")).read_text())
    assert report["status"] == ("success" if outcome == "empty" else outcome)
    if expected:
        assert "returned:" not in result.stdout
        failures = [iteration["error"] for iteration in report["iterations"] if iteration["status"] == "failed"]
        assert failures and all(error["code"] == (3001 if plain_error else 7) for error in failures)
    if outcome == "failed":
        marker = (tmp_path / "data/job.failed").read_text()
        assert marker.startswith(f"ErrorCode={3001 if plain_error else 7}\n")
        assert "boom" in marker
    elif not expected:
        assert "returned:success" in result.stdout
        assert not (tmp_path / "data/job.failed").exists()
    if outcome == "partial":
        assert report["error"] is None
        assert not (tmp_path / "data/job.failed").exists()
        assert (tmp_path / "data/structured/result.txt").read_text() == "processed"
    if outcome == "empty":
        assert len(report["iterations"]) == 1
        assert report["iterations"][0]["status"] == "completed"


def test_fail_fast_exits_without_second_tile__ga572_bv_1(tmp_path: Path) -> None:
    """GA572-BV-1: fail-fast remains a one-tile failure with process exit 1."""
    # Given: two inputs whose flow fails immediately
    body = "from rdetoolkit import workflows\nfrom processing import pipeline\nworkflows.run(flow=pipeline, exit_on_failure=True)\n"
    # When: running with the existing fail-fast policy
    result = _script(tmp_path, "failed", body, policy="fail_fast")
    # Then: finalization happens before exit and the remaining tile is never run
    assert result.returncode == 1, result.stderr
    report = json.loads(next((tmp_path / "data/logs").glob("run_report_*.json")).read_text())
    assert len(report["iterations"]) == 1
    assert report["error"]["code"] == 7


@pytest.mark.parametrize("status, expected", [("success", 0), ("failed", 1), ("partial", 2), ("future-status", 1)])
def test_public_exit_code_without_schema_change__ga572_bv_2(status: str, expected: int) -> None:
    """GA572-BV-2: a derived property agrees with CLI and stays outside schema 2."""
    # Given: a report of any known or future status
    report = _make_report(status=status)
    # When: accessing the public exit value before and after serialization
    restored = RunReport.from_json(report.to_json())
    # Then: consumers share the mapping without adding a JSON field
    assert report.exit_code == restored.exit_code == determine_exit_code(report) == expected
    assert "exit_code" not in report.to_dict()
    assert report.schema_version == restored.schema_version == "2"


@pytest.mark.parametrize("options", [{}, {"exit_on_failure": False}])
def test_programmatic_failed_report_stays_available__ga572_ep_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, options: dict[str, Any]) -> None:
    """GA572-EP-2: the default library call keeps returning its failed RunReport."""
    # Given: an ordinary programmatic flow failure
    _build_tree(tmp_path / "data")
    monkeypatch.chdir(tmp_path)

    @flow
    def pipeline() -> None:
        raise StructuredError("boom", 7)

    # When: running without the opt-in process behavior
    report = workflows.run(flow=pipeline, **options)
    # Then: report inspection and error propagation remain available
    assert report.status == "failed"
    assert report.error is not None and report.error["code"] == 7
    assert report.exit_code == 1


@pytest.mark.parametrize("exception", [SystemExit, KeyboardInterrupt])
def test_control_exceptions_remain_original__ga572_neg_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exception: type[BaseException]) -> None:
    """GA572-NEG-3: opting in cannot catch or remap process-control exceptions."""
    # Given: a flow that raises a specific control exception
    _build_tree(tmp_path / "data")
    monkeypatch.chdir(tmp_path)
    original = exception(23)

    @flow
    def pipeline() -> None:
        raise original

    # When / Then: executing through the public boundary preserves its identity
    with pytest.raises(exception) as raised:
        workflows.run(flow=pipeline, exit_on_failure=True)
    assert raised.value is original
    assert not (tmp_path / "data/job.failed").exists()


def test_sigterm_finalizes_before_exit__ga572_neg_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA572-NEG-3: SIGTERM keeps 3004 and becomes process exit 1 after finalization."""
    # Given: an active flow receiving the Runner-handled termination signal
    _build_tree(tmp_path / "data")
    monkeypatch.chdir(tmp_path)

    @flow
    def pipeline() -> None:
        signal.raise_signal(signal.SIGTERM)

    previous = signal.signal(signal.SIGTERM, lambda _signum, _frame: None)
    try:
        # When: execution is opted into process failure signaling
        with pytest.raises(SystemExit) as raised:
            workflows.run(flow=pipeline, exit_on_failure=True)
    finally:
        signal.signal(signal.SIGTERM, previous)
    # Then: the persisted interruption stays distinguishable from a user failure
    assert raised.value.code == 1
    assert (tmp_path / "data/job.failed").read_text().startswith("ErrorCode=3004\n")


@pytest.mark.parametrize("callback", [None, lambda src, out: None])
def test_exit_mode_requires_flow__ga572_neg_4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, callback: Any) -> None:
    """GA572-NEG-4: the v2 exit option cannot silently alter the legacy contract."""
    # Given: a legacy or callback-free entry and no project artifacts
    monkeypatch.chdir(tmp_path)
    # When / Then: invalid entry options fail with the existing usage code
    with pytest.raises(RdeConfigError) as raised:
        workflows.run(custom_dataset_function=callback, exit_on_failure=True)
    assert raised.value.code == 1001
    assert "exit_on_failure" in str(raised.value)
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize("conflict", [False, True])
def test_existing_argument_errors_survive__ga572_neg_5(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, conflict: bool) -> None:
    """GA572-NEG-5: exit policy cannot swallow entry or configuration errors."""
    # Given: a complete tree but an invalid call or config
    _build_tree(tmp_path / "data")
    monkeypatch.chdir(tmp_path)

    @flow
    def pipeline() -> None:
        pass

    options = {"custom_dataset_function": lambda src, out: None} if conflict else {"config": {"invalid": True}}
    # When / Then: the original typed configuration error propagates unchanged
    if conflict:
        with pytest.raises(RdeConfigError) as raised:
            workflows.run(flow=pipeline, exit_on_failure=True, **options)
        assert raised.value.code == 1001
    else:
        with pytest.raises(SystemExit) as exited:
            workflows.run(flow=pipeline, exit_on_failure=True, **options)
        assert exited.value.code == 1
        report = json.loads(next((tmp_path / "data/logs").glob("run_report_*.json")).read_text())
        assert report["error"]["code"] == 1002
        assert (tmp_path / "data/job.failed").read_text().startswith("ErrorCode=1002\n")


def test_template_class_uses_the_exit_policy__ga572_neg_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA572-NEG-1: concrete ProcessingTemplate entries share the failure exit."""
    # Given: a failing concrete template and a valid input
    _build_tree(tmp_path / "data")
    monkeypatch.chdir(tmp_path)

    class Skeleton(ProcessingTemplate):
        @slot
        def process(self, index: int) -> None: ...

        @final
        def __flow__(self, iteration: IterationInfo) -> None:
            self.process(iteration.index)

    class Pipeline(Skeleton):
        def process(self, index: int) -> None:
            raise StructuredError("template failure", 7)

    # When: selecting the template through the same public API
    with pytest.raises(SystemExit) as raised:
        workflows.run(flow=Pipeline, exit_on_failure=True)
    # Then: the original code is persisted before the process exit
    assert raised.value.code == 1
    assert (tmp_path / "data/job.failed").read_text().startswith("ErrorCode=7\n")


@pytest.mark.parametrize("language", ["en", "ja"])
@pytest.mark.parametrize("outcome, expected", [("success", 0), ("failed", 1), ("partial", 2)])
def test_migration_main_example_executes__ga572_doc(tmp_path: Path, language: str, outcome: str, expected: int) -> None:
    """GA572-DOC: the exact migration example yields the promised process result."""
    # Given: the tagged production main example in either migration guide
    suffix = ".en" if language == "en" else ""
    guide = (Path(__file__).resolve().parents[2] / f"docs/migration_v1_to_v2{suffix}.md").read_text()
    match = re.search(r"<!-- test: ga572-main -->\s*```python\n(.*?)```", guide, re.DOTALL)
    assert match is not None
    # When: executing the documentation verbatim with a real public flow
    result = _script(tmp_path, outcome, match.group(1))
    # Then: the script follows the production exit contract
    assert result.returncode == expected, result.stderr
