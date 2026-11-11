"""Issue #600: null mode normalization and public Runner config discovery.

EP/BV table: local/develop/v2/review/issue600_20261111/test_design.md.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest
from hypothesis import given, strategies as st
from pydantic import ValidationError

import rdetoolkit.runner as runner_api
from rdetoolkit import flow, workflows
from rdetoolkit.errors import RdeConfigError
from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.runner.mode_resolver import ModeKind, resolve_mode
from rdetoolkit.types import RdeConfig, V2SystemSettings
from tests.v2.contract.fixtures import _generate


@pytest.mark.parametrize("model", [RdeConfig, V2SystemSettings])
def test_null_mode_is_unset_without_mutation__tc_600_ep_001(model: type[RdeConfig | V2SystemSettings]) -> None:
    """TC-600-EP-001: null means implicit invoice and preserves sibling fields."""
    # Given: a caller-owned configuration mapping containing a null mode
    settings = {"extended_mode": None, "save_raw": True}
    source = {"system": settings} if model is RdeConfig else settings
    original = copy.deepcopy(source)
    # When: the public model validates the mapping
    result = model.model_validate(source)
    system = result.system if isinstance(result, RdeConfig) else result
    # Then: only the null mode is omitted from explicitly configured fields
    assert system.extended_mode == "invoice"
    assert system.model_fields_set == {"save_raw"}
    assert source == original


@pytest.mark.parametrize("layout", ["nested", "data", "alias"])
@pytest.mark.parametrize("as_string", [False, True])
def test_helper_resolves_data_layout__tc_600_ep_002(tmp_path: Path, layout: str, as_string: bool) -> None:
    """TC-600-EP-002: the helper accepts the Runner's project and data roots."""
    # Given: a legacy tasksupport file in one of the supported data layouts
    root = tmp_path / ("data" if layout == "data" else "project")
    data_root = root / "data" if layout == "nested" else root
    support = data_root / "tasksupport"
    support.mkdir(parents=True)
    (support / "rdeconfig.yaml").write_text("system:\n  save_raw: true\ncustom:\n  label: legacy\n", encoding="utf-8")
    # When: loading through the public runner package
    config = runner_api.load_run_config(str(root) if as_string else root)
    # Then: legacy settings and legacy execution defaults are used
    assert config.system.save_raw is True
    assert config.custom == {"label": "legacy"}
    assert config.execution.on_iteration_error == "fail_fast"


@pytest.mark.parametrize(
    ("filename", "content"),
    [("rdeconfig.yaml", "custom:\n  label: root\n"), ("pyproject.toml", '[tool.rdetoolkit.custom]\nlabel = "root"\n')],
)
def test_project_config_has_priority__tc_600_ep_003(tmp_path: Path, filename: str, content: str) -> None:
    """TC-600-EP-003: root config takes priority over broken legacy material."""
    # Given: a valid project config and invalid lower-priority tasksupport config
    support = tmp_path / "data" / "tasksupport"
    support.mkdir(parents=True)
    (support / "rdeconfig.yaml").write_text("system: [broken\n", encoding="utf-8")
    (tmp_path / filename).write_text(content, encoding="utf-8")
    if filename == "rdeconfig.yaml":
        (tmp_path / "pyproject.toml").write_text('[tool.rdetoolkit.custom]\nlabel = "toml"\n', encoding="utf-8")
    # When: discovering configuration from the project root
    config = runner_api.load_run_config(tmp_path)
    # Then: the root configuration is authoritative
    assert config.custom == {"label": "root"}
    assert config.execution.on_iteration_error == "continue"


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("rdeconfig.yaml", "system:\n  extended_mode: null\n  save_raw: true\n"),
        ("rdeconfig.yml", "system:\n  extended_mode: null\n  save_raw: true\n"),
        ("pyproject.toml", "[tool.rdetoolkit.system]\nsave_raw = true\n"),
    ],
)
def test_legacy_fallback_with_unrelated_project_toml__tc_600_ep_004(tmp_path: Path, filename: str, content: str) -> None:
    """TC-600-EP-004: unrelated project metadata does not hide legacy config."""
    # Given: project metadata without a tool table and legacy tasksupport config
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "sample"\n', encoding="utf-8")
    support = tmp_path / "data" / "tasksupport"
    support.mkdir(parents=True)
    (support / filename).write_text(content, encoding="utf-8")
    # When: using the helper's complete discovery chain
    config = runner_api.load_run_config(tmp_path)
    # Then: the v1 file is normalized, including its implicit mode
    assert config.system.save_raw is True
    assert config.execution.on_iteration_error == "fail_fast"
    assert "extended_mode" not in config.system.model_fields_set


