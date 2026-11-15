from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from rdetoolkit.graph.config import (
    PlotConfigBuilder,
    determine_formats,
    determine_titles,
)
from rdetoolkit.graph.io.file_writer import FileWriter
from rdetoolkit.graph.io.path_validator import PathValidator
from rdetoolkit.graph.models import (
    AxisConfig,
    DirectionConfig,
    LegendConfig,
    MatplotlibArtifact,
    NormalizedColumns,
    OutputConfig,
    PlotConfig,
    PlotMode,
    RenderCollections,
    RenderResult,
    build_direction_config,
    normalize_direction_filter,
)
from rdetoolkit.graph.exceptions import PlotRequestError
from rdetoolkit.graph.normalizers import ColumnNormalizer
from rdetoolkit.graph.renderers.mpl_runtime import detach_figure, style_scope
from rdetoolkit.graph.strategies.all_graphs import builtin_html_renderer
from rdetoolkit.graph.strategies.render_coordinator import (
    build_matplotlib_artifacts,
    collect_render_results,
)
from rdetoolkit.graph.textutils import parse_header
from rdetoolkit.graph.validation import validate_axis_limits, validate_plot_request

if TYPE_CHECKING:
    import pandas as pd


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
    """Validate and normalize column specifications for plotting.

    Columns are resolved to positions and never round-trip through their labels, so
    duplicate headers plot when addressed by position or by the default selection,
    while a label carried by several columns is rejected as ambiguous (GE-06).

    Raises:
        ColumnNotFoundError: For an unknown label or an out-of-range position.
        TypeError: For a column spec that is neither ``int`` nor ``str``.
        PlotRequestError: ``reason="ambiguous_column"`` for a label on several columns.
        ValueError: If x and y cannot be paired ("must be equal"), there are more
            direction columns than y columns ("cannot exceed"), or no y column remains.
    """
    normalizer = ColumnNormalizer(df)
    x_positions = _column_positions(df, normalizer, 0 if x_col is None else x_col)
    normalized_y_specs = _normalize_y_specs(y_cols)
    if normalized_y_specs is None:
        excluded = set(x_positions)
        pair_y_indices = [position for position in range(df.shape[1]) if position not in excluded]
    else:
        pair_y_indices = _column_positions(df, normalizer, normalized_y_specs)
    pair_x_indices = _pair_x_positions(x_positions, pair_y_indices)
    direction_indices = _direction_positions(df, normalizer, direction_cols, len(pair_y_indices))

    if not pair_y_indices:
        msg = "DataFrame must have at least one y column for plotting"
        raise ValueError(msg)

    config_x_col: int | list[int]
    config_x_col = (
        pair_x_indices[0]
        if len(set(pair_x_indices)) == 1
        else pair_x_indices
    )

    parsed_headers = _parse_headers(df)
    first_x_idx = pair_x_indices[0]
    first_y_idx = pair_y_indices[0]
    derived_x_label = _format_axis_label(df.columns[first_x_idx], parsed_headers[first_x_idx])
    derived_y_label = _format_axis_label(df.columns[first_y_idx], parsed_headers[first_y_idx])

    return NormalizedColumns(
        x_col=config_x_col,
        y_cols=pair_y_indices,
        direction_cols=list(direction_indices),
        derived_x_label=derived_x_label,
        derived_y_label=derived_y_label,
    )


def _column_positions(
    df: pd.DataFrame,
    normalizer: ColumnNormalizer,
    spec: int | str | Sequence[int | str],
) -> list[int]:
    """Resolve one spec or a sequence of specs to column positions."""
    if isinstance(spec, (int, str)):
        return [_column_position(df, normalizer, spec)]
    if isinstance(spec, Sequence) and not isinstance(spec, bytes):
        return [_column_position(df, normalizer, item) for item in spec]
    msg = f"Invalid column specification type: {type(spec)}"
    raise TypeError(msg)


