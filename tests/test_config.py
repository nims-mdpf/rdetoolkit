import os
from pathlib import Path
import shutil

import pytest
import yaml
from rdetoolkit.config import is_toml, is_yaml, parse_config_file, get_config, load_config
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
    # 一時的にpyproject.tomlをリネームして、テストの対象ファイルから外す。teardownで元に戻す。
    test_file = "pyproject.toml"
    backup_path = Path(test_file).with_suffix(Path(test_file).suffix + ".bak")

    if Path(test_file).exists():
        # backup
        shutil.copy(Path(test_file), backup_path)
        Path(test_file).unlink()  # 元のファイルを削除

    yield

    # teardown: 元に戻す
    if backup_path.exists():
        shutil.copy(backup_path, Path(test_file))
        backup_path.unlink()  # バックアップファイルを削除


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
    # 入力ではmultidata_tileはNoneだが、デフォルト値が格納されることをテスト
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
