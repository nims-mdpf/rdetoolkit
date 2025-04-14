import json
from pathlib import Path
import shutil
from typing import Optional
import pytest
import yaml
import toml

from rdetoolkit.workflows import run
from rdetoolkit.models.config import Config, SystemSettings, MultiDataTileSettings


@pytest.fixture
def pre_invoice_filepath():
    invoice_path = Path("data/invoice")
    invoice_path.mkdir(parents=True, exist_ok=True)
    invoice_filepath = Path(__file__).parent.joinpath("samplefile", "invoice.json")
    shutil.copy2(invoice_filepath, invoice_path.joinpath("invoice.json"))

    yield invoice_path.joinpath("invoice.json")

    if invoice_path.joinpath("invoice.json").exists():
        invoice_path.joinpath("invoice.json").unlink()


@pytest.fixture
def pre_schema_filepath():
    tasksupport_path = Path("data/tasksupport")
    tasksupport_path.mkdir(parents=True, exist_ok=True)
    schema_filepath = Path(__file__).parent.joinpath("samplefile", "invoice.schema.json")
    shutil.copy2(schema_filepath, tasksupport_path.joinpath("invoice.schema.json"))

    yield tasksupport_path.joinpath("invoice.schema.json")

    if tasksupport_path.joinpath("invoice.schema.json").exists():
        tasksupport_path.joinpath("invoice.schema.json").unlink()


@pytest.fixture
def metadata_def_json_file():
    Path("data/tasksupport").mkdir(parents=True, exist_ok=True)
    json_path = Path("data/tasksupport").joinpath("metadata-def.json")
    json_data = {
        "constant": {"test_meta1": {"value": "value"}, "test_meta2": {"value": 100}, "test_meta3": {"value": True}},
        "variable": [
            {"test_meta1": {"value": "v1"}, "test_meta2": {"value": 200, "unit": "m"}, "test_meta3": {"value": False}},
            {"test_meta1": {"value": "v1"}, "test_meta2": {"value": 200, "unit": "m"}, "test_meta3": {"value": False}},
        ],
    }
    with open(json_path, mode="w", encoding="utf-8") as json_file:
        json.dump(json_data, json_file, ensure_ascii=False, indent=4)

    yield json_path

    if json_path.exists():
        json_path.unlink()
    if Path("temp").exists():
        shutil.rmtree("temp")


