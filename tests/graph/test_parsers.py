from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from rdetoolkit.graph.exceptions import InvalidCSVFormatError, InvalidMetadataError
from rdetoolkit.graph.models import CSVFormat
from rdetoolkit.graph.parsers import CSVParser


class TestIsHeaderLine:
    """Test _is_header_line() header detection logic."""

    def test_detects_non_numeric_line_as_header(self):
        assert CSVParser._is_header_line("voltage,current,power") is True
        assert CSVParser._is_header_line("x,y,z") is True
        assert CSVParser._is_header_line("cycle_number,capacity") is True

    def test_detects_all_numeric_line_as_data(self):
        assert CSVParser._is_header_line("1.5,2.3,4.7") is False
        assert CSVParser._is_header_line("0,0,0") is False
        assert CSVParser._is_header_line("-1.2,3.4,-5.6") is False

    def test_handles_mixed_text_and_numbers(self):
        assert CSVParser._is_header_line("voltage (V),1.5") is True
        assert CSVParser._is_header_line("1cyc,2cyc,3cyc") is True

    def test_handles_empty_and_whitespace(self):
        assert CSVParser._is_header_line("") is True
        assert CSVParser._is_header_line("   ") is True
        assert CSVParser._is_header_line(",,,") is True


class TestDetectFormat:
    """Test _detect_format() CSV format detection."""

    def test_detects_single_header_format(self):
        """has_meta=False, data_start_line=2 → SINGLE_HEADER."""
        assert CSVParser._detect_format(has_meta=False, data_start_line=2) == CSVFormat.SINGLE_HEADER

    def test_detects_no_header_format(self):
        """has_meta=False, data_start_line=1 → NO_HEADER."""
        assert CSVParser._detect_format(has_meta=False, data_start_line=1) == CSVFormat.NO_HEADER

    def test_detects_meta_block_format(self):
        """has_meta=True → META_BLOCK regardless of data_start_line."""
        assert CSVParser._detect_format(has_meta=True, data_start_line=1) == CSVFormat.META_BLOCK
        assert CSVParser._detect_format(has_meta=True, data_start_line=2) == CSVFormat.META_BLOCK
        assert CSVParser._detect_format(has_meta=True, data_start_line=5) == CSVFormat.META_BLOCK

    def test_raises_on_unknown_format(self):
        """Unknown combinations raise InvalidCSVFormatError."""
        with pytest.raises(InvalidCSVFormatError, match="Unknown CSV format"):
            CSVParser._detect_format(has_meta=False, data_start_line=3)

        with pytest.raises(InvalidCSVFormatError, match="Unknown CSV format"):
            CSVParser._detect_format(has_meta=False, data_start_line=0)


class TestReadCSVWithMetadata:
    """Test _read_csv_with_metadata() metadata extraction."""

    def test_reads_file_with_metadata_block(self, tmp_path: Path):
        """CSV with comment block is parsed correctly."""
        csv_file = tmp_path / "with_meta.csv"
        csv_file.write_text(
            "#title,Test Graph\n"
            "#dimension,x,y\n"
            "#x,voltage,V\n"
            "#y,current,A\n"
            "#legend,1cyc,2cyc\n"
            "1.0,2.0,3.0\n"
            "4.0,5.0,6.0\n",
        )

        lines, meta_lines, data_start_line, has_meta = CSVParser._read_csv_with_metadata(csv_file)

        assert has_meta is True
        assert data_start_line == 6  # After 5 comment lines
        assert len(meta_lines) == 5
        assert meta_lines[0] == ["#title", "Test Graph"]
        assert meta_lines[1] == ["#dimension", "x", "y"]

    def test_reads_file_with_single_header(self, tmp_path: Path):
        """CSV with single header row is parsed correctly."""
        csv_file = tmp_path / "single_header.csv"
        csv_file.write_text(
            "voltage,current\n"
            "1.0,2.0\n"
            "3.0,4.0\n",
        )

        lines, meta_lines, data_start_line, has_meta = CSVParser._read_csv_with_metadata(csv_file)

        assert has_meta is False
        assert data_start_line == 2  # Header on line 1, data starts line 2
        assert len(meta_lines) == 0

    def test_reads_file_with_no_header(self, tmp_path: Path):
        """CSV with no header (all numeric) is parsed correctly."""
        csv_file = tmp_path / "no_header.csv"
        csv_file.write_text(
            "1.0,2.0,3.0\n"
            "4.0,5.0,6.0\n",
        )

        lines, meta_lines, data_start_line, has_meta = CSVParser._read_csv_with_metadata(csv_file)

        assert has_meta is False
        assert data_start_line == 1  # Data starts immediately
        assert len(meta_lines) == 0

    def test_skips_empty_lines(self, tmp_path: Path):
        """Empty lines at start are skipped."""
        csv_file = tmp_path / "with_empty.csv"
        csv_file.write_text(
            "\n"
            "\n"
            "#title,Test\n"
            "1.0,2.0\n",
        )

        lines, meta_lines, data_start_line, has_meta = CSVParser._read_csv_with_metadata(csv_file)

        assert has_meta is True
        assert data_start_line == 4  # After empty lines and comment
        assert len(meta_lines) == 1


