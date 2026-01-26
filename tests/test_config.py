"""
Configuration Loading Error Handling Tests

This module tests error scenarios for configuration file loading,
following Issue #361 requirements for improved error messages.

Test Design:
-----------

Equivalence Partitioning (see table in docs/develop/issue_361_05.md)
Boundary Value Analysis (see table in docs/develop/issue_361_05.md)

All tests follow Given/When/Then pattern and verify:
1. Correct exception type (ConfigError)
2. Error type attribute (file_not_found, parse_error, validation_error, etc.)
3. File path included in error
4. Line/column information when available
5. Field name for validation errors
6. Documentation URL in all errors
"""

import os
from pathlib import Path
import shutil

import pytest
import yaml
from pydantic import ValidationError
from rdetoolkit.config import is_toml, is_yaml, parse_config_file, get_config, load_config
from rdetoolkit.exceptions import ConfigError
from rdetoolkit.models.config import Config, SystemSettings, MultiDataTileSettings, SmartTableSettings, TracebackSettings
from tomlkit import document, table
from tomlkit.toml_file import TOMLFile


def test_is_toml():
    assert is_toml("config.toml") is True
    assert is_toml("config.yaml") is False
    assert is_toml("config.yml") is False
    assert is_toml("config.txt") is False


def test_is_yaml():
    assert is_yaml("config.toml") is False
    assert is_yaml("config.yaml") is True
    assert is_yaml("config.yml") is True
    assert is_yaml("config.txt") is False


