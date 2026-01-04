"""Unit tests for Result-based mode processing functions.

Tests for invoice_mode_process_result and backward compatibility.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
from rdetoolkit.models.result import WorkflowExecutionStatus
from rdetoolkit.result import Success, Failure
from rdetoolkit.modeproc import invoice_mode_process_result, invoice_mode_process


# =============================================================================
# invoice_mode_process_result Tests
# =============================================================================


def test_invoice_mode_process_result_success():
    """Test invoice_mode_process_result returns Success on successful execution."""
    # Setup
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)

    expected_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test Invoice",
        status="success",
        mode="invoice",
        target="test_target",
    )

    # Mock pipeline execution
    with patch("rdetoolkit.modeproc.PipelineFactory.create_invoice_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = expected_status
        mock_factory.return_value = mock_pipeline

        # Execute
        result = invoice_mode_process_result(index, srcpaths, resource_paths)

        # Assert
        assert isinstance(result, Success)
        status = result.unwrap()
        assert status == expected_status
        assert status.status == "success"
        assert status.mode == "invoice"


def test_invoice_mode_process_result_with_dataset_callback():
    """Test invoice_mode_process_result passes dataset callback to context."""
    # Setup
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)
    callback = Mock()

    expected_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test Invoice",
        status="success",
        mode="invoice",
        target="test_target",
    )

    # Mock pipeline execution
    with (
        patch("rdetoolkit.modeproc.ProcessingContext") as mock_context_class,
        patch("rdetoolkit.modeproc.PipelineFactory.create_invoice_pipeline") as mock_factory,
    ):
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = expected_status
        mock_factory.return_value = mock_pipeline

        # Execute
        result = invoice_mode_process_result(index, srcpaths, resource_paths, callback)

        # Assert
        assert isinstance(result, Success)
        # Verify callback was passed to ProcessingContext
        mock_context_class.assert_called_once()
        call_kwargs = mock_context_class.call_args.kwargs
        assert call_kwargs["datasets_function"] == callback


def test_invoice_mode_process_result_failure_on_exception():
    """Test invoice_mode_process_result returns Failure when exception occurs."""
    # Setup
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)

    error = RuntimeError("Pipeline execution failed")

    # Mock pipeline to raise exception
    with patch("rdetoolkit.modeproc.PipelineFactory.create_invoice_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.side_effect = error
        mock_factory.return_value = mock_pipeline

        # Execute
        result = invoice_mode_process_result(index, srcpaths, resource_paths)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == error
        assert str(result.error) == "Pipeline execution failed"


def test_invoice_mode_process_result_failure_on_validation_error():
    """Test invoice_mode_process_result captures validation errors."""
    # Setup
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)

    error = ValueError("Validation failed: invalid data")

    # Mock pipeline to raise validation error
    with patch("rdetoolkit.modeproc.PipelineFactory.create_invoice_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.side_effect = error
        mock_factory.return_value = mock_pipeline

        # Execute
        result = invoice_mode_process_result(index, srcpaths, resource_paths)

        # Assert
        assert isinstance(result, Failure)
        assert isinstance(result.error, ValueError)
        assert "Validation failed" in str(result.error)


def test_invoice_mode_process_result_failure_on_callback_error():
    """Test invoice_mode_process_result captures dataset callback errors."""
    # Setup
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)

    error = Exception("Dataset callback failed")

    # Mock pipeline to raise callback error
    with patch("rdetoolkit.modeproc.PipelineFactory.create_invoice_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.side_effect = error
        mock_factory.return_value = mock_pipeline

        # Execute
        result = invoice_mode_process_result(index, srcpaths, resource_paths)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == error


# =============================================================================
# Backward Compatibility Tests
# =============================================================================


def test_invoice_mode_process_backward_compatibility_success():
    """Test invoice_mode_process maintains backward compatibility with success case."""
    # Setup
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)

    expected_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test Invoice",
        status="success",
        mode="invoice",
        target="test_target",
    )

    # Mock pipeline execution
    with patch("rdetoolkit.modeproc.PipelineFactory.create_invoice_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = expected_status
        mock_factory.return_value = mock_pipeline

        # Execute - should return WorkflowExecutionStatus, not Result
        status = invoice_mode_process(index, srcpaths, resource_paths)

        # Assert
        assert isinstance(status, WorkflowExecutionStatus)
        assert status == expected_status
        assert status.status == "success"


def test_invoice_mode_process_backward_compatibility_raises_exception():
    """Test invoice_mode_process raises exception for backward compatibility."""
    # Setup
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)

    error = RuntimeError("Pipeline execution failed")

    # Mock pipeline to raise exception
    with patch("rdetoolkit.modeproc.PipelineFactory.create_invoice_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.side_effect = error
        mock_factory.return_value = mock_pipeline

        # Execute - should raise exception, not return Result
        with pytest.raises(RuntimeError, match="Pipeline execution failed"):
            invoice_mode_process(index, srcpaths, resource_paths)


def test_invoice_mode_process_delegates_to_result_function():
    """Test invoice_mode_process correctly delegates to invoice_mode_process_result."""
    # Setup
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)
    callback = Mock()

    expected_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test Invoice",
        status="success",
        mode="invoice",
        target="test_target",
    )

    # Mock the result function directly
    with patch("rdetoolkit.modeproc.invoice_mode_process_result") as mock_result_fn:
        mock_result_fn.return_value = Success(expected_status)

        # Execute
        status = invoice_mode_process(index, srcpaths, resource_paths, callback)

        # Assert
        assert status == expected_status
        # Verify invoice_mode_process_result was called with correct args
        mock_result_fn.assert_called_once_with(index, srcpaths, resource_paths, callback)


# =============================================================================
# Integration Tests
# =============================================================================


def test_result_pattern_enables_explicit_error_handling():
    """Test Result pattern enables explicit error handling without exceptions."""
    # Setup
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)

    error = RuntimeError("Processing failed")

    # Mock pipeline to fail
    with patch("rdetoolkit.modeproc.PipelineFactory.create_invoice_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.side_effect = error
        mock_factory.return_value = mock_pipeline

        # Explicit error handling without try/except
        result = invoice_mode_process_result(index, srcpaths, resource_paths)

        if result.is_success():
            # Process successful result
            _ = result.unwrap()
        else:
            # Handle error explicitly
            error_obj = result.error
            assert error_obj == error
            assert str(error_obj) == "Processing failed"


def test_migration_path_from_exception_to_result():
    """Test smooth migration from exception-based to Result-based code."""
    # Setup
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)

    expected_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test Invoice",
        status="success",
        mode="invoice",
        target="test_target",
    )

    # Mock pipeline execution
    with patch("rdetoolkit.modeproc.PipelineFactory.create_invoice_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = expected_status
        mock_factory.return_value = mock_pipeline

        # Old code still works
        status1 = invoice_mode_process(index, srcpaths, resource_paths)

        # New code uses Result
        result = invoice_mode_process_result(index, srcpaths, resource_paths)
        status2 = result.unwrap()

        # Same result
        assert status1 == status2


def test_result_unwrap_convenience():
    """Test Result type provides convenient unwrap method."""
    # Setup
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)

    expected_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test Invoice",
        status="success",
        mode="invoice",
        target="test_target",
    )

    # Mock pipeline execution
    with patch("rdetoolkit.modeproc.PipelineFactory.create_invoice_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = expected_status
        mock_factory.return_value = mock_pipeline

        # Execute
        result = invoice_mode_process_result(index, srcpaths, resource_paths)

        # Can unwrap directly if success is guaranteed
        status = result.unwrap()
        assert status == expected_status
