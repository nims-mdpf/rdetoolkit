"""Unit tests for Result-based mode processing functions.

Tests for invoice_mode_process_result and backward compatibility.
"""

# Equivalence Partitioning Table
# | API | Input/State Partition | Rationale | Expected Outcome | Test ID |
# | --- | --- | --- | --- | --- |
# | `rdetoolkit.modeproc.rdeformat_mode_process` | failed status with exception_object | propagate failed status with original exception | raises original exception | TC-EP-001 |
# | `rdetoolkit.modeproc.rdeformat_mode_process` | failed status without exception_object | failed status needs fallback error | raises RuntimeError with message | TC-EP-002 |
# | `rdetoolkit.modeproc.multifile_mode_process` | failed status with exception_object | propagate failed status with original exception | raises original exception | TC-EP-003 |
# | `rdetoolkit.modeproc.multifile_mode_process` | failed status without exception_object | failed status needs fallback error | raises RuntimeError with message | TC-EP-004 |
# | `rdetoolkit.modeproc.excel_invoice_mode_process` | failed status with exception_object | propagate failed status with original exception | raises original exception | TC-EP-005 |
# | `rdetoolkit.modeproc.excel_invoice_mode_process` | failed status without exception_object | failed status needs fallback error | raises RuntimeError with message | TC-EP-006 |
# | `rdetoolkit.modeproc.invoice_mode_process` | failed status with exception_object | propagate failed status with original exception | raises original exception | TC-EP-007 |
# | `rdetoolkit.modeproc.invoice_mode_process` | failed status without exception_object | failed status needs fallback error | raises RuntimeError with message | TC-EP-008 |
# | `rdetoolkit.modeproc.smarttable_invoice_mode_process` | failed status with exception_object | propagate failed status with original exception | raises original exception | TC-EP-009 |
# | `rdetoolkit.modeproc.smarttable_invoice_mode_process` | failed status without exception_object | failed status needs fallback error | raises RuntimeError with message | TC-EP-010 |
#
# Boundary Value Table
# | API | Boundary | Rationale | Expected Outcome | Test ID |
# | --- | --- | --- | --- | --- |
# | `rdetoolkit.modeproc.rdeformat_mode_process` | `status.status="failed"` | boundary between success and failure statuses | raises RuntimeError with message | TC-EP-002 |
# | `rdetoolkit.modeproc.multifile_mode_process` | `status.status="failed"` | boundary between success and failure statuses | raises RuntimeError with message | TC-EP-004 |
# | `rdetoolkit.modeproc.excel_invoice_mode_process` | `status.status="failed"` | boundary between success and failure statuses | raises RuntimeError with message | TC-EP-006 |
# | `rdetoolkit.modeproc.invoice_mode_process` | `status.status="failed"` | boundary between success and failure statuses | raises RuntimeError with message | TC-EP-008 |
# | `rdetoolkit.modeproc.smarttable_invoice_mode_process` | `status.status="failed"` | boundary between success and failure statuses | raises RuntimeError with message | TC-EP-010 |
#
# Test commands:
# pytest -q --maxfail=1 --cov=rdetoolkit --cov-branch --cov-report=term-missing --cov-report=html tests/test_modeproc_result.py
# tox -e py39

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from pathlib import Path

from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
from rdetoolkit.models.result import WorkflowExecutionStatus
from rdetoolkit.result import Success, Failure
from rdetoolkit.modeproc import (
    invoice_mode_process_result,
    invoice_mode_process,
    rdeformat_mode_process_result,
    rdeformat_mode_process,
    multifile_mode_process_result,
    multifile_mode_process,
    excel_invoice_mode_process_result,
    excel_invoice_mode_process,
    smarttable_invoice_mode_process_result,
    smarttable_invoice_mode_process,
)


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


