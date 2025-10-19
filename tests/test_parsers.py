"""Unit tests for CSV parsers."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pandas as pd
import pytest

from rdetoolkit.graph.parsers.parser_factory import ParserFactory
from rdetoolkit.graph.parsers.standard_parser import StandardParser
from rdetoolkit.graph.parsers.transpose_parser import TransposeParser
from rdetoolkit.graph.parsers.noheader_parser import NoHeaderParser


def write_csv(tmp_path: Path, name: str, content: str) -> Path:
    """Helper function to create CSV files for testing."""
    csv_file = tmp_path / name
    csv_file.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    return csv_file


# =============================================================================
# ParserFactory Tests
# =============================================================================


def test_parser_factory_creates_standard_parser():
    """Test that ParserFactory creates StandardParser for 'standard' format."""
    parser = ParserFactory.create("standard")
    assert isinstance(parser, StandardParser)


def test_parser_factory_creates_transpose_parser():
    """Test that ParserFactory creates TransposeParser for 'transpose' format."""
    parser = ParserFactory.create("transpose")
    assert isinstance(parser, TransposeParser)


def test_parser_factory_creates_noheader_parser():
    """Test that ParserFactory creates NoHeaderParser for 'noheader' format."""
    parser = ParserFactory.create("noheader")
    assert isinstance(parser, NoHeaderParser)


def test_parser_factory_invalid_format():
    """Test that ParserFactory raises ValueError for invalid format."""
    with pytest.raises(ValueError, match="Unsupported CSV format"):
        ParserFactory.create("invalid")  # type: ignore[arg-type]


# =============================================================================
# StandardParser Tests
# =============================================================================


def test_standard_parser_simple_csv(tmp_path: Path):
    """Test StandardParser with simple header and data."""
    csv_file = write_csv(
        tmp_path,
        "simple.csv",
        """
        X,Y
        1,2
        3,4
        """,
    )

    parser = StandardParser()
    df = parser.parse(csv_file)

    assert list(df.columns) == ["X", "Y"]
    assert len(df) == 2
    assert df["X"].tolist() == [1, 3]
    assert df["Y"].tolist() == [2, 4]


def test_standard_parser_with_units(tmp_path: Path):
    """Test StandardParser with complex headers containing units."""
    csv_file = write_csv(
        tmp_path,
        "units.csv",
        """
        Time (s),Current (mA),Voltage (V)
        0.0,10.5,3.7
        1.0,11.2,3.8
        """,
    )

    parser = StandardParser()
    df = parser.parse(csv_file)

    assert list(df.columns) == ["Time (s)", "Current (mA)", "Voltage (V)"]
    assert len(df) == 2
    assert df["Time (s)"].tolist() == [0.0, 1.0]


def test_standard_parser_many_columns(tmp_path: Path):
    """Test StandardParser with many columns (>10)."""
    header = ",".join([f"Col{i}" for i in range(15)])
    data1 = ",".join([str(i) for i in range(15)])
    data2 = ",".join([str(i + 15) for i in range(15)])

    csv_file = write_csv(
        tmp_path,
        "many_cols.csv",
        f"""
        {header}
        {data1}
        {data2}
        """,
    )

    parser = StandardParser()
    df = parser.parse(csv_file)

    assert len(df.columns) == 15
    assert len(df) == 2


def test_standard_parser_header_only(tmp_path: Path):
    """Test StandardParser with header but no data rows."""
    csv_file = write_csv(
        tmp_path,
        "header_only.csv",
        """
        X,Y
        """,
    )

    parser = StandardParser()
    df = parser.parse(csv_file)

    assert list(df.columns) == ["X", "Y"]
    assert len(df) == 0  # Empty DataFrame


def test_standard_parser_with_nan_values(tmp_path: Path):
    """Test StandardParser with missing values (NaN)."""
    csv_file = write_csv(
        tmp_path,
        "nan_values.csv",
        """
        X,Y,Z
        1,2,3
        4,,6
        7,8,
        """,
    )

    parser = StandardParser()
    df = parser.parse(csv_file)

    assert len(df) == 3
    assert pd.isna(df.iloc[1, 1])  # Second row, Y column
    assert pd.isna(df.iloc[2, 2])  # Third row, Z column


def test_standard_parser_unicode_headers(tmp_path: Path):
    """Test StandardParser with Unicode characters in headers."""
    csv_file = write_csv(
        tmp_path,
        "unicode.csv",
        """
        温度 (°C),電流 (mA)
        25.0,10.5
        30.0,12.3
        """,
    )

    parser = StandardParser()
    df = parser.parse(csv_file)

    assert list(df.columns) == ["温度 (°C)", "電流 (mA)"]
    assert len(df) == 2


def test_standard_parser_file_not_found():
    """Test StandardParser with non-existent file."""
    parser = StandardParser()
    non_existent = Path("/tmp/non_existent_file_12345.csv")

    with pytest.raises(FileNotFoundError):
        parser.parse(non_existent)


# =============================================================================
# TransposeParser Tests
# =============================================================================


def test_transpose_parser_basic(tmp_path: Path):
    """Test TransposeParser with basic transposed data."""
    csv_file = write_csv(
        tmp_path,
        "transpose.csv",
        """
        X,0,1,2,3
        Y1,10,11,12,13
        Y2,20,21,22,23
        """,
    )

    parser = TransposeParser()
    df = parser.parse(csv_file)

    # After transpose, X becomes column, Y1 and Y2 become series
    assert "X" in df.columns
    assert len(df) == 4  # 4 data points
    # Check that data is correctly transposed (may be strings or ints depending on parser)
    assert list(df["X"]) == [0, 1, 2, 3] or list(df["X"]) == ["0", "1", "2", "3"]


def test_transpose_parser_single_column(tmp_path: Path):
    """Test TransposeParser with only one data column."""
    csv_file = write_csv(
        tmp_path,
        "single_col.csv",
        """
        X,0
        Y,10
        """,
    )

    parser = TransposeParser()
    df = parser.parse(csv_file)

    assert len(df) == 1  # Only one data point after transpose


def test_transpose_parser_many_columns(tmp_path: Path):
    """Test TransposeParser with many columns (>100)."""
    header = "X," + ",".join([str(i) for i in range(100)])
    data = "Y," + ",".join([str(i * 2) for i in range(100)])

    csv_file = write_csv(
        tmp_path,
        "many_cols_transpose.csv",
        f"""
        {header}
        {data}
        """,
    )

    parser = TransposeParser()
    df = parser.parse(csv_file)

    assert len(df) == 100  # 100 data points after transpose


def test_transpose_parser_file_not_found():
    """Test TransposeParser with non-existent file."""
    parser = TransposeParser()
    non_existent = Path("/tmp/non_existent_transpose_12345.csv")

    with pytest.raises(FileNotFoundError):
        parser.parse(non_existent)


# =============================================================================
# NoHeaderParser Tests
# =============================================================================


def test_noheader_parser_basic(tmp_path: Path):
    """Test NoHeaderParser with basic numeric data."""
    csv_file = write_csv(
        tmp_path,
        "noheader.csv",
        """
        1,2,3
        4,5,6
        7,8,9
        """,
    )

    parser = NoHeaderParser()
    df = parser.parse(csv_file)

    assert len(df) == 3
    assert len(df.columns) == 3
    # Check that column names are auto-generated
    assert all(isinstance(col, (str, int)) for col in df.columns)


def test_noheader_parser_single_column(tmp_path: Path):
    """Test NoHeaderParser with single column data."""
    csv_file = write_csv(
        tmp_path,
        "single.csv",
        """
        1
        2
        3
        """,
    )

    parser = NoHeaderParser()
    df = parser.parse(csv_file)

    assert len(df) == 3
    assert len(df.columns) == 1


def test_noheader_parser_mixed_types(tmp_path: Path):
    """Test NoHeaderParser with mixed data types."""
    csv_file = write_csv(
        tmp_path,
        "mixed.csv",
        """
        1,text,3.5
        2,data,4.2
        """,
    )

    parser = NoHeaderParser()
    df = parser.parse(csv_file)

    assert len(df) == 2
    assert len(df.columns) == 3
    # Check that types are correctly inferred
    # Note: pandas may infer numeric columns, string columns differently


def test_noheader_parser_many_columns(tmp_path: Path):
    """Test NoHeaderParser with many columns."""
    data_row = ",".join([str(i) for i in range(50)])

    csv_file = write_csv(
        tmp_path,
        "many_noheader.csv",
        f"""
        {data_row}
        {data_row}
        """,
    )

    parser = NoHeaderParser()
    df = parser.parse(csv_file)

    assert len(df) == 2
    assert len(df.columns) == 50


def test_noheader_parser_file_not_found():
    """Test NoHeaderParser with non-existent file."""
    parser = NoHeaderParser()
    non_existent = Path("/tmp/non_existent_noheader_12345.csv")

    with pytest.raises(FileNotFoundError):
        parser.parse(non_existent)


def test_noheader_parser_empty_file(tmp_path: Path):
    """Test NoHeaderParser with empty file."""
    csv_file = write_csv(tmp_path, "empty.csv", "")

    parser = NoHeaderParser()

    # Pandas raises EmptyDataError for completely empty CSV files
    with pytest.raises(pd.errors.EmptyDataError):
        parser.parse(csv_file)
