"""Test SmartTableEarlyExitProcessor functionality."""

from pathlib import Path
from unittest.mock import Mock, patch
import pytest
import tempfile
import os

from rdetoolkit.processing.processors.smarttable_early_exit import SmartTableEarlyExitProcessor
from rdetoolkit.exceptions import SkipRemainingProcessorsError


class TestSmartTableEarlyExitProcessor:
    """Test suite for SmartTableEarlyExitProcessor functionality."""

    def test_process_not_smarttable_mode(self):
        """Test processing when not in SmartTable mode."""
        processor = SmartTableEarlyExitProcessor()

        # Create mock context
        mock_context = Mock()
        mock_context.is_smarttable_mode = False
        mock_context.resource_paths.rawfiles = (
            Path("/data/inputdata/smarttable_test.xlsx"),
            Path("/data/temp/file.csv"),
        )

        # Should not raise StopIteration when not in SmartTable mode
        processor.process(mock_context)

    def test_process_with_original_smarttable_file_save_enabled(self):
        """Test processing when rawfiles contains original SmartTable file and save_table_file is enabled."""
        processor = SmartTableEarlyExitProcessor()

        # Create mock context with save_table_file enabled
        mock_context = Mock()
        mock_context.is_smarttable_mode = True
        mock_context.resource_paths.rawfiles = (
            Path("/data/inputdata/smarttable_test.xlsx"),
        )
        mock_context.srcpaths.config.smarttable = Mock()
        mock_context.srcpaths.config.smarttable.save_table_file = True

        # Mock system settings to avoid copying during test
        mock_context.srcpaths.config.system.save_raw = False
        mock_context.srcpaths.config.system.save_nonshared_raw = False

        # Should raise SkipRemainingProcessorsError when original SmartTable file is found and save_table_file is True
        with pytest.raises(SkipRemainingProcessorsError) as exc_info:
            processor.process(mock_context)

        assert "SmartTable file processing completed" in str(exc_info.value)

    def test_process_with_original_smarttable_file_save_disabled(self):
        """Test processing when rawfiles contains original SmartTable file but save_table_file is disabled."""
        processor = SmartTableEarlyExitProcessor()

        # Create mock context with save_table_file disabled
        mock_context = Mock()
        mock_context.is_smarttable_mode = True
        mock_context.resource_paths.rawfiles = (
            Path("/data/inputdata/smarttable_test.xlsx"),
        )
        mock_context.srcpaths.config.smarttable = Mock()
        mock_context.srcpaths.config.smarttable.save_table_file = False

        # Should NOT raise StopIteration when save_table_file is False
        processor.process(mock_context)  # Should not raise any exception

    def test_process_with_csv_files_only(self):
        """Test processing when rawfiles contains only CSV files."""
        processor = SmartTableEarlyExitProcessor()

        # Create mock context
        mock_context = Mock()
        mock_context.is_smarttable_mode = True
        mock_context.resource_paths.rawfiles = (
            Path("/data/temp/fsmarttable_test_0000.csv"),
            Path("/data/temp/extracted_file.txt"),
        )

        # Should not raise StopIteration when no original SmartTable file
        processor.process(mock_context)

    def test_process_with_multiple_files_including_smarttable(self):
        """Test processing with multiple files including SmartTable file."""
        processor = SmartTableEarlyExitProcessor()

        # Create mock context with save_table_file enabled
        mock_context = Mock()
        mock_context.is_smarttable_mode = True
        mock_context.resource_paths.rawfiles = (
            Path("/data/inputdata/smarttable_experiment.csv"),
            Path("/data/temp/fsmarttable_test_0000.csv"),
            Path("/data/temp/other_file.txt"),
        )
        mock_context.srcpaths.config.smarttable = Mock()
        mock_context.srcpaths.config.smarttable.save_table_file = True

        # Mock system settings to avoid copying during test
        mock_context.srcpaths.config.system.save_raw = False
        mock_context.srcpaths.config.system.save_nonshared_raw = False

        # Should raise SkipRemainingProcessorsError when original SmartTable file is found
        with pytest.raises(SkipRemainingProcessorsError) as exc_info:
            processor.process(mock_context)

        assert "SmartTable file processing completed" in str(exc_info.value)

    def test_is_original_smarttable_file_true_cases(self):
        """Test identification of original SmartTable files."""
        processor = SmartTableEarlyExitProcessor()

        # Test valid SmartTable files
        true_cases = [
            Path("/data/inputdata/smarttable_test.xlsx"),
            Path("/data/inputdata/smarttable_experiment.csv"),
            Path("/project/data/inputdata/smarttable_data.tsv"),
            Path("/path/to/inputdata/smarttable_sample.XLSX"),  # Case insensitive
        ]

        for test_path in true_cases:
            assert processor._is_original_smarttable_file(test_path) is True

    def test_is_original_smarttable_file_false_cases(self):
        """Test identification of non-SmartTable files."""
        processor = SmartTableEarlyExitProcessor()

        # Test invalid cases
        false_cases = [
            Path("/data/temp/fsmarttable_test_0000.csv"),  # Generated CSV
            Path("/data/raw/smarttable_test.xlsx"),  # Not in inputdata
            Path("/data/inputdata/table_test.xlsx"),  # No smarttable_ prefix
            Path("/data/inputdata/smarttable_test.txt"),  # Unsupported extension
            Path("/data/inputdata/other_file.csv"),  # No smarttable_ prefix
            Path("/data/output/smarttable_test.xlsx"),  # Not in inputdata
        ]

        for test_path in false_cases:
            assert processor._is_original_smarttable_file(test_path) is False

    def test_is_original_smarttable_file_edge_cases(self):
        """Test edge cases for SmartTable file identification."""
        processor = SmartTableEarlyExitProcessor()

        # Test edge cases
        edge_cases = [
            (Path("/data/inputdata/smarttable_.xlsx"), True),  # Empty name part
            (Path("/data/inputdata/smarttable_a.csv"), True),  # Single char name
            (Path("/inputdata/smarttable_test.xlsx"), True),  # Root inputdata
            (Path("/data/inputdata/nested/smarttable_test.xlsx"), True),  # Nested under inputdata
        ]

        for test_path, expected in edge_cases:
            assert processor._is_original_smarttable_file(test_path) is expected

    def test_process_with_tsv_file(self):
        """Test processing with TSV SmartTable file."""
        processor = SmartTableEarlyExitProcessor()

        # Create mock context with save_table_file enabled
        mock_context = Mock()
        mock_context.is_smarttable_mode = True
        mock_context.resource_paths.rawfiles = (
            Path("/data/inputdata/smarttable_data.tsv"),
        )
        mock_context.srcpaths.config.smarttable = Mock()
        mock_context.srcpaths.config.smarttable.save_table_file = True

        # Mock system settings to avoid copying during test
        mock_context.srcpaths.config.system.save_raw = False
        mock_context.srcpaths.config.system.save_nonshared_raw = False

        # Should raise SkipRemainingProcessorsError for TSV files too
        with pytest.raises(SkipRemainingProcessorsError):
            processor.process(mock_context)

    def test_process_with_empty_rawfiles(self):
        """Test processing with empty rawfiles."""
        processor = SmartTableEarlyExitProcessor()

        # Create mock context
        mock_context = Mock()
        mock_context.is_smarttable_mode = True
        mock_context.resource_paths.rawfiles = ()

        # Should not raise StopIteration when rawfiles is empty
        processor.process(mock_context)

    def test_case_insensitive_extension_matching(self):
        """Test that extensions are matched case-insensitively."""
        processor = SmartTableEarlyExitProcessor()

        test_cases = [
            Path("/data/inputdata/smarttable_test.XLSX"),
            Path("/data/inputdata/smarttable_test.Csv"),
            Path("/data/inputdata/smarttable_test.TSV"),
            Path("/data/inputdata/smarttable_test.xlsx"),
            Path("/data/inputdata/smarttable_test.csv"),
            Path("/data/inputdata/smarttable_test.tsv"),
        ]

        for test_path in test_cases:
            assert processor._is_original_smarttable_file(test_path) is True

    def test_process_with_smarttable_config_none(self):
        """Test processing when smarttable config is None."""
        processor = SmartTableEarlyExitProcessor()

        # Create mock context with smarttable config as None
        mock_context = Mock()
        mock_context.is_smarttable_mode = True
        mock_context.resource_paths.rawfiles = (
            Path("/data/inputdata/smarttable_test.xlsx"),
        )
        mock_context.srcpaths.config.smarttable = None

        # Should NOT raise StopIteration when smarttable config is None
        processor.process(mock_context)  # Should not raise any exception

    def test_process_with_smarttable_config_missing_save_table_file(self):
        """Test processing when smarttable config exists but save_table_file attribute is missing."""
        processor = SmartTableEarlyExitProcessor()

        # Create mock context with smarttable config that doesn't have save_table_file
        mock_context = Mock()
        mock_context.is_smarttable_mode = True
        mock_context.resource_paths.rawfiles = (
            Path("/data/inputdata/smarttable_test.xlsx"),
        )
        # Create a mock that doesn't have save_table_file attribute
        mock_smarttable = Mock(spec=[])  # Empty spec means no attributes
        mock_context.srcpaths.config.smarttable = mock_smarttable

        # Should NOT raise SkipRemainingProcessorsError when save_table_file attribute is missing
        processor.process(mock_context)  # Should not raise any exception

    def test_copy_smarttable_file_to_raw(self):
        """Test copying SmartTable file to raw directory."""
        processor = SmartTableEarlyExitProcessor()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create source file
            source_file = temp_path / "inputdata" / "smarttable_test.xlsx"
            source_file.parent.mkdir(parents=True)
            source_file.write_text("test content")

            # Create mock context
            mock_context = Mock()
            mock_context.is_smarttable_mode = True
            mock_context.resource_paths.rawfiles = (source_file,)
            mock_context.srcpaths.config.smarttable = Mock()
            mock_context.srcpaths.config.smarttable.save_table_file = True

            # Configure system settings
            mock_context.srcpaths.config.system.save_raw = True
            mock_context.srcpaths.config.system.save_nonshared_raw = False

            # Set up raw directory path
            raw_dir = temp_path / "raw"
            mock_context.resource_paths.raw = raw_dir
            mock_context.resource_paths.nonshared_raw = None

            # Should raise SkipRemainingProcessorsError and copy file
            with pytest.raises(SkipRemainingProcessorsError):
                processor.process(mock_context)

            # Verify file was copied
            copied_file = raw_dir / "smarttable_test.xlsx"
            assert copied_file.exists()
            assert copied_file.read_text() == "test content"

    def test_copy_smarttable_file_to_nonshared_raw(self):
        """Test copying SmartTable file to nonshared_raw directory."""
        processor = SmartTableEarlyExitProcessor()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create source file
            source_file = temp_path / "inputdata" / "smarttable_data.csv"
            source_file.parent.mkdir(parents=True)
            source_file.write_text("csv,data\n1,test")

            # Create mock context
            mock_context = Mock()
            mock_context.is_smarttable_mode = True
            mock_context.resource_paths.rawfiles = (source_file,)
            mock_context.srcpaths.config.smarttable = Mock()
            mock_context.srcpaths.config.smarttable.save_table_file = True

            # Configure system settings
            mock_context.srcpaths.config.system.save_raw = False
            mock_context.srcpaths.config.system.save_nonshared_raw = True

            # Set up nonshared_raw directory path
            nonshared_raw_dir = temp_path / "nonshared_raw"
            mock_context.resource_paths.raw = None
            mock_context.resource_paths.nonshared_raw = nonshared_raw_dir

            # Should raise SkipRemainingProcessorsError and copy file
            with pytest.raises(SkipRemainingProcessorsError):
                processor.process(mock_context)

            # Verify file was copied
            copied_file = nonshared_raw_dir / "smarttable_data.csv"
            assert copied_file.exists()
            assert copied_file.read_text() == "csv,data\n1,test"

    def test_copy_smarttable_file_to_both_directories(self):
        """Test copying SmartTable file to both raw and nonshared_raw directories."""
        processor = SmartTableEarlyExitProcessor()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create source file
            source_file = temp_path / "inputdata" / "smarttable_experiment.tsv"
            source_file.parent.mkdir(parents=True)
            source_file.write_text("col1\tcol2\nval1\tval2")

            # Create mock context
            mock_context = Mock()
            mock_context.is_smarttable_mode = True
            mock_context.resource_paths.rawfiles = (source_file,)
            mock_context.srcpaths.config.smarttable = Mock()
            mock_context.srcpaths.config.smarttable.save_table_file = True

            # Configure system settings for both directories
            mock_context.srcpaths.config.system.save_raw = True
            mock_context.srcpaths.config.system.save_nonshared_raw = True

            # Set up both directory paths
            raw_dir = temp_path / "raw"
            nonshared_raw_dir = temp_path / "nonshared_raw"
            mock_context.resource_paths.raw = raw_dir
            mock_context.resource_paths.nonshared_raw = nonshared_raw_dir

            # Should raise SkipRemainingProcessorsError and copy file to both
            with pytest.raises(SkipRemainingProcessorsError):
                processor.process(mock_context)

            # Verify file was copied to both directories
            raw_file = raw_dir / "smarttable_experiment.tsv"
            nonshared_raw_file = nonshared_raw_dir / "smarttable_experiment.tsv"

            assert raw_file.exists()
            assert nonshared_raw_file.exists()
            assert raw_file.read_text() == "col1\tcol2\nval1\tval2"
            assert nonshared_raw_file.read_text() == "col1\tcol2\nval1\tval2"
