"""GA-09 (#690): the isolated ``rde_runner`` fixture and ``RdeTestResult``.

Every test here drives the real v2 Runner (``workflows.run(flow=...)``) on a
staged copy of a project; nothing is mocked.

EP table
========

| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-RR-EP-001 | nested layout | ``<project>/data`` tree, succeeding flow | staged copy under tmp_path, ``data_root`` = staged ``data``, report/events paths, outputs kept |
| TC-RR-EP-002 | alias-flat layout | markers directly below the project | ``data_root`` = staged project root, no ``data`` child created |
| TC-RR-EP-003 | failed run | flow raises | inspectable result (no exception), ``job.failed`` kept, ``assert_success`` explains |
| TC-RR-EP-004 | sequence | failure then success in one test | separate staged roots, second run clean |
| TC-RR-EP-005 | reused fixture | one module-scoped project, two tests | each test stages its own copy, source unchanged |
| TC-RR-EP-006 | two runners | two ``RdeTestRunner`` objects on one base dir | distinct staged roots |
| TC-RR-EP-007 | config | ``RdeConfig`` object and override mapping | flow sees the configured values |
| TC-RR-EP-008 | modes | the five frozen mode fixtures | mode-specific outputs and tile counts |
| TC-RR-EP-009 | cwd | monkeypatched cwd | flow runs in the staged root, caller cwd restored |
| TC-RR-EP-010 | success | ``assert_success`` on a successful run | returns ``None`` |
| TC-RR-EP-011 | sidecar | diagnostics sidecar present / absent | ``diagnostics_path`` set / ``None`` |
| TC-RR-EP-012 | artifact path | relative artifact name | resolved below ``data_root`` |
| TC-RR-EP-013 | iterations | failed tile | typed summary carries code/name |
| TC-RR-EP-014 | template | concrete ProcessingTemplate subclass | runs on the same path |

BV / negative table
===================

| TC | Boundary | Input | Expected |
|----|----------|-------|----------|
| TC-RR-BV-001 | project | missing path | ``FileNotFoundError``, nothing staged |
| TC-RR-BV-002 | project | regular file | ``NotADirectoryError`` |
| TC-RR-BV-003 | flow | ``None`` | ``TypeError`` before staging (never the v1 callback entry) |
| TC-RR-BV-004 | interruption | flow raises ``KeyboardInterrupt`` | propagated unchanged, source intact, cwd restored |
| TC-RR-BV-005 | flow | non-callable | the Runner's ``TypeError`` propagates unchanged |
| TC-RR-BV-006 | mutation | flow rewrites inputs and invoice | source tree byte-identical |
| TC-RR-BV-007 | symlink | project input is a symlink to an outside file | outside file unchanged |
| TC-RR-BV-008 | artifact path | absolute / traversal / empty / non-str | ``ValueError`` / ``TypeError`` |
| TC-RR-BV-009 | partial | one of two tiles fails | ``assert_success`` fails naming ``partial`` |
| TC-RR-BV-010 | env | flow sets an environment variable | not an rdetoolkit concern, but the runner adds none |
| TC-RR-BV-011 | staging inside project | ``project=tmp_path`` with the fixture / staging several levels down | staging directory left out of the copy, siblings kept |
| TC-RR-BV-012 | project vs staging | project is the staging directory / lies below it | ``ValueError``, nothing staged / copied normally |
| TC-RR-BV-013 | earlier outputs | outputs of an earlier run in the source data root (nested / flat), flow writes nothing | not staged; ``assert_artifact`` and ``expect_files`` fail; inputs, ``invoice/`` and other files staged |
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import final

import pytest

from rdetoolkit import flow
from rdetoolkit.templates import ProcessingTemplate, slot
from rdetoolkit.testing import RdeIterationSummary, RdeTestResult, RdeTestRunner
from rdetoolkit.testing.runner import _collect_result
from rdetoolkit.types import InputPaths, InvoiceData, OutputContext, RdeConfig
from tests.v2.contract.fixtures import _generate

_INVOICE = {
    "datasetId": "rde-runner-dataset",
    "basic": {"dateSubmitted": "2026-11-15", "dataOwnerId": "1" * 56, "dataName": "rde runner sample"},
    "custom": {"temperature": 25.0},
}
_SCHEMA = {
    "$id": "https://rde.nims.go.jp/rde/dataset-templates/ga690/invoice.schema.json",
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["custom"],
    "properties": {
        "custom": {
            "type": "object",
            "label": {"ja": "固有情報", "en": "Custom"},
            "required": ["temperature"],
            "properties": {"temperature": {"type": "number", "label": {"ja": "温度", "en": "temperature"}}},
        },
    },
}

_CWD_SEEN: list[Path] = []


def _write_data_material(data: Path, *, inputs: tuple[str, ...] = ("sample.txt",)) -> None:
    (data / "inputdata").mkdir(parents=True)
    for name in inputs:
        (data / "inputdata" / name).write_text(f"measured {name}", encoding="utf-8")
    (data / "invoice").mkdir()
    (data / "invoice" / "invoice.json").write_text(json.dumps(_INVOICE), encoding="utf-8")
    (data / "tasksupport").mkdir()
    (data / "tasksupport" / "invoice.schema.json").write_text(json.dumps(_SCHEMA), encoding="utf-8")


def _nested_project(root: Path, *, inputs: tuple[str, ...] = ("sample.txt",)) -> Path:
    _write_data_material(root / "data", inputs=inputs)
    return root


def _flat_project(root: Path) -> Path:
    _write_data_material(root)
    return root


def _tree_digest(root: Path) -> dict[str, str]:
    """Return every entry below ``root`` with a content digest (``dir`` for directories)."""
    digest: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            digest[relative] = f"link:{os.readlink(path)}"
        elif path.is_dir():
            digest[relative] = "dir"
        else:
            digest[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


@flow(id="tests.ga690.writes_result")
def _writes_result(paths: InputPaths, invoice: InvoiceData, out: OutputContext) -> None:
    _CWD_SEEN.append(Path.cwd())
    names = ",".join(sorted(path.name for path in paths.rawfiles))
    out.write_bytes("struct", "result.csv", f"time,value\n0,{invoice.raw['datasetId']}\n".encode())
    out.write_bytes("struct", "inputs.txt", names.encode())


@flow(id="tests.ga690.failing")
def _failing(paths: InputPaths) -> None:
    del paths
    msg = "deliberate failure"
    raise ValueError(msg)


@flow(id="tests.ga690.fails_on_b")
def _fails_on_b(paths: InputPaths) -> None:
    if any(path.name == "b.txt" for path in paths.rawfiles):
        msg = "tile b is broken"
        raise ValueError(msg)


@flow(id="tests.ga690.interrupted")
def _interrupted(paths: InputPaths) -> None:
    del paths
    raise KeyboardInterrupt


@flow(id="tests.ga690.mutating")
def _mutating(paths: InputPaths) -> None:
    for path in sorted(paths.inputdata.iterdir()):
        path.write_text("overwritten by the flow", encoding="utf-8")
    (paths.inputdata / "created.txt").write_text("new", encoding="utf-8")
    (paths.invoice / "invoice.json").write_text("{}", encoding="utf-8")
    (paths.tasksupport / "extra.json").write_text("{}", encoding="utf-8")


@flow(id="tests.ga690.reads_config")
def _reads_config(config: RdeConfig, out: OutputContext) -> None:
    out.write_bytes("struct", "custom.json", json.dumps(dict(config.custom), sort_keys=True).encode())


@flow(id="tests.ga690.noop")
def _noop(paths: InputPaths, invoice: InvoiceData) -> None:
    assert paths.inputdata.is_dir()
    assert invoice.raw


class _Skeleton(ProcessingTemplate):
    @slot
    def label(self, paths: InputPaths) -> str: ...

    @final
    def __flow__(self, paths: InputPaths, out: OutputContext) -> None:
        out.write_bytes("struct", "template.txt", self.label(paths).encode())


class _Concrete(_Skeleton):
    def label(self, paths: InputPaths) -> str:
        return paths.rawfiles[0].name


@pytest.fixture(scope="module")
def shared_project(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Path, dict[str, str]]]:
    """Provide one project reused by several tests, asserting at teardown it never changed."""
    root = _nested_project(tmp_path_factory.mktemp("shared") / "project")
    before = _tree_digest(root)
    yield root, before
    # Then (module teardown): no test that reused the project changed it
    assert _tree_digest(root) == before


def test_nested_layout_runs_on_a_staged_copy__tc_rr_ep_001(rde_runner: RdeTestRunner, tmp_path: Path) -> None:
    """TC-RR-EP-001: a nested project is copied below tmp_path and run for real."""
    # Given: a nested RDE project outside the runner's staging area
    project = _nested_project(tmp_path / "source" / "project")
    before = _tree_digest(project)

    # When: running it through the fixture
    result = rde_runner.run(flow=_writes_result, project=project)

    # Then: the run succeeded on a staged copy below tmp_path
    assert isinstance(result, RdeTestResult)
    assert result.report.status == "success", result.report.error
    assert result.status == "success"
    assert result.project_root != project
    assert result.project_root.is_relative_to(tmp_path)
    assert result.project_root.name == "project"
    assert result.data_root == result.project_root / "data"
    # And: the outputs and the run's own records stay available for assertions
    assert (result.data_root / "structured" / "result.csv").read_text(encoding="utf-8").startswith("time,value")
    assert result.report_path == result.data_root / "logs" / f"run_report_{result.report.run_id}.json"
    assert result.report_path is not None
    assert json.loads(result.report_path.read_text(encoding="utf-8"))["run_id"] == result.report.run_id
    assert result.events_path == result.data_root / "logs" / f"events_{result.report.run_id}.jsonl"
    assert result.job_failed_path is None
    assert result.diagnostics_path is None
    # And: the source project is byte-identical
    assert _tree_digest(project) == before


def test_alias_flat_layout_resolves_like_production__tc_rr_ep_002(rde_runner: RdeTestRunner, tmp_path: Path) -> None:
    """TC-RR-EP-002: an alias-flat project is its own data root."""
    # Given: a project whose RDE markers sit directly below the root
    project = _flat_project(tmp_path / "flat")
    before = _tree_digest(project)

    # When: running it
    result = rde_runner.run(flow=_writes_result, project=project)

    # Then: the staged root is the data root and no nested data/ appears
    assert result.status == "success", result.report.error
    assert result.data_root == result.project_root
    assert not (result.project_root / "data").exists()
    assert (result.data_root / "structured" / "result.csv").is_file()
    assert _tree_digest(project) == before


def test_failure_is_inspectable_not_raised__tc_rr_ep_003(rde_runner: RdeTestRunner, tmp_path: Path) -> None:
    """TC-RR-EP-003: a failed run returns a result whose assert_success explains the failure."""
    # Given: a project and a flow that fails its only tile
    project = _nested_project(tmp_path / "project")
    before = _tree_digest(project)

    # When: running it (no exception escapes)
    result = rde_runner.run(flow=_failing, project=project)

    # Then: the failed report and job.failed stay inspectable
    assert result.status == "failed"
    assert result.report.error is not None
    assert result.report.error["code"] == 3001
    assert result.job_failed_path == result.data_root / "job.failed"
    assert result.job_failed_path is not None
    assert result.job_failed_path.read_text(encoding="utf-8").startswith("ErrorCode=")
    # And: assert_success fails with the status, code, message and where to look
    with pytest.raises(AssertionError) as excinfo:
        result.assert_success()
    message = str(excinfo.value)
    assert "'failed'" in message
    assert "3001" in message
    assert "NodeExecutionFailed" in message
    assert "deliberate failure" in message
    assert str(result.data_root) in message
    assert "job.failed" in message
    assert _tree_digest(project) == before


def test_failure_then_success_use_separate_roots__tc_rr_ep_004(rde_runner: RdeTestRunner, tmp_path: Path) -> None:
    """TC-RR-EP-004: sequential runs are staged separately by default."""
    # Given: one project
    project = _nested_project(tmp_path / "project")

    # When: a failing run is followed by a successful one
    failed = rde_runner.run(flow=_failing, project=project)
    succeeded = rde_runner.run(flow=_writes_result, project=project)

    # Then: each run owns its own staged root; the second sees none of the first
    assert failed.status == "failed"
    assert succeeded.status == "success", succeeded.report.error
    assert failed.project_root != succeeded.project_root
    assert (failed.data_root / "job.failed").is_file()
    assert not (succeeded.data_root / "job.failed").exists()
    assert succeeded.job_failed_path is None
    # And: the first run's artifacts were not cleaned up by the second
    assert failed.report_path is not None
    assert failed.report_path.is_file()


def test_reused_project_fixture_first__tc_rr_ep_005(
    rde_runner: RdeTestRunner, shared_project: tuple[Path, dict[str, str]], tmp_path: Path,
) -> None:
    """TC-RR-EP-005 (a): a module-scoped project is staged, not written."""
    # Given: the shared project
    project, before = shared_project
    # When: a mutating flow runs on it
    result = rde_runner.run(flow=_mutating, project=project)
    # Then: only the staged copy changed
    assert result.project_root.is_relative_to(tmp_path)
    assert (result.data_root / "inputdata" / "created.txt").is_file()
    assert _tree_digest(project) == before


def test_reused_project_fixture_second__tc_rr_ep_005(
    rde_runner: RdeTestRunner, shared_project: tuple[Path, dict[str, str]], tmp_path: Path,
) -> None:
    """TC-RR-EP-005 (b): a later test sees the pristine shared project, independent of order."""
    # Given: the shared project, possibly after the mutating test ran
    project, before = shared_project
    # When: running a reading flow
    result = rde_runner.run(flow=_writes_result, project=project)
    # Then: it sees only the original input, staged below this test's tmp_path
    assert result.status == "success", result.report.error
    assert result.project_root.is_relative_to(tmp_path)
    assert (result.data_root / "structured" / "inputs.txt").read_text(encoding="utf-8") == "sample.txt"
    assert not (result.data_root / "inputdata" / "created.txt").exists()
    assert _tree_digest(project) == before


def test_two_runner_objects_never_share_a_root__tc_rr_ep_006(tmp_path: Path) -> None:
    """TC-RR-EP-006: two runners on one base directory stage distinct roots."""
    # Given: two runners on the same base directory and one project
    project = _nested_project(tmp_path / "project")
    first = RdeTestRunner(tmp_path / "staging")
    second = RdeTestRunner(tmp_path / "staging")

    # When: each runs once
    one = first.run(flow=_writes_result, project=project)
    two = second.run(flow=_writes_result, project=project)

    # Then: both succeed on separate copies
    assert one.status == two.status == "success"
    assert one.project_root != two.project_root
    assert one.project_root.parent.parent == two.project_root.parent.parent == tmp_path / "staging"


@pytest.mark.parametrize(
    "config",
    [
        pytest.param(RdeConfig(custom={"normalize": False}), id="rdeconfig-object"),
        pytest.param({"custom": {"normalize": False}}, id="override-mapping"),
    ],
)
def test_custom_config_reaches_the_flow__tc_rr_ep_007(rde_runner: RdeTestRunner, tmp_path: Path, config: object) -> None:
    """TC-RR-EP-007: an RdeConfig or an override mapping configures the run."""
    # Given: a project and a configuration carrying a custom value
    project = _nested_project(tmp_path / "project")
    # When: running with that configuration
    result = rde_runner.run(flow=_reads_config, project=project, config=config)
    # Then: the flow received it
    assert result.status == "success", result.report.error
    written = json.loads((result.data_root / "structured" / "custom.json").read_text(encoding="utf-8"))
    assert written == {"normalize": False}


def _mode_overrides(mode: str) -> dict[str, object]:
    extended_mode = {"multidatatile": "MultiDataTile", "rdeformat": "rdeformat"}.get(mode)
    return {
        "system": {
            "extended_mode": extended_mode or "invoice",
            "save_raw": True,
            "save_nonshared_raw": True,
            "save_thumbnail_image": False,
            "magic_variable": False,
        },
        "smarttable": {"save_table_file": False},
    }


@pytest.mark.parametrize("mode", ["invoice", "excelinvoice", "multidatatile", "rdeformat", "smarttable"])
def test_every_mode_runs_through_the_fixture__tc_rr_ep_008(rde_runner: RdeTestRunner, tmp_path: Path, mode: str) -> None:
    """TC-RR-EP-008: each frozen mode fixture runs with its mode-specific outputs."""
    # Given: the committed mode input material as a nested project
    project = tmp_path / "source" / mode
    _generate.materialize_sut_case(mode, project)
    before = _tree_digest(project)
    expected_tiles = json.loads((_generate.EXPECTED_ROOT / mode / "ok.json").read_text(encoding="utf-8"))
    tile_count = expected_tiles["observed"]["callback_count"]

    # When: running the no-op flow in that mode
    result = rde_runner.run(flow=_noop, project=project, config=_mode_overrides(mode))

    # Then: the mode and tile count v1 observed are reproduced on the staged copy
    assert result.status == "success", result.report.error
    assert result.report.mode == mode
    assert len(result.iterations) == tile_count
    assert [summary.index for summary in result.iterations] == list(range(tile_count))
    assert (result.data_root / "invoice" / "invoice.json").is_file()
    if tile_count > 1:
        assert (result.data_root / "divided" / "0001" / "invoice" / "invoice.json").is_file()
    assert _tree_digest(project) == before


def test_flow_runs_in_staged_root_and_cwd_is_restored__tc_rr_ep_009(
    rde_runner: RdeTestRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-RR-EP-009: the flow sees the staged root as cwd, like production; the caller's cwd returns."""
    # Given: a monkeypatched working directory and a relative project path
    _nested_project(tmp_path / "work" / "project")
    monkeypatch.chdir(tmp_path / "work")
    _CWD_SEEN.clear()

    # When: running with the relative spelling
    result = rde_runner.run(flow=_writes_result, project="project")

    # Then: the flow ran from the staged root and the caller's cwd is unchanged
    assert result.status == "success", result.report.error
    assert [result.project_root] == _CWD_SEEN
    assert Path.cwd() == tmp_path / "work"


