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
            df = pd.read_csv(csv_path, header=None)

            df.columns = [f"Column_{i}" for i in range(len(df.columns))]

        except pd.errors.ParserError as e:
            msg = f"Failed to parse headerless CSV file: {csv_path}"
            raise pd.errors.ParserError(msg) from e

        return df