def custom_config_yaml_file(mode: Optional[str], filename: str):
    dirname = Path("data/tasksupport")
    data = {"extended_mode": mode, "save_raw": True, "magic_variable": False, "save_thumbnail_image": True}

    if Path(filename).suffix == ".toml":
        test_toml_path = dirname.joinpath(filename)
        with open(test_toml_path, mode="w", encoding="utf-8") as f:
            toml.dump(data, f)
    elif Path(filename).suffix in [".yaml", ".yml"]:
        test_yaml_path = dirname.joinpath(filename)
        with open(test_yaml_path, mode="w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def test_run_config_args(inputfile_single, tasksupport, metadata_def_json_file, pre_schema_filepath, pre_invoice_filepath, metadata_json):
    """configが引数として渡された場合"""
    config = Config(system=SystemSettings(extended_mode=None, save_raw=False, save_thumbnail_image=False, magic_variable=False), multidata_tile=MultiDataTileSettings(ignore_errors=False))
    run(config=config)
    assert config is not None
    assert config.system.extended_mode is None
    assert config.system.save_raw is False
    assert config.system.save_thumbnail_image is False
    assert config.system.magic_variable is False
    assert config.multidata_tile.ignore_errors is False


@pytest.mark.parametrize("config_file", ["rdeconfig.yaml", "pyproject.toml", "rdeconfig.yml"])
def test_run_config_file_rdeformat_mode(
    inputfile_rdeformat, tasksupport, metadata_def_json_file, pre_schema_filepath, pre_invoice_filepath, metadata_json, config_file,
):
    """configが引数Noneでファイルとして渡された場合"""
    if Path("data/tasksupport/rdeconfig.yml").exists():
        Path("data/tasksupport/rdeconfig.yml").unlink()
    custom_config_yaml_file("rdeformat", config_file)
    config = Config(system=SystemSettings(extended_mode="rdeformat", save_raw=False, save_thumbnail_image=False, magic_variable=False), multidata_tile=MultiDataTileSettings(ignore_errors=False))
    run()
    assert config is not None
    assert config.system.extended_mode == "rdeformat"
    assert config.system.save_raw is False
    assert config.system.save_thumbnail_image is False
    assert config.system.magic_variable is False
    assert config.multidata_tile.ignore_errors is False


@pytest.mark.parametrize("config_file", ["rdeconfig.yaml", "pyproject.toml", "rdeconfig.yml"])
def test_run_config_file_multifile_mode(
    inputfile_multimode, tasksupport, metadata_def_json_file, pre_schema_filepath, pre_invoice_filepath, metadata_json, config_file,
):
    """configが引数Noneでファイルとして渡された場合"""
    if Path("data/tasksupport/rdeconfig.yml").exists():
        Path("data/tasksupport/rdeconfig.yml").unlink()
    custom_config_yaml_file("MultiDataTile", config_file)
    config = Config(system=SystemSettings(extended_mode="MultiDataTile", save_raw=False, save_thumbnail_image=False, magic_variable=False), multidata_tile=MultiDataTileSettings(ignore_errors=False))
    run()
    assert config is not None
    assert config.system.extended_mode == "MultiDataTile"
    assert config.system.save_raw is False
    assert config.system.save_thumbnail_image is False
    assert config.system.magic_variable is False
    assert config.multidata_tile.ignore_errors is False


def test_run_empty_config(
    inputfile_single, tasksupport_empty_config, metadata_def_json_file, pre_schema_filepath, pre_invoice_filepath, metadata_json,
):
    """configファイルの実態はあるがファイル内容が空の場合"""
    config = Config(system=SystemSettings(extended_mode=None, save_raw=True, save_thumbnail_image=False, magic_variable=False), multidata_tile=MultiDataTileSettings(ignore_errors=False))
    run()
    assert config is not None
    assert config.system.extended_mode is None
    assert config.system.save_raw is True
    assert config.system.save_thumbnail_image is False
    assert config.system.magic_variable is False
    assert config.multidata_tile.ignore_errors is False


# def test_multidatatile_mode_process():
#     __config = Config()
#     __config.system.extended_mode = "multidatatile"
#     __config.multidata_tile.ignore_errors = True

#     srcpaths = RdeInputDirPaths(
#         inputdata=Path("path/to/inputdata"),
#         invoice=Path("path/to/invoice"),
#         tasksupport=Path("path/to/tasksupport"),
#         config=__config
#     )

#     resource_paths = RdeOutputResourcePath(
#         invoice=Path("path/to/invoice"),
#         invoice_org=Path("path/to/invoice_org"),
#         raw=Path("path/to/raw"),
#         rawfiles=(Path("path/to/rawfile1"), Path("path/to/rawfile2")),
#         thumbnail=Path("path/to/thumbnail"),
#         main_image=Path("path/to/main_image"),
#         other_image=Path("path/to/other_image"),
#         meta=Path("path/to/meta"),
#         struct=Path("path/to/struct"),
#         logs=Path("path/to/logs"),
#         nonshared_raw=Path("path/to/nonshared_raw"),
#         invoice_schema_json=Path("path/to/invoice_schema_json")
#     )

#     logger = logging.getLogger("test_logger")
#     logger.setLevel(logging.WARNING)

#     def custom_function(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
#         raise Exception("Exception raised")

#     with patch("src.rdetoolkit.workflows.multifile_mode_process") as mock_multifile_mode_process:
#         with skip_exception_context(Exception, logger=logger, enabled=__config.multidata_tile.ignore_errors):
#             multifile_mode_process(srcpaths, resource_paths, custom_function)

#     mock_multifile_mode_process.assert_called_once_with(srcpaths, resource_paths, custom_function)

#     logger.warning.assert_called_once_with("Skipped exception: Exception raised")
