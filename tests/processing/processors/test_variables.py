"""Unit tests for magic variable processing."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from rdetoolkit.processing.processors.variables import VariableApplier
from rdetoolkit.processing.context import ProcessingContext


class TestVariableApplier:
    """Test cases for VariableApplier processor."""

    def test_get_name(self):
        """Test processor name."""
        processor = VariableApplier()
        assert processor.get_name() == "VariableApplier"

    def test_process_magic_variables_disabled(self, processing_context_disabled_features):
        """Test VariableApplier when magic variables are disabled."""
        processor = VariableApplier()
        context = processing_context_disabled_features
        
        # Verify that magic_variable is disabled
        assert not context.srcpaths.config.system.magic_variable
        
        with patch('rdetoolkit.processing.processors.variables.apply_magic_variable') as mock_apply:
            processor.process(context)
            # Should not call apply_magic_variable when disabled
            mock_apply.assert_not_called()

    def test_process_no_raw_files(self, processing_context_no_rawfiles):
        """Test VariableApplier when no raw files are available."""
        processor = VariableApplier()
        context = processing_context_no_rawfiles
        context.srcpaths.config.system.magic_variable = True
        
        # Verify that no raw files are available
        assert not context.resource_paths.rawfiles
        
        with patch('rdetoolkit.processing.processors.variables.apply_magic_variable') as mock_apply:
            processor.process(context)
            # Should not call apply_magic_variable when no raw files
            mock_apply.assert_not_called()

    @patch('rdetoolkit.processing.processors.variables.apply_magic_variable')
    def test_process_magic_variables_success_with_result(self, mock_apply, basic_processing_context):
        """Test successful magic variable application with result."""
        processor = VariableApplier()
        context = basic_processing_context
        context.srcpaths.config.system.magic_variable = True
        
        # Mock apply_magic_variable to return a result
        mock_result = {"basic": {"dataName": "test_file.txt"}}
        mock_apply.return_value = mock_result
        
        processor.process(context)
        
        # Verify that apply_magic_variable was called with correct arguments
        mock_apply.assert_called_once_with(
            context.invoice_dst_filepath,
            context.resource_paths.rawfiles[0],
            save_filepath=context.invoice_dst_filepath
        )

    @patch('rdetoolkit.processing.processors.variables.apply_magic_variable')
    def test_process_magic_variables_success_no_result(self, mock_apply, basic_processing_context):
        """Test successful magic variable application with no result."""
        processor = VariableApplier()
        context = basic_processing_context
        context.srcpaths.config.system.magic_variable = True
        
        # Mock apply_magic_variable to return empty result
        mock_apply.return_value = {}
        
        processor.process(context)
        
        # Verify that apply_magic_variable was called with correct arguments
        mock_apply.assert_called_once_with(
            context.invoice_dst_filepath,
            context.resource_paths.rawfiles[0],
            save_filepath=context.invoice_dst_filepath
        )

    @patch('rdetoolkit.processing.processors.variables.apply_magic_variable')
    def test_process_magic_variables_failure(self, mock_apply, basic_processing_context):
        """Test magic variable application handles exceptions."""
        processor = VariableApplier()
        context = basic_processing_context
        context.srcpaths.config.system.magic_variable = True
        
        # Mock apply_magic_variable to raise an exception
        mock_apply.side_effect = ValueError("Test magic variable error")
        
        # Should re-raise the exception
        with pytest.raises(ValueError):
            processor.process(context)
        
        # Verify that apply_magic_variable was called
        mock_apply.assert_called_once_with(
            context.invoice_dst_filepath,
            context.resource_paths.rawfiles[0],
            save_filepath=context.invoice_dst_filepath
        )

    @patch('rdetoolkit.processing.processors.variables.apply_magic_variable')
    @patch('rdetoolkit.processing.processors.variables.logger')
    def test_process_logs_debug_messages_disabled(self, mock_logger, mock_apply, processing_context_disabled_features):
        """Test that appropriate debug messages are logged when disabled."""
        processor = VariableApplier()
        context = processing_context_disabled_features
        
        processor.process(context)
        
        # Verify that debug disabled message was logged
        mock_logger.debug.assert_called_with("Magic variables disabled, skipping")
        # Should not call apply_magic_variable
        mock_apply.assert_not_called()

    @patch('rdetoolkit.processing.processors.variables.apply_magic_variable')
    @patch('rdetoolkit.processing.processors.variables.logger')
    def test_process_logs_debug_messages_no_raw_files(self, mock_logger, mock_apply, processing_context_no_rawfiles):
        """Test that appropriate debug messages are logged when no raw files."""
        processor = VariableApplier()
        context = processing_context_no_rawfiles
        context.srcpaths.config.system.magic_variable = True
        
        processor.process(context)
        
        # Verify that debug message was logged
        mock_logger.debug.assert_called_with("No raw files available for variable replacement")
        # Should not call apply_magic_variable
        mock_apply.assert_not_called()

    @patch('rdetoolkit.processing.processors.variables.apply_magic_variable')
    @patch('rdetoolkit.processing.processors.variables.logger')
    def test_process_logs_debug_messages_success_with_result(self, mock_logger, mock_apply, basic_processing_context):
        """Test that appropriate debug messages are logged on success with result."""
        processor = VariableApplier()
        context = basic_processing_context
        context.srcpaths.config.system.magic_variable = True
        
        # Mock apply_magic_variable to return a result
        mock_result = {"basic": {"dataName": "test_file.txt"}}
        mock_apply.return_value = mock_result
        
        processor.process(context)
        
        # Verify that debug success message was logged
        mock_logger.debug.assert_called_with("Magic variable replacement completed successfully")

    @patch('rdetoolkit.processing.processors.variables.apply_magic_variable')
    @patch('rdetoolkit.processing.processors.variables.logger')
    def test_process_logs_debug_messages_success_no_result(self, mock_logger, mock_apply, basic_processing_context):
        """Test that appropriate debug messages are logged on success with no result."""
        processor = VariableApplier()
        context = basic_processing_context
        context.srcpaths.config.system.magic_variable = True
        
        # Mock apply_magic_variable to return empty result
        mock_apply.return_value = {}
        
        processor.process(context)
        
        # Verify that debug no variables message was logged
        mock_logger.debug.assert_called_with("No magic variables found for replacement")

    @patch('rdetoolkit.processing.processors.variables.apply_magic_variable')
    @patch('rdetoolkit.processing.processors.variables.logger')
    def test_process_logs_error_on_exception(self, mock_logger, mock_apply, basic_processing_context):
        """Test that error is logged when exception occurs."""
        processor = VariableApplier()
        context = basic_processing_context
        context.srcpaths.config.system.magic_variable = True
        
        # Mock apply_magic_variable to raise an exception
        error_message = "Test magic variable error"
        mock_apply.side_effect = ValueError(error_message)
        
        with pytest.raises(ValueError):
            processor.process(context)
        
        # Verify that error message was logged
        mock_logger.error.assert_called_with(f"Magic variable replacement failed: {error_message}")

    @patch('rdetoolkit.processing.processors.variables.apply_magic_variable')
    def test_process_with_multiple_raw_files(self, mock_apply, basic_processing_context):
        """Test that processor uses the first raw file when multiple are available."""
        processor = VariableApplier()
        context = basic_processing_context
        context.srcpaths.config.system.magic_variable = True
        
        # Add multiple raw files to context
        additional_files = (
            Path("data/inputdata/test2.txt"),
            Path("data/inputdata/test3.txt"),
        )
        context.resource_paths.rawfiles = context.resource_paths.rawfiles + additional_files
        
        mock_apply.return_value = {"basic": {"dataName": "test_file.txt"}}
        
        processor.process(context)
        
        # Verify that apply_magic_variable was called with the first raw file
        mock_apply.assert_called_once_with(
            context.invoice_dst_filepath,
            context.resource_paths.rawfiles[0],  # Should use the first file
            save_filepath=context.invoice_dst_filepath
        )

    @patch('rdetoolkit.processing.processors.variables.apply_magic_variable')
    def test_process_with_different_exception_types(self, mock_apply, basic_processing_context):
        """Test that processor handles different exception types."""
        processor = VariableApplier()
        context = basic_processing_context
        context.srcpaths.config.system.magic_variable = True
        
        # Test with FileNotFoundError
        mock_apply.side_effect = FileNotFoundError("File not found")
        
        with pytest.raises(FileNotFoundError):
            processor.process(context)
        
        # Test with RuntimeError
        mock_apply.side_effect = RuntimeError("Runtime error")
        
        with pytest.raises(RuntimeError):
            processor.process(context)