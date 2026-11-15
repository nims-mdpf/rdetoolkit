"""Plotly renderer: draws a ``PlotPlan`` as an interactive HTML figure.

``render(plan, figure, data)`` is the plan-consuming entry point; the legacy
``render_html(df, config)`` builds the plan with ``compat.plan_from_config`` (Plotly
legacy labels, C-12) and draws it. Series selection, direction splits, legend roles
and colours come from the plan, exactly as for Matplotlib (GE-06).

The module global ``go`` is read at call time (tests replace it, C-13) and is
``None`` when Plotly is not installed.
"""

from __future__ import annotations

from typing import Any, Final

import pandas as pd

try:
    import plotly.graph_objs as go
except ImportError:  # pragma: no cover - exercised in environments without plotly
    go = None

from rdetoolkit.graph import compat
from rdetoolkit.graph.exceptions import RendererUnavailableError, UnsupportedFormatError
from rdetoolkit.graph.legend_policy import resolve_legend_policy
from rdetoolkit.graph.models import PlotConfig
from rdetoolkit.graph.plan import FigurePlan, PlotData, PlotPlan, SeriesPlan
from rdetoolkit.graph.renderers.base import RendererCapabilities
from rdetoolkit.graph.spec import AxisSpec, LegendSpec

_PLOTLY_INSTALL_HINT: Final = 'pip install "rdetoolkit[plotly]"'
_PLOTLY_IMPORT_ERROR: Final = (
    "Plotly is required for HTML output but is not installed. "
    f"Install it with: {_PLOTLY_INSTALL_HINT}"
)

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
_TRACE_MODES: Final = {"line": "lines", "scatter": "markers"}
_PIXELS_PER_INCH: Final = 100
# Individual figures stay out of the declared kinds: HTML is an overlay artifact
# (format matrix), although ``render`` itself can draw any planned figure.
_CAPABILITIES: Final = RendererCapabilities(
    renderer_id="plotly",
    formats=frozenset({"html"}),
    figure_kinds=frozenset({"overlay"}),
    requires=("plotly",),
    install_hint=_PLOTLY_INSTALL_HINT,
)


