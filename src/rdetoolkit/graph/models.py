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