def test_invoice_mode_process_result_failure_on_failed_status_with_exception():
    """Test invoice_mode_process_result returns Failure when status.status == 'failed' with exception_object."""
    # Setup
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)

    original_error = ValueError("Validation failed in pipeline")
    failed_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test Invoice",
        status="failed",
        mode="invoice",
        error_code=500,
        error_message="Validation error occurred",
        target="test_target",
    )
    failed_status.exception_object = original_error

    # Mock pipeline to return failed status
    with patch("rdetoolkit.modeproc.PipelineFactory.create_invoice_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = failed_status
        mock_factory.return_value = mock_pipeline

        # Execute
        result = invoice_mode_process_result(index, srcpaths, resource_paths)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == original_error
        assert str(result.error) == "Validation failed in pipeline"


def test_invoice_mode_process_result_failure_on_failed_status_without_exception():
    """Test invoice_mode_process_result returns Failure when status.status == 'failed' without exception_object."""
    # Setup
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)

    failed_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test Invoice",
        status="failed",
        mode="invoice",
        error_code=500,
        error_message="Custom error message",
        target="test_target",
    )

    # Mock pipeline to return failed status without exception_object
    with patch("rdetoolkit.modeproc.PipelineFactory.create_invoice_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = failed_status
        mock_factory.return_value = mock_pipeline

        # Execute
        result = invoice_mode_process_result(index, srcpaths, resource_paths)

        # Assert
        assert isinstance(result, Failure)
        assert isinstance(result.error, RuntimeError)
        assert "Pipeline execution failed: Custom error message" in str(result.error)


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


def test_invoice_mode_process_failed_status_with_exception_object__tc_ep_007():
    """Test invoice_mode_process raises exception_object on failed status."""
    # Given: pipeline returns failed status with exception_object
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)
    original_error = ValueError("Invoice failed in pipeline")

    failed_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test Invoice",
        status="failed",
        mode="invoice",
        error_message="Invoice failed in pipeline",
        target="test_target",
        exception_object=original_error,
    )

    with patch("rdetoolkit.modeproc.PipelineFactory.create_invoice_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = failed_status
        mock_factory.return_value = mock_pipeline

        # When: calling invoice_mode_process
        # Then: it raises the original exception
        with pytest.raises(ValueError, match="Invoice failed in pipeline"):
            invoice_mode_process(index, srcpaths, resource_paths)


def test_invoice_mode_process_failed_status_without_exception_object__tc_ep_008():
    """Test invoice_mode_process raises RuntimeError on failed status without exception_object."""
    # Given: pipeline returns failed status without exception_object
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)

    failed_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test Invoice",
        status="failed",
        mode="invoice",
        error_message="Invoice failed in pipeline",
        target="test_target",
    )

    with patch("rdetoolkit.modeproc.PipelineFactory.create_invoice_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = failed_status
        mock_factory.return_value = mock_pipeline

        # When: calling invoice_mode_process
        # Then: it raises a RuntimeError with the pipeline error message
        with pytest.raises(RuntimeError, match="Pipeline execution failed: Invoice failed in pipeline"):
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


# =============================================================================
# rdeformat_mode_process_result Tests
# =============================================================================


def test_rdeformat_mode_process_result_success():
    """Test rdeformat_mode_process_result returns Success on successful execution."""
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)

    expected_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test RDEFormat",
        status="success",
        mode="rdeformat",
        target="test_target",
    )

    with patch("rdetoolkit.modeproc.PipelineFactory.create_rdeformat_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = expected_status
        mock_factory.return_value = mock_pipeline

        result = rdeformat_mode_process_result(index, srcpaths, resource_paths)

        assert isinstance(result, Success)
        assert result.unwrap() == expected_status


def test_rdeformat_mode_process_result_failure():
    """Test rdeformat_mode_process_result returns Failure on exception."""
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)
    error = RuntimeError("RDEFormat pipeline failed")

    with patch("rdetoolkit.modeproc.PipelineFactory.create_rdeformat_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.side_effect = error
        mock_factory.return_value = mock_pipeline

        result = rdeformat_mode_process_result(index, srcpaths, resource_paths)

        assert isinstance(result, Failure)
        assert result.error == error


def test_rdeformat_mode_process_result_failure_on_failed_status():
    """Test rdeformat_mode_process_result returns Failure when status.status == 'failed'."""
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)

    failed_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test RDEFormat",
        status="failed",
        mode="rdeformat",
        error_message="RDEFormat processing failed",
        target="test_target",
    )

    with patch("rdetoolkit.modeproc.PipelineFactory.create_rdeformat_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = failed_status
        mock_factory.return_value = mock_pipeline

        result = rdeformat_mode_process_result(index, srcpaths, resource_paths)

        assert isinstance(result, Failure)
        assert isinstance(result.error, RuntimeError)
        assert "RDEFormat processing failed" in str(result.error)


def test_rdeformat_mode_process_backward_compatibility():
    """Test rdeformat_mode_process maintains backward compatibility."""
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)
    error = RuntimeError("Pipeline failed")

    with patch("rdetoolkit.modeproc.PipelineFactory.create_rdeformat_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.side_effect = error
        mock_factory.return_value = mock_pipeline

        with pytest.raises(RuntimeError, match="Pipeline failed"):
            rdeformat_mode_process(index, srcpaths, resource_paths)


def test_rdeformat_mode_process_failed_status_with_exception_object__tc_ep_001():
    """Test rdeformat_mode_process raises exception_object on failed status."""
    # Given: pipeline returns failed status with exception_object
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)
    original_error = RuntimeError("RDEFormat failed in pipeline")

    failed_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test RDEFormat",
        status="failed",
        mode="rdeformat",
        error_message="RDEFormat failed in pipeline",
        target="test_target",
        exception_object=original_error,
    )

    with patch("rdetoolkit.modeproc.PipelineFactory.create_rdeformat_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = failed_status
        mock_factory.return_value = mock_pipeline

        # When: calling rdeformat_mode_process
        # Then: it raises the original exception
        with pytest.raises(RuntimeError, match="RDEFormat failed in pipeline"):
            rdeformat_mode_process(index, srcpaths, resource_paths)


def test_rdeformat_mode_process_failed_status_without_exception_object__tc_ep_002():
    """Test rdeformat_mode_process raises RuntimeError on failed status without exception_object."""
    # Given: pipeline returns failed status without exception_object
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)

    failed_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test RDEFormat",
        status="failed",
        mode="rdeformat",
        error_message="RDEFormat failed in pipeline",
        target="test_target",
    )

    with patch("rdetoolkit.modeproc.PipelineFactory.create_rdeformat_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = failed_status
        mock_factory.return_value = mock_pipeline

        # When: calling rdeformat_mode_process
        # Then: it raises a RuntimeError with the pipeline error message
        with pytest.raises(RuntimeError, match="Pipeline execution failed: RDEFormat failed in pipeline"):
            rdeformat_mode_process(index, srcpaths, resource_paths)


# =============================================================================
# multifile_mode_process_result Tests
# =============================================================================


def test_multifile_mode_process_result_success():
    """Test multifile_mode_process_result returns Success on successful execution."""
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)

    expected_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test MultiFile",
        status="success",
        mode="MultiDataTile",
        target="test_target",
    )

    with patch("rdetoolkit.modeproc.PipelineFactory.create_multifile_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = expected_status
        mock_factory.return_value = mock_pipeline

        result = multifile_mode_process_result(index, srcpaths, resource_paths)

        assert isinstance(result, Success)
        assert result.unwrap() == expected_status


def test_multifile_mode_process_result_failure():
    """Test multifile_mode_process_result returns Failure on exception."""
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)
    error = ValueError("MultiFile validation failed")

    with patch("rdetoolkit.modeproc.PipelineFactory.create_multifile_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.side_effect = error
        mock_factory.return_value = mock_pipeline

        result = multifile_mode_process_result(index, srcpaths, resource_paths)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ValueError)


