from __future__ import annotations

from pathlib import Path

import pandas as pd

from rdetoolkit.graph.parsers.base import CSVParserProtocol
from rdetoolkit.graph.parsers.noheader_parser import NoHeaderParser
from rdetoolkit.graph.parsers.standard_parser import StandardParser
from rdetoolkit.graph.parsers.transpose_parser import TransposeParser


class ParserFactory:
    """Factory for creating CSV parsers.

    Supports:
        - Explicit format selection
        - Auto-detection based on CSV structure (future enhancement)

    Example:
        >>> factory = ParserFactory()
        >>> parser = factory.create("standard")
        >>> df = parser.parse(Path("data.csv"))
    """

    @staticmethod
    def create(format_type: str) -> CSVParserProtocol:
        """Create parser for specified format.

        Args:
            format_type: CSV format type
                - "standard": Standard CSV with column headers
                - "transpose": Transposed CSV (row-oriented)
                - "noheader": CSV without headers

        Returns:
            Appropriate CSVParser implementation

        Raises:
            ValueError: If format_type is not supported

        Example:
            >>> parser = ParserFactory.create("standard")
            >>> isinstance(parser, StandardParser)
            True
        """
        format_lower = format_type.lower()

        if format_lower == "standard":
            return StandardParser()
        if format_lower == "transpose":
            return TransposeParser()
        if format_lower == "noheader":
            return NoHeaderParser()

        msg = (
            f"Unsupported CSV format: {format_type!r}. "
            f"Supported formats: 'standard', 'transpose', 'noheader'"
        )
        raise ValueError(msg)

    @staticmethod
    def auto_detect(csv_path: Path) -> CSVParserProtocol:
        """Auto-detect CSV format and return appropriate parser.

        Detection heuristics:
            1. Try standard format first (most common)
            2. Check if transposition improves structure
            3. Fall back to noheader if headers look like data

        Args:
            csv_path: Path to CSV file

        Returns:
            Best-matching CSVParser implementation

        Raises:
            FileNotFoundError: If CSV file doesn't exist

        Note:
            This is a basic heuristic. Explicit format specification
            via create() is recommended when format is known.
        """
        if not csv_path.exists():
            msg = f"CSV file not found: {csv_path}"
            raise FileNotFoundError(msg)

        try:
            df = pd.read_csv(csv_path)

            first_row = df.iloc[0] if len(df) > 0 else None
            if (
                first_row is not None
                and first_row.apply(lambda x: isinstance(x, (int, float))).all()
            ):
                return NoHeaderParser()

            if all(isinstance(col, (int, float)) for col in df.columns):
                return NoHeaderParser()

            return StandardParser()

        except (pd.errors.ParserError, ValueError):
            return NoHeaderParser()
