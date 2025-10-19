from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from rdetoolkit.core import detect_encoding
from rdetoolkit.graph.models import CSVFormat
from rdetoolkit.graph.exceptions import InvalidMetadataError, InvalidCSVFormatError


OPTIONAL_UNIT_INDEX = 2


@dataclass
class _MetadataContext:
    """Accumulator for parsing metadata comment blocks."""

    title: str = "Graph"
    axis_names: list[str] = field(default_factory=list)
    legends: list[str] = field(default_factory=list)
    xaxis_label: str = "x"
    yaxis_label: str = "y"

    def process_row(self, row: list[str]) -> None:
        """Process a single metadata row."""
        if not row:
            return

        tag = row[0]
        if tag == "#title":
            self.title = self._require_fields(row, 2, "#title")[1]
            return
        if tag == "#dimension":
            fields = self._require_fields(row, 3, "#dimension")
            self.axis_names = fields[1:3]
            return
        if self._matches_axis_tag(tag, 0):
            self.xaxis_label = self._extract_axis_label(row, 0)
            return
        if self._matches_axis_tag(tag, 1):
            self.yaxis_label = self._extract_axis_label(row, 1)
            return
        if tag == "#legend":
            self.legends = self._require_fields(row, 2, "#legend")[1:]

    def _matches_axis_tag(self, tag: str, index: int) -> bool:
        return len(self.axis_names) > index and tag == f"#{self.axis_names[index]}"

    def _extract_axis_label(self, row: list[str], index: int) -> str:
        axis_tag = f"#{self.axis_names[index]}"
        fields = self._require_fields(row, 2, axis_tag)
        label = fields[1]
        if len(fields) > OPTIONAL_UNIT_INDEX and fields[OPTIONAL_UNIT_INDEX]:
            label = f"{label} ({fields[OPTIONAL_UNIT_INDEX]})"
        return label

    def _require_fields(self, row: list[str], count: int, tag: str) -> list[str]:
        if len(row) < count:
            emsg = f"{tag} metadata requires at least {count - 1} arguments."
            raise InvalidMetadataError(emsg)
        return row

    def to_tuple(self) -> tuple[str, list[str], list[str], str, str]:
        return self.title, self.axis_names, self.legends, self.xaxis_label, self.yaxis_label


