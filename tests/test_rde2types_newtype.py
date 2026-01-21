"""Tests for enhanced type safety in rde2types module.

This module tests NewType definitions, ValidatedPath hierarchy,
and FileGroup collection types introduced in Issue #335.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.models.config import Config
from rdetoolkit.models.rde2types import (
    CsvFile,
    ExcelFile,
    FileGroup,
    JsonFile,
    ProcessedFileGroup,
    RdeDatasetPaths,
    RdeInputDirPaths,
    RdeOutputResourcePath,
    ValidatedDirectory,
    ValidatedPath,
    ZipFile,
    create_excel_invoice_path,
    create_input_data_dir,
    create_output_dir,
    create_smarttable_path,
    create_zip_file_path,
)


class TestNewTypeHelpers:
    """Test NewType helper functions."""

    def test_create_zip_file_path_from_path(self) -> None:
        """Test creating ZipFilePath from Path object."""
        path = Path("test.zip")
        zip_path = create_zip_file_path(path)
        assert isinstance(zip_path, Path)
        assert str(zip_path) == "test.zip"

    def test_create_zip_file_path_from_string(self) -> None:
        """Test creating ZipFilePath from string."""
        zip_path = create_zip_file_path("test.zip")
        assert isinstance(zip_path, Path)
        assert str(zip_path) == "test.zip"

    def test_create_excel_invoice_path(self) -> None:
        """Test creating ExcelInvoicePath."""
        excel_path = create_excel_invoice_path("invoice.xlsx")
        assert isinstance(excel_path, Path)
        assert str(excel_path) == "invoice.xlsx"

    def test_create_smarttable_path(self) -> None:
        """Test creating SmartTablePath."""
        st_path = create_smarttable_path("table.csv")
        assert isinstance(st_path, Path)

    def test_create_directory_paths(self) -> None:
        """Test creating directory path NewTypes."""
        input_dir = create_input_data_dir("input")
        output_dir = create_output_dir("output")
        assert isinstance(input_dir, Path)
        assert isinstance(output_dir, Path)


class TestValidatedPath:
    """Test ValidatedPath base class."""

    def test_create_validated_path(self) -> None:
        """Test creating basic ValidatedPath."""
        vpath = ValidatedPath(Path("test.txt"))
        assert vpath.path == Path("test.txt")

    def test_validated_path_immutable(self) -> None:
        """Test that ValidatedPath is immutable."""
        vpath = ValidatedPath(Path("test.txt"))
        with pytest.raises((AttributeError, TypeError)):
            vpath.path = Path("other.txt")  # type: ignore[misc]

    def test_validated_path_str(self) -> None:
        """Test string representation."""
        vpath = ValidatedPath(Path("test.txt"))
        assert str(vpath) == "test.txt"

    def test_validated_path_fspath(self) -> None:
        """Test path-like protocol."""
        vpath = ValidatedPath(Path("test.txt"))
        assert vpath.__fspath__() == "test.txt"

    def test_validated_path_from_string(self) -> None:
        """Test creating from string."""
        vpath = ValidatedPath.from_string("test.txt")
        assert vpath.path == Path("test.txt")

    def test_validated_path_from_parts(self) -> None:
        """Test creating from path parts."""
        vpath = ValidatedPath.from_parts("dir", "subdir", "file.txt")
        assert vpath.path == Path("dir/subdir/file.txt")

    def test_validated_path_type_error(self) -> None:
        """Test that non-Path raises TypeError."""
        with pytest.raises(TypeError, match="path must be a Path instance"):
            ValidatedPath("not_a_path")  # type: ignore[arg-type]


class TestZipFile:
    """Test ZipFile validated path."""

    def test_valid_zip_file(self) -> None:
        """Test valid ZIP file path."""
        zip_file = ZipFile(Path("archive.zip"))
        assert zip_file.path.suffix == ".zip"

    def test_zip_file_case_insensitive(self) -> None:
        """Test that extension check is case insensitive."""
        zip_file = ZipFile(Path("archive.ZIP"))
        assert zip_file.path == Path("archive.ZIP")

    def test_invalid_zip_file_extension(self) -> None:
        """Test that non-ZIP extension raises ValueError."""
        with pytest.raises(ValueError, match="Not a ZIP file"):
            ZipFile(Path("data.txt"))

    def test_zip_file_immutable(self) -> None:
        """Test ZIP file is immutable."""
        zip_file = ZipFile(Path("archive.zip"))
        with pytest.raises((AttributeError, TypeError)):
            zip_file.path = Path("other.zip")  # type: ignore[misc]


class TestExcelFile:
    """Test ExcelFile validated path."""

    def test_valid_xlsx_file(self) -> None:
        """Test valid .xlsx file."""
        excel = ExcelFile(Path("invoice.xlsx"))
        assert excel.path.suffix == ".xlsx"

    def test_valid_xls_file(self) -> None:
        """Test valid .xls file."""
        excel = ExcelFile(Path("invoice.xls"))
        assert excel.path.suffix == ".xls"

    def test_valid_xlsm_file(self) -> None:
        """Test valid .xlsm file."""
        excel = ExcelFile(Path("invoice.xlsm"))
        assert excel.path.suffix == ".xlsm"

    def test_excel_case_insensitive(self) -> None:
        """Test case insensitive extension matching."""
        excel = ExcelFile(Path("invoice.XLSX"))
        assert excel.path == Path("invoice.XLSX")

    def test_invalid_excel_extension(self) -> None:
        """Test that invalid extension raises ValueError."""
        with pytest.raises(ValueError, match="Not an Excel file"):
            ExcelFile(Path("data.csv"))


class TestCsvFile:
    """Test CsvFile validated path."""

    def test_valid_csv_file(self) -> None:
        """Test valid CSV file path."""
        csv = CsvFile(Path("data.csv"))
        assert csv.path.suffix == ".csv"

    def test_csv_case_insensitive(self) -> None:
        """Test case insensitive extension."""
        csv = CsvFile(Path("data.CSV"))
        assert csv.path == Path("data.CSV")

    def test_invalid_csv_extension(self) -> None:
        """Test invalid extension raises error."""
        with pytest.raises(ValueError, match="Not a CSV file"):
            CsvFile(Path("data.txt"))


class TestJsonFile:
    """Test JsonFile validated path."""

    def test_valid_json_file(self) -> None:
        """Test valid JSON file path."""
        json_file = JsonFile(Path("config.json"))
        assert json_file.path.suffix == ".json"

    def test_invalid_json_extension(self) -> None:
        """Test invalid extension raises error."""
        with pytest.raises(ValueError, match="Not a JSON file"):
            JsonFile(Path("config.txt"))


class TestValidatedDirectory:
    """Test ValidatedDirectory class."""

    def test_validated_directory_no_check(self, tmp_path: Path) -> None:
        """Test directory without existence check."""
        vdir = ValidatedDirectory(tmp_path, must_exist=False)
        assert vdir.path == tmp_path

    def test_validated_directory_exists(self, tmp_path: Path) -> None:
        """Test directory with existence check passes for existing dir."""
        vdir = ValidatedDirectory(tmp_path, must_exist=True)
        assert vdir.path == tmp_path

    def test_validated_directory_not_exists(self, tmp_path: Path) -> None:
        """Test directory existence check fails for non-existent dir."""
        non_existent = tmp_path / "does_not_exist"
        with pytest.raises(ValueError, match="Directory does not exist"):
            ValidatedDirectory(non_existent, must_exist=True)

    def test_validated_directory_not_a_dir(self, tmp_path: Path) -> None:
        """Test directory check fails for file."""
        file_path = tmp_path / "file.txt"
        file_path.touch()
        with pytest.raises(ValueError, match="Path is not a directory"):
            ValidatedDirectory(file_path, must_exist=True)


class TestFileGroup:
    """Test FileGroup collection type."""

    def test_create_empty_file_group(self) -> None:
        """Test creating empty FileGroup."""
        group = FileGroup.empty()
        assert group.file_count == 0
        assert not group.has_zip_files
        assert not group.has_excel_invoices

    def test_create_file_group_basic(self) -> None:
        """Test creating basic FileGroup."""
        raw_files = (Path("file1.txt"), Path("file2.txt"))
        group = FileGroup(raw_files=raw_files)
        assert group.file_count == 2
        assert len(group.raw_files) == 2

    def test_file_group_with_typed_files(self) -> None:
        """Test FileGroup with typed file collections."""
        zip_files = (ZipFile(Path("archive.zip")),)
        excel_files = (ExcelFile(Path("invoice.xlsx")),)
        group = FileGroup(
            raw_files=(),
            zip_files=zip_files,
            excel_invoices=excel_files,
        )
        assert group.has_zip_files
        assert group.has_excel_invoices

    def test_file_group_all_files(self) -> None:
        """Test all_files property."""
        zip_files = (ZipFile(Path("archive.zip")),)
        excel_files = (ExcelFile(Path("invoice.xlsx")),)
        other_files = (Path("readme.txt"),)
        group = FileGroup(
            raw_files=(Path("data.txt"),),
            zip_files=zip_files,
            excel_invoices=excel_files,
            other_files=other_files,
        )
        all_files = group.all_files
        assert len(all_files) == 4

    def test_file_group_from_paths_auto_classify(self) -> None:
        """Test creating FileGroup with auto-classification."""
        paths = [
            Path("data.txt"),
            Path("archive.zip"),
            Path("invoice.xlsx"),
            Path("other.pdf"),
        ]
        group = FileGroup.from_paths(paths, auto_classify=True)
        assert len(group.zip_files) == 1
        assert len(group.excel_invoices) == 1
        assert len(group.other_files) == 2  # data.txt and other.pdf

    def test_file_group_from_paths_no_classify(self) -> None:
        """Test creating FileGroup without auto-classification."""
        paths = [Path("data.txt"), Path("archive.zip")]
        group = FileGroup.from_paths(paths, auto_classify=False)
        assert len(group.raw_files) == 2
        assert len(group.zip_files) == 0

    def test_file_group_immutable(self) -> None:
        """Test that FileGroup is immutable."""
        group = FileGroup(raw_files=(Path("file.txt"),))
        with pytest.raises((AttributeError, TypeError)):
            group.raw_files = (Path("other.txt"),)  # type: ignore[misc]

    def test_file_group_type_validation(self) -> None:
        """Test that FileGroup validates collection types."""
        with pytest.raises(TypeError, match="must be a tuple"):
            FileGroup(raw_files=[Path("file.txt")])  # type: ignore[arg-type]


class TestProcessedFileGroup:
    """Test ProcessedFileGroup collection type."""

    def test_create_processed_file_group(self) -> None:
        """Test creating ProcessedFileGroup."""
        group = ProcessedFileGroup(
            unzipped_files=(Path("file1.txt"), Path("file2.txt")),
            excel_invoice=ExcelFile(Path("invoice.xlsx")),
        )
        assert group.has_excel_invoice
        assert not group.has_smarttable
        assert group.total_file_count == 3

    def test_processed_file_group_with_smarttable(self) -> None:
        """Test ProcessedFileGroup with SmartTable CSV."""
        group = ProcessedFileGroup(
            smarttable_csv=CsvFile(Path("smart_table.csv")),
        )
        assert group.has_smarttable
        assert group.total_file_count == 1

    def test_processed_file_group_empty(self) -> None:
        """Test empty ProcessedFileGroup."""
        group = ProcessedFileGroup()
        assert not group.has_excel_invoice
        assert not group.has_smarttable
        assert group.total_file_count == 0


class TestIntegration:
    """Integration tests for type safety improvements."""

    def test_end_to_end_file_processing(self, tmp_path: Path) -> None:
        """Test complete workflow with new types."""
        # Create test files
        zip_file = tmp_path / "archive.zip"
        excel_file = tmp_path / "invoice.xlsx"
        csv_file = tmp_path / "data.csv"

        zip_file.touch()
        excel_file.touch()
        csv_file.touch()

        # Create FileGroup
        paths = [zip_file, excel_file, csv_file]
        group = FileGroup.from_paths(paths, auto_classify=True)

        assert group.has_zip_files
        assert group.has_excel_invoices
        assert group.file_count == 3

        # Create ProcessedFileGroup
        processed = ProcessedFileGroup(
            unzipped_files=(csv_file,),
            excel_invoice=ExcelFile(excel_file),
        )

        assert processed.has_excel_invoice
        assert processed.total_file_count == 2


class TestRdeDatasetPaths:
    """Test RdeDatasetPaths class (Issue #207)."""

    def test_smarttable_row_data_property_none(self, tmp_path: Path) -> None:
        """Test smarttable_row_data property returns None when not set."""
        input_paths = RdeInputDirPaths(
            inputdata=tmp_path / "input",
            invoice=tmp_path / "invoice",
            tasksupport=tmp_path / "tasksupport",
        )

        output_paths = RdeOutputResourcePath(
            raw=tmp_path / "raw",
            nonshared_raw=tmp_path / "nonshared_raw",
            rawfiles=(),
            struct=tmp_path / "struct",
            main_image=tmp_path / "main_image",
            other_image=tmp_path / "other_image",
            meta=tmp_path / "meta",
            thumbnail=tmp_path / "thumbnail",
            logs=tmp_path / "logs",
            invoice=tmp_path / "invoice",
            invoice_schema_json=tmp_path / "schema.json",
            invoice_org=tmp_path / "invoice_org",
            smarttable_row_data=None,
        )

        dataset_paths = RdeDatasetPaths(input_paths, output_paths)
        assert dataset_paths.smarttable_row_data is None

    def test_smarttable_row_data_property_with_data(self, tmp_path: Path) -> None:
        """Test smarttable_row_data property returns data from output_paths."""
        input_paths = RdeInputDirPaths(
            inputdata=tmp_path / "input",
            invoice=tmp_path / "invoice",
            tasksupport=tmp_path / "tasksupport",
        )

        row_data: dict[str, Any] = {
            "basic/dataName": "test_data",
            "sample/name": "sample_001",
            "measurement/temperature": "25.5",
        }

        output_paths = RdeOutputResourcePath(
            raw=tmp_path / "raw",
            nonshared_raw=tmp_path / "nonshared_raw",
            rawfiles=(),
            struct=tmp_path / "struct",
            main_image=tmp_path / "main_image",
            other_image=tmp_path / "other_image",
            meta=tmp_path / "meta",
            thumbnail=tmp_path / "thumbnail",
            logs=tmp_path / "logs",
            invoice=tmp_path / "invoice",
            invoice_schema_json=tmp_path / "schema.json",
            invoice_org=tmp_path / "invoice_org",
            smarttable_row_data=row_data,
        )

        dataset_paths = RdeDatasetPaths(input_paths, output_paths)

        # Test that the property returns the same data
        assert dataset_paths.smarttable_row_data == row_data
        assert dataset_paths.smarttable_row_data is not None

        # Test accessing specific fields
        assert dataset_paths.smarttable_row_data["basic/dataName"] == "test_data"
        assert dataset_paths.smarttable_row_data["sample/name"] == "sample_001"
        assert dataset_paths.smarttable_row_data["measurement/temperature"] == "25.5"

    def test_smarttable_row_data_property_dict_get_pattern(self, tmp_path: Path) -> None:
        """Test using .get() pattern for safe access to row data."""
        input_paths = RdeInputDirPaths(
            inputdata=tmp_path / "input",
            invoice=tmp_path / "invoice",
            tasksupport=tmp_path / "tasksupport",
        )

        row_data: dict[str, Any] = {"basic/dataName": "test"}

        output_paths = RdeOutputResourcePath(
            raw=tmp_path / "raw",
            nonshared_raw=tmp_path / "nonshared_raw",
            rawfiles=(),
            struct=tmp_path / "struct",
            main_image=tmp_path / "main_image",
            other_image=tmp_path / "other_image",
            meta=tmp_path / "meta",
            thumbnail=tmp_path / "thumbnail",
            logs=tmp_path / "logs",
            invoice=tmp_path / "invoice",
            invoice_schema_json=tmp_path / "schema.json",
            invoice_org=tmp_path / "invoice_org",
            smarttable_row_data=row_data,
        )

        dataset_paths = RdeDatasetPaths(input_paths, output_paths)

        # Test safe access pattern from docstring example
        if dataset_paths.smarttable_row_data:
            sample_name = dataset_paths.smarttable_row_data.get("sample/name", "")
            data_name = dataset_paths.smarttable_row_data.get("basic/dataName", "")

            assert sample_name == ""  # Not in row_data
            assert data_name == "test"
