"""SmartTable file handling.

This module provides the SmartTableFile class for processing SmartTable
files, which are used in extended_mode for intelligent tabular data handling.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.invoicefile._helpers import _ensure_pandas

if TYPE_CHECKING:
    import pandas as pd


class SmartTableFile:
    """Handles SmartTable files (Excel/CSV/TSV) for invoice generation.

    This class reads table files containing metadata and maps them to invoice structure
    according to SmartTable format specifications. The first row (display names) is
    skipped, and the second row is used as the mapping key headers.
    """

    def __init__(self, smarttable_path: Path):
        """Initialize SmartTableFile with the path to the table file.

        Args:
            smarttable_path: Path to the SmartTable file (.xlsx, .csv, .tsv)

        Raises:
            StructuredError: If file format is not supported or file doesn't exist.
        """
        self.smarttable_path = smarttable_path
        self._validate_file()
        self._data: pd.DataFrame | None = None

    def _validate_file(self) -> None:
        """Validate the SmartTable file format and existence."""
        if not self.smarttable_path.exists():
            error_msg = f"SmartTable file not found: {self.smarttable_path}"
            raise StructuredError(error_msg)

        supported_extensions = [".xlsx", ".csv", ".tsv"]
        if self.smarttable_path.suffix.lower() not in supported_extensions:
            error_msg = f"Unsupported file format: {self.smarttable_path.suffix}. Supported formats: {supported_extensions}"
            raise StructuredError(error_msg)

        if not self.smarttable_path.name.startswith("smarttable_"):
            error_msg = f"Invalid naming convention: {self.smarttable_path.name}. File must start with 'smarttable_'"
            raise StructuredError(error_msg)

    def read_table(self) -> pd.DataFrame:
        """Read the SmartTable file and return as DataFrame.

        The first row (display names) is skipped, and the second row is used
        as column headers (mapping keys).

        Returns:
            DataFrame containing the table data with mapping key headers.

        Raises:
            StructuredError: If file reading fails or format is invalid.
        """
        if self._data is not None:
            return self._data

        pd = _ensure_pandas()
        try:
            if self.smarttable_path.suffix.lower() == ".xlsx":
                # Read Excel file, skip first row (display names), use second row as header
                self._data = pd.read_excel(self.smarttable_path, sheet_name=0, dtype=str, skiprows=[0], header=0)
            elif self.smarttable_path.suffix.lower() == ".csv":
                # Read CSV file, skip first row (display names), use second row as header
                self._data = pd.read_csv(self.smarttable_path, dtype=str, skiprows=[0], header=0)
            elif self.smarttable_path.suffix.lower() == ".tsv":
                # Read TSV file, skip first row (display names), use second row as header
                self._data = pd.read_csv(self.smarttable_path, sep="\t", dtype=str, skiprows=[0], header=0)

            if self._data is None:
                error_msg = (
                    "Unsupported SmartTable file extension: "
                    f"{self.smarttable_path.suffix}"
                )
                raise StructuredError(error_msg)

            mapping_prefixes = ["basic/", "custom/", "sample/", "meta/", "inputdata"]
            has_mapping_keys = any(
                any(col.startswith(prefix) for prefix in mapping_prefixes)
                for col in self._data.columns
            )
            if not has_mapping_keys:
                error_msg = "SmartTable file must have mapping keys with prefixes: basic/, custom/, sample/, meta/, inputdata"
                raise StructuredError(error_msg)

            return self._data

        except Exception as e:
            if isinstance(e, StructuredError):
                raise
            error_msg = f"Failed to read SmartTable file {self.smarttable_path}: {str(e)}"
            raise StructuredError(error_msg) from e

    def generate_row_csvs_with_file_mapping(
        self,
        output_dir: Path,
        extracted_files: list[Path] | None = None,
    ) -> list[tuple[Path, tuple[Path, ...]]]:
        """Generate individual CSV files for each row with file mapping.

        This method creates a CSV file for each data row and maps inputdata<N> columns
        to actual file paths from extracted zip files.

        Args:
            output_dir: Directory to save individual CSV files.
            extracted_files: List of extracted files from zip (optional).

        Returns:
            List of tuples where each tuple contains:
            - Path to the generated CSV file
            - Tuple of related file paths based on inputdata<N> columns

        Raises:
            StructuredError: If CSV generation or file mapping fails.
        """
        data = self.read_table()
        csv_file_mappings = []

        pd = _ensure_pandas()
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            inputdata_columns = [col for col in data.columns if col.startswith("inputdata")]

            for idx, row in data.iterrows():
                # New naming convention: smarttable_<original_filename>_XXXX.csv
                csv_filename = f"f{self.smarttable_path.stem}_{idx:04d}.csv"
                csv_path = output_dir / csv_filename

                single_row_df = pd.DataFrame([row], columns=data.columns)
                single_row_df.to_csv(csv_path, index=False)

                # Map inputdata<N> values to actual file paths
                related_files = []
                for col in inputdata_columns:
                    file_relative_path = row[col]
                    if pd.isna(file_relative_path) or file_relative_path == "":
                        continue

                    # Find matching file in extracted files
                    if extracted_files:
                        matching_file = self._find_file_by_relative_path(
                            file_relative_path, extracted_files,
                        )
                        if matching_file:
                            related_files.append(matching_file)

                csv_file_mappings.append((csv_path, tuple(related_files)))
            return csv_file_mappings

        except Exception as e:
            error_msg = f"Failed to generate CSV files with file mapping: {str(e)}"
            raise StructuredError(error_msg) from e

    def _find_file_by_relative_path(self, relative_path: str, extracted_files: list[Path]) -> Path | None:
        """Find extracted file by relative path.

        Args:
            relative_path: Relative path from inputdata<N> column.
            extracted_files: List of extracted files.

        Returns:
            Path to the matching file or None if not found.
        """
        # Normalize the relative path (remove leading/trailing slashes)
        normalized_path = relative_path.strip("/\\")

        for file_path in extracted_files:
            file_str = str(file_path)

            if file_str.replace("\\", "/").endswith(normalized_path.replace("\\", "/")):
                return file_path

            # Also check by exact relative path match
            # Extract relative part after temp directory
            path_parts = file_path.parts
            min_parts = 2  # at least temp/file
            if len(path_parts) >= min_parts:
                relative_part = "/".join(path_parts[-len(Path(normalized_path).parts):])
                if relative_part == normalized_path.replace("\\", "/"):
                    return file_path
        return None
