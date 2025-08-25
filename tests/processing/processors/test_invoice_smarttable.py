import json
from pathlib import Path

import pandas as pd
import pytest

from unittest.mock import patch

from rdetoolkit.exceptions import StructuredError, SkipRemainingProcessorsError
from rdetoolkit.processing.processors.invoice import SmartTableInvoiceInitializer
from rdetoolkit.processing.processors.smarttable_early_exit import SmartTableEarlyExitProcessor


class TestSmartTableInvoiceInitializerIntegration:
    """Integration test cases for SmartTableInvoiceInitializer processor."""

    def test_process_new_invoice_from_csv(self, smarttable_processing_context):
        """Test creating a new invoice from CSV when no original invoice exists."""
        processor = SmartTableInvoiceInitializer()
        context = smarttable_processing_context

        # Create actual CSV file with test data
        csv_data = pd.DataFrame({
            'basic/dataName': ['Test Data'],
            'basic/description': ['Test Description'],
            'custom/customField1': ['customValue1'],
            'sample/names': ['Sample Name'],
            'sample/generalAttributes.term1': ['value1'],
            'sample/specificAttributes.class1.term2': ['value2'],
            'meta/ignored': ['should be ignored'],
            'inputdata1': ['also ignored']
        })

        # Write CSV to actual file
        csv_path = context.resource_paths.rawfiles[0]
        csv_data.to_csv(csv_path, index=False)

        # Process
        processor.process(context)

        # Read and verify the generated invoice
        invoice_path = context.invoice_dst_filepath
        assert invoice_path.exists()

        with open(invoice_path, 'r') as f:
            invoice_data = json.load(f)

        # Check basic fields
        assert invoice_data['basic']['dataName'] == 'Test Data'
        assert invoice_data['basic']['description'] == 'Test Description'

        # Check custom fields
        assert invoice_data['custom']['customField1'] == 'customValue1'

        # Check sample fields
        assert invoice_data['sample']['names'] == ['Sample Name']

        # Check generalAttributes
        assert 'generalAttributes' in invoice_data['sample']
        assert any(
            attr['termId'] == 'term1' and attr['value'] == 'value1'
            for attr in invoice_data['sample']['generalAttributes']
        )

        # Check specificAttributes
        assert 'specificAttributes' in invoice_data['sample']
        assert any(
            attr['classId'] == 'class1' and attr['termId'] == 'term2' and attr['value'] == 'value2'
            for attr in invoice_data['sample']['specificAttributes']
        )

    def test_process_update_existing_invoice(self, smarttable_processing_context):
        """Test updating an existing invoice with CSV data."""
        processor = SmartTableInvoiceInitializer()
        context = smarttable_processing_context

        # Create existing invoice file
        existing_invoice = {
            "basic": {
                "dataName": "Original Name",
                "description": "Original Description"
            },
            "custom": {
                "existingField": "preserved_value"
            },
            "sample": {
                "generalAttributes": [
                    {"termId": "term1", "value": "old_value1"},
                    {"termId": "term2", "value": "preserved_value2"}
                ]
            }
        }

        with open(context.resource_paths.invoice_org, 'w') as f:
            json.dump(existing_invoice, f)

        # Create CSV with updates
        csv_data = pd.DataFrame({
            'basic/dataName': ['Updated Name'],
            'sample/generalAttributes.term1': ['updated_value1'],
            'sample/generalAttributes.term3': ['new_value3']
        })

        csv_path = context.resource_paths.rawfiles[0]
        csv_data.to_csv(csv_path, index=False)

        # Process
        processor.process(context)

        # Read and verify the updated invoice
        invoice_path = context.invoice_dst_filepath
        with open(invoice_path, 'r') as f:
            invoice_data = json.load(f)

        # Check updated fields
        assert invoice_data['basic']['dataName'] == 'Updated Name'
        assert invoice_data['basic']['description'] == 'Original Description'  # Preserved

        # Check preserved custom fields
        assert invoice_data['custom']['existingField'] == 'preserved_value'

        # Check generalAttributes updates
        attrs = invoice_data['sample']['generalAttributes']
        term1_attr = next((a for a in attrs if a['termId'] == 'term1'), None)
        term2_attr = next((a for a in attrs if a['termId'] == 'term2'), None)
        term3_attr = next((a for a in attrs if a['termId'] == 'term3'), None)

        assert term1_attr['value'] == 'updated_value1'  # Updated
        assert term2_attr['value'] == 'preserved_value2'  # Preserved
        assert term3_attr['value'] == 'new_value3'  # New

    def test_process_with_empty_and_nan_values(self, smarttable_processing_context):
        """Test processing CSV with empty strings and NaN values."""
        processor = SmartTableInvoiceInitializer()
        context = smarttable_processing_context

        # Create CSV with empty and NaN values
        csv_data = pd.DataFrame({
            'basic/dataName': ['Valid Name'],
            'basic/empty': [''],  # Empty string - should be skipped
            'basic/nan': [pd.NA],  # NaN - should be skipped
            'custom/field1': ['value1']
        })

        csv_path = context.resource_paths.rawfiles[0]
        csv_data.to_csv(csv_path, index=False)

        # Process
        processor.process(context)

        # Read and verify
        invoice_path = context.invoice_dst_filepath
        with open(invoice_path, 'r') as f:
            invoice_data = json.load(f)

        # Check that only non-empty values were written
        assert invoice_data['basic']['dataName'] == 'Valid Name'
        assert 'empty' not in invoice_data['basic']
        assert 'nan' not in invoice_data['basic']
        assert invoice_data['custom']['field1'] == 'value1'

    def test_process_type_conversion_with_schema(self, smarttable_processing_context):
        """Test type conversion for custom fields using schema."""
        processor = SmartTableInvoiceInitializer()
        context = smarttable_processing_context

        # Create CSV with values needing type conversion
        csv_data = pd.DataFrame({
            'custom/sample1': ['2023-01-01 00:00:00'],
            'custom/sample2': ['3.14'],
            'custom/sample3': ['1'],
        })

        csv_path = context.resource_paths.rawfiles[0]
        csv_data.to_csv(csv_path, index=False)

        processor.process(context)

        # Read and verify type conversions
        invoice_path = context.invoice_dst_filepath
        with open(invoice_path, 'r') as f:
            invoice_data = json.load(f)

        assert invoice_data['custom']['sample1'] == "2023-01-01"
        assert invoice_data['custom']['sample2'] == 3.14
        assert invoice_data['custom']['sample3'] == 1

    def test_process_no_rawfiles(self, smarttable_processing_context):
        """Test process raises StructuredError when no raw files exist."""
        processor = SmartTableInvoiceInitializer()
        context = smarttable_processing_context

        # Remove rawfiles
        context.resource_paths.rawfiles = ()

        with pytest.raises(StructuredError, match="No CSV file found in rawfiles"):
            processor.process(context)

    def test_process_csv_read_error(self, smarttable_processing_context):
        """Test process handles CSV read errors properly."""
        processor = SmartTableInvoiceInitializer()
        context = smarttable_processing_context

        # Create an invalid CSV file
        csv_path = context.resource_paths.rawfiles[0]
        csv_path.write_text("This is not valid CSV content\x00\x01\x02")

        with pytest.raises(StructuredError) as exc_info:
            processor.process(context)

        assert "Failed to initialize invoice from SmartTable" in str(exc_info.value)

    def test_process_complex_specific_attributes(self, smarttable_processing_context):
        """Test processing multiple specificAttributes with same classId."""
        processor = SmartTableInvoiceInitializer()
        context = smarttable_processing_context

        # Create CSV with multiple specific attributes
        csv_data = pd.DataFrame({
            'sample/specificAttributes.class1.term1': ['value1'],
            'sample/specificAttributes.class1.term2': ['value2'],
            'sample/specificAttributes.class2.term1': ['value3']
        })

        csv_path = context.resource_paths.rawfiles[0]
        csv_data.to_csv(csv_path, index=False)

        # Process
        processor.process(context)

        # Read and verify specific attributes structure
        invoice_path = context.invoice_dst_filepath
        with open(invoice_path, 'r') as f:
            invoice_data = json.load(f)

        spec_attrs = invoice_data['sample']['specificAttributes']

        # Should have 3 entries
        assert len(spec_attrs) == 3

        # Check each attribute
        assert any(a['classId'] == 'class1' and a['termId'] == 'term1' and a['value'] == 'value1' for a in spec_attrs)
        assert any(a['classId'] == 'class1' and a['termId'] == 'term2' and a['value'] == 'value2' for a in spec_attrs)
        assert any(a['classId'] == 'class2' and a['termId'] == 'term1' and a['value'] == 'value3' for a in spec_attrs)

    def test_process_general_attributes_update(self, smarttable_processing_context):
        """Test updating and adding generalAttributes."""
        processor = SmartTableInvoiceInitializer()
        context = smarttable_processing_context

        # Create CSV with general attributes
        csv_data = pd.DataFrame({
            'sample/generalAttributes.color': ['red'],
            'sample/generalAttributes.size': ['large'],
            'sample/generalAttributes.weight': ['100kg']
        })

        csv_path = context.resource_paths.rawfiles[0]
        csv_data.to_csv(csv_path, index=False)

        # Process
        processor.process(context)

        # Read and verify
        invoice_path = context.invoice_dst_filepath
        with open(invoice_path, 'r') as f:
            invoice_data = json.load(f)

        gen_attrs = invoice_data['sample']['generalAttributes']

        # Should have 3 entries
        assert len(gen_attrs) == 3

        # Check each attribute
        assert any(a['termId'] == 'color' and a['value'] == 'red' for a in gen_attrs)
        assert any(a['termId'] == 'size' and a['value'] == 'large' for a in gen_attrs)
        assert any(a['termId'] == 'weight' and a['value'] == '100kg' for a in gen_attrs)

    def test_process_names_field_as_array(self, smarttable_processing_context):
        """Test that sample/names field is correctly converted to array."""
        processor = SmartTableInvoiceInitializer()
        context = smarttable_processing_context

        # Create CSV with names field
        csv_data = pd.DataFrame({
            'sample/names': ['Test Sample Name'],
            'sample/otherField': ['Not an array']
        })

        csv_path = context.resource_paths.rawfiles[0]
        csv_data.to_csv(csv_path, index=False)

        # Process
        processor.process(context)

        # Read and verify
        invoice_path = context.invoice_dst_filepath
        with open(invoice_path, 'r') as f:
            invoice_data = json.load(f)

        # names should be an array
        assert isinstance(invoice_data['sample']['names'], list)
        assert invoice_data['sample']['names'] == ['Test Sample Name']

        # otherField should be a string
        assert isinstance(invoice_data['sample']['otherField'], str)
        assert invoice_data['sample']['otherField'] == 'Not an array'

    def test_process_not_smarttable_mode(self, basic_processing_context):
        """Test process raises ValueError when not in SmartTable mode."""
        processor = SmartTableInvoiceInitializer()
        context = basic_processing_context

        # Ensure context is not in SmartTable mode
        assert not context.is_smarttable_mode

        with pytest.raises(ValueError, match="SmartTable file not provided in processing context"):
            processor.process(context)

    def test_get_name(self):
        """Test processor name."""
        processor = SmartTableInvoiceInitializer()
        assert processor.get_name() == "SmartTableInvoiceInitializer"