def test_assert_success_passes_on_success__tc_rr_ep_010(rde_runner: RdeTestRunner, tmp_path: Path) -> None:
    """TC-RR-EP-010: assert_success is silent for a successful run."""
    # Given / When: a successful run
    result = rde_runner.run(flow=_writes_result, project=_nested_project(tmp_path / "project"))
    # Then: no assertion error
    assert result.assert_success() is None


def test_diagnostics_path_follows_the_sidecar__tc_rr_ep_011(rde_runner: RdeTestRunner, tmp_path: Path) -> None:
    """TC-RR-EP-011: diagnostics_path names logs/diagnostics_<run_id>.json only when it exists."""
    # Given: a failed run, which writes its sidecar since #686
    result = rde_runner.run(flow=_failing, project=_nested_project(tmp_path / "project"))
    sidecar = result.data_root / "logs" / f"diagnostics_{result.report.run_id}.json"
    assert result.diagnostics_path == sidecar

    # And: once the sidecar is gone (a historic run), no path is exposed
    sidecar.unlink()
    without = _collect_result(result.report, project_root=result.project_root, data_root=result.data_root)
    assert without.diagnostics_path is None
    sidecar.write_text("{}", encoding="utf-8")

    # When: collecting the result again once the sidecar exists
    collected = _collect_result(result.report, project_root=result.project_root, data_root=result.data_root)

    # Then: the documented sidecar path is exposed
    assert collected.diagnostics_path == sidecar


