"""Unit tests for validation processors."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from rdetoolkit.processing.processors.validation import MetadataValidator, InvoiceValidator
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.exceptions import MetadataValidationError, InvoiceSchemaValidationError


class TestMetadataValidator:
    """Test cases for MetadataValidator processor."""

    def test_get_name(self):
        """Test processor name."""
        processor = MetadataValidator()
        assert processor.get_name() == "MetadataValidator"

    def test_process_metadata_file_not_exists(self, basic_processing_context):
        """Test MetadataValidator when metadata.json does not exist."""
        processor = MetadataValidator()
        context = basic_processing_context
        
        # Mock metadata_path.exists() to return False
        with patch('rdetoolkit.processing.processors.validation.metadata_validate') as mock_validate:
            with patch('pathlib.Path.exists', return_value=False):
                processor.process(context)
                # Should not call metadata_validate when file doesn't exist
                mock_validate.assert_not_called()

    @patch('rdetoolkit.processing.processors.validation.metadata_validate')
    def test_process_metadata_validation_success(self, mock_validate, basic_processing_context):
        """Test successful metadata validation."""
        processor = MetadataValidator()
        context = basic_processing_context
        
        # Mock metadata_path.exists() to return True
        with patch('pathlib.Path.exists', return_value=True):
            processor.process(context)
            
            # Verify that metadata_validate was called with correct argument
            mock_validate.assert_called_once_with(context.metadata_path)

    @patch('rdetoolkit.processing.processors.validation.metadata_validate')
    def test_process_metadata_validation_failure(self, mock_validate, basic_processing_context):
        """Test metadata validation handles exceptions."""
        processor = MetadataValidator()
        context = basic_processing_context
        
        # Mock metadata_path.exists() to return True
        with patch('pathlib.Path.exists', return_value=True):
            # Mock validation to raise an exception
            mock_validate.side_effect = MetadataValidationError("Test validation error")
            
            # Should re-raise the exception
            with pytest.raises(MetadataValidationError):
                processor.process(context)
            
            # Verify that metadata_validate was called
            mock_validate.assert_called_once_with(context.metadata_path)

    @patch('rdetoolkit.processing.processors.validation.metadata_validate')
    @patch('rdetoolkit.processing.processors.validation.logger')
    def test_process_logs_debug_messages_success(self, mock_logger, mock_validate, basic_processing_context):
        """Test that appropriate debug messages are logged on success."""
        processor = MetadataValidator()
        context = basic_processing_context
        
        with patch('pathlib.Path.exists', return_value=True):
            processor.process(context)
            
            # Verify that debug success message was logged
            mock_logger.debug.assert_called_with("Metadata validation completed successfully")

    @patch('rdetoolkit.processing.processors.validation.metadata_validate')
    @patch('rdetoolkit.processing.processors.validation.logger')
    def test_process_logs_debug_messages_file_not_exists(self, mock_logger, mock_validate, basic_processing_context):
        """Test that appropriate debug messages are logged when file doesn't exist."""
        processor = MetadataValidator()
        context = basic_processing_context
        
        with patch('pathlib.Path.exists', return_value=False):
            processor.process(context)
            
            # Verify that debug message was logged
            mock_logger.debug.assert_called_with("metadata.json does not exist, skipping validation")
            # Should not call metadata_validate
            mock_validate.assert_not_called()

    @patch('rdetoolkit.processing.processors.validation.metadata_validate')
    @patch('rdetoolkit.processing.processors.validation.logger')
    def test_process_logs_error_on_exception(self, mock_logger, mock_validate, basic_processing_context):
        """Test that error is logged when exception occurs."""
        processor = MetadataValidator()
        context = basic_processing_context
        
        with patch('pathlib.Path.exists', return_value=True):
            # Mock validation to raise an exception
            error_message = "Test metadata validation error"
            mock_validate.side_effect = MetadataValidationError(error_message)
            
            with pytest.raises(MetadataValidationError):
                processor.process(context)
            
            # Verify that error message was logged
            mock_logger.error.assert_called_with(f"Metadata validation failed: {error_message}")


class TestInvoiceValidator:
    """Test cases for InvoiceValidator processor."""

    def test_get_name(self):
        """Test processor name."""
        processor = InvoiceValidator()
        assert processor.get_name() == "InvoiceValidator"

    @patch('rdetoolkit.processing.processors.validation.invoice_validate')
    def test_process_invoice_validation_success(self, mock_validate, basic_processing_context):
        """Test successful invoice validation."""
        processor = InvoiceValidator()
        context = basic_processing_context
        
        processor.process(context)
        
        # Verify that invoice_validate was called with correct arguments
        mock_validate.assert_called_once_with(
            context.invoice_dst_filepath,
            context.schema_path
        )

    @patch('rdetoolkit.processing.processors.validation.invoice_validate')
    def test_process_invoice_validation_failure(self, mock_validate, basic_processing_context):
        """Test invoice validation handles exceptions."""
        processor = InvoiceValidator()
        context = basic_processing_context
        
        # Mock validation to raise an exception
        mock_validate.side_effect = InvoiceSchemaValidationError("Test validation error")
        
        # Should re-raise the exception
        with pytest.raises(InvoiceSchemaValidationError):
            processor.process(context)
        
        # Verify that invoice_validate was called
        mock_validate.assert_called_once_with(
            context.invoice_dst_filepath,
            context.schema_path
        )

    @patch('rdetoolkit.processing.processors.validation.invoice_validate')
    @patch('rdetoolkit.processing.processors.validation.logger')
    def test_process_logs_debug_messages_success(self, mock_logger, mock_validate, basic_processing_context):
        """Test that appropriate debug messages are logged on success."""
        processor = InvoiceValidator()
        context = basic_processing_context
        
        processor.process(context)
        
        # Verify that debug success message was logged
        mock_logger.debug.assert_called_with("Invoice validation completed successfully")

    @patch('rdetoolkit.processing.processors.validation.invoice_validate')
    @patch('rdetoolkit.processing.processors.validation.logger')
    def test_process_logs_error_on_exception(self, mock_logger, mock_validate, basic_processing_context):
        """Test that error is logged when exception occurs."""
        processor = InvoiceValidator()
        context = basic_processing_context
        
        # Mock validation to raise an exception
        error_message = "Test invoice validation error"
        mock_validate.side_effect = InvoiceSchemaValidationError(error_message)
        
        with pytest.raises(InvoiceSchemaValidationError):
            processor.process(context)
        
        # Verify that error message was logged
        mock_logger.error.assert_called_with(f"Invoice validation failed: {error_message}")

    @patch('rdetoolkit.processing.processors.validation.invoice_validate')
    def test_process_with_different_exception_types(self, mock_validate, basic_processing_context):
        """Test invoice validation handles different exception types."""
        processor = InvoiceValidator()
        context = basic_processing_context
        
        # Test with FileNotFoundError
        mock_validate.side_effect = FileNotFoundError("File not found")
        
        with pytest.raises(FileNotFoundError):
            processor.process(context)
        
        # Test with ValueError
        mock_validate.side_effect = ValueError("Invalid value")
        
        with pytest.raises(ValueError):
            processor.process(context)