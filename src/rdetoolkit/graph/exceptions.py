from __future__ import annotations

from typing import Any


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


class PlotRequestError(PlotConfigError, ValueError):
    """Raised when a plot request is invalid before anything is rendered or written.

    It is a ``PlotConfigError`` for graph-aware callers and a ``ValueError`` so that
    callers catching the builtin type (for example the CLI command) keep working.

    Args:
        message: Human-readable description of the problem.
        reason: Stable machine-readable identifier, for example ``"invalid_mode"``,
            ``"contradictory_switches"`` or ``"no_figures"``.
    """

    def __init__(self, message: str, *, reason: str) -> None:
        """Initialize PlotRequestError.

        Args:
            message: Human-readable description of the problem.
            reason: Stable machine-readable identifier of the problem.
        """
        self.reason = reason
        super().__init__(message)


class GraphUserWarning(UserWarning):
    """Warning category for graph requests that succeed with a caveat."""


class UnknownReaderError(InvalidCSVFormatError, ValueError):
    """Raised when a table reader id is not registered.

    The message starts with ``"Unsupported CSV format: "`` like the legacy
    ``ParserFactory`` error, which callers may match.
    """


class AmbiguousFormatError(InvalidCSVFormatError, ValueError):
    """Raised when automatic table-format detection cannot choose a reader.

    Args:
        message: Explanation naming the candidates, their evidence and the remedy.
        decision: The detection decision that was ambiguous.
    """

    def __init__(self, message: str, *, decision: Any) -> None:
        """Initialize AmbiguousFormatError.

        Args:
            message: Explanation naming the candidates, their evidence and the remedy.
            decision: The detection decision that was ambiguous.
        """
        self.decision = decision
        super().__init__(message)


class DuplicateReaderError(GraphPlottingError, ValueError):
    """Raised when two table readers claim the same id."""


class ReaderPluginError(GraphPlottingError):
    """Raised when a requested reader plugin cannot be loaded."""


class RendererUnavailableError(RendererError, ImportError):
    """Raised when a renderer's optional dependency is not installed."""


class UnsupportedFormatError(RendererError, ValueError):
    """Raised when no renderer supports an output format for a figure kind."""


class OutputPathError(GraphPlottingError, ValueError):
    """Raised when an artifact destination is unsafe or unusable.

    Messages keep the legacy ``PathValidator`` wording (for example
    ``"contains path separators"`` or ``"Output path is not a directory"``).
    """


class ArtifactCollisionError(GraphPlottingError, ValueError):
    """Raised when artifact destinations clash, before anything is rendered."""