def test_artifact_path_resolves_below_data_root__tc_rr_ep_012(rde_runner: RdeTestRunner, tmp_path: Path) -> None:
    """TC-RR-EP-012: artifact names are relative to the isolated data root."""
    # Given: a successful run
    result = rde_runner.run(flow=_writes_result, project=_nested_project(tmp_path / "project"))
    # When / Then: POSIX and Path spellings resolve to the same artifact
    assert result.artifact_path("structured/result.csv") == result.data_root / "structured" / "result.csv"
    assert result.artifact_path(Path("structured") / "result.csv") == result.data_root / "structured" / "result.csv"


def test_iteration_summaries_are_typed__tc_rr_ep_013(rde_runner: RdeTestRunner, tmp_path: Path) -> None:
    """TC-RR-EP-013: each iteration is summarised with its status and error identity."""
    # Given / When: a failing run
    result = rde_runner.run(flow=_failing, project=_nested_project(tmp_path / "project"))
    # Then: the one tile is summarised
    assert result.iterations == (
        RdeIterationSummary(
            index=0,
            datatile_id="sample",
            status="failed",
            error_code=3001,
            error_name="NodeExecutionFailed",
            error_message=result.report.iterations[0]["error"]["message"],
        ),
    )


def test_template_subclass_runs__tc_rr_ep_014(rde_runner: RdeTestRunner, tmp_path: Path) -> None:
    """TC-RR-EP-014: a concrete ProcessingTemplate subclass is accepted like workflows.run."""
    # Given / When: running a concrete template class
    result = rde_runner.run(flow=_Concrete, project=_nested_project(tmp_path / "project"))
    # Then: the template's flow ran
    assert result.status == "success", result.report.error
    assert (result.data_root / "structured" / "template.txt").read_text(encoding="utf-8") == "sample.txt"


