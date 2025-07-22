"""Unit tests for invoice initialization processors."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

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
        
    def test_ensure_required_fields_basic_structure(self, tmp_path):
        """Test _ensure_required_fields basic functionality with temporary schema files."""
        processor = SmartTableInvoiceInitializer()
        
        # Create a temporary schema file
        schema_file = tmp_path / "invoice.schema.json"
        schema_data = {"required": ["custom", "sample"]}
        with open(schema_file, 'w') as f:
            import json
            json.dump(schema_data, f)
        
        # Mock context with the temporary schema file
        context = MagicMock()
        context.resource_paths.invoice_schema_json = schema_file
        
        # Test data without custom and sample
        invoice_data = {"basic": {}}
        processor._ensure_required_fields(invoice_data, context)
        
        # Should add both fields
        assert "basic" in invoice_data
        assert "custom" in invoice_data
        assert "sample" in invoice_data
        assert invoice_data["custom"] == {}
        assert invoice_data["sample"] == {}

    def test_ensure_required_fields_custom_only_schema(self, tmp_path):
        """Test _ensure_required_fields when schema requires only custom."""
        processor = SmartTableInvoiceInitializer()
        
        # Create schema requiring only custom
        schema_file = tmp_path / "invoice.schema.json"
        schema_data = {"required": ["custom"]}
        with open(schema_file, 'w') as f:
            import json
            json.dump(schema_data, f)
        
        context = MagicMock()
        context.resource_paths.invoice_schema_json = schema_file
        
        # Test data with sample field present
        invoice_data = {"basic": {}, "sample": {"existing": "data"}}
        processor._ensure_required_fields(invoice_data, context)
        
        # Should add custom and remove sample
        assert "basic" in invoice_data
        assert "custom" in invoice_data
        assert "sample" not in invoice_data

    def test_ensure_required_fields_sample_only_schema(self, tmp_path):
        """Test _ensure_required_fields when schema requires only sample."""
        processor = SmartTableInvoiceInitializer()
        
        # Create schema requiring only sample
        schema_file = tmp_path / "invoice.schema.json"
        schema_data = {"required": ["sample"]}
        with open(schema_file, 'w') as f:
            import json
            json.dump(schema_data, f)
        
        context = MagicMock()
        context.resource_paths.invoice_schema_json = schema_file
        
        # Test data with custom field present
        invoice_data = {"basic": {}, "custom": {"existing": "data"}}
        processor._ensure_required_fields(invoice_data, context)
        
        # Should add sample and remove custom
        assert "basic" in invoice_data
        assert "sample" in invoice_data
        assert "custom" not in invoice_data

    def test_ensure_required_fields_neither_required_schema(self, tmp_path):
        """Test _ensure_required_fields when schema requires neither custom nor sample."""
        processor = SmartTableInvoiceInitializer()
        
        # Create schema not requiring custom or sample
        schema_file = tmp_path / "invoice.schema.json"
        schema_data = {"required": []}
        with open(schema_file, 'w') as f:
            import json
            json.dump(schema_data, f)
        
        context = MagicMock()
        context.resource_paths.invoice_schema_json = schema_file
        
        # Test data with both fields present
        invoice_data = {"basic": {}, "custom": {"data": "test"}, "sample": {"data": "test"}}
        processor._ensure_required_fields(invoice_data, context)
        
        # Should remove both custom and sample
        assert "basic" in invoice_data
        assert "custom" not in invoice_data
        assert "sample" not in invoice_data

    def test_ensure_required_fields_preserve_existing(self, tmp_path):
        """Test _ensure_required_fields preserves existing required fields."""
        processor = SmartTableInvoiceInitializer()
        
        # Create schema requiring both custom and sample
        schema_file = tmp_path / "invoice.schema.json"
        schema_data = {"required": ["custom", "sample"]}
        with open(schema_file, 'w') as f:
            import json
            json.dump(schema_data, f)
        
        context = MagicMock()
        context.resource_paths.invoice_schema_json = schema_file
        
        # Test data with both fields already present
        existing_custom = {"existing": "custom_data"}
        existing_sample = {"existing": "sample_data"}
        invoice_data = {"basic": {}, "custom": existing_custom, "sample": existing_sample}
        processor._ensure_required_fields(invoice_data, context)
        
        # Should preserve existing data
        assert "basic" in invoice_data
        assert invoice_data["custom"] == existing_custom
        assert invoice_data["sample"] == existing_sample

    def test_ensure_required_fields_schema_not_found(self):
        """Test _ensure_required_fields handles schema file not found."""
        processor = SmartTableInvoiceInitializer()
        
        # Mock context with non-existent schema file
        context = MagicMock()
        context.resource_paths.invoice_schema_json = Path("/non/existent/file.json")
        
        # Test data without custom and sample
        invoice_data = {"basic": {}}
        processor._ensure_required_fields(invoice_data, context)
        
        # Should fallback to default behavior (add both fields)
        assert "basic" in invoice_data
        assert "custom" in invoice_data
        assert "sample" in invoice_data

    def test_ensure_required_fields_malformed_schema(self, tmp_path):
        """Test _ensure_required_fields handles malformed JSON schema."""
        processor = SmartTableInvoiceInitializer()
        
        # Create malformed JSON file
        schema_file = tmp_path / "invoice.schema.json"
        with open(schema_file, 'w') as f:
            f.write("{ malformed json")
        
        context = MagicMock()
        context.resource_paths.invoice_schema_json = schema_file
        
        # Test data without custom and sample
        invoice_data = {"basic": {}}
        processor._ensure_required_fields(invoice_data, context)
        
        # Should fallback to default behavior
        assert "basic" in invoice_data
        assert "custom" in invoice_data
        assert "sample" in invoice_data

    def test_ensure_required_fields_no_required_field_in_schema(self, tmp_path):
        """Test _ensure_required_fields when schema has no 'required' field."""
        processor = SmartTableInvoiceInitializer()
        
        # Create schema without required field
        schema_file = tmp_path / "invoice.schema.json"
        schema_data = {"properties": {}}
        with open(schema_file, 'w') as f:
            import json
            json.dump(schema_data, f)
        
        context = MagicMock()
        context.resource_paths.invoice_schema_json = schema_file
        
        # Test data with custom and sample
        invoice_data = {"basic": {}, "custom": {"data": "test"}, "sample": {"data": "test"}}
        processor._ensure_required_fields(invoice_data, context)
        
        # Should remove both fields since required defaults to empty list
        assert "basic" in invoice_data
        assert "custom" not in invoice_data
        assert "sample" not in invoice_data


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
