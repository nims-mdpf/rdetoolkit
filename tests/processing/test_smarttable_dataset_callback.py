"""Integration tests for SmartTable dataset callback with row data access."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.models.rde2types import RdeDatasetPaths, RdeInputDirPaths, RdeOutputResourcePath
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.processing.processors.datasets import DatasetRunner
from rdetoolkit.processing.processors.invoice import SmartTableInvoiceInitializer


class CallbackTestHelper:
    """Helper class to capture callback invocations."""

    def __init__(self) -> None:
        """Initialize the test helper."""
        self.called = False
        self.received_paths: RdeDatasetPaths | None = None
        self.row_data: dict[str, Any] | None = None

    def callback_new_signature(self, paths: RdeDatasetPaths) -> None:
        """Callback using new single-argument signature."""
        self.called = True
        self.received_paths = paths
        self.row_data = paths.smarttable_row_data

    def callback_legacy_signature(
        self, srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath,
    ) -> None:
        """Callback using legacy two-argument signature."""
        self.called = True
        self.received_paths = RdeDatasetPaths(srcpaths, resource_paths)
        self.row_data = self.received_paths.smarttable_row_data


@pytest.fixture
def smarttable_test_setup(tmp_path: Path) -> dict[str, Any]:
    """Create test environment for SmartTable workflow.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Dictionary containing test file paths and directories
    """
    # Create directory structure
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    temp_dir = tmp_path / "temp"
    tasksupport_dir = tmp_path / "tasksupport"

    for directory in [input_dir, output_dir, temp_dir, tasksupport_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    # Create SmartTable CSV with test data
    csv_content = """basic/dataName,sample/name,custom/temperature,custom/pressure
