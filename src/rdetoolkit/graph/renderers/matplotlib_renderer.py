
from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from rdetoolkit.graph.models import Direction, PlotConfig
from rdetoolkit.graph.config import apply_matplotlib_config
from rdetoolkit.graph.textutils import parse_header, titleize

CENTER_POSITION = 0.5
LEGEND_RIGHT_THRESHOLD = 0.7
TEXT_Y_THRESHOLD = 0.9


class MatplotlibRenderer:
    """Matplotlib-based renderer for static plots."""

    def render_overlay(self, df: pd.DataFrame, config: PlotConfig) -> Figure:
        """Render all data series on a single graph.

        This implements the logic from legacy plot_all_graphs().

        Args:
            df: DataFrame containing plot data
            config: Plot configuration

        Workflow:
            1. Apply matplotlib configuration
            2. Create figure and axes
            3. Plot all y_cols with direction-based coloring
            4. Setup legend with max_items control
            5. Apply axis labels, limits, grid, invert
            6. Return Figure (no file I/O)
        """
        apply_matplotlib_config()
        fig, ax = plt.subplots(figsize=(8.85, 8), tight_layout=True)
        x_cols, y_cols, direction_cols = self._resolve_overlay_columns(df, config)
        color_map, direction_filters = self._build_direction_context(config)
        legend_handles, legend_labels = self._plot_overlay_series(
            ax,
            df,
            config,
            x_cols,
            y_cols,
            direction_cols,
            color_map,
            direction_filters,
        )

        self._configure_axes(ax, config, config.title)
        self._apply_legend(ax, legend_handles, legend_labels, config)

        return fig



    def render_individual(
        self,
        df: pd.DataFrame,
        config: PlotConfig,
        y_col_index: int,
        series_position: int | None = None,
    ) -> Figure:
        """Render individual graph for a single series.

        This implements the logic from legacy plot_individual_graphs().

        Args:
            df: DataFrame containing plot data
            config: Plot configuration
            y_col_index: Index of the y column to plot
            series_position: Position of the series within y_cols (0-based).
                When omitted, defaults to the first series.

        Workflow:
            1. Apply matplotlib configuration
            2. Create figure for single series
            3. Plot with direction-based line splitting
            4. Setup title: "{config.title} - {series_name}"
            5. Apply axis configuration
            6. Return Figure
        """
        apply_matplotlib_config()
        series_idx = 0 if series_position is None else series_position

        fig, ax = plt.subplots(figsize=(8.85, 8), tight_layout=True)

        x_col_idx = self._resolve_x_column_index(df, config, series_idx)
        if config.y_cols is None:
            msg = "y_cols must be specified in PlotConfig"
            raise ValueError(msg)

        x_data = df.iloc[:, x_col_idx]
        y_data = df.iloc[:, y_col_index]
        series_label = self._build_series_label(df, y_col_index, config)

        direction_col_idx = self._resolve_direction_column_index(df, config, series_idx)
        color_map, direction_filters = self._build_direction_context(config)
        legend_handles, legend_labels = self._plot_series(
            ax,
            df,
            config,
            x_data,
            y_data,
            direction_col_idx,
            color_map,
            direction_filters,
        )

        title_base = config.title if config.title else "Plot"
        plot_title = f"{title_base} - {series_label}"
        self._configure_axes(ax, config, plot_title)

        if len(legend_handles) > 1:
            self._apply_legend(ax, legend_handles, legend_labels, config)

        return fig

    def _resolve_overlay_columns(
        self,
        df: pd.DataFrame,
        config: PlotConfig,
    ) -> tuple[list[int], list[int], list[int | None]]:
        if config.x_col is None or config.y_cols is None:
            msg = "x_col and y_cols must be specified in PlotConfig"
            raise ValueError(msg)

        x_specs = config.x_col if isinstance(config.x_col, list) else [config.x_col]
        x_cols = [_resolve_column_index(df, spec) for spec in x_specs]
        y_cols = [_resolve_column_index(df, spec) for spec in config.y_cols]

        if len(x_cols) == 1 and len(y_cols) > 1:
            x_cols = x_cols * len(y_cols)
        elif len(x_cols) != len(y_cols):
            msg = f"x_cols ({len(x_cols)}) and y_cols ({len(y_cols)}) must match"
            raise ValueError(msg)

        direction_cols = _resolve_column_indices(df, config.direction_cols, len(y_cols))

        return x_cols, y_cols, direction_cols

    def _build_direction_context(
        self,
        config: PlotConfig,
    ) -> tuple[dict[object, str], set[str]]:
        color_map: dict[object, str] = {}
        if getattr(config.direction, "use_custom_colors", False):
            for key, color in config.direction.colors.items():
                color_map[key] = color
                if isinstance(key, Direction):
                    color_map[key.value] = color

        filter_values = config.direction.filters or []
        filters = {
            (value.value if isinstance(value, Direction) else str(value))
            for value in filter_values
            if value is not None
        }

        return color_map, filters

    def _plot_overlay_series(
        self,
        ax: Any,
        df: pd.DataFrame,
        config: PlotConfig,
        x_cols: list[int],
        y_cols: list[int],
        direction_cols: list[int | None],
        color_map: dict[object, str],
        direction_filters: set[str],
    ) -> tuple[list[Any], list[str]]:
        series_colors = plt.cm.tab10.colors  # type: ignore[attr-defined]
        legend_handles: list[Any] = []
        legend_labels: list[str] = []

        for index, (x_idx, y_idx, direction_idx) in enumerate(
            zip(x_cols, y_cols, direction_cols)):
            x_data = df.iloc[:, x_idx]
            y_data = df.iloc[:, y_idx]
            raw_series_name = df.columns[y_idx]
            parsed_series, parsed_label, _ = parse_header(str(raw_series_name))
            series_label = parsed_series or parsed_label or str(raw_series_name)
            if config.humanize:
                series_label = titleize(series_label)

            base_color = series_colors[index % len(series_colors)]
            if direction_idx is not None:
                direction_data = df.iloc[:, direction_idx]
                unique_directions = [
                    direction
                    for direction in direction_data.unique()
                    if pd.notna(direction)
                ]
                first_segment = True
                for direction in unique_directions:
                    direction_value_raw = (
                        direction.value
                        if isinstance(direction, Direction) else direction
                    )
                    direction_value = str(direction_value_raw)
                    if direction_filters and direction_value not in direction_filters:
                        continue

                    mask = direction_data == direction
                    dir_color = color_map.get(direction)
                    if dir_color is None:
                        dir_color = color_map.get(direction_value, base_color)

                    label = series_label if first_segment else "_nolegend_"
                    line, = ax.plot(
                        x_data[mask],
                        y_data[mask],
                        color=dir_color,
                        label=label,
                        linewidth=1.5,
                    )
                    if first_segment:
                        legend_handles.append(line)
                        legend_labels.append(series_label)
                        first_segment = False
            else:
                line, = ax.plot(
                    x_data,
                    y_data,
                    color=base_color,
                    label=series_label,
                    linewidth=1.5,
                )
                legend_handles.append(line)
                legend_labels.append(series_label)

        return legend_handles, legend_labels

    def _configure_axes(self, ax: Any, config: PlotConfig, title: str | None) -> None:
        ax.set_xlabel(config.x_axis.label or "X")
        ax.set_ylabel(config.y_axis.label or "Y")

        if config.x_axis.scale == "log":
            ax.set_xscale("log")
        if config.y_axis.scale == "log":
            ax.set_yscale("log")

        if config.x_axis.lim:
            ax.set_xlim(config.x_axis.lim)
        if config.y_axis.lim:
            ax.set_ylim(config.y_axis.lim)

        if config.x_axis.grid or config.y_axis.grid:
            ax.grid(True, alpha=0.3)

        if config.x_axis.invert:
            ax.invert_xaxis()
        if config.y_axis.invert:
            ax.invert_yaxis()

        if title:
            title_artist = ax.set_title(title, pad=20, loc="center")
            title_pos = title_artist.get_position()
            if title_pos[0] != CENTER_POSITION:
                title_artist.set_position((CENTER_POSITION, title_pos[1]))
            title_artist.set_horizontalalignment("center")

    def _apply_legend(
        self,
        ax: Any,
        handles: list[Any],
        labels: list[str],
        config: PlotConfig,
    ) -> None:
        legend_obj = None

        filtered_handles: list[Any] = []
        filtered_labels: list[str] = []
        seen_labels: set[str] = set()

        for handle, label in zip(handles, labels):
            if not label or label == "_nolegend_":
                continue
            if label in seen_labels:
                continue
            seen_labels.add(label)
            filtered_handles.append(handle)
            filtered_labels.append(label)

        should_render = False
        if filtered_labels:
            show_threshold = len(filtered_labels) > 1
            if config.legend.loc is not None:
                show_threshold = True

            max_items = config.legend.max_items
            within_limit = (
                max_items is None
                or len(filtered_labels) <= max_items
            )

            should_render = show_threshold and within_limit

        if should_render:
            legend_kwargs: dict[str, Any] = {}
            if config.legend.loc is not None:
                legend_kwargs["loc"] = config.legend.loc
            legend_obj = ax.legend(filtered_handles, filtered_labels, **legend_kwargs)

        if config.legend.info:
            self._add_legend_info(ax, legend_obj, config.legend.info)

    def _add_legend_info(
        self,
        ax: Any,
        legend_obj: Any,
        legend_info: str,
    ) -> None:
        """Render additional legend info text near the legend or top-right."""
        info_text = legend_info.replace("\\n", "\n")
        if not info_text:
            return

        fontsize = self._determine_info_fontsize(legend_obj)
        text_x, text_y, halign, valign = self._calculate_info_position(ax, legend_obj)
        self._draw_info_text(ax, info_text, fontsize, text_x, text_y, halign, valign)

    def _resolve_x_column_index(
        self,
        df: pd.DataFrame,
        config: PlotConfig,
        series_position: int,
    ) -> int:
        if config.x_col is None:
            msg = "x_col must be specified in PlotConfig"
            raise ValueError(msg)

        if isinstance(config.x_col, list):
            resolved_x_cols = [_resolve_column_index(df, col) for col in config.x_col]
            if not resolved_x_cols:
                msg = "At least one x_col is required when providing a list"
                raise ValueError(msg)
            if series_position < len(resolved_x_cols):
                return resolved_x_cols[series_position]
            return resolved_x_cols[0]

        return _resolve_column_index(df, config.x_col)

    def _resolve_direction_column_index(
        self,
        df: pd.DataFrame,
        config: PlotConfig,
        series_position: int,
    ) -> int | None:
        if not config.direction_cols or config.y_cols is None:
            return None

        resolved_direction_cols = _resolve_column_indices(
            df,
            config.direction_cols,
            len(config.y_cols),
        )
        if series_position < len(resolved_direction_cols):
            return resolved_direction_cols[series_position]
        return None

    def _build_series_label(
        self,
        df: pd.DataFrame,
        y_col_index: int,
        config: PlotConfig,
    ) -> str:
        raw_series_name = df.columns[y_col_index]
        series_name, series_label_text, _ = parse_header(str(raw_series_name))
        series_label = series_name or series_label_text or str(raw_series_name)
        if config.humanize:
            series_label = titleize(series_label)
        return series_label

    def _plot_series(
        self,
        ax: Any,
        df: pd.DataFrame,
        config: PlotConfig,
        x_data: pd.Series,
        y_data: pd.Series,
        direction_col_idx: int | None,
        color_map: dict[object, str],
        direction_filters: set[str],
    ) -> tuple[list[Any], list[str]]:
        if direction_col_idx is None:
            ax.plot(x_data, y_data, linewidth=1.5)
            return [], []

        return self._plot_direction_segments(
            ax,
            df,
            config,
            direction_col_idx,
            x_data,
            y_data,
            color_map,
            direction_filters,
        )

    def _plot_direction_segments(
        self,
        ax: Any,
        df: pd.DataFrame,
        config: PlotConfig,
        direction_col_idx: int,
        x_data: pd.Series,
        y_data: pd.Series,
        color_map: dict[object, str],
        direction_filters: set[str],
    ) -> tuple[list[Any], list[str]]:
        direction_data = df.iloc[:, direction_col_idx]
        unique_directions = [
            value for value in direction_data.unique() if pd.notna(value)
        ]

        legend_handles: list[Any] = []
        legend_labels: list[str] = []
        for direction in unique_directions:
            direction_value = self._normalize_direction_value(direction)
            if direction_filters and direction_value not in direction_filters:
                continue

            mask = direction_data == direction
            color_kwargs = self._resolve_direction_color(
                config,
                direction,
                direction_value,
                color_map,
            )
            line, = ax.plot(
                x_data[mask],
                y_data[mask],
                linewidth=1.5,
                label=direction_value,
                **color_kwargs,
            )
            legend_handles.append(line)
            legend_labels.append(direction_value)

        return legend_handles, legend_labels

    @staticmethod
    def _normalize_direction_value(direction: Any) -> str:
        return str(direction.value) if isinstance(direction, Direction) else str(direction)

    def _resolve_direction_color(
        self,
        config: PlotConfig,
        direction: Any,
        direction_value: str,
        color_map: dict[object, str],
    ) -> dict[str, Any]:
        if not getattr(config.direction, "use_custom_colors", False):
            return {}

        color = color_map.get(direction)
        if color is None:
            color = color_map.get(direction_value)
        if color is None:
            return {}
        return {"color": color}

    def _determine_info_fontsize(self, legend_obj: Any) -> float:
        default_font = plt.rcParams.get("legend.fontsize", plt.rcParams.get("font.size", 12))
        fontsize = self._coerce_font_size(default_font)
        if legend_obj is not None:
            legend_texts = legend_obj.get_texts()
            if legend_texts:
                fontsize = max(8, legend_texts[0].get_fontsize() - 2)
        return fontsize

    def _calculate_info_position(
        self,
        ax: Any,
        legend_obj: Any,
    ) -> tuple[float, float, str, str]:
        default_position = (0.98, 0.98, "right", "top")
        renderer = self._prepare_renderer(ax, legend_obj)
        if legend_obj is None or renderer is None:
            return default_position

        legend_bbox_axes = legend_obj.get_window_extent(renderer=renderer)
        legend_bbox_axes = legend_bbox_axes.transformed(ax.transAxes.inverted())

        legend_center_x = (legend_bbox_axes.x0 + legend_bbox_axes.x1) / 2
        legend_center_y = (legend_bbox_axes.y0 + legend_bbox_axes.y1) / 2
        is_right = (
            legend_center_x > CENTER_POSITION
            or legend_bbox_axes.x1 > LEGEND_RIGHT_THRESHOLD
        )
        is_bottom = legend_center_y < CENTER_POSITION

        text_y, valign = self._compute_vertical_position(legend_bbox_axes, is_bottom)
        text_x, halign = self._compute_horizontal_position(
            legend_bbox_axes,
            is_right,
            text_y,
            is_bottom,
        )
        text_y = max(min(text_y, 0.98), 0.02)
        return text_x, text_y, halign, valign

    def _draw_info_text(
        self,
        ax: Any,
        info_text: str,
        fontsize: float,
        x: float,
        y: float,
        halign: str,
        valign: str,
    ) -> None:
        ax.text(
            x,
            y,
            info_text,
            transform=ax.transAxes,
            fontsize=fontsize,
            verticalalignment=valign,
            horizontalalignment=halign,
            linespacing=1.2,
        )

    def _prepare_renderer(self, ax: Any, legend_obj: Any) -> Any:
        if legend_obj is None:
            return None
        figure = ax.figure
        canvas = getattr(figure, "canvas", None)
        if canvas is None:
            return None
        canvas.draw()
        try:
            return canvas.get_renderer()
        except AttributeError:
            return None

    @staticmethod
    def _compute_vertical_position(
        legend_bbox_axes: Any,
        is_bottom: bool,
    ) -> tuple[float, str]:
        if is_bottom:
            if legend_bbox_axes.y1 + 0.05 < 1.0:
                return legend_bbox_axes.y1 + 0.02, "bottom"
            return 0.98, "top"
        return legend_bbox_axes.y0 - 0.05, "top"

    @staticmethod
    def _compute_horizontal_position(
        legend_bbox_axes: Any,
        is_right: bool,
        text_y: float,
        is_bottom: bool,
    ) -> tuple[float, str]:
        if is_bottom and text_y > TEXT_Y_THRESHOLD:
            return 0.98, "right"
        if is_right:
            return legend_bbox_axes.x1, "right"
        return legend_bbox_axes.x0, "left"

    @staticmethod
    def _coerce_font_size(font_value: Any) -> float:
        try:
            numeric = float(font_value)
        except (TypeError, ValueError):
            numeric = 12.0
        return max(8, numeric - 2)

def _resolve_column_index(df: pd.DataFrame, column: int | str) -> int:
    """Resolve a column specification (index or name) into a column index."""
    if isinstance(column, int):
        return column

    loc = df.columns.get_loc(column)
    if isinstance(loc, slice):
        emsg = (
            "Column specification "
            f"'{column}' resolved to a slice, expected single column"
        )
        raise ValueError(emsg)
    if isinstance(loc, list):
        emsg = f"Column specification '{column}' resolved to multiple columns: {loc}"
        raise ValueError(emsg)
    return int(loc)


def _resolve_column_indices(
    df: pd.DataFrame,
    columns: list[int | str | None] | None,
    default_length: int,
) -> list[int | None]:
    """Resolve optional column specifications into indices, preserving None entries."""
    if columns is None:
        return [None] * default_length

    resolved: list[int | None] = []
    for column in columns:
        if column is None:
            resolved.append(None)
        else:
            resolved.append(_resolve_column_index(df, column))

    if len(resolved) > default_length:
        emsg = (
            f"direction_cols length ({len(resolved)}) cannot exceed number of y columns"
            f" ({default_length})"
        )
        raise ValueError(emsg)

    while len(resolved) < default_length:
        resolved.append(None)

    return resolved