def _column_position(df: pd.DataFrame, normalizer: ColumnNormalizer, spec: int | str) -> int:
    """One position; the legacy error types for unknown columns, a typed error for ambiguous labels."""
    position = normalizer.to_index(spec)
    if isinstance(spec, str):
        matches = [index for index, label in enumerate(df.columns) if label == spec]
        if len(matches) > 1:
            msg = f"column {spec!r} matches columns {matches}; address one of them by position"
            raise PlotRequestError(msg, reason="ambiguous_column")
    return position


def _pair_x_positions(x_positions: list[int], y_positions: list[int]) -> list[int]:
    """One x position per y: a single x is shared, otherwise the counts must match."""
    if len(x_positions) == 1:
        return x_positions * len(y_positions)
    if len(x_positions) == len(y_positions):
        return x_positions
    msg = (
        f"x_col length ({len(x_positions)}) and y_cols length ({len(y_positions)}) "
        f"must be equal or x_col must be a single column"
    )
    raise ValueError(msg)


def _direction_positions(
    df: pd.DataFrame,
    normalizer: ColumnNormalizer,
    direction_cols: int | str | Sequence[int | str | None] | None,
    y_count: int,
) -> list[int | None]:
    """One direction position (or ``None``) per y; a shorter list is padded with ``None``."""
    if direction_cols is None:
        return [None] * y_count
    specs = [direction_cols] if isinstance(direction_cols, (int, str)) else list(direction_cols)
    positions: list[int | None] = []
    for spec in specs:
        if spec is None:
            positions.append(None)
        elif isinstance(spec, (int, str)):
            positions.append(_column_position(df, normalizer, spec))
        else:
            msg = f"Direction column specification must be int, str, or None, got {type(spec)}"
            raise TypeError(msg)
    if len(positions) > y_count:
        msg = f"direction_cols length ({len(positions)}) cannot exceed number of y columns ({y_count})"
        raise ValueError(msg)
    return positions + [None] * (y_count - len(positions))


def _resolve_plot_mode(mode: Literal["overlay", "individual"]) -> PlotMode:
    """Convert user-facing mode flag into PlotMode enum.

    Raises:
        PlotRequestError: ``reason="invalid_mode"`` for any value other than
            ``"overlay"`` or ``"individual"`` (v1 silently fell back to individual).
    """
    validate_plot_request(mode=mode, no_individual=None)
    return PlotMode.OVERLAY if mode == "overlay" else PlotMode.INDIVIDUAL


