from __future__ import annotations

from pathlib import Path

import pandas as pd


class TransposeParser:
    """Parser for transposed CSV format.

    Reads CSV where data is row-oriented and transposes to column-oriented.

    Example:
        >>> parser = TransposeParser()
        >>> df = parser.parse(Path("transposed_data.csv"))
        >>> df.columns
        Index(['Time', 'Voltage', 'Current'], dtype='object')
    """

    def parse(self, csv_path: Path) -> pd.DataFrame:
        """Parse and transpose CSV file.

        Args:
            csv_path: Path to transposed CSV file

        Returns:
            Transposed DataFrame with proper column headers

        Raises:
            FileNotFoundError: If CSV file doesn't exist
            pd.errors.ParserError: If CSV parsing fails
        """
        if not csv_path.exists():
            msg = f"CSV file not found: {csv_path}"
            raise FileNotFoundError(msg)

        try:
            df = pd.read_csv(csv_path, index_col=0)

            df_transposed = df.T

            df_transposed = df_transposed.reset_index(drop=False)

            if df_transposed.columns[0] == "index":
                original_index_name = df.index.name if df.index.name else "index"
                df_transposed.rename(
                    columns={"index": original_index_name}, inplace=True,
                )

        except pd.errors.ParserError as e:
            msg = f"Failed to parse transposed CSV file: {csv_path}"
            raise pd.errors.ParserError(msg) from e

        return df_transposed