class PlotlyRenderer:
    """Plotly-based renderer for interactive HTML graphs.

    Features:
        - Linear/Log scale toggle buttons for X and Y axes
        - Direction-based trace grouping
        - Initial scale settings from the plan
        - Position-based series colours shared with the Matplotlib renderer
    """

    @property
    def capabilities(self) -> RendererCapabilities:
        """HTML for overlay figures; needs the optional ``plotly`` module."""
        return _CAPABILITIES

    def export(self, handle: Any, fmt: str, *, dpi: int) -> bytes:  # noqa: ARG002 - HTML has no resolution
        """Serialize a figure as the HTML document ``write_html`` would write.

        Args:
            handle: A figure returned by ``render``.
            fmt: ``"html"``.
            dpi: Ignored.

        Returns:
            The UTF-8 encoded HTML document.

        Raises:
            UnsupportedFormatError: For any other format.
        """
        if fmt.lower() != "html":
            msg = f"PlotlyRenderer cannot export {fmt!r}; supported formats: ['html']"
            raise UnsupportedFormatError(msg)
        html: str = handle.to_html()
        return html.encode("utf-8")

    def close(self, handle: Any) -> None:
        """Release a figure; Plotly figures hold no external resources."""

    def render_html(self, df: pd.DataFrame, config: PlotConfig) -> go.Figure:
        """Render an interactive HTML graph (legacy adapter).

        Args:
            df: DataFrame containing plot data
            config: Plot configuration

        Returns:
            plotly.graph_objs.Figure object

        Raises:
            RendererUnavailableError: An ``ImportError``, if Plotly is not installed.
            ValueError: For column specs that cannot be planned.
        """
        self._ensure_plotly_available()
        plan = compat.plan_from_config(
            df,
            config,
            label_of=compat.legacy_plotly_label,
            axis_label_of=compat.legacy_plotly_axis_label,
        )
        return self.render(plan, plan.figures[0], PlotData(frames=(df,)))

    def render(self, plan: PlotPlan, figure: FigurePlan, data: PlotData) -> go.Figure:
        """Draw one planned figure as a Plotly figure.

        Args:
            plan: The plan.
            figure: One of ``plan.figures``.
            data: The frames the plan was built from.

        Returns:
            plotly.graph_objs.Figure object

        Raises:
            RendererUnavailableError: An ``ImportError``, if Plotly is not installed.
        """
        self._ensure_plotly_available()
        by_id = {entry.series_id: entry for entry in plan.series}
        series = [by_id[series_id] for series_id in figure.series_ids]
        traces = [trace for entry in series for trace in self._series_traces(plan, entry, data)]
        legend_item_count = self._count_legend_visible_traces(traces)
        layout = self._build_layout(plan, figure, series, legend_item_count)
        fig = go.Figure(data=traces, layout=layout)
        self._apply_legend_annotation(fig, plan.legend.info)
        return fig

    @staticmethod
    def _count_legend_visible_traces(traces: list[Any]) -> int:
        """Count traces that will appear as legend entries.

        Direction filtering can drop configured series entirely, and split
        series mark only their first segment with showlegend=True, so the
        legend size must be derived from the built traces rather than the
        configured series count.
        """
        return sum(
            1 for trace in traces
            if getattr(trace, "showlegend", True) is not False
        )

    def _ensure_plotly_available(self) -> None:
        # Kept in the render path in addition to the engine's up-front check (C-14).
        if go is None:
            raise RendererUnavailableError(_PLOTLY_IMPORT_ERROR)

    @staticmethod
    def _series_traces(plan: PlotPlan, series: SeriesPlan, data: PlotData) -> list[Any]:
        """One trace per segment; only the first segment of a legend owner is listed."""
        base_color = DEFAULT_PLOTLY_COLORS[series.color_index % len(DEFAULT_PLOTLY_COLORS)]
        mode = _TRACE_MODES[plan.mark]
        style_key = "line" if plan.mark == "line" else "marker"
        traces: list[Any] = []
        for position, (direction, x_values, y_values) in enumerate(data.segments(series)):
            color = base_color if direction is None else plan.direction_colors.get(direction, base_color)
            traces.append(
                go.Scatter(
                    x=x_values,
                    y=y_values,
                    mode=mode,
                    name=series.label,
                    legendgroup=series.label,
                    showlegend=series.show_in_legend and position == 0,
                    **{style_key: {"color": color}},
                ),
            )
        return traces

    def _build_layout(
        self,
        plan: PlotPlan,
        figure: FigurePlan,
        series: list[SeriesPlan],
        legend_item_count: int,
    ) -> Any:
        # v1 falls back to the raw header of the first series when there is no title.
        title = figure.title if figure.title else series[0].y_name
        showlegend, legend_layout = self._resolve_legend_layout(plan.legend, legend_item_count)
        layout_kwargs: dict[str, Any] = {
            "title": title,
            "xaxis": self._build_axis_layout(plan.x_axis, figure.x_label or "X"),
            "yaxis": self._build_axis_layout(plan.y_axis, figure.y_label or "Y"),
            "showlegend": showlegend,
            "updatemenus": self._build_update_menus(plan),
        }
        if legend_layout is not None:
            layout_kwargs["legend"] = legend_layout
        layout_kwargs.update(_explicit_size(plan))
        return go.Layout(**layout_kwargs)

    def _resolve_legend_layout(
        self,
        legend: LegendSpec,
        legend_item_count: int,
    ) -> tuple[bool, dict[str, Any] | None]:
        """Map legend.policy onto Plotly's showlegend/legend layout.

        "legacy" preserves the pre-policy Plotly behavior (legend shown at
        Plotly's default position, suppressed once max_items is exceeded).
        Other policies mirror the Matplotlib renderer: "hide" and any
        placement whose item count exceeds max_items suppress the legend,
        while the concrete placements map to the corresponding Plotly
        legend positions.
        """
        max_items = legend.max_items
        over_limit = max_items is not None and legend_item_count > max_items

        policy = legend.policy
        if policy == "legacy":
            return not over_limit, None

        resolved = resolve_legend_policy(
            policy,
            legend_item_count,
            legend.outside_threshold,
            max_items,
            bottom_threshold=legend.bottom_threshold,
        )
        if resolved == "hide" or over_limit:
            return False, None

        if resolved == "inside":
            return True, {"x": 0.98, "xanchor": "right", "y": 0.98, "yanchor": "top"}
        if resolved == "outside_bottom":
            return True, {
                "orientation": "h",
                "x": 0.5,
                "xanchor": "center",
                "y": -0.2,
                "yanchor": "top",
            }
        # resolved == "outside_right"
        return True, {"x": 1.02, "xanchor": "left", "y": 1.0, "yanchor": "top"}

    def _build_axis_layout(self, axis: AxisSpec, label: str) -> dict[str, Any]:
        axis_layout: dict[str, Any] = {
            "title": label,
            "type": axis.scale,
        }
        if axis.scale == "log":
            axis_layout.update({
                "dtick": 1,
                "exponentformat": "power",
                "showexponent": "all",
            })
        return axis_layout

    def _build_update_menus(self, plan: PlotPlan) -> list[dict[str, Any]]:
        return [
            self._scale_toggle_menu(
                axis="xaxis",
                label_prefix="X",
                current_scale=plan.x_axis.scale,
                position=(1.15, 1.08),
            ),
            self._scale_toggle_menu(
                axis="yaxis",
                label_prefix="Y",
                current_scale=plan.y_axis.scale,
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


def _explicit_size(plan: PlotPlan) -> dict[str, int]:
    """Layout width/height in pixels (inches x 100), only for an explicitly requested size.

    The Matplotlib default size is no HTML default, so an implicit size leaves the
    Plotly layout responsive (and its keyword set unchanged, ruling C-13).
    rcParams are Matplotlib-only and do not affect HTML.
    """
    if plan.origins.get("style.figure_size") != "explicit" or plan.style.figure_size is None:
        return {}
    width, height = plan.style.figure_size
    return {"width": round(width * _PIXELS_PER_INCH), "height": round(height * _PIXELS_PER_INCH)}
