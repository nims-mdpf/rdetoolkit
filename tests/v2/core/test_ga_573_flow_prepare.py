"""GA573 EP/BV: ``@flow(prepare=...)`` prepares inputs before mode discovery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from rdetoolkit import flow, workflows
from rdetoolkit.api.request import build_run_request
from rdetoolkit.cli.app import app
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import RdeConfig
from tests.v2.runner.test_event_log_robustness_k4 import _build_tree

_MULTIDATA_CONFIG: dict[str, Any] = {
    "system": {"extended_mode": "MultiDataTile", "save_thumbnail_image": False},
}


def split_combined(inputdata: Path, config: RdeConfig) -> None:
    """Split ``combined.txt`` into one input file per ``---`` separated block."""
    _ = config
    combined = inputdata / "combined.txt"
    if not combined.exists():
        return
    for index, block in enumerate(combined.read_text(encoding="utf-8").split("---\n")):
        (inputdata / f"part_{index}.txt").write_text(block, encoding="utf-8")
    combined.unlink()


def _concatenated_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data_root = tmp_path / "data"
    _build_tree(data_root)
    (data_root / "inputdata" / "file_0.txt").unlink()
    (data_root / "inputdata" / "combined.txt").write_text("a\n---\nb\n---\nc\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return data_root


def _events(data_root: Path, run_id: str) -> list[dict[str, Any]]:
    lines = (data_root / "logs" / f"events_{run_id}.jsonl").read_text(encoding="utf-8").splitlines()
    # The first line is the ``run.meta`` header, which is not an event.
    return [record for record in map(json.loads, lines) if "name" in record]


def test_flow_entry_runs_prepare_before_mode_discovery__ga573_ep_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA573-EP-1: the prepared inputs, not the raw ones, decide the tiles."""
    # Given: one concatenated instrument file and a flow declaring its split
    data_root = _concatenated_project(tmp_path, monkeypatch)
    seen: list[tuple[Path, Any]] = []

    def prepare(inputdata: Path, config: RdeConfig) -> None:
        seen.append((inputdata, config))
        split_combined(inputdata, config)

    tiles: list[int] = []

    @flow(prepare=prepare)
    def pipeline() -> None:
        tiles.append(len(tiles))

    # When: executing through the public v2 entry
    report = workflows.run(flow=pipeline, config=_MULTIDATA_CONFIG)
    # Then: preparation ran once, with the run's inputdata and config, and the
    # Runner discovered one tile per prepared file
    assert report.status == "success", report.error
    assert len(seen) == 1
    assert seen[0][0] == data_root / "inputdata"
    assert isinstance(seen[0][1], RdeConfig)
    assert seen[0][1].system.extended_mode == "MultiDataTile"
    assert len(report.iterations) == 3
    assert tiles == [0, 1, 2]
    assert sorted(path.name for path in (data_root / "inputdata").iterdir()) == ["part_0.txt", "part_1.txt", "part_2.txt"]


def test_prepare_is_recorded_in_run_events__ga573_ep_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA573-EP-2: preparation appears in the event log between start and the first tile."""
    # Given: a flow declaring a preparation step
    data_root = _concatenated_project(tmp_path, monkeypatch)

    @flow(prepare=split_combined)
    def pipeline() -> None:
        return None

    # When: executing it through the Runner
    report = workflows.run(flow=pipeline, config=_MULTIDATA_CONFIG)
    # Then: prepare.started / prepare.completed identify the callable and are
    # ordered after run.started and before any iteration
    events = _events(data_root, report.run_id)
    names = [event["name"] for event in events]
    assert names[0] == "run.started"
    assert names[1:3] == ["prepare.started", "prepare.completed"]
    assert names.index("prepare.completed") < names.index("iteration.started")
    prepare_id = f"{split_combined.__module__}.{split_combined.__qualname__}"
    assert events[1]["payload"] == {"prepare_id": prepare_id}
    assert events[2]["payload"]["prepare_id"] == prepare_id
    assert events[2]["payload"]["duration_ms"] >= 0.0


def test_cli_run_flow_honors_prepare_declaration__ga573_ep_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA573-EP-3: ``rdetoolkit run --flow`` runs the same preparation as ``workflows.run``."""
    # Given: an importable flow with a preparation step and an unprepared project
    data_root = _concatenated_project(tmp_path, monkeypatch)
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "ga573_cli_flow.py").write_text(
        "from pathlib import Path\n"
        "from rdetoolkit import flow\n"
        "def prepare(inputdata: Path, config) -> None:\n"
        "    combined = inputdata / 'combined.txt'\n"
        "    for index, block in enumerate(combined.read_text(encoding='utf-8').split('---\\n')):\n"
        "        (inputdata / f'part_{index}.txt').write_text(block, encoding='utf-8')\n"
        "    combined.unlink()\n"
        "@flow(prepare=prepare)\n"
        "def pipeline() -> None:\n"
        "    return None\n",
        encoding="utf-8",
    )
    config = tmp_path / "rdeconfig.yaml"
    config.write_text("system:\n  extended_mode: MultiDataTile\n  save_thumbnail_image: false\n", encoding="utf-8")
    # When: running the actual CLI entry
    result = CliRunner().invoke(app, ["run", "--flow", "ga573_cli_flow:pipeline", "--config", str(config)])
    # Then: three tiles were run, not the single unprepared one
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["status"] == "success"
    assert len(report["iterations"]) == 3
    assert (data_root / "divided" / "0002").is_dir()
    assert not (data_root / "divided" / "0003").exists()


