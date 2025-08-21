import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import pandas as pd

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.processing.processors.invoice import (
    StandardInvoiceInitializer,
    ExcelInvoiceInitializer,
    SmartTableInvoiceInitializer,
    InvoiceInitializerFactory,
    # Backward compatibility aliases
    InvoiceHandler,
    ExcelInvoiceHandler,
)


class TestStandardInvoiceInitializer:
    """Test cases for StandardInvoiceInitializer processor."""

    def test_get_name(self):
        """Test processor name."""
        processor = StandardInvoiceInitializer()
        assert processor.get_name() == "StandardInvoiceInitializer"

    @patch('rdetoolkit.processing.processors.invoice.InvoiceFile')
    def test_process_success(self, mock_invoice_file, basic_processing_context):
        """Test successful invoice initialization."""
        processor = StandardInvoiceInitializer()
        context = basic_processing_context

        processor.process(context)

        # Verify invoice copy was called
        mock_invoice_file.copy_original_invoice.assert_called_once_with(
            context.resource_paths.invoice_org,
            context.invoice_dst_filepath,
        )

    @patch('rdetoolkit.processing.processors.invoice.InvoiceFile')
    def test_process_failure(self, mock_invoice_file, basic_processing_context):
        """Test invoice initialization handles exceptions."""
        processor = StandardInvoiceInitializer()
        context = basic_processing_context

        # Mock invoice copy to raise an exception
        mock_invoice_file.copy_original_invoice.side_effect = Exception("Copy failed")

        # Should re-raise the exception
        with pytest.raises(Exception, match="Copy failed"):
            processor.process(context)

    @patch('rdetoolkit.processing.processors.invoice.InvoiceFile')
    @patch('rdetoolkit.processing.processors.invoice.logger')
    def test_process_logging(self, mock_logger, mock_invoice_file, basic_processing_context):
        """Test that appropriate debug messages are logged."""
        processor = StandardInvoiceInitializer()
        context = basic_processing_context

        processor.process(context)

        # Verify debug messages
        mock_logger.debug.assert_any_call(f"Initializing invoice file: {context.invoice_dst_filepath}")
        mock_logger.debug.assert_any_call("Standard invoice initialization completed successfully")

    @patch('rdetoolkit.processing.processors.invoice.InvoiceFile')
    @patch('rdetoolkit.processing.processors.invoice.logger')
    def test_process_error_logging(self, mock_logger, mock_invoice_file, basic_processing_context):
        """Test that error messages are logged on failure."""
        processor = StandardInvoiceInitializer()
        context = basic_processing_context

        error_message = "Copy failed"
        mock_invoice_file.copy_original_invoice.side_effect = Exception(error_message)

        with pytest.raises(Exception):
            processor.process(context)

        # Verify error logging
        mock_logger.error.assert_called_with(f"Standard invoice initialization failed: {error_message}")