def test_missing_project_is_rejected__tc_rr_bv_001(rde_runner: RdeTestRunner, tmp_path: Path) -> None:
    """TC-RR-BV-001: a missing project fails before anything is staged."""
    # Given: a path that does not exist
    missing = tmp_path / "missing"
    # When / Then: FileNotFoundError names it, and no staging directory appears
    with pytest.raises(FileNotFoundError, match="missing"):
        rde_runner.run(flow=_writes_result, project=missing)
    assert not rde_runner.base_dir.exists() or not any(rde_runner.base_dir.iterdir())


def test_regular_file_project_is_rejected__tc_rr_bv_002(rde_runner: RdeTestRunner, tmp_path: Path) -> None:
    """TC-RR-BV-002: a project that is a file is rejected."""
    # Given: a regular file
    regular = tmp_path / "file.txt"
    regular.write_text("", encoding="utf-8")
    # When / Then
    with pytest.raises(NotADirectoryError, match="file.txt"):
        rde_runner.run(flow=_writes_result, project=regular)


def test_none_flow_is_rejected_before_staging__tc_rr_bv_003(rde_runner: RdeTestRunner, tmp_path: Path) -> None:
    """TC-RR-BV-003: flow=None never falls through to the v1 callback entry."""
    # Given: a valid project
    project = _nested_project(tmp_path / "project")
    # When / Then: TypeError, nothing staged
    with pytest.raises(TypeError, match="flow"):
        rde_runner.run(flow=None, project=project)  # type: ignore[arg-type]
    assert not rde_runner.base_dir.exists() or not any(rde_runner.base_dir.iterdir())


