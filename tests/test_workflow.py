import json
import os
import shutil
from pathlib import Path
from typing import Optional

import pytest
import toml
import yaml

import rdetoolkit.rdelogger as rdelogger
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.workflows import run, _process_mode, _create_error_status
from rdetoolkit.models.config import Config, SystemSettings, MultiDataTileSettings
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
from rdetoolkit.models.result import WorkflowExecutionStatus

"""
| Equivalence Partitioning |
| API                 | Input/State Partition                              | Rationale                                  | Expected Outcome                                        | Test ID      |
| ------------------- | -------------------------------------------------- | ------------------------------------------ | ------------------------------------------------------- | ------------ |
| _process_mode       | smarttable file present                            | SmartTable branch has highest precedence   | SmartTableInvoice mode executes                         | TC-EP-001    |
| _process_mode       | excel invoice present, extended_mode also set      | Excelinvoice should precede extended_mode  | Excelinvoice mode executes                              | TC-EP-002    |
| _process_mode       | extended_mode="rdeformat"                          | Valid extended_mode value                  | rdeformat mode executes                                 | TC-EP-003    |
| _process_mode       | extended_mode=\"MultiDataTile\", ignore_errors=False | Multidata tile failure should bubble       | StructuredError is raised                               | TC-EP-004    |
| _process_mode       | downstream handler returns None                    | Guard against missing status               | StructuredError is raised                               | TC-EP-005    |
| _process_mode       | downstream handler returns status.failed           | Failures must raise StructuredError        | StructuredError with error_code propagates              | TC-EP-006    |
| _process_mode       | downstream handler raises generic Exception        | Unexpected errors are wrapped              | StructuredError is raised with wrapped message          | TC-EP-007    |

| Boundary Value |
| API           | Boundary Scenario                                        | Rationale                                        | Expected Outcome                         | Test ID      |
| ------------- | -------------------------------------------------------- | ------------------------------------------------ | ---------------------------------------- | ------------ |
| _process_mode | smarttable vs excel inputs present                       | Confirms first-branch priority boundary          | SmartTableInvoice chosen (not Excelinvoice) | TC-EP-001    |
| _process_mode | excel present while extended_mode also configured        | Confirms second/third priority boundary          | Excelinvoice chosen (not extended_mode)  | TC-EP-002    |
| _process_mode | extended_mode set to allowed value                    | Boundary between valid extended_mode and default | rdeformat branch executes                | TC-EP-003    |
| _process_mode | MultiDataTile ignore_errors=False                        | Boundary between handled/unhandled exceptions    | StructuredError raised                   | TC-EP-004    |
| _process_mode | handler returns None vs valid WorkflowExecutionStatus    | Boundary between valid/invalid status responses  | StructuredError raised on None           | TC-EP-005    |
| _process_mode | handler returns status.failed                            | Boundary between success and explicit failure    | StructuredError raised                   | TC-EP-006    |
"""


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


def test_workflow_creates_timestamped_log_file(tmp_path, monkeypatch):
    """Test that workflow.run() creates a log file with timestamp in name."""
    from unittest import mock
    from datetime import datetime

    # Mock StorageDir to use tmp_path
    def mock_get_outputdir(create, name):
        path = tmp_path / name
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    monkeypatch.setattr('rdetoolkit.rde2util.StorageDir.get_specific_outputdir', mock_get_outputdir)

    # Mock datetime.now() to return a fixed timestamp
    fixed_datetime = datetime(2026, 1, 6, 9, 28, 45)
    with mock.patch('rdetoolkit.rdelogger.datetime') as mock_datetime:
        mock_datetime.now.return_value = fixed_datetime

        # Setup minimal test environment
        (tmp_path / "inputdata").mkdir()
        (tmp_path / "invoice").mkdir()
        (tmp_path / "tasksupport").mkdir()
        (tmp_path / "logs").mkdir()

        # Create minimal config files
        config_file = tmp_path / "tasksupport" / "rdeconfig.yml"
        config_file.write_text("system:\n  extended_mode: null\n")

        schema_file = tmp_path / "tasksupport" / "invoice.schema.json"
        schema_file.write_text("{}")

        invoice_file = tmp_path / "invoice" / "invoice.json"
        invoice_file.write_text('{"basic": {}}')

        metadata_file = tmp_path / "tasksupport" / "metadata-def.json"
        metadata_file.write_text('{"constant": {}, "variable": []}')

        # Create a test input file
        test_input = tmp_path / "inputdata" / "test.txt"
        test_input.write_text("test data")

        # Execute workflow (may fail due to incomplete setup, but log file should be created)
        try:
            from rdetoolkit.workflows import run
            run()
        except (SystemExit, Exception):
            # Workflow may fail due to missing data, but log file should be created
            pass

        # Verify timestamped log file was created
        expected_log_filename = "rdesys_20260106_092845.log"
        log_file_path = tmp_path / "logs" / expected_log_filename

        assert log_file_path.exists(), f"Expected log file {expected_log_filename} was not created"


