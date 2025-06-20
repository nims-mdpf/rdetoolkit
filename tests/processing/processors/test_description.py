import pytest
from unittest.mock import patch, MagicMock

from rdetoolkit.processing.processors.descriptions import DescriptionUpdater
from rdetoolkit.processing.context import ProcessingContext


class TestDescriptionUpdater:
    """Test cases for DescriptionUpdater processor."""

    def test_get_name(self):
        """Test processor name."""
        processor = DescriptionUpdater()
        assert processor.get_name() == "DescriptionUpdater"

    @patch('rdetoolkit.processing.processors.descriptions.update_description_with_features')
    def test_process_success(self, mock_update_func, basic_processing_context):
        """Test successful description update."""
        processor = DescriptionUpdater()
        context = basic_processing_context

        # プロセッサを実行
        processor.process(context)

        # Verify that update_description_with_features was called with correct arguments
        mock_update_func.assert_called_once_with(
            context.resource_paths,
            context.invoice_dst_filepath,
            context.metadata_def_path,
        )

    @patch('rdetoolkit.processing.processors.descriptions.update_description_with_features')
    def test_process_with_exception_suppressed(self, mock_update_func, basic_processing_context):
        """Test that exceptions are properly suppressed during update."""
        processor = DescriptionUpdater()
        context = basic_processing_context

        mock_update_func.side_effect = ValueError("Test error")

        # The processor should complete successfully even when an exception occurs
        processor.process(context)
        mock_update_func.assert_called_once_with(
            context.resource_paths,
            context.invoice_dst_filepath,
            context.metadata_def_path,
        )

    @patch('rdetoolkit.processing.processors.descriptions.update_description_with_features')
    @patch('rdetoolkit.processing.processors.descriptions.logger')
    def test_process_logs_debug_messages(self, mock_logger, mock_update_func, basic_processing_context):
        """Test that appropriate debug messages are logged."""
        processor = DescriptionUpdater()
        context = basic_processing_context

        processor.process(context)

        # Verify that log messages were recorded
        mock_logger.debug.assert_any_call("Updating descriptions with features")
        mock_logger.debug.assert_any_call("Description update completed (errors suppressed)")