class TestParseSingleHeader:
    """Test _parse_single_header() for single header CSV."""

    def test_parses_basic_csv_with_header(self, tmp_path: Path):
        """Basic CSV with header is parsed correctly."""
        csv_file = tmp_path / "basic.csv"
        csv_file.write_text(
            "voltage,current\n"
            "1.5,2.3\n"
            "3.7,4.1\n",
        )

        df, metadata = CSVParser._parse_single_header(csv_file)

        assert len(df) == 2
        assert list(df.columns) == ["voltage", "current"]
        assert metadata["xaxis_label"] == "voltage"
        assert metadata["yaxis_label"] == "current"
        assert metadata["mode"] == "x1y1x2y2"

    def test_handles_single_column_csv(self, tmp_path: Path):
        """Single column CSV has None for yaxis_label."""
        csv_file = tmp_path / "single_col.csv"
        csv_file.write_text(
            "voltage\n"
            "1.5\n"
            "3.7\n",
        )

        df, metadata = CSVParser._parse_single_header(csv_file)

        assert len(df) == 2
        assert list(df.columns) == ["voltage"]
        assert metadata["xaxis_label"] == "voltage"
        assert metadata["yaxis_label"] is None
        assert metadata["mode"] == "x1y1x2y2"


class TestParseNoHeader:
    """Test _parse_no_header() for CSV without header."""

    def test_generates_default_headers(self, tmp_path: Path):
        """Default headers are generated for no-header CSV."""
        csv_file = tmp_path / "no_header.csv"
        csv_file.write_text(
            "1.0,2.0,3.0\n"
            "4.0,5.0,6.0\n",
        )

        df, metadata = CSVParser._parse_no_header(csv_file, data_start_line=1)

        assert len(df) == 2
        assert list(df.columns) == ["x (arb.unit)", "y1 (arb.unit)", "y2 (arb.unit)"]
        assert metadata["xaxis_label"] == "x (arb.unit)"
        assert metadata["yaxis_label"] == "y (arb.unit)"
        assert metadata["mode"] == "x1y1x2y2"

    def test_handles_single_column(self, tmp_path: Path):
        """Single column gets x label only."""
        csv_file = tmp_path / "single.csv"
        csv_file.write_text(
            "1.0\n"
            "2.0\n",
        )

        df, metadata = CSVParser._parse_no_header(csv_file, data_start_line=1)

        assert len(df) == 2
        assert list(df.columns) == ["x (arb.unit)"]
        assert metadata["xaxis_label"] == "x (arb.unit)"

    def test_respects_data_start_line(self, tmp_path: Path):
        """data_start_line parameter controls skiprows."""
        csv_file = tmp_path / "skip.csv"
        csv_file.write_text(
            "# comment\n"
            "1.0,2.0\n"
            "3.0,4.0\n",
        )

        df, metadata = CSVParser._parse_no_header(csv_file, data_start_line=2)

        # skiprows=1 (data_start_line - 1), so first data line is skipped
        assert len(df) == 2  # Lines 2 and 3


class TestParseMetaBlock:
    """Test _parse_meta_block() for CSV with metadata block."""

    def test_parses_complete_metadata_block(self, tmp_path: Path):
        """Complete metadata block is parsed correctly."""
        csv_file = tmp_path / "meta_block.csv"
        csv_file.write_text(
            "#title,Battery Cycling\n"
            "#dimension,x,y\n"
            "#x,voltage,V\n"
            "#y,current,A\n"
            "#legend,1cyc,2cyc\n"
            "1.0,2.0,3.0\n"
            "4.0,5.0,6.0\n",
        )

        meta_lines = [
            ["#title", "Battery Cycling"],
            ["#dimension", "x", "y"],
            ["#x", "voltage", "V"],
            ["#y", "current", "A"],
            ["#legend", "1cyc", "2cyc"],
        ]

        df, metadata = CSVParser._parse_meta_block(csv_file, meta_lines, data_start_line=6)

        assert len(df) == 2
        assert list(df.columns) == ["voltage (V)", "1cyc (A)", "2cyc (A)"]
        assert metadata["xaxis_label"] == "voltage (V)"
        assert metadata["yaxis_label"] == "current (A)"
        assert metadata["mode"] == "x1y1x2y2"


