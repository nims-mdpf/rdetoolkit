"""Tests for rdetoolkit v2 config_loader (TC-CFG-001..007).

Written before implementation (TDD Red phase).
Target: make all tests pass in codex-worker Green phase.

Design authority:
  - local/develop/v2/Design.md §4.4 (extra="forbid" on v2 config sections)
  - local/develop/v2/session_b1.md (load_config fallback chain)
  - decisions_pre_A1.md Ruling 5 (v1 spellings in config)

Fallback chain: rdeconfig.yaml -> pyproject.toml [tool.rdetoolkit] -> RdeConfig()
Priority:       overrides dict > file config > defaults
"""
from __future__ import annotations

from pathlib import Path

import pytest

# Target imports — fail until implementation exists (expected in Red phase):
# from rdetoolkit.runner.config_loader import load_config
# from rdetoolkit.types import RdeConfig


class TestLoadConfig:
    """Tests for load_config() fallback chain and validation (Design §4.4)."""

    def test_load_config_reads_from_rdeconfig_yaml_when_present(self, tmp_path: Path) -> None:
        """TC-CFG-001: When rdeconfig.yaml exists, config is loaded from it."""
        from rdetoolkit.runner.config_loader import load_config
        from rdetoolkit.types import RdeConfig

        rdeconfig_yaml = tmp_path / "rdeconfig.yaml"
        rdeconfig_yaml.write_text("system:\n  extended_mode: invoice\n")

        result = load_config(tmp_path)

        assert isinstance(result, RdeConfig)

    def test_load_config_falls_back_to_pyproject_toml_when_rdeconfig_absent(
        self, tmp_path: Path
    ) -> None:
        """TC-CFG-002: When rdeconfig.yaml is absent, config is loaded from pyproject.toml."""
        from rdetoolkit.runner.config_loader import load_config
        from rdetoolkit.types import RdeConfig

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.rdetoolkit]\n"
            "[tool.rdetoolkit.system]\n"
            'extended_mode = "invoice"\n'
        )

        result = load_config(tmp_path)

        assert isinstance(result, RdeConfig)

    def test_load_config_returns_default_rdeconfig_when_no_config_files_present(
        self, tmp_path: Path
    ) -> None:
        """TC-CFG-003: With no config files, returns a default RdeConfig() with all defaults."""
        from rdetoolkit.runner.config_loader import load_config
        from rdetoolkit.types import RdeConfig

        result = load_config(tmp_path)

        assert isinstance(result, RdeConfig)
        assert result == RdeConfig(), (
            f"Default load_config must equal RdeConfig(), got {result}"
        )

    def test_load_config_overrides_dict_takes_priority_over_file_values(
        self, tmp_path: Path
    ) -> None:
        """TC-CFG-004: overrides dict values take priority over values read from rdeconfig.yaml."""
        from rdetoolkit.runner.config_loader import load_config
        from rdetoolkit.types import RdeConfig

        rdeconfig_yaml = tmp_path / "rdeconfig.yaml"
        rdeconfig_yaml.write_text("system:\n  extended_mode: invoice\n")

        result = load_config(tmp_path, overrides={"system": {"extended_mode": "rdeformat"}})

        assert isinstance(result, RdeConfig)
        assert result.system.extended_mode == "rdeformat", (
            f"overrides must take priority; expected 'rdeformat', got {result.system.extended_mode!r}"
        )

    def test_load_config_raises_catalogued_error_on_lineage_key_in_provenance_section(
        self, tmp_path: Path
    ) -> None:
        """TC-CFG-005: lineage keys raise RdeConfigError(1002).

        Design v2.1 R2/ADR-022: value-lineage settings do not exist in v2.0;
        RdeConfig sections have extra='forbid' and reject them at load time.
        """
        from rdetoolkit.errors import RdeConfigError
        from rdetoolkit.runner.config_loader import load_config

        rdeconfig_yaml = tmp_path / "rdeconfig.yaml"
        rdeconfig_yaml.write_text("provenance:\n  lineage: on\n")

        with pytest.raises(RdeConfigError) as exc_info:
            load_config(tmp_path)
        assert exc_info.value.code == 1002

    def test_load_config_raises_catalogued_error_on_unknown_key_in_execution_section(
        self, tmp_path: Path
    ) -> None:
        """TC-CFG-006: Unknown execution key raises RdeConfigError(1002).

        RdeConfig execution section has extra='forbid' (Design §4.4 / SF#17).
        """
        from rdetoolkit.errors import RdeConfigError
        from rdetoolkit.runner.config_loader import load_config

        rdeconfig_yaml = tmp_path / "rdeconfig.yaml"
        rdeconfig_yaml.write_text("execution:\n  typo_key: some_value\n")

        with pytest.raises(RdeConfigError) as exc_info:
            load_config(tmp_path)
        assert exc_info.value.code == 1002

    def test_load_config_happy_path_returns_correct_rdeconfig_fields(
        self, tmp_path: Path
    ) -> None:
        """TC-CFG-007: Normal load with valid rdeconfig.yaml returns a populated RdeConfig."""
        from rdetoolkit.runner.config_loader import load_config
        from rdetoolkit.types import RdeConfig

        rdeconfig_yaml = tmp_path / "rdeconfig.yaml"
        rdeconfig_yaml.write_text(
            "system:\n"
            "  extended_mode: invoice\n"
            "execution:\n"
            "  type_check: 'off'\n"
            "provenance:\n"
            "  repr_head: 'off'\n"
        )

        result = load_config(tmp_path)

        assert isinstance(result, RdeConfig)
        assert result.system.extended_mode == "invoice"
        assert result.execution.type_check == "off"
        assert result.provenance.repr_head == "off"