def test_interruption_propagates_and_keeps_source__tc_rr_bv_004(
    rde_runner: RdeTestRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-RR-BV-004: an interrupt is not swallowed, and nothing outside tmp staging changes."""
    # Given: a project, a known cwd
    project = _nested_project(tmp_path / "project")
    before = _tree_digest(project)
    monkeypatch.chdir(tmp_path)
    # When / Then: the KeyboardInterrupt reaches the caller unchanged
    with pytest.raises(KeyboardInterrupt):
        rde_runner.run(flow=_interrupted, project=project)
    assert Path.cwd() == tmp_path
    assert _tree_digest(project) == before
    # And: the staged copy is still there for inspection
    staged = sorted(rde_runner.base_dir.glob("*/project"))
    assert len(staged) == 1
    assert (staged[0] / "data" / "inputdata" / "sample.txt").is_file()


def test_runner_type_error_is_preserved__tc_rr_bv_005(rde_runner: RdeTestRunner, tmp_path: Path) -> None:
    """TC-RR-BV-005: the Runner's own rejection of a non-callable flow propagates."""
    # Given: a project and a non-callable flow
    project = _nested_project(tmp_path / "project")
    # When / Then: the request builder's TypeError is not wrapped
    with pytest.raises(TypeError, match="flow must be callable"):
        rde_runner.run(flow="not a flow", project=project)  # type: ignore[arg-type]


def test_flow_mutation_never_reaches_the_source__tc_rr_bv_006(rde_runner: RdeTestRunner, tmp_path: Path) -> None:
    """TC-RR-BV-006: inputs, invoice and tasksupport of the source stay byte-identical."""
    # Given: a project and a flow that rewrites its inputs
    project = _nested_project(tmp_path / "project")
    before = _tree_digest(project)
    # When: running it
    result = rde_runner.run(flow=_mutating, project=project)
    # Then: the staged copy was rewritten, the source was not
    assert (result.data_root / "tasksupport" / "extra.json").is_file()
    assert _tree_digest(project) == before


def test_symlinked_input_is_copied_by_content__tc_rr_bv_007(rde_runner: RdeTestRunner, tmp_path: Path) -> None:
    """TC-RR-BV-007: a symlink in the project cannot route a flow's write to the outside target."""
    # Given: an input that is a symlink to a file outside the project
    project = _nested_project(tmp_path / "project", inputs=())
    outside = tmp_path / "outside.txt"
    outside.write_text("original", encoding="utf-8")
    (project / "data" / "inputdata" / "linked.txt").symlink_to(outside)
    # When: a flow overwrites every input
    result = rde_runner.run(flow=_mutating, project=project)
    # Then: the target outside the project is unchanged
    assert outside.read_text(encoding="utf-8") == "original"
    assert not (result.data_root / "inputdata" / "linked.txt").is_symlink()


@pytest.mark.parametrize(
    ("name", "error"),
    [
        pytest.param("/etc/passwd", ValueError, id="absolute"),
        pytest.param("../outside.txt", ValueError, id="parent"),
        pytest.param("structured/../../outside.txt", ValueError, id="nested-parent"),
        pytest.param("C:/Windows/win.ini", ValueError, id="windows-drive"),
        pytest.param("..\\outside.txt", ValueError, id="backslash-parent"),
        pytest.param("", ValueError, id="empty"),
        pytest.param(".", ValueError, id="dot"),
        pytest.param(3, TypeError, id="not-a-path"),
    ],
)
def test_artifact_path_rejects_escapes__tc_rr_bv_008(
    rde_runner: RdeTestRunner, tmp_path: Path, name: object, error: type[Exception],
) -> None:
    """TC-RR-BV-008: artifact names that are absolute or leave the data root are refused."""
    # Given: a finished run
    result = rde_runner.run(flow=_writes_result, project=_nested_project(tmp_path / "project"))
    # When / Then
    with pytest.raises(error, match="artifact"):
        result.artifact_path(name)  # type: ignore[arg-type]


def test_partial_run_fails_assert_success__tc_rr_bv_009(rde_runner: RdeTestRunner, tmp_path: Path) -> None:
    """TC-RR-BV-009: a partial run is not a success; the failed tile is named."""
    # Given: two tiles in MultiDataTile mode, one of which fails
    project = _nested_project(tmp_path / "project", inputs=("a.txt", "b.txt"))
    config = {"system": {"extended_mode": "MultiDataTile"}, "execution": {"on_iteration_error": "continue"}}
    # When: running it
    result = rde_runner.run(flow=_fails_on_b, project=project, config=config)
    # Then: the run is partial and assert_success says which tile failed
    assert result.status == "partial", result.report.to_json()
    assert [summary.status for summary in result.iterations] == ["completed", "failed"]
    with pytest.raises(AssertionError) as excinfo:
        result.assert_success()
    assert "'partial'" in str(excinfo.value)
    assert "iteration 1" in str(excinfo.value)
    assert "tile b is broken" in str(excinfo.value)


def test_runner_adds_no_environment_state__tc_rr_bv_010(rde_runner: RdeTestRunner, tmp_path: Path) -> None:
    """TC-RR-BV-010: running leaves the process environment as it found it."""
    # Given: a snapshot of the environment
    before = dict(os.environ)
    # When: running twice
    rde_runner.run(flow=_writes_result, project=_nested_project(tmp_path / "one"))
    rde_runner.run(flow=_failing, project=_nested_project(tmp_path / "two"))
    # Then: no variable was added, removed or changed
    assert dict(os.environ) == before


class _BytesPath:
    def __fspath__(self) -> bytes:
        return b"structured/result.csv"


def test_artifact_path_rejects_bytes_paths__tc_rr_bv_008(rde_runner: RdeTestRunner, tmp_path: Path) -> None:
    """TC-RR-BV-008 (bytes): a bytes os.PathLike is not a text artifact name."""
    # Given: a finished run
    result = rde_runner.run(flow=_writes_result, project=_nested_project(tmp_path / "project"))
    # When / Then
    with pytest.raises(TypeError, match="artifact path must be text"):
        result.artifact_path(_BytesPath())  # type: ignore[arg-type]


def test_failure_summary_without_stacktrace(tmp_path: Path) -> None:
    """A failed tile without a recorded stack trace is still described."""
    # Given: a report whose failed iteration carries no stack trace
    from rdetoolkit.report.run_report import RunReport

    report = RunReport(
        run_id="r1", status="failed", flow_id="f", mode="invoice", started_at="", duration_ms=0.0,
        config_digest="", warnings=[], error=None,
        iterations=[{"index": 0, "datatile_id": "t", "status": "failed", "error": {"code": 3001, "name": "N", "message": "m"}}],
    )
    result = _collect_result(report, project_root=tmp_path, data_root=tmp_path)
    # When
    summary = result.failure_summary(expected_status="success")
    # Then: the tile is described and no stack-trace lines are invented
    assert "iteration 0 (datatile 't') failed: [3001 N] m" in summary
    assert "    " not in summary


def test_rde_runner_fixture_stages_below_tmp_path(rde_runner: RdeTestRunner, tmp_path: Path) -> None:
    """The fixture's base directory belongs to this test's tmp_path."""
    # Given / When / Then
    assert rde_runner.base_dir.is_relative_to(tmp_path)
    shutil.rmtree(rde_runner.base_dir, ignore_errors=True)


def test_project_may_contain_the_staging_directory__tc_rr_bv_011(rde_runner: RdeTestRunner, tmp_path: Path) -> None:
    """TC-RR-BV-011: ``project=tmp_path`` with the standard fixture (staging below the project)."""
    # Given: the project is tmp_path itself, which also holds the fixture's staging directory
    project = _nested_project(tmp_path)
    before = {key: value for key, value in _tree_digest(project).items() if not key.startswith("rde_runner")}
    # When: running twice
    first = rde_runner.run(flow=_writes_result, project=project)
    second = rde_runner.run(flow=_writes_result, project=project)
    # Then: both runs succeed and neither staged copy contains the staging directory
    for result in (first, second):
        assert result.status == "success", result.failure_summary(expected_status="success")
        assert not (result.project_root / rde_runner.base_dir.name).exists()
        assert (result.data_root / "inputdata" / "sample.txt").is_file()
    assert {key: value for key, value in _tree_digest(project).items() if not key.startswith("rde_runner")} == before


def test_deeply_nested_staging_directory_is_left_out__tc_rr_bv_011(tmp_path: Path) -> None:
    """TC-RR-BV-011: a staging directory several levels below the project is not copied either."""
    # Given
    project = _nested_project(tmp_path / "project")
    runner = RdeTestRunner(project / "build" / "runs")
    (project / "build" / "keep.txt").parent.mkdir(parents=True, exist_ok=True)
    (project / "build" / "keep.txt").write_text("kept", encoding="utf-8")
    # When
    result = runner.run(flow=_writes_result, project=project)
    # Then: only the staging directory is left out; its siblings are staged
    assert result.status == "success", result.failure_summary(expected_status="success")
    assert (result.project_root / "build" / "keep.txt").read_text(encoding="utf-8") == "kept"
    assert not (result.project_root / "build" / "runs").exists()


@pytest.mark.parametrize("relation", ["same", "inside"])
def test_project_inside_the_staging_directory_is_refused__tc_rr_bv_012(tmp_path: Path, relation: str) -> None:
    """TC-RR-BV-012: the staging directory (or a directory below it) is not a project."""
    # Given
    base = tmp_path / "runs"
    project = _nested_project(base if relation == "same" else base / "nested")
    runner = RdeTestRunner(base)
    # When / Then
    if relation == "same":
        with pytest.raises(ValueError, match="staging directory"):
            runner.run(flow=_writes_result, project=project)
        assert not any(path.name.startswith("run-") for path in base.iterdir())
    else:
        # A project below the staging directory (for example a retained run) is copied normally.
        result = runner.run(flow=_writes_result, project=project)
        assert result.status == "success", result.failure_summary(expected_status="success")


@flow(id="tests.ga690.writes_nothing")
def _writes_nothing(paths: InputPaths) -> None:
    del paths


_STALE_OUTPUTS = (
    "structured/old.csv",
    "meta/metadata.json",
    "main_image/old.png",
    "raw/old.txt",
    "nonshared_raw/old.txt",
    "logs/old.log",
    "temp/old.tmp",
    "invoice_patch/old.json",
    "divided/0002/structured/old.csv",
    "job.failed",
)


@pytest.mark.parametrize("layout", ["nested", "flat"])
def test_previous_outputs_are_not_staged__tc_rr_bv_013(tmp_path: Path, layout: str) -> None:
    """TC-RR-BV-013: outputs left in the source project by an earlier run never satisfy a check of this run."""
    # Given: a project holding outputs of an earlier run next to its inputs and one unrelated file
    project = _nested_project(tmp_path / "project") if layout == "nested" else _flat_project(tmp_path / "project")
    data = project / "data" if layout == "nested" else project
    for name in _STALE_OUTPUTS:
        (data / name).parent.mkdir(parents=True, exist_ok=True)
        (data / name).write_text("stale", encoding="utf-8")
    (data / "notes.md").write_text("kept", encoding="utf-8")
    before = _tree_digest(project)
    # When: running a flow that writes nothing
    result = RdeTestRunner(tmp_path / "runs").run(flow=_writes_nothing, project=project)
    # Then: none of the earlier outputs is in the staged data root, the inputs and other files are
    assert result.status == "success", result.failure_summary(expected_status="success")
    assert result.job_failed_path is None
    for name in _STALE_OUTPUTS:
        assert not result.artifact_path(name).exists(), name
    with pytest.raises(AssertionError, match="structured/old.csv"):
        result.assert_artifact("structured/old.csv")
    assert (result.data_root / "inputdata" / "sample.txt").is_file()
    assert (result.data_root / "invoice" / "invoice.json").is_file()
    assert (result.data_root / "tasksupport" / "invoice.schema.json").is_file()
    assert (result.data_root / "notes.md").read_text(encoding="utf-8") == "kept"
    assert _tree_digest(project) == before


def test_previous_outputs_fail_expect_files__tc_rr_bv_013(tmp_path: Path) -> None:
    """TC-RR-BV-013: ``rde_case(expect_files=...)`` fails for a file only an earlier run wrote."""
    from rdetoolkit.testing.case import case_from_marker, check_case  # noqa: PLC0415

    # Given
    project = _nested_project(tmp_path / "project")
    (project / "data" / "structured").mkdir()
    (project / "data" / "structured" / "result.csv").write_text("stale", encoding="utf-8")
    case = case_from_marker((), {"flow": _writes_nothing, "project": project, "expect_files": ["structured/result.csv"]}, rootpath=tmp_path)
    # When
    result = RdeTestRunner(tmp_path / "runs").run(flow=_writes_nothing, project=project)
    failures = check_case(case, result)
    # Then
    assert any("structured/result.csv" in failure for failure in failures), failures
