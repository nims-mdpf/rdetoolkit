from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from rdetoolkit.graph.config import PlotConfigBuilder
from rdetoolkit.graph.io.file_writer import FileWriter
from rdetoolkit.graph.io.path_validator import PathValidator
from rdetoolkit.graph.models import (
    AxisConfig,
    DirectionConfig,
    LegendConfig,
    OutputConfig,
    PlotConfig,
    PlotMode,
    RenderResult,
)
from rdetoolkit.graph.normalizers import validate_column_specs
from rdetoolkit.graph.parsers.parser_factory import ParserFactory
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer
from rdetoolkit.graph.strategies.all_graphs import OverlayStrategy
from rdetoolkit.graph.strategies.individual import IndividualStrategy
from rdetoolkit.graph.textutils import parse_header


@dataclass(frozen=True)
class MatplotlibArtifact:
    """Rendered matplotlib artifact with its target filename."""

    filename: str
    figure: Any
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class NormalizedColumns:
    """Normalized column specifications ready for PlotConfig consumption."""

    x_col: int | list[int]
    y_cols: list[int]
    direction_cols: list[int | str | None]
    derived_x_label: str
    derived_y_label: str


@dataclass(frozen=True)
class RenderCollections:
    """Rendered results from overlay and individual strategies."""

    overlay: list[RenderResult]
    individual: list[RenderResult]

    def all_results(self) -> list[RenderResult]:
        """Return combined results preserving order."""
        return [*self.overlay, *self.individual]


def _resolve_column_index(df: pd.DataFrame, column: int | str) -> int:
    """Resolve a column specifier into a DataFrame index."""
    if isinstance(column, int):
        return column

    loc = df.columns.get_loc(column)
    if isinstance(loc, slice):
        emsg = f"Column specification '{column}' resolved to a slice"
        raise ValueError(emsg)
    if isinstance(loc, Iterable) and not isinstance(loc, str):
        emsg = (
            "Column specification "
            f"'{column}' resolved to multiple columns: {list(loc)}"
        )
        raise ValueError(emsg)
    return int(loc)


def _parse_headers(df: pd.DataFrame) -> list[tuple[str | None, str, str | None]]:
    """Parse DataFrame headers into (series, label, unit)."""
    return [parse_header(str(header)) for header in df.columns]


def _format_axis_label(
    column_name: Any,
    parsed: tuple[str | None, str, str | None] | None,
) -> str:
    """Return axis label composed of label and optional unit."""
    if not parsed:
        return str(column_name)

    _, label, unit = parsed
    base = label or str(column_name)
    return f"{base} ({unit})" if unit else base


def _normalize_y_specs(
    y_cols: int | str | list[int | str] | None,
) -> Sequence[int | str] | None:
    """Normalize y column specification into a list."""
    if y_cols is None:
        return None
    if isinstance(y_cols, (int, str)):
        return [y_cols]
    return list(y_cols)


def _normalize_columns(
    df: pd.DataFrame,
    x_col: int | str | list[int | str] | None,
    y_cols: int | str | list[int | str] | None,
    direction_cols: int | str | list[int | str] | None,
) -> NormalizedColumns:
    """Validate and normalize column specifications for plotting."""
    normalized_y_cols = _normalize_y_specs(y_cols)
    column_specs = validate_column_specs(
        df,
        x_col=x_col,
        y_cols=normalized_y_cols,
        direction_cols=direction_cols,
    )

    if not column_specs["pairs"]:
        msg = "DataFrame must have at least one y column for plotting"
        raise ValueError(msg)

    pair_x_indices = [
        _resolve_column_index(df, x_name) for x_name, _ in column_specs["pairs"]
    ]
    pair_y_indices = [
        _resolve_column_index(df, y_name) for _, y_name in column_specs["pairs"]
    ]

    config_x_col: int | list[int]
    config_x_col = (
        pair_x_indices[0]
        if len(set(pair_x_indices)) == 1
        else pair_x_indices
    )

    parsed_headers = _parse_headers(df)
    first_x_idx = pair_x_indices[0]
    first_y_idx = pair_y_indices[0]
    derived_x_label = _format_axis_label(
        df.columns[first_x_idx],
        parsed_headers[first_x_idx] if first_x_idx < len(parsed_headers) else None,
    )
    derived_y_label = _format_axis_label(
        df.columns[first_y_idx],
        parsed_headers[first_y_idx] if first_y_idx < len(parsed_headers) else None,
    )

    return NormalizedColumns(
        x_col=config_x_col,
        y_cols=pair_y_indices,
        direction_cols=list(column_specs["direction_cols"]),
        derived_x_label=derived_x_label,
        derived_y_label=derived_y_label,
    )


