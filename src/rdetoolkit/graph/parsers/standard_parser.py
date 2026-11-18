from __future__ import annotations

from pathlib import Path

import pandas as pd


class StandardParser:
    """Parser for standard CSV format with headers.

    This is the most common CSV format with column names in the first row.

    Example:
        >>> parser = StandardParser()
        >>> df = parser.parse(Path("data.csv"))
        >>> df.columns
        Index(['Time', 'Voltage', 'Current'], dtype='object')
    """

    def __init__(self, *, encoding: str | None = None, delimiter: str | None = None) -> None:
        """Create the parser.

        Args:
            encoding: Text encoding passed to ``pandas.read_csv``; ``None`` keeps the
                pandas default (UTF-8), exactly as before these options existed.
            delimiter: Field delimiter passed as ``sep``; ``None`` keeps the default comma.
        """
        self.encoding = encoding
        self.delimiter = delimiter

    def _read_options(self) -> dict[str, str]:
        """Return only the options that were set, so the no-argument call is unchanged."""
        options: dict[str, str] = {}
        if self.encoding is not None:
            options["encoding"] = self.encoding
        if self.delimiter is not None:
            options["sep"] = self.delimiter
        return options

    def parse(self, csv_path: Path) -> pd.DataFrame:
        """Parse standard CSV file.

        Args:
            csv_path: Path to CSV file

        Returns:
            DataFrame with column headers from first row

        Raises:
            FileNotFoundError: If CSV file doesn't exist
            pd.errors.ParserError: If CSV parsing fails
        """
        if not csv_path.exists():
            msg = f"CSV file not found: {csv_path}"
            raise FileNotFoundError(msg)

        try:
            df = pd.read_csv(csv_path, **self._read_options())
        except pd.errors.ParserError as e:
            msg = f"Failed to parse CSV file: {csv_path}"
            raise pd.errors.ParserError(msg) from e

        return df
