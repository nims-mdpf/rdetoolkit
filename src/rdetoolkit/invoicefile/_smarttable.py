"""SmartTable file handling.

This module provides the SmartTableFile class for processing SmartTable
files, which are used in extended_mode for intelligent tabular data handling.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.invoicefile._helpers import _ensure_pandas
from rdetoolkit.rdelogger import get_logger

if TYPE_CHECKING:
    import pandas as pd

logger = get_logger(__name__)


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
        missing_references: list[tuple[int, str, str]] = []
        zip_was_uploaded = extracted_files is not None

        pd = _ensure_pandas()
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            inputdata_columns = [col for col in data.columns if col.startswith("inputdata")]
            available_files = extracted_files if extracted_files is not None else []

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

                    matching_file = self._find_file_by_relative_path(
                        str(file_relative_path), available_files,
                    )
                    if matching_file:
                        related_files.append(matching_file)
                        continue

                    missing_references.append(
                        (self._to_smarttable_row_number(idx), col, str(file_relative_path)),
                    )

                csv_file_mappings.append((csv_path, tuple(related_files)))

            if missing_references:
                self._raise_missing_reference_error(
                    missing_references,
                    zip_was_uploaded=zip_was_uploaded,
                )
            return csv_file_mappings

        except StructuredError:
            raise
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

    def _to_smarttable_row_number(self, data_row_index: int) -> int:
        """Convert a zero-based data row index to a SmartTable display row number."""
        first_data_row_number = 3
        return int(data_row_index) + first_data_row_number

    def _raise_missing_reference_error(
        self,
        missing_references: list[tuple[int, str, str]],
        *,
        zip_was_uploaded: bool,
    ) -> None:
        """Raise a user-facing error for unresolved inputdata references."""
        logger.error(
            self._missing_reference_log_message(zip_was_uploaded),
            self._format_missing_references_for_log(missing_references),
        )
        first_row_number, first_column, first_path = missing_references[0]
        first_column_label = self._sanitize_text(first_column)
        first_basename = self._basename_for_message(first_path)
        if zip_was_uploaded:
            error_msg = (
                "SmartTable row "
                f"{first_row_number} references missing file in uploaded zip: "
                f"{first_column_label}={first_basename}"
            )
        else:
            error_msg = (
                "SmartTable row "
                f"{first_row_number} references {first_column_label}={first_basename} "
                "but no zip was uploaded"
            )
        raise StructuredError(error_msg, eobj=missing_references)

    def _missing_reference_log_message(self, zip_was_uploaded: bool) -> str:
        """Return the summary log message for unresolved inputdata references."""
        if zip_was_uploaded:
            return "SmartTable references files missing from the uploaded zip:\n%s"
        return "SmartTable references inputdata files but no zip was uploaded:\n%s"

    def _format_missing_references_for_log(self, missing_references: list[tuple[int, str, str]]) -> str:
        """Render missing references as a control-character-safe log payload."""
        return "\n".join(
            "row "
            f"{row_number}: {self._sanitize_text(column)}={self._sanitize_text(relative_path)}"
            for row_number, column, relative_path in missing_references
        )

    def _basename_for_message(self, relative_path: str) -> str:
        """Return a short filename for user-facing error messages."""
        normalized_path = relative_path.strip().strip("/\\").replace("\\", "/")
        if not normalized_path:
            return self._sanitize_text(relative_path)
        return self._sanitize_text(Path(normalized_path).name)

    def _sanitize_text(self, value: str) -> str:
        """Escape control characters before including user-provided text in logs/messages."""
        replacements = {
            "\n": "\\n",
            "\r": "\\r",
            "\t": "\\t",
        }
        return "".join(
            replacements.get(char, char if char.isprintable() else f"\\x{ord(char):02x}")
            for char in value
        )