def test_prepare_failure_fails_run_before_any_tile__ga573_neg_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA573-NEG-1: an ordinary prepare exception is an execution failure (3001), not 1002."""
    # Given: a preparation step that cannot parse its input
    data_root = _concatenated_project(tmp_path, monkeypatch)
    called: list[str] = []

    def prepare(inputdata: Path, config: RdeConfig) -> None:
        _ = (inputdata, config)
        msg = "bad header"
        raise ValueError(msg)

    @flow(prepare=prepare)
    def pipeline() -> None:
        called.append("body")

    # When: executing through the Runner
    report = workflows.run(flow=pipeline, config=_MULTIDATA_CONFIG)
    # Then: the run fails with 3001 naming the preparation, the body never runs,
    # job.failed is written, and the failure is in the event log
    assert report.status == "failed"
    assert report.error is not None and report.error["code"] == 3001
    assert "input preparation" in report.error["message"]
    assert "ValueError" in report.error["message"] and "bad header" in report.error["message"]
    assert called == []
    assert report.iterations == []
    assert (data_root / "job.failed").read_text(encoding="utf-8").startswith("ErrorCode=3001\n")
    events = _events(data_root, report.run_id)
    failed = [event for event in events if event["name"] == "prepare.failed"]
    assert len(failed) == 1
    assert failed[0]["payload"]["error_type"] == "ValueError"
    assert failed[0]["payload"]["error_msg"] == "bad header"
    assert "prepare.completed" not in [event["name"] for event in events]


def test_prepare_structured_error_keeps_its_code__ga573_neg_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA573-NEG-2: a ``StructuredError`` from prepare publishes its own ecode/emsg."""
    # Given: a preparation step reporting a user error code
    data_root = _concatenated_project(tmp_path, monkeypatch)

    def prepare(inputdata: Path, config: RdeConfig) -> None:
        _ = (inputdata, config)
        msg = "Unsupported instrument file"
        raise StructuredError(msg, 21)

    @flow(prepare=prepare)
    def pipeline() -> None:
        return None

    # When: executing through the Runner
    report = workflows.run(flow=pipeline, config=_MULTIDATA_CONFIG)
    # Then: the user code and message reach the report and job.failed verbatim
    assert report.status == "failed"
    assert report.error is not None and report.error["code"] == 21
    assert (data_root / "job.failed").read_text(encoding="utf-8") == "ErrorCode=21\nErrorMessage=Unsupported instrument file\n"


@pytest.mark.parametrize("exception", [KeyboardInterrupt, SystemExit])
def test_prepare_process_control_propagates__ga573_neg_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exception: type[BaseException]) -> None:
    """GA573-NEG-3: process-control exceptions from prepare are never mapped."""
    # Given: a preparation step that stops the process
    data_root = _concatenated_project(tmp_path, monkeypatch)

    def prepare(inputdata: Path, config: RdeConfig) -> None:
        _ = (inputdata, config)
        raise exception

    @flow(prepare=prepare)
    def pipeline() -> None:
        return None

    # When / Then: the exception escapes and no misleading marker is created
    with pytest.raises(exception):
        workflows.run(flow=pipeline, config=_MULTIDATA_CONFIG)
    assert not (data_root / "job.failed").exists()


def test_validate_only_runs_prepare_but_not_the_flow__ga573_bv_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA573-BV-1: validate-only resolves the mode the real run will see."""
    # Given: a flow with a preparation step
    data_root = _concatenated_project(tmp_path, monkeypatch)
    calls: list[str] = []

    def prepare(inputdata: Path, config: RdeConfig) -> None:
        calls.append("prepare")
        split_combined(inputdata, config)

    @flow(prepare=prepare)
    def pipeline() -> None:
        calls.append("body")

    request = build_run_request(flow=pipeline, custom_dataset_function=None, config=_MULTIDATA_CONFIG, root=tmp_path, validate_only=True)
    runner = Runner(root=tmp_path, inputdata_path=data_root / "inputdata", unpacked_dir_path=data_root / "temp")
    # When: running the pre-flight validation
    report = runner.run(request)
    # Then: preparation ran and the flow body did not
    assert report.status == "success", report.error
    assert calls == ["prepare"]
    assert report.iterations == []


def test_direct_call_does_not_run_prepare__ga573_bv_2() -> None:
    """GA573-BV-2: a decorated flow stays a plain function outside the Runner."""
    # Given: a flow with a preparation step that must not run on direct calls
    calls: list[str] = []

    def prepare(inputdata: Path, config: RdeConfig) -> None:
        _ = (inputdata, config)
        calls.append("prepare")

    @flow(prepare=prepare)
    def pipeline(value: int = 2) -> int:
        calls.append("body")
        return value * 2

    # When: calling the function directly
    result = pipeline()
    # Then: only the body ran and the metadata is preserved
    assert result == 4
    assert calls == ["body"]
    assert pipeline.__name__ == "pipeline"


def test_flow_without_prepare_emits_no_prepare_events__ga573_bv_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA573-BV-3: flows that do not declare prepare keep their event sequence."""
    # Given: an ordinary flow
    data_root = tmp_path / "data"
    _build_tree(data_root)
    monkeypatch.chdir(tmp_path)

    @flow
    def pipeline() -> None:
        return None

    # When: executing it
    report = workflows.run(flow=pipeline, config={"system": {"save_thumbnail_image": False}})
    # Then: no prepare.* event is written
    names = [event["name"] for event in _events(data_root, report.run_id)]
    assert report.status == "success"
    assert not [name for name in names if name.startswith("prepare.")]


def test_non_callable_prepare_is_rejected_at_decoration__ga573_neg_4() -> None:
    """GA573-NEG-4: a non-callable prepare fails when the flow is declared, not mid-run."""
    # Given / When / Then: decorating with a non-callable prepare raises TypeError
    with pytest.raises(TypeError, match="prepare"):

        @flow(prepare="split_combined")  # type: ignore[arg-type]
        def pipeline() -> None:
            return None