def _normalize_direction_filter(
    direction_filter: list[str | Any] | str | None,
) -> list[str]:
    """Normalize direction filter values into strings."""
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


def _build_direction_config(
    *, filters: list[str], direction_colors: dict[str, str] | None,
) -> DirectionConfig:
    """Create DirectionConfig from filters and optional color overrides."""
    direction_config = DirectionConfig(filters=filters)
    if direction_colors:
        direction_config.colors.update(direction_colors)
        direction_config.use_custom_colors = True
    return direction_config


def _determine_titles(
    *, title: str | None, name: str | None,
) -> tuple[str | None, str]:
    """Resolve display title and base filename for outputs."""
    display_title = title if title is not None else name
    base_filename = name or title or "plot"
    return display_title, base_filename


def _determine_formats(html: bool, return_fig: bool) -> list[str]:
    """Compute output formats based on execution mode."""
    formats = ["png"]
    if html and not return_fig:
        formats.append("html")
    return formats


def _resolve_plot_mode(mode: Literal["overlay", "individual"]) -> PlotMode:
    """Convert user-facing mode flag into PlotMode enum."""
    return PlotMode.OVERLAY if mode == "overlay" else PlotMode.INDIVIDUAL


def _normalize_axis_limits(
    limits: tuple[float | None, float | None] | None,
) -> tuple[float, float] | None:
    """Return axis limits only when both bounds are specified."""
    if not limits:
        return None
    start, end = limits
    if start is None or end is None:
        return None
    return (start, end)


def _build_plot_config(
    *,
    plot_mode: PlotMode,
    normalized: NormalizedColumns,
    direction_config: DirectionConfig,
    display_title: str | None,
    x_label: str | None,
    y_label: str | None,
    logx: bool,
    logy: bool,
    xlim: tuple[float | None, float | None] | None,
    ylim: tuple[float | None, float | None] | None,
    grid: bool,
    invert_x: bool,
    invert_y: bool,
    legend_info: str | None,
    legend_loc: str | int | None,
    max_legend_items: int | None,
    formats: list[str],
    no_individual: bool,
    return_fig: bool,
    base_filename: str,
    main_image_dir_path: Path | None,
) -> PlotConfig:
    """Build PlotConfig using the builder pattern."""
    builder = PlotConfigBuilder()
    builder.set_mode(plot_mode)
    builder.set_title(display_title)
    builder.set_columns(
        x_col=normalized.x_col,
        y_cols=normalized.y_cols,
        direction_cols=normalized.direction_cols,
    )
    builder.set_x_axis(
        AxisConfig(
            label=x_label or normalized.derived_x_label,
            scale="log" if logx else "linear",
            lim=_normalize_axis_limits(xlim),
            grid=grid,
            invert=invert_x,
        ),
    )
    builder.set_y_axis(
        AxisConfig(
            label=y_label or normalized.derived_y_label,
            scale="log" if logy else "linear",
            lim=_normalize_axis_limits(ylim),
            grid=grid,
            invert=invert_y,
        ),
    )
    builder.set_direction(direction_config)
    builder.set_legend(
        LegendConfig(
            info=legend_info,
            loc=legend_loc,
            max_items=max_legend_items,
        ),
    )
    builder.set_output(
        OutputConfig(
            formats=formats,
            no_individual=no_individual,
            return_fig=return_fig,
            base_name=base_filename,
            main_image_dir=main_image_dir_path,
        ),
    )
    return builder.build()


def _collect_render_results(
    df: pd.DataFrame,
    config: PlotConfig,
    plot_mode: PlotMode,
) -> RenderCollections:
    """Render graphs according to the selected strategy."""
    renderer = MatplotlibRenderer()
    overlay_results: list[RenderResult] = []
    individual_results: list[RenderResult] = []

    if plot_mode == PlotMode.OVERLAY:
        overlay_results = OverlayStrategy(renderer).render(df, config)
        if not config.output.no_individual:
            individual_output = IndividualStrategy(renderer).render(df, config)
            if individual_output is not None:
                individual_results = individual_output
    else:
        individual_output = IndividualStrategy(renderer).render(df, config)
        if individual_output is not None:
            individual_results = individual_output

    return RenderCollections(
        overlay=overlay_results,
        individual=individual_results,
    )


