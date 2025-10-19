from __future__ import annotations


class GraphPlottingError(Exception):
    """Base exception for graph plotting errors."""


class ColumnNotFoundError(GraphPlottingError):
    """Raised when a specified column is not found in the DataFrame.

    Args:
        column_name: Name of the column that was not found.
        available_columns: List of available column names (optional).
    """

    def __init__(self, column_name: str, available_columns: list[str] | None = None):
        """Initialize ColumnNotFoundError.

        Args:
            column_name: Name of the column that was not found.
            available_columns: List of available column names (optional).
        """
        self.column_name = column_name
        self.available_columns = available_columns

        msg = f"Column '{column_name}' not found"
        if available_columns:
            msg += f". Available columns: {', '.join(available_columns)}"
        super().__init__(msg)


class InvalidMetadataError(GraphPlottingError):
    """Raised when CSV metadata is invalid or incomplete.

    This addresses the metadata validation issues identified in review_cc.md.
    """


class InvalidCSVFormatError(GraphPlottingError):
    """Raised when CSV format cannot be determined."""


class DirectionError(GraphPlottingError):
    """Raised when direction column processing fails.

    This addresses the direction_col issues identified in review_cc.md.
    """


class DualAxisError(GraphPlottingError):
    """Raised when dual axis configuration is invalid.

    This addresses the critical IndexError bug in dual_axis mode
    identified in review_cc.md (致命的).
    """


class PlotConfigError(GraphPlottingError):
    """Raised when plot configuration is invalid."""


class RendererError(GraphPlottingError):
    """Raised when rendering fails."""