Experiment_001,Sample_A,25.5,101.3"""

    csv_file = temp_dir / "fsmarttable_test_0000.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    # Create invoice schema
    schema_path = output_dir / "invoice.schema.json"
    schema_content = """{
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["custom", "sample"],
    "properties": {
        "basic": {
            "type": "object",
            "label": {"ja": "基本情報", "en": "Basic Information"},
            "properties": {}
        },
        "custom": {
            "type": "object",
            "label": {"ja": "固有情報", "en": "Custom Information"},
            "required": [],
            "properties": {
                "temperature": {
                    "type": "number",
                    "label": {"ja": "温度", "en": "Temperature"}
                },
                "pressure": {
                    "type": "number",
                    "label": {"ja": "圧力", "en": "Pressure"}
                }
            }
        },
        "sample": {
            "type": "object",
            "label": {"ja": "試料情報", "en": "Sample Information"},
            "required": ["names", "sampleId"],
            "properties": {
                "names": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "sampleId": {
                    "type": "string"
                }
            }
        }
    }
}"""
    schema_path.write_text(schema_content, encoding="utf-8")

    # Create original invoice
    invoice_org_path = output_dir / "invoice_org" / "invoice.json"
    invoice_org_path.parent.mkdir(parents=True, exist_ok=True)
    invoice_org_content = """{
    "basic": {},
    "custom": {},
    "sample": {
        "names": [],
        "sampleId": ""
    }
}"""
    invoice_org_path.write_text(invoice_org_content, encoding="utf-8")

    # Create invoice directory
    invoice_dir = output_dir / "invoice"
    invoice_dir.mkdir(parents=True, exist_ok=True)

    # Create meta directory
    meta_dir = output_dir / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    return {
        "csv_file": csv_file,
        "input_dir": input_dir,
        "output_dir": output_dir,
        "tasksupport_dir": tasksupport_dir,
        "schema_path": schema_path,
        "invoice_org_path": invoice_org_path,
        "invoice_dir": invoice_dir,
        "meta_dir": meta_dir,
    }


def test_dataset_callback_receives_smarttable_row_data_new_signature(
    smarttable_test_setup: dict[str, Any],
) -> None:
    """Test that callback receives smarttable_row_data with new signature."""
    setup = smarttable_test_setup

    # Create context
    srcpaths = RdeInputDirPaths(
        inputdata=setup["input_dir"],
        invoice=setup["input_dir"] / "invoice",
        tasksupport=setup["tasksupport_dir"],
    )

    resource_paths = RdeOutputResourcePath(
        raw=setup["output_dir"] / "raw",
        nonshared_raw=setup["output_dir"] / "nonshared_raw",
        rawfiles=(setup["csv_file"],),
        struct=setup["output_dir"] / "struct",
        main_image=setup["output_dir"] / "main_image",
        other_image=setup["output_dir"] / "other_image",
        meta=setup["meta_dir"],
        thumbnail=setup["output_dir"] / "thumbnail",
        logs=setup["output_dir"] / "logs",
        invoice=setup["invoice_dir"],
        invoice_schema_json=setup["schema_path"],
        invoice_org=setup["invoice_org_path"],
        smarttable_rowfile=setup["csv_file"],
    )

    # Setup callback
    helper = CallbackTestHelper()

    context = ProcessingContext(
        index="0",
        srcpaths=srcpaths,
        resource_paths=resource_paths,
        datasets_function=helper.callback_new_signature,
        mode_name="SmartTableInvoice",
        smarttable_file=setup["input_dir"] / "smarttable_test.csv",
    )

    # Execute pipeline steps
    # 1. Initialize invoice (this should populate smarttable_row_data)
    invoice_processor = SmartTableInvoiceInitializer()
    invoice_processor.process(context)

    # Verify that row data was stored in context
    assert context.resource_paths.smarttable_row_data is not None

    # 2. Run dataset callback
    dataset_runner = DatasetRunner()
    dataset_runner.process(context)

    # Verify callback was called
    assert helper.called is True
    assert helper.received_paths is not None

    # Verify callback received row data
    assert helper.row_data is not None
    assert isinstance(helper.row_data, dict)

    # Verify data content
    assert "basic/dataName" in helper.row_data
    assert helper.row_data["basic/dataName"] == "Experiment_001"

    assert "sample/name" in helper.row_data
    assert helper.row_data["sample/name"] == "Sample_A"

    assert "custom/temperature" in helper.row_data
    assert helper.row_data["custom/temperature"] == "25.5"

    assert "custom/pressure" in helper.row_data
    assert helper.row_data["custom/pressure"] == "101.3"


def test_dataset_callback_receives_smarttable_row_data_legacy_signature(
    smarttable_test_setup: dict[str, Any],
) -> None:
    """Test that callback receives smarttable_row_data with legacy signature."""
    setup = smarttable_test_setup

    # Create context (same as above)
    srcpaths = RdeInputDirPaths(
        inputdata=setup["input_dir"],
        invoice=setup["input_dir"] / "invoice",
        tasksupport=setup["tasksupport_dir"],
    )

    resource_paths = RdeOutputResourcePath(
        raw=setup["output_dir"] / "raw",
        nonshared_raw=setup["output_dir"] / "nonshared_raw",
        rawfiles=(setup["csv_file"],),
        struct=setup["output_dir"] / "struct",
        main_image=setup["output_dir"] / "main_image",
        other_image=setup["output_dir"] / "other_image",
        meta=setup["meta_dir"],
        thumbnail=setup["output_dir"] / "thumbnail",
        logs=setup["output_dir"] / "logs",
        invoice=setup["invoice_dir"],
        invoice_schema_json=setup["schema_path"],
        invoice_org=setup["invoice_org_path"],
        smarttable_rowfile=setup["csv_file"],
    )

    # Setup callback with legacy signature
    helper = CallbackTestHelper()

    context = ProcessingContext(
        index="0",
        srcpaths=srcpaths,
        resource_paths=resource_paths,
        datasets_function=helper.callback_legacy_signature,
        mode_name="SmartTableInvoice",
        smarttable_file=setup["input_dir"] / "smarttable_test.csv",
    )

    # Execute pipeline steps
    invoice_processor = SmartTableInvoiceInitializer()
    invoice_processor.process(context)

    dataset_runner = DatasetRunner()
    dataset_runner.process(context)

    # Verify callback was called with legacy signature
    assert helper.called is True
    assert helper.row_data is not None
    assert helper.row_data["basic/dataName"] == "Experiment_001"


def test_callback_without_smarttable_mode(tmp_path: Path) -> None:
    """Test that smarttable_row_data is None when not in SmartTable mode."""
    # Create minimal context for non-SmartTable mode
    srcpaths = RdeInputDirPaths(
        inputdata=tmp_path / "input",
        invoice=tmp_path / "invoice",
        tasksupport=tmp_path / "tasksupport",
    )

    resource_paths = RdeOutputResourcePath(
        raw=tmp_path / "raw",
        nonshared_raw=tmp_path / "nonshared_raw",
        rawfiles=(),
        struct=tmp_path / "struct",
        main_image=tmp_path / "main_image",
        other_image=tmp_path / "other_image",
        meta=tmp_path / "meta",
        thumbnail=tmp_path / "thumbnail",
        logs=tmp_path / "logs",
        invoice=tmp_path / "invoice",
        invoice_schema_json=tmp_path / "schema.json",
        invoice_org=tmp_path / "invoice_org",
        smarttable_rowfile=None,  # Not SmartTable mode
        smarttable_row_data=None,
    )

    helper = CallbackTestHelper()

    context = ProcessingContext(
        index="0",
        srcpaths=srcpaths,
        resource_paths=resource_paths,
        datasets_function=helper.callback_new_signature,
        mode_name="Invoice",  # Standard mode, not SmartTable
    )

    # Run callback
    dataset_runner = DatasetRunner()
    dataset_runner.process(context)

    # Verify callback received None for row_data
    assert helper.called is True
    assert helper.row_data is None


def test_issue_207_expected_api_pattern(smarttable_test_setup: dict[str, Any]) -> None:
    """Verify that the Issue #207 expected API pattern works as documented.

    This test ensures that the improved API from Issue #207 works correctly,
    where users can directly access row data without manual CSV parsing.
    """
    setup = smarttable_test_setup

    # Create context
    srcpaths = RdeInputDirPaths(
        inputdata=setup["input_dir"],
        invoice=setup["input_dir"] / "invoice",
        tasksupport=setup["tasksupport_dir"],
    )

    resource_paths = RdeOutputResourcePath(
        raw=setup["output_dir"] / "raw",
        nonshared_raw=setup["output_dir"] / "nonshared_raw",
        rawfiles=(setup["csv_file"],),
        struct=setup["output_dir"] / "struct",
        main_image=setup["output_dir"] / "main_image",
        other_image=setup["output_dir"] / "other_image",
        meta=setup["meta_dir"],
        thumbnail=setup["output_dir"] / "thumbnail",
        logs=setup["output_dir"] / "logs",
        invoice=setup["invoice_dir"],
        invoice_schema_json=setup["schema_path"],
        invoice_org=setup["invoice_org_path"],
        smarttable_rowfile=setup["csv_file"],
    )

    # AFTER pattern (new improved API from Issue #207)
    def custom_dataset_after(paths: RdeDatasetPaths) -> None:
        """Example user callback demonstrating the improved API."""
        row_data = paths.smarttable_row_data  # dict[str, Any]
        if row_data:
            sample_name = row_data.get("sample/name")
            assert sample_name == "Sample_A"

            # Can also access other fields directly
            data_name = row_data.get("basic/dataName")
            assert data_name == "Experiment_001"

            temperature = row_data.get("custom/temperature")
            assert temperature == "25.5"

    context = ProcessingContext(
        index="0",
        srcpaths=srcpaths,
        resource_paths=resource_paths,
        datasets_function=custom_dataset_after,
        mode_name="SmartTableInvoice",
        smarttable_file=setup["input_dir"] / "smarttable_test.csv",
    )

    # Execute pipeline steps
    invoice_processor = SmartTableInvoiceInitializer()
    invoice_processor.process(context)

    dataset_runner = DatasetRunner()
    dataset_runner.process(context)

    # If no assertion errors were raised, the test passes


def test_smarttable_row_data_empty_csv(tmp_path: Path) -> None:
    """Test behavior when SmartTable CSV has no data rows."""
    # Setup similar to smarttable_test_setup but with empty CSV
    output_dir = tmp_path / "output"
    temp_dir = tmp_path / "temp"
    tasksupport_dir = tmp_path / "tasksupport"

    for directory in [output_dir, temp_dir, tasksupport_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    # Create empty CSV (header only)
    csv_content = """basic/dataName,sample/name,custom/temperature,custom/pressure"""
    csv_file = temp_dir / "fsmarttable_test_0000.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    # Create schema and invoice
    schema_path = output_dir / "invoice.schema.json"
    schema_path.write_text('{"type": "object", "properties": {}}', encoding="utf-8")

    invoice_org_path = output_dir / "invoice_org" / "invoice.json"
    invoice_org_path.parent.mkdir(parents=True, exist_ok=True)
    invoice_org_path.write_text("{}", encoding="utf-8")

    invoice_dir = output_dir / "invoice"
    invoice_dir.mkdir(parents=True, exist_ok=True)

    meta_dir = output_dir / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    # Create context
    srcpaths = RdeInputDirPaths(
        inputdata=tmp_path / "input",
        invoice=tmp_path / "input" / "invoice",
        tasksupport=tasksupport_dir,
    )

    resource_paths = RdeOutputResourcePath(
        raw=output_dir / "raw",
        nonshared_raw=output_dir / "nonshared_raw",
        rawfiles=(csv_file,),
        struct=output_dir / "struct",
        main_image=output_dir / "main_image",
        other_image=output_dir / "other_image",
        meta=meta_dir,
        thumbnail=output_dir / "thumbnail",
        logs=output_dir / "logs",
        invoice=invoice_dir,
        invoice_schema_json=schema_path,
        invoice_org=invoice_org_path,
        smarttable_rowfile=csv_file,
    )

    helper = CallbackTestHelper()

    context = ProcessingContext(
        index="0",
        srcpaths=srcpaths,
        resource_paths=resource_paths,
        datasets_function=helper.callback_new_signature,
        mode_name="SmartTableInvoice",
        smarttable_file=tmp_path / "input" / "smarttable_test.csv",
    )

    # Execute pipeline steps
    invoice_processor = SmartTableInvoiceInitializer()
    invoice_processor.process(context)

    # Row data should be None for empty CSV
    assert context.resource_paths.smarttable_row_data is None

    dataset_runner = DatasetRunner()
    dataset_runner.process(context)

    # Callback should receive None
    assert helper.called is True
    assert helper.row_data is None