class TestExtractMetadata:
    """Test _extract_metadata() validation and extraction."""

    def test_extracts_complete_metadata(self):
        """Complete metadata is extracted correctly."""
        meta_lines = [
            ["#title", "Test Graph"],
            ["#dimension", "x", "y"],
            ["#x", "voltage", "V"],
            ["#y", "current", "A"],
            ["#legend", "1cyc", "2cyc"],
        ]

        title, axis, legends, xaxis_label, yaxis_label = CSVParser._extract_metadata(meta_lines)

        assert title == "Test Graph"
        assert axis == ["x", "y"]
        assert legends == ["1cyc", "2cyc"]
        assert xaxis_label == "voltage (V)"
        assert yaxis_label == "current (A)"

    def test_uses_defaults_for_missing_optional_fields(self):
        """Missing optional fields use defaults."""
        meta_lines = [
            ["#dimension", "x", "y"],
            ["#x", "time"],
            ["#y", "value"],
        ]

        title, axis, legends, xaxis_label, yaxis_label = CSVParser._extract_metadata(meta_lines)

        assert title == "Graph"  # Default
        assert axis == ["x", "y"]
        assert legends == []  # No #legend tag
        assert xaxis_label == "time"
        assert yaxis_label == "value"

    def test_handles_missing_unit_in_axis_tags(self):
        """Axis tags without units work correctly."""
        meta_lines = [
            ["#dimension", "x", "y"],
            ["#x", "time"],
            ["#y", "value", "units"],
        ]

        title, axis, legends, xaxis_label, yaxis_label = CSVParser._extract_metadata(meta_lines)

        assert xaxis_label == "time"  # No unit
        assert yaxis_label == "value (units)"  # With unit

    def test_raises_on_insufficient_title_fields(self):
        """#title with insufficient fields raises InvalidMetadataError."""
        meta_lines = [
            ["#title"],  # Missing title value
        ]

        with pytest.raises(InvalidMetadataError, match="#title metadata requires"):
            CSVParser._extract_metadata(meta_lines)

    def test_raises_on_insufficient_dimension_fields(self):
        """#dimension with insufficient fields raises InvalidMetadataError."""
        meta_lines = [
            ["#dimension", "x"],  # Need at least 2 axis names
        ]

        with pytest.raises(InvalidMetadataError, match="#dimension metadata requires"):
            CSVParser._extract_metadata(meta_lines)

    def test_handles_insufficient_axis_fields_gracefully(self):
        """Axis tags with insufficient fields use defaults (Legacy behavior)."""
        meta_lines = [
            ["#dimension", "x", "y"],
            ["#x"],  # Missing axis label - should raise error
        ]

        # Legacy implementation would raise IndexError, but our implementation
        # uses _require_fields which raises InvalidMetadataError
        with pytest.raises(InvalidMetadataError, match="#x metadata requires"):
            CSVParser._extract_metadata(meta_lines)

    def test_raises_on_insufficient_legend_fields(self):
        """#legend with insufficient fields raises InvalidMetadataError."""
        meta_lines = [
            ["#legend"],  # No legend values
        ]

        with pytest.raises(InvalidMetadataError, match="#legend metadata requires"):
            CSVParser._extract_metadata(meta_lines)


class TestCSVParserIntegration:
    """Integration tests for CSVParser.parse() entry point."""

    def test_parses_meta_block_format(self, tmp_path: Path):
        """META_BLOCK format is detected and parsed."""
        csv_file = tmp_path / "meta.csv"
        csv_file.write_text(
            "#dimension,x,y\n"
            "#x,voltage,V\n"
            "#y,current,A\n"
            "#legend,1cyc\n"
            "1.0,2.0\n",
        )

        df, metadata = CSVParser.parse(csv_file)

        assert len(df) == 1
        assert "voltage" in df.columns[0]
        assert metadata["mode"] == "x1y1x2y2"

    def test_parses_single_header_format(self, tmp_path: Path):
        """SINGLE_HEADER format is detected and parsed."""
        csv_file = tmp_path / "header.csv"
        csv_file.write_text(
            "voltage,current\n"
            "1.0,2.0\n",
        )

        df, metadata = CSVParser.parse(csv_file)

        assert len(df) == 1
        assert list(df.columns) == ["voltage", "current"]
        assert metadata["xaxis_label"] == "voltage"

    def test_parses_no_header_format(self, tmp_path: Path):
        """NO_HEADER format is detected and parsed."""
        csv_file = tmp_path / "noheader.csv"
        csv_file.write_text(
            "1.0,2.0\n"
            "3.0,4.0\n",
        )

        df, metadata = CSVParser.parse(csv_file)

        assert len(df) == 2
        assert "arb.unit" in df.columns[0]
        assert metadata["xaxis_label"] == "x (arb.unit)"
