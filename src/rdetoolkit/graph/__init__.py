"""Graph module for RDEToolKit.

This module provides functionality for plotting graphs from CSV data with
various configuration options including direction-based coloring, unit-aware
overlays and customizable styling. Dual-axis (secondary y axis) plots are not
supported: ``PlotMode.DUAL_AXIS`` and ``PlotConfig.y2_axis`` remain importable for
compatibility, but rendering them raises ``PlotRequestError``
(``reason="dual_axis_unsupported"``).

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
    "PlotRequestError": ("rdetoolkit.graph.exceptions", "PlotRequestError"),
    "GraphUserWarning": ("rdetoolkit.graph.exceptions", "GraphUserWarning"),
    "PlotMode": ("rdetoolkit.graph.models", "PlotMode"),
    "CSVFormat": ("rdetoolkit.graph.models", "CSVFormat"),
    "Direction": ("rdetoolkit.graph.models", "Direction"),
    "AxisConfig": ("rdetoolkit.graph.models", "AxisConfig"),
    "LegendConfig": ("rdetoolkit.graph.models", "LegendConfig"),
    "DirectionConfig": ("rdetoolkit.graph.models", "DirectionConfig"),
    "normalize_direction_filter": ("rdetoolkit.graph.models", "normalize_direction_filter"),
    "build_direction_config": ("rdetoolkit.graph.models", "build_direction_config"),
    "RenderResult": ("rdetoolkit.graph.models", "RenderResult"),
    "OutputConfig": ("rdetoolkit.graph.models", "OutputConfig"),
    "PlotConfig": ("rdetoolkit.graph.models", "PlotConfig"),
    "CSVMetadata": ("rdetoolkit.graph.models", "CSVMetadata"),
    "ParsedData": ("rdetoolkit.graph.models", "ParsedData"),
    "MatplotlibArtifact": ("rdetoolkit.graph.models", "MatplotlibArtifact"),
    "NormalizedColumns": ("rdetoolkit.graph.models", "NormalizedColumns"),
    "RenderCollections": ("rdetoolkit.graph.models", "RenderCollections"),
    "titleize": ("rdetoolkit.graph.textutils", "titleize"),
    "sanitize_filename": ("rdetoolkit.graph.textutils", "sanitize_filename"),
    "to_snake_case": ("rdetoolkit.graph.textutils", "to_snake_case"),
    "parse_header": ("rdetoolkit.graph.textutils", "parse_header"),
    "ColumnNormalizer": ("rdetoolkit.graph.normalizers", "ColumnNormalizer"),
    "resolve_column_index": ("rdetoolkit.graph.normalizers", "resolve_column_index"),
    "validate_column_specs": ("rdetoolkit.graph.normalizers", "validate_column_specs"),
    "PlotConfigBuilder": ("rdetoolkit.graph.config", "PlotConfigBuilder"),
    "apply_matplotlib_config": ("rdetoolkit.graph.config", "apply_matplotlib_config"),
    "DEFAULT_FIG_SIZE": ("rdetoolkit.graph.config", "DEFAULT_FIG_SIZE"),
    "DEFAULT_PLOT_PARAMS": ("rdetoolkit.graph.config", "DEFAULT_PLOT_PARAMS"),
    "determine_titles": ("rdetoolkit.graph.config", "determine_titles"),
    "determine_formats": ("rdetoolkit.graph.config", "determine_formats"),
    "normalize_axis_limits": ("rdetoolkit.graph.config", "normalize_axis_limits"),
    "collect_render_results": ("rdetoolkit.graph.strategies", "collect_render_results"),
    "build_matplotlib_artifacts": ("rdetoolkit.graph.strategies", "build_matplotlib_artifacts"),
    "render_graph": ("rdetoolkit.graph.engine", "render_graph"),
    "build_plot_plan": ("rdetoolkit.graph.plan", "build_plot_plan"),
    "GraphSpec": ("rdetoolkit.graph.spec", "GraphSpec"),
    "SeriesSpec": ("rdetoolkit.graph.spec", "SeriesSpec"),
    "AxisSpec": ("rdetoolkit.graph.spec", "AxisSpec"),
    "LegendSpec": ("rdetoolkit.graph.spec", "LegendSpec"),
    "StyleSpec": ("rdetoolkit.graph.spec", "StyleSpec"),
    "OutputSpec": ("rdetoolkit.graph.spec", "OutputSpec"),
    "PlotPlan": ("rdetoolkit.graph.plan", "PlotPlan"),
    "SeriesPlan": ("rdetoolkit.graph.plan", "SeriesPlan"),
    "FigurePlan": ("rdetoolkit.graph.plan", "FigurePlan"),
    "GraphDiagnostic": ("rdetoolkit.graph.plan", "GraphDiagnostic"),
    "PlotData": ("rdetoolkit.graph.plan", "PlotData"),
    "GraphResult": ("rdetoolkit.graph.result", "GraphResult"),
    "Artifact": ("rdetoolkit.graph.result", "Artifact"),
    "TableReader": ("rdetoolkit.graph.readers", "TableReader"),
    "TableData": ("rdetoolkit.graph.readers", "TableData"),
    "ColumnProvenance": ("rdetoolkit.graph.readers", "ColumnProvenance"),
    "ReaderRegistry": ("rdetoolkit.graph.readers", "ReaderRegistry"),
    "builtin_readers": ("rdetoolkit.graph.readers", "builtin_readers"),
    "discover_readers": ("rdetoolkit.graph.readers", "discover_readers"),
    "read_table": ("rdetoolkit.graph.readers", "read_table"),
    "detect_table_format": ("rdetoolkit.graph.readers", "detect_table_format"),
    "DetectionDecision": ("rdetoolkit.graph.readers", "DetectionDecision"),
    "FormatCandidate": ("rdetoolkit.graph.readers", "FormatCandidate"),
    "UnknownReaderError": ("rdetoolkit.graph.exceptions", "UnknownReaderError"),
    "AmbiguousFormatError": ("rdetoolkit.graph.exceptions", "AmbiguousFormatError"),
    "DuplicateReaderError": ("rdetoolkit.graph.exceptions", "DuplicateReaderError"),
    "ReaderPluginError": ("rdetoolkit.graph.exceptions", "ReaderPluginError"),
    "GraphRenderer": ("rdetoolkit.graph.renderers.base", "GraphRenderer"),
    "RendererCapabilities": ("rdetoolkit.graph.renderers.base", "RendererCapabilities"),
    "RendererRegistry": ("rdetoolkit.graph.renderers.registry", "RendererRegistry"),
    "builtin_renderers": ("rdetoolkit.graph.renderers.registry", "builtin_renderers"),
    "RendererUnavailableError": ("rdetoolkit.graph.exceptions", "RendererUnavailableError"),
    "UnsupportedFormatError": ("rdetoolkit.graph.exceptions", "UnsupportedFormatError"),
}

__all__ = list(_LAZY_ATTRS.keys())


def __getattr__(name: str) -> Any:
    if name in _LAZY_ATTRS:
        module_name, attr_name = _LAZY_ATTRS[name]
        module = import_module(module_name)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    emsg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(emsg)


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(globals()))
