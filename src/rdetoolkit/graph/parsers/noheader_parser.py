from __future__ import annotations

from pathlib import Path

import pandas as pd


class NoHeaderParser:
    """Parser for CSV without headers.

    Generates auto-numbered column names for headerless CSV files.

    Example:
        >>> parser = NoHeaderParser()
        >>> df = parser.parse(Path("noheader.csv"))
        >>> df.columns
        Index(['Column_0', 'Column_1', 'Column_2'], dtype='object')
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
        """Parse headerless CSV file.

        Args:
            csv_path: Path to headerless CSV file

        Returns:
            DataFrame with auto-generated column names (Column_0, Column_1, ...)

        Raises:
            FileNotFoundError: If CSV file doesn't exist
            pd.errors.ParserError: If CSV parsing fails
        """
        if not csv_path.exists():
            msg = f"CSV file not found: {csv_path}"
            raise FileNotFoundError(msg)

        try:
            df = pd.read_csv(csv_path, header=None, **self._read_options())

            df.columns = [f"Column_{i}" for i in range(len(df.columns))]

        except pd.errors.ParserError as e:
            msg = f"Failed to parse headerless CSV file: {csv_path}"
            raise pd.errors.ParserError(msg) from e

        return df