class CSVParser:

    @staticmethod
    def parse(csv_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
        """Parse CSV file and extract metadata.

        Args:
            csv_path: Path to CSV file

        Returns:
            tuple: (DataFrame, metadata dictionary)

        Note:
            This maintains backward compatibility with legacy process_csv().
            Metadata dict format:
            {
                'xaxis_label': str | None,
                'yaxis_label': str | None,
                'mode': str | None,
                ...
            }
        """
        _, meta_lines, data_start_line, has_meta = CSVParser._read_csv_with_metadata(csv_path)

        csv_format = CSVParser._detect_format(has_meta, data_start_line)

        handlers = {
            CSVFormat.META_BLOCK: lambda: CSVParser._parse_meta_block(
                csv_path, meta_lines, data_start_line,
            ),
            CSVFormat.SINGLE_HEADER: lambda: CSVParser._parse_single_header(csv_path),
            CSVFormat.NO_HEADER: lambda: CSVParser._parse_no_header(
                csv_path, data_start_line,
            ),
        }
        return handlers[csv_format]()

    @staticmethod
    def _read_csv_with_metadata(csv_path: Path) -> tuple[list[str], list[list[str]], int, bool]:
        try:
            enc = detect_encoding(str(csv_path))
        except Exception:
            enc = "utf-8"

        with open(csv_path, encoding=enc) as f:
            lines = f.readlines()

        meta_lines: list[list[str]] = []
        data_start_line = 0
        has_meta = False

        for i, line in enumerate(lines):
            if line.strip() == "":
                continue
            if line.startswith("#"):
                meta_lines.append(next(csv.reader([line])))
                has_meta = True
            elif i == 0 and CSVParser._is_header_line(line):
                data_start_line = 2
                break
            else:
                data_start_line = i + 1
                break

        return lines, meta_lines, data_start_line, has_meta

    @staticmethod
    def _is_header_line(line: str) -> bool:
        """Check if a line is a header line."""
        try:
            elements = line.strip().split(",")
            for elem in elements:
                float(elem)
            return False
        except ValueError:
            return True

    @staticmethod
    def _detect_format(has_meta: bool, data_start_line: int) -> CSVFormat:
        """Detect CSV format based on metadata and data start line.

        Legacy logic:
        - has_meta=False, data_start_line=2 → single_header
        - has_meta=False, data_start_line=1 → no_header
        - has_meta=True → meta_block

        Args:
            has_meta: Whether metadata lines exist
            data_start_line: Line number where data starts (1-indexed)

        Returns:
            CSVFormat enum value

        Raises:
            InvalidCSVFormatError: If format cannot be determined
        """
        default_start_line = 2
        if not has_meta and data_start_line == default_start_line:
            return CSVFormat.SINGLE_HEADER
        if not has_meta and data_start_line == 1:
            return CSVFormat.NO_HEADER
        if has_meta:
            return CSVFormat.META_BLOCK

        emsg = f"Unknown CSV format: has_meta={has_meta}, data_start_line={data_start_line}"
        raise InvalidCSVFormatError(emsg)

    @staticmethod
    def _parse_single_header(csv_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
        """Parse CSV with single header row.

        Args:
            csv_path: Path to CSV file

        Returns:
            tuple: (DataFrame, metadata dict)

        """
        default_mode = 'x1y1x2y2'
        df = pd.read_csv(csv_path, header=0)
        metadata = {
            'xaxis_label': df.columns[0],
            'yaxis_label': df.columns[1] if len(df.columns) > 1 else None,
            'mode': default_mode,
        }

        return df, metadata

    @staticmethod
    def _parse_no_header(csv_path: Path, data_start_line: int) -> tuple[pd.DataFrame, dict[str, Any]]:
        """Parse CSV with no header.

        Args:
            csv_path: Path to CSV file
            data_start_line: Line number where data starts

        Returns:
            tuple: (DataFrame, metadata dict)

        """
        skiprows = data_start_line - 1
        df = pd.read_csv(csv_path, skiprows=skiprows, header=None)

        header = ["x (arb.unit)"] + [f"y{i} (arb.unit)" for i in range(1, len(df.columns))]
        df.columns = header

        metadata = {
            'xaxis_label': header[0],
            'yaxis_label': "y (arb.unit)",
            'mode': 'x1y1x2y2',
        }

        return df, metadata

    @staticmethod
    def _parse_meta_block(
        csv_path: Path,
        meta_lines: list[list[str]],
        data_start_line: int,
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        """Parse CSV with metadata block.

        Args:
            csv_path: Path to CSV file
            meta_lines: Parsed metadata lines
            data_start_line: Line number where data starts

        Returns:
            tuple: (DataFrame, metadata dict)
        """
        title, axis, legends, xaxis_label, yaxis_label = CSVParser._extract_metadata(meta_lines)
        skiprows = data_start_line - 1
        df = pd.read_csv(csv_path, skiprows=skiprows, header=None)
        header = [xaxis_label] + [
            f"{legend} ({yaxis_label.split('(')[-1].strip(')')})"
            for legend in legends
        ]
        df.columns = header

        metadata = {
            'xaxis_label': xaxis_label,
            'yaxis_label': yaxis_label,
            'mode': 'x1y1x2y2',
        }

        return df, metadata

    @staticmethod
    def _extract_metadata(meta_lines: list[list[str]]) -> tuple[str, list[str], list[str], str, str]:
        """Extract metadata from comment lines.

        Legacy-compatible implementation.

        Args:
            meta_lines: Parsed metadata lines

        Returns:
            tuple: (title, axis, legends, xaxis_label, yaxis_label)

        Raises:
            InvalidMetadataError: If required metadata is missing

        """
        context = _MetadataContext()
        for row in meta_lines:
            context.process_row(row)
        return context.to_tuple()
