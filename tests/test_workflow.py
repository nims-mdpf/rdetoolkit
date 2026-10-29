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
from rdetoolkit.workflows import run
from rdetoolkit.models.config import Config, SystemSettings, MultiDataTileSettings

# Equivalence Partitioning Table
# | API           | Input/State Partition                              | Rationale                                  | Expected Outcome                             | Test ID   |
# | ------------- | -------------------------------------------------- | ------------------------------------------ | -------------------------------------------- | --------- |
#
# Boundary Value Table
# | API           | Boundary Scenario                                     | Rationale                                        | Expected Outcome                            | Test ID   |
# | ------------- | ----------------------------------------------------- | ------------------------------------------------ | ------------------------------------------- | --------- |


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


def test_structured_error_propagation_in_workflow(tmp_path, monkeypatch):
    """Test that an invalid invoice.schema.json is reported before the callback runs.

    UPDATED (Session J2 / merge-v1 I7, divergence D3, orchestrator-granted
    exception to the tests/-root freeze). The fixture below carries an
    ``invoice.schema.json`` that rdetoolkit rejects in BOTH versions -- it lacks
    the required ``properties.custom.label`` / ``.required`` / ``.properties``.
    The old expectation (``ErrorCode=21`` from the callback) pinned v1's stage
    ORDER, in which the schema was only validated after the dataset callback had
    already run and raised. The unified Runner validates the source invoice and
    its schema in ``pre_validate`` (contracts.md §I6-0), so the defect is now
    reported as catalog code 4001 and the callback is never invoked at all.

    This assertion is strictly stronger than the one it replaces: it pins the
    published error code AND the remediation message AND the fact that no user
    code ran, through an explicit call counter. The original intent of
    issue_203 -- "the decorator's values must not mask the real error" -- is
    preserved below and now also covers the decorator vs. validation case.
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
        # Given: a dataset callback that would raise, and a counter proving
        # whether it was reached at all
        calls = []

        @catch_exception_with_message(error_message="Dataset processing failed", error_code=50)
        def custom_dataset_function(srcpaths, resource_paths):
            calls.append(1)
            raise StructuredError("error message in dataset()", 21)

        # When: running the public v1 entry point on the invalid schema
        with pytest.raises(SystemExit) as exit_info:
            run(custom_dataset_function=custom_dataset_function)

        # Then: the process exits 1, exactly as v1 did
        assert exit_info.value.code == 1

        # And: job.failed carries the front-loaded validation contract
        job_failed_path = test_data_dir / "job.failed"
        assert job_failed_path.exists(), "job.failed file was not created"

        content = job_failed_path.read_text()
        # Equality, not containment: the decorator's 50 and the callback's 21
        # are both excluded by it, so a future change that let either of them
        # reach job.failed would surface here as a published-code change. The
        # two "not in content" assertions this replaces became vacuous once the
        # callback stopped running at all.
        assert content.splitlines()[0] == "ErrorCode=4001", f"Expected the first line to be ErrorCode=4001, got: {content}"
        assert "Validation Errors in invoice.schema.json" in content, f"Expected the schema validation message in job.failed, got: {content}"

        # And: validation happened BEFORE any user code ran
        assert calls == [], "pre_validate must reject the schema before the dataset callback runs"

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
