"""Unit tests for dataset processing processor."""

import pytest
from unittest.mock import patch, MagicMock

from rdetoolkit.processing.processors.datasets import DatasetRunner


class TestDatasetRunner:
    """Test cases for DatasetRunner processor."""

    def test_get_name(self):
        """Test processor name."""
        processor = DatasetRunner()
        assert processor.get_name() == "DatasetRunner"

    def test_process_no_dataset_function(self, basic_processing_context):
        """Test DatasetRunner when no dataset function is provided."""
        processor = DatasetRunner()
        context = basic_processing_context
        context.datasets_function = None

        # Verify that datasets_function is None
        assert context.datasets_function is None

        # Should complete without calling any function
        processor.process(context)

    def test_process_dataset_function_success(self, basic_processing_context):
        """Test successful dataset function execution."""
        processor = DatasetRunner()
        context = basic_processing_context

        # Create a mock dataset function
        mock_function = MagicMock()
        context.datasets_function = mock_function

        processor.process(context)

        # Verify that dataset function was called with correct arguments
        mock_function.assert_called_once_with(context.srcpaths, context.resource_paths)

    def test_process_dataset_function_failure(self, basic_processing_context):
        """Test dataset function execution handles exceptions."""
        processor = DatasetRunner()
        context = basic_processing_context

        # Create a mock dataset function that raises an exception
        mock_function = MagicMock()
        mock_function.side_effect = ValueError("Test dataset processing error")
        context.datasets_function = mock_function

        # Should re-raise the exception
        with pytest.raises(ValueError):
            processor.process(context)

        # Verify that dataset function was called
        mock_function.assert_called_once_with(context.srcpaths, context.resource_paths)

    @patch('rdetoolkit.processing.processors.datasets.logger')
    def test_process_logs_debug_messages_no_function(self, mock_logger, basic_processing_context):
        """Test that appropriate debug messages are logged when no function provided."""
        processor = DatasetRunner()
        context = basic_processing_context
        context.datasets_function = None

        processor.process(context)

        # Verify that debug message was logged
        mock_logger.debug.assert_called_with("No dataset processing function provided, skipping")

    @patch('rdetoolkit.processing.processors.datasets.logger')
    def test_process_logs_debug_messages_success(self, mock_logger, basic_processing_context):
        """Test that appropriate debug messages are logged on success."""
        processor = DatasetRunner()
        context = basic_processing_context

        # Create a mock dataset function
        mock_function = MagicMock()
        context.datasets_function = mock_function

        processor.process(context)

        # Check that both debug messages were logged
        debug_calls = [call.args[0] for call in mock_logger.debug.call_args_list]
        assert "Executing custom dataset processing function" in debug_calls
        assert "Custom dataset processing completed successfully" in debug_calls

    @patch('rdetoolkit.processing.processors.datasets.logger')
    def test_process_logs_error_on_exception(self, mock_logger, basic_processing_context):
        """Test that error is logged when exception occurs."""
        processor = DatasetRunner()
        context = basic_processing_context

        # Create a mock dataset function that raises an exception
        mock_function = MagicMock()
        error_message = "Test dataset processing error"
        mock_function.side_effect = ValueError(error_message)
        context.datasets_function = mock_function

        with pytest.raises(ValueError):
            processor.process(context)

        # Verify that error message was logged
        mock_logger.error.assert_called_with(f"Custom dataset processing failed: {error_message}")

    def test_process_dataset_function_with_side_effects(self, basic_processing_context):
        """Test dataset function that has side effects."""
        processor = DatasetRunner()
        context = basic_processing_context

        # Track if the function was called and had side effects
        side_effect_tracker = {"called": False, "data_modified": False}

        def mock_dataset_function(_srcpaths, _resource_paths):
            # Mark that function was called and simulate data modification
            side_effect_tracker["called"] = True
            side_effect_tracker["data_modified"] = True

        context.datasets_function = mock_dataset_function

        processor.process(context)

        # Verify that the function was executed and had its side effects
        assert side_effect_tracker["called"] is True
        assert side_effect_tracker["data_modified"] is True

    def test_process_with_different_exception_types(self, basic_processing_context):
        """Test that processor handles different exception types."""
        processor = DatasetRunner()
        context = basic_processing_context

        # Test with FileNotFoundError
        mock_function = MagicMock()
        mock_function.side_effect = FileNotFoundError("File not found")
        context.datasets_function = mock_function

        with pytest.raises(FileNotFoundError):
            processor.process(context)

        # Test with RuntimeError
        mock_function.side_effect = RuntimeError("Runtime error")
        context.datasets_function = mock_function

        with pytest.raises(RuntimeError):
            processor.process(context)

    def test_process_dataset_function_receives_correct_arguments(self, basic_processing_context):
        """Test that dataset function receives the correct arguments."""
        processor = DatasetRunner()
        context = basic_processing_context

        # Create a dataset function that validates its arguments
        def mock_dataset_function(srcpaths, resource_paths):
            # Verify that the arguments are the expected objects
            assert srcpaths is context.srcpaths
            assert resource_paths is context.resource_paths
            # Verify that srcpaths has expected attributes
            assert hasattr(srcpaths, 'inputdata')
            assert hasattr(srcpaths, 'invoice')
            assert hasattr(srcpaths, 'tasksupport')
            assert hasattr(srcpaths, 'config')
            # Verify that resource_paths has expected attributes
            assert hasattr(resource_paths, 'rawfiles')
            assert hasattr(resource_paths, 'raw')
            assert hasattr(resource_paths, 'main_image')

        context.datasets_function = mock_dataset_function

        # Should complete without assertion errors
        processor.process(context)

    def test_process_dataset_function_can_be_lambda(self, basic_processing_context):
        """Test that dataset function can be a lambda function."""
        processor = DatasetRunner()
        context = basic_processing_context

        # Create a lambda function as dataset function
        executed = []
        context.datasets_function = lambda _srcpaths, _resource_paths: executed.append(True)

        processor.process(context)

        # Verify that lambda function was executed
        assert len(executed) == 1
        assert executed[0] is True

    @patch('rdetoolkit.processing.processors.datasets.logger')
    def test_process_logs_execution_order(self, mock_logger, basic_processing_context):
        """Test that debug messages are logged in correct order."""
        processor = DatasetRunner()
        context = basic_processing_context

        # Create a dataset function that we can track execution of
        execution_order = []

        def mock_dataset_function(_srcpaths, _resource_paths):
            execution_order.append("function_executed")

        context.datasets_function = mock_dataset_function

        processor.process(context)

        # Verify that function was executed
        assert execution_order == ["function_executed"]

        # Verify that logging happened in correct order
        debug_calls = [call.args[0] for call in mock_logger.debug.call_args_list]

        # Should have "Executing..." before function execution and "completed..." after
        assert "Executing custom dataset processing function" in debug_calls
        assert "Custom dataset processing completed successfully" in debug_calls

        # Find indices to verify order
        executing_index = debug_calls.index("Executing custom dataset processing function")
        completed_index = debug_calls.index("Custom dataset processing completed successfully")
        assert executing_index < completed_index