class TestExcelInvoiceInitializer:
    """Test cases for ExcelInvoiceInitializer processor."""

    def test_get_name(self):
        """Test processor name."""
        processor = ExcelInvoiceInitializer()
        assert processor.get_name() == "ExcelInvoiceInitializer"

    def test_process_no_excel_file(self, basic_processing_context):
        """Test ExcelInvoiceInitializer when no Excel file is provided."""
        processor = ExcelInvoiceInitializer()
        context = basic_processing_context
        context.excel_file = None

        # Should raise ValueError
        with pytest.raises(ValueError, match="Excel file path is required"):
            processor.process(context)

    @patch('rdetoolkit.processing.processors.invoice.ExcelInvoiceFile')
    def test_process_success(self, mock_excel_invoice_file, basic_processing_context):
        """Test successful Excel invoice initialization."""
        processor = ExcelInvoiceInitializer()
        context = basic_processing_context
        context.excel_file = Path("test_excel.xlsx")

        # Mock Excel invoice file
        mock_excel_invoice = MagicMock()
        mock_excel_invoice_file.return_value = mock_excel_invoice

        processor.process(context)
        # Verify Excel invoice file creation
        mock_excel_invoice_file.assert_called_once_with(context.excel_file)
        # Verify overwrite was called
        mock_excel_invoice.overwrite.assert_called_once_with(
            context.resource_paths.invoice_org,
            context.invoice_dst_filepath,
            context.resource_paths.invoice_schema_json,
            int(context.index),
        )

    @patch('rdetoolkit.processing.processors.invoice.ExcelInvoiceFile')
    def test_process_structured_error(self, mock_excel_invoice_file, basic_processing_context):
        """Test ExcelInvoiceInitializer handles StructuredError."""
        processor = ExcelInvoiceInitializer()
        context = basic_processing_context
        context.excel_file = Path("test_excel.xlsx")

        # Mock Excel invoice to raise StructuredError
        mock_excel_invoice = MagicMock()
        mock_excel_invoice.overwrite.side_effect = StructuredError("Structured error")
        mock_excel_invoice_file.return_value = mock_excel_invoice

        # Should re-raise StructuredError
        with pytest.raises(StructuredError, match="Structured error"):
            processor.process(context)

    @patch('rdetoolkit.processing.processors.invoice.ExcelInvoiceFile')
    def test_process_general_exception(self, mock_excel_invoice_file, basic_processing_context):
        """Test ExcelInvoiceInitializer handles general exceptions."""
        processor = ExcelInvoiceInitializer()
        context = basic_processing_context
        context.excel_file = Path("test_excel.xlsx")

        # Mock Excel invoice to raise general exception
        mock_excel_invoice = MagicMock()
        mock_excel_invoice.overwrite.side_effect = ValueError("General error")
        mock_excel_invoice_file.return_value = mock_excel_invoice

        # Should wrap in StructuredError
        with pytest.raises(StructuredError) as exc_info:
            processor.process(context)

        assert f"Failed to generate invoice file for data {context.index}" in str(exc_info.value)

    def test_parse_index_success(self):
        """Test successful index parsing."""
        processor = ExcelInvoiceInitializer()

        assert processor._parse_index("0001") == 1
        assert processor._parse_index("123") == 123
        assert processor._parse_index("0") == 0

    def test_parse_index_failure(self):
        """Test index parsing failure."""
        processor = ExcelInvoiceInitializer()

        with pytest.raises(ValueError, match="Invalid index format"):
            processor._parse_index("abc")

        with pytest.raises(ValueError, match="Invalid index format"):
            processor._parse_index("12.5")

    @patch('rdetoolkit.processing.processors.invoice.ExcelInvoiceFile')
    @patch('rdetoolkit.processing.processors.invoice.logger')
    def test_process_logging(self, mock_logger, mock_excel_invoice_file, basic_processing_context):
        """Test that appropriate debug messages are logged."""
        processor = ExcelInvoiceInitializer()
        context = basic_processing_context
        context.excel_file = Path("test_excel.xlsx")

        mock_excel_invoice = MagicMock()
        mock_excel_invoice_file.return_value = mock_excel_invoice

        processor.process(context)

        # Verify debug messages
        mock_logger.debug.assert_any_call(f"Initializing invoice from Excel file: {context.excel_file}")
        mock_logger.debug.assert_any_call("Excel invoice initialization completed successfully")


class TestInvoiceInitializerFactory:
    """Test cases for InvoiceInitializerFactory."""

    def test_create_standard_initializer(self):
        """Test creating standard invoice initializer."""
        # Test various standard modes
        for mode in ("rdeformat", "multidatatile", "invoice"):
            processor = InvoiceInitializerFactory.create(mode)
            assert isinstance(processor, StandardInvoiceInitializer)

    def test_create_excel_initializer(self):
        """Test creating Excel invoice initializer."""
        processor = InvoiceInitializerFactory.create("excelinvoice")
        assert isinstance(processor, ExcelInvoiceInitializer)

    def test_create_case_insensitive(self):
        """Test factory is case insensitive."""
        processor1 = InvoiceInitializerFactory.create("RDEFORMAT")
        processor2 = InvoiceInitializerFactory.create("ExcelInvoice")

        assert isinstance(processor1, StandardInvoiceInitializer)
        assert isinstance(processor2, ExcelInvoiceInitializer)

    def test_create_unsupported_mode(self):
        """Test factory raises error for unsupported mode."""
        with pytest.raises(ValueError, match="Unsupported mode for invoice initialization"):
            InvoiceInitializerFactory.create("unknown_mode")

    def test_get_supported_modes(self):
        """Test getting supported modes."""
        modes = InvoiceInitializerFactory.get_supported_modes()
        expected_modes = ("rdeformat", "multidatatile", "invoice", "excelinvoice")

        assert modes == expected_modes
        assert isinstance(modes, tuple)

    @pytest.mark.parametrize("mode,expected_class", [
        ("rdeformat", StandardInvoiceInitializer),
        ("multidatatile", StandardInvoiceInitializer),
        ("invoice", StandardInvoiceInitializer),
        ("excelinvoice", ExcelInvoiceInitializer),
    ])
    def test_factory_creates_correct_processor(self, mode, expected_class):
        """Test factory creates correct processor for each mode."""
        processor = InvoiceInitializerFactory.create(mode)
        assert isinstance(processor, expected_class)