def test_workflow_timestamp_consistency_in_single_run(tmp_path, monkeypatch):
    """Test that a single workflow run uses the same timestamp throughout."""
    from unittest import mock

    # Mock StorageDir to use tmp_path
    def mock_get_outputdir(create, name):
        path = tmp_path / name
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    monkeypatch.setattr('rdetoolkit.rde2util.StorageDir.get_specific_outputdir', mock_get_outputdir)

    # Setup test environment
    (tmp_path / "inputdata").mkdir()
    (tmp_path / "invoice").mkdir()
    (tmp_path / "tasksupport").mkdir()
    (tmp_path / "logs").mkdir()

    # Create minimal config files
    config_file = tmp_path / "tasksupport" / "rdeconfig.yml"
    config_file.write_text("system:\n  extended_mode: null\n")

    schema_file = tmp_path / "tasksupport" / "invoice.schema.json"
    schema_file.write_text("{}")

    invoice_file = tmp_path / "invoice" / "invoice.json"
    invoice_file.write_text('{"basic": {}}')

    metadata_file = tmp_path / "tasksupport" / "metadata-def.json"
    metadata_file.write_text('{"constant": {}, "variable": []}')

    # Create a test input file
    test_input = tmp_path / "inputdata" / "test.txt"
    test_input.write_text("test data")

    original_generate = rdelogger.generate_log_timestamp

    with mock.patch('rdetoolkit.rdelogger.generate_log_timestamp', wraps=original_generate) as mock_generate:
        try:
            from rdetoolkit.workflows import run
            run()
        except (SystemExit, Exception):
            pass

    # Verify timestamp generation was called exactly once per run
    assert mock_generate.call_count == 1, f"Timestamp should be generated exactly once per workflow run, but was called {mock_generate.call_count} times"


def test_multiple_workflow_runs_create_different_log_files(tmp_path, monkeypatch):
    """Test that consecutive workflow runs create separate log files."""
    import time

    # Mock StorageDir to use tmp_path
    def mock_get_outputdir(create, name):
        path = tmp_path / name
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    monkeypatch.setattr('rdetoolkit.rde2util.StorageDir.get_specific_outputdir', mock_get_outputdir)

    # Setup test environment
    (tmp_path / "inputdata").mkdir()
    (tmp_path / "invoice").mkdir()
    (tmp_path / "tasksupport").mkdir()
    (tmp_path / "logs").mkdir()

    # Create minimal config files
    config_file = tmp_path / "tasksupport" / "rdeconfig.yml"
    config_file.write_text("system:\n  extended_mode: null\n")

    schema_file = tmp_path / "tasksupport" / "invoice.schema.json"
    schema_file.write_text("{}")

    invoice_file = tmp_path / "invoice" / "invoice.json"
    invoice_file.write_text('{"basic": {}}')

    metadata_file = tmp_path / "tasksupport" / "metadata-def.json"
    metadata_file.write_text('{"constant": {}, "variable": []}')

    # Create a test input file
    test_input = tmp_path / "inputdata" / "test.txt"
    test_input.write_text("test data")

    log_files_created = []

    # Run workflow twice with a time gap
    for i in range(2):
        try:
            from rdetoolkit.workflows import run
            run()
        except (SystemExit, Exception):
            pass

        # Collect log files created
        logs_dir = tmp_path / "logs"
        current_logs = list(logs_dir.glob("rdesys_*.log"))
        log_files_created.extend(current_logs)

        if i == 0:
            time.sleep(1.1)  # Ensure different timestamp for second run

    # Verify multiple log files were created
    unique_logs = set(log_files_created)
    assert len(unique_logs) >= 2, f"Multiple workflow runs should create different log files, but only {len(unique_logs)} unique file(s) found"

    # Verify all log files follow the naming pattern
    for log_file in unique_logs:
        assert log_file.name.startswith("rdesys_"), f"Log file {log_file.name} should start with 'rdesys_'"
        assert log_file.name.endswith(".log"), f"Log file {log_file.name} should end with '.log'"
        # Extract timestamp part: rdesys_YYYYMMDD_HHMMSS.log
        timestamp_part = log_file.stem.replace("rdesys_", "")
        assert len(timestamp_part) == 15, f"Timestamp part should be 15 chars: {timestamp_part}"
        assert timestamp_part[8] == "_", f"Timestamp should have underscore at position 8: {timestamp_part}"


