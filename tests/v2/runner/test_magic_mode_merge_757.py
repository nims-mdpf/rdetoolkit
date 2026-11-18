"""Integration contracts MC01-MC06 for interpolation and mode-planning merges."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml

from rdetoolkit.api.request import LegacyCallbackTarget
from rdetoolkit.cli.repro_cmd import _config_yaml
from rdetoolkit.config.normalize import ConfigNormalizer
from rdetoolkit.domain.magic import ResolutionContext, resolve_invoice
from rdetoolkit.domain.magic_policy import options_from_config
from rdetoolkit.errors import RdeValidationError
from rdetoolkit.fileops import readf_json, writef_json
from rdetoolkit.modes.stages import ArtifactStage, plan_artifact_stages
from rdetoolkit.runner.config_loader import compute_config_digest
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.preview import preview_registration
from rdetoolkit.types import RdeConfig
from tests.v2.contract.fixtures import _generate
from tests.v2.runner.stage_order_helpers import make_plan
from tests.v2.runner.test_magic_integration import _seed


def _tree(root: Path) -> dict[str, bytes | None]:
    return {p.relative_to(root).as_posix(): p.read_bytes() if p.is_file() else None for p in root.rglob("*")}


@pytest.mark.parametrize("system", [{}, {"extended_mode": "invoice", "magic_variable": False}, {"extended_mode": "MultiDataTile", "magic_variable": True}, {"extended_mode": "RDEFormat", "magic_variable": False}])
def test_replay_preserves_both_policy_fields(tmp_path: Path, system: dict[str, Any]) -> None:
    """MC01: Mode and interpolation intent survive the same config roundtrip."""
    # Given: independently meaningful mode spelling and magic flag presence
    config = ConfigNormalizer().normalize(RdeConfig(system=system), root=tmp_path, origin="v2")
    digest = compute_config_digest(config)
    # When: exporting the effective settings and reloading the YAML
    text = _config_yaml(config, digest)
    replayed = ConfigNormalizer().normalize(yaml.safe_load(text), root=tmp_path, origin="v2")
    # Then: neither policy can be lost while retaining the other's identity
    assert compute_config_digest(replayed) == digest
    assert options_from_config(replayed) == options_from_config(config)
    assert replayed.system.extended_mode == config.system.extended_mode
    for field in ("extended_mode", "magic_variable"):
        assert (field in replayed.system.model_fields_set) == (field in config.system.model_fields_set)


@pytest.mark.parametrize("system", [{}, {"magic_variable": True}])
def test_flow_stage_has_no_rawfile_gate(tmp_path: Path, system: dict[str, Any]) -> None:
    """MC02: Strict auto and enabled stages support independent invoice sources."""
    # Given: a strict flow plan with no raw attachments
    plan = replace(make_plan(ModeKind.invoice, tmp_path), config=RdeConfig(system=system))
    # When: describing the frozen stage contract
    magic = next(stage for stage in plan_artifact_stages(plan, has_rawfiles=False) if stage.name is ArtifactStage.magic)
    # Then: rawfile absence cannot disable invoice or metadata interpolation
    assert magic.enabled is True
    assert magic.reason is None


@pytest.mark.parametrize("legacy,system,reason", [(False, {"magic_variable": False}, "disabled_by_config"), (True, {"magic_variable": True}, "no_rawfiles"), (True, {}, "disabled_by_config")])
def test_legacy_and_disabled_gates(tmp_path: Path, legacy: bool, system: dict[str, Any], reason: str) -> None:
    """MC03: Existing legacy raw gates and explicit flow disabling remain intact."""
    # Given: an explicitly disabled flow or a legacy callback plan
    plan = replace(make_plan(ModeKind.invoice, tmp_path), config=RdeConfig(system=system))
    if legacy:
        plan = replace(plan, target=LegacyCallbackTarget(function=None))
    # When: describing a tile without attachments
    magic = next(stage for stage in plan_artifact_stages(plan, has_rawfiles=False) if stage.name is ArtifactStage.magic)
    # Then: the target's documented omission policy is retained
    assert magic.enabled is False
    assert magic.reason == reason


@pytest.mark.parametrize(
    "template",
    [
        "${}", "${filename:extra}", "${unsupported}", "${invoice:basic:field:extra}",
        "${invoice:basic:../x}", "${invoice:basic:x.y}", "${metadata:variable:x}",
        "${invoice:basic:x y}", "${invoice:sample:id}", "${", "${invoice:${filename}}",
        "$${", "x" * 16385 + "${filename}",
    ],
    ids=lambda value: "overlong" if len(value) > 80 else value,
)
def test_explain_rejects_invalid_template(tmp_path: Path, template: str) -> None:
    """MC04: Explain and ordinary validate-only reject the same strict syntax."""
    # Given: an invalid eligible template in an otherwise valid project
    root = _seed(tmp_path, template)
    before = _tree(root)
    # When: explaining the registration without invoking a flow
    with pytest.raises(RdeValidationError) as caught:
        preview_registration(root)
    # Then: the interpolation error keeps its own identity and nothing is written
    assert caught.value.code == 4009
    assert caught.value.name == "InvalidMagicExpression"
    assert _tree(root) == before


@pytest.mark.parametrize("case", ["auto", "disabled", "rdeformat"])
def test_explain_stage_matches_interpolation_policy(tmp_path: Path, case: str) -> None:
    """MC05: Explain preserves pure policy and mode-specific stage omission."""
    # Given: an applicable template or deliberately omitted interpolation stage
    if case == "rdeformat":
        root = tmp_path / "rdeformat"
        _generate.materialize_sut_case("rdeformat", root)
    else:
        root = _seed(tmp_path, "${metadata:constant:id}")
    path = root / "data/invoice/invoice.json"
    invoice = readf_json(path)
    if case != "auto":
        invoice["basic"]["dataName"] = "${}"
    writef_json(path, invoice)
    overrides: dict[str, Any] | None = None
    if case == "disabled":
        overrides = {"system": {"magic_variable": False}}
    elif case == "rdeformat":
        overrides = {"system": {"extended_mode": "rdeformat"}}
    before = _tree(root)
    # When: generating a registration explanation without user code or logs
    result = preview_registration(root, overrides=overrides)
    magic = next(stage for stage in result.stages if stage.name is ArtifactStage.magic)
    # Then: the selected stage matches strict execution rather than legacy defaults
    assert magic.enabled is (case == "auto")
    assert magic.reason == {"auto": None, "disabled": "disabled_by_config", "rdeformat": "omitted_by_mode"}[case]
    assert _tree(root) == before


def test_missing_source_keeps_its_identity() -> None:
    """MC06: Missing interpolation sources cannot use the archive-planning code."""
    # Given: a requested original-invoice key that does not exist
    context = ResolutionContext.from_sources(original_invoice={}, current_invoice={"basic": {"dataName": "${invoice:custom:absent}"}})
    # When: resolving the field
    with pytest.raises(RdeValidationError) as caught:
        resolve_invoice(context)
    # Then: the dedicated source code and name remain paired
    assert caught.value.code == 4010
    assert caught.value.name == "MissingMagicSource"