def _resolve_no_individual_flag(
    *,
    requested: bool | None,
    plot_mode: PlotMode,
    normalized: NormalizedColumns,
) -> bool:
    """Determine whether individual plots should be skipped."""
    if requested is not None:
        return requested
    return plot_mode == PlotMode.OVERLAY and len(normalized.y_cols) <= 1


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
    x_tick_format: Literal["auto", "plain", "sci", "eng"] = "auto",
    y_tick_format: Literal["auto", "plain", "sci", "eng"] = "auto",
    xlim: tuple[float | None, float | None] | None,
    ylim: tuple[float | None, float | None] | None,
    grid: bool,
    invert_x: bool,
    invert_y: bool,
    legend_info: str | None,
    legend_loc: str | int | None,
    max_legend_items: int | None,
    legend_policy: Literal[
        "legacy", "auto", "inside", "outside_right", "outside_bottom", "hide",
    ] = "legacy",
    legend_outside_threshold: int = 8,
    legend_bottom_threshold: int | None = 21,
    legend_ncol: int | None = None,
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
            lim=validate_axis_limits(xlim, scale="log" if logx else "linear", axis="x"),
            grid=grid,
            invert=invert_x,
            tick_format=x_tick_format,
        ),
    )
    builder.set_y_axis(
        AxisConfig(
            label=y_label or normalized.derived_y_label,
            # A label derived from the first column is re-derived per figure by the
            # planner (mixed units, individual figures); a passed y_label is kept as is.
            label_origin="explicit" if y_label else "derived",
            scale="log" if logy else "linear",
            lim=validate_axis_limits(ylim, scale="log" if logy else "linear", axis="y"),
            grid=grid,
            invert=invert_y,
            tick_format=y_tick_format,
        ),
    )
    builder.set_direction(direction_config)
    builder.set_legend(
        LegendConfig(
            info=legend_info,
            loc=legend_loc,
            max_items=max_legend_items,
            policy=legend_policy,
            outside_threshold=legend_outside_threshold,
            bottom_threshold=legend_bottom_threshold,
            ncol=legend_ncol,
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


def _save_render_results(
    collections: RenderCollections,
    output_dir_path: Path,
    main_image_dir_path: Path | None,
    html_output_dir_path: Path | None = None,
) -> None:
    """Persist rendered results to disk."""
    if not collections.overlay and not collections.individual:
        return

    writer = FileWriter()
    validator = PathValidator()
    output_path = validator.ensure_directory(output_dir_path)
    html_output_path = (
        output_path
        if html_output_dir_path is None
        else validator.ensure_directory(html_output_dir_path)
    )
    main_image_path: Path | None = None
    if main_image_dir_path is not None:
        main_image_path = validator.ensure_directory(main_image_dir_path)

    for result in collections.overlay:
        target_dir = output_path
        if result.format.lower() == "html":
            target_dir = html_output_path
        elif main_image_path is not None:
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
    html_output_dir: str | Path | None = None,
    csv_format: str = "standard",
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
    no_individual: bool | None = None,
    max_legend_items: int | None = None,
    legend_policy: Literal[
        "legacy", "auto", "inside", "outside_right", "outside_bottom", "hide",
    ] = "legacy",
    legend_outside_threshold: int = 8,
    legend_bottom_threshold: int | None = 21,
    legend_ncol: int | None = None,
    *,
    x_tick_format: Literal["auto", "plain", "sci", "eng"] = "auto",
    y_tick_format: Literal["auto", "plain", "sci", "eng"] = "auto",
) -> None:
    """Generate graph from CSV file.

    Main user-facing API for CSV to graph conversion.

    Args:
        csv_path: Path to CSV file
        output_dir: Output directory for plots (default: same as CSV)
        main_image_dir: Directory for combined plot outputs
                        (overrides output_dir for non-HTML overlay artifacts)
        html_output_dir: Directory for HTML outputs (default: CSV directory)
        csv_format: Reader id: "standard", "transpose", "noheader", "meta_block",
            "auto", or the id of a registered ``rdetoolkit.graph.readers`` entry point
        logy: Use log scale for y-axis
        logx: Use log scale for x-axis
        html: Generate interactive HTML output with Plotly (needs the plotly
            extra; a missing Plotly raises RendererUnavailableError, an
            ImportError, before anything is drawn or written)
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
        no_individual: Skip individual plots; None enables auto-detection (overlay)
        max_legend_items: Maximum legend items to display
        legend_policy: Legend placement policy. "legacy" (default) preserves
            existing behavior. "auto" chooses placement based on item count.
            "inside"/"outside_right"/"outside_bottom" force a placement.
            "hide" suppresses the legend.
        legend_outside_threshold: Item-count threshold used by "auto" to
            switch from inside to outside-right placement (default: 8).
        legend_bottom_threshold: Item count at or above which "auto"
            switches to outside-bottom placement (default: 21). None
            disables the automatic switch to bottom placement.
        legend_ncol: Number of legend columns for "outside_bottom"
            placement (defaults to 3 when None).
        x_tick_format: X-axis tick label formatter
                       ("auto", "plain", "sci", or "eng")
        y_tick_format: Y-axis tick label formatter
                       ("auto", "plain", "sci", or "eng")

    Example:
        >>> csv2graph(
        ...     "data.csv",
        ...     output_dir="plots",
        ...     mode="overlay",
        ...     logy=True,
        ...     grid=True,
        ... )
    """
    from rdetoolkit.graph.readers import read_table

    csv_path = Path(csv_path)
    # The three legacy ids stay case-insensitive as with ParserFactory.create; any
    # other id (or "auto") goes through the reader registry and its entry points.
    legacy_id = csv_format.lower()
    reader_id = legacy_id if legacy_id in ("standard", "transpose", "noheader") else csv_format
    df = read_table(csv_path, reader=reader_id).frame

    if html_output_dir is not None and not isinstance(html_output_dir, (str, Path)):
        msg = "html_output_dir must be a str, Path, or None"
        raise TypeError(msg)
    output_dir = csv_path.parent if output_dir is None else Path(output_dir)
    if main_image_dir is not None:
        main_image_dir = Path(main_image_dir)
    html_output_dir = csv_path.parent if html_output_dir is None else Path(html_output_dir)
    title = csv_path.stem if title is None else title

    plot_from_dataframe(
        df=df,
        output_dir=output_dir,
        main_image_dir=main_image_dir,
        html_output_dir=html_output_dir,
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
        legend_policy=legend_policy,
        legend_outside_threshold=legend_outside_threshold,
        legend_bottom_threshold=legend_bottom_threshold,
        legend_ncol=legend_ncol,
        x_tick_format=x_tick_format,
        y_tick_format=y_tick_format,
        return_fig=False,
    )


def plot_from_dataframe(
    df: pd.DataFrame,
    output_dir: str | Path,
    main_image_dir: str | Path | None = None,
    html_output_dir: str | Path | None = None,
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
    no_individual: bool | None = None,
    max_legend_items: int | None = None,
    return_fig: bool = False,
    *,
    legend_policy: Literal[
        "legacy", "auto", "inside", "outside_right", "outside_bottom", "hide",
    ] = "legacy",
    legend_outside_threshold: int = 8,
    legend_bottom_threshold: int | None = 21,
    legend_ncol: int | None = None,
    x_tick_format: Literal["auto", "plain", "sci", "eng"] = "auto",
    y_tick_format: Literal["auto", "plain", "sci", "eng"] = "auto",
) -> list[Any] | None:
    """Generate graph from pandas DataFrame.

    Generic API for plotting from any DataFrame.
    Maintains backward compatibility with existing code.

    Args:
        df: Input DataFrame
        output_dir: Output directory for plots
        main_image_dir: Directory where main rendered images are stored
        html_output_dir: Directory for HTML artifacts (defaults to output_dir)
        logy: Use log scale for y-axis
        logx: Use log scale for x-axis
        html: Generate interactive HTML output with Plotly (needs the plotly
            extra; a missing Plotly raises RendererUnavailableError, an
            ImportError, before anything is drawn or written)
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
        no_individual: Skip individual plots; None enables auto-detection (overlay)
        max_legend_items: Maximum legend items to display
        return_fig: Return figure objects instead of saving
        legend_policy: Legend placement policy. "legacy" (default) preserves
            existing behavior. "auto" chooses placement based on item count.
            "inside"/"outside_right"/"outside_bottom" force a placement.
            "hide" suppresses the legend.
        legend_outside_threshold: Item-count threshold used by "auto" to
            switch from inside to outside-right placement (default: 8).
        legend_bottom_threshold: Item count at or above which "auto"
            switches to outside-bottom placement (default: 21). None
            disables the automatic switch to bottom placement.
        legend_ncol: Number of legend columns for "outside_bottom"
            placement (defaults to 3 when None).
        x_tick_format: X-axis tick label formatter
                       ("auto", "plain", "sci", or "eng")
        y_tick_format: Y-axis tick label formatter
                       ("auto", "plain", "sci", or "eng")

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
    if no_individual is not None and not isinstance(no_individual, bool):
        msg = "no_individual must be True, False, or None"
        raise TypeError(msg)
    if html_output_dir is not None and not isinstance(html_output_dir, (str, Path)):
        msg = "html_output_dir must be a str, Path, or None"
        raise TypeError(msg)

    # Reject the request before any column resolution or filesystem access so an
    # invalid mode or a switch combination that yields no figure never writes anything.
    validate_plot_request(mode=mode, no_individual=no_individual)

    output_dir_path = Path(output_dir)
    main_image_dir_path = Path(main_image_dir) if main_image_dir is not None else None
    html_output_dir_path = (
        Path(html_output_dir) if html_output_dir is not None else output_dir_path
    )

    normalized_columns = _normalize_columns(
        df,
        x_col=x_col,
        y_cols=y_cols,
        direction_cols=direction_cols,
    )

    direction_filters = normalize_direction_filter(direction_filter)
    direction_config = build_direction_config(
        filters=direction_filters,
        direction_colors=direction_colors,
    )

    plot_mode = _resolve_plot_mode(mode)
    resolved_no_individual = _resolve_no_individual_flag(
        requested=no_individual,
        plot_mode=plot_mode,
        normalized=normalized_columns,
    )
    display_title, base_filename = determine_titles(title=title, name=name)
    formats = determine_formats(html=html, return_fig=return_fig)
    if "html" in formats:
        # Fail on a missing Plotly before any figure is drawn or any file is written.
        builtin_html_renderer()

    config = _build_plot_config(
        plot_mode=plot_mode,
        normalized=normalized_columns,
        direction_config=direction_config,
        display_title=display_title,
        x_label=x_label,
        y_label=y_label,
        logx=logx,
        logy=logy,
        x_tick_format=x_tick_format,
        y_tick_format=y_tick_format,
        xlim=xlim,
        ylim=ylim,
        grid=grid,
        invert_x=invert_x,
        invert_y=invert_y,
        legend_info=legend_info,
        legend_loc=legend_loc,
        max_legend_items=max_legend_items,
        legend_policy=legend_policy,
        legend_outside_threshold=legend_outside_threshold,
        legend_bottom_threshold=legend_bottom_threshold,
        legend_ncol=legend_ncol,
        formats=formats,
        no_individual=resolved_no_individual,
        return_fig=return_fig,
        base_filename=base_filename,
        main_image_dir_path=main_image_dir_path,
    )

    # The legacy renderer applies the house style to rcParams; the scope keeps that
    # change away from the caller, and figures are saved inside it so they look as before.
    with style_scope():
        collections = _collect_owned(df, config, plot_mode)
        if return_fig:
            return _hand_over(collections)
        try:
            _save_render_results(
                collections,
                output_dir_path,
                main_image_dir_path,
                html_output_dir_path,
            )
        finally:
            # Save-only figures are owned by the facade: close them even when writing fails.
            _close_figures(collections.all_results())
    return None


def _collect_owned(df: pd.DataFrame, config: PlotConfig, plot_mode: PlotMode) -> RenderCollections:
    """Render through the patchable module seam; close what a failed render already opened."""
    before = set(plt.get_fignums())
    try:
        return collect_render_results(df, config, plot_mode)
    except BaseException:
        # Figures finished before the failure never reach the caller.
        for number in sorted(set(plt.get_fignums()) - before):
            plt.close(number)
        raise


def _hand_over(collections: RenderCollections) -> list[MatplotlibArtifact]:
    """Detach every Matplotlib figure inside the style scope, then give them to the caller."""
    results = collections.all_results()
    try:
        for figure in _matplotlib_figures(results):
            detach_figure(figure)
    except BaseException:
        _close_figures(results)
        raise
    return build_matplotlib_artifacts(collections)


def _matplotlib_figures(results: Sequence[RenderResult]) -> list[Figure]:
    """Distinct Matplotlib figures of the results; foreign figures (Plotly, stubs) are skipped."""
    figures: dict[int, Figure] = {}
    for result in results:
        if isinstance(result.figure, Figure):
            figures.setdefault(id(result.figure), result.figure)
    return list(figures.values())


def _close_figures(results: Sequence[RenderResult]) -> None:
    for figure in _matplotlib_figures(results):
        plt.close(figure)