def test_log_filename_pattern():
    """Test that generated log filename matches expected pattern."""
    import re
    timestamp = rdelogger.generate_log_timestamp()
    log_filename = f"rdesys_{timestamp}.log"

    # Pattern: rdesys_YYYYMMDD_HHMMSS.log
    pattern = r"^rdesys_\d{8}_\d{6}\.log$"
    assert re.match(pattern, log_filename), f"Log filename {log_filename} does not match expected pattern"

    # Verify no problematic characters for cross-platform compatibility
    assert ":" not in log_filename, "Log filename should not contain colons"
    assert "/" not in log_filename, "Log filename should not contain forward slashes"
    assert "\\" not in log_filename, "Log filename should not contain backslashes"


def test_multiple_workflow_runs_no_log_duplication(tmp_path, monkeypatch):
    """Test that multiple workflow runs don't write to previous log files."""
    from unittest import mock
    from datetime import datetime

    # Mock StorageDir to use tmp_path
    def mock_get_outputdir(create, name):
        path = tmp_path / name
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    monkeypatch.setattr('rdetoolkit.rde2util.StorageDir.get_specific_outputdir', mock_get_outputdir)

    # Setup test environment
    (tmp_path / "inputdata").mkdir()
    (tmp_path / "invoice").mkdir()
    (tmp_path / "tasksupport").mkdir()
    (tmp_path / "logs").mkdir()

    # Create minimal config files
    config_file = tmp_path / "tasksupport" / "rdeconfig.yml"
    config_file.write_text("system:\n  extended_mode: null\n")

    schema_file = tmp_path / "tasksupport" / "invoice.schema.json"
    schema_file.write_text("{}")

    invoice_file = tmp_path / "invoice" / "invoice.json"
    invoice_file.write_text('{"basic": {}}')

    metadata_file = tmp_path / "tasksupport" / "metadata-def.json"
    metadata_file.write_text('{"constant": {}, "variable": []}')

    # Create a test input file
    test_input = tmp_path / "inputdata" / "test.txt"
    test_input.write_text("test data")

    # Track created log files
    log_files = []

    # Run workflow twice with different mocked timestamps
    timestamps = [
        datetime(2026, 1, 6, 10, 0, 0),
        datetime(2026, 1, 6, 10, 1, 0),
    ]

    for i, timestamp in enumerate(timestamps):
        with mock.patch('rdetoolkit.rdelogger.datetime') as mock_datetime:
            mock_datetime.now.return_value = timestamp

            try:
                from rdetoolkit.workflows import run
                run()
            except (SystemExit, Exception):
                # Workflow may fail, but log file should be created
                pass

        # Record the log file for this run
        expected_filename = f"rdesys_{timestamp.strftime('%Y%m%d_%H%M%S')}.log"
        log_file = tmp_path / "logs" / expected_filename
        log_files.append(log_file)

    # Verify both log files were created
    assert log_files[0].exists(), "First log file should exist"
    assert log_files[1].exists(), "Second log file should exist"

    # Get file sizes
    size_log1 = log_files[0].stat().st_size
    size_log2 = log_files[1].stat().st_size

    # Both should have content (not zero)
    assert size_log1 > 0, "First log file should have content"
    assert size_log2 > 0, "Second log file should have content"

    # The key assertion: sizes should be similar (not doubled)
    # If handlers accumulated, log2 would have content from both runs
    # We allow some variance but they should be roughly equal
    ratio = max(size_log1, size_log2) / min(size_log1, size_log2)
    assert ratio < 1.5, (
        f"Log file sizes too different (ratio: {ratio:.2f}). "
        "This suggests handler accumulation - second run might be writing to both files. "
        f"Log1: {size_log1} bytes, Log2: {size_log2} bytes"
    )


