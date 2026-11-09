"""GA577 EP/BV: flow error options apply only at the Runner boundary."""

from __future__ import annotations

import signal
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from rdetoolkit import flow, node, workflows
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.cli.app import app
from rdetoolkit.types import IterationInfo
from tests.v2.runner.test_event_log_robustness_k4 import _build_tree


@node
def _fail_node() -> None:
    raise ValueError("boom")


@pytest.mark.parametrize("failure", ["plain", "node", "structured"])
@pytest.mark.parametrize("options, code, message", [
    ({"error_code": 7, "error_message": "Cannot process input"}, 7, "Cannot process input"),
    ({"error_code": 7}, 7, "boom"),
    ({"error_message": "Cannot process input"}, 3001, "Cannot process input"),
])
def test_runner_applies_flow_error_policy__ga577_neg_1_bv_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str, options: dict[str, Any], code: int, message: str) -> None:
    """GA577-NEG-1/BV-1: explicit code/message replace any body exception."""
    # Given: a real Runner dataset and an opted-in flow failure
    _build_tree(tmp_path / "data")
    monkeypatch.chdir(tmp_path)

    @flow(**options)
    def pipeline() -> None:
        if failure == "node":
            _fail_node()
        if failure == "structured":
            raise StructuredError("boom", 41)
        raise ValueError("boom")

    # When: executing through the public v2 entry
    report = workflows.run(flow=pipeline, config={"system": {"save_thumbnail_image": False}})
    # Then: the selected policy appears in the report and the platform marker
    assert report.status == "failed"
    assert report.error is not None and report.error["code"] == code
    assert report.error["message"] == message
    assert (tmp_path / "data" / "job.failed").read_text(encoding="utf-8") == f"ErrorCode={code}\nErrorMessage={message}\n"
    assert "ValueError: boom" in report.iterations[0]["stacktrace"] or "StructuredError" in report.iterations[0]["stacktrace"]
    if failure == "node":
        assert report.iterations[0]["node_calls"][0]["status"] == "failed"


def test_direct_call_still_raises_original_exception__ga577_bv_2() -> None:
    """GA577-BV-2: error options never change plain direct-call semantics."""
    # Given: a decorated function with a selected Runner error code
    original = ValueError("direct")

    @flow(error_code=7, error_message="mapped")
    def pipeline() -> None:
        raise original

    # When: calling the function directly
    with pytest.raises(ValueError) as raised:
        pipeline()
    # Then: the exact exception escapes unwrapped
    assert raised.value is original


def test_opted_in_flow_keeps_eager_semantics__ga577_ep_1() -> None:
    """GA577-EP-1: defaults, branches, loops, literals and containers remain Python."""
    # Given: an opted-in flow exercising the legacy B2 syntax family
    @flow(error_code=7, error_message="mapped")
    def pipeline(count: int = 3) -> list[str]:
        values = []
        if count:
            for index in range(count):
                values.append(f"sample-{index}")
        return values

    # When: calling it normally with default and literal arguments
    default = pipeline()
    empty = pipeline(0)
    # Then: metadata, signature and ordinary Python results are preserved
    assert default == ["sample-0", "sample-1", "sample-2"]
    assert empty == []
    assert pipeline.__name__ == "pipeline"


def test_error_policy_preserves_success__ga577_ep_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA577-EP-1: the Runner preserves successful opted-in execution."""
    # Given: an opted-in flow with an ordinary successful result
    _build_tree(tmp_path / "data")
    monkeypatch.chdir(tmp_path)

    @flow(error_code=7, error_message="mapped")
    def pipeline() -> str:
        return "result"

    # When: executing through the Runner
    report = workflows.run(flow=pipeline, config={"system": {"save_thumbnail_image": False}})
    # Then: success is never converted into an error
    assert report.status == "success"
    assert report.error is None
    assert not (tmp_path / "data" / "job.failed").exists()


def test_cli_honors_flow_error_declaration__ga577_neg_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA577-NEG-1: the real CLI resolves and honors decorated error metadata."""
    # Given: an importable opted-in flow and a complete project directory
    _build_tree(tmp_path / "data")
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "ga577_cli_flow.py").write_text(
        'from rdetoolkit import flow\n@flow(error_code=7, error_message="mapped")\ndef pipeline() -> None:\n    raise ValueError("boom")\n',
        encoding="utf-8",
    )
    config = tmp_path / "rdeconfig.yaml"
    config.write_text("system:\n  save_thumbnail_image: false\n", encoding="utf-8")
    # When: running the actual --flow command
    result = CliRunner().invoke(app, ["run", "--flow", "ga577_cli_flow:pipeline", "--config", str(config)])
    # Then: the CLI exits nonzero and the selected code/message reach RDE
    assert result.exit_code == 1, result.output
    assert (tmp_path / "data" / "job.failed").read_text(encoding="utf-8") == "ErrorCode=7\nErrorMessage=mapped\n"


@pytest.mark.parametrize("exception", [KeyboardInterrupt, SystemExit])
def test_flow_policy_does_not_catch_process_control__ga577_neg_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exception: type[BaseException]) -> None:
    """GA577-NEG-2: process-control exceptions cannot become ordinary failures."""
    # Given: an opted-in flow that stops the process
    _build_tree(tmp_path / "data")
    monkeypatch.chdir(tmp_path)

    @flow(error_code=7, error_message="mapped")
    def pipeline() -> None:
        raise exception

    # When: executing it through the Runner
    with pytest.raises(exception):
        workflows.run(flow=pipeline, config={"system": {"save_thumbnail_image": False}})
    # Then: no misleading mapped failure marker is created
    assert not (tmp_path / "data" / "job.failed").exists()


def test_sigterm_stops_opted_in_flow_before_next_tile__ga577_neg_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA577-NEG-3: the Runner's SIGTERM cannot become a user-code failure."""
    # Given: two tiles and a flow that receives SIGTERM on the first one
    _build_tree(tmp_path / "data")
    (tmp_path / "data" / "inputdata" / "file_1.txt").write_text("data-1", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    seen: list[int] = []
    unhandled: list[int] = []

    @flow(error_code=7, error_message="mapped")
    def pipeline(iteration: IterationInfo) -> None:
        seen.append(iteration.index)
        if iteration.index == 0:
            signal.raise_signal(signal.SIGTERM)

    previous = signal.signal(signal.SIGTERM, lambda signum, _frame: unhandled.append(signum))
    try:
        # When: the public Runner uses continue for ordinary tile failures
        report = workflows.run(flow=pipeline, config={
            "system": {"extended_mode": "MultiDataTile", "save_thumbnail_image": False},
            "execution": {"on_iteration_error": "continue"},
        })
    finally:
        signal.signal(signal.SIGTERM, previous)
    # Then: interruption retains its catalogued identity and stops the run
    assert report.status == "failed"
    assert report.error is not None and report.error["code"] == 3004
    assert report.error["name"] == "RunInterrupted"
    assert seen == [0]
    assert unhandled == []
    assert (tmp_path / "data" / "job.failed").read_text(encoding="utf-8").startswith("ErrorCode=3004\n")
