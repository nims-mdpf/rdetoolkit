"""GA #695: ``execution.type_check`` accepts exactly ``off`` / ``warn`` / ``strict``.

Before #695 the strict ``RdeConfig`` model declared ``type_check: str``, so a
typo such as ``strcit`` loaded silently and the recorder treated every
non-``off``/non-``warn`` value like ``strict``. The setting is now a
``Literal`` and an unknown value is rejected at configuration load time
through the existing E1002 path, naming the key and the valid options.

EP table:

| Class | Input | Expected | Test ID |
|---|---|---|---|
| valid | ``off`` / ``warn`` / ``strict`` | loaded unchanged | TC-695-EP-001 |
| valid | key omitted | ``off`` default | TC-695-EP-002 |
| invalid | misspelling ``strcit`` | E1002 | TC-695-EP-003 |
| invalid | wrong case ``Strict`` / ``WARN`` / ``Off`` | E1002 | TC-695-EP-003 |
| invalid | ``None`` / list / int / bool | E1002 | TC-695-EP-003 |
| invalid | padded `` strict`` / empty string | E1002 | TC-695-EP-003 |
| source | explicit ``RdeConfig(...)`` | ValidationError | TC-695-EP-004 |
| source | discovered ``rdeconfig.yaml`` / ``pyproject.toml`` | E1002 | TC-695-EP-005 |
| source | mapping override over valid YAML | E1002 / override wins | TC-695-EP-006 |
| source | nested merge keeps sibling keys | both keys effective | TC-695-EP-007 |
| entry | ``Runner.run(validate_only=True)`` | failed report, code 1002 | TC-695-EP-008 |
| entry | ``rdetoolkit run --flow ... --validate-only`` | exit 1, flow never called | TC-695-EP-009 |
| v1 | normalized v1 configuration | ``fail_fast`` + ``off`` unchanged | TC-695-EP-010 |
| runtime | valid value reaches the recorder | same mode string | TC-695-EP-011 |

BV: the valid set is closed — the case boundary (``strict`` vs ``Strict``) and
whitespace boundary (``strict`` vs `` strict``) are both rejected.
"""

from __future__ import annotations

import json
import typing
from pathlib import Path
from typing import Any, Literal

import pytest
import yaml
from pydantic import ValidationError
from typer.testing import CliRunner

from rdetoolkit.api.request import build_run_request
from rdetoolkit.cli.app import app
from rdetoolkit.config.normalize import ConfigNormalizer
from rdetoolkit.errors import RdeConfigError
from rdetoolkit.runner.config_loader import load_config
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import RdeConfig, V2ExecutionSettings

FIXTURE_MODULE = "tests.v2.cli.fixtures.run_flows"

VALID_VALUES = ("off", "warn", "strict")

INVALID_VALUES: list[Any] = [
    pytest.param("strcit", id="misspelled"),
    pytest.param("Strict", id="capitalized"),
    pytest.param("WARN", id="upper-case"),
    pytest.param("Off", id="title-case-off"),
    pytest.param(" strict", id="leading-space"),
    pytest.param("", id="empty-string"),
    pytest.param(None, id="none"),
    pytest.param(["strict"], id="list"),
    pytest.param(1, id="integer"),
    pytest.param(True, id="bool"),
]


def _assert_actionable_1002(error: RdeConfigError) -> None:
    """The E1002 message names the offending key and every valid option."""
    assert error.code == 1002
    message = str(error)
    assert "execution.type_check" in message
    for option in VALID_VALUES:
        assert f"'{option}'" in message