def _make_paths(tmp_path: Path, extended_mode: Optional[str] = None, ignore_errors: bool = False) -> tuple[RdeInputDirPaths, RdeOutputResourcePath, Config]:
    """Helper to build minimal input/output structures for _process_mode tests."""
    input_dir = tmp_path / "inputdata"
    invoice_dir = tmp_path / "invoice"
    tasksupport_dir = tmp_path / "tasksupport"
    for directory in (input_dir, invoice_dir, tasksupport_dir):
        directory.mkdir(parents=True, exist_ok=True)

    raw_file = input_dir / "dummy.txt"
    raw_file.write_text("dummy", encoding="utf-8")

    config = Config(
        system=SystemSettings(extended_mode=extended_mode, save_raw=True, save_thumbnail_image=False, magic_variable=False),
        multidata_tile=MultiDataTileSettings(ignore_errors=ignore_errors),
    )

    srcpaths = RdeInputDirPaths(
        inputdata=input_dir,
        invoice=invoice_dir,
        tasksupport=tasksupport_dir,
        config=config,
    )

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

    return srcpaths, rdeoutput_resource, config


def _success_status(idx: int, mode: str = "Invoice") -> WorkflowExecutionStatus:
    return WorkflowExecutionStatus(
        run_id=str(idx),
        title="tile",
        status="success",
        mode=mode,
        error_code=None,
        error_message=None,
        target=None,
        stacktrace=None,
    )


def test_process_mode_prefers_smarttable_over_excel__tc_ep_001(tmp_path, monkeypatch):
    """Given both smarttable and excel inputs, when processing, then SmartTableInvoice is chosen."""
    srcpaths, rdeoutput_resource, config = _make_paths(tmp_path)

    smart_called = []
    excel_called = []

    def fake_smarttable(*args, **kwargs):
        smart_called.append(True)
        return _success_status(0, "SmartTableInvoice")

    def fake_excel(*args, **kwargs):
        excel_called.append(True)
        return _success_status(0, "Excelinvoice")

    monkeypatch.setattr("rdetoolkit.workflows.smarttable_invoice_mode_process", fake_smarttable)
    monkeypatch.setattr("rdetoolkit.workflows.excel_invoice_mode_process", fake_excel)

    # Given: both smarttable and excel inputs are available
    smarttable_file = tmp_path / "smarttable.csv"
    smarttable_file.write_text("dummy", encoding="utf-8")
    excel_bundle = tmp_path / "excel.zip"
    excel_bundle.write_text("zip", encoding="utf-8")

    # When: _process_mode is executed
    status, error_info, mode = _process_mode(
        idx=0,
        srcpaths=srcpaths,
        rdeoutput_resource=rdeoutput_resource,
        config=config,
        excel_invoice_files=excel_bundle,
        smarttable_file=smarttable_file,
        custom_dataset_function=None,
        logger=None,
    )

    # Then: SmartTableInvoice branch runs before Excelinvoice
    assert smart_called, "SmartTableInvoice should run when smarttable file is present"
    assert not excel_called, "Excelinvoice should be skipped when smarttable file is present"
    assert mode == "SmartTableInvoice"
    assert status.status == "success"
    assert error_info is None


def test_process_mode_prefers_excel_before_extended_mode__tc_ep_002(tmp_path, monkeypatch):
    """Given excel input and extended_mode set, when processing, then Excelinvoice is chosen before extended_mode."""
    srcpaths, rdeoutput_resource, config = _make_paths(tmp_path, extended_mode="rdeformat")

    excel_called = []
    monkeypatch.setattr("rdetoolkit.workflows.excel_invoice_mode_process", lambda *args, **kwargs: excel_called.append(True) or _success_status(0, "Excelinvoice"))
    monkeypatch.setattr("rdetoolkit.workflows.rdeformat_mode_process", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("should not be called")))

    # Given: excel invoice bundle exists and extended_mode also set
    excel_bundle = tmp_path / "excel.zip"
    excel_bundle.write_text("zip", encoding="utf-8")

    # When
    status, error_info, mode = _process_mode(
        idx=0,
        srcpaths=srcpaths,
        rdeoutput_resource=rdeoutput_resource,
        config=config,
        excel_invoice_files=excel_bundle,
        smarttable_file=None,
        custom_dataset_function=None,
        logger=None,
    )

    # Then
    assert excel_called, "Excelinvoice branch should run before extended_mode"
    assert mode == "Excelinvoice"
    assert status.status == "success"
    assert error_info is None


