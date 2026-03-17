"""Test SmartTableFile functionality with SmartTable file-mapping coverage.

Equivalence Partitioning:
| API | Input/State Partition | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `SmartTableFile.generate_row_csvs_with_file_mapping` | All `inputdata` values resolve to extracted files | Valid SmartTable references should preserve current behavior | Returns per-row CSV mappings with related files | `TC-EP-001` |
| `SmartTableFile.generate_row_csvs_with_file_mapping` | One `inputdata` value does not exist in extracted files | Missing file should fail early with actionable context | Raises `StructuredError` including row, column, basename | `TC-EP-002` |
| `SmartTableFile.generate_row_csvs_with_file_mapping` | Multiple `inputdata` values are missing across rows | UI needs one concise example while logs keep all details | Raises representative `StructuredError` and logs all mismatches | `TC-EP-003` |
|
Boundary Value:
| API | Boundary | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `SmartTableFile.generate_row_csvs_with_file_mapping` | Second data row (`idx=1`) in SmartTable | User-facing row number must match the displayed SmartTable row (`4`) | Error message reports SmartTable row `4` | `TC-BV-001` |
"""

from pathlib import Path
import pytest
import pandas as pd
from unittest.mock import patch

from rdetoolkit.invoicefile import SmartTableFile
from rdetoolkit.exceptions import StructuredError