def _build_matplotlib_artifacts(
    collections: RenderCollections,
) -> list[MatplotlibArtifact]:
    """Convert render results into in-memory artifacts."""
    artifacts: list[MatplotlibArtifact] = []
    for result in collections.all_results():
        if result.format.lower() == "html":
            continue
        metadata = {"format": result.format}
        artifacts.append(
            MatplotlibArtifact(
                filename=result.filename,
                figure=result.figure,
                metadata=metadata,
            ),
        )
    return artifacts


def _save_render_results(
    collections: RenderCollections,
    output_dir_path: Path,
    main_image_dir_path: Path | None,
) -> None:
    """Persist rendered results to disk."""
    if not collections.overlay and not collections.individual:
        return

    writer = FileWriter()
    validator = PathValidator()
    output_path = validator.ensure_directory(output_dir_path)
    main_image_path: Path | None = None
    if main_image_dir_path is not None:
        main_image_path = validator.ensure_directory(main_image_dir_path)

    for result in collections.overlay:
        target_dir = output_path
        if (
            main_image_path is not None
            and result.format.lower() != "html"
        ):
            target_dir = main_image_path
        writer.save_figure(
            result.figure,
            target_dir,
            result.filename,
            result.format,
        )

    for result in collections.individual:
        writer.save_figure(
            result.figure,
            output_path,
            result.filename,
            result.format,
        )


def csv2graph(
    csv_path: str | Path,
    output_dir: str | Path | None = None,
    main_image_dir: str | Path | None = None,
    csv_format: Literal["standard", "transpose", "noheader"] = "standard",
    logy: bool = False,
    logx: bool = False,
    html: bool = False,
    mode: Literal["overlay", "individual"] = "overlay",
    x_col: int | str | list[int | str] | None = None,
    y_cols: int | str | list[int | str] | None = None,
    direction_cols: int | str | list[int | str] | None = None,
    direction_filter: list[str] | None = None,
    direction_colors: dict[str, str] | None = None,
    title: str | None = None,
    legend_info: str | None = None,
    legend_loc: str | int | None = None,
    xlim: tuple[float | None, float | None] | None = None,
    ylim: tuple[float | None, float | None] | None = None,
    grid: bool = False,
    invert_x: bool = False,
    invert_y: bool = False,
    no_individual: bool = False,
    max_legend_items: int | None = None,
) -> None:
    """Generate graph from CSV file.

    Main user-facing API for CSV to graph conversion.

    Args:
        csv_path: Path to CSV file
        output_dir: Output directory for plots (default: same as CSV)
        main_image_dir: Directory for combined plot outputs
                        (overrides output_dir for non-HTML overlay artifacts)
        csv_format: CSV format type ("standard", "transpose", "noheader")
        logy: Use log scale for y-axis
        logx: Use log scale for x-axis
        html: Generate interactive HTML output with Plotly
        mode: Plotting mode ("overlay" or "individual")
        x_col: X-axis column specification
        y_cols: Y-axis column(s) specification
        direction_cols: Direction column(s) for filtering/coloring
        direction_filter: List of directions to include
        direction_colors: Color mapping for directions
        title: Plot title
        legend_info: Additional legend information
        legend_loc: Legend location (str or int)
        xlim: X-axis limits (min, max)
        ylim: Y-axis limits (min, max)
        grid: Show grid
        invert_x: Invert x-axis
        invert_y: Invert y-axis
        no_individual: Skip individual plots (when mode="overlay")
        max_legend_items: Maximum legend items to display

    Example:
        >>> csv2graph(
        ...     "data.csv",
        ...     output_dir="plots",
        ...     mode="overlay",
        ...     logy=True,
        ...     grid=True,
        ... )
    """
    csv_path = Path(csv_path)
    parser = ParserFactory.create(csv_format)
    df = parser.parse(csv_path)

    output_dir = csv_path.parent if output_dir is None else Path(output_dir)
    if main_image_dir is not None:
        main_image_dir = Path(main_image_dir)
    title = csv_path.stem if title is None else title

    plot_from_dataframe(
        df=df,
        output_dir=output_dir,
        main_image_dir=main_image_dir,
        logy=logy,
        logx=logx,
        html=html,
        mode=mode,
        x_col=x_col,
        y_cols=y_cols,
        direction_cols=direction_cols,
        direction_filter=direction_filter,
        direction_colors=direction_colors,
        title=title,
        legend_info=legend_info,
        legend_loc=legend_loc,
        xlim=xlim,
        ylim=ylim,
        grid=grid,
        invert_x=invert_x,
        invert_y=invert_y,
        no_individual=no_individual,
        max_legend_items=max_legend_items,
        return_fig=False,
    )