class TestSmartTableEarlyExitProcessorIntegration:
    """Integration test cases for SmartTableEarlyExitProcessor focusing on invoice dataName updates."""

    @patch('rdetoolkit.processing.processors.smarttable_early_exit.MetadataValidator')
    @patch('rdetoolkit.processing.processors.smarttable_early_exit.InvoiceValidator')
    def test_update_invoice_dataname_with_xlsx_file(self, mock_invoice_validator, mock_meta_validator, smarttable_processing_context):
        """Test updating invoice.json dataName with XLSX SmartTable file name."""
        processor = SmartTableEarlyExitProcessor()
        context = smarttable_processing_context

        # Create an actual invoice.json file with initial data
        initial_invoice_data = {
            "datasetId": "test-dataset-id",
            "basic": {
                "dateSubmitted": "",
                "dataOwnerId": "test-owner-id",
                "dataName": "original_data_name",
                "instrumentId": None,
                "experimentId": None,
                "description": "Original test description"
            },
            "custom": {
                "field1": "value1",
                "field2": 123
            },
            "sample": {
                "sampleId": "",
                "names": ["test sample"],
                "generalAttributes": []
            }
        }

        # Write initial invoice.json
        invoice_path = context.invoice_dst_filepath
        with open(invoice_path, 'w', encoding='utf-8') as f:
            json.dump(initial_invoice_data, f, ensure_ascii=False, indent=2)

        # Set up SmartTable file path with XLSX extension
        smarttable_file = Path("/data/inputdata/smarttable_experiment_data.xlsx")
        context.resource_paths.rawfiles = (smarttable_file,)

        # Enable save_table_file
        if context.srcpaths.config.smarttable is None:
            from unittest.mock import Mock
            context.srcpaths.config.smarttable = Mock()
        context.srcpaths.config.smarttable.save_table_file = True

        # Disable actual file copying to avoid filesystem issues
        context.srcpaths.config.system.save_raw = False
        context.srcpaths.config.system.save_nonshared_raw = False

        # Mock validators to skip validation
        mock_meta_validator.return_value.process.return_value = None
        mock_invoice_validator.return_value.process.return_value = None

        # Process (should raise SkipRemainingProcessorsError after updating invoice)
        with pytest.raises(SkipRemainingProcessorsError):
            processor.process(context)

        # Read updated invoice.json
        with open(invoice_path, 'r', encoding='utf-8') as f:
            updated_invoice = json.load(f)

        # Verify dataName was updated to file name
        assert updated_invoice['basic']['dataName'] == 'smarttable_experiment_data.xlsx'

        # Verify other fields remain unchanged
        assert updated_invoice['basic']['dateSubmitted'] == ""
        assert updated_invoice['basic']['dataOwnerId'] == "test-owner-id"
        assert updated_invoice['basic']['description'] == "Original test description"
        assert updated_invoice['custom']['field1'] == "value1"
        assert updated_invoice['custom']['field2'] == 123
        assert updated_invoice['sample']['names'] == ["test sample"]

    @patch('rdetoolkit.processing.processors.smarttable_early_exit.MetadataValidator')
    @patch('rdetoolkit.processing.processors.smarttable_early_exit.InvoiceValidator')
    def test_update_invoice_dataname_with_csv_file(self, mock_invoice_validator, mock_meta_validator, smarttable_processing_context):
        """Test updating invoice.json dataName with CSV SmartTable file name."""
        processor = SmartTableEarlyExitProcessor()
        context = smarttable_processing_context

        # Create initial invoice.json
        initial_invoice_data = {
            "basic": {
                "dataName": "old_name",
                "description": "Test description"
            },
            "custom": {},
            "sample": {}
        }

        invoice_path = context.invoice_dst_filepath
        with open(invoice_path, 'w', encoding='utf-8') as f:
            json.dump(initial_invoice_data, f, ensure_ascii=False, indent=2)

        # Set up CSV SmartTable file
        smarttable_file = Path("/data/inputdata/smarttable_results.csv")
        context.resource_paths.rawfiles = (smarttable_file,)
        if context.srcpaths.config.smarttable is None:
            from unittest.mock import Mock
            context.srcpaths.config.smarttable = Mock()
        context.srcpaths.config.smarttable.save_table_file = True
        context.srcpaths.config.system.save_raw = False
        context.srcpaths.config.system.save_nonshared_raw = False

        # Mock validators to skip validation
        mock_meta_validator.return_value.process.return_value = None
        mock_invoice_validator.return_value.process.return_value = None

        # Process
        with pytest.raises(SkipRemainingProcessorsError):
            processor.process(context)

        # Verify dataName was updated
        with open(invoice_path, 'r', encoding='utf-8') as f:
            updated_invoice = json.load(f)

        assert updated_invoice['basic']['dataName'] == 'smarttable_results.csv'
        assert updated_invoice['basic']['description'] == "Test description"

    @patch('rdetoolkit.processing.processors.smarttable_early_exit.MetadataValidator')
    @patch('rdetoolkit.processing.processors.smarttable_early_exit.InvoiceValidator')
    def test_update_invoice_dataname_with_tsv_file(self, mock_invoice_validator, mock_meta_validator, smarttable_processing_context):
        """Test updating invoice.json dataName with TSV SmartTable file name."""
        processor = SmartTableEarlyExitProcessor()
        context = smarttable_processing_context

        # Create initial invoice.json
        initial_invoice_data = {
            "basic": {
                "dataName": "initial_name",
                "description": None
            },
            "custom": {"existing": "value"},
            "sample": {"names": ["sample"]}
        }

        invoice_path = context.invoice_dst_filepath
        with open(invoice_path, 'w', encoding='utf-8') as f:
            json.dump(initial_invoice_data, f, ensure_ascii=False, indent=2)

        # Set up TSV SmartTable file
        smarttable_file = Path("/data/inputdata/smarttable_measurements.tsv")
        context.resource_paths.rawfiles = (smarttable_file,)
        if context.srcpaths.config.smarttable is None:
            from unittest.mock import Mock
            context.srcpaths.config.smarttable = Mock()
        context.srcpaths.config.smarttable.save_table_file = True
        context.srcpaths.config.system.save_raw = False
        context.srcpaths.config.system.save_nonshared_raw = False

        # Mock validators to skip validation
        mock_meta_validator.return_value.process.return_value = None
        mock_invoice_validator.return_value.process.return_value = None

        # Process
        with pytest.raises(SkipRemainingProcessorsError):
            processor.process(context)

        # Verify dataName was updated
        with open(invoice_path, 'r', encoding='utf-8') as f:
            updated_invoice = json.load(f)

        assert updated_invoice['basic']['dataName'] == 'smarttable_measurements.tsv'
        assert updated_invoice['basic']['description'] is None
        assert updated_invoice['custom']['existing'] == "value"
        assert updated_invoice['sample']['names'] == ["sample"]

    @patch('rdetoolkit.processing.processors.smarttable_early_exit.MetadataValidator')
    @patch('rdetoolkit.processing.processors.smarttable_early_exit.InvoiceValidator')
    def test_no_dataname_update_when_save_table_file_disabled(self, mock_invoice_validator, mock_meta_validator, smarttable_processing_context):
        """Test that dataName is NOT updated when save_table_file is disabled."""
        processor = SmartTableEarlyExitProcessor()
        context = smarttable_processing_context

        # Create initial invoice.json
        original_data_name = "should_remain_unchanged"
        initial_invoice_data = {
            "basic": {
                "dataName": original_data_name,
                "description": "Test"
            }
        }

        invoice_path = context.invoice_dst_filepath
        with open(invoice_path, 'w', encoding='utf-8') as f:
            json.dump(initial_invoice_data, f, ensure_ascii=False, indent=2)

        # Set up SmartTable file but disable save_table_file
        smarttable_file = Path("/data/inputdata/smarttable_test.xlsx")
        context.resource_paths.rawfiles = (smarttable_file,)
        if context.srcpaths.config.smarttable is None:
            from unittest.mock import Mock
            context.srcpaths.config.smarttable = Mock()
        context.srcpaths.config.smarttable.save_table_file = False  # Disabled

        # Mock validators to skip validation
        mock_meta_validator.return_value.process.return_value = None
        mock_invoice_validator.return_value.process.return_value = None

        # Process (should still raise SkipRemainingProcessorsError due to validation)
        with pytest.raises(SkipRemainingProcessorsError):
            processor.process(context)

        # Verify dataName was NOT updated
        with open(invoice_path, 'r', encoding='utf-8') as f:
            updated_invoice = json.load(f)

        assert updated_invoice['basic']['dataName'] == original_data_name  # Should remain unchanged

    @patch('rdetoolkit.processing.processors.smarttable_early_exit.MetadataValidator')
    @patch('rdetoolkit.processing.processors.smarttable_early_exit.InvoiceValidator')
    def test_multiple_smarttable_files_uses_first_match(self, mock_invoice_validator, mock_meta_validator, smarttable_processing_context):
        """Test that when multiple SmartTable files exist, the first one is used for dataName update."""
        processor = SmartTableEarlyExitProcessor()
        context = smarttable_processing_context

        # Create initial invoice.json
        initial_invoice_data = {
            "basic": {"dataName": "original"},
            "custom": {},
            "sample": {}
        }

        invoice_path = context.invoice_dst_filepath
        with open(invoice_path, 'w', encoding='utf-8') as f:
            json.dump(initial_invoice_data, f, ensure_ascii=False, indent=2)

        # Set up multiple SmartTable files (first should be used)
        smarttable_files = (
            Path("/data/inputdata/smarttable_first.xlsx"),
            Path("/data/inputdata/smarttable_second.csv"),
            Path("/data/temp/fsmarttable_extracted.csv")  # This is not original SmartTable
        )
        context.resource_paths.rawfiles = smarttable_files
        if context.srcpaths.config.smarttable is None:
            from unittest.mock import Mock
            context.srcpaths.config.smarttable = Mock()
        context.srcpaths.config.smarttable.save_table_file = True
        context.srcpaths.config.system.save_raw = False
        context.srcpaths.config.system.save_nonshared_raw = False

        # Mock validators to skip validation
        mock_meta_validator.return_value.process.return_value = None
        mock_invoice_validator.return_value.process.return_value = None

        # Process
        with pytest.raises(SkipRemainingProcessorsError):
            processor.process(context)

        # Verify dataName was updated with the first SmartTable file
        with open(invoice_path, 'r', encoding='utf-8') as f:
            updated_invoice = json.load(f)

        assert updated_invoice['basic']['dataName'] == 'smarttable_first.xlsx'
