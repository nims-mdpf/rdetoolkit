"""An ``RdeConfig`` object passed to the Runner is used as-is.

A v1 ``Config`` object has always been used without reading any config file.
An ``RdeConfig`` object was instead dumped in full and merged over the
discovered files, which turned every default (including
``system.extended_mode``) into an "explicitly set" value: a plain
``RdeConfig()`` with SmartTable or ExcelInvoice input published a false W1001.
Both object kinds now mean "this is the config"; mappings keep their override
semantics.

Test design (equivalence partitioning / boundary values):

    Case               | Source                                         | Expected
    -------------------|------------------------------------------------|------------------------------------------
    TC-C02R1-EP-001    | ``RdeConfig()`` + root rdeconfig.yaml           | file not read; values equal the object
    TC-C02R1-EP-002    | ``RdeConfig()`` + SmartTable / ExcelInvoice     | mode detected, no W1001
    TC-C02R1-EP-003    | ``RdeConfig(execution=...)`` + tasksupport file | tasksupport values not merged in
    TC-C02R1-EP-004    | mapping overrides + root rdeconfig.yaml         | still merged over the file (unchanged)
    TC-C02R1-EP-005    | ``workflows.run(flow=..., config=RdeConfig())`` | no W1001 in events or report
    TC-C02R1-NEG-001   | ``RdeConfig`` with explicit extended_mode       | conflicting detection still warns W1001
    TC-C02R1-BV-001    | the passed object                               | Runner does not mutate it
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rdetoolkit import flow, workflows
from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import RdeConfig
from tests.v2.contract.fixtures import _generate

_W1001 = 1001
_SMARTTABLE_FILE = "smarttable_data.xlsx"
_EXCELINVOICE_FILE = "data_excel_invoice.xlsx"


def _runner(root: Path, filename: str | None = None) -> tuple[Runner, MemoryEventSink]:
    inputdata = root / "inputdata"
    inputdata.mkdir(parents=True, exist_ok=True)
    if filename is not None:
        (inputdata / filename).touch()
    sink = MemoryEventSink()
    sink.open("c02r1")
    runner = Runner(root=root, inputdata_path=inputdata, unpacked_dir_path=root / "temp", event_sink=sink)
    runner.run_id = "c02r1"
    return runner, sink


def _warning_codes(sink: MemoryEventSink) -> list[object]:
    return [event.payload.get("code") for event in sink.events if event.name == "warning"]


def test_rdeconfig_object_does_not_read_config_files__tc_c02r1_ep_001(tmp_path: Path) -> None:
    """TC-C02R1-EP-001: the object is the whole config; a project file is not merged in."""
    # Given: a root rdeconfig.yaml and an RdeConfig object that sets nothing
    (tmp_path / "rdeconfig.yaml").write_text("custom:\n  label: from-file\nsystem:\n  save_raw: true\n", encoding="utf-8")
    runner, _ = _runner(tmp_path)
    # When: the Runner loads the config from that object
    config = runner.load_config(RdeConfig())
    # Then: the effective config is the object's values, not the file's
    assert config.model_dump() == RdeConfig().model_dump()


@pytest.mark.parametrize(
    ("filename", "expected_mode"),
    [(_SMARTTABLE_FILE, ModeKind.smarttable), (_EXCELINVOICE_FILE, ModeKind.excelinvoice)],
    ids=["smarttable", "excelinvoice"],
)
def test_default_rdeconfig_object_emits_no_w1001__tc_c02r1_ep_002(
    tmp_path: Path,
    filename: str,
    expected_mode: ModeKind,
) -> None:
    """TC-C02R1-EP-002: a default object leaves the mode implicit, so detection is not a conflict."""
    # Given: SmartTable or ExcelInvoice input and RdeConfig()
    runner, sink = _runner(tmp_path, filename)
    # When: the config is loaded and the mode resolved
    config = runner.load_config(RdeConfig())
    mode = runner.resolve_mode(config)
    # Then: detection decides and no W1001 is published
    assert mode is expected_mode
    assert "extended_mode" not in config.system.model_fields_set
    assert _warning_codes(sink) == []


def test_rdeconfig_object_ignores_tasksupport_file__tc_c02r1_ep_003(tmp_path: Path) -> None:
    """TC-C02R1-EP-003: fields the object did not set keep the object's defaults, not file values."""
    # Given: a tasksupport file setting system values, and an object that sets only execution
    (tmp_path / "tasksupport").mkdir()
    (tmp_path / "tasksupport" / "rdeconfig.yaml").write_text("system:\n  save_raw: true\n", encoding="utf-8")
    runner, _ = _runner(tmp_path)
    source = RdeConfig.model_validate({"execution": {"on_iteration_error": "fail_fast"}})
    # When
    config = runner.load_config(source)
    # Then: execution comes from the object and system keeps the object's defaults
    assert config.execution.on_iteration_error == "fail_fast"
    assert config.system.save_raw is RdeConfig().system.save_raw


