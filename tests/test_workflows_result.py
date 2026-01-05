"""Unit tests for Result-based workflow functions.

Tests for check_files_result and backward compatibility with check_files.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.models.config import Config
from rdetoolkit.models.rde2types import RdeInputDirPaths
from rdetoolkit.result import Success, Failure
from rdetoolkit.workflows import check_files_result, check_files


# =============================================================================
# check_files_result Tests
# =============================================================================


def test_check_files_result_success_invoice_mode():
    """Test check_files_result returns Success for valid invoice mode."""
    srcpaths = Mock(spec=RdeInputDirPaths)
    srcpaths.inputdata = Path("/data/inputdata")

    # Mock the input checker to return invoice mode result
    mock_checker = Mock()
    mock_checker.checker_type = "invoice"
    mock_checker.parse.return_value = ([("file1.txt",)], None)

    with (
        patch("rdetoolkit.rde2util.StorageDir.get_specific_outputdir") as mock_storage,
        patch("rdetoolkit.modeproc.selected_input_checker", return_value=mock_checker),
    ):
        mock_storage.return_value = Path("/data/temp")

        result = check_files_result(srcpaths, mode="invoice")

        assert isinstance(result, Success)
        rawfiles, excel_invoice, smarttable = result.unwrap()
        assert rawfiles == [("file1.txt",)]
        assert excel_invoice is None
        assert smarttable is None


def test_check_files_result_success_excel_invoice_mode():
    """Test check_files_result returns Success for excel invoice mode."""
    srcpaths = Mock(spec=RdeInputDirPaths)
    srcpaths.inputdata = Path("/data/inputdata")

    # Mock the input checker to return excel invoice mode result
    mock_checker = Mock()
    mock_checker.checker_type = "excel_invoice"
    excel_file = Path("/data/inputdata/dataset_excel_invoice.xlsx")
    mock_checker.parse.return_value = ([("file1.txt",)], excel_file)

    with (
        patch("rdetoolkit.rde2util.StorageDir.get_specific_outputdir") as mock_storage,
        patch("rdetoolkit.modeproc.selected_input_checker", return_value=mock_checker),
    ):
        mock_storage.return_value = Path("/data/temp")

        result = check_files_result(srcpaths, mode="excelinvoice")

        assert isinstance(result, Success)
        rawfiles, excel_invoice, smarttable = result.unwrap()
        assert rawfiles == [("file1.txt",)]
        assert excel_invoice == excel_file
        assert smarttable is None


def test_check_files_result_success_smarttable_mode():
    """Test check_files_result returns Success for smarttable mode."""
    srcpaths = Mock(spec=RdeInputDirPaths)
    srcpaths.inputdata = Path("/data/inputdata")

    # Mock the input checker to return smarttable mode result
    mock_checker = Mock()
    mock_checker.checker_type = "smarttable"
    smarttable_file = Path("/data/inputdata/smarttable.csv")
    mock_checker.parse.return_value = ([("file1.txt",)], smarttable_file)

    with (
        patch("rdetoolkit.rde2util.StorageDir.get_specific_outputdir") as mock_storage,
        patch("rdetoolkit.modeproc.selected_input_checker", return_value=mock_checker),
    ):
        mock_storage.return_value = Path("/data/temp")

        result = check_files_result(srcpaths, mode="smarttable")

        assert isinstance(result, Success)
        rawfiles, excel_invoice, smarttable = result.unwrap()
        assert rawfiles == [("file1.txt",)]
        assert excel_invoice is None
        assert smarttable == smarttable_file


def test_check_files_result_failure_structured_error():
    """Test check_files_result returns Failure when StructuredError is raised."""
    srcpaths = Mock(spec=RdeInputDirPaths)
    srcpaths.inputdata = Path("/data/inputdata")

    error = StructuredError("File validation failed", 101)

    with (
        patch("rdetoolkit.rde2util.StorageDir.get_specific_outputdir") as mock_storage,
        patch("rdetoolkit.modeproc.selected_input_checker") as mock_selected,
    ):
        mock_storage.return_value = Path("/data/temp")
        mock_selected.side_effect = error

        result = check_files_result(srcpaths, mode="invoice")

        assert isinstance(result, Failure)
        assert result.error == error
        assert result.error.emsg == "File validation failed"
        assert result.error.ecode == 101


def test_check_files_result_failure_unexpected_exception():
    """Test check_files_result wraps unexpected exceptions in StructuredError."""
    srcpaths = Mock(spec=RdeInputDirPaths)
    srcpaths.inputdata = Path("/data/inputdata")

    with (
        patch("rdetoolkit.rde2util.StorageDir.get_specific_outputdir") as mock_storage,
        patch("rdetoolkit.modeproc.selected_input_checker") as mock_selected,
    ):
        mock_storage.return_value = Path("/data/temp")
        mock_selected.side_effect = RuntimeError("Unexpected error")

        result = check_files_result(srcpaths, mode="invoice")

        assert isinstance(result, Failure)
        assert isinstance(result.error, StructuredError)
        assert "Unexpected error in check_files" in result.error.emsg
        assert result.error.ecode == 999


def test_check_files_result_with_none_mode():
    """Test check_files_result handles None mode correctly."""
    srcpaths = Mock(spec=RdeInputDirPaths)
    srcpaths.inputdata = Path("/data/inputdata")

    mock_checker = Mock()
    mock_checker.checker_type = "invoice"
    mock_checker.parse.return_value = ([("file1.txt",)], None)

    with (
        patch("rdetoolkit.rde2util.StorageDir.get_specific_outputdir") as mock_storage,
        patch("rdetoolkit.modeproc.selected_input_checker", return_value=mock_checker) as mock_selected,
    ):
        mock_storage.return_value = Path("/data/temp")

        result = check_files_result(srcpaths, mode=None)

        assert isinstance(result, Success)
        # Verify that mode was converted to empty string
        call_args = mock_selected.call_args
        assert call_args[0][2] == ""  # mode argument


def test_check_files_result_with_config():
    """Test check_files_result passes config to input checker."""
    srcpaths = Mock(spec=RdeInputDirPaths)
    srcpaths.inputdata = Path("/data/inputdata")
    config = Mock(spec=Config)

    mock_checker = Mock()
    mock_checker.checker_type = "invoice"
    mock_checker.parse.return_value = ([("file1.txt",)], None)

    with (
        patch("rdetoolkit.rde2util.StorageDir.get_specific_outputdir") as mock_storage,
        patch("rdetoolkit.modeproc.selected_input_checker", return_value=mock_checker) as mock_selected,
    ):
        mock_storage.return_value = Path("/data/temp")

        result = check_files_result(srcpaths, mode="invoice", config=config)

        assert isinstance(result, Success)
        # Verify config was passed
        call_args = mock_selected.call_args
        assert call_args[0][3] == config  # config argument


# =============================================================================
# Backward Compatibility Tests
# =============================================================================


def test_check_files_backward_compatibility_success():
    """Test check_files maintains backward compatibility with successful case."""
    srcpaths = Mock(spec=RdeInputDirPaths)
    srcpaths.inputdata = Path("/data/inputdata")

    mock_checker = Mock()
    mock_checker.checker_type = "invoice"
    mock_checker.parse.return_value = ([("file1.txt",)], None)

    with (
        patch("rdetoolkit.rde2util.StorageDir.get_specific_outputdir") as mock_storage,
        patch("rdetoolkit.modeproc.selected_input_checker", return_value=mock_checker),
    ):
        mock_storage.return_value = Path("/data/temp")

        # Should return tuple, not Result
        rawfiles, excel_invoice, smarttable = check_files(srcpaths, mode="invoice")

        assert rawfiles == [("file1.txt",)]
        assert excel_invoice is None
        assert smarttable is None


def test_check_files_backward_compatibility_raises_exception():
    """Test check_files raises StructuredError for backward compatibility."""
    srcpaths = Mock(spec=RdeInputDirPaths)
    srcpaths.inputdata = Path("/data/inputdata")

    error = StructuredError("File validation failed", 101)

    with (
        patch("rdetoolkit.rde2util.StorageDir.get_specific_outputdir") as mock_storage,
        patch("rdetoolkit.modeproc.selected_input_checker") as mock_selected,
    ):
        mock_storage.return_value = Path("/data/temp")
        mock_selected.side_effect = error

        # Should raise exception, not return Result
        with pytest.raises(StructuredError, match="File validation failed"):
            check_files(srcpaths, mode="invoice")


def test_check_files_delegates_to_check_files_result():
    """Test check_files correctly delegates to check_files_result."""
    srcpaths = Mock(spec=RdeInputDirPaths)
    srcpaths.inputdata = Path("/data/inputdata")
    config = Mock(spec=Config)

    mock_checker = Mock()
    mock_checker.checker_type = "invoice"
    mock_checker.parse.return_value = ([("file1.txt",)], None)

    with (
        patch("rdetoolkit.rde2util.StorageDir.get_specific_outputdir") as mock_storage,
        patch("rdetoolkit.modeproc.selected_input_checker", return_value=mock_checker),
        patch("rdetoolkit.workflows.check_files_result") as mock_result_fn,
    ):
        mock_storage.return_value = Path("/data/temp")
        mock_result_fn.return_value = Success(([("file1.txt",)], None, None))

        check_files(srcpaths, mode="invoice", config=config)

        # Verify check_files_result was called with correct args
        mock_result_fn.assert_called_once_with(srcpaths, mode="invoice", config=config)


# =============================================================================
# Integration Tests
# =============================================================================


def test_result_pattern_enables_explicit_error_handling():
    """Test Result pattern enables explicit error handling without exceptions."""
    srcpaths = Mock(spec=RdeInputDirPaths)
    srcpaths.inputdata = Path("/data/inputdata")

    error = StructuredError("Validation error", 404)

    with (
        patch("rdetoolkit.rde2util.StorageDir.get_specific_outputdir") as mock_storage,
        patch("rdetoolkit.modeproc.selected_input_checker") as mock_selected,
    ):
        mock_storage.return_value = Path("/data/temp")
        mock_selected.side_effect = error

        # Explicit error handling without try/except
        result = check_files_result(srcpaths, mode="invoice")

        if result.is_success():
            rawfiles, excel, smarttable = result.unwrap()
            # Process files
        else:
            # Handle error explicitly
            error_obj = result.error
            assert error_obj.emsg == "Validation error"
            assert error_obj.ecode == 404


def test_migration_path_from_exception_to_result():
    """Test smooth migration from exception-based to Result-based code."""
    srcpaths = Mock(spec=RdeInputDirPaths)
    srcpaths.inputdata = Path("/data/inputdata")

    mock_checker = Mock()
    mock_checker.checker_type = "invoice"
    mock_checker.parse.return_value = ([("file1.txt",)], None)

    with (
        patch("rdetoolkit.rde2util.StorageDir.get_specific_outputdir") as mock_storage,
        patch("rdetoolkit.modeproc.selected_input_checker", return_value=mock_checker),
    ):
        mock_storage.return_value = Path("/data/temp")

        # Old code still works
        rawfiles1, _, _ = check_files(srcpaths, mode="invoice")

        # New code uses Result
        result = check_files_result(srcpaths, mode="invoice")
        rawfiles2, _, _ = result.unwrap()

        # Same result
        assert rawfiles1 == rawfiles2
