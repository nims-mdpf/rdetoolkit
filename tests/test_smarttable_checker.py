"""Test SmartTableChecker functionality."""

from pathlib import Path
import pytest
import zipfile
from unittest.mock import Mock, patch

from rdetoolkit.impl.input_controller import SmartTableChecker
from rdetoolkit.exceptions import StructuredError


class TestSmartTableChecker:
    """Test suite for SmartTableChecker functionality."""

    def test_checker_type(self):
        """Test that checker_type returns correct value."""
        checker = SmartTableChecker(Path("data/temp"))
        assert checker.checker_type == "smarttable"

    def test_parse_with_excel_file(self, tmp_path):
        """Test parsing with SmartTable Excel file."""
        # Create test files
        smarttable_file = tmp_path / "smarttable_test.xlsx"
        smarttable_file.touch()

        with patch('rdetoolkit.impl.input_controller.SmartTableFile') as mock_st:
            mock_instance = Mock()
            mock_st.return_value = mock_instance
            mock_instance.generate_row_csvs_with_file_mapping.return_value = [
                (Path("data/temp/row_0.csv"), (Path("file1.txt"),)),
                (Path("data/temp/row_1.csv"), (Path("file2.txt"),)),
            ]

            checker = SmartTableChecker(Path("data/temp"), save_table_file=True)
            rawfiles, smarttable_path = checker.parse(tmp_path)

            assert len(rawfiles) == 3
            # First entry: SmartTable file only
            assert rawfiles[0] == (smarttable_file,)
            # Subsequent entries: Each CSV with related files
            assert rawfiles[1] == (Path("data/temp/row_0.csv"), Path("file1.txt"))
            assert rawfiles[2] == (Path("data/temp/row_1.csv"), Path("file2.txt"))
            assert smarttable_path == smarttable_file

    def test_parse_with_csv_file(self, tmp_path):
        """Test parsing with SmartTable CSV file."""
        smarttable_file = tmp_path / "smarttable_data.csv"
        smarttable_file.touch()

        with patch('rdetoolkit.impl.input_controller.SmartTableFile') as mock_st:
            mock_instance = Mock()
            mock_st.return_value = mock_instance
            mock_instance.generate_row_csvs_with_file_mapping.return_value = [
                (Path("data/temp/row_0.csv"), ()),
            ]

            checker = SmartTableChecker(Path("data/temp"), save_table_file=True)
            rawfiles, smarttable_path = checker.parse(tmp_path)

            assert len(rawfiles) == 2
            # First entry: SmartTable file only
            assert rawfiles[0] == (smarttable_file,)
            # Second entry: CSV file only
            assert rawfiles[1] == (Path("data/temp/row_0.csv"),)
            assert smarttable_path == smarttable_file

    def test_parse_with_tsv_file(self, tmp_path):
        """Test parsing with SmartTable TSV file."""
        smarttable_file = tmp_path / "smarttable_experiment.tsv"
        smarttable_file.touch()

        with patch('rdetoolkit.impl.input_controller.SmartTableFile') as mock_st:
            mock_instance = Mock()
            mock_st.return_value = mock_instance
            mock_instance.generate_row_csvs_with_file_mapping.return_value = [
                (Path("data/temp/row_0.csv"), (Path("data1.txt"), Path("data2.txt"))),
            ]

            checker = SmartTableChecker(Path("data/temp"), save_table_file=True)
            rawfiles, smarttable_path = checker.parse(tmp_path)

            assert len(rawfiles) == 2
            # First entry: SmartTable file only
            assert rawfiles[0] == (smarttable_file,)
            # Second entry: CSV file with related files
            assert rawfiles[1] == (Path("data/temp/row_0.csv"), Path("data1.txt"), Path("data2.txt"))
            assert smarttable_path == smarttable_file

    def test_parse_with_zip_file(self, tmp_path):
        """Test parsing with SmartTable file and zip file."""
        # Create SmartTable file
        smarttable_file = tmp_path / "smarttable_with_zip.xlsx"
        smarttable_file.touch()

        # Create zip file with test content
        zip_file = tmp_path / "test_data.zip"
        test_content = tmp_path / "test_content.txt"
        test_content.write_text("test data")

        with zipfile.ZipFile(zip_file, 'w') as zf:
            zf.write(test_content, "test_content.txt")

        with patch('rdetoolkit.impl.input_controller.SmartTableFile') as mock_st:
            mock_instance = Mock()
            mock_st.return_value = mock_instance
            mock_instance.generate_row_csvs_with_file_mapping.return_value = [
                (Path("data/temp/row_0.csv"), (Path("data/temp/test_content.txt"),)),
            ]

            checker = SmartTableChecker(Path("data/temp"), save_table_file=True)
            rawfiles, smarttable_path = checker.parse(tmp_path)

            assert len(rawfiles) == 2
            # First entry: SmartTable file only
            assert rawfiles[0] == (smarttable_file,)
            # Second entry: CSV file with extracted file
            assert rawfiles[1] == (Path("data/temp/row_0.csv"), Path("data/temp/test_content.txt"))
            assert smarttable_path == smarttable_file

    def test_parse_no_smarttable_files(self, tmp_path):
        """Test parsing when no SmartTable files are found."""
        # Create non-SmartTable files
        (tmp_path / "regular_file.txt").touch()
        (tmp_path / "data.xlsx").touch()  # Excel file but doesn't start with smarttable_

        checker = SmartTableChecker(Path("data/temp"))

        with pytest.raises(StructuredError) as exc_info:
            checker.parse(tmp_path)

        assert "No SmartTable files found" in str(exc_info.value)

    def test_parse_multiple_smarttable_files(self, tmp_path):
        """Test parsing when multiple SmartTable files are found."""
        # Create multiple SmartTable files
        (tmp_path / "smarttable_1.xlsx").touch()
        (tmp_path / "smarttable_2.csv").touch()

        checker = SmartTableChecker(Path("data/temp"))

        with pytest.raises(StructuredError) as exc_info:
            checker.parse(tmp_path)

        assert "Multiple SmartTable files found" in str(exc_info.value)

    def test_parse_invalid_extension(self, tmp_path):
        """Test parsing with invalid file extension."""
        # Create file with smarttable_ prefix but invalid extension
        (tmp_path / "smarttable_data.txt").touch()

        checker = SmartTableChecker(Path("data/temp"))

        with pytest.raises(StructuredError) as exc_info:
            checker.parse(tmp_path)

        assert "No SmartTable files found" in str(exc_info.value)

    def test_unpacked_smarttable_functionality(self, tmp_path):
        """Test the _unpacked_smarttable method."""
        # Create test zip file
        zip_file = tmp_path / "test.zip"
        test_file = tmp_path / "source.txt"
        test_file.write_text("test content")

        with zipfile.ZipFile(zip_file, 'w') as zf:
            zf.write(test_file, "extracted.txt")

        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()

        checker = SmartTableChecker(temp_dir)
        extracted_files = checker._unpacked_smarttable(zip_file)

        assert len(extracted_files) == 1
        assert extracted_files[0].name == "extracted.txt"
        assert extracted_files[0].is_file()

    def test_edge_case_empty_directory(self, tmp_path):
        """Test parsing with empty directory."""
        checker = SmartTableChecker(Path("data/temp"))

        with pytest.raises(StructuredError) as exc_info:
            checker.parse(tmp_path)

        assert "No SmartTable files found" in str(exc_info.value)

    def test_case_insensitive_extensions(self, tmp_path):
        """Test that file extensions are handled case-insensitively."""
        smarttable_file = tmp_path / "smarttable_test.XLSX"
        smarttable_file.touch()

        with patch('rdetoolkit.impl.input_controller.SmartTableFile') as mock_st:
            mock_instance = Mock()
            mock_st.return_value = mock_instance
            mock_instance.generate_row_csvs_with_file_mapping.return_value = [
                (Path("data/temp/row_0.csv"), ()),
            ]

            checker = SmartTableChecker(Path("data/temp"), save_table_file=True)
            rawfiles, smarttable_path = checker.parse(tmp_path)

            assert len(rawfiles) == 2
            # First entry: SmartTable file only
            assert rawfiles[0] == (smarttable_file,)
            # Second entry: CSV file only
            assert rawfiles[1] == (Path("data/temp/row_0.csv"),)
            assert smarttable_path == smarttable_file

    def test_multiple_zip_files_handling(self, tmp_path):
        """Test handling multiple zip files."""
        # Create SmartTable file
        smarttable_file = tmp_path / "smarttable_test.xlsx"
        smarttable_file.touch()

        # Create multiple zip files
        for i in range(2):
            zip_file = tmp_path / f"data_{i}.zip"
            test_file = tmp_path / f"source_{i}.txt"
            test_file.write_text(f"test content {i}")

            with zipfile.ZipFile(zip_file, 'w') as zf:
                zf.write(test_file, f"extracted_{i}.txt")

        with patch('rdetoolkit.impl.input_controller.SmartTableFile') as mock_st:
            mock_instance = Mock()
            mock_st.return_value = mock_instance
            # Mock should be called with extracted files from both zips
            mock_instance.generate_row_csvs_with_file_mapping.return_value = [
                (Path("data/temp/row_0.csv"), (Path("data/temp/extracted_0.txt"), Path("data/temp/extracted_1.txt"))),
            ]

            checker = SmartTableChecker(Path("data/temp"), save_table_file=True)
            rawfiles, smarttable_path = checker.parse(tmp_path)

            assert len(rawfiles) == 2
            # First entry: SmartTable file only
            assert rawfiles[0] == (smarttable_file,)
            # Second entry: CSV file + 2 extracted files
            assert len(rawfiles[1]) == 3  # CSV file + 2 extracted files
            assert rawfiles[1][0] == Path("data/temp/row_0.csv")  # First should be CSV file
            assert smarttable_path == smarttable_file

    def test_save_table_file_false(self, tmp_path):
        """Test that when save_table_file=False, SmartTable file is not included in rawfiles."""
        # Create test files
        smarttable_file = tmp_path / "smarttable_test.xlsx"
        smarttable_file.touch()

        with patch('rdetoolkit.impl.input_controller.SmartTableFile') as mock_st:
            mock_instance = Mock()
            mock_st.return_value = mock_instance
            mock_instance.generate_row_csvs_with_file_mapping.return_value = [
                (Path("data/temp/row_0.csv"), (Path("file1.txt"),)),
                (Path("data/temp/row_1.csv"), (Path("file2.txt"),)),
            ]

            # Default behavior: save_table_file=False
            checker = SmartTableChecker(Path("data/temp"))
            rawfiles, smarttable_path = checker.parse(tmp_path)

            # Only CSV files should be in rawfiles, not the SmartTable file
            assert len(rawfiles) == 2
            assert rawfiles[0] == (Path("data/temp/row_0.csv"), Path("file1.txt"))
            assert rawfiles[1] == (Path("data/temp/row_1.csv"), Path("file2.txt"))
            assert smarttable_path == smarttable_file

    def test_save_table_file_explicit_false(self, tmp_path):
        """Test explicit save_table_file=False behavior."""
        smarttable_file = tmp_path / "smarttable_data.csv"
        smarttable_file.touch()

        with patch('rdetoolkit.impl.input_controller.SmartTableFile') as mock_st:
            mock_instance = Mock()
            mock_st.return_value = mock_instance
            mock_instance.generate_row_csvs_with_file_mapping.return_value = [
                (Path("data/temp/row_0.csv"), ()),
            ]

            checker = SmartTableChecker(Path("data/temp"), save_table_file=False)
            rawfiles, smarttable_path = checker.parse(tmp_path)

            # Only CSV files should be in rawfiles
            assert len(rawfiles) == 1
            assert rawfiles[0] == (Path("data/temp/row_0.csv"),)
            assert smarttable_path == smarttable_file
