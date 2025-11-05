import json
from pathlib import Path
import shutil
from typing import Optional
import pytest
import yaml
import toml

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.workflows import run, _process_mode, _create_error_status
from rdetoolkit.models.config import Config, SystemSettings, MultiDataTileSettings
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath


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


def test_multidatatitle_ignore_errors_collects_structured_error(monkeypatch, tmp_path):
    """ignore_errors=True の MultiDataTile で StructuredError が捕捉され、ジョブが継続できることを確認する"""
    input_dir = tmp_path / "inputdata"
    tasksupport_dir = tmp_path / "tasksupport"
    invoice_dir = tmp_path / "invoice"
    for directory in (input_dir, tasksupport_dir, invoice_dir):
        directory.mkdir(parents=True, exist_ok=True)

    raw_file = input_dir / "sample.txt"
    raw_file.write_text("dummy", encoding="utf-8")
    (tasksupport_dir / "invoice.schema.json").write_text("{}", encoding="utf-8")
    (tasksupport_dir / "invoice_org.json").write_text("{}", encoding="utf-8")

    rdeoutput_resource = RdeOutputResourcePath(
        raw=tmp_path / "raw",
        nonshared_raw=tmp_path / "nonshared_raw",
        rawfiles=(raw_file,),
        struct=tmp_path / "struct",
        main_image=tmp_path / "main_image",
        other_image=tmp_path / "other_image",
        meta=tmp_path / "meta",
        thumbnail=tmp_path / "thumbnail",
        logs=tmp_path / "logs",
        invoice=invoice_dir,
        invoice_schema_json=tasksupport_dir / "invoice.schema.json",
        invoice_org=tasksupport_dir / "invoice_org.json",
        temp=tmp_path / "temp",
    )

    config = Config(
        system=SystemSettings(extended_mode="MultiDataTile", save_raw=True, save_thumbnail_image=False, magic_variable=False),
        multidata_tile=MultiDataTileSettings(ignore_errors=True),
    )

    srcpaths = RdeInputDirPaths(
        inputdata=input_dir,
        invoice=invoice_dir,
        tasksupport=tasksupport_dir,
        config=config,
    )

    error_message = "温度数とサイクル数が不一致です。invoiceで1個の温度を指定してください。"
    structured_error = StructuredError(error_message, ecode=1060)

    def raise_structured_error(*_args, **_kwargs):
        raise structured_error

    monkeypatch.setattr("rdetoolkit.workflows.multifile_mode_process", raise_structured_error)

    status, error_info, mode = _process_mode(
        idx=0,
        srcpaths=srcpaths,
        rdeoutput_resource=rdeoutput_resource,
        config=config,
        excel_invoice_files=None,
        smarttable_file=None,
        custom_dataset_function=None,
        logger=None,
    )

    assert status is None
    assert mode == "MultiDataTile"
    assert error_info["code"] == 1060
    assert error_message in (error_info["message"] or "")
    assert "StructuredError" in (error_info["stacktrace"] or "")

    failure_status = _create_error_status(0, error_info, rdeoutput_resource, mode)
    assert failure_status.status == "failed"
    assert failure_status.error_code == 1060
    assert error_message in (failure_status.error_message or "")
    assert str(raw_file) in (failure_status.target or "")


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


def test_structured_error_propagation_in_workflow(tmp_path, monkeypatch):
    """Test that StructuredError from custom dataset function propagates correctly to job.failed.
    
    This test reproduces the issue reported in issue_203 where custom error messages
    and codes were not being written to job.failed correctly.
    """
    from rdetoolkit.errors import catch_exception_with_message
    from rdetoolkit.exceptions import StructuredError
    from unittest.mock import patch
    import tempfile
    import os
    
    # Setup test directories
    test_data_dir = tmp_path / "data"
    test_data_dir.mkdir()
    (test_data_dir / "inputdata").mkdir()
    (test_data_dir / "invoice").mkdir()
    (test_data_dir / "tasksupport").mkdir()
    (test_data_dir / "logs").mkdir()
    
    # Create required files
    invoice_content = {
        "basic": {
            "dataName": "Test Data",
            "experimentTitle": "Test Experiment"
        },
        "custom": {}
    }
    
    with open(test_data_dir / "invoice" / "invoice.json", "w") as f:
        json.dump(invoice_content, f)
    
    schema_content = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "basic": {"type": "object"},
            "custom": {"type": "object"}
        }
    }
    
    with open(test_data_dir / "tasksupport" / "invoice.schema.json", "w") as f:
        json.dump(schema_content, f)
    
    metadata_content = {
        "constant": {},
        "variable": []
    }
    
    with open(test_data_dir / "tasksupport" / "metadata-def.json", "w") as f:
        json.dump(metadata_content, f)
    
    # Create a test input file
    test_input_file = test_data_dir / "inputdata" / "test.txt"
    test_input_file.write_text("test data")
    
    # Change to test directory
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        # Define custom dataset function that raises StructuredError
        @catch_exception_with_message(error_message="Dataset processing failed", error_code=50)
        def custom_dataset_function(srcpaths, resource_paths):
            raise StructuredError("error message in dataset()", 21)
        
        # Run the workflow and expect it to exit with error
        with pytest.raises(SystemExit):
            run(custom_dataset_function=custom_dataset_function)
        
        # Check that job.failed was created with correct content
        job_failed_path = test_data_dir / "job.failed"
        assert job_failed_path.exists(), "job.failed file was not created"
        
        content = job_failed_path.read_text()
        
        # The StructuredError values should be used, not the decorator values
        assert "ErrorCode=21" in content, f"Expected ErrorCode=21 in job.failed, got: {content}"
        assert "ErrorMessage=Error: error message in dataset()" in content, f"Expected correct error message in job.failed, got: {content}"
        
        # Should NOT contain the decorator values
        assert "ErrorCode=50" not in content, "Should not contain decorator error code"
        assert "Dataset processing failed" not in content, "Should not contain decorator error message"
        
    finally:
        os.chdir(original_cwd)