def test_process_mode_uses_extended_mode_value__tc_ep_003(tmp_path, monkeypatch):
    """Given extended_mode set to allowed value, when processing, then rdeformat branch executes."""
    srcpaths, rdeoutput_resource, config = _make_paths(tmp_path, extended_mode="rdeformat")

    called = []
    monkeypatch.setattr("rdetoolkit.workflows.rdeformat_mode_process", lambda *args, **kwargs: called.append(True) or _success_status(0, "rdeformat"))

    # Given: extended_mode specified
    # When
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

    # Then
    assert called, "rdeformat branch should execute when extended_mode equals rdeformat (case-insensitive)"
    assert mode == "rdeformat"
    assert status.status == "success"
    assert error_info is None


def test_process_mode_multidatatitle_propagates_structured_error__tc_ep_004(tmp_path, monkeypatch):
    """Given MultiDataTile without ignore_errors, when handler raises StructuredError, then it propagates."""
    srcpaths, rdeoutput_resource, config = _make_paths(tmp_path, extended_mode="MultiDataTile", ignore_errors=False)

    monkeypatch.setattr("rdetoolkit.workflows.multifile_mode_process", lambda *args, **kwargs: (_ for _ in ()).throw(StructuredError("boom", 900)))

    # Given: ignore_errors is False
    # When/Then: StructuredError propagates
    with pytest.raises(StructuredError) as excinfo:
        _process_mode(
            idx=0,
            srcpaths=srcpaths,
            rdeoutput_resource=rdeoutput_resource,
            config=config,
            excel_invoice_files=None,
            smarttable_file=None,
            custom_dataset_function=None,
            logger=None,
        )

    assert "boom" in str(excinfo.value)
    assert excinfo.value.ecode == 900


def test_process_mode_raises_when_status_none__tc_ep_005(tmp_path, monkeypatch):
    """Given downstream handler returns None, when processing, then StructuredError is raised."""
    srcpaths, rdeoutput_resource, config = _make_paths(tmp_path)
    monkeypatch.setattr("rdetoolkit.workflows.invoice_mode_process", lambda *args, **kwargs: None)

    # When/Then
    with pytest.raises(StructuredError) as excinfo:
        _process_mode(
            idx=1,
            srcpaths=srcpaths,
            rdeoutput_resource=rdeoutput_resource,
            config=config,
            excel_invoice_files=None,
            smarttable_file=None,
            custom_dataset_function=None,
            logger=None,
        )

    assert "did not return a workflow status" in str(excinfo.value)


def test_process_mode_raises_on_failed_status__tc_ep_006(tmp_path, monkeypatch):
    """Given handler returns failed status, when processing, then StructuredError is raised with code."""
    srcpaths, rdeoutput_resource, config = _make_paths(tmp_path)
    logger = type("Logger", (), {"error": lambda *_args, **_kwargs: None})()

    failed_status = WorkflowExecutionStatus(
        run_id="2",
        title="tile",
        status="failed",
        mode="Invoice",
        error_code=321,
        error_message="bad",
        target=None,
        stacktrace="trace",
    )
    monkeypatch.setattr("rdetoolkit.workflows.invoice_mode_process", lambda *args, **kwargs: failed_status)

    # When/Then
    with pytest.raises(StructuredError) as excinfo:
        _process_mode(
            idx=2,
            srcpaths=srcpaths,
            rdeoutput_resource=rdeoutput_resource,
            config=config,
            excel_invoice_files=None,
            smarttable_file=None,
            custom_dataset_function=None,
            logger=logger,
        )

    assert excinfo.value.ecode == 321
    assert "bad" in str(excinfo.value)


def test_process_mode_wraps_unexpected_exception__tc_ep_007(tmp_path, monkeypatch):
    """Given handler raises unexpected Exception, when processing, then StructuredError wraps it."""
    srcpaths, rdeoutput_resource, config = _make_paths(tmp_path)

    def boom(*_args, **_kwargs):
        raise RuntimeError("crash")

    monkeypatch.setattr("rdetoolkit.workflows.invoice_mode_process", boom)

    # When/Then
    with pytest.raises(StructuredError) as excinfo:
        _process_mode(
            idx=3,
            srcpaths=srcpaths,
            rdeoutput_resource=rdeoutput_resource,
            config=config,
            excel_invoice_files=None,
            smarttable_file=None,
            custom_dataset_function=None,
            logger=None,
        )

    assert "Unexpected error in Invoice mode" in str(excinfo.value)
    assert "crash" in str(excinfo.value)
