"""Magic interpolation at the real v2 Runner boundary (RUN01-RUN10)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from rdetoolkit.api.request import FlowTarget, RunRequest
from rdetoolkit.config.normalize import ConfigNormalizer
from rdetoolkit.domain.magic_policy import options_from_config
from rdetoolkit.errors import RdeValidationError
from rdetoolkit.fileops import readf_json, writef_json
from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.planner import RunPlanner
from rdetoolkit.runner.config_loader import compute_config_digest
from rdetoolkit.types import OutputContext, RdeConfig
from tests.v2.contract.fixtures import _generate


def _seed(tmp_path: Path, template: str) -> Path:
    root = tmp_path / "case"
    _generate.materialize_sut_case("invoice", root)
    invoice = root / "data/invoice/invoice.json"
    data = readf_json(invoice)
    data["basic"]["dataName"] = template
    writef_json(invoice, data)
    return root


@pytest.mark.parametrize("source", [None, {}, RdeConfig()])
def test_policy_default(source: object, tmp_path: Path) -> None:
    """RUN01: Omitted booleans retain auto semantics after normalization."""
    # Given: omitted configuration through each supported model/mapping path
    config = ConfigNormalizer().normalize(source, root=tmp_path, origin="v2")
    # When: choosing v2 interpolation behavior
    options = options_from_config(config)
    # Then: omission always means auto
    assert options.policy == "auto"
    assert options.missing == "error"


@pytest.mark.parametrize("value,expected", [(True, "enabled"), (False, "disabled")])
def test_policy_boolean(value: bool, expected: str) -> None:
    """RUN02: Explicit boolean choices retain their meaning."""
    # Given: an explicit legacy boolean in a flow config
    config = RdeConfig(system={"magic_variable": value})
    # When: adapting it to the strict policy
    options = options_from_config(config)
    # Then: the explicit choice is retained
    assert options.policy == expected


@pytest.mark.parametrize("policy", ["auto", "enabled", "disabled"])
def test_policy_inputs(policy: str) -> None:
    """RUN02: All explicit policies support the missing-value override."""
    # Given: the explicit v2 configuration namespace
    config = RdeConfig(custom={"interpolation": {"policy": policy, "missing": "omit"}})
    # When: validating the options
    options = options_from_config(config)
    # Then: all three states and missing override are supported
    assert options.policy == policy
    assert options.missing == "omit"


@pytest.mark.parametrize("custom", [None, [], True, "secret", {"policy": "secret"}, {"missing": "secret"}, {"unknown": True}])
def test_invalid_options(custom: Any) -> None:
    """RUN03: Invalid options fail without echoing private values."""
    # Given: malformed interpolation options
    config = RdeConfig(custom={"interpolation": custom})
    # When: reading the policy
    with pytest.raises(RdeValidationError) as caught:
        options_from_config(config)
    # Then: its type/code and privacy contract are stable
    assert caught.value.code == 4005
    assert "secret" not in str(caught.value)


def test_contradictory_options() -> None:
    """RUN03: Conflicting explicit switches cannot silently override each other."""
    # Given: two explicit incompatible switches
    config = RdeConfig(system={"magic_variable": False}, custom={"interpolation": {"policy": "enabled"}})
    # When: selecting the effective policy
    with pytest.raises(RdeValidationError) as caught:
        options_from_config(config)
    # Then: configuration does not silently choose a winner
    assert caught.value.code == 4005


def test_runner_auto(tmp_path: Path) -> None:
    """RUN04: A real flow interpolates without a magic flag."""
    # Given: a real invoice flow and no magic flag
    root = _seed(tmp_path, "${invoice:basic:dataOwnerId}")
    before = readf_json(root / "data/invoice/invoice.json")
    # When: running the ordinary eager flow
    report = Runner(root=root).run(lambda: None)
    # Then: the placeholder expands without configuration
    assert report.status == "success"
    assert readf_json(root / "data/invoice/invoice.json")["basic"]["dataName"] == before["basic"]["dataOwnerId"]


def test_runner_disabled(tmp_path: Path) -> None:
    """RUN05: Explicit disabling preserves literals and emits its reason."""
    # Given: explicit disabled interpolation
    root = _seed(tmp_path, "${filename}")
    events = MemoryEventSink()
    # When: the tile completes
    report = Runner(root=root, event_sink=events).run(lambda: None, system={"magic_variable": False})
    # Then: names stay literal and the reason is observable
    assert report.status == "success"
    assert readf_json(root / "data/invoice/invoice.json")["basic"]["dataName"] == "${filename}"
    assert any(event.name == "warning" and event.payload.get("code") == 1102 for event in events.events)


@pytest.mark.parametrize("template,code", [("${}", 4005), ("${filename:extra}", 4005), ("${invoice:custom:absent}", 4006)])
def test_runner_failure(tmp_path: Path, template: str, code: int) -> None:
    """RUN06: Strict errors retain their code without partial invoice writes."""
    # Given: a template rejected by the strict v2 contract
    root = _seed(tmp_path, template)
    path = root / "data/invoice/invoice.json"
    before = path.read_bytes()
    # When: processing a real tile
    report = Runner(root=root).run(lambda: None)
    # Then: the precise catalog error survives and no partial replacement is saved
    assert report.status == "failed"
    assert report.iterations[0]["error"]["code"] == code
    assert path.read_bytes() == before


def test_plan_snapshot(tmp_path: Path) -> None:
    """RUN07: The original value belongs to the plan, independent of its path."""
    # Given: a plan created before any tile may update the invoice
    root = _seed(tmp_path, "original")
    data_root = root / "data"
    planner = RunPlanner(inputdata_path=data_root / "inputdata", unpacked_dir_path=data_root / "temp", run_id_factory=lambda: "snapshot")
    plan = planner.create(RunRequest(root=root, target=FlowTarget(function=lambda: None)), config=RdeConfig(), mode=ModeKind.invoice, data_root=data_root)
    # When: an overlapping writer changes the path afterwards
    writef_json(data_root / "invoice/invoice.json", {"basic": {"dataName": "changed"}})
    # Then: original scope remains the value captured by this plan
    assert json.loads(plan.original_invoice_snapshot)["basic"]["dataName"] == "original"


@pytest.mark.parametrize("template,expected", [("${}", "failed"), ("${filename:extra}", "failed"), ("${metadata:constant:runtime}", "success")])
def test_validate_only_magic(tmp_path: Path, template: str, expected: str) -> None:
    """RUN10: Validate-only checks syntax and defers runtime values without a flow."""
    # Given: syntax or runtime-dependent input and a flow that must not run
    root = _seed(tmp_path, template)
    events = MemoryEventSink()
    called: list[bool] = []
    request = RunRequest(root=root, target=FlowTarget(function=lambda: called.append(True)), validate_only=True)
    # When: checking the request without executing tiles
    report = Runner(root=root, event_sink=events).run(request)
    # Then: syntax errors are real failures, while runtime metadata is deferred
    assert report.status == expected
    assert called == []
    if expected == "failed":
        assert report.error["code"] == 4005
    else:
        assert any("deferred" in event.payload.get("message", "") for event in events.events)


def test_smarttable_metadata_without_attachment(tmp_path: Path) -> None:
    """RUN08: A real SmartTable row resolves flow metadata with no attachment."""
    # Given: a registration row without a related-file column
    root = tmp_path / "smarttable"
    _generate.build_smarttable_workspace(root, rows=(("", "${metadata:constant:label}", "1"),), with_file_column=False)

    def write_tile_metadata(out: OutputContext) -> None:
        writef_json(out.meta / "metadata.json", {"constant": {"label": {"value": "row-label"}}, "variable": []})

    # When: processing the table through the actual Runner and builder
    report = Runner(root=root, inputdata_path=root / "data/inputdata", unpacked_dir_path=root / "data/temp").run(write_tile_metadata, system={"magic_variable": True})
    # Then: no rawfile gate prevents resolving the tile metadata
    assert report.status == "success", report.error
    assert report.mode == "smarttable"
    assert readf_json(root / "data/invoice/invoice.json")["basic"]["dataName"] == "row-label"


def test_digest_distinguishes_omitted_and_disabled() -> None:
    """RUN11: Config identity includes the policy-significant boolean omission."""
    # Given: configs with equal boolean values and different effective policies
    auto = RdeConfig()
    disabled = RdeConfig(system={"magic_variable": False})
    # When: computing their report fingerprints
    first, second = compute_config_digest(auto), compute_config_digest(disabled)
    # Then: replay cannot confuse automatic and disabled interpolation
    assert first != second


def test_repro_config_preserves_disabled(tmp_path: Path) -> None:
    """RUN11: Repro export cannot discard the explicit false default."""
    from rdetoolkit.cli.repro_cmd import _config_yaml

    # Given: an explicitly disabled effective config
    disabled = RdeConfig(system={"magic_variable": False})
    # When: exporting and normalizing its reproducible YAML
    text = _config_yaml(disabled, compute_config_digest(disabled))
    reloaded = ConfigNormalizer().normalize(yaml.safe_load(text), root=tmp_path, origin="v2")
    # Then: the policy retains its meaning through serialization
    assert options_from_config(reloaded).policy == "disabled"


def test_planning_rejects_invalid_policy_without_tiles(tmp_path: Path) -> None:
    """RUN13: Empty runs still validate policy at the planning boundary."""
    # Given: no tiles and an invalid explicit interpolation policy
    planner = RunPlanner(inputdata_path=tmp_path / "inputdata", unpacked_dir_path=tmp_path / "temp", run_id_factory=lambda: "invalid-policy")
    request = RunRequest(root=tmp_path, target=FlowTarget(function=lambda: None))
    config = RdeConfig(custom={"interpolation": {"policy": "invalid"}})
    # When: a real run plan is constructed
    with pytest.raises(RdeValidationError) as caught:
        planner.create(request, config=config, mode=ModeKind.invoice, data_root=tmp_path)
    # Then: no user flow or tile is needed to reject the invalid setting
    assert caught.value.code == 4005
