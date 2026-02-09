from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal


class PlotMode(str, Enum):
    """Plot rendering modes."""

    OVERLAY = "overlay"
    INDIVIDUAL = "individual"
    DUAL_AXIS = "dual_axis"


class CSVFormat(str, Enum):
    """CSV format types for parsing."""

    META_BLOCK = "meta_block"
    SINGLE_HEADER = "single_header"
    NO_HEADER = "no_header"


class Direction(str, Enum):
    """Direction types for series coloring."""

    CHARGE = "Charge"
    DISCHARGE = "Discharge"
    REST = "Rest"


@dataclass
class AxisConfig:
    """Axis configuration.

    Attributes:
        label: Axis label text
        unit: Unit text (optional)
        scale: Axis scale ('linear' or 'log')
        grid: Whether to show grid lines
        invert: Whether to invert axis direction
        lim: Axis limits as (min, max) tuple (optional)
    """

    label: str
    unit: str | None = None
    scale: Literal["linear", "log"] = "linear"
    grid: bool = True
    invert: bool = False
    lim: tuple[float, float] | None = None


@dataclass
class LegendConfig:
    """Legend configuration.

    Attributes:
        max_items: Maximum number of legend items to display
        info: Legend information text (optional)
        loc: Legend location (auto-placement if None)
    """

    max_items: int | None = 20
    info: str | None = None
    loc: str | int | None = None


@dataclass
class DirectionConfig:
    """Direction-based series configuration.

    Attributes:
        column: Direction column name
        filters: Direction filters to apply (empty = all)
        colors: Color mapping for each direction
        use_custom_colors: Whether to apply explicit color overrides
    """

    column: str | None = None
    filters: list[Direction | str] = field(default_factory=list)
    colors: dict[Direction | str, str] = field(
        default_factory=lambda: {
            Direction.CHARGE: "red",
            Direction.DISCHARGE: "blue",
            Direction.REST: "green",
        },
    )
    use_custom_colors: bool = False


def normalize_direction_filter(
    direction_filter: list[str | Any] | str | None,
) -> list[str]:
    """Normalize direction filter values into strings.

    Converts various direction filter input formats into a normalized list of strings.
    Handles None values, enum types with .value attribute, and ensures consistent
    string representation.

    Args:
        direction_filter: Direction filter specification. Can be:
            - None: Returns empty list
            - str: Single direction name, returned as list
            - list: List of direction values (str, enum, or None)

    Returns:
        List of normalized direction filter strings with None values filtered out

    Examples:
        >>> normalize_direction_filter(None)
        []
        >>> normalize_direction_filter("Charge")
        ['Charge']
        >>> normalize_direction_filter(["Charge", "Discharge"])
        ['Charge', 'Discharge']
        >>> normalize_direction_filter(["Charge", None, "Rest"])
        ['Charge', 'Rest']
    """
    if not direction_filter:
        return []

    candidates = (
        [direction_filter]
        if isinstance(direction_filter, str)
        else [value for value in direction_filter if value is not None]
    )

    normalized: list[str] = []
    for value in candidates:
        if hasattr(value, "value"):
            normalized.append(str(value.value))
        else:
            normalized.append(str(value))
    return normalized


def build_direction_config(
    *, filters: list[str], direction_colors: dict[str, str] | None,
) -> DirectionConfig:
    """Create DirectionConfig from filters and optional color overrides.

    Builds a DirectionConfig object with the specified filters and applies custom
    color mappings if provided. Default colors are used for directions not
    explicitly specified in direction_colors.

    Args:
        filters: List of direction filter strings to apply
        direction_colors: Optional mapping of direction names to color values.
            If provided, these colors override the defaults and use_custom_colors
            is set to True

    Returns:
        Configured DirectionConfig object with filters and colors

    Examples:
        >>> config = build_direction_config(filters=["Charge"], direction_colors=None)
        >>> config.filters
        ['Charge']
        >>> config.use_custom_colors
        False
        >>> config = build_direction_config(
        ...     filters=["Charge"],
        ...     direction_colors={"Charge": "orange"}
        ... )
        >>> config.colors["Charge"]
        'orange'
        >>> config.use_custom_colors
        True
    """
    direction_config = DirectionConfig(filters=filters)
    if direction_colors:
        direction_config.colors.update(direction_colors)
        direction_config.use_custom_colors = True
    return direction_config


