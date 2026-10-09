"""Test SmartTableFileCopier functionality."""

from pathlib import Path
from unittest.mock import Mock, patch

from rdetoolkit.processing.processors.files import SmartTableFileCopier


class TestSmartTableFileCopier:
    """Test suite for SmartTableFileCopier functionality."""

    def test_process_with_save_raw_enabled(self):
        """Test processing with save_raw enabled."""
        copier = SmartTableFileCopier()

        # Create mock context
        mock_context = Mock()
        mock_context.srcpaths.config.system.save_raw = True
        mock_context.srcpaths.config.system.save_nonshared_raw = False
        mock_context.is_smarttable_mode = False  # Not in SmartTable mode
        mock_context.srcpaths.config.smarttable = None
        # rawfiles no longer contains SmartTable generated row CSVs (Task 01/02).
        mock_context.resource_paths.rawfiles = (
            Path("/data/temp/extracted_file.txt"),
        )
        mock_context.resource_paths.raw = Path("/output/raw")

        with patch.object(copier, '_copy_files') as mock_copy:
            copier.process(mock_context)

            # Should call _copy_files for raw directory with the untouched files
            mock_copy.assert_called_once_with(
                Path("/output/raw"),
                (Path("/data/temp/extracted_file.txt"),),
            )

    def test_process_with_save_nonshared_raw_enabled(self):
        """Test processing with save_nonshared_raw enabled."""
        copier = SmartTableFileCopier()

        # Create mock context
        mock_context = Mock()
        mock_context.srcpaths.config.system.save_raw = False
        mock_context.srcpaths.config.system.save_nonshared_raw = True
        mock_context.is_smarttable_mode = False  # Not in SmartTable mode
        mock_context.srcpaths.config.smarttable = None
        mock_context.resource_paths.rawfiles = (
            Path("/data/temp/data_file.txt"),
        )
        mock_context.resource_paths.nonshared_raw = Path("/output/nonshared_raw")

        with patch.object(copier, '_copy_files') as mock_copy:
            copier.process(mock_context)

            # Should call _copy_files for nonshared_raw directory with the untouched files
            mock_copy.assert_called_once_with(
                Path("/output/nonshared_raw"),
                (Path("/data/temp/data_file.txt"),),
            )

    def test_process_with_both_saves_enabled(self):
        """Test processing with both save options enabled."""
        copier = SmartTableFileCopier()

        # Create mock context
        mock_context = Mock()
        mock_context.srcpaths.config.system.save_raw = True
        mock_context.srcpaths.config.system.save_nonshared_raw = True
        mock_context.is_smarttable_mode = False  # Not in SmartTable mode
        mock_context.srcpaths.config.smarttable = None
        mock_context.resource_paths.rawfiles = (
            Path("/data/temp/extracted_file.txt"),
        )
        mock_context.resource_paths.raw = Path("/output/raw")
        mock_context.resource_paths.nonshared_raw = Path("/output/nonshared_raw")

        with patch.object(copier, '_copy_files') as mock_copy:
            copier.process(mock_context)

            # Should call _copy_files twice, once for each directory
            assert mock_copy.call_count == 2

            # Verify calls were made with the untouched files
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

    def test_process_with_smarttable_file_save_enabled(self):
        """Test processing with SmartTable file save enabled."""
        copier = SmartTableFileCopier()

        # Create mock context
        mock_context = Mock()
        mock_context.srcpaths.config.system.save_raw = True
        mock_context.srcpaths.config.system.save_nonshared_raw = False
        mock_context.is_smarttable_mode = True
        mock_context.srcpaths.config.smarttable = Mock()
        mock_context.srcpaths.config.smarttable.save_table_file = True
        mock_context.smarttable_file = Path("/data/inputdata/smarttable_test.xlsx")
        # rawfiles contains the SmartTable original file and a user file; the
        # generated row CSV is never present here (Task 01/02 invariant).
        mock_context.resource_paths.rawfiles = (
            Path("/data/inputdata/smarttable_test.xlsx"),  # SmartTable file
            Path("/data/temp/extracted_file.txt"),  # Other file
        )
        mock_context.resource_paths.raw = Path("/output/raw")

        with patch.object(copier, '_copy_files') as mock_copy:
            copier.process(mock_context)

            # Should call _copy_files with SmartTable file and extracted file
            expected_files = (
                Path("/data/inputdata/smarttable_test.xlsx"),
                Path("/data/temp/extracted_file.txt"),
            )
            mock_copy.assert_called_once_with(
                Path("/output/raw"),
                expected_files,
            )

    def test_process_with_smarttable_file_save_disabled(self):
        """Test processing with SmartTable file save disabled."""
        copier = SmartTableFileCopier()

        # Create mock context
        mock_context = Mock()
        mock_context.srcpaths.config.system.save_raw = True
        mock_context.srcpaths.config.system.save_nonshared_raw = False
        mock_context.is_smarttable_mode = True
        mock_context.srcpaths.config.smarttable = Mock()
        mock_context.srcpaths.config.smarttable.save_table_file = False
        mock_context.smarttable_file = Path("/data/inputdata/smarttable_test.xlsx")
        # rawfiles includes the SmartTable file, but it should be filtered out
        mock_context.resource_paths.rawfiles = (
            Path("/data/inputdata/smarttable_test.xlsx"),  # SmartTable file (should be filtered)
            Path("/data/temp/extracted_file.txt"),  # Other file (should be kept)
        )
        mock_context.resource_paths.raw = Path("/output/raw")

        with patch.object(copier, '_copy_files') as mock_copy:
            copier.process(mock_context)

            # Should call _copy_files with only extracted file (SmartTable file filtered out)
            mock_copy.assert_called_once_with(
                Path("/output/raw"),
                (Path("/data/temp/extracted_file.txt"),),
            )

    def test_process_with_smarttable_settings_none(self):
        """Test processing when smarttable settings is None."""
        copier = SmartTableFileCopier()

        # Create mock context
        mock_context = Mock()
        mock_context.srcpaths.config.system.save_raw = True
        mock_context.srcpaths.config.system.save_nonshared_raw = False
        mock_context.is_smarttable_mode = True
        mock_context.srcpaths.config.smarttable = None
        mock_context.smarttable_file = Path("/input/smarttable_test.xlsx")
        mock_context.resource_paths.rawfiles = (
            Path("/data/temp/extracted_file.txt"),
        )
        mock_context.resource_paths.raw = Path("/output/raw")

        with patch.object(copier, '_copy_files') as mock_copy:
            copier.process(mock_context)

            # Should call _copy_files with the untouched files (no smarttable file present)
            mock_copy.assert_called_once_with(
                Path("/output/raw"),
                (Path("/data/temp/extracted_file.txt"),),
            )

    def test_process_not_smarttable_mode(self):
        """Test processing when not in SmartTable mode."""
        copier = SmartTableFileCopier()

        # Create mock context
        mock_context = Mock()
        mock_context.srcpaths.config.system.save_raw = True
        mock_context.srcpaths.config.system.save_nonshared_raw = False
        mock_context.is_smarttable_mode = False
        mock_context.resource_paths.rawfiles = (
            Path("/data/temp/extracted_file.txt"),
        )
        mock_context.resource_paths.raw = Path("/output/raw")

        with patch.object(copier, '_copy_files') as mock_copy:
            copier.process(mock_context)

            # Should call _copy_files with the untouched files
            mock_copy.assert_called_once_with(
                Path("/output/raw"),
                (Path("/data/temp/extracted_file.txt"),),
            )

    def test_process_with_smarttable_save_both_directories(self):
        """Test processing with SmartTable file save for both raw and nonshared_raw."""
        copier = SmartTableFileCopier()

        # Create mock context
        mock_context = Mock()
        mock_context.srcpaths.config.system.save_raw = True
        mock_context.srcpaths.config.system.save_nonshared_raw = True
        mock_context.is_smarttable_mode = True
        mock_context.srcpaths.config.smarttable = Mock()
        mock_context.srcpaths.config.smarttable.save_table_file = True
        mock_context.smarttable_file = Path("/data/inputdata/smarttable_data.csv")
        mock_context.resource_paths.rawfiles = (
            Path("/data/inputdata/smarttable_data.csv"),  # SmartTable file
            Path("/data/temp/important_file.txt"),  # Other file
        )
        mock_context.resource_paths.raw = Path("/output/raw")
        mock_context.resource_paths.nonshared_raw = Path("/output/nonshared_raw")

        with patch.object(copier, '_copy_files') as mock_copy:
            copier.process(mock_context)

            # Should call _copy_files twice with both SmartTable file and important file
            assert mock_copy.call_count == 2

            expected_files = (
                Path("/data/inputdata/smarttable_data.csv"),
                Path("/data/temp/important_file.txt"),
            )

            calls = mock_copy.call_args_list
            assert calls[0][0] == (Path("/output/raw"), expected_files)
            assert calls[1][0] == (Path("/output/nonshared_raw"), expected_files)


