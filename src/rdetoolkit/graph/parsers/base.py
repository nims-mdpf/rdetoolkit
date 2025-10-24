"""CSV parser protocol and helper utilities."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from rdetoolkit.graph.exceptions import InvalidCSVFormatError, InvalidMetadataError
from rdetoolkit.graph.models import CSVFormat


@dataclass
class _MetadataAccumulator:
    """Helper for collecting metadata information from comment rows."""

    title: str = "Graph"
    axis_names: list[str] = field(default_factory=list)
    legends: list[str] = field(default_factory=list)
    xaxis_label: str = "x"
    yaxis_label: str = "y"

    def process_row(self, row: Sequence[str]) -> None:
        if not row:
            return

        tag = str(row[0]).lower()
        if tag == "#title":
            self.title = self._require_fields(row, 2, "#title")[1]
            return
        if tag == "#dimension":
            fields = self._require_fields(row, 3, "#dimension")
            self.axis_names = [fields[1], fields[2]]
            return
        if self._matches_axis_tag(tag, 0):
            self.xaxis_label = self._extract_axis_label(row, 0)
            return
        if self._matches_axis_tag(tag, 1):
            self.yaxis_label = self._extract_axis_label(row, 1)
            return
        if tag == "#legend":
            fields = self._require_fields(row, 2, "#legend")
            self.legends = list(fields[1:])

    def _matches_axis_tag(self, tag: str, index: int) -> bool:
        if len(self.axis_names) <= index:
            return False
        return tag == f"#{self.axis_names[index].lower()}"

    def _extract_axis_label(self, row: Sequence[str], index: int) -> str:
        axis_name = self.axis_names[index]
        axis_tag = f"#{axis_name}"
        fields = self._require_fields(row, 2, axis_tag)
        label = fields[1]
        if len(fields) > OPTIONAL_UNIT_INDEX and fields[OPTIONAL_UNIT_INDEX]:
            label = f"{label} ({fields[OPTIONAL_UNIT_INDEX]})"
        return label

    def _require_fields(
        self,
        row: Sequence[str],
        min_fields: int,
        tag: str,
    ) -> Sequence[str]:
        if len(row) < min_fields:
            msg = f"{tag} metadata requires at least {min_fields - 1} value(s)"
            raise InvalidMetadataError(msg)
        return row

    def to_tuple(self) -> tuple[str, list[str], list[str], str, str]:
        axis_names = self.axis_names or ["x", "y"]
        return self.title, axis_names, self.legends, self.xaxis_label, self.yaxis_label


class CSVParserProtocol(Protocol):
    """Protocol implemented by concrete CSV parser strategies."""

    def parse(self, csv_path: Path) -> pd.DataFrame:
        """Parse the CSV file at ``csv_path`` and return a DataFrame."""
        ...


class CSVParser:
    """Utility functions for parsing CSV files with legacy-compatible metadata."""

    DEFAULT_MODE = "x1y1x2y2"

    @staticmethod
    def parse(csv_path: str | Path) -> tuple[pd.DataFrame, dict[str, Any]]:
        """Parse CSV file and return DataFrame with accompanying metadata."""
        path = Path(csv_path)
        if not path.exists():
            msg = f"CSV file not found: {path}"
            raise FileNotFoundError(msg)

        lines, meta_lines, data_start_line, has_meta = CSVParser._read_csv_with_metadata(path)
        fmt = CSVParser._detect_format(has_meta=has_meta, data_start_line=data_start_line)

        if fmt is CSVFormat.META_BLOCK:
            df, metadata = CSVParser._parse_meta_block(path, meta_lines, data_start_line)
        elif fmt is CSVFormat.SINGLE_HEADER:
            df, metadata = CSVParser._parse_single_header(path)
        elif fmt is CSVFormat.NO_HEADER:
            df, metadata = CSVParser._parse_no_header(path, data_start_line=data_start_line)
        else:  # pragma: no cover - guarded by _detect_format
            msg = f"Unhandled CSV format: {fmt}"
            raise InvalidCSVFormatError(msg)

        metadata.setdefault("mode", CSVParser.DEFAULT_MODE)
        metadata["mode"] = CSVParser.DEFAULT_MODE
        return df, metadata

    @staticmethod
    def _is_header_line(line: str) -> bool:
        """Return True if ``line`` looks like a header (contains text)."""
        if not line or not line.strip():
            return True

        tokens = [token.strip() for token in line.split(",")]
        if not tokens or all(token == "" for token in tokens):
            return True

        for token in tokens:
            if token == "":
                return True
            try:
                float(token)
            except ValueError:
                return True
        return False

    @staticmethod
    def _read_csv_with_metadata(
        csv_path: Path,
    ) -> tuple[list[str], list[list[str]], int, bool]:
        """Read raw CSV lines and extract metadata comment block."""
        text = csv_path.read_text(encoding="utf-8")
        lines = text.splitlines()

        meta_lines: list[list[str]] = []
        data_start_line = len(lines) + 1
        has_meta = False

        for index, raw_line in enumerate(lines, start=1):
            stripped = raw_line.strip()
            if not stripped:
                continue

            if stripped.startswith("#"):
                meta_lines.append(next(csv.reader([stripped])))
                has_meta = True
                continue

            data_start_line = (
                index + 1 if CSVParser._is_header_line(stripped) else index
            )
            break
        else:
            data_start_line = len(lines) + 1

        return lines, meta_lines, data_start_line, has_meta

    @staticmethod
    def _detect_format(*, has_meta: bool, data_start_line: int) -> CSVFormat:
        """Determine CSV format from metadata flags and first data line."""
        if has_meta:
            return CSVFormat.META_BLOCK
        if data_start_line == SINGLE_HEADER_LINE:
            return CSVFormat.SINGLE_HEADER
        if data_start_line == NO_HEADER_LINE:
            return CSVFormat.NO_HEADER
        msg = f"Unknown CSV format (has_meta={has_meta}, data_start_line={data_start_line})"
        raise InvalidCSVFormatError(msg)

    @staticmethod
    def _parse_single_header(csv_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
        df = pd.read_csv(csv_path)
        columns = list(df.columns)

        xaxis_label = columns[0] if columns else "x"
        yaxis_label = columns[1] if len(columns) > 1 else None
        legends = [CSVParser._parse_label_and_unit(col)[0] for col in columns[1:]]

        metadata = {
            "title": csv_path.stem,
            "legends": legends,
            "xaxis_label": xaxis_label,
            "yaxis_label": yaxis_label,
            "mode": CSVParser.DEFAULT_MODE,
        }
        return df, metadata

    @staticmethod
    def _parse_no_header(
        csv_path: Path,
        *,
        data_start_line: int,
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        skiprows = max(data_start_line - 1, 0)
        df = pd.read_csv(csv_path, skiprows=skiprows, header=None)

        column_count = len(df.columns)
        header = ["x (arb.unit)"]
        if column_count > 1:
            header.extend([f"y{i} (arb.unit)" for i in range(1, column_count)])
        df.columns = header

        legends = [col.split(" (")[0] for col in header[1:]]
        yaxis_label = "y (arb.unit)" if column_count > 1 else None

        metadata = {
            "title": csv_path.stem,
            "legends": legends,
            "xaxis_label": header[0],
            "yaxis_label": yaxis_label,
            "mode": CSVParser.DEFAULT_MODE,
        }
        return df, metadata

    @staticmethod
    def _parse_meta_block(
        csv_path: Path,
        meta_lines: Sequence[Sequence[str]],
        data_start_line: int,
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        title, _axis, legends, xaxis_label, yaxis_label = CSVParser._extract_metadata(meta_lines)

        skiprows = max(data_start_line - 1, 0)
        df = pd.read_csv(csv_path, skiprows=skiprows, header=None)

        _, y_unit = CSVParser._split_label_and_unit(yaxis_label)
        legend_names = [value.strip() for value in legends if value.strip()]

        if not legend_names:
            legend_names = [f"y{i}" for i in range(1, df.shape[1])]

        y_column_count = max(df.shape[1] - 1, 0)
        if len(legend_names) < y_column_count:
            legend_names.extend(f"y{i}" for i in range(len(legend_names) + 1, y_column_count + 1))
        legend_names = legend_names[:y_column_count]

        header = [xaxis_label]
        for legend in legend_names:
            if y_unit:
                header.append(f"{legend} ({y_unit})")
            else:
                header.append(legend)

        if len(header) != len(df.columns):
            msg = "Metadata legends count does not match data columns"
            raise InvalidMetadataError(msg)

        df.columns = header

        metadata = {
            "title": title,
            "legends": legend_names,
            "xaxis_label": xaxis_label,
            "yaxis_label": yaxis_label,
            "mode": CSVParser.DEFAULT_MODE,
        }
        return df, metadata

    @staticmethod
    def _extract_metadata(
        meta_lines: Sequence[Sequence[str]],
    ) -> tuple[str, list[str], list[str], str, str]:
        context = _MetadataAccumulator()
        for row in meta_lines:
            context.process_row(row)
        return context.to_tuple()

    @staticmethod
    def _require_fields(tag: str, row: Sequence[str], min_fields: int) -> None:
        if len(row) < min_fields:
            msg = f"{tag} metadata requires at least {min_fields - 1} value(s)"
            raise InvalidMetadataError(msg)

    @staticmethod
    def _split_label_and_unit(label: str | None) -> tuple[str | None, str | None]:
        if not label:
            return label, None
        if "(" in label and label.endswith(")"):
            base, unit = label.rsplit("(", 1)
            return base.strip(), unit.strip(")\n \t")
        return label, None

    @staticmethod
    def _parse_label_and_unit(label: str) -> tuple[str, str]:
        if "(" in label and label.endswith(")"):
            base, unit = label.rsplit("(", 1)
            return base.strip(), unit.strip(")")
        return label, ""


__all__ = ["CSVParser", "CSVParserProtocol"]
SINGLE_HEADER_LINE = 2
NO_HEADER_LINE = 1
OPTIONAL_UNIT_INDEX = 2
