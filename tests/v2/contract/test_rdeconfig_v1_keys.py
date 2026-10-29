"""Contract tests for the v1 artifact keys added to ``RdeConfig``.

EP table:

| API | Partition | Expected | Test ID |
|---|---|---|---|
| ``RdeConfig`` | omitted artifact keys | v1-identical defaults | TC-EP-G2-001 |
| ``RdeConfig`` | all artifact keys supplied | values retained in their sections | TC-EP-G2-002 |
| ``load_config`` | artifact keys in YAML | values loaded from YAML | TC-EP-G2-003 |
| ``load_config`` | YAML plus overrides | overrides win | TC-EP-G2-004 |
| ``load_config`` | unknown key in any strict section | ``RdeConfigError(1002)`` | TC-EP-G2-005 |

BV table:

| API | Boundary | Expected | Test ID |
|---|---|---|---|
| ``RdeConfig`` | empty ``system`` and ``smarttable`` mappings | defaults preserved | TC-BV-G2-001 |
"""

from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.errors import RdeConfigError
from rdetoolkit.runner.config_loader import load_config
from rdetoolkit.types import RdeConfig


def test_artifact_keys_use_v1_defaults__tc_ep_g2_001() -> None:
    """TC-EP-G2-001: Artifact behavior defaults match the v1 configuration."""
    # Given: no explicit configuration values
    # When: constructing the strict v2 configuration
    config = RdeConfig()

    # Then: all seven artifact keys have their v1 defaults
    assert config.system.save_raw is False
    assert config.system.save_nonshared_raw is True
    assert config.system.save_thumbnail_image is False
    assert config.system.magic_variable is False
    assert config.system.save_invoice_to_structured is False
    assert config.system.feature_description is True
    assert config.smarttable.save_table_file is False


def test_artifact_keys_accept_explicit_values__tc_ep_g2_002() -> None:
    """TC-EP-G2-002: Artifact behavior keys can be set in canonical sections."""
    # Given: explicit values opposite to every artifact-key default
    values = {
        "save_raw": True,
        "save_nonshared_raw": False,
        "save_thumbnail_image": True,
        "magic_variable": True,
        "save_invoice_to_structured": True,
        "feature_description": False,
    }

    # When: constructing RdeConfig from those values
    config = RdeConfig(system=values, smarttable={"save_table_file": True})

    # Then: the system and smarttable sections retain every explicit value
    assert config.system.model_dump(exclude={"extended_mode"}) == values
    assert config.smarttable.save_table_file is True


def test_artifact_keys_load_from_yaml__tc_ep_g2_003(tmp_path: Path) -> None:
    """TC-EP-G2-003: Artifact behavior keys are configurable through YAML."""
    # Given: an rdeconfig.yaml containing all artifact behavior keys
    (tmp_path / "rdeconfig.yaml").write_text(
        """\
system:
  save_raw: true
  save_nonshared_raw: false
  save_thumbnail_image: true
  magic_variable: true
  save_invoice_to_structured: true
  feature_description: false
smarttable:
  save_table_file: true
""",
        encoding="utf-8",
    )

    # When: loading the configuration from the root directory
    config = load_config(tmp_path)

    # Then: YAML values reach their canonical model fields
    assert config.system.save_raw is True
    assert config.system.save_nonshared_raw is False
    assert config.system.save_thumbnail_image is True
    assert config.system.magic_variable is True
    assert config.system.save_invoice_to_structured is True
    assert config.system.feature_description is False
    assert config.smarttable.save_table_file is True


def test_artifact_key_overrides_win_over_yaml__tc_ep_g2_004(tmp_path: Path) -> None:
    """TC-EP-G2-004: Explicit overrides take precedence over artifact YAML."""
    # Given: YAML values and conflicting explicit overrides
    (tmp_path / "rdeconfig.yaml").write_text(
        "system:\n  save_raw: false\nsmarttable:\n  save_table_file: false\n",
        encoding="utf-8",
    )
    overrides = {
        "system": {"save_raw": True},
        "smarttable": {"save_table_file": True},
    }

    # When: loading the YAML with overrides
    config = load_config(tmp_path, overrides)

    # Then: override values take precedence in both sections
    assert config.system.save_raw is True
    assert config.smarttable.save_table_file is True


@pytest.mark.parametrize(
    "invalid_config",
    [
        pytest.param({"unexpected": True}, id="top-level"),
        pytest.param({"system": {"unexpected": True}}, id="system"),
        pytest.param({"smarttable": {"unexpected": True}}, id="smarttable"),
        pytest.param({"execution": {"unexpected": True}}, id="execution"),
        pytest.param({"provenance": {"unexpected": True}}, id="provenance"),
    ],
)
def test_all_config_sections_remain_strict__tc_ep_g2_005(
    invalid_config: dict[str, Any],
    tmp_path: Path,
) -> None:
    """TC-EP-G2-005: Unknown keys surface as catalogued config errors."""
    # Given: an unknown key at the root or in a strict child section
    # When: loading it through the public Runner config boundary
    with pytest.raises(RdeConfigError) as exc_info:
        load_config(tmp_path, invalid_config)

    # Then: the error retains its catalogued type and integer code
    assert exc_info.value.code == 1002


def test_empty_artifact_sections_preserve_defaults__tc_bv_g2_001() -> None:
    """TC-BV-G2-001: Empty artifact sections retain all field defaults."""
    # Given: explicitly empty system and smarttable mappings
    # When: validating the boundary input
    config = RdeConfig(system={}, smarttable={})

    # Then: the artifact settings still use their v1 defaults
    assert config.system.save_raw is False
    assert config.system.save_nonshared_raw is True
    assert config.system.feature_description is True
    assert config.smarttable.save_table_file is False