def plot_from_dataframe(
    df: pd.DataFrame,
    output_dir: str | Path,
    main_image_dir: str | Path | None = None,
    logy: bool = False,
    logx: bool = False,
    html: bool = False,
    mode: Literal["overlay", "individual"] = "overlay",
    x_col: int | str | list[int | str] | None = None,
    y_cols: int | str | list[int | str] | None = None,
    direction_cols: int | str | list[int | str] | None = None,
    direction_filter: list[str] | None = None,
    direction_colors: dict[str, str] | None = None,
    title: str | None = None,
    name: str | None = None,
    x_label: str | None = None,
    y_label: str | None = None,
    legend_info: str | None = None,
    legend_loc: str | int | None = None,
    xlim: tuple[float | None, float | None] | None = None,
    ylim: tuple[float | None, float | None] | None = None,
    grid: bool = False,
    invert_x: bool = False,
    invert_y: bool = False,
    no_individual: bool = False,
    max_legend_items: int | None = None,
    return_fig: bool = False,
) -> list[Any] | None:
    """Generate graph from pandas DataFrame.

    Generic API for plotting from any DataFrame.
    Maintains backward compatibility with existing code.

    Args:
        df: Input DataFrame
        output_dir: Output directory for plots
        main_image_dir: Directory where main rendered images are stored
        logy: Use log scale for y-axis
        logx: Use log scale for x-axis
        html: Generate interactive HTML output with Plotly
        mode: Plotting mode ("overlay" or "individual")
        x_col: X-axis column specification
        y_cols: Y-axis column(s) specification
        direction_cols: Direction column(s) for filtering/coloring
        direction_filter: List of directions to include
        direction_colors: Color mapping for directions
        title: Plot title (also used for filename if name not specified)
        name: Base filename for output
                (if specified, takes precedence over title for filenames)
        x_label: X-axis label
        y_label: Y-axis label
        legend_info: Additional legend information
        legend_loc: Legend location (str or int)
        xlim: X-axis limits (min, max)
        ylim: Y-axis limits (min, max)
        grid: Show grid
        invert_x: Invert x-axis
        invert_y: Invert y-axis
        no_individual: Skip individual plots (when mode="overlay")
        max_legend_items: Maximum legend items to display
        return_fig: Return figure objects instead of saving

    Returns:
        List of figure objects if return_fig=True, otherwise None

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({"x": [1, 2, 3], "y": [1, 4, 9]})
        >>> plot_from_dataframe(
        ...     df,
        ...     output_dir="plots",
        ...     x_col="x",
        ...     y_cols="y",
        ...     mode="overlay",
        ... )
    """
    output_dir_path = Path(output_dir)
    main_image_dir_path = Path(main_image_dir) if main_image_dir is not None else None

    normalized_columns = _normalize_columns(
        df,
        x_col=x_col,
        y_cols=y_cols,
        direction_cols=direction_cols,
    )

    direction_filters = _normalize_direction_filter(direction_filter)
    direction_config = _build_direction_config(
        filters=direction_filters,
        direction_colors=direction_colors,
    )

    plot_mode = _resolve_plot_mode(mode)
    display_title, base_filename = _determine_titles(title=title, name=name)
    formats = _determine_formats(html=html, return_fig=return_fig)

    config = _build_plot_config(
        plot_mode=plot_mode,
        normalized=normalized_columns,
        direction_config=direction_config,
        display_title=display_title,
        x_label=x_label,
        y_label=y_label,
        logx=logx,
        logy=logy,
        xlim=xlim,
        ylim=ylim,
        grid=grid,
        invert_x=invert_x,
        invert_y=invert_y,
        legend_info=legend_info,
        legend_loc=legend_loc,
        max_legend_items=max_legend_items,
        formats=formats,
        no_individual=no_individual,
        return_fig=return_fig,
        base_filename=base_filename,
        main_image_dir_path=main_image_dir_path,
    )

    collections = _collect_render_results(df, config, plot_mode)

    if return_fig:
        return _build_matplotlib_artifacts(collections)

    _save_render_results(collections, output_dir_path, main_image_dir_path)
    return None
