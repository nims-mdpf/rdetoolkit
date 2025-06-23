"""Test SmartTableFileCopier functionality."""

from pathlib import Path
from unittest.mock import Mock, patch

from rdetoolkit.processing.processors.files import SmartTableFileCopier


class TestSmartTableFileCopier:
    """Test suite for SmartTableFileCopier functionality."""

    def test_is_smarttable_generated_csv_true_cases(self):
        """Test identification of SmartTable generated CSV files."""
        copier = SmartTableFileCopier()

        # Test valid SmartTable CSV patterns
        test_cases = [
            Path("/data/temp/fsmarttable_test_0000.csv"),
            Path("/temp/fsmarttable_experiment_0001.csv"),
            Path("/output/temp/fsmarttable_data_0002.csv"),
        ]

        for test_path in test_cases:
            assert copier._is_smarttable_generated_csv(test_path) is True

    def test_is_smarttable_generated_csv_false_cases(self):
        """Test identification of non-SmartTable files."""
        copier = SmartTableFileCopier()

        # Test invalid patterns
        test_cases = [
            Path("/data/regular_file.csv"),  # No 'f' prefix
            Path("/data/temp/smarttable_test.csv"),  # No 'f' prefix
            Path("/data/temp/fsmarttable_test.txt"),  # Not .csv
            Path("/data/fsmarttable_test_0000.csv"),  # Not in temp directory
            Path("/data/temp/other_file.csv"),  # Different naming pattern
            Path("/data/temp/fother_pattern_0000.csv"),  # Doesn't start with 'fsmarttable'
        ]

        for test_path in test_cases:
            assert copier._is_smarttable_generated_csv(test_path) is False

    def test_filter_smarttable_csvs(self):
        """Test filtering of SmartTable CSV files."""
        copier = SmartTableFileCopier()

        source_files = (
            Path("/data/temp/fsmarttable_test_0000.csv"),  # Should be filtered out
            Path("/data/temp/extracted_file.txt"),  # Should be kept
            Path("/data/temp/fsmarttable_test_0001.csv"),  # Should be filtered out
            Path("/data/raw/regular_file.csv"),  # Should be kept (not in temp)
            Path("/data/temp/other_data.dat"),  # Should be kept
        )

        result = copier._filter_smarttable_csvs(source_files)

        expected = (
            Path("/data/temp/extracted_file.txt"),
            Path("/data/raw/regular_file.csv"),
            Path("/data/temp/other_data.dat"),
        )

        assert result == expected

    def test_process_with_save_raw_enabled(self):
        """Test processing with save_raw enabled."""
        copier = SmartTableFileCopier()

        # Create mock context
        mock_context = Mock()
        mock_context.srcpaths.config.system.save_raw = True
        mock_context.srcpaths.config.system.save_nonshared_raw = False
        mock_context.resource_paths.rawfiles = (
            Path("/data/temp/fsmarttable_test_0000.csv"),
            Path("/data/temp/extracted_file.txt"),
        )
        mock_context.resource_paths.raw = Path("/output/raw")

        with patch.object(copier, '_copy_files') as mock_copy:
            copier.process(mock_context)

            # Should call _copy_files for raw directory with filtered files
            mock_copy.assert_called_once_with(
                Path("/output/raw"),
                (Path("/data/temp/extracted_file.txt"),)
            )

    def test_process_with_save_nonshared_raw_enabled(self):
        """Test processing with save_nonshared_raw enabled."""
        copier = SmartTableFileCopier()

        # Create mock context
        mock_context = Mock()
        mock_context.srcpaths.config.system.save_raw = False
        mock_context.srcpaths.config.system.save_nonshared_raw = True
        mock_context.resource_paths.rawfiles = (
            Path("/data/temp/fsmarttable_test_0000.csv"),
            Path("/data/temp/data_file.txt"),
        )
        mock_context.resource_paths.nonshared_raw = Path("/output/nonshared_raw")

        with patch.object(copier, '_copy_files') as mock_copy:
            copier.process(mock_context)

            # Should call _copy_files for nonshared_raw directory with filtered files
            mock_copy.assert_called_once_with(
                Path("/output/nonshared_raw"),
                (Path("/data/temp/data_file.txt"),)
            )

    def test_process_with_both_saves_enabled(self):
        """Test processing with both save options enabled."""
        copier = SmartTableFileCopier()

        # Create mock context
        mock_context = Mock()
        mock_context.srcpaths.config.system.save_raw = True
        mock_context.srcpaths.config.system.save_nonshared_raw = True
        mock_context.resource_paths.rawfiles = (
            Path("/data/temp/fsmarttable_test_0000.csv"),
            Path("/data/temp/extracted_file.txt"),
        )
        mock_context.resource_paths.raw = Path("/output/raw")
        mock_context.resource_paths.nonshared_raw = Path("/output/nonshared_raw")

        with patch.object(copier, '_copy_files') as mock_copy:
            copier.process(mock_context)

            # Should call _copy_files twice, once for each directory
            assert mock_copy.call_count == 2

            # Verify calls were made with filtered files
            calls = mock_copy.call_args_list
            assert calls[0][0] == (Path("/output/raw"), (Path("/data/temp/extracted_file.txt"),))
            assert calls[1][0] == (Path("/output/nonshared_raw"), (Path("/data/temp/extracted_file.txt"),))

    def test_process_with_no_saves_enabled(self):
        """Test processing with no save options enabled."""
        copier = SmartTableFileCopier()

        # Create mock context
        mock_context = Mock()
        mock_context.srcpaths.config.system.save_raw = False
        mock_context.srcpaths.config.system.save_nonshared_raw = False

        with patch.object(copier, '_copy_files') as mock_copy:
            copier.process(mock_context)

            # Should not call _copy_files at all
            mock_copy.assert_not_called()

    def test_copy_files_functionality(self, tmp_path):
        """Test the actual file copying functionality."""
        copier = SmartTableFileCopier()

        # Create source files
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        source_file1 = source_dir / "file1.txt"
        source_file1.write_text("content1")

        source_file2 = source_dir / "file2.dat"
        source_file2.write_text("content2")

        # Create destination directory
        dest_dir = tmp_path / "dest"

        # Test copying
        source_files = (source_file1, source_file2)
        copier._copy_files(dest_dir, source_files)

        # Verify files were copied
        assert (dest_dir / "file1.txt").exists()
        assert (dest_dir / "file2.dat").exists()
        assert (dest_dir / "file1.txt").read_text() == "content1"
        assert (dest_dir / "file2.dat").read_text() == "content2"

    def test_filter_with_empty_files(self):
        """Test filtering with empty file list."""
        copier = SmartTableFileCopier()

        result = copier._filter_smarttable_csvs(tuple())

        assert result == tuple()

    def test_filter_with_only_smarttable_csvs(self):
        """Test filtering when all files are SmartTable CSVs."""
        copier = SmartTableFileCopier()

        source_files = (
            Path("/data/temp/fsmarttable_test_0000.csv"),
            Path("/data/temp/fsmarttable_exp_0001.csv"),
        )

        result = copier._filter_smarttable_csvs(source_files)

        assert result == tuple()

    def test_complex_naming_patterns(self):
        """Test various naming patterns for SmartTable CSV detection."""
        copier = SmartTableFileCopier()

        # Test cases that should be identified as SmartTable CSVs
        true_cases = [
            Path("/temp/fsmarttable_complex_name_with_underscores_0000.csv"),
            Path("/data/temp/fsmarttable_a_0099.csv"),
            Path("/tmp/temp/fsmarttable_experiment123_0001.csv"),
        ]

        for test_path in true_cases:
            assert copier._is_smarttable_generated_csv(test_path) is True

        # Test cases that should NOT be identified as SmartTable CSVs
        false_cases = [
            Path("/temp/fsmart_table_test_0000.csv"),  # Missing 'table' part
            Path("/temp/smarttable_test_0000.csv"),   # Missing 'f' prefix
            Path("/temp/fsmarttable_test.csv"),       # Missing numeric suffix
        ]

        for test_path in false_cases:
            assert copier._is_smarttable_generated_csv(test_path) is False
