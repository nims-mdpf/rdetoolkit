"""Graph module for RDEToolKit.

This module provides functionality for plotting graphs from CSV data with
various configuration options including direction-based coloring, dual-axis plots,
and customizable styling.

Public API:
    csv2graph: Main plotting function (to be implemented in api.py)
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "csv2graph": ("rdetoolkit.graph.api", "csv2graph"),
    "plot_from_dataframe": ("rdetoolkit.graph.api", "plot_from_dataframe"),
    "GraphPlottingError": ("rdetoolkit.graph.exceptions", "GraphPlottingError"),
    "ColumnNotFoundError": ("rdetoolkit.graph.exceptions", "ColumnNotFoundError"),
    "InvalidMetadataError": ("rdetoolkit.graph.exceptions", "InvalidMetadataError"),
    "InvalidCSVFormatError": ("rdetoolkit.graph.exceptions", "InvalidCSVFormatError"),
    "DirectionError": ("rdetoolkit.graph.exceptions", "DirectionError"),
    "DualAxisError": ("rdetoolkit.graph.exceptions", "DualAxisError"),
    "PlotConfigError": ("rdetoolkit.graph.exceptions", "PlotConfigError"),
    "RendererError": ("rdetoolkit.graph.exceptions", "RendererError"),
    "PlotMode": ("rdetoolkit.graph.models", "PlotMode"),
    "CSVFormat": ("rdetoolkit.graph.models", "CSVFormat"),
    "Direction": ("rdetoolkit.graph.models", "Direction"),
    "AxisConfig": ("rdetoolkit.graph.models", "AxisConfig"),
    "LegendConfig": ("rdetoolkit.graph.models", "LegendConfig"),
    "DirectionConfig": ("rdetoolkit.graph.models", "DirectionConfig"),
    "OutputConfig": ("rdetoolkit.graph.models", "OutputConfig"),
    "PlotConfig": ("rdetoolkit.graph.models", "PlotConfig"),
    "CSVMetadata": ("rdetoolkit.graph.models", "CSVMetadata"),
    "ParsedData": ("rdetoolkit.graph.models", "ParsedData"),
    "titleize": ("rdetoolkit.graph.textutils", "titleize"),
    "sanitize_filename": ("rdetoolkit.graph.textutils", "sanitize_filename"),
    "to_snake_case": ("rdetoolkit.graph.textutils", "to_snake_case"),
    "parse_header": ("rdetoolkit.graph.textutils", "parse_header"),
    "ColumnNormalizer": ("rdetoolkit.graph.normalizers", "ColumnNormalizer"),
    "validate_column_specs": ("rdetoolkit.graph.normalizers", "validate_column_specs"),
    "PlotConfigBuilder": ("rdetoolkit.graph.config", "PlotConfigBuilder"),
    "apply_matplotlib_config": ("rdetoolkit.graph.config", "apply_matplotlib_config"),
    "DEFAULT_FIG_SIZE": ("rdetoolkit.graph.config", "DEFAULT_FIG_SIZE"),
    "DEFAULT_PLOT_PARAMS": ("rdetoolkit.graph.config", "DEFAULT_PLOT_PARAMS"),
}

__all__ = list(_LAZY_ATTRS.keys())


def __getattr__(name: str) -> Any:
    if name in _LAZY_ATTRS:
        module_name, attr_name = _LAZY_ATTRS[name]
        module = import_module(module_name)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(globals()))
