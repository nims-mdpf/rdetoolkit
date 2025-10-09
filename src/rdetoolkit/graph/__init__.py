"""Graph module for RDEToolKit.

This module provides functionality for plotting graphs from CSV data with
various configuration options including direction-based coloring, dual-axis plots,
and customizable styling.

Public API:
    csv2graph: Main plotting function (to be implemented in api.py)
"""

from __future__ import annotations

from rdetoolkit.graph.exceptions import (
    ColumnNotFoundError,
    DirectionError,
    DualAxisError,
    GraphPlottingError,
    InvalidCSVFormatError,
    InvalidMetadataError,
    PlotConfigError,
    RendererError,
)
from rdetoolkit.graph.models import (
    AxisConfig,
    CSVFormat,
    CSVMetadata,
    Direction,
    DirectionConfig,
    LegendConfig,
    OutputConfig,
    ParsedData,
    PlotConfig,
    PlotMode,
)

from rdetoolkit.graph.textutils import titleize, parse_header, sanitize_filename, to_snake_case
from rdetoolkit.graph.normalizers import ColumnNormalizer, validate_column_specs
from rdetoolkit.graph.config import (
    PlotConfigBuilder,
    apply_matplotlib_config,
    DEFAULT_FIG_SIZE,
    DEFAULT_PLOT_PARAMS,
)

__all__ = [
    # Main API (to be added when api.py is implemented)
    # "csv2graph",
    # Exceptions
    "GraphPlottingError",
    "ColumnNotFoundError",
    "InvalidMetadataError",
    "InvalidCSVFormatError",
    "DirectionError",
    "DualAxisError",
    "PlotConfigError",
    "RendererError",
    # Models
    "PlotMode",
    "CSVFormat",
    "Direction",
    "AxisConfig",
    "LegendConfig",
    "DirectionConfig",
    "OutputConfig",
    "PlotConfig",
    "CSVMetadata",
    "ParsedData",
    # Text utilities
    "titleize",
    "sanitize_filename",
    "to_snake_case",
    "parse_header",
    # Normalizers
    "ColumnNormalizer",
    "validate_column_specs",
    # Config
    "PlotConfigBuilder",
    "apply_matplotlib_config",
    "DEFAULT_FIG_SIZE",
    "DEFAULT_PLOT_PARAMS",
]