def test_nested_overrides_preserve_sources__tc_600_ep_005(tmp_path: Path) -> None:
    """TC-600-EP-005: mapping overrides retain unrelated values without mutation."""
    # Given: file values and a read-only override containing nested custom data
    path = tmp_path / "rdeconfig.yaml"
    content = "system:\n  save_raw: true\ncustom:\n  group:\n    keep: 1\n    replace: old\n"
    path.write_text(content, encoding="utf-8")
    overrides = MappingProxyType({"system": {"extended_mode": "MultiDataTile"}, "custom": {"group": {"replace": [2]}}})
    original = copy.deepcopy(dict(overrides))
    # When: loading and modifying the resulting configuration
    config = runner_api.load_run_config(tmp_path, overrides=overrides)
    config.custom["group"]["replace"].append(3)
    # Then: deep merge preserves siblings and owns its mutable results
    assert config.system.extended_mode == "MultiDataTile"
    assert config.system.model_fields_set == {"save_raw", "extended_mode"}
    assert config.custom["group"] == {"keep": 1, "replace": [2, 3]}
    assert dict(overrides) == original
    assert path.read_text(encoding="utf-8") == content


def test_null_override_clears_discovered_mode__tc_600_ep_006(tmp_path: Path) -> None:
    """TC-600-EP-006: a null override removes an explicit file mode."""
    # Given: an explicit mode discovered from a project file
    (tmp_path / "rdeconfig.yaml").write_text("system:\n  extended_mode: MultiDataTile\n  save_raw: true\n", encoding="utf-8")
    # When: an override clears that mode
    config = runner_api.load_run_config(tmp_path, overrides={"system": {"extended_mode": None}})
    # Then: the resulting invoice default is implicit and sibling values remain
    assert config.system.extended_mode == "invoice"
    assert config.system.model_fields_set == {"save_raw"}
    assert config.system.save_raw is True


@flow
def _observe_config(config: RdeConfig) -> None:
    assert config.system.save_raw is True
    assert config.custom["label"] == "retained"


