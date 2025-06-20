"""Test SmartTableInvoiceInitializer with new specification."""

import json
from pathlib import Path
import pytest
import pandas as pd
from unittest.mock import Mock, patch

from rdetoolkit.processing.processors.invoice import SmartTableInvoiceInitializer
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.exceptions import StructuredError


class TestSmartTableInvoiceInitializerNew:
    """Test suite for SmartTableInvoiceInitializer with new specification."""

    def test_process_general_attributes(self, tmp_path):
        """Test processing sample/generalAttributes.<termId> mapping."""
        # Create test CSV file
        csv_file = tmp_path / "fsmarttable_test_0000.csv"
        csv_content = """basic/dataName,sample/generalAttributes.3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e
TestSample,TestValue"""
        csv_file.write_text(csv_content)

        # Create mock context
        context = self._create_mock_context(csv_file, tmp_path)
        
        # Create original invoice with existing generalAttributes
        original_invoice = {
            "basic": {},
            "custom": {},
            "sample": {
                "generalAttributes": [
                    {
                        "termId": "3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e",
                        "value": None
                    },
                    {
                        "termId": "other-term-id",
                        "value": "existing_value"
                    }
                ]
            }
        }
        context.resource_paths.invoice_org.write_text(json.dumps(original_invoice))

        # Run processor
        processor = SmartTableInvoiceInitializer()
        processor.process(context)

        # Check result
        result_file = context.invoice_dst_filepath
        assert result_file.exists()
        
        with open(result_file) as f:
            result = json.load(f)
        
        # Verify generalAttributes was updated
        assert result["basic"]["dataName"] == "TestSample"
        assert len(result["sample"]["generalAttributes"]) == 2
        
        # Check that the specific termId was updated
        updated_attr = next(
            attr for attr in result["sample"]["generalAttributes"]
            if attr["termId"] == "3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e"
        )
        assert updated_attr["value"] == "TestValue"
        
        # Check that other attributes remained unchanged
        other_attr = next(
            attr for attr in result["sample"]["generalAttributes"]
            if attr["termId"] == "other-term-id"
        )
        assert other_attr["value"] == "existing_value"

    def test_process_specific_attributes(self, tmp_path):
        """Test processing sample/specificAttributes.<classId>.<termId> mapping."""
        # Create test CSV file
        csv_file = tmp_path / "fsmarttable_test_0000.csv"
        csv_content = """basic/dataName,sample/specificAttributes.01cb3c01-37a4-5a43-d8ca-f523ca99a75b.3250c45d-0ed6-1438-43b5-eb679918604a
TestSample,SpecificValue"""
        csv_file.write_text(csv_content)

        # Create mock context
        context = self._create_mock_context(csv_file, tmp_path)
        
        # Create original invoice with existing specificAttributes
        original_invoice = {
            "basic": {},
            "custom": {},
            "sample": {
                "specificAttributes": [
                    {
                        "classId": "01cb3c01-37a4-5a43-d8ca-f523ca99a75b",
                        "termId": "3250c45d-0ed6-1438-43b5-eb679918604a",
                        "value": None
                    }
                ]
            }
        }
        context.resource_paths.invoice_org.write_text(json.dumps(original_invoice))

        # Run processor
        processor = SmartTableInvoiceInitializer()
        processor.process(context)

        # Check result
        result_file = context.invoice_dst_filepath
        assert result_file.exists()
        
        with open(result_file) as f:
            result = json.load(f)
        
        # Verify specificAttributes was updated
        assert result["basic"]["dataName"] == "TestSample"
        assert len(result["sample"]["specificAttributes"]) == 1
        
        # Check that the specific attribute was updated
        updated_attr = result["sample"]["specificAttributes"][0]
        assert updated_attr["classId"] == "01cb3c01-37a4-5a43-d8ca-f523ca99a75b"
        assert updated_attr["termId"] == "3250c45d-0ed6-1438-43b5-eb679918604a"
        assert updated_attr["value"] == "SpecificValue"

    def test_process_meta_prefix_ignored(self, tmp_path):
        """Test that meta/ prefix is ignored as per specification."""
        # Create test CSV file
        csv_file = tmp_path / "fsmarttable_test_0000.csv"
        csv_content = """basic/dataName,meta/someField
TestSample,MetaValue"""
        csv_file.write_text(csv_content)

        # Create mock context
        context = self._create_mock_context(csv_file, tmp_path)
        
        # Create original invoice
        original_invoice = {"basic": {}, "custom": {}, "sample": {}}
        context.resource_paths.invoice_org.write_text(json.dumps(original_invoice))

        # Run processor
        processor = SmartTableInvoiceInitializer()
        processor.process(context)

        # Check result
        result_file = context.invoice_dst_filepath
        assert result_file.exists()
        
        with open(result_file) as f:
            result = json.load(f)
        
        # Verify meta field was ignored
        assert result["basic"]["dataName"] == "TestSample"
        assert "someField" not in result.get("meta", {})
        assert "meta" not in result or not result["meta"]

    def test_process_inputdata_columns_ignored(self, tmp_path):
        """Test that inputdata columns are ignored in invoice generation."""
        # Create test CSV file
        csv_file = tmp_path / "fsmarttable_test_0000.csv"
        csv_content = """basic/dataName,inputdata1,inputdata2
TestSample,file1.txt,file2.txt"""
        csv_file.write_text(csv_content)

        # Create mock context
        context = self._create_mock_context(csv_file, tmp_path)
        
        # Create original invoice
        original_invoice = {"basic": {}, "custom": {}, "sample": {}}
        context.resource_paths.invoice_org.write_text(json.dumps(original_invoice))

        # Run processor
        processor = SmartTableInvoiceInitializer()
        processor.process(context)

        # Check result
        result_file = context.invoice_dst_filepath
        assert result_file.exists()
        
        with open(result_file) as f:
            result = json.load(f)
        
        # Verify inputdata fields were ignored
        assert result["basic"]["dataName"] == "TestSample"
        assert "inputdata1" not in result["basic"]
        assert "inputdata2" not in result["basic"]

    def test_inherit_original_invoice_values(self, tmp_path):
        """Test that original invoice values are inherited when not overridden."""
        # Create test CSV file with only one field
        csv_file = tmp_path / "fsmarttable_test_0000.csv"
        csv_content = """basic/dataName
NewSampleName"""
        csv_file.write_text(csv_content)

        # Create mock context
        context = self._create_mock_context(csv_file, tmp_path)
        
        # Create original invoice with existing values
        original_invoice = {
            "datasetId": "original-dataset-id",
            "basic": {
                "dataName": "original-name",
                "description": "original-description",
                "dataOwnerId": "original-owner"
            },
            "custom": {
                "temperature": "25",
                "pressure": "1.0"
            },
            "sample": {
                "sampleId": "original-sample-id",
                "names": ["original-sample-name"]
            }
        }
        context.resource_paths.invoice_org.write_text(json.dumps(original_invoice))

        # Run processor
        processor = SmartTableInvoiceInitializer()
        processor.process(context)

        # Check result
        result_file = context.invoice_dst_filepath
        assert result_file.exists()
        
        with open(result_file) as f:
            result = json.load(f)
        
        # Verify overridden field
        assert result["basic"]["dataName"] == "NewSampleName"
        
        # Verify inherited fields
        assert result["datasetId"] == "original-dataset-id"
        assert result["basic"]["description"] == "original-description"
        assert result["basic"]["dataOwnerId"] == "original-owner"
        assert result["custom"]["temperature"] == "25"
        assert result["custom"]["pressure"] == "1.0"
        assert result["sample"]["sampleId"] == "original-sample-id"
        assert result["sample"]["names"] == ["original-sample-name"]

    def test_process_sample_names_as_array(self, tmp_path):
        """Test that sample/names field is processed as array."""
        # Create test CSV file
        csv_file = tmp_path / "fsmarttable_test_0000.csv"
        csv_content = """sample/names
NewSampleName"""
        csv_file.write_text(csv_content)

        # Create mock context
        context = self._create_mock_context(csv_file, tmp_path)
        
        # Create original invoice
        original_invoice = {"basic": {}, "custom": {}, "sample": {}}
        context.resource_paths.invoice_org.write_text(json.dumps(original_invoice))

        # Run processor
        processor = SmartTableInvoiceInitializer()
        processor.process(context)

        # Check result
        result_file = context.invoice_dst_filepath
        assert result_file.exists()
        
        with open(result_file) as f:
            result = json.load(f)
        
        # Verify names field is an array
        assert result["sample"]["names"] == ["NewSampleName"]
        assert isinstance(result["sample"]["names"], list)

    def test_no_original_invoice_file(self, tmp_path):
        """Test processing when no original invoice file exists."""
        # Create test CSV file
        csv_file = tmp_path / "fsmarttable_test_0000.csv"
        csv_content = """basic/dataName,custom/temperature
TestSample,25"""
        csv_file.write_text(csv_content)

        # Create mock context without original invoice file
        context = self._create_mock_context(csv_file, tmp_path)
        
        # Don't create original invoice file

        # Run processor
        processor = SmartTableInvoiceInitializer()
        processor.process(context)

        # Check result
        result_file = context.invoice_dst_filepath
        assert result_file.exists()
        
        with open(result_file) as f:
            result = json.load(f)
        
        # Verify only specified fields are present
        assert result["basic"]["dataName"] == "TestSample"
        assert result["custom"]["temperature"] == "25"
        assert "datasetId" not in result

    def _create_mock_context(self, csv_file: Path, tmp_path: Path) -> Mock:
        """Create a mock processing context for testing."""
        context = Mock(spec=ProcessingContext)
        context.is_smarttable_mode = True
        context.mode_name = "SmartTableInvoice"
        
        # Mock resource paths
        context.resource_paths = Mock()
        context.resource_paths.rawfiles = (csv_file,)
        context.resource_paths.invoice_org = tmp_path / "invoice_org.json"
        context.invoice_dst_filepath = tmp_path / "invoice.json"
        
        # Ensure directories exist
        context.invoice_dst_filepath.parent.mkdir(parents=True, exist_ok=True)
        
        return context

    def test_error_handling_no_csv_file(self, tmp_path):
        """Test error handling when no CSV file is provided."""
        context = Mock(spec=ProcessingContext)
        context.is_smarttable_mode = True
        context.mode_name = "SmartTableInvoice"
        context.resource_paths = Mock()
        context.resource_paths.rawfiles = ()  # No files

        processor = SmartTableInvoiceInitializer()
        
        with pytest.raises(StructuredError) as exc_info:
            processor.process(context)
        
        assert "No CSV file found in rawfiles" in str(exc_info.value)

    def test_error_handling_not_smarttable_mode(self, tmp_path):
        """Test error handling when not in SmartTable mode."""
        context = Mock(spec=ProcessingContext)
        context.is_smarttable_mode = False
        context.mode_name = "SomeOtherMode"

        processor = SmartTableInvoiceInitializer()
        
        with pytest.raises(ValueError) as exc_info:
            processor.process(context)
        
        assert "SmartTable file not provided in processing context" in str(exc_info.value)