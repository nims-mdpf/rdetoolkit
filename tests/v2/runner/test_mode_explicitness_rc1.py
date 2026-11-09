"""An implicit ``extended_mode`` must stay implicit through loading (RC1 C02).

Review ``interrogate_v2.0.0rc1`` C02: ``runner/config_loader.load_config``
dumped the defaulted model (every field) and re-normalized it, so
``extended_mode`` landed in ``model_fields_set`` and a SmartTable /
ExcelInvoice input with no config file emitted W1001. The v1 origin had the
same defect: ``ConfigNormalizer._convert_v1`` wrote ``extended_mode="invoice"``
whenever the v1 value was absent. Design §6.2 / §507: W1001 is published only
when an **explicitly configured** mode conflicts with file detection. The
resolved mode must not change for any input.

EP table:
| TC | Source | Input | Expected |
|----|--------|-------|----------|
| TC-RC1-C02-EP-001 | v2, no config file | SmartTable / ExcelInvoice | resolved by detection, no W1001 |
| TC-RC1-C02-EP-002 | v2 overrides without a mode | SmartTable | no W1001 |
| TC-RC1-C02-EP-003 | v1 tasksupport file without a mode | SmartTable | no W1001 |
| TC-RC1-C02-EP-004 | ``workflows.run(config=Config())`` | SmartTable / ExcelInvoice | no W1001 |
| TC-RC1-C02-EP-005 | ``workflows.run(config=None)``, no file | SmartTable | no W1001 |

BV / negative table:
| TC | Source | Input | Expected |
|----|--------|-------|----------|
| TC-RC1-C02-NEG-001 | v2 ``rdeconfig.yaml`` ``extended_mode: invoice`` | SmartTable | W1001 |
| TC-RC1-C02-NEG-002 | v2 override ``extended_mode: MultiDataTile`` | ExcelInvoice | W1001 |
| TC-RC1-C02-NEG-003 | v1 tasksupport ``extended_mode: MultiDataTile`` | SmartTable | W1001 |
| TC-RC1-C02-NEG-004 | ``workflows.run`` v1 ``MultiDataTile`` | SmartTable / ExcelInvoice | W1001 |
| TC-RC1-C02-BV-001 | no config, plain invoice input | invoice | no W1001, mode invoice, value unchanged |
| TC-RC1-C02-BV-002 | nested unset sections | v2 config file setting one system key | other sections still defaults |
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.models.config import Config, SystemSettings
from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.runner.config_loader import load_config
from rdetoolkit.runner.mode_resolver import ModeKind, resolve_mode
from rdetoolkit.types import RdeConfig
from tests.v2.contract.fixtures import _generate

_W1001 = 1001
_SMARTTABLE_FILE = "smarttable_data.xlsx"
_EXCELINVOICE_FILE = "data_excel_invoice.xlsx"


def _detect(root: Path, filename: str, overrides: dict[str, Any] | None = None) -> tuple[RdeConfig, ModeKind, list[int]]:
    """Load the config like the Runner does and resolve the mode for one input file."""
    inputdata = root / "inputdata"
    inputdata.mkdir(parents=True, exist_ok=True)
    (inputdata / filename).touch()
    config = load_config(root, overrides, data_root=root)
    sink = MemoryEventSink()
    sink.open("rc1-c02")
    mode = resolve_mode(config, inputdata, root / "temp", sink, "rc1-c02")
    codes = [event.payload.get("code") for event in sink.events if event.name == "warning"]
    return config, mode, codes


class TestV2LoaderKeepsTheModeImplicit:
    @pytest.mark.parametrize(
        ("filename", "expected_mode"),
        [(_SMARTTABLE_FILE, ModeKind.smarttable), (_EXCELINVOICE_FILE, ModeKind.excelinvoice)],
        ids=["smarttable", "excelinvoice"],
    )
    def test_no_config_file_emits_no_w1001__tc_rc1_c02_ep_001(self, tmp_path: Path, filename: str, expected_mode: ModeKind) -> None:
        # Given: no configuration file anywhere
        # When: the config is loaded and the mode resolved
        config, mode, codes = _detect(tmp_path, filename)

        # Then: detection decides, the mode is still implicit, and nothing is warned
        assert mode is expected_mode
        assert "extended_mode" not in config.system.model_fields_set
        assert config.system.extended_mode == "invoice"
        assert codes == []

    def test_overrides_without_a_mode_emit_no_w1001__tc_rc1_c02_ep_002(self, tmp_path: Path) -> None:
        # Given: an override that touches another system key only
        # When
        config, mode, codes = _detect(tmp_path, _SMARTTABLE_FILE, {"system": {"save_raw": False}})

        # Then: the override applies and the mode stays implicit
        assert config.system.save_raw is False
        assert mode is ModeKind.smarttable
        assert codes == []

    def test_v1_tasksupport_file_without_a_mode_emits_no_w1001__tc_rc1_c02_ep_003(self, tmp_path: Path) -> None:
        # Given: a v1 tasksupport file that configures something else
        (tmp_path / "tasksupport").mkdir()
        (tmp_path / "tasksupport" / "rdeconfig.yaml").write_text("system:\n  save_raw: false\n", encoding="utf-8")

        # When
        config, mode, codes = _detect(tmp_path, _SMARTTABLE_FILE)

        # Then: the v1 value is honoured and the mode is still implicit
        assert config.system.save_raw is False
        assert config.execution.on_iteration_error == "fail_fast"
        assert mode is ModeKind.smarttable
        assert codes == []

    def test_plain_invoice_input_is_unchanged__tc_rc1_c02_bv_001(self, tmp_path: Path) -> None:
        # Given: no config and an ordinary input
        # When
        config, mode, codes = _detect(tmp_path, "sample.txt")

        # Then: the resolved mode and the effective value are what they always were
        assert mode is ModeKind.invoice
        assert config.model_dump() == RdeConfig().model_dump()
        assert codes == []

    def test_unset_nested_sections_keep_their_defaults__tc_rc1_c02_bv_002(self, tmp_path: Path) -> None:
        # Given: a v2 config file setting a single system key
        (tmp_path / "rdeconfig.yaml").write_text("system:\n  save_thumbnail_image: true\n", encoding="utf-8")

        # When
        config, _, codes = _detect(tmp_path, _SMARTTABLE_FILE)

        # Then: the loaded value is the default model plus that key
        expected = RdeConfig().model_dump()
        expected["system"]["save_thumbnail_image"] = True
        assert config.model_dump() == expected
        assert config.system.model_fields_set == {"save_thumbnail_image"}
        assert codes == []

    def test_explicit_invoice_in_rdeconfig_still_warns__tc_rc1_c02_neg_001(self, tmp_path: Path) -> None:
        # Given: an explicit invoice mode in the project rdeconfig.yaml
        (tmp_path / "rdeconfig.yaml").write_text("system:\n  extended_mode: invoice\n", encoding="utf-8")

        # When
        config, mode, codes = _detect(tmp_path, _SMARTTABLE_FILE)

        # Then: detection still wins, and the explicit conflict is published
        assert "extended_mode" in config.system.model_fields_set
        assert mode is ModeKind.smarttable
        assert codes == [_W1001]

    def test_explicit_override_mode_still_warns__tc_rc1_c02_neg_002(self, tmp_path: Path) -> None:
        # Given / When: an override configuring MultiDataTile
        _, mode, codes = _detect(tmp_path, _EXCELINVOICE_FILE, {"system": {"extended_mode": "MultiDataTile"}})

        # Then
        assert mode is ModeKind.excelinvoice
        assert codes == [_W1001]

    def test_explicit_v1_tasksupport_mode_still_warns__tc_rc1_c02_neg_003(self, tmp_path: Path) -> None:
        # Given: a v1 tasksupport file configuring MultiDataTile
        (tmp_path / "tasksupport").mkdir()
        (tmp_path / "tasksupport" / "rdeconfig.yaml").write_text("system:\n  extended_mode: MultiDataTile\n", encoding="utf-8")

        # When
        config, mode, codes = _detect(tmp_path, _SMARTTABLE_FILE)

        # Then
        assert config.system.extended_mode == "MultiDataTile"
        assert mode is ModeKind.smarttable
        assert codes == [_W1001]


def _noop_callback(srcpaths: object, resource_paths: object) -> None:
    del srcpaths, resource_paths


def _materialize(mode: str, root: Path) -> Path:
    _generate.materialize_sut_case(mode, root)
    return root


def _run_v1_entry(root: Path, config: Config | None, monkeypatch: pytest.MonkeyPatch) -> tuple[str, list[int]]:
    """Run ``workflows.run`` on a materialized input; return (resolved mode, warning codes)."""
    from rdetoolkit import workflows  # noqa: PLC0415

    monkeypatch.chdir(root)
    try:
        workflows.run(custom_dataset_function=_noop_callback, config=config)
    except SystemExit:
        pass
    logs = root / "data" / "logs"
    report_path = next(iter(sorted(logs.glob("run_report_*.json"))))
    resolved = json.loads(report_path.read_text(encoding="utf-8"))["mode"]
    codes: list[int] = []
    for events_path in sorted(logs.glob("events_*.jsonl")):
        for line in events_path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record.get("name") == "warning":
                codes.append(record["payload"]["code"])
    return resolved, codes


class TestV1EntryKeepsTheModeImplicit:
    @pytest.mark.parametrize("mode", ["smarttable", "excelinvoice"])
    def test_default_v1_config_emits_no_w1001__tc_rc1_c02_ep_004(
        self, mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
    ) -> None:
        # Given: a v1 job whose Config() never sets the mode
        # When: the public v1 entry point runs
        resolved, codes = _run_v1_entry(_materialize(mode, tmp_path / mode), Config(), monkeypatch)

        # Then: the detected mode is used and no W1001 is published anywhere
        assert resolved == mode
        assert codes == []
        assert "ModeOverriddenByFileDetection" not in capfd.readouterr().err

    def test_config_none_without_file_emits_no_w1001__tc_rc1_c02_ep_005(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
    ) -> None:
        # Given: config=None and no tasksupport rdeconfig at all
        root = _materialize("smarttable", tmp_path / "smarttable")
        for name in ("rdeconfig.yaml", "rdeconfig.yml", "pyproject.toml"):
            (root / "data" / "tasksupport" / name).unlink(missing_ok=True)

        # When
        resolved, codes = _run_v1_entry(root, None, monkeypatch)

        # Then
        assert resolved == "smarttable"
        assert codes == []
        assert "ModeOverriddenByFileDetection" not in capfd.readouterr().err

    @pytest.mark.parametrize("mode", ["smarttable", "excelinvoice"])
    def test_explicit_v1_mode_conflict_still_warns__tc_rc1_c02_neg_004(
        self, mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
    ) -> None:
        # Given: a v1 job that explicitly configures MultiDataTile
        config = Config(system=SystemSettings(extended_mode="MultiDataTile"))

        # When
        resolved, codes = _run_v1_entry(_materialize(mode, tmp_path / mode), config, monkeypatch)

        # Then: detection still wins, and the conflict is published once
        assert resolved == mode
        assert codes == [_W1001]
        assert "ModeOverriddenByFileDetection" in capfd.readouterr().err