def test_mapping_source_still_overrides_files__tc_c02r1_ep_004(tmp_path: Path) -> None:
    """TC-C02R1-EP-004: a mapping keeps its patch semantics over the discovered file."""
    # Given: a root file and a mapping that overrides one key
    (tmp_path / "rdeconfig.yaml").write_text("custom:\n  label: from-file\nsystem:\n  save_raw: true\n", encoding="utf-8")
    runner, _ = _runner(tmp_path)
    # When
    config = runner.load_config({"custom": {"label": "override"}})
    # Then: the override wins and the file's other values are kept
    assert config.custom == {"label": "override"}
    assert config.system.save_raw is True


@flow
def _noop_flow() -> None:
    return None


@pytest.mark.parametrize("mode", ["smarttable", "excelinvoice"])
def test_workflows_run_with_default_rdeconfig_emits_no_w1001__tc_c02r1_ep_005(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    """TC-C02R1-EP-005: the public flow entry with RdeConfig() publishes no W1001."""
    # Given: a SmartTable / ExcelInvoice input tree and a no-op flow
    _generate.materialize_sut_case(mode, tmp_path)
    monkeypatch.chdir(tmp_path)
    # When: the flow entry runs with a default RdeConfig object
    report = workflows.run(flow=_noop_flow, config=RdeConfig())
    # Then: the detected mode is used and neither the events nor the report carry W1001
    assert report.mode == mode
    assert _W1001 not in [warning.code for warning in report.warnings]
    logs = tmp_path / "data" / "logs"
    codes = [
        json.loads(line)["payload"].get("code")
        for path in sorted(logs.glob("events_*.jsonl"))
        for line in path.read_text(encoding="utf-8").splitlines()
        if json.loads(line).get("name") == "warning"
    ]
    assert _W1001 not in codes


def test_explicit_mode_in_rdeconfig_object_still_warns__tc_c02r1_neg_001(tmp_path: Path) -> None:
    """TC-C02R1-NEG-001: a mode the object really sets is explicit, so a conflicting detection warns."""
    # Given: SmartTable input and an object that explicitly asks for MultiDataTile
    runner, sink = _runner(tmp_path, _SMARTTABLE_FILE)
    source = RdeConfig.model_validate({"system": {"extended_mode": "MultiDataTile"}})
    # When
    config = runner.load_config(source)
    mode = runner.resolve_mode(config)
    # Then: detection wins and W1001 is published
    assert mode is ModeKind.smarttable
    assert _warning_codes(sink) == [_W1001]


def test_runner_does_not_mutate_the_passed_object__tc_c02r1_bv_001(tmp_path: Path) -> None:
    """TC-C02R1-BV-001: the caller's object is not the Runner's working copy."""
    # Given: an object the caller keeps using
    source = RdeConfig.model_validate({"custom": {"items": [1]}})
    runner, _ = _runner(tmp_path)
    # When: the Runner loads it and the result is changed
    config = runner.load_config(source)
    config.custom["items"].append(2)
    # Then: the caller's object is unchanged
    assert source.custom == {"items": [1]}