def test_multifile_mode_process_result_failure_on_failed_status():
    """Test multifile_mode_process_result returns Failure when status.status == 'failed'."""
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)

    failed_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test MultiFile",
        status="failed",
        mode="MultiDataTile",
        error_message="MultiFile validation failed",
        target="test_target",
    )

    with patch("rdetoolkit.modeproc.PipelineFactory.create_multifile_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = failed_status
        mock_factory.return_value = mock_pipeline

        result = multifile_mode_process_result(index, srcpaths, resource_paths)

        assert isinstance(result, Failure)
        assert isinstance(result.error, RuntimeError)
        assert "MultiFile validation failed" in str(result.error)


def test_multifile_mode_process_backward_compatibility():
    """Test multifile_mode_process maintains backward compatibility."""
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)
    error = ValueError("Validation failed")

    with patch("rdetoolkit.modeproc.PipelineFactory.create_multifile_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.side_effect = error
        mock_factory.return_value = mock_pipeline

        with pytest.raises(ValueError, match="Validation failed"):
            multifile_mode_process(index, srcpaths, resource_paths)


def test_multifile_mode_process_failed_status_with_exception_object__tc_ep_003():
    """Test multifile_mode_process raises exception_object on failed status."""
    # Given: pipeline returns failed status with exception_object
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)
    original_error = ValueError("MultiFile failed in pipeline")

    failed_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test MultiFile",
        status="failed",
        mode="MultiDataTile",
        error_message="MultiFile failed in pipeline",
        target="test_target",
        exception_object=original_error,
    )

    with patch("rdetoolkit.modeproc.PipelineFactory.create_multifile_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = failed_status
        mock_factory.return_value = mock_pipeline

        # When: calling multifile_mode_process
        # Then: it raises the original exception
        with pytest.raises(ValueError, match="MultiFile failed in pipeline"):
            multifile_mode_process(index, srcpaths, resource_paths)


def test_multifile_mode_process_failed_status_without_exception_object__tc_ep_004():
    """Test multifile_mode_process raises RuntimeError on failed status without exception_object."""
    # Given: pipeline returns failed status without exception_object
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)

    failed_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test MultiFile",
        status="failed",
        mode="MultiDataTile",
        error_message="MultiFile failed in pipeline",
        target="test_target",
    )

    with patch("rdetoolkit.modeproc.PipelineFactory.create_multifile_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = failed_status
        mock_factory.return_value = mock_pipeline

        # When: calling multifile_mode_process
        # Then: it raises a RuntimeError with the pipeline error message
        with pytest.raises(RuntimeError, match="Pipeline execution failed: MultiFile failed in pipeline"):
            multifile_mode_process(index, srcpaths, resource_paths)


# =============================================================================
# excel_invoice_mode_process_result Tests
# =============================================================================


def test_excel_invoice_mode_process_result_success():
    """Test excel_invoice_mode_process_result returns Success on successful execution."""
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)
    excel_file = Path("/tmp/test_excel_invoice.xlsx")  # noqa: S108
    idx = 0

    expected_status = WorkflowExecutionStatus(
        run_id=str(idx),
        title="Test ExcelInvoice",
        status="success",
        mode="Excelinvoice",
        target="test_target",
    )

    with patch("rdetoolkit.modeproc.PipelineFactory.create_excel_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = expected_status
        mock_factory.return_value = mock_pipeline

        result = excel_invoice_mode_process_result(srcpaths, resource_paths, excel_file, idx)

        assert isinstance(result, Success)
        assert result.unwrap() == expected_status


def test_excel_invoice_mode_process_result_failure():
    """Test excel_invoice_mode_process_result returns Failure on exception."""
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)
    excel_file = Path("/tmp/test_excel_invoice.xlsx")  # noqa: S108
    idx = 0
    error = RuntimeError("Excel parsing failed")

    with patch("rdetoolkit.modeproc.PipelineFactory.create_excel_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.side_effect = error
        mock_factory.return_value = mock_pipeline

        result = excel_invoice_mode_process_result(srcpaths, resource_paths, excel_file, idx)

        assert isinstance(result, Failure)
        assert result.error == error


def test_excel_invoice_mode_process_result_failure_on_failed_status():
    """Test excel_invoice_mode_process_result returns Failure when status.status == 'failed'."""
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)
    excel_file = Path("/tmp/test_excel_invoice.xlsx")  # noqa: S108
    idx = 0

    failed_status = WorkflowExecutionStatus(
        run_id=str(idx),
        title="Test ExcelInvoice",
        status="failed",
        mode="Excelinvoice",
        error_message="Excel parsing error",
        target="test_target",
    )

    with patch("rdetoolkit.modeproc.PipelineFactory.create_excel_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = failed_status
        mock_factory.return_value = mock_pipeline

        result = excel_invoice_mode_process_result(srcpaths, resource_paths, excel_file, idx)

        assert isinstance(result, Failure)
        assert isinstance(result.error, RuntimeError)
        assert "Excel parsing error" in str(result.error)


def test_excel_invoice_mode_process_backward_compatibility():
    """Test excel_invoice_mode_process maintains backward compatibility."""
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)
    excel_file = Path("/tmp/test_excel_invoice.xlsx")  # noqa: S108
    idx = 0
    error = RuntimeError("Excel parsing failed")

    with patch("rdetoolkit.modeproc.PipelineFactory.create_excel_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.side_effect = error
        mock_factory.return_value = mock_pipeline

        with pytest.raises(RuntimeError, match="Excel parsing failed"):
            excel_invoice_mode_process(srcpaths, resource_paths, excel_file, idx)


def test_excel_invoice_mode_process_failed_status_with_exception_object__tc_ep_005():
    """Test excel_invoice_mode_process raises exception_object on failed status."""
    # Given: pipeline returns failed status with exception_object
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)
    excel_file = Path("/tmp/test_excel_invoice.xlsx")  # noqa: S108
    idx = 0
    original_error = RuntimeError("Excel invoice failed in pipeline")

    failed_status = WorkflowExecutionStatus(
        run_id=str(idx),
        title="Test ExcelInvoice",
        status="failed",
        mode="Excelinvoice",
        error_message="Excel invoice failed in pipeline",
        target="test_target",
        exception_object=original_error,
    )

    with patch("rdetoolkit.modeproc.PipelineFactory.create_excel_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = failed_status
        mock_factory.return_value = mock_pipeline

        # When: calling excel_invoice_mode_process
        # Then: it raises the original exception
        with pytest.raises(RuntimeError, match="Excel invoice failed in pipeline"):
            excel_invoice_mode_process(srcpaths, resource_paths, excel_file, idx)


def test_excel_invoice_mode_process_failed_status_without_exception_object__tc_ep_006():
    """Test excel_invoice_mode_process raises RuntimeError on failed status without exception_object."""
    # Given: pipeline returns failed status without exception_object
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)
    excel_file = Path("/tmp/test_excel_invoice.xlsx")  # noqa: S108
    idx = 0

    failed_status = WorkflowExecutionStatus(
        run_id=str(idx),
        title="Test ExcelInvoice",
        status="failed",
        mode="Excelinvoice",
        error_message="Excel invoice failed in pipeline",
        target="test_target",
    )

    with patch("rdetoolkit.modeproc.PipelineFactory.create_excel_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = failed_status
        mock_factory.return_value = mock_pipeline

        # When: calling excel_invoice_mode_process
        # Then: it raises a RuntimeError with the pipeline error message
        with pytest.raises(RuntimeError, match="Pipeline execution failed: Excel invoice failed in pipeline"):
            excel_invoice_mode_process(srcpaths, resource_paths, excel_file, idx)


# =============================================================================
# smarttable_invoice_mode_process_result Tests
# =============================================================================


def test_smarttable_invoice_mode_process_result_success():
    """Test smarttable_invoice_mode_process_result returns Success on successful execution."""
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)
    smarttable_file = Path("/tmp/test_smarttable.xlsx")  # noqa: S108

    expected_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test SmartTable",
        status="success",
        mode="SmartTableInvoice",
        target="test_target",
    )

    with patch("rdetoolkit.modeproc.PipelineFactory.create_smarttable_invoice_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = expected_status
        mock_factory.return_value = mock_pipeline

        result = smarttable_invoice_mode_process_result(index, srcpaths, resource_paths, smarttable_file)

        assert isinstance(result, Success)
        assert result.unwrap() == expected_status


def test_smarttable_invoice_mode_process_result_failure():
    """Test smarttable_invoice_mode_process_result returns Failure on exception."""
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)
    smarttable_file = Path("/tmp/test_smarttable.xlsx")  # noqa: S108
    error = ValueError("SmartTable validation failed")

    with patch("rdetoolkit.modeproc.PipelineFactory.create_smarttable_invoice_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.side_effect = error
        mock_factory.return_value = mock_pipeline

        result = smarttable_invoice_mode_process_result(index, srcpaths, resource_paths, smarttable_file)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ValueError)


