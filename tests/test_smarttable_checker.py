"""Test SmartTableChecker functionality.

Equivalence Partitioning:
| API | Input/State Partition | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| ``SmartTableChecker.parse`` | ``save_table_file=True``, N>=2 data rows | valid domain | original file entry ``(None, (smarttable_file,))`` is placed at divided/0001 (index 1); last row occupies data/ root (index 0) | TC-EP-SMARTTABLE-001 |
| ``SmartTableChecker.parse`` | ``save_table_file=False``, N>=2 data rows | valid domain | last row occupies data/ root (index 0); earlier rows populate divided folders in table order | TC-EP-SMARTTABLE-002 |

Boundary Value:
| API | Boundary | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| ``SmartTableChecker.parse`` | ``save_table_file=True``, 0 data rows | minimum row count; only the original file tile exists | original file entry alone occupies data/ root | TC-BV-SMARTTABLE-001 |
| ``SmartTableChecker.parse`` | ``save_table_file=True``, 1 data row | minimum row count that exercises root/divided reordering with data | original file entry at divided/0001, single row at data/ root | TC-BV-SMARTTABLE-002 |
| ``SmartTableChecker.parse`` | ``save_table_file=False``, 1 data row | minimum row count | single row occupies data/ root alone | TC-BV-SMARTTABLE-003 |

Validation commands:
Direct: ``uv run pytest tests/test_smarttable_checker.py -q``
Tox: ``tox -e py312-module -- tests/test_smarttable_checker.py``
"""

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
            # idx=0 -> data/ root: last row (registered last by RDE)
            assert rawfiles[0] == (Path("data/temp/row_1.csv"), (Path("file2.txt"),))
            # idx=1 -> data/divided/0001: original SmartTable file (registered first)
            assert rawfiles[1] == (None, (smarttable_file,))
            # idx=2 -> data/divided/0002: remaining row(s) in table order
            assert rawfiles[2] == (Path("data/temp/row_0.csv"), (Path("file1.txt"),))
            assert smarttable_path == smarttable_file

    def test_parse_with_csv_file(self, tmp_path):
        """Test parsing with SmartTable CSV file (single data row)."""
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
            # idx=0 -> data/ root: the single data row (registered last)
            assert rawfiles[0] == (Path("data/temp/row_0.csv"), ())
            # idx=1 -> data/divided/0001: original SmartTable file (registered first)
            assert rawfiles[1] == (None, (smarttable_file,))
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
            # idx=0 -> data/ root: the single data row with related files (registered last)
            assert rawfiles[0] == (Path("data/temp/row_0.csv"), (Path("data1.txt"), Path("data2.txt")))
            # idx=1 -> data/divided/0001: original SmartTable file (registered first)
            assert rawfiles[1] == (None, (smarttable_file,))
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
            # idx=0 -> data/ root: the single data row with extracted file (registered last)
            assert rawfiles[0] == (Path("data/temp/row_0.csv"), (Path("data/temp/test_content.txt"),))
            # idx=1 -> data/divided/0001: original SmartTable file (registered first)
            assert rawfiles[1] == (None, (smarttable_file,))
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
            # idx=0 -> data/ root: the single data row (registered last)
            assert rawfiles[0] == (Path("data/temp/row_0.csv"), ())
            # idx=1 -> data/divided/0001: original SmartTable file (registered first)
            assert rawfiles[1] == (None, (smarttable_file,))
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
            # idx=0 -> data/ root: the single data row (CSV file + 2 extracted files), registered last
            assert rawfiles[0][0] == Path("data/temp/row_0.csv")
            assert len(rawfiles[0][1]) == 2
            # idx=1 -> data/divided/0001: original SmartTable file (registered first)
            assert rawfiles[1] == (None, (smarttable_file,))
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

            # SmartTable file is excluded; the LAST row occupies data/ root (registered
            # last by RDE) so registration order stays row_0 -> row_1.
            assert len(rawfiles) == 2
            assert rawfiles[0] == (Path("data/temp/row_1.csv"), (Path("file2.txt"),))  # idx=0 -> data/ root (last row)
            assert rawfiles[1] == (Path("data/temp/row_0.csv"), (Path("file1.txt"),))  # idx=1 -> data/divided/0001 (first row)
            assert smarttable_path == smarttable_file

    def test_save_table_file_explicit_false(self, tmp_path):
        """Test explicit save_table_file=False behavior with a single data row."""
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

            # Only the single data row should be in rawfiles, occupying data/ root alone.
            assert len(rawfiles) == 1
            assert rawfiles[0] == (Path("data/temp/row_0.csv"), ())
            assert smarttable_path == smarttable_file

    def test_parse_save_table_file_true_no_data_rows(self, tmp_path):
        """Test save_table_file=True with zero data rows.

        With no data rows generated from the table, the original file entry
        alone occupies data/ root.
        """
        smarttable_file = tmp_path / "smarttable_test.xlsx"
        smarttable_file.touch()

        with patch('rdetoolkit.impl.input_controller.SmartTableFile') as mock_st:
            mock_instance = Mock()
            mock_st.return_value = mock_instance
            mock_instance.generate_row_csvs_with_file_mapping.return_value = []

            checker = SmartTableChecker(Path("data/temp"), save_table_file=True)
            rawfiles, smarttable_path = checker.parse(tmp_path)

            assert len(rawfiles) == 1
            assert rawfiles[0] == (None, (smarttable_file,))
            assert smarttable_path == smarttable_file

    def test_parse_save_table_file_true_table_at_divided_0001(self, tmp_path):
        """Test original SmartTable file goes to divided/0001 when save_table_file=True.

        The RDE system registers data/divided/0001..N first and data/ root LAST.
        Placing the original file entry at idx=1 (divided/0001) makes it register
        first, followed by remaining rows, with the last row registering last at
        data/ root:
        - idx=0 → data/ root (last data row, registered last)
        - idx=1 → data/divided/0001/ (original SmartTable file, registered first)
        - idx=2 → data/divided/0002/ (first data row)
        """
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
            assert rawfiles[0] == (Path("data/temp/row_1.csv"), (Path("file2.txt"),))  # idx=0 -> data/ root (last row, registered last)
            assert rawfiles[1] == (None, (smarttable_file,))  # idx=1 -> divided/0001 (original file, registered first)
            assert rawfiles[2] == (Path("data/temp/row_0.csv"), (Path("file1.txt"),))  # idx=2 -> divided/0002 (first row)
            assert smarttable_path == smarttable_file

    def test_parse_save_table_file_false_last_row_first(self, tmp_path):
        """Test the LAST data row goes to data/ root when save_table_file=False.

        The RDE system registers data/divided/0001..N first and data/ root LAST, and
        data/ root must always be registered. With no SmartTable file to occupy it,
        the final data row is placed at idx=0 so registration order stays row_0..row_2:
        - idx=0 → data/ root (row_2, the last row, registered last)
        - idx=1 → data/divided/0001/ (row_0, the first row)
        - idx=2 → data/divided/0002/ (row_1, the second row)
        """
        smarttable_file = tmp_path / "smarttable_test.xlsx"
        smarttable_file.touch()

        with patch('rdetoolkit.impl.input_controller.SmartTableFile') as mock_st:
            mock_instance = Mock()
            mock_st.return_value = mock_instance
            mock_instance.generate_row_csvs_with_file_mapping.return_value = [
                (Path("data/temp/row_0.csv"), (Path("file0.txt"),)),
                (Path("data/temp/row_1.csv"), (Path("file1.txt"),)),
                (Path("data/temp/row_2.csv"), (Path("file2.txt"),)),
            ]

            checker = SmartTableChecker(Path("data/temp"), save_table_file=False)
            rawfiles, smarttable_path = checker.parse(tmp_path)

            assert len(rawfiles) == 3
            assert rawfiles[0] == (Path("data/temp/row_2.csv"), (Path("file2.txt"),))  # idx=0 -> data/ root (last row)
            assert rawfiles[1] == (Path("data/temp/row_0.csv"), (Path("file0.txt"),))  # idx=1 -> data/divided/0001 (first row)
            assert rawfiles[2] == (Path("data/temp/row_1.csv"), (Path("file1.txt"),))  # idx=2 -> data/divided/0002 (second row)
            assert smarttable_path == smarttable_file

    def test_parse_save_table_file_false_no_data_rows(self, tmp_path):
        """Test save_table_file=False with zero data rows results in empty rawfiles."""
        smarttable_file = tmp_path / "smarttable_test.xlsx"
        smarttable_file.touch()

        with patch('rdetoolkit.impl.input_controller.SmartTableFile') as mock_st:
            mock_instance = Mock()
            mock_st.return_value = mock_instance
            mock_instance.generate_row_csvs_with_file_mapping.return_value = []

            checker = SmartTableChecker(Path("data/temp"), save_table_file=False)
            rawfiles, smarttable_path = checker.parse(tmp_path)

            assert rawfiles == []
            assert smarttable_path == smarttable_file
