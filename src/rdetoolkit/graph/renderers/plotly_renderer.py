from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

try:
    import plotly.graph_objs as go  # type: ignore[import]
except ImportError:  # pragma: no cover - exercised in environments without plotly
    go = None  # type: ignore[assignment]
    _PLOTLY_IMPORT_ERROR = (
        "Plotly is required for HTML output but is not installed. "
        "Install it with: pip install plotly"
    )
else:
    _PLOTLY_IMPORT_ERROR = ""

from rdetoolkit.graph.models import Direction, PlotConfig
from rdetoolkit.graph.textutils import titleize

DEFAULT_PLOTLY_COLORS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]


@dataclass
class _PlotlyColorContext:
    """Track series color assignments for Plotly traces."""

    palette: Sequence[str]
    assignments: dict[str, str] = field(default_factory=dict)
    index: int = 0

    def color_for(self, series_name: str) -> str:
        if series_name not in self.assignments:
            self.assignments[series_name] = self.palette[self.index % len(self.palette)]
            self.index += 1
        return self.assignments[series_name]


class PlotlyRenderer:
    """Plotly-based renderer for interactive HTML graphs.

    Features:
        - Linear/Log scale toggle buttons for X and Y axes
        - Direction-based trace grouping
        - Initial scale settings from PlotConfig
        - Series-based color consistency
    """

    def render_html(self, df: pd.DataFrame, config: PlotConfig) -> go.Figure:
        """Render interactive HTML graph with Plotly.

        Migrated from legacy plot_html() (csv2graph.py L434-L589).

        Features:
            - X/Y axis Linear/Log toggle buttons
            - Direction-based trace grouping (legendgroup)
            - Initial scale from config.x_axis.scale, config.y_axis.scale
            - Series-based coloring

        Args:
            df: DataFrame containing plot data
            config: Plot configuration

        Returns:
            plotly.graph_objs.Figure object
        """
        self._ensure_plotly_available()
        x_cols, y_cols, direction_cols = self._validate_plot_columns(config)
        color_context = _PlotlyColorContext(DEFAULT_PLOTLY_COLORS)
        direction_filters, custom_direction_colors, use_custom_direction_colors = (
            self._prepare_direction_filters(config)
        )

        traces = self._build_traces(
            df=df,
            config=config,
            x_cols=x_cols,
            y_cols=y_cols,
            direction_cols=direction_cols,
            color_context=color_context,
            direction_filters=direction_filters,
            custom_direction_colors=custom_direction_colors,
            use_custom_direction_colors=use_custom_direction_colors,
        )

        layout = self._build_layout(df, config, y_cols)
        fig = go.Figure(data=traces, layout=layout)
        self._apply_legend_annotation(fig, config.legend.info)
        return fig

    def _ensure_plotly_available(self) -> None:
        if go is None:  # pragma: no cover - hit only when plotly missing
            raise ImportError(_PLOTLY_IMPORT_ERROR)

    def _validate_plot_columns(
        self,
        config: PlotConfig,
    ) -> tuple[list[int | str], list[int | str], list[int | str | None]]:
        if config.x_col is None or config.y_cols is None:
            msg = "x_col and y_cols must be specified in PlotConfig"
            raise ValueError(msg)

        x_cols = list(config.x_col) if isinstance(config.x_col, list) else [config.x_col]
        y_cols = list(config.y_cols)

        if len(x_cols) == 1 and len(y_cols) > 1:
            x_cols = x_cols * len(y_cols)
        elif len(x_cols) != len(y_cols):
            msg = f"x_cols ({len(x_cols)}) and y_cols ({len(y_cols)}) must match"
            raise ValueError(msg)

        direction_cols = (
            list(config.direction_cols)
            if config.direction_cols
            else [None] * len(y_cols)
        )
        if len(direction_cols) != len(y_cols):
            msg = f"direction_cols ({len(direction_cols)}) must match y_cols ({len(y_cols)})"
            raise ValueError(msg)

        return x_cols, y_cols, direction_cols

    def _prepare_direction_filters(
        self,
        config: PlotConfig,
    ) -> tuple[set[str], dict[str, str], bool]:
        filter_values = config.direction.filters or []
        direction_filters = {
            str(value.value) if isinstance(value, Direction) else str(value)
            for value in filter_values
            if value is not None
        }

        use_custom_colors = getattr(config.direction, "use_custom_colors", False)
        custom_colors: dict[str, str] = {}
        if use_custom_colors:
            for key, color in config.direction.colors.items():
                label = key.value if isinstance(key, Direction) else str(key)
                custom_colors[label] = color

        return direction_filters, custom_colors, use_custom_colors

    def _build_traces(
        self,
        df: pd.DataFrame,
        config: PlotConfig,
        x_cols: list[int | str],
        y_cols: list[int | str],
        direction_cols: list[int | str | None],
        color_context: _PlotlyColorContext,
        direction_filters: set[str],
        custom_direction_colors: dict[str, str],
        use_custom_direction_colors: bool,
    ) -> list[Any]:
        traces: list[Any] = []
        for x_col_idx, y_col_idx, dir_col_idx in zip(x_cols, y_cols, direction_cols):
            series_name = self._resolve_series_name(df, y_col_idx, config)
            base_color = color_context.color_for(series_name)
            traces.extend(
                self._build_series_traces(
                    df,
                    series_name,
                    x_col_idx,
                    y_col_idx,
                    dir_col_idx,
                    base_color,
                    direction_filters,
                    custom_direction_colors,
                    use_custom_direction_colors,
                ),
            )
        return traces

    def _resolve_series_name(
        self,
        df: pd.DataFrame,
        y_col_idx: int | str,
        config: PlotConfig,
    ) -> str:
        series_name = str(df.columns[y_col_idx])
        if config.humanize:
            series_name = titleize(series_name)
        return series_name

    def _build_series_traces(
        self,
        df: pd.DataFrame,
        series_name: str,
        x_col_idx: int | str,
        y_col_idx: int | str,
        dir_col_idx: int | str | None,
        base_color: str,
        direction_filters: set[str],
        custom_direction_colors: dict[str, str],
        use_custom_direction_colors: bool,
    ) -> list[Any]:
        x_data = df.iloc[:, x_col_idx]
        y_data = df.iloc[:, y_col_idx]

        if dir_col_idx is None:
            return [
                go.Scatter(
                    x=x_data,
                    y=y_data,
                    mode="lines",
                    name=series_name,
                    line={"color": base_color},
                    legendgroup=series_name,
                ),
            ]

        direction_data = df.iloc[:, dir_col_idx]
        return self._build_direction_traces(
            series_name,
            x_data,
            y_data,
            direction_data,
            base_color,
            direction_filters,
            custom_direction_colors,
            use_custom_direction_colors,
        )

    def _build_direction_traces(
        self,
        series_name: str,
        x_data: pd.Series,
        y_data: pd.Series,
        direction_data: pd.Series,
        base_color: str,
        direction_filters: set[str],
        custom_direction_colors: dict[str, str],
        use_custom_direction_colors: bool,
    ) -> list[Any]:
        unique_directions = [
            value for value in direction_data.unique() if pd.notna(value)
        ]
        traces: list[Any] = []
        first_direction = True

        for direction in unique_directions:
            direction_value = self._normalize_direction_value(direction)
            if direction_filters and direction_value not in direction_filters:
                continue

            mask = direction_data == direction
            line_color = self._select_direction_color(
                direction_value,
                base_color,
                custom_direction_colors,
                use_custom_direction_colors,
            )
            traces.append(
                go.Scatter(
                    x=x_data[mask],
                    y=y_data[mask],
                    mode="lines",
                    name=series_name,
                    line={"color": line_color},
                    legendgroup=series_name,
                    showlegend=first_direction,
                ),
            )
            first_direction = False

        return traces

    @staticmethod
    def _normalize_direction_value(direction: Any) -> str:
        return str(direction.value) if isinstance(direction, Direction) else str(direction)

    @staticmethod
    def _select_direction_color(
        direction_value: str,
        base_color: str,
        custom_direction_colors: dict[str, str],
        use_custom_direction_colors: bool,
    ) -> str:
        if not use_custom_direction_colors:
            return base_color
        return custom_direction_colors.get(direction_value, base_color)

    def _build_layout(
        self,
        df: pd.DataFrame,
        config: PlotConfig,
        y_cols: list[int | str],
    ) -> Any:
        y_reference = y_cols[0]
        default_title = (
            df.columns[y_reference]
            if isinstance(y_reference, int)
            else str(y_reference)
        )
        title = config.title if config.title else default_title
        return go.Layout(
            title=title,
            xaxis={
                "title": config.x_axis.label or "X",
                "type": config.x_axis.scale,
            },
            yaxis={
                "title": config.y_axis.label or "Y",
                "type": config.y_axis.scale,
            },
            showlegend=True,
            updatemenus=self._build_update_menus(config),
        )

    def _build_update_menus(self, config: PlotConfig) -> list[dict[str, Any]]:
        return [
            self._scale_toggle_menu(
                axis="xaxis",
                label_prefix="X",
                current_scale=config.x_axis.scale,
                position=(1.15, 1.08),
            ),
            self._scale_toggle_menu(
                axis="yaxis",
                label_prefix="Y",
                current_scale=config.y_axis.scale,
                position=(1.15, 1.03),
            ),
        ]

    def _scale_toggle_menu(
        self,
        *,
        axis: str,
        label_prefix: str,
        current_scale: str,
        position: tuple[float, float],
    ) -> dict[str, Any]:
        x_pos, y_pos = position
        return {
            "buttons": [
                {
                    "label": f"{label_prefix} Linear",
                    "method": "relayout",
                    "args": [{f"{axis}.type": "linear"}],
                },
                {
                    "label": f"{label_prefix} Log",
                    "method": "relayout",
                    "args": [{f"{axis}.type": "log"}],
                },
            ],
            "direction": "down",
            "showactive": True,
            "active": 1 if current_scale == "log" else 0,
            "x": x_pos,
            "xanchor": "left",
            "y": y_pos,
            "yanchor": "top",
            "type": "dropdown",
        }

    def _apply_legend_annotation(
        self,
        fig: Any,
        legend_info: str | None,
    ) -> None:
        if not legend_info:
            return
        legend_info_formatted = legend_info.replace("\\n", "<br>")
        fig.add_annotation(
            text=legend_info_formatted,
            xref="paper",
            yref="paper",
            x=1.0,
            y=1.02,
            xanchor="right",
            yanchor="bottom",
            showarrow=False,
            font={"size": 12},
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="rgba(0,0,0,0.2)",
            borderwidth=1,
        )