def test_smarttable_invoice_mode_process_result_failure_on_failed_status():
    """Test smarttable_invoice_mode_process_result returns Failure when status.status == 'failed'."""
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)
    smarttable_file = Path("/tmp/test_smarttable.xlsx")  # noqa: S108

    failed_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test SmartTable",
        status="failed",
        mode="SmartTableInvoice",
        error_message="SmartTable processing error",
        target="test_target",
    )

    with patch("rdetoolkit.modeproc.PipelineFactory.create_smarttable_invoice_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = failed_status
        mock_factory.return_value = mock_pipeline

        result = smarttable_invoice_mode_process_result(index, srcpaths, resource_paths, smarttable_file)

        assert isinstance(result, Failure)
        assert isinstance(result.error, RuntimeError)
        assert "SmartTable processing error" in str(result.error)


def test_smarttable_invoice_mode_process_backward_compatibility():
    """Test smarttable_invoice_mode_process maintains backward compatibility."""
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)
    smarttable_file = Path("/tmp/test_smarttable.xlsx")  # noqa: S108
    error = ValueError("SmartTable validation failed")

    with patch("rdetoolkit.modeproc.PipelineFactory.create_smarttable_invoice_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.side_effect = error
        mock_factory.return_value = mock_pipeline

        with pytest.raises(ValueError, match="SmartTable validation failed"):
            smarttable_invoice_mode_process(index, srcpaths, resource_paths, smarttable_file)


def test_smarttable_invoice_mode_process_failed_status_with_exception_object__tc_ep_009():
    """Test smarttable_invoice_mode_process raises exception_object on failed status."""
    # Given: pipeline returns failed status with exception_object
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)
    smarttable_file = Path("/tmp/test_smarttable.xlsx")  # noqa: S108
    original_error = RuntimeError("SmartTable failed in pipeline")

    failed_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test SmartTable",
        status="failed",
        mode="SmartTableInvoice",
        error_message="SmartTable failed in pipeline",
        target="test_target",
        exception_object=original_error,
    )

    with patch("rdetoolkit.modeproc.PipelineFactory.create_smarttable_invoice_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = failed_status
        mock_factory.return_value = mock_pipeline

        # When: calling smarttable_invoice_mode_process
        # Then: it raises the original exception
        with pytest.raises(RuntimeError, match="SmartTable failed in pipeline"):
            smarttable_invoice_mode_process(index, srcpaths, resource_paths, smarttable_file)


def test_smarttable_invoice_mode_process_failed_status_without_exception_object__tc_ep_010():
    """Test smarttable_invoice_mode_process raises RuntimeError on failed status without exception_object."""
    # Given: pipeline returns failed status without exception_object
    index = "0"
    srcpaths = Mock(spec=RdeInputDirPaths)
    resource_paths = Mock(spec=RdeOutputResourcePath)
    smarttable_file = Path("/tmp/test_smarttable.xlsx")  # noqa: S108

    failed_status = WorkflowExecutionStatus(
        run_id=index,
        title="Test SmartTable",
        status="failed",
        mode="SmartTableInvoice",
        error_message="SmartTable failed in pipeline",
        target="test_target",
    )

    with patch("rdetoolkit.modeproc.PipelineFactory.create_smarttable_invoice_pipeline") as mock_factory:
        mock_pipeline = Mock()
        mock_pipeline.execute.return_value = failed_status
        mock_factory.return_value = mock_pipeline

        # When: calling smarttable_invoice_mode_process
        # Then: it raises a RuntimeError with the pipeline error message
        with pytest.raises(RuntimeError, match="Pipeline execution failed: SmartTable failed in pipeline"):
            smarttable_invoice_mode_process(index, srcpaths, resource_paths, smarttable_file)