@pytest.mark.parametrize("location", ["root", "tasksupport"])
@pytest.mark.parametrize("mode", [None, "MultiDataTile"])
def test_helper_and_mapping_runs_share_digest__tc_600_ep_007(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, location: str, mode: str | None,
) -> None:
    """TC-600-EP-007: preloaded objects and mapping overrides produce the same run config."""
    # Given: valid invoice inputs and discovered settings unrelated to the override
    _generate.materialize_sut_case("invoice", tmp_path)
    config_dir = tmp_path if location == "root" else tmp_path / "data" / "tasksupport"
    (config_dir / "rdeconfig.yaml").write_text("system:\n  save_raw: true\ncustom:\n  label: retained\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    overrides = {"system": {"extended_mode": mode}}
    # When: the public entry runs with the helper's object and with the mapping
    preloaded = workflows.run(flow=_observe_config, config=runner_api.load_run_config(overrides=overrides))
    mapped = workflows.run(flow=_observe_config, config=overrides)
    # Then: both successful runs use precisely the same effective configuration
    assert preloaded.status == mapped.status == "success"
    assert preloaded.config_digest == mapped.config_digest
    assert preloaded.config_digest.startswith("sha256:")


@pytest.mark.parametrize(
    "overrides",
    [
        {"unknown": True}, {"system": {"typo": True}}, {"execution": {"typo": True}},
        {"provenance": {"lineage": True}}, {"smarttable": {"typo": True}},
        {"system": []}, {"system": {"extended_mode": 1}}, {"system": {"save_raw": "invalid"}},
        {"execution": {"on_iteration_error": "invalid"}}, {"provenance": {"repr_head": "invalid"}},
        {"custom": []},
    ],
)
def test_invalid_overrides_raise_catalogued_error__tc_600_neg_001(tmp_path: Path, overrides: Mapping[str, Any]) -> None:
    """TC-600-NEG-001: invalid overrides keep the strict v2 error contract."""
    # Given: overrides outside the canonical configuration contract
    # When: loading through the public helper
    with pytest.raises(RdeConfigError) as caught:
        runner_api.load_run_config(tmp_path, overrides=overrides)
    # Then: the normalizer's catalogued configuration error propagates
    assert caught.value.code == 1002


@pytest.mark.parametrize(
    ("relative", "content"),
    [
        ("rdeconfig.yaml", "system: [broken\n"), ("rdeconfig.yaml", "- not-a-mapping\n"),
        ("rdeconfig.yaml", "system:\n  unknown: true\n"), ("pyproject.toml", "[broken\n"),
        ("data/tasksupport/rdeconfig.yaml", "system: [broken\n"),
        ("data/tasksupport/rdeconfig.yaml", "system:\n  extended_mode: invalid\n"),
        ("data/tasksupport/rdeconfig.yml", "system: [broken\n"),
        ("data/tasksupport/pyproject.toml", "[broken\n"),
    ],
)
def test_invalid_discovered_files_raise_catalogued_error__tc_600_neg_002(tmp_path: Path, relative: str, content: str) -> None:
    """TC-600-NEG-002: invalid discovered material is never silently ignored."""
    # Given: an invalid file at a supported discovery location
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    # When: discovering the effective configuration
    with pytest.raises(RdeConfigError) as caught:
        runner_api.load_run_config(tmp_path)
    # Then: the public error type and integer code are retained
    assert caught.value.code == 1002


@flow
def _noop_flow() -> None:
    pass


@pytest.mark.parametrize("mode", ["smarttable", "excelinvoice"])
@pytest.mark.parametrize("source", ["object", "mapping", "helper"])
def test_null_mode_does_not_warn_on_detection__tc_600_neg_003(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], mode: str, source: str,
) -> None:
    """TC-600-NEG-003: null mode is implicit for object, mapping and helper sources."""
    # Given: real detected-mode input and a null mode configuration
    _generate.materialize_sut_case(mode, tmp_path)
    monkeypatch.chdir(tmp_path)
    overrides = {"system": {"extended_mode": None}}
    config = overrides if source == "mapping" else (
        RdeConfig.model_validate(overrides) if source == "object" else runner_api.load_run_config(overrides=overrides)
    )
    # When: the public flow entry executes
    report = workflows.run(flow=_noop_flow, config=config)
    # Then: detection succeeds without a conflict warning in any output
    assert report.status == "success"
    assert report.mode == mode
    assert 1001 not in [warning.code for warning in report.warnings]
    events = [
        json.loads(line)
        for path in (tmp_path / "data" / "logs").glob("events_*.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert any(event.get("name") == "run.started" for event in events)
    assert all(event["payload"].get("code") != 1001 for event in events if event.get("name") == "warning")
    assert "ModeOverriddenByFileDetection" not in capsys.readouterr().err


@pytest.mark.parametrize("filename", ["smarttable_data.xlsx", "data_excel_invoice.xlsx"])
@pytest.mark.parametrize("configured", ["invoice", "MultiDataTile"])
def test_explicit_helper_mode_still_warns__tc_600_neg_004(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], filename: str, configured: str,
) -> None:
    """TC-600-NEG-004: a helper override remains explicit for W1001."""
    # Given: input detection conflicting with a non-null helper override
    inputdata = tmp_path / "inputdata"
    inputdata.mkdir()
    (inputdata / filename).touch()
    config = runner_api.load_run_config(tmp_path, overrides={"system": {"extended_mode": configured}})
    sink = MemoryEventSink()
    sink.open("issue600")
    # When: resolving the mode using the loaded config
    mode = resolve_mode(config, inputdata, tmp_path / "temp", sink, "issue600")
    # Then: the conflict warning is preserved in the event stream and stderr
    assert mode in {ModeKind.smarttable, ModeKind.excelinvoice}
    assert "extended_mode" in config.system.model_fields_set
    assert [event.payload["code"] for event in sink.events if event.name == "warning"] == [1001]
    assert "ModeOverriddenByFileDetection" in capsys.readouterr().err


@pytest.mark.parametrize("settings", [{"extended_mode": value} for value in [1, False, [], {}]] + [{"extended_mode": None, "unknown": True}])
def test_null_support_keeps_model_strict__tc_600_neg_005(settings: dict[str, Any]) -> None:
    """TC-600-NEG-005: accepting null does not accept invalid values or extra keys."""
    # Given: non-null invalid data or an unknown sibling alongside null
    # When: validating the public canonical model
    with pytest.raises(ValidationError) as caught:
        RdeConfig.model_validate({"system": settings})
    # Then: the model identifies the offending field under system
    field = "unknown" if "unknown" in settings else "extended_mode"
    assert caught.value.errors()[0]["loc"] == ("system", field)


@pytest.mark.parametrize("overrides", [None, {}])
def test_no_files_defaults_to_cwd_without_side_effects__tc_600_bv_001(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, overrides: Mapping[str, Any] | None,
) -> None:
    """TC-600-BV-001: omitted root and empty input use defaults without creating directories."""
    # Given: an empty current project directory
    monkeypatch.chdir(tmp_path)
    # When: loading with no explicit root and no effective overrides
    config = runner_api.load_run_config(overrides=overrides)
    # Then: canonical defaults are returned without filesystem writes
    assert config == RdeConfig()
    assert config.system.model_fields_set == set()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.property
@given(st.dictionaries(st.sampled_from(["save_raw", "save_nonshared_raw", "magic_variable"]), st.booleans()))
def test_null_normalization_is_idempotent__tc_600_pbt_001(settings: dict[str, bool]) -> None:
    """TC-600-PBT-001: null removal preserves values, explicit siblings and caller ownership."""
    # Given: arbitrary sibling settings and a caller-owned null mode
    source = {"system": {**settings, "extended_mode": None}}
    original = copy.deepcopy(source)
    # When: validating the null form and revalidating its explicit dump
    once = RdeConfig.model_validate(source)
    twice = RdeConfig.model_validate(once.model_dump(exclude_unset=True))
    # Then: normalization is idempotent and equivalent to omitting the mode
    assert once == twice == RdeConfig.model_validate({"system": settings})
    assert once.system.model_fields_set == twice.system.model_fields_set == set(settings)
    assert source == original