def _write_yaml(root: Path, data: dict[str, Any]) -> None:
    (root / "rdeconfig.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


class TestModelAnnotation:
    """TC-695-EP-001/002: the public model declares the closed value set."""

    def test_annotation_is_closed_literal__tc_695_ep_001(self) -> None:
        # Given: the strict v2 execution settings model
        # When: its type_check annotation is inspected
        annotation = V2ExecutionSettings.model_fields["type_check"].annotation
        # Then: it is exactly the three-value Literal (not a bare str)
        assert typing.get_origin(annotation) is Literal
        assert set(typing.get_args(annotation)) == set(VALID_VALUES)

    def test_default_is_off__tc_695_ep_002(self) -> None:
        # Given/When: an execution section without type_check
        settings = V2ExecutionSettings()
        # Then: the default is unchanged
        assert settings.type_check == "off"
        assert RdeConfig().execution.type_check == "off"

    @pytest.mark.parametrize("value", VALID_VALUES)
    def test_valid_values_load_unchanged__tc_695_ep_001(self, value: str) -> None:
        # Given/When: each valid value through the explicit model
        config = RdeConfig(execution={"type_check": value})
        # Then: it is stored verbatim
        assert config.execution.type_check == value


class TestExplicitModelRejects:
    """TC-695-EP-004: an explicit ``RdeConfig(...)`` rejects invalid values."""

    @pytest.mark.parametrize("value", INVALID_VALUES)
    def test_invalid_value_raises_validation_error__tc_695_ep_004(self, value: Any) -> None:
        # Given: an invalid type_check value
        # When/Then: constructing the strict model fails on that field
        with pytest.raises(ValidationError) as excinfo:
            RdeConfig(execution={"type_check": value})
        locations = [error["loc"] for error in excinfo.value.errors()]
        assert ("execution", "type_check") in locations


class TestNormalizerRejects:
    """TC-695-EP-003: the normalizer maps invalid values to E1002."""

    @pytest.mark.parametrize("value", INVALID_VALUES)
    def test_v2_mapping_invalid_value_is_1002__tc_695_ep_003(self, tmp_path: Path, value: Any) -> None:
        # Given: a v2 mapping source with an invalid value
        source = {"execution": {"type_check": value}}
        # When/Then: normalization raises the catalog config error
        with pytest.raises(RdeConfigError) as excinfo:
            ConfigNormalizer().normalize(source, root=tmp_path, origin="v2")
        _assert_actionable_1002(excinfo.value)

    @pytest.mark.parametrize("value", VALID_VALUES)
    def test_v2_mapping_valid_value_loads__tc_695_ep_001(self, tmp_path: Path, value: str) -> None:
        # Given/When: a valid v2 mapping source
        config = ConfigNormalizer().normalize({"execution": {"type_check": value}}, root=tmp_path, origin="v2")
        # Then: the value is effective
        assert config.execution.type_check == value


class TestDiscoveryRejects:
    """TC-695-EP-005: discovered files are rejected at load time."""

    def test_discovered_yaml_invalid_is_1002__tc_695_ep_005(self, tmp_path: Path) -> None:
        # Given: rdeconfig.yaml at the project root with a misspelling
        _write_yaml(tmp_path, {"execution": {"type_check": "strcit"}})
        # When/Then: Runner config loading rejects it
        with pytest.raises(RdeConfigError) as excinfo:
            load_config(tmp_path, data_root=tmp_path / "data")
        _assert_actionable_1002(excinfo.value)

    def test_discovered_pyproject_invalid_is_1002__tc_695_ep_005(self, tmp_path: Path) -> None:
        # Given: [tool.rdetoolkit] with a wrong-case value
        (tmp_path / "pyproject.toml").write_text(
            '[tool.rdetoolkit.execution]\ntype_check = "Strict"\n',
            encoding="utf-8",
        )
        # When/Then: Runner config loading rejects it
        with pytest.raises(RdeConfigError) as excinfo:
            load_config(tmp_path, data_root=tmp_path / "data")
        _assert_actionable_1002(excinfo.value)

    @pytest.mark.parametrize("value", VALID_VALUES)
    def test_discovered_yaml_valid_loads__tc_695_ep_001(self, tmp_path: Path, value: str) -> None:
        # Given: a valid discovered value
        _write_yaml(tmp_path, {"execution": {"type_check": value}})
        # When: the Runner loads config
        config = load_config(tmp_path, data_root=tmp_path / "data")
        # Then: the value is effective
        assert config.execution.type_check == value


class TestOverridePrecedence:
    """TC-695-EP-006/007: overrides merge over discovered files and are validated."""

    def test_invalid_override_over_valid_yaml_is_1002__tc_695_ep_006(self, tmp_path: Path) -> None:
        # Given: a valid discovered file and an invalid override
        _write_yaml(tmp_path, {"execution": {"type_check": "warn"}})
        # When/Then: the merged config is rejected
        with pytest.raises(RdeConfigError) as excinfo:
            load_config(tmp_path, {"execution": {"type_check": "strcit"}}, data_root=tmp_path / "data")
        _assert_actionable_1002(excinfo.value)

    def test_valid_override_wins_over_yaml__tc_695_ep_006(self, tmp_path: Path) -> None:
        # Given: a discovered warn and an explicit strict override
        _write_yaml(tmp_path, {"execution": {"type_check": "warn"}})
        # When: config is loaded
        config = load_config(tmp_path, {"execution": {"type_check": "strict"}}, data_root=tmp_path / "data")
        # Then: the override wins
        assert config.execution.type_check == "strict"

    def test_nested_merge_keeps_sibling_key__tc_695_ep_007(self, tmp_path: Path) -> None:
        # Given: a file setting the error policy and an override setting type_check
        _write_yaml(tmp_path, {"execution": {"on_iteration_error": "fail_fast"}})
        # When: config is loaded
        config = load_config(tmp_path, {"execution": {"type_check": "warn"}}, data_root=tmp_path / "data")
        # Then: both nested keys are effective
        assert config.execution.type_check == "warn"
        assert config.execution.on_iteration_error == "fail_fast"

    def test_nested_merge_invalid_sibling_still_rejected__tc_695_ep_007(self, tmp_path: Path) -> None:
        # Given: a valid error policy in the file and an invalid type_check override
        _write_yaml(tmp_path, {"execution": {"on_iteration_error": "fail_fast"}})
        # When/Then: the invalid nested value is still rejected after the merge
        with pytest.raises(RdeConfigError) as excinfo:
            load_config(tmp_path, {"execution": {"type_check": None}}, data_root=tmp_path / "data")
        _assert_actionable_1002(excinfo.value)


def _never_called_flow() -> None:
    msg = "validate-only must never call the flow"
    raise AssertionError(msg)


def _seed_data_root(root: Path) -> None:
    data = root / "data"
    (data / "inputdata").mkdir(parents=True)
    (data / "inputdata" / "sample.txt").write_text("x", encoding="utf-8")
    (data / "invoice").mkdir()
    (data / "invoice" / "invoice.json").write_text(
        json.dumps({"datasetId": "d", "basic": {"dateSubmitted": "2026-07-11", "dataOwnerId": "0" * 56, "dataName": "s"}}),
        encoding="utf-8",
    )
    (data / "tasksupport").mkdir()
    (data / "tasksupport" / "invoice.schema.json").write_text(json.dumps({"properties": {}}), encoding="utf-8")
    (data / "tasksupport" / "metadata-def.json").write_text(
        json.dumps({"constant": {}, "variable": []}),
        encoding="utf-8",
    )
    (data / "temp").mkdir()


class TestRunnerValidateOnly:
    """TC-695-EP-008: the Runner's validate-only pre-flight rejects the value."""

    def test_validate_only_override_invalid_fails_with_1002__tc_695_ep_008(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Given: a valid project and an invalid type_check override
        _seed_data_root(tmp_path)
        monkeypatch.chdir(tmp_path)
        request = build_run_request(
            flow=_never_called_flow,
            custom_dataset_function=None,
            config={"execution": {"type_check": "strcit"}},
            root=tmp_path,
            validate_only=True,
        )
        data_root = tmp_path / "data"
        # When: the Runner runs the validate-only pre-flight
        report = Runner(root=tmp_path, inputdata_path=data_root / "inputdata", unpacked_dir_path=data_root / "temp").run(
            request,
        )
        # Then: it fails with the catalog config error naming the key
        assert report.status == "failed"
        assert report.error is not None
        assert report.error["code"] == 1002
        assert "execution.type_check" in report.error["message"]

    def test_validate_only_override_valid_succeeds__tc_695_ep_008(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Given: a valid project and a valid override
        _seed_data_root(tmp_path)
        monkeypatch.chdir(tmp_path)
        request = build_run_request(
            flow=_never_called_flow,
            custom_dataset_function=None,
            config={"execution": {"type_check": "warn"}},
            root=tmp_path,
            validate_only=True,
        )
        data_root = tmp_path / "data"
        # When: the Runner runs the validate-only pre-flight
        report = Runner(root=tmp_path, inputdata_path=data_root / "inputdata", unpacked_dir_path=data_root / "temp").run(
            request,
        )
        # Then: it succeeds without calling the flow
        assert report.status == "success"


class TestCliValidateOnly:
    """TC-695-EP-009: ``rdetoolkit run --flow ... --validate-only`` catches the value."""

    @pytest.mark.parametrize("source", ["discovered", "config-option"])
    def test_cli_validate_only_invalid_exits_1_without_calling_flow__tc_695_ep_009(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        source: str,
    ) -> None:
        from tests.v2.cli.fixtures import run_flows

        # Given: a valid project whose type_check is misspelled in a file or --config override
        _seed_data_root(tmp_path)
        monkeypatch.chdir(tmp_path)
        # The shipped command takes the flow as the positional REF (the issue's
        # ``--flow`` spelling is not a shipped option; no alias is added).
        args = ["run", f"{FIXTURE_MODULE}:validate_only_pipeline", "--validate-only"]
        if source == "discovered":
            _write_yaml(tmp_path, {"execution": {"type_check": "strcit"}})
        else:
            override = tmp_path / "override.yaml"
            override.write_text(yaml.safe_dump({"execution": {"type_check": "strcit"}}), encoding="utf-8")
            args += ["--config", str(override)]
        before = len(run_flows.VALIDATE_ONLY_SENTINEL)
        # When: the validate-only pre-flight runs
        result = CliRunner().invoke(app, args)
        # Then: it exits 1, names the key, and never calls the flow
        assert result.exit_code == 1, result.output
        assert "execution.type_check" in result.output
        assert len(run_flows.VALIDATE_ONLY_SENTINEL) == before


class TestV1CompatibilityUnchanged:
    """TC-695-EP-010: v1-origin defaults and mapping are unchanged."""

    def test_v1_origin_defaults_unchanged__tc_695_ep_010(self, tmp_path: Path) -> None:
        # Given/When: an empty v1 configuration is normalized
        config = ConfigNormalizer().normalize({}, root=tmp_path, origin="v1")
        # Then: the v1 error policy and the type_check default are unchanged
        assert config.execution.on_iteration_error == "fail_fast"
        assert config.execution.type_check == "off"

    def test_v1_ignore_errors_mapping_unchanged__tc_695_ep_010(self, tmp_path: Path) -> None:
        # Given/When: the v1 ignore_errors switch is normalized
        config = ConfigNormalizer().normalize(
            {"multidata_tile": {"ignore_errors": True}},
            root=tmp_path,
            origin="v1",
        )
        # Then: it still maps to the continue policy
        assert config.execution.on_iteration_error == "continue"
        assert config.execution.type_check == "off"

    def test_tasksupport_v1_config_defaults_unchanged__tc_695_ep_010(self, tmp_path: Path) -> None:
        # Given: a v1 tasksupport rdeconfig.yaml (no v2 execution section)
        tasksupport = tmp_path / "data" / "tasksupport"
        tasksupport.mkdir(parents=True)
        (tasksupport / "rdeconfig.yaml").write_text(
            yaml.safe_dump({"system": {"extended_mode": None}}),
            encoding="utf-8",
        )
        # When: the Runner discovers it
        config = load_config(tmp_path, data_root=tmp_path / "data")
        # Then: v1 defaults apply and type_check stays off
        assert config.execution.on_iteration_error == "fail_fast"
        assert config.execution.type_check == "off"


class TestRuntimeModeUnchanged:
    """TC-695-EP-011: a valid value reaches the recorder verbatim.

    The warn/strict exception mapping itself is pinned by
    ``tests/v2/runner/test_execute.py`` (TC-EXEC-011) and
    ``tests/v2/core/test_node.py`` (TC-EP-110..112); this case pins that the
    narrowed annotation does not alter the value handed to the recorder.
    """

    @pytest.mark.parametrize("value", VALID_VALUES)
    def test_recorder_receives_configured_mode__tc_695_ep_011(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        value: str,
    ) -> None:
        from rdetoolkit.core import calllog

        seen: list[str] = []
        original_init = calllog.CallLogRecorder.__init__

        def _spy_init(self: calllog.CallLogRecorder, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)
            seen.append(self.type_check)

        monkeypatch.setattr(calllog.CallLogRecorder, "__init__", _spy_init)
        # Given: a valid project and a valid configured mode
        _seed_data_root(tmp_path)
        monkeypatch.chdir(tmp_path)
        request = build_run_request(
            flow=_noop_flow,
            custom_dataset_function=None,
            config={"execution": {"type_check": value}},
            root=tmp_path,
        )
        data_root = tmp_path / "data"
        # When: the Runner executes the flow
        report = Runner(root=tmp_path, inputdata_path=data_root / "inputdata", unpacked_dir_path=data_root / "temp").run(
            request,
        )
        # Then: the run succeeds and every recorder used exactly that mode
        assert report.status == "success", report.error
        assert seen
        assert set(seen) == {value}


def _noop_flow() -> None:
    return None
