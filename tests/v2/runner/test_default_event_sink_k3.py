"""FileEventSink is the Runner's default sink (Session K3, ruling #1).

Design authority: PhaseK_prompts ruling #6(a) / Q6 — once the data root is
resolved the Runner writes ``<data_root>/logs/events_<run_id>.jsonl`` unless a
sink was injected. Every production entry (CLI ``run --flow``, CLI
``--validate-only``, ``workflows.run(flow=...)``, the public callback entry
``workflows.run(custom_dataset_function=...)``) builds its Runner without a
sink, so each of them now leaves the file behind. ``data/logs/**`` is excluded
from v1 parity (Design §6.3), so this adds no contract artifact.

EP table:

| TC-ID         | Partition                                   | Expected                                                    |
|---------------|---------------------------------------------|-------------------------------------------------------------|
| TC-K3-DEF-001 | Runner.run, no sink injected                | events_<run_id>.jsonl under <data_root>/logs, ends run.completed |
| TC-K3-DEF-002 | Runner.run, MemoryEventSink injected        | injected sink receives events, no events file              |
| TC-K3-DEF-003 | validate-only request                       | events file written, no iteration events                   |
| TC-K3-DEF-004 | workflows.run(flow=...)                     | events file under data/logs                                 |
| TC-K3-DEF-005 | workflows.run(custom_dataset_function=...)  | events file under data/logs with one iteration per tile        |
| TC-K3-DEF-006 | CLI run --flow --validate-only with W1001   | W1001 warning recorded in the CLI's events file             |
| TC-K3-DEF-007 | failed run (pre_validate fails)             | events file still ends with run.completed status failed     |

BV table:

| TC-ID         | Boundary                                    | Expected                                                    |
|---------------|---------------------------------------------|-------------------------------------------------------------|
| TC-K3-DEF-BV1 | step-by-step iterate() with no run()        | no events file, no RuntimeError (sink never opened)         |
| TC-K3-DEF-BV2 | alias-flat root                             | events under <root>/logs, no <root>/data created            |
| TC-K3-DEF-BV3 | two consecutive runs                        | two distinct events files (run_id-scoped accumulation)      |
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml
from typer.testing import CliRunner

from rdetoolkit import workflows
from rdetoolkit.api.request import build_run_request
from rdetoolkit.cli.app import app
from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import IterationInfo, RdeConfig

_FIXTURE_MODULE = "tests.v2.cli.fixtures.run_flows"

_INVOICE: dict[str, Any] = {
    "datasetId": "k3-dataset",
    "basic": {"dateSubmitted": "2026-10-16", "dataOwnerId": "0" * 56, "dataName": "k3"},
}


def _build_tree(data_root: Path, *, files: int = 1) -> None:
    (data_root / "inputdata").mkdir(parents=True)
    for index in range(files):
        (data_root / "inputdata" / f"file_{index}.txt").write_text(f"data-{index}", encoding="utf-8")
    (data_root / "invoice").mkdir(parents=True)
    (data_root / "invoice" / "invoice.json").write_text(json.dumps(_INVOICE), encoding="utf-8")
    (data_root / "tasksupport").mkdir(parents=True)
    (data_root / "tasksupport" / "invoice.schema.json").write_text(json.dumps({"properties": {}}), encoding="utf-8")
    (data_root / "tasksupport" / "metadata-def.json").write_text(
        json.dumps({"constant": {}, "variable": []}),
        encoding="utf-8",
    )
    (data_root / "temp").mkdir(parents=True)


def _events_files(logs_dir: Path) -> list[Path]:
    return sorted(logs_dir.glob("events_*.jsonl"))


def _read(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@node(id="k3_default_sink_step")
def _step(iteration: IterationInfo) -> int:
    return iteration.index


@flow
def _one_node_flow(iteration: IterationInfo) -> None:
    _step(iteration)


def _runner(root: Path, data_root: Path, **kwargs: Any) -> Runner:
    return Runner(root=root, inputdata_path=data_root / "inputdata", unpacked_dir_path=data_root / "temp", **kwargs)


class TestRunnerDefaultSink:
    def test_run_writes_events_file__tc_k3_def_001(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-K3-DEF-001: a Runner built without a sink records its run to disk."""
        # Given: a standard data/ layout and a Runner without an injected sink
        _build_tree(tmp_path / "data")
        monkeypatch.chdir(tmp_path)
        runner = _runner(tmp_path, tmp_path / "data", run_id_factory=lambda: "k3-def-001")
        # When: running a one-node flow
        report = runner.run(_one_node_flow)
        # Then: the run's events file exists under <data_root>/logs and is complete
        assert report.status == "success"
        path = tmp_path / "data" / "logs" / "events_k3-def-001.jsonl"
        lines = _read(path)
        assert lines[0]["type"] == "run.meta"
        assert lines[0]["run_id"] == "k3-def-001"
        names = [line.get("name") for line in lines[1:]]
        assert names[0] == "run.started"
        assert names[-1] == "run.completed"
        assert lines[-1]["payload"] == {"status": "success"}
        assert {"iteration.started", "node.started", "node.completed", "iteration.completed"} <= set(names)
        assert {line["run_id"] for line in lines} == {"k3-def-001"}

    def test_injected_sink_wins__tc_k3_def_002(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-K3-DEF-002: an injected sink replaces the file default entirely."""
        # Given: an injected in-memory sink
        _build_tree(tmp_path / "data")
        monkeypatch.chdir(tmp_path)
        sink = MemoryEventSink()
        runner = _runner(tmp_path, tmp_path / "data", event_sink=sink)
        # When: running
        runner.run(_one_node_flow)
        # Then: the memory sink saw the run and no events file was written
        assert runner.event_sink is sink
        assert [event.name for event in sink.events][-1] == "run.completed"
        assert _events_files(tmp_path / "data" / "logs") == []

    def test_validate_only_writes_events__tc_k3_def_003(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-K3-DEF-003: a pre-flight check is recorded too (ruling #1)."""
        # Given: a valid tree and a validate-only request
        _build_tree(tmp_path / "data")
        monkeypatch.chdir(tmp_path)
        runner = _runner(tmp_path, tmp_path / "data", run_id_factory=lambda: "k3-def-003")
        request = build_run_request(
            flow=_one_node_flow,
            custom_dataset_function=None,
            config=None,
            root=tmp_path,
            validate_only=True,
        )
        # When: validating
        report = runner.run(request)
        # Then: the events file records the run start and end only
        assert report.status == "success"
        names = [line.get("name") for line in _read(tmp_path / "data" / "logs" / "events_k3-def-003.jsonl")[1:]]
        assert names == ["run.started", "run.completed"]

    def test_failed_run_still_ends_with_run_completed__tc_k3_def_007(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-K3-DEF-007: a failing run closes its events file with status failed."""
        # Given: a tree whose invoice schema is missing (pre_validate -> 4003)
        _build_tree(tmp_path / "data")
        (tmp_path / "data" / "tasksupport" / "invoice.schema.json").unlink()
        monkeypatch.chdir(tmp_path)
        runner = _runner(tmp_path, tmp_path / "data", run_id_factory=lambda: "k3-def-007")
        # When: running
        report = runner.run(_one_node_flow)
        # Then: the failure is the last recorded event
        assert report.status == "failed"
        lines = _read(tmp_path / "data" / "logs" / "events_k3-def-007.jsonl")
        assert lines[-1]["name"] == "run.completed"
        assert lines[-1]["payload"] == {"status": "failed"}

    def test_step_by_step_iterate_needs_no_open__tc_k3_def_bv1(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-K3-DEF-BV1: driving ``iterate`` directly never touches an unopened file."""
        # Given: an alias-flat tree and a Runner driven without ``run``
        _build_tree(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = _runner(tmp_path, tmp_path)
        runner.run_id = "k3-def-bv1"
        # When: iterating directly
        report = runner.iterate(_one_node_flow, ModeKind.multidatatile, RdeConfig())
        # Then: the tile ran and no events file exists (there is no run to record)
        assert report.status == "success"
        assert _events_files(tmp_path / "logs") == []

    def test_alias_flat_root_writes_below_root__tc_k3_def_bv2(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-K3-DEF-BV2: the events file follows the single resolved data root."""
        # Given: an alias-flat project
        _build_tree(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = _runner(tmp_path, tmp_path, run_id_factory=lambda: "k3-def-bv2")
        # When: running
        runner.run(_one_node_flow)
        # Then: events live in <root>/logs and no data/ child appeared
        assert (tmp_path / "logs" / "events_k3-def-bv2.jsonl").is_file()
        assert not (tmp_path / "data").exists()

    def test_runs_accumulate_by_run_id__tc_k3_def_bv3(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-K3-DEF-BV3: events files are run-scoped and accumulate (ruling #4)."""
        # Given: one tree and two run ids
        _build_tree(tmp_path / "data")
        monkeypatch.chdir(tmp_path)
        ids = iter(["k3-run-a", "k3-run-b"])
        runner = _runner(tmp_path, tmp_path / "data", run_id_factory=lambda: next(ids))
        # When: running twice
        runner.run(_one_node_flow)
        runner.run(_one_node_flow)
        # Then: both files are kept
        names = [path.name for path in _events_files(tmp_path / "data" / "logs")]
        assert names == ["events_k3-run-a.jsonl", "events_k3-run-b.jsonl"]


class TestProductionEntriesWriteEvents:
    def test_workflows_run_flow_writes_events__tc_k3_def_004(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-K3-DEF-004: the public ``flow=`` entry records its run."""
        # Given: a standard layout as the CWD
        _build_tree(tmp_path / "data")
        monkeypatch.chdir(tmp_path)
        # When: running through the public entry
        report: Any = workflows.run(flow=_one_node_flow)
        # Then: data/logs holds this run's events file
        path = tmp_path / "data" / "logs" / f"events_{report.run_id}.jsonl"
        assert _read(path)[-1]["name"] == "run.completed"

    def test_public_callback_entry_writes_events__tc_k3_def_005(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-K3-DEF-005: the v1 callback entry records its run (not a v1 artifact)."""
        # Given: a standard layout and a v1 callback
        _build_tree(tmp_path / "data")
        monkeypatch.chdir(tmp_path)
        calls: list[object] = []

        def _callback(srcpaths: object, resource_paths: object) -> None:
            calls.append(srcpaths)

        # When: running through the public callback entry
        workflows.run(custom_dataset_function=_callback)
        # Then: exactly one events file exists and it outlines the one tile
        assert len(calls) == 1
        files = _events_files(tmp_path / "data" / "logs")
        assert len(files) == 1
        lines = _read(files[0])
        names = [line.get("name") for line in lines[1:]]
        assert names[0] == "run.started"
        assert names[-1] == "run.completed"
        assert names.count("iteration.started") == names.count("iteration.completed") == 1

    def test_cli_validate_only_records_w1001__tc_k3_def_006(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-K3-DEF-006: the CLI's W1001 is now visible in its own events file.

        Closes the Session J2 debt: the CLI owns no sink, so the W1001 that
        ``--validate-only`` publishes used to reach only an in-memory default
        and vanish.
        """
        # Given: a declared invoice mode that an ExcelInvoice input overrides
        _build_tree(tmp_path / "data")
        with pd.ExcelWriter(tmp_path / "data" / "inputdata" / "sample_excel_invoice.xlsx") as writer:
            pd.DataFrame([["invoiceList_format_id"], [""]]).to_excel(
                writer,
                sheet_name="invoice_form",
                index=False,
                header=False,
            )
        (tmp_path / "rdeconfig.yaml").write_text(
            yaml.safe_dump({"system": {"extended_mode": "invoice"}}),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        # When: validating through the CLI
        result = CliRunner().invoke(
            app,
            ["run", "--flow", f"{_FIXTURE_MODULE}:validate_only_pipeline", "--validate-only"],
        )
        # Then: the CLI's events file carries exactly one W1001 with its run id
        assert result.exit_code == 0, result.output
        files = _events_files(tmp_path / "data" / "logs")
        assert len(files) == 1
        lines = _read(files[0])
        warnings = [line for line in lines if line.get("name") == "warning" and line["payload"]["code"] == 1001]
        assert len(warnings) == 1
        assert warnings[0]["run_id"] == lines[0]["run_id"]
        assert lines[-1]["name"] == "run.completed"
