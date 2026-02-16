"""Type stubs for SmartTable file handling."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

class SmartTableFile:
    """Handles SmartTable files (Excel/CSV/TSV) for invoice generation."""

    smarttable_path: Path
    _data: pd.DataFrame | None

    def __init__(self, smarttable_path: Path) -> None:
        """Initialize SmartTableFile with the path to the table file."""
        ...

    def _validate_file(self) -> None:
        """Validate the SmartTable file format and existence."""
        ...

    def read_table(self) -> pd.DataFrame:
        """Read the SmartTable file and return as DataFrame."""
        ...

    def generate_row_csvs_with_file_mapping(
        self,
        output_dir: Path,
        extracted_files: list[Path] | None = None,
    ) -> list[tuple[Path, tuple[Path, ...]]]:
        """Generate individual CSV files for each row with file mapping."""
        ...

    def _find_file_by_relative_path(
        self, relative_path: str, extracted_files: list[Path]
    ) -> Path | None:
        """Find extracted file by relative path."""
        ...
