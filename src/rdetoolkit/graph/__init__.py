"""Graph module for RDEToolKit.

This module provides functionality for plotting graphs from CSV data with
various configuration options including direction-based coloring, dual-axis plots,
and customizable styling.

Every package-root attribute belongs to exactly one tier (the authoritative
inventory is the export table in ``docs/rdetoolkit/csv2graph.md``):

* supported -- the GA public API (``csv2graph``, ``plot_from_dataframe``, the
  graph exceptions and the configuration models).
* compatibility -- helpers the shipped stub already promised; kept in
  ``__all__`` so existing typed imports keep working, but new code should
  import them from their defining submodule.
* private -- implementation helpers that stay resolvable at runtime for
  backward compatibility, but are not exported, listed or typed here.

All attributes are imported lazily so that ``import rdetoolkit.graph`` does not
pull in matplotlib.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_PUBLIC_ATTRS: dict[str, tuple[str, str]] = {
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
}

# Promised by the package stub before the GA inventory existed; dropping them
# would break strict-typed consumers, so they stay exported but are not
# recommended for new code.
_COMPAT_ATTRS: dict[str, tuple[str, str]] = {
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

# Never typed or exported at the package root; resolvable only so that code
# which reached them through the old lazy map keeps running.
_PRIVATE_ATTRS: dict[str, tuple[str, str]] = {
    "normalize_direction_filter": ("rdetoolkit.graph.models", "normalize_direction_filter"),
    "build_direction_config": ("rdetoolkit.graph.models", "build_direction_config"),
    "RenderResult": ("rdetoolkit.graph.models", "RenderResult"),
    "MatplotlibArtifact": ("rdetoolkit.graph.models", "MatplotlibArtifact"),
    "NormalizedColumns": ("rdetoolkit.graph.models", "NormalizedColumns"),
    "RenderCollections": ("rdetoolkit.graph.models", "RenderCollections"),
    "resolve_column_index": ("rdetoolkit.graph.normalizers", "resolve_column_index"),
    "determine_titles": ("rdetoolkit.graph.config", "determine_titles"),
    "determine_formats": ("rdetoolkit.graph.config", "determine_formats"),
    "normalize_axis_limits": ("rdetoolkit.graph.config", "normalize_axis_limits"),
    "collect_render_results": ("rdetoolkit.graph.strategies", "collect_render_results"),
    "build_matplotlib_artifacts": ("rdetoolkit.graph.strategies", "build_matplotlib_artifacts"),
}

_LAZY_ATTRS: dict[str, tuple[str, str]] = {**_PUBLIC_ATTRS, **_COMPAT_ATTRS, **_PRIVATE_ATTRS}

# Supported tier, then compatibility tier (== the package stub's __all__).
__all__ = [
    "csv2graph",
    "plot_from_dataframe",
    "GraphPlottingError",
    "ColumnNotFoundError",
    "InvalidMetadataError",
    "InvalidCSVFormatError",
    "DirectionError",
    "DualAxisError",
    "PlotConfigError",
    "RendererError",
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
    "titleize",
    "sanitize_filename",
    "to_snake_case",
    "parse_header",
    "ColumnNormalizer",
    "validate_column_specs",
    "PlotConfigBuilder",
    "apply_matplotlib_config",
    "DEFAULT_FIG_SIZE",
    "DEFAULT_PLOT_PARAMS",
]


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
    # Cached private helpers land in globals(); keep them out of the listing.
    return sorted((set(__all__) | set(globals())) - set(_PRIVATE_ATTRS))