class TestSmartTableFileCopierRowCsvExclusion:
    """Regression tests locking in the structural guarantee (Task 01/02).

    SmartTable-generated row CSV files are never copied to raw/nonshared_raw,
    because they are never present in ``rawfiles`` to begin with.

    These tests intentionally do NOT rely on any filename-based filtering in
    SmartTableFileCopier (that dead code path was removed in this task);
    instead they assert the structural invariant directly.
    """

    def test_save_raw_never_copies_row_csv_when_absent_from_rawfiles(self):
        """save_raw=True: rawfiles without a row CSV never produces one in raw/."""
        copier = SmartTableFileCopier()

        mock_context = Mock()
        mock_context.srcpaths.config.system.save_raw = True
        mock_context.srcpaths.config.system.save_nonshared_raw = False
        mock_context.is_smarttable_mode = True
        mock_context.srcpaths.config.smarttable = Mock()
        mock_context.srcpaths.config.smarttable.save_table_file = True
        # NOTE: rawfiles (Task 01/02 structure) never contains a row CSV such
        # as "fsmarttable_*.csv"; only the original SmartTable file and user
        # files coming from the tile's related files are present.
        mock_context.resource_paths.rawfiles = (
            Path("/data/inputdata/smarttable_test.xlsx"),
            Path("/data/divided/0001/extracted_file.txt"),
        )
        # The row CSV path is reachable via resource_paths.smarttable_rawfile,
        # but that must have no bearing on what gets copied.
        mock_context.resource_paths.smarttable_rawfile = Path("/data/temp/fsmarttable_test_0000.csv")
        mock_context.resource_paths.raw = Path("/output/raw")

        with patch.object(copier, '_copy_files') as mock_copy:
            copier.process(mock_context)

            copied_dest, copied_files = mock_copy.call_args[0]
            assert copied_dest == Path("/output/raw")
            assert Path("/data/temp/fsmarttable_test_0000.csv") not in copied_files
            assert all(f.suffix != '.csv' or 'fsmarttable' not in f.name for f in copied_files)

    def test_save_nonshared_raw_never_copies_row_csv_when_absent_from_rawfiles(self):
        """save_nonshared_raw=True: rawfiles without a row CSV never produces one in nonshared_raw/."""
        copier = SmartTableFileCopier()

        mock_context = Mock()
        mock_context.srcpaths.config.system.save_raw = False
        mock_context.srcpaths.config.system.save_nonshared_raw = True
        mock_context.is_smarttable_mode = True
        mock_context.srcpaths.config.smarttable = Mock()
        mock_context.srcpaths.config.smarttable.save_table_file = True
        mock_context.resource_paths.rawfiles = (
            Path("/data/inputdata/smarttable_test.xlsx"),
            Path("/data/divided/0001/extracted_file.txt"),
        )
        mock_context.resource_paths.smarttable_rawfile = Path("/data/temp/fsmarttable_test_0001.csv")
        mock_context.resource_paths.nonshared_raw = Path("/output/nonshared_raw")

        with patch.object(copier, '_copy_files') as mock_copy:
            copier.process(mock_context)

            copied_dest, copied_files = mock_copy.call_args[0]
            assert copied_dest == Path("/output/nonshared_raw")
            assert Path("/data/temp/fsmarttable_test_0001.csv") not in copied_files

    def test_row_csv_only_reachable_via_accessor_is_not_copied_even_when_save_table_file_false(self):
        """Row CSV reachable only via the accessor must still not be copied.

        Even when the original SmartTable file is filtered out (save_table_file=False),
        the row CSV referenced only via the smarttable row-file accessor must not appear
        among the copied files, since it was never part of rawfiles.
        """
        copier = SmartTableFileCopier()

        mock_context = Mock()
        mock_context.srcpaths.config.system.save_raw = True
        mock_context.srcpaths.config.system.save_nonshared_raw = False
        mock_context.is_smarttable_mode = True
        mock_context.srcpaths.config.smarttable = Mock()
        mock_context.srcpaths.config.smarttable.save_table_file = False
        mock_context.resource_paths.rawfiles = (
            Path("/data/inputdata/smarttable_test.xlsx"),
            Path("/data/divided/0001/extracted_file.txt"),
        )
        mock_context.resource_paths.smarttable_rawfile = Path("/data/temp/fsmarttable_test_0002.csv")
        mock_context.resource_paths.raw = Path("/output/raw")

        with patch.object(copier, '_copy_files') as mock_copy:
            copier.process(mock_context)

            mock_copy.assert_called_once_with(
                Path("/output/raw"),
                (Path("/data/divided/0001/extracted_file.txt"),),
            )
