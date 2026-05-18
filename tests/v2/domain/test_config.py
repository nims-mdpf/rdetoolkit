"""Tests for v2 domain config loading.

EP Table:
| API           | Partition              | Rationale             | Expected              | Test ID      |
|---------------|------------------------|-----------------------|-----------------------|--------------|
| load_config   | rdeconfig.yaml exists  | primary config source | Config loaded         | TC-EP-001    |
| load_config   | pyproject fallback     | fallback source       | Config loaded         | TC-EP-002    |
| load_config   | invalid mode           | validation error      | ConfigError raised    | TC-EP-003    |

BV Table:
| API           | Boundary               | Rationale             | Expected              | Test ID      |
|---------------|------------------------|-----------------------|-----------------------|--------------|
| load_config   | empty directory        | no config available   | default Config loaded | TC-BV-001    |
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rdetoolkit.exceptions import ConfigError


class TestLoadDomainConfig:
    """Tests for domain config loading."""

    def test_loads_rdeconfig_yaml__tc_ep_001(self, tmp_path: Path) -> None:
        """TC-EP-001: rdeconfig.yaml is loaded as the primary source."""
        from rdetoolkit.domain.config import load_domain_config

        # Given: a tasksupport directory with rdeconfig.yaml
        tasksupport = tmp_path / "tasksupport"
        tasksupport.mkdir()
        (tasksupport / "rdeconfig.yaml").write_text(
            "system:\n  extended_mode: rdeformat\n  save_raw: true\n",
            encoding="utf-8",
        )

        # When: loading domain config
        config = load_domain_config(tasksupport)

        # Then: values come from rdeconfig.yaml
        assert config.system.extended_mode == "rdeformat"
        assert config.system.save_raw is True

    def test_falls_back_to_pyproject_toml__tc_ep_002(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-EP-002: pyproject.toml is used when no rdeconfig exists."""
        from rdetoolkit.domain.config import load_domain_config

        # Given: an empty tasksupport directory and a project pyproject.toml
        tasksupport = tmp_path / "tasksupport"
        tasksupport.mkdir()
        (tmp_path / "pyproject.toml").write_text(
            "[tool.rdetoolkit.system]\nextended_mode = \"MultiDataTile\"\nsave_raw = true\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        # When: loading domain config
        config = load_domain_config(tasksupport)

        # Then: values come from pyproject.toml
        assert config.system.extended_mode == "MultiDataTile"
        assert config.system.save_raw is True

    def test_invalid_required_value_raises_validation_error__tc_ep_003(self, tmp_path: Path) -> None:
        """TC-EP-003: invalid config values raise ConfigError."""
        from rdetoolkit.domain.config import load_domain_config

        # Given: a config with an invalid required discriminator value
        tasksupport = tmp_path / "tasksupport"
        tasksupport.mkdir()
        (tasksupport / "rdeconfig.yaml").write_text(
            "system:\n  extended_mode: multidatatile\n",
            encoding="utf-8",
        )

        # When / Then: validation fails with field information
        with pytest.raises(ConfigError, match="extended_mode"):
            load_domain_config(tasksupport)

    def test_empty_directory_returns_default_config__tc_bv_001(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-BV-001: no config file returns a default Config instance."""
        from rdetoolkit.domain.config import load_domain_config

        # Given: no config files in tasksupport or project root
        tasksupport = tmp_path / "tasksupport"
        tasksupport.mkdir()
        monkeypatch.chdir(tmp_path)

        # When: loading domain config
        config = load_domain_config(tasksupport)

        # Then: defaults are populated
        assert config.system.extended_mode is None
        assert config.multidata_tile is not None