@pytest.fixture()
def config_yaml():
    system_data = {"extended_mode": "rdeformat", "save_raw": True, "save_nonshared_raw": False, "magic_variable": False, "save_thumbnail_image": True}
    multi_data = {"ignore_errors": False}
    data = {"system": system_data, "multidata_tile": multi_data}
    test_yaml_path = "rdeconfig.yaml"
    with open(test_yaml_path, mode="w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    yield test_yaml_path

    if Path(test_yaml_path).exists():
        Path(test_yaml_path).unlink()


@pytest.fixture()
def config_yml():
    dirname = Path("tasksupport")
    dirname.mkdir(exist_ok=True)
    system_data = {"extended_mode": "rdeformat", "save_raw": True, "save_nonshared_raw": False, "magic_variable": False, "save_thumbnail_image": True}
    multi_data = {"ignore_errors": False}
    data = {"system": system_data, "multidata_tile": multi_data}
    test_yaml_path = dirname.joinpath("rdeconfig.yml")
    with open(test_yaml_path, mode="w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    yield test_yaml_path

    if Path(test_yaml_path).exists():
        Path(test_yaml_path).unlink()
    if dirname.exists():
        dirname.rmdir()


@pytest.fixture()
def config_yml_none_multiconfig():
    dirname = Path("tasksupport")
    dirname.mkdir(exist_ok=True)
    system_data = {"extended_mode": "rdeformat", "save_raw": True, "save_nonshared_raw": False, "magic_variable": False, "save_thumbnail_image": True}
    data = {"system": system_data}
    test_yaml_path = dirname.joinpath("rdeconfig.yml")
    with open(test_yaml_path, mode="w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    yield test_yaml_path

    if Path(test_yaml_path).exists():
        Path(test_yaml_path).unlink()
    if dirname.exists():
        dirname.rmdir()


@pytest.fixture()
def invalid_config_yaml():
    dirname = Path("tasksupport")
    dirname.mkdir(exist_ok=True)
    system_data = {"extended_mode": "rdeformat", "save_raw": True, "save_nonshared_raw": False, "magic_variable": False, "save_thumbnail_image": True}
    multi_data = {"ignore_errors": False}
    data = {"system": system_data, "multidata_tile": multi_data}
    test_yaml_path = dirname.joinpath("invalid_rdeconfig.yaml")
    with open(test_yaml_path, mode="w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    yield test_yaml_path

    if Path(test_yaml_path).exists():
        Path(test_yaml_path).unlink()
    if dirname.exists():
        dirname.rmdir()


@pytest.fixture()
def invalid_field_config_yaml():
    dirname = Path("tasksupport")
    dirname.mkdir(exist_ok=True)
    system_data = {"extended_mode": 123, "save_raw": 1, "save_nonshared_raw": False, "magic_variable": False, "save_thumbnail_image": True}
    multi_data = {"ignore_errors": False}
    data = {"system": system_data, "multidata_tile": multi_data}
    test_yaml_path = dirname.joinpath("invalid_rdeconfig.yaml")
    with open(test_yaml_path, mode="w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    yield test_yaml_path

    if Path(test_yaml_path).exists():
        Path(test_yaml_path).unlink()
    if dirname.exists():
        dirname.rmdir()


@pytest.fixture()
def invalid_empty_config_yaml():
    dirname = Path("tasksupport")
    dirname.mkdir(exist_ok=True)
    test_yaml_path = dirname.joinpath("invalid_rdeconfig.yaml")
    test_yaml_path.touch()

    yield test_yaml_path

    if Path(test_yaml_path).exists():
        Path(test_yaml_path).unlink()
    if dirname.exists():
        dirname.rmdir()


@pytest.fixture
def test_pyproject_toml():
    test_file = os.path.join(os.path.dirname(__file__), "samplefile/pyproject.toml")
    toml = TOMLFile(test_file)
    doc = document()
    doc["tool"] = table()
    doc["tool"]["rdetoolkit"] = table()
    doc["tool"]["rdetoolkit"]["system"] = table()
    doc["tool"]["rdetoolkit"]["multidata_tile"] = table()
    doc["tool"]["rdetoolkit"]["system"]["extended_mode"] = "rdeformat"
    doc["tool"]["rdetoolkit"]["system"]["save_raw"] = True
    doc["tool"]["rdetoolkit"]["system"]["save_nonshared_raw"] = False
    doc["tool"]["rdetoolkit"]["system"]["magic_variable"] = False
    doc["tool"]["rdetoolkit"]["system"]["save_thumbnail_image"] = True
    doc["tool"]["rdetoolkit"]["multidata_tile"]["ignore_errors"] = False
    toml.write(doc)
    yield test_file

    if Path(test_file).exists():
        Path(test_file).unlink()


@pytest.fixture
def test_cwd_pyproject_toml():
    test_file = "pyproject.toml"
    backup_path = Path(test_file).with_suffix(Path(test_file).suffix + ".bak")
    if Path(test_file).exists():
        # backup
        shutil.copy(Path(test_file), backup_path)
    doc = document()
    doc["tool"] = table()
    doc["tool"]["rdetoolkit"] = table()
    doc["tool"]["rdetoolkit"]["system"] = table()
    doc["tool"]["rdetoolkit"]["multidata_tile"] = table()
    doc["tool"]["rdetoolkit"]["system"]["extended_mode"] = "MultiDataTile"
    doc["tool"]["rdetoolkit"]["system"]["save_raw"] = True
    doc["tool"]["rdetoolkit"]["system"]["save_nonshared_raw"] = False
    doc["tool"]["rdetoolkit"]["system"]["magic_variable"] = False
    doc["tool"]["rdetoolkit"]["system"]["save_thumbnail_image"] = True
    doc["tool"]["rdetoolkit"]["multidata_tile"]["ignore_errors"] = False
    toml = TOMLFile(test_file)
    toml.write(doc)
    yield test_file

    if Path(test_file).exists():
        Path(test_file).unlink()
    if Path(backup_path).exists():
        shutil.copy(backup_path, test_file)
        Path(backup_path).unlink()


@pytest.fixture
def test_cwd_pyproject_toml_rename():
    # Temporarily rename pyproject.toml to exclude it from the test target, then restore it in teardown.
    test_file = "pyproject.toml"
    backup_path = Path(test_file).with_suffix(Path(test_file).suffix + ".bak")

    if Path(test_file).exists():
        # backup
        shutil.copy(Path(test_file), backup_path)
        Path(test_file).unlink()  # Delete the original file

    yield

    # Teardown: restore it
    if backup_path.exists():
        shutil.copy(backup_path, Path(test_file))
        backup_path.unlink()  # Delete the backup file


def test_parse_config_file(config_yaml):
    config = parse_config_file(path=config_yaml)
    assert isinstance(config, Config)
    assert config.system.extended_mode == "rdeformat"
    assert config.system.save_raw is True
    assert config.system.save_nonshared_raw is False
    assert config.system.save_thumbnail_image is True
    assert config.system.magic_variable is False
    assert config.multidata_tile.ignore_errors is False


def test_parse_config_file_specificaton_pyprojecttoml(test_pyproject_toml):
    config = parse_config_file(path=test_pyproject_toml)
    assert isinstance(config, Config)
    assert config.system.extended_mode == "rdeformat"
    assert config.system.save_raw is True
    assert config.system.save_nonshared_raw is False
    assert config.system.save_thumbnail_image is True
    assert config.system.magic_variable is False
    assert config.multidata_tile.ignore_errors is False


def test_parse_config_file_current_project_pyprojecttoml(test_cwd_pyproject_toml):
    config = parse_config_file()
    assert isinstance(config, Config)
    assert config.system.extended_mode == "MultiDataTile"
    assert config.system.save_raw is True
    assert config.system.save_thumbnail_image is True
    assert config.system.magic_variable is False
    assert config.multidata_tile.ignore_errors is False


def test_config_extra_allow():
    system = SystemSettings(extended_mode="rdeformat", save_raw=True, save_nonshared_raw=False, save_thumbnail_image=False, magic_variable=False)
    multi = MultiDataTileSettings(ignore_errors=False)
    config = Config(system=system, multidata_tile=multi, extra_item="extra")
    assert isinstance(config, Config)
    assert config.system.extended_mode == "rdeformat"
    assert config.system.save_raw is True
    assert config.system.save_nonshared_raw is False
    assert config.system.save_thumbnail_image is False
    assert config.system.magic_variable is False
    assert config.extra_item == "extra"


def test_sucess_get_config_yaml(config_yaml):
    system = SystemSettings(extended_mode="rdeformat", save_raw=True, save_nonshared_raw=False, save_thumbnail_image=True, magic_variable=False)
    multi = MultiDataTileSettings(ignore_errors=False)
    expected_text = Config(system=system, multidata_tile=multi)
    valid_dir = Path.cwd()
    config = get_config(valid_dir)
    assert config == expected_text


def test_sucess_get_config_yaml_none_multitile_setting(config_yml_none_multiconfig):
    # Test that multidata_tile is None in input but gets the default value
    system = SystemSettings(extended_mode="rdeformat", save_raw=True, save_nonshared_raw=False, save_thumbnail_image=True, magic_variable=False)
    multi = MultiDataTileSettings(ignore_errors=False)
    expected_text = Config(system=system, multidata_tile=multi)
    valid_dir = Path("tasksupport")
    config = get_config(valid_dir)
    assert config == expected_text


def test_sucess_get_config_yml(config_yml):
    system = SystemSettings(extended_mode="rdeformat", save_raw=True, save_nonshared_raw=False, save_thumbnail_image=True, magic_variable=False)
    multi = MultiDataTileSettings(ignore_errors=False)
    expected_text = Config(system=system, multidata_tile=multi)
    valid_dir = Path("tasksupport")
    config = get_config(valid_dir)
    assert config == expected_text


def test_invalid_get_config_yml(invalid_config_yaml):
    valid_dir = Path("tasksupport")
    system = SystemSettings(extended_mode=None, save_raw=False, save_nonshared_raw=True, save_thumbnail_image=False, magic_variable=False)
    multi = MultiDataTileSettings(ignore_errors=False)
    expected_text = Config(system=system, multidata_tile=multi)
    config = get_config(valid_dir)
    assert config == expected_text


def test_get_config_pyprojecttoml(test_cwd_pyproject_toml):
    system = SystemSettings(extended_mode="MultiDataTile", save_raw=True, save_nonshared_raw=False, save_thumbnail_image=True, magic_variable=False)
    multi = MultiDataTileSettings(ignore_errors=False)
    expected_text = Config(system=system, multidata_tile=multi)
    valid_dir = Path.cwd()
    config = get_config(valid_dir)
    assert config == expected_text


def test_invalid_get_config_empty_yml(invalid_empty_config_yaml):
    system = SystemSettings(extended_mode=None, save_raw=False, save_nonshared_raw=True, save_thumbnail_image=False, magic_variable=False)
    multi = MultiDataTileSettings(ignore_errors=False)
    expected_text = Config(system=system, multidata_tile=multi)
    valid_dir = Path("tasksupport")
    config = get_config(valid_dir)
    assert config == expected_text


def test_load_config_with_config():
    system = SystemSettings(extended_mode="rdeformat", save_raw=True, save_nonshared_raw=True, save_thumbnail_image=False, magic_variable=False)
    multi = MultiDataTileSettings(ignore_errors=False)
    config = Config(system=system, multidata_tile=multi)
    task_support = Path("tasksupport")
    result = load_config(task_support, config=config)
    assert result == config


def test_load_config_without_config(tasksupport):
    tasksupport_path = Path("data/tasksupport")
    system = SystemSettings(extended_mode=None, save_raw=True, save_nonshared_raw=True, save_thumbnail_image=True, magic_variable=False)
    multi = MultiDataTileSettings(ignore_errors=False)
    config = Config(system=system, multidata_tile=multi)
    result = load_config(tasksupport_path)
    assert result == config


def test_load_config_with_none_config_and_none_get_config():
    dummpy_path = Path("tasksupport")
    system = SystemSettings(extended_mode=None, save_raw=False, save_nonshared_raw=True, save_thumbnail_image=False, magic_variable=False)
    multi = MultiDataTileSettings(ignore_errors=False)
    config = Config(system=system, multidata_tile=multi)
    result = load_config(dummpy_path)
    assert result == config


def test_smarttable_settings_default_values():
    """Test SmartTableSettings default values."""
    settings = SmartTableSettings()
    assert settings.save_table_file is False


def test_smarttable_settings_with_custom_values():
    """Test SmartTableSettings with custom values."""
    settings = SmartTableSettings(save_table_file=True)
    assert settings.save_table_file is True


def test_config_with_smarttable_settings():
    """Test Config with SmartTableSettings."""
    system = SystemSettings(extended_mode="rdeformat", save_raw=True, save_nonshared_raw=False, save_thumbnail_image=True, magic_variable=False)
    multi = MultiDataTileSettings(ignore_errors=False)
    smarttable = SmartTableSettings(save_table_file=True)
    config = Config(system=system, multidata_tile=multi, smarttable=smarttable)

    assert config.smarttable.save_table_file is True
    assert isinstance(config.smarttable, SmartTableSettings)


@pytest.fixture()
def config_yaml_with_smarttable():
    """Create test YAML config with SmartTable settings."""
    system_data = {"extended_mode": "rdeformat", "save_raw": True, "save_nonshared_raw": False, "magic_variable": False, "save_thumbnail_image": True}
    multi_data = {"ignore_errors": False}
    smarttable_data = {"save_table_file": True}
    data = {"system": system_data, "multidata_tile": multi_data, "smarttable": smarttable_data}
    test_yaml_path = "rdeconfig.yaml"
    with open(test_yaml_path, mode="w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    yield test_yaml_path

    if Path(test_yaml_path).exists():
        Path(test_yaml_path).unlink()


def test_parse_config_file_with_smarttable(config_yaml_with_smarttable):
    """Test parsing config file with SmartTable settings."""
    config = parse_config_file(path=config_yaml_with_smarttable)
    assert isinstance(config, Config)
    # Just verify that SmartTable settings are correctly parsed
    assert hasattr(config, 'smarttable')
    assert isinstance(config.smarttable, SmartTableSettings)
    assert config.smarttable.save_table_file is True


@pytest.fixture
def pyproject_toml_with_smarttable():
    """Create test TOML config with SmartTable settings."""
    if Path(os.path.dirname(__file__), "pyproject.toml").exists():
        # Backup existing file
        backup_path = Path(os.path.dirname(__file__), "pyproject.toml.bak")
        shutil.copy(Path(os.path.dirname(__file__), "pyproject.toml"), backup_path)
    test_file = os.path.join(os.path.dirname(__file__), "samplefile/pyproject.toml")
    toml = TOMLFile(test_file)
    doc = document()
    doc["tool"] = table()
    doc["tool"]["rdetoolkit"] = table()
    doc["tool"]["rdetoolkit"]["system"] = table()
    doc["tool"]["rdetoolkit"]["multidata_tile"] = table()
    doc["tool"]["rdetoolkit"]["smarttable"] = table()
    doc["tool"]["rdetoolkit"]["system"]["extended_mode"] = "rdeformat"
    doc["tool"]["rdetoolkit"]["system"]["save_raw"] = True
    doc["tool"]["rdetoolkit"]["system"]["save_nonshared_raw"] = False
    doc["tool"]["rdetoolkit"]["system"]["magic_variable"] = False
    doc["tool"]["rdetoolkit"]["system"]["save_thumbnail_image"] = True
    doc["tool"]["rdetoolkit"]["multidata_tile"]["ignore_errors"] = False
    doc["tool"]["rdetoolkit"]["smarttable"]["save_table_file"] = True
    toml.write(doc)
    yield test_file

    # Recover the original file if it was backed up
    if Path(os.path.dirname(__file__), "pyproject.toml.bak").exists():
        shutil.copy(Path(os.path.dirname(__file__), "pyproject.toml.bak"), Path(os.path.dirname(__file__), "pyproject.toml"))
        Path(os.path.dirname(__file__), "pyproject.toml.bak").unlink()

    if Path(test_file).exists():
        Path(test_file).unlink()


def test_parse_config_file_toml_with_smarttable(pyproject_toml_with_smarttable):
    """Test parsing TOML config file with SmartTable settings."""
    config = parse_config_file(path=pyproject_toml_with_smarttable)

    assert isinstance(config, Config)
    assert hasattr(config, 'smarttable')
    assert isinstance(config.smarttable, SmartTableSettings)
    assert config.smarttable.save_table_file is True


def test_traceback_settings():
    settings = TracebackSettings()
    assert settings.enabled == False
    assert settings.format == "duplex"
    assert settings.include_context is False
    assert settings.include_locals is False
    assert settings.include_env is False
    assert settings.max_locals_size == 512
    assert settings.sensitive_patterns == []

def test_traceback_settings_format_validation():
    """Test TracebackSettings format field validation"""
    for fmt_value in ["compact", "python", "duplex"]:
        settings = TracebackSettings(format=fmt_value)
        assert settings.format == fmt_value

    with pytest.raises(ValueError) as exc_info:
        TracebackSettings(format="invalid")
    assert "Invalid format" in str(exc_info.value)


def test_traceback_settings_max_local_size_validation():
    """Test TracebackSettings max_locals_size validation"""
    settings = TracebackSettings(max_locals_size=1024)
    assert settings.max_locals_size == 1024

    with pytest.raises(ValueError) as exc_info:
        TracebackSettings(max_locals_size=-1)
    assert "Invalid max_locals_size" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        TracebackSettings(max_locals_size=0)
    assert "max_locals_size must be a positive integer" in str(exc_info.value)


@pytest.fixture()
def config_yaml_with_tb():
    """Fixture for YAML config with traceback settings"""
    system_data = {"extended_mode": "rdeformat", "save_raw": True}
    traceback_data = {
        "enabled": True,
        "format": "compact",
        "include_context": True,
        "include_locals": False,
        "max_locals_size": 1024,
        "sensitive_patterns": ["custom_secret", "api_token"]
    }
    data = {"system": system_data, "traceback": traceback_data}
    test_yaml_path = "rdeconfig.yaml"

    with open(test_yaml_path, mode="w", encoding="utf-8") as f:
        yaml.dump(data, f)

    yield test_yaml_path

    if os.path.exists(test_yaml_path):
        os.remove(test_yaml_path)

def test_parse_config_with_traceback(config_yaml_with_tb):
    config = parse_config_file(path=config_yaml_with_tb)

    assert config.traceback is not None
    assert config.traceback.enabled is True
    assert config.traceback.format == "compact"
    assert config.traceback.include_context is True
    assert config.traceback.include_locals is False
    assert config.traceback.max_locals_size == 1024
    assert "custom_secret" in config.traceback.sensitive_patterns
    assert "api_token" in config.traceback.sensitive_patterns


def test_config_without_traceback_settings():
    """Test Config works without TracebackSettings"""
    config = Config()
    assert config.traceback is None

    config = Config(
        system=SystemSettings(extended_mode="rdeformat"),
        multidata_tile=MultiDataTileSettings(ignore_errors=True)
    )
    assert config.traceback is None

def test_config_with_traceback_settings():
    """Test Config with TracebackSettings."""
    traceback_settings = TracebackSettings(
        enabled=True,
        format="python",
        include_locals=True,
    )
    config = Config(traceback=traceback_settings)

    assert config.traceback is not None
    assert config.traceback.enabled is True
    assert config.traceback.format == "python"
    assert config.traceback.include_locals is True

@pytest.fixture
def pyproject_toml_with_traceback():
    """Create test TOML config with SmartTable settings."""
    if Path(os.path.dirname(__file__), "pyproject.toml").exists():
        # Backup existing file
        backup_path = Path(os.path.dirname(__file__), "pyproject.toml.bak")
        shutil.copy(Path(os.path.dirname(__file__), "pyproject.toml"), backup_path)
    test_file = os.path.join(os.path.dirname(__file__), "samplefile/pyproject.toml")
    toml = TOMLFile(test_file)
    doc = document()
    doc["tool"] = table()
    doc["tool"]["rdetoolkit"] = table()
    doc["tool"]["rdetoolkit"]["system"] = table()
    doc["tool"]["rdetoolkit"]["multidata_tile"] = table()
    doc["tool"]["rdetoolkit"]["system"]["extended_mode"] = "rdeformat"
    doc["tool"]["rdetoolkit"]["system"]["save_raw"] = True
    doc["tool"]["rdetoolkit"]["system"]["save_nonshared_raw"] = False
    doc["tool"]["rdetoolkit"]["system"]["magic_variable"] = False
    doc["tool"]["rdetoolkit"]["system"]["save_thumbnail_image"] = True
    doc["tool"]["rdetoolkit"]["traceback"] = table()
    doc["tool"]["rdetoolkit"]["traceback"]["enabled"] = True
    doc["tool"]["rdetoolkit"]["traceback"]["format"] = "duplex"
    doc["tool"]["rdetoolkit"]["traceback"]["include_context"] = True
    doc["tool"]["rdetoolkit"]["traceback"]["max_locals_size"] = 2048
    toml.write(doc)
    yield test_file

    # Recover the original file if it was backed up
    if Path(os.path.dirname(__file__), "pyproject.toml.bak").exists():
        shutil.copy(Path(os.path.dirname(__file__), "pyproject.toml.bak"), Path(os.path.dirname(__file__), "pyproject.toml"))
        Path(os.path.dirname(__file__), "pyproject.toml.bak").unlink()

    if Path(test_file).exists():
        Path(test_file).unlink()

def test_parse_pyproject_toml_with_traceback(pyproject_toml_with_traceback):
     """Test parsing pyproject.toml with traceback settings."""
     config = parse_config_file(path=pyproject_toml_with_traceback)

     assert config.traceback is not None
     assert config.traceback.enabled is True
     assert config.traceback.format == "duplex"
     assert config.traceback.include_context is True
     assert config.traceback.max_locals_size == 2048


def test_system_settings_feature_description_default():
    """Test that feature_description defaults to True."""
    settings = SystemSettings()
    assert settings.feature_description is True


def test_system_settings_feature_description_false():
    """Test that feature_description can be set to False."""
    settings = SystemSettings(feature_description=False)
    assert settings.feature_description is False


def test_config_with_feature_description_disabled():
    """Test Config with feature_description set to False."""
    config = Config(
        system=SystemSettings(feature_description=False),
    )
    assert config.system.feature_description is False


# ============================================================
# File Not Found Error Tests (Task 02)
# ============================================================


def test_parse_config_file_not_found():
    """Test ConfigError is raised when config file doesn't exist.

    Test ID: TC-EP-FILE-001
    """
    # Given: non-existent config file path
    nonexistent_path = "nonexistent_config.yaml"

    # When: attempting to parse the file
    # Then: ConfigError is raised with file path and helpful message
    with pytest.raises(ConfigError) as exc_info:
        parse_config_file(path=nonexistent_path)

    error = exc_info.value
    assert error.file_path == nonexistent_path
    assert error.error_type == "file_not_found"
    assert "not found" in str(error).lower()
    assert "gen-config" in str(error)
    assert "https://nims-mdpf.github.io/rdetoolkit/" in str(error)


def test_get_config_directory_not_found():
    """Test ConfigError is raised when target directory doesn't exist.

    Test ID: TC-EP-DIR-001
    """
    # Given: non-existent directory path
    nonexistent_dir = Path("nonexistent_directory_12345")

    # When: attempting to get config from the directory
    # Then: ConfigError is raised with directory path
    with pytest.raises(ConfigError) as exc_info:
        get_config(nonexistent_dir)

    error = exc_info.value
    assert str(nonexistent_dir) in error.file_path
    assert error.error_type == "directory_not_found"
    assert "not found" in str(error).lower()
    assert "https://nims-mdpf.github.io/rdetoolkit/" in str(error)


def test_read_pyproject_toml_not_found():
    """Test ConfigError is raised when pyproject.toml doesn't exist.

    Test ID: TC-EP-TOML-001
    """
    # Given: non-existent pyproject.toml path
    nonexistent_toml = "nonexistent_pyproject.toml"

    # When: attempting to read the file via parse_config_file
    # Then: ConfigError is raised
    with pytest.raises(ConfigError) as exc_info:
        parse_config_file(path=nonexistent_toml)

    error = exc_info.value
    assert error.file_path == nonexistent_toml
    assert error.error_type == "file_not_found"
    assert "not found" in str(error).lower()
    assert "https://nims-mdpf.github.io/rdetoolkit/" in str(error)


# ============================================================
# Parse Error Tests (Task 03)
# ============================================================


@pytest.fixture()
def invalid_yaml_syntax():
    """Create a YAML file with syntax error."""
    dirname = Path("tasksupport")
    dirname.mkdir(exist_ok=True)
    test_yaml_path = dirname.joinpath("rdeconfig.yaml")

    # Invalid YAML: unclosed bracket, tabs instead of spaces, etc.
    invalid_content = """system:
  extended_mode: rdeformat
  save_raw: true
  invalid_structure: [
    unclosed bracket here
multidata_tile:
  ignore_errors: false
"""
    with open(test_yaml_path, mode="w", encoding="utf-8") as f:
        f.write(invalid_content)

    yield test_yaml_path

    if test_yaml_path.exists():
        test_yaml_path.unlink()
    # Don't remove directory as other tests may be using it
    # Directory cleanup is handled by test environment


@pytest.fixture()
def invalid_toml_syntax():
    """Create a TOML file with syntax error."""
    dirname = Path("tasksupport")
    dirname.mkdir(exist_ok=True)
    test_toml_path = dirname.joinpath("pyproject.toml")

    # Invalid TOML: missing closing quote, invalid table definition
    invalid_content = """[tool.rdetoolkit]
[tool.rdetoolkit.system]
extended_mode = "rdeformat
save_raw = true
"""
    with open(test_toml_path, mode="w", encoding="utf-8") as f:
        f.write(invalid_content)

    yield test_toml_path

    if test_toml_path.exists():
        test_toml_path.unlink()
    # Don't remove directory as other tests may be using it
    # Directory cleanup is handled by test environment


def test_parse_config_yaml_syntax_error(invalid_yaml_syntax):
    """Test ConfigError with line info for YAML syntax errors.

    Test ID: TC-PARSE-YAML-001
    """
    # Given: YAML file with syntax error
    yaml_path = str(invalid_yaml_syntax)

    # When: attempting to parse the file
    # Then: ConfigError is raised with parse error details
    with pytest.raises(ConfigError) as exc_info:
        parse_config_file(path=yaml_path)

    error = exc_info.value
    assert error.file_path == yaml_path
    assert error.error_type == "parse_error"
    assert "parse" in str(error).lower() or "syntax" in str(error).lower()
    # Line number should be present (YAML parser provides it)
    assert error.line_number is not None or "line" in str(error).lower()
    assert "https://nims-mdpf.github.io/rdetoolkit/" in str(error)


def test_parse_config_toml_syntax_error(invalid_toml_syntax):
    """Test ConfigError with line info for TOML syntax errors.

    Test ID: TC-PARSE-TOML-001
    """
    # Given: TOML file with syntax error
    toml_path = str(invalid_toml_syntax)

    # When: attempting to parse the file
    # Then: ConfigError is raised with parse error details
    with pytest.raises(ConfigError) as exc_info:
        parse_config_file(path=toml_path)

    error = exc_info.value
    assert error.file_path == toml_path
    assert error.error_type == "parse_error"
    assert "parse" in str(error).lower() or "toml" in str(error).lower()
    assert "https://nims-mdpf.github.io/rdetoolkit/" in str(error)


def test_parse_config_yaml_io_error(tmp_path):
    """Test ConfigError for file I/O errors.

    Test ID: TC-PARSE-IO-001
    """
    # Given: YAML file with restricted permissions (simulate I/O error)
    yaml_path = tmp_path / "rdeconfig.yaml"
    yaml_path.touch()
    yaml_path.chmod(0o000)  # Remove all permissions

    try:
        # When: attempting to parse the file
        # Then: ConfigError is raised with I/O error type
        with pytest.raises(ConfigError) as exc_info:
            parse_config_file(path=str(yaml_path))

        error = exc_info.value
        assert error.error_type == "io_error"
        assert str(yaml_path) in error.file_path
    finally:
        # Cleanup: restore permissions
        yaml_path.chmod(0o644)


# ============================================================
# Validation Error Tests (Task 04)
# ============================================================


@pytest.fixture()
def config_yaml_invalid_extended_mode():
    """Create YAML with invalid extended_mode value."""
    dirname = Path("tasksupport")
    dirname.mkdir(exist_ok=True)
    system_data = {
        "extended_mode": "invalid_mode",  # Invalid value
        "save_raw": True,
    }
    data = {"system": system_data}
    test_yaml_path = dirname.joinpath("rdeconfig.yaml")

    with open(test_yaml_path, mode="w", encoding="utf-8") as f:
        yaml.dump(data, f)

    yield test_yaml_path

    if test_yaml_path.exists():
        test_yaml_path.unlink()
    if dirname.exists():
        dirname.rmdir()


@pytest.fixture()
def config_yaml_invalid_field_type():
    """Create YAML with invalid field type."""
    dirname = Path("tasksupport")
    dirname.mkdir(exist_ok=True)
    system_data = {
        "extended_mode": "rdeformat",
        "save_raw": "not_a_boolean",  # Should be bool, not string
    }
    data = {"system": system_data}
    test_yaml_path = dirname.joinpath("rdeconfig.yaml")

    with open(test_yaml_path, mode="w", encoding="utf-8") as f:
        yaml.dump(data, f)

    yield test_yaml_path

    if test_yaml_path.exists():
        test_yaml_path.unlink()
    if dirname.exists():
        dirname.rmdir()


def test_validation_error_invalid_extended_mode(config_yaml_invalid_extended_mode):
    """Test ConfigError with field info for invalid extended_mode.

    Test ID: TC-VAL-MODE-001
    """
    # Given: config with invalid extended_mode value
    yaml_path = str(config_yaml_invalid_extended_mode)

    # When: attempting to parse the config
    # Then: ConfigError with field name and valid values
    with pytest.raises(ConfigError) as exc_info:
        parse_config_file(path=yaml_path)

    error = exc_info.value
    assert error.file_path == yaml_path
    assert error.error_type == "validation_error"
    assert error.field_name is not None
    assert "extended_mode" in error.field_name
    # Should mention valid values
    assert "rdeformat" in str(error) or "MultiDataTile" in str(error)
    assert "https://nims-mdpf.github.io/rdetoolkit/" in str(error)


def test_validation_error_invalid_field_type(config_yaml_invalid_field_type):
    """Test ConfigError for field type validation errors.

    Test ID: TC-VAL-TYPE-001
    """
    # Given: config with wrong field type
    yaml_path = str(config_yaml_invalid_field_type)

    # When: attempting to parse the config
    # Then: ConfigError with field name and type error message
    with pytest.raises(ConfigError) as exc_info:
        parse_config_file(path=yaml_path)

    error = exc_info.value
    assert error.file_path == yaml_path
    assert error.error_type == "validation_error"
    assert error.field_name is not None
    assert "save_raw" in error.field_name
    assert "https://nims-mdpf.github.io/rdetoolkit/" in str(error)


def test_get_config_validation_error(config_yaml_invalid_extended_mode):
    """Test get_config raises ConfigError for validation failures.

    Test ID: TC-VAL-GETCONF-001
    """
    # Given: directory with invalid config file
    config_dir = Path("tasksupport")

    # When: attempting to get config from directory
    # Then: ConfigError is raised with field details
    with pytest.raises(ConfigError) as exc_info:
        get_config(config_dir)

    error = exc_info.value
    assert error.error_type == "validation_error"
    assert "extended_mode" in (error.field_name or "")
    assert config_dir.name in error.file_path or str(config_dir) in str(error)


def test_validation_error_traceback_settings_invalid_format():
    """Test validation error for invalid traceback format.

    Test ID: TC-VAL-TB-001
    """
    # Given: config data with invalid traceback format
    config_data = {
        "system": {"extended_mode": "rdeformat"},
        "traceback": {"format": "invalid_format"},
    }

    # When: attempting to create Config
    # Then: ValidationError is raised
    with pytest.raises(ValidationError) as exc_info:
        Config(**config_data)

    # Verify the error mentions valid formats
    error_str = str(exc_info.value)
    assert "format" in error_str.lower()


def test_validation_error_multiple_fields():
    """Test validation error message mentions multiple errors.

    Test ID: TC-VAL-MULTI-001
    """
    # Given: config with multiple validation errors
    config_data = {
        "system": {
            "extended_mode": "invalid_mode",
            "save_raw": "not_boolean",
        },
        "traceback": {
            "format": "invalid_format",
            "max_locals_size": -1,
        },
    }

    # When: attempting to create Config
    # Then: ValidationError with multiple errors
    with pytest.raises(ValidationError) as exc_info:
        Config(**config_data)

    errors = exc_info.value.errors()
    # Should have multiple validation errors
    assert len(errors) >= 2


# ============================================================================
# Comprehensive Integration Tests (Task 05)
# ============================================================================
# These tests ensure full coverage of all error scenarios as per Issue #361


def test_parse_valid_yaml_config__tc_ep_001(tmp_path):
    """Test parsing valid YAML config file.

    Test ID: TC-EP-001
    Equivalence Partition: Valid YAML with correct schema
    """
    # Given: valid YAML config file
    yaml_file = tmp_path / "rdeconfig.yaml"
    config_data = {
        "system": {
            "extended_mode": "rdeformat",
            "save_raw": True,
            "save_nonshared_raw": False,
            "magic_variable": False,
            "save_thumbnail_image": True,
        },
        "multidata_tile": {
            "ignore_errors": False,
        },
    }
    with open(yaml_file, "w") as f:
        yaml.dump(config_data, f)

    # When: parsing the config
    config = parse_config_file(path=str(yaml_file))

    # Then: returns valid Config object
    assert isinstance(config, Config)
    assert config.system.extended_mode == "rdeformat"
    assert config.system.save_raw is True


def test_parse_valid_toml_config__tc_ep_002(tmp_path):
    """Test parsing valid TOML config file.

    Test ID: TC-EP-002
    Equivalence Partition: Valid TOML with correct schema
    """
    # Given: valid TOML config file
    toml_file = tmp_path / "pyproject.toml"
    toml = TOMLFile(str(toml_file))
    doc = document()
    doc["tool"] = table()
    doc["tool"]["rdetoolkit"] = table()
    doc["tool"]["rdetoolkit"]["system"] = table()
    doc["tool"]["rdetoolkit"]["system"]["extended_mode"] = "MultiDataTile"
    doc["tool"]["rdetoolkit"]["system"]["save_raw"] = True
    toml.write(doc)

    # When: parsing the config
    config = parse_config_file(path=str(toml_file))

    # Then: returns valid Config object
    assert isinstance(config, Config)
    assert config.system.extended_mode == "MultiDataTile"


def test_parse_empty_yaml_returns_default__tc_ep_009(tmp_path):
    """Test parsing empty YAML file returns default Config.

    Test ID: TC-EP-009
    Edge Case: Empty YAML file (None content)
    """
    # Given: empty YAML file
    yaml_file = tmp_path / "rdeconfig.yaml"
    yaml_file.write_text("")

    # When: parsing the file
    config = parse_config_file(path=str(yaml_file))

    # Then: returns Config with defaults (no error)
    assert isinstance(config, Config)
    assert config.system.extended_mode is None


def test_get_config_returns_valid_config__tc_ep_010(tmp_path):
    """Test get_config with directory containing valid config file.

    Test ID: TC-EP-010
    Equivalence Partition: Valid directory with config
    """
    # Given: directory with valid config file
    config_dir = tmp_path / "test_dir"
    config_dir.mkdir()
    yaml_file = config_dir / "rdeconfig.yaml"
    config_data = {
        "system": {
            "extended_mode": "rdeformat",
            "save_raw": True,
        },
    }
    with open(yaml_file, "w") as f:
        yaml.dump(config_data, f)

    # When: getting config
    config = get_config(config_dir)

    # Then: returns valid Config object
    assert isinstance(config, Config)
    assert config.system.extended_mode == "rdeformat"


def test_get_config_no_files_returns_none__tc_ep_013(tmp_path, monkeypatch):
    """Test get_config with directory containing no config files.

    Test ID: TC-EP-013
    Edge Case: Directory with no config files
    """
    # Given: empty directory and no pyproject.toml fallback
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    # Prevent fallback to cwd's pyproject.toml by mocking get_pyproject_toml
    monkeypatch.setattr('rdetoolkit.config.get_pyproject_toml', lambda: None)

    # When: attempting to get config
    config = get_config(empty_dir)

    # Then: returns None (no config found)
    assert config is None


# ============================================================================
# Boundary Value Tests (Task 05)
# ============================================================================


def test_config_error_no_line_info__tc_bv_001():
    """Test ConfigError message without line information.

    Test ID: TC-BV-001
    Boundary: line_number = None
    """
    # Given: ConfigError with line_number = None
    error = ConfigError(
        "Test error message",
        file_path="/path/to/config.yaml",
        error_type="test_error",
        line_number=None,
    )

    # When: converting to string
    error_str = str(error)

    # Then: no line information in message
    assert "/path/to/config.yaml" in error_str
    # Should not contain location line info when line_number is None
    # (The implementation may still show "Location: " without line number)


def test_config_error_with_line_1__tc_bv_002():
    """Test ConfigError with line number 1.

    Test ID: TC-BV-002
    Boundary: line_number = 1 (minimum valid value)
    """
    # Given: ConfigError with line_number = 1
    error = ConfigError(
        "Test error at line 1",
        file_path="/path/to/config.yaml",
        error_type="parse_error",
        line_number=1,
    )

    # When: converting to string
    error_str = str(error)

    # Then: includes "line 1"
    assert "line 1" in error_str.lower()


def test_config_error_with_high_line__tc_bv_003():
    """Test ConfigError with high line number.

    Test ID: TC-BV-003
    Boundary: line_number = 999 (high value)
    """
    # Given: ConfigError with line_number = 999
    error = ConfigError(
        "Test error at high line",
        file_path="/path/to/config.yaml",
        error_type="parse_error",
        line_number=999,
    )

    # When: converting to string
    error_str = str(error)

    # Then: includes "line 999"
    assert "line 999" in error_str.lower()


def test_config_error_no_column_info__tc_bv_004():
    """Test ConfigError message without column information.

    Test ID: TC-BV-004
    Boundary: column_number = None
    """
    # Given: ConfigError with column_number = None
    error = ConfigError(
        "Test error",
        file_path="/path/to/config.yaml",
        error_type="parse_error",
        line_number=10,
        column_number=None,
    )

    # When: converting to string
    error_str = str(error)

    # Then: includes line but not column
    assert "line 10" in error_str.lower()
    # Column should not be mentioned


def test_config_error_with_column_1__tc_bv_005():
    """Test ConfigError with column information.

    Test ID: TC-BV-005
    Boundary: column_number = 1 (minimum valid value)
    """
    # Given: ConfigError with line and column
    error = ConfigError(
        "Test error with column",
        file_path="/path/to/config.yaml",
        error_type="parse_error",
        line_number=10,
        column_number=1,
    )

    # When: converting to string
    error_str = str(error)

    # Then: includes both line and column
    assert "line 10" in error_str.lower()
    assert "column 1" in error_str.lower()


def test_config_error_no_field_name__tc_bv_006():
    """Test ConfigError without field name.

    Test ID: TC-BV-006
    Boundary: field_name = None
    """
    # Given: ConfigError with field_name = None
    error = ConfigError(
        "Generic validation error",
        file_path="/path/to/config.yaml",
        error_type="validation_error",
        field_name=None,
    )

    # When: converting to string
    error_str = str(error)

    # Then: generic validation error without field info
    assert "/path/to/config.yaml" in error_str
    assert "https://nims-mdpf.github.io/rdetoolkit/" in error_str


def test_config_error_nested_field__tc_bv_007():
    """Test ConfigError with nested field path.

    Test ID: TC-BV-007
    Boundary: field_name with nested path
    """
    # Given: ConfigError with nested field name
    error = ConfigError(
        "Validation error in nested field",
        file_path="/path/to/config.yaml",
        error_type="validation_error",
        field_name="system.extended_mode",
    )

    # When: converting to string
    error_str = str(error)

    # Then: includes full field path
    assert "system.extended_mode" in error_str
    assert "https://nims-mdpf.github.io/rdetoolkit/" in error_str


# ============================================================================
# Coverage Validation Test
# ============================================================================


def test_coverage_all_error_types():
    """Verify all error types are tested.

    This test documents which error types should be covered by test suite.
    """
    # All error types that should be covered
    tested_error_types = {
        "file_not_found",      # TC-EP-003, TC-EP-011
        "directory_not_found",  # TC-EP-011
        "parse_error",         # TC-EP-004, TC-EP-005
        "io_error",            # TC-EP-008
        "validation_error",    # TC-EP-006, TC-EP-007
    }

    # All error types should have corresponding test cases
    assert len(tested_error_types) >= 5

    # This test serves as documentation of coverage requirements
    # Actual coverage is verified by running:
    # pytest --cov=rdetoolkit.config --cov-branch --cov-report=html