class TestSmartTableFile:
    """Test suite for SmartTableFile functionality."""

    def test_init_with_excel_file(self, tmp_path):
        """Test initialization with Excel file."""
        excel_file = tmp_path / "smarttable_test.xlsx"
        excel_file.touch()

        st_file = SmartTableFile(excel_file)
        assert st_file.smarttable_path == excel_file

    def test_init_with_csv_file(self, tmp_path):
        """Test initialization with CSV file."""
        csv_file = tmp_path / "smarttable_test.csv"
        csv_file.touch()

        st_file = SmartTableFile(csv_file)
        assert st_file.smarttable_path == csv_file

    def test_init_with_tsv_file(self, tmp_path):
        """Test initialization with TSV file."""
        tsv_file = tmp_path / "smarttable_test.tsv"
        tsv_file.touch()

        st_file = SmartTableFile(tsv_file)
        assert st_file.smarttable_path == tsv_file

    def test_init_with_invalid_extension(self, tmp_path):
        """Test initialization with invalid file extension."""
        invalid_file = tmp_path / "smarttable_test.txt"
        invalid_file.touch()

        with pytest.raises(StructuredError) as exc_info:
            SmartTableFile(invalid_file)

        assert "Unsupported file format" in str(exc_info.value)

    def test_read_table_excel(self, tmp_path):
        """Test reading Excel table."""
        excel_file = tmp_path / "smarttable_test.xlsx"

        # Create test data with actual Excel file
        test_data = pd.DataFrame({
            'A': ['Display Name 1', 'basic/dataName', 'Sample1', 'Sample2'],
            'B': ['Display Name 2', 'custom/value', 'Value1', 'Value2'],
            'C': ['Display Name 3', 'sample/name', 'Name1', 'Name2'],
        })
        test_data.to_excel(excel_file, index=False, header=False)

        st_file = SmartTableFile(excel_file)
        result = st_file.read_table()

        # Should skip first row and use second as header
        assert len(result) == 2  # Two data rows
        assert list(result.columns) == ['basic/dataName', 'custom/value', 'sample/name']

    def test_read_table_csv(self, tmp_path):
        """Test reading CSV table."""
        csv_file = tmp_path / "smarttable_test.csv"
        csv_content = """Display Name 1,Display Name 2,Display Name 3
basic/dataName,custom/value,sample/name
Sample1,Value1,Name1
Sample2,Value2,Name2"""
        csv_file.write_text(csv_content)

        st_file = SmartTableFile(csv_file)
        result = st_file.read_table()

        assert len(result) == 2
        assert list(result.columns) == ['basic/dataName', 'custom/value', 'sample/name']
        assert result.iloc[0]['basic/dataName'] == 'Sample1'

    def test_read_table_tsv(self, tmp_path):
        """Test reading TSV table."""
        tsv_file = tmp_path / "smarttable_test.tsv"
        tsv_content = """Display Name 1\tDisplay Name 2\tDisplay Name 3
basic/dataName\tcustom/value\tsample/name
Sample1\tValue1\tName1
Sample2\tValue2\tName2"""
        tsv_file.write_text(tsv_content)

        st_file = SmartTableFile(tsv_file)
        result = st_file.read_table()

        assert len(result) == 2
        assert list(result.columns) == ['basic/dataName', 'custom/value', 'sample/name']
        assert result.iloc[0]['basic/dataName'] == 'Sample1'

    def test_read_table_with_encoding_detection(self, tmp_path):
        """Test CSV reading with encoding detection."""
        csv_file = tmp_path / "smarttable_test.csv"
        csv_content = """Display Name,Value
basic/dataName,テストデータ
Sample1,データ1"""
        # Write with different encoding
        csv_file.write_text(csv_content, encoding='utf-8')

        st_file = SmartTableFile(csv_file)

        with patch('chardet.detect') as mock_detect:
            mock_detect.return_value = {'encoding': 'utf-8', 'confidence': 0.99}
            result = st_file.read_table()

            assert len(result) == 1
            assert 'basic/dataName' in result.columns


    def test_generate_row_csvs_with_file_mapping(self, tmp_path):
        """TC-EP-001: Generating individual CSV files keeps related file mappings."""
        # Given: a SmartTable whose inputdata values all exist in extracted files
        csv_file = tmp_path / "smarttable_test.csv"
        csv_content = """File,Name,Value
inputdata1,basic/dataName,custom/value
test1.txt,Sample1,Value1
test2.txt,Sample2,Value2"""
        csv_file.write_text(csv_content)

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        extracted_files = [
            Path("/temp/test1.txt"),
            Path("/temp/test2.txt"),
            Path("/temp/other.txt"),
        ]

        st_file = SmartTableFile(csv_file)

        # When: generating row CSV files with extracted file mappings
        result = st_file.generate_row_csvs_with_file_mapping(output_dir, extracted_files)

        # Then: each row CSV is created and linked to the matching extracted file
        assert len(result) == 2

        # Check first row - new naming convention
        csv_path_0, related_files_0 = result[0]
        assert csv_path_0.name == "fsmarttable_test_0000.csv"
        assert csv_path_0.exists()
        assert related_files_0 == (Path("/temp/test1.txt"),)

        # Check second row
        csv_path_1, related_files_1 = result[1]
        assert csv_path_1.name == "fsmarttable_test_0001.csv"
        assert csv_path_1.exists()
        assert related_files_1 == (Path("/temp/test2.txt"),)

    def test_generate_row_csvs_with_file_mapping_raises_for_missing_file__tc_ep_002(self, tmp_path, caplog):
        """TC-EP-002: Missing inputdata file raises a concise StructuredError."""
        # Given: a SmartTable row that references a file absent from the uploaded zip
        csv_file = tmp_path / "smarttable_missing.csv"
        csv_file.write_text(
            """File,Name
inputdata1,basic/dataName
nested/results/missing_file.dat,Sample1""",
        )
        output_dir = tmp_path / "output"
        extracted_files = [Path("/temp/results/present_file.dat")]
        st_file = SmartTableFile(csv_file)
        caplog.set_level("ERROR", logger="rdetoolkit.invoicefile._smarttable")

        # When: generating row CSV files with an unresolved inputdata reference
        with pytest.raises(StructuredError) as exc_info:
            st_file.generate_row_csvs_with_file_mapping(output_dir, extracted_files)

        # Then: the error exposes SmartTable row, column, and basename only
        error = exc_info.value
        assert str(error) == "SmartTable row 3 references missing file in zip: inputdata1=missing_file.dat"
        assert "nested/results/missing_file.dat" not in str(error)
        assert error.eobj == [(3, "inputdata1", "nested/results/missing_file.dat")]
        assert "row 3: inputdata1=nested/results/missing_file.dat" in caplog.text

    def test_generate_row_csvs_with_file_mapping_logs_all_missing_files__tc_ep_003(self, tmp_path, caplog):
        """TC-EP-003: Multiple missing inputdata files are aggregated in logs."""
        # Given: multiple SmartTable rows whose inputdata references do not exist in the uploaded zip
        csv_file = tmp_path / "smarttable_multiple_missing.csv"
        csv_file.write_text(
            """File,Second File,Name
inputdata1,inputdata2,basic/dataName
missing/first.dat,missing/second.dat,Sample1
missing/third.dat,,Sample2""",
        )
        output_dir = tmp_path / "output"
        extracted_files = [Path("/temp/present.dat")]
        st_file = SmartTableFile(csv_file)
        caplog.set_level("ERROR", logger="rdetoolkit.invoicefile._smarttable")

        # When: generating row CSV files encounters multiple unresolved references
        with pytest.raises(StructuredError) as exc_info:
            st_file.generate_row_csvs_with_file_mapping(output_dir, extracted_files)

        # Then: the exception uses the first representative case and the log keeps all mismatches
        error = exc_info.value
        assert str(error) == "SmartTable row 3 references missing file in zip: inputdata1=first.dat"
        assert error.eobj == [
            (3, "inputdata1", "missing/first.dat"),
            (3, "inputdata2", "missing/second.dat"),
            (4, "inputdata1", "missing/third.dat"),
        ]
        assert "row 3: inputdata1=missing/first.dat" in caplog.text
        assert "row 3: inputdata2=missing/second.dat" in caplog.text
        assert "row 4: inputdata1=missing/third.dat" in caplog.text

    def test_generate_row_csvs_with_file_mapping_reports_display_row_number__tc_bv_001(self, tmp_path):
        """TC-BV-001: Missing file in the second data row reports SmartTable row 4."""
        # Given: the first data row resolves and the second data row is missing its referenced file
        csv_file = tmp_path / "smarttable_row_number.csv"
        csv_file.write_text(
            """File,Name
inputdata1,basic/dataName
present.dat,Sample1
missing.dat,Sample2""",
        )
        output_dir = tmp_path / "output"
        extracted_files = [Path("/temp/present.dat")]
        st_file = SmartTableFile(csv_file)

        # When: generating row CSV files checks the second data row
        with pytest.raises(StructuredError) as exc_info:
            st_file.generate_row_csvs_with_file_mapping(output_dir, extracted_files)

        # Then: the reported row number matches the displayed SmartTable row number
        assert str(exc_info.value) == "SmartTable row 4 references missing file in zip: inputdata1=missing.dat"

    def test_generate_row_csvs_no_extracted_files(self, tmp_path):
        """Test generating CSV files without extracted files."""
        csv_file = tmp_path / "smarttable_test.csv"
        csv_content = """Name,Value
basic/dataName,custom/value
Sample1,Value1
Sample2,Value2"""
        csv_file.write_text(csv_content)

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        st_file = SmartTableFile(csv_file)
        result = st_file.generate_row_csvs_with_file_mapping(output_dir, None)

        assert len(result) == 2

        for i, (csv_path, related_files) in enumerate(result):
            assert csv_path.name == f"fsmarttable_test_{i:04d}.csv"
            assert csv_path.exists()
            assert related_files == ()


    def test_read_table_validation(self, tmp_path):
        """Test reading table with validation."""
        csv_file = tmp_path / "smarttable_test.csv"
        csv_content = """Name,Value
basic/dataName,custom/value
Sample1,Value1"""
        csv_file.write_text(csv_content)

        st_file = SmartTableFile(csv_file)
        result = st_file.read_table()

        assert len(result) == 1
        assert list(result.columns) == ['basic/dataName', 'custom/value']

    def test_read_table_invalid_mapping_keys(self, tmp_path):
        """Test reading table without proper mapping keys."""
        csv_file = tmp_path / "smarttable_invalid.csv"
        csv_content = """Name,Value
invalid_key,another_invalid
Sample1,Value1"""
        csv_file.write_text(csv_content)

        st_file = SmartTableFile(csv_file)

        with pytest.raises(StructuredError) as exc_info:
            st_file.read_table()

        assert "must have mapping keys with prefixes" in str(exc_info.value)