@dataclass
class RenderResult:
    """Result of rendering operation.

    Attributes:
        figure: matplotlib Figure or plotly Figure
        filename: Suggested filename (without directory)
        format: Output format ('png', 'svg', 'html')
    """
    figure: Any
    filename: str
    format: str


@dataclass
class OutputConfig:
    """Output configuration.

    Attributes:
        main_image_dir: Main output directory for images
        no_individual: Skip individual plot generation
        return_fig: Return matplotlib figure object
        formats: Output image formats (e.g., ['png', 'svg'])
        base_name: Preferred base filename (without extension)
    """

    main_image_dir: Path | None = None
    no_individual: bool = False
    return_fig: bool = False
    formats: list[str] = field(default_factory=lambda: ["png"])
    base_name: str | None = None


@dataclass
class PlotConfig:
    """Complete plot configuration.

    This is the main configuration object built using Builder pattern.

    Attributes:
        mode: Plot mode (combined, individual, dual_axis)
        title: Plot title (optional)
        x_axis: X-axis configuration
        y_axis: Y-axis configuration
        y2_axis: Secondary Y-axis configuration (dual_axis only)
        legend: Legend configuration
        direction: Direction-based configuration
        output: Output configuration
        humanize: Apply humanization to labels
        csv_format: CSV parsing format
        x_col: X column specification (added in Phase 5)
        y_cols: Y column specifications (added in Phase 5)
        direction_cols: Direction column specifications (added in Phase 5)
    """

    mode: PlotMode = PlotMode.OVERLAY
    title: str | None = None
    x_axis: AxisConfig = field(default_factory=lambda: AxisConfig(label="X"))
    y_axis: AxisConfig = field(default_factory=lambda: AxisConfig(label="Y"))
    y2_axis: AxisConfig | None = None
    legend: LegendConfig = field(default_factory=LegendConfig)
    direction: DirectionConfig = field(default_factory=DirectionConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    humanize: bool = False
    csv_format: CSVFormat = CSVFormat.META_BLOCK
    x_col: int | str | list[int | str] | None = None
    y_cols: list[int | str] | None = None
    direction_cols: list[int | str | None] | None = None


@dataclass
class CSVMetadata:
    """CSV metadata extracted from meta_block format.

    Attributes:
        dimension: Column dimension specification
        headers: Column headers
        additional: Additional metadata key-value pairs
    """

    dimension: str
    headers: list[str]
    additional: dict[str, str] = field(default_factory=dict)


@dataclass
class ParsedData:
    """Parsed CSV data with metadata.

    Attributes:
        data: DataFrame containing the data
        metadata: CSV metadata (None for non-meta_block formats)
        x_col: X-axis column name
        y_cols: Y-axis column names
        series_col: Series column name (optional)
        direction_col: Direction column name (optional)
    """

    data: object  # pandas.DataFrame (avoid import here)
    metadata: CSVMetadata | None
    x_col: str
    y_cols: list[str]
    series_col: str | None = None
    direction_col: str | None = None


@dataclass(frozen=True)
class MatplotlibArtifact:
    """Rendered matplotlib artifact with its target filename.

    Attributes:
        filename: Target filename for the artifact
        figure: matplotlib Figure object
        metadata: Optional metadata dict (e.g., format information)
    """

    filename: str
    figure: Any
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class NormalizedColumns:
    """Normalized column specifications ready for PlotConfig consumption.

    Attributes:
        x_col: X column index or list of indices
        y_cols: Y column indices
        direction_cols: Direction column specifications
        derived_x_label: Derived X-axis label from headers
        derived_y_label: Derived Y-axis label from headers
    """

    x_col: int | list[int]
    y_cols: list[int]
    direction_cols: list[int | str | None]
    derived_x_label: str
    derived_y_label: str


@dataclass(frozen=True)
class RenderCollections:
    """Rendered results from overlay and individual strategies.

    Attributes:
        overlay: List of overlay render results
        individual: List of individual render results
    """

    overlay: list[RenderResult]
    individual: list[RenderResult]

    def all_results(self) -> list[RenderResult]:
        """Return combined results preserving order."""
        return [*self.overlay, *self.individual]