class TestSmartTableInvoiceInitializer:
    """Test cases for SmartTableInvoiceInitializer processor."""

    def test_get_name(self):
        """Test processor name."""
        processor = SmartTableInvoiceInitializer()
        assert processor.get_name() == "SmartTableInvoiceInitializer"

    def test_ensure_required_fields_basic_structure(self):
        """Test _ensure_required_fields basic functionality."""
        processor = SmartTableInvoiceInitializer()

        # Test data without any fields
        invoice_data = {}
        processor._ensure_required_fields(invoice_data)

        # Should add only basic field (custom and sample fields are controlled by schema validation now)
        assert "basic" in invoice_data
        assert invoice_data["basic"] == {}
        # custom and sample fields are no longer automatically added

    def test_ensure_required_fields_preserve_existing(self):
        """Test _ensure_required_fields preserves existing fields."""
        processor = SmartTableInvoiceInitializer()

        # Test data with existing fields
        existing_basic = {"dataName": "test"}
        existing_custom = {"existing": "custom_data"}
        existing_sample = {"existing": "sample_data"}
        invoice_data = {"basic": existing_basic, "custom": existing_custom, "sample": existing_sample}
        processor._ensure_required_fields(invoice_data)

        # Should preserve existing data
        assert invoice_data["basic"] == existing_basic
        assert invoice_data["custom"] == existing_custom
        assert invoice_data["sample"] == existing_sample

    def test_ensure_required_fields_partial_fields(self):
        """Test _ensure_required_fields with existing basic field."""
        processor = SmartTableInvoiceInitializer()

        # Test data with only basic field
        invoice_data = {"basic": {"dataName": "test"}}
        processor._ensure_required_fields(invoice_data)

        # Should preserve existing basic field (custom and sample fields are controlled by schema validation now)
        assert invoice_data["basic"] == {"dataName": "test"}
        # custom and sample fields are no longer automatically added

    def test_process_not_smarttable_mode(self, basic_processing_context):
        """Test process raises ValueError when not in SmartTable mode."""
        processor = SmartTableInvoiceInitializer()
        context = basic_processing_context

        # Ensure context is not in SmartTable mode
        assert not context.is_smarttable_mode

        with pytest.raises(ValueError, match="SmartTable file not provided in processing context"):
            processor.process(context)

    @patch('pathlib.Path.exists')
    @patch('pandas.read_csv')
    @patch('rdetoolkit.processing.processors.invoice.readf_json')
    @patch('rdetoolkit.processing.processors.invoice.writef_json')
    def test_process_new_invoice_from_csv(self, mock_writef_json, mock_readf_json, mock_read_csv, mock_exists, smarttable_processing_context):
        """Test creating a new invoice from CSV when no original invoice exists."""
        processor = SmartTableInvoiceInitializer()
        context = smarttable_processing_context

        # Mock CSV data with various field types
        csv_data = pd.DataFrame({
            'basic/dataName': ['Test Data'],
            'basic/description': ['Test Description'],
            'custom/sample1': ['2023-01-01'],
            'sample/names': ['Sample Name'],
            'sample/generalAttributes.term1': ['value1'],
            'sample/specificAttributes.class1.term2': ['value2'],
            'meta/ignored': ['should be ignored'],
            'inputdata1': ['also ignored']
        })
        mock_read_csv.return_value = csv_data

        # Mock that original invoice doesn't exist
        mock_exists.return_value = False

        # Mock schema - minimal structure based on real schema
        mock_readf_json.return_value = {
            "type": "object",
            "required": ["custom", "sample"],
            "properties": {
                "custom": {
                    "type": "object",
                    "label": {"ja": "固有情報", "en": "Custom Information"},
                    "required": ["sample1"],
                    "properties": {
                        "sample1": {
                            "type": "string",
                            "format": "date",
                            "label": {"ja": "サンプル１", "en": "sample1"}
                        }
                    }
                },
                "sample": {
                    "type": "object",
                    "label": {"ja": "試料情報", "en": "Sample Information"},
                    "properties": {
                        "generalAttributes": {
                            "type": "array",
                            "items": []
                        },
                        "specificAttributes": {
                            "type": "array",
                            "items": []
                        }
                    }
                }
            }
        }

        # Process
        processor.process(context)

        # Verify CSV was read
        mock_read_csv.assert_called_once()

        # Verify invoice was written
        mock_writef_json.assert_called_once()
        _, written_data = mock_writef_json.call_args[0]

        # Check basic fields
        assert written_data['basic']['dataName'] == 'Test Data'
        assert written_data['basic']['description'] == 'Test Description'

        # Check custom fields
        assert written_data['custom']['sample1'] == '2023-01-01'

        # Check sample fields
        assert written_data['sample']['names'] == ['Sample Name']  # Should be array

        # Check generalAttributes
        assert 'generalAttributes' in written_data['sample']
        assert any(
            attr['termId'] == 'term1' and attr['value'] == 'value1'
            for attr in written_data['sample']['generalAttributes']
        )
        # Check specificAttributes
        assert 'specificAttributes' in written_data['sample']
        assert any(
            attr['classId'] == 'class1' and attr['termId'] == 'term2' and attr['value'] == 'value2'
            for attr in written_data['sample']['specificAttributes']
        )

    @patch('pathlib.Path.exists')
    @patch('pandas.read_csv')
    @patch('rdetoolkit.processing.processors.invoice.readf_json')
    @patch('rdetoolkit.processing.processors.invoice.writef_json')
    def test_process_update_existing_invoice(self, mock_writef_json, mock_readf_json, mock_read_csv, mock_exists, smarttable_processing_context):
        """Test updating an existing invoice with CSV data."""
        processor = SmartTableInvoiceInitializer()
        context = smarttable_processing_context

        # Mock CSV data with updates
        csv_data = pd.DataFrame({
            'basic/dataName': ['Updated Name'],
            'sample/generalAttributes.term1': ['updated_value1'],
            'sample/generalAttributes.term3': ['new_value3']
        })
        mock_read_csv.return_value = csv_data

        # Mock that original invoice exists
        mock_exists.return_value = True

        # Mock existing invoice data
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

        # Mock schema
        mock_readf_json.side_effect = [
            existing_invoice,
            {"definitions": {}, "properties": {}}
        ]

        # Process
        processor.process(context)

        # Verify invoice was written
        mock_writef_json.assert_called_once()
        _, written_data = mock_writef_json.call_args[0]

        # Check updated fields
        assert written_data['basic']['dataName'] == 'Updated Name'
        assert written_data['basic']['description'] == 'Original Description'

        # Check preserved custom fields
        assert written_data['custom']['existingField'] == 'preserved_value'

        # Check generalAttributes updates
        attrs = written_data['sample']['generalAttributes']
        term1_attr = next((a for a in attrs if a['termId'] == 'term1'), None)
        term2_attr = next((a for a in attrs if a['termId'] == 'term2'), None)
        term3_attr = next((a for a in attrs if a['termId'] == 'term3'), None)

        assert term1_attr['value'] == 'updated_value1'
        assert term2_attr['value'] == 'preserved_value2'
        assert term3_attr['value'] == 'new_value3'

    @patch('pathlib.Path.exists')
    @patch('pandas.read_csv')
    @patch('rdetoolkit.processing.processors.invoice.readf_json')
    @patch('rdetoolkit.processing.processors.invoice.writef_json')
    def test_process_with_empty_and_nan_values(self, mock_writef_json, mock_readf_json, mock_read_csv, mock_exists, smarttable_processing_context):
        """Test processing CSV with empty strings and NaN values."""
        processor = SmartTableInvoiceInitializer()
        context = smarttable_processing_context

        # Mock CSV data with empty and NaN values
        csv_data = pd.DataFrame({
            'basic/dataName': ['Valid Name'],
            'basic/empty': [''],
            'basic/nan': [pd.NA],
            'custom/field1': ['value1']
        })
        mock_read_csv.return_value = csv_data

        # Mock that original invoice doesn't exist
        mock_exists.return_value = False

        # Mock schema - minimal structure
        mock_readf_json.return_value = {
            "type": "object",
            "required": ["custom", "sample"],
            "properties": {
                "custom": {
                    "type": "object",
                    "label": {"ja": "固有情報", "en": "Custom Information"},
                    "required": [],
                    "properties": {
                        "field1": {
                            "type": "string",
                            "label": {"ja": "フィールド１", "en": "Field 1"}
                        }
                    }
                },
                "sample": {
                    "type": "object",
                    "label": {"ja": "試料情報", "en": "Sample Information"},
                    "properties": {}
                }
            }
        }

        processor.process(context)

        mock_writef_json.assert_called_once()
        _, written_data = mock_writef_json.call_args[0]

        # Check that only non-empty values were written
        assert written_data['basic']['dataName'] == 'Valid Name'
        assert 'empty' not in written_data['basic']
        assert 'nan' not in written_data['basic']
        assert written_data['custom']['field1'] == 'value1'

    @patch('pathlib.Path.exists')
    @patch('pandas.read_csv')
    @patch('rdetoolkit.processing.processors.invoice.readf_json')
    @patch('rdetoolkit.processing.processors.invoice.writef_json')
    def test_process_type_conversion_with_schema(self, mock_writef_json, mock_readf_json, mock_read_csv, mock_exists, smarttable_processing_context):
        """Test type conversion for custom fields using schema."""
        processor = SmartTableInvoiceInitializer()
        context = smarttable_processing_context

        # Mock CSV data with values needing type conversion
        csv_data = pd.DataFrame({
            'custom/intField': ['42'],
            'custom/floatField': ['3.14'],
            'custom/boolField': ['true'],
            'custom/stringField': ['text']
        })
        mock_read_csv.return_value = csv_data

        # Mock that original invoice doesn't exist
        mock_exists.return_value = False

        # Mock schema with type definitions
        mock_readf_json.return_value = {
            "type": "object",
            "required": ["custom", "sample"],
            "properties": {
                "custom": {
                    "type": "object",
                    "label": {"ja": "固有情報", "en": "Custom Information"},
                    "required": ["intField", "floatField", "boolField", "stringField"],
                    "properties": {
                        "intField": {
                            "type": "integer",
                            "label": {"ja": "整数フィールド", "en": "Integer Field"}
                        },
                        "floatField": {
                            "type": "number",
                            "label": {"ja": "浮動小数点フィールド", "en": "Float Field"}
                        },
                        "boolField": {
                            "type": "boolean",
                            "label": {"ja": "ブールフィールド", "en": "Boolean Field"}
                        },
                        "stringField": {
                            "type": "string",
                            "label": {"ja": "文字列フィールド", "en": "String Field"}
                        }
                    }
                },
                "sample": {
                    "type": "object",
                    "label": {"ja": "試料情報", "en": "Sample Information"},
                    "properties": {}
                }
            }
        }

        processor.process(context)

        # Verify type conversions
        written_path, written_data = mock_writef_json.call_args[0]
        assert written_data['custom']['intField'] == 42
        assert written_data['custom']['floatField'] == 3.14
        assert written_data['custom']['boolField'] is True
        assert written_data['custom']['stringField'] == 'text'

    def test_process_no_rawfiles(self, smarttable_processing_context):
        """Test process raises StructuredError when no raw files exist."""
        processor = SmartTableInvoiceInitializer()
        context = smarttable_processing_context

        # Remove rawfiles
        context.resource_paths.rawfiles = ()

        with pytest.raises(StructuredError, match="No CSV file found in rawfiles"):
            processor.process(context)

    @patch('pandas.read_csv')
    def test_process_csv_read_error(self, mock_read_csv, smarttable_processing_context):
        """Test process handles CSV read errors properly."""
        processor = SmartTableInvoiceInitializer()
        context = smarttable_processing_context

        # Mock CSV read error
        mock_read_csv.side_effect = pd.errors.EmptyDataError("No data")

        with pytest.raises(StructuredError) as exc_info:
            processor.process(context)

        assert "Failed to initialize invoice from SmartTable" in str(exc_info.value)

    @patch('pathlib.Path.exists')
    @patch('pandas.read_csv')
    @patch('rdetoolkit.processing.processors.invoice.readf_json')
    @patch('rdetoolkit.processing.processors.invoice.writef_json')
    @patch('rdetoolkit.processing.processors.invoice.logger')
    def test_process_logging(self, mock_logger, mock_writef_json, mock_readf_json, mock_read_csv, mock_exists, smarttable_processing_context):
        """Test that appropriate debug messages are logged during processing."""
        processor = SmartTableInvoiceInitializer()
        context = smarttable_processing_context

        # Mock simple CSV data
        csv_data = pd.DataFrame({'basic/dataName': ['Test']})
        mock_read_csv.return_value = csv_data

        # Mock that original invoice doesn't exist
        mock_exists.return_value = False
        mock_readf_json.return_value = {"definitions": {}, "properties": {}}

        # Process
        processor.process(context)

        # Verify debug logging
        mock_logger.debug.assert_any_call(f"Processing SmartTable invoice initialization for {context.mode_name}")
        assert any("Processing CSV file" in str(call) for call in mock_logger.debug.call_args_list)
        assert any("Successfully generated invoice" in str(call) for call in mock_logger.debug.call_args_list)

    @patch('pathlib.Path.exists')
    @patch('pandas.read_csv')
    @patch('rdetoolkit.processing.processors.invoice.readf_json')
    @patch('rdetoolkit.processing.processors.invoice.writef_json')
    def test_process_complex_specific_attributes(self, mock_writef_json, mock_readf_json, mock_read_csv, mock_exists, smarttable_processing_context):
        """Test processing multiple specificAttributes with same classId."""
        processor = SmartTableInvoiceInitializer()
        context = smarttable_processing_context

        # Mock CSV with multiple specific attributes
        csv_data = pd.DataFrame({
            'sample/specificAttributes.class1.term1': ['value1'],
            'sample/specificAttributes.class1.term2': ['value2'],
            'sample/specificAttributes.class2.term1': ['value3']
        })
        mock_read_csv.return_value = csv_data

        # Mock that original invoice doesn't exist
        mock_exists.return_value = False
        mock_readf_json.return_value = {"definitions": {}, "properties": {}}

        # Process
        processor.process(context)

        # Verify specific attributes structure
        written_path, written_data = mock_writef_json.call_args[0]
        spec_attrs = written_data['sample']['specificAttributes']

        # Should have 3 entries
        assert len(spec_attrs) == 3

        # Check each attribute
        assert any(a['classId'] == 'class1' and a['termId'] == 'term1' and a['value'] == 'value1' for a in spec_attrs)
        assert any(a['classId'] == 'class1' and a['termId'] == 'term2' and a['value'] == 'value2' for a in spec_attrs)
        assert any(a['classId'] == 'class2' and a['termId'] == 'term1' and a['value'] == 'value3' for a in spec_attrs)


class TestBackwardCompatibilityAliases:
    """Test backward compatibility aliases."""

    def test_invoice_handler_alias(self):
        """Test InvoiceHandler alias works correctly."""
        processor = InvoiceHandler()
        assert isinstance(processor, StandardInvoiceInitializer)
        assert processor.get_name() == "StandardInvoiceInitializer"

    def test_excel_invoice_handler_alias(self):
        """Test ExcelInvoiceHandler alias works correctly."""
        processor = ExcelInvoiceHandler()
        assert isinstance(processor, ExcelInvoiceInitializer)
        assert processor.get_name() == "ExcelInvoiceInitializer"
