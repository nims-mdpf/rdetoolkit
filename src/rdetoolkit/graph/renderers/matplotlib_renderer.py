"""Matplotlib renderer: draws a ``PlotPlan`` with the csv2graph house style.

``render(plan, figure, data)`` is the plan-consuming entry point. The legacy methods
``render_overlay(df, config)`` and ``render_individual(df, config, ...)`` are adapters:
they build the plan with ``compat.plan_from_config`` (Matplotlib legacy labels, C-12)
and draw it, so no column, label or direction spec is interpreted here (GE-06).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Final, Literal, Protocol

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.category import StrCategoryConverter
from matplotlib.figure import Figure
from matplotlib.ticker import (
    EngFormatter,
    LogFormatterMathtext,
    LogLocator,
    MaxNLocator,
    NullFormatter,
    NullLocator,
    ScalarFormatter,
)

from rdetoolkit.graph import compat
from rdetoolkit.graph.config import DEFAULT_FIG_SIZE, apply_matplotlib_config
from rdetoolkit.graph.legend_policy import (
    resolve_legend_policy as _resolve_legend_policy,
)
from rdetoolkit.graph.models import AxisConfig, LegendConfig, PlotConfig
from rdetoolkit.graph.plan import FigurePlan, PlotData, PlotPlan, SeriesPlan
from rdetoolkit.graph.renderers.mpl_runtime import draw_series, new_figure
from rdetoolkit.graph.spec import AxisSpec, LegendSpec

CENTER_POSITION = 0.5
LEGEND_RIGHT_THRESHOLD = 0.7
TEXT_Y_THRESHOLD = 0.9
DEFAULT_OUTSIDE_LEGEND_NCOL = 3
OUTSIDE_LEGEND_MARGIN_INCHES = 0.2
_LINE_WIDTH: Final = 1.5
_NO_LEGEND: Final = "_nolegend_"


class _LegendSource(Protocol):
    """Anything carrying legend settings: a legacy ``PlotConfig`` or a ``PlotPlan``."""

    @property
    def legend(self) -> LegendConfig | LegendSpec: ...


@dataclass(frozen=True)
class _PlanMemo:
    """The last legacy plan, valid while the same frame and an unchanged config are passed."""

    df: pd.DataFrame
    config: PlotConfig
    fingerprint: str
    plan: PlotPlan


class MatplotlibRenderer:
    """Matplotlib-based renderer for static plots."""

    def __init__(self) -> None:
        """Create a renderer; it remembers the last legacy plan it built."""
        self._memo: _PlanMemo | None = None

    def render(self, plan: PlotPlan, figure: FigurePlan, data: PlotData) -> Figure:
        """Draw one planned figure on a pyplot-free figure.

        The house style is applied to the ambient rcParams (callers scope it, as the
        engine does with ``mpl_runtime.style_scope``).

        Args:
            plan: The plan.
            figure: One of ``plan.figures``.
            data: The frames the plan was built from.

        Returns:
            The drawn figure (``Figure`` + Agg canvas, not registered with pyplot).
        """
        apply_matplotlib_config()
        fig, ax = new_figure(DEFAULT_FIG_SIZE)
        axes = (_axis_config(plan.x_axis, figure.x_label), _axis_config(plan.y_axis, figure.y_label))
        # The spec API grids each axis on its own; the legacy renderer grids both when either asks.
        self._draw_figure(ax, plan, figure, data, axes, per_axis_grid=True)
        return fig

    def render_overlay(self, df: pd.DataFrame, config: PlotConfig) -> Figure:
        """Render all data series on a single graph (legacy adapter).

        Args:
            df: DataFrame containing plot data
            config: Plot configuration

        Returns:
            A pyplot figure owned by the caller.

        Raises:
            ValueError: For column specs that cannot be planned (raised before a
                figure exists).
        """
        plan = self._plan_for(df, config)
        return self._render_legacy(plan, plan.figures[0], df, config)

    def render_individual(
        self,
        df: pd.DataFrame,
        config: PlotConfig,
        y_col_index: int,
        series_position: int | None = None,
    ) -> Figure:
        """Render the individual graph of one series (legacy adapter).

        Args:
            df: DataFrame containing plot data
            config: Plot configuration
            y_col_index: Column position of the series' y values.
            series_position: Position of the series within ``config.y_cols``;
                ``None`` selects the first series plotting ``y_col_index``.

        Returns:
            A pyplot figure owned by the caller.

        Raises:
            ValueError: For column specs that cannot be planned, or a position /
                column pair that names no planned series (before a figure exists).
        """
        plan = self._plan_for(df, config)
        return self._render_legacy(plan, _individual_figure(plan, y_col_index, series_position), df, config)

    def _plan_for(self, df: pd.DataFrame, config: PlotConfig) -> PlotPlan:
        """Plan a legacy pair once per renderer, so N individual figures share one plan."""
        fingerprint = repr(config)
        memo = self._memo
        if memo is not None and memo.df is df and memo.config is config and memo.fingerprint == fingerprint:
            return memo.plan
        plan = compat.plan_from_config(df, config, label_of=compat.legacy_mpl_label)
        self._memo = _PlanMemo(df=df, config=config, fingerprint=fingerprint, plan=plan)
        return plan

    def _render_legacy(self, plan: PlotPlan, figure: FigurePlan, df: pd.DataFrame, config: PlotConfig) -> Figure:
        apply_matplotlib_config()
        fig, ax = self._new_figure()
        try:
            # Tick formatting keeps the legacy axis settings (scilimits, unit); labels come from the plan.
            axes = (
                dataclasses.replace(config.x_axis, label=figure.x_label),
                dataclasses.replace(config.y_axis, label=figure.y_label),
            )
            self._draw_figure(ax, plan, figure, PlotData(frames=(df,)), axes, per_axis_grid=False)
        except BaseException:
            # The caller never receives this handle, so it must not stay open.
            plt.close(fig)
            raise
        return fig

    def _new_figure(self) -> tuple[Figure, Any]:
        """Create the figure of one legacy ``render_*`` call (a pyplot figure)."""
        return plt.subplots(figsize=DEFAULT_FIG_SIZE, tight_layout=True)

    def _draw_figure(
        self,
        ax: Any,
        plan: PlotPlan,
        figure: FigurePlan,
        data: PlotData,
        axes: tuple[AxisConfig, AxisConfig],
        *,
        per_axis_grid: bool,
    ) -> None:
        """Draw the series of one planned figure, then axes and legend."""
        by_id = {entry.series_id: entry for entry in plan.series}
        series = [by_id[series_id] for series_id in figure.series_ids]
        if figure.kind == "overlay":
            handles, labels = self._draw_overlay(ax, plan, series, data)
            show_legend = True
        else:
            handles, labels = self._draw_individual(ax, plan, series[0], data)
            # v1 draws an individual legend only when a series splits into several directions.
            show_legend = len(handles) > 1
        self._configure_axes(ax, axes[0], axes[1], figure.title, per_axis_grid=per_axis_grid)
        if show_legend:
            self._apply_legend(ax, handles, labels, plan)

    def _draw_overlay(
        self,
        ax: Any,
        plan: PlotPlan,
        series: list[SeriesPlan],
        data: PlotData,
    ) -> tuple[list[Any], list[str]]:
        """Overlay colours follow the series position; only a series' first segment is labelled."""
        palette = plt.cm.tab10.colors  # type: ignore[attr-defined]
        handles: list[Any] = []
        labels: list[str] = []
        for entry in series:
            color = palette[entry.color_index % len(palette)]
            artists = draw_series(ax, plan, entry, data, color=color, **_mark_kwargs(plan))
            for position, artist in enumerate(artists):
                artist.set_label(entry.label if position == 0 else _NO_LEGEND)
            if artists and entry.show_in_legend:
                handles.append(artists[0])
                labels.append(entry.label)
        return handles, labels

    def _draw_individual(
        self,
        ax: Any,
        plan: PlotPlan,
        entry: SeriesPlan,
        data: PlotData,
    ) -> tuple[list[Any], list[str]]:
        """The v1 individual look: default colours, one legend entry per direction."""
        artists = draw_series(ax, plan, entry, data, **_mark_kwargs(plan))
        if entry.direction_index is None:
            return [], []
        for artist, direction in zip(artists, entry.directions, strict=True):
            artist.set_label(direction)
        return artists, list(entry.directions)

    def _configure_axes(
        self,
        ax: Any,
        x_axis: AxisConfig,
        y_axis: AxisConfig,
        title: str | None,
        *,
        per_axis_grid: bool = False,
    ) -> None:
        ax.set_xlabel(self._compose_axis_label(x_axis, "X"))
        ax.set_ylabel(self._compose_axis_label(y_axis, "Y"))

        if x_axis.scale == "log":
            ax.set_xscale("log")
            self._apply_log_axis_formatting(ax.xaxis)
        else:
            self._apply_tick_formatting(ax.xaxis, x_axis)
        if y_axis.scale == "log":
            ax.set_yscale("log")
            self._apply_log_axis_formatting(ax.yaxis)
        else:
            self._apply_tick_formatting(ax.yaxis, y_axis)

        # A None side keeps Matplotlib's automatic limit, so (0, None) fixes the
        # lower bound only. Limits follow the scale so a scale change cannot re-derive them.
        if x_axis.lim is not None:
            ax.set_xlim(*x_axis.lim)
        if y_axis.lim is not None:
            ax.set_ylim(*y_axis.lim)

        self._apply_grid(ax, x_axis.grid, y_axis.grid, per_axis=per_axis_grid)

        if x_axis.invert:
            ax.invert_xaxis()
        if y_axis.invert:
            ax.invert_yaxis()

        if title:
            title_artist = ax.set_title(title, pad=20, loc="center")
            title_pos = title_artist.get_position()
            if title_pos[0] != CENTER_POSITION:
                title_artist.set_position((CENTER_POSITION, title_pos[1]))
            title_artist.set_horizontalalignment("center")

    @staticmethod
    def _apply_grid(ax: Any, x_grid: bool, y_grid: bool, *, per_axis: bool) -> None:
        if not (x_grid or y_grid):
            return
        ax.grid(True, alpha=0.3)
        if per_axis and x_grid != y_grid:
            (ax.yaxis if x_grid else ax.xaxis).grid(False)

    def _apply_legend(
        self,
        ax: Any,
        handles: list[Any],
        labels: list[str],
        config: _LegendSource,
    ) -> None:
        filtered_handles, filtered_labels = self._filter_legend_entries(handles, labels)

        legend_obj = self._render_legend(ax, filtered_handles, filtered_labels, config)

        if config.legend.info:
            self._add_legend_info(ax, legend_obj, config.legend.info)

    def _filter_legend_entries(
        self,
        handles: list[Any],
        labels: list[str],
    ) -> tuple[list[Any], list[str]]:
        """Drop empty and hidden labels.

        Duplicate labels never reach this point: the plan gives each label a single
        legend owner (``SeriesPlan.show_in_legend``), the same rule Plotly follows.
        """
        filtered_handles: list[Any] = []
        filtered_labels: list[str] = []

        for handle, label in zip(handles, labels, strict=True):
            if not label or label == _NO_LEGEND:
                continue
            filtered_handles.append(handle)
            filtered_labels.append(label)

        return filtered_handles, filtered_labels

    def _render_legend(
        self,
        ax: Any,
        filtered_handles: list[Any],
        filtered_labels: list[str],
        config: _LegendSource,
    ) -> Any:
        """Render the legend according to config.legend.policy and return the Legend object."""
        if config.legend.policy == "legacy":
            return self._render_legend_legacy(ax, filtered_handles, filtered_labels, config)

        resolved_policy = _resolve_legend_policy(
            config.legend.policy,
            len(filtered_labels),
            config.legend.outside_threshold,
            config.legend.max_items,
            bottom_threshold=config.legend.bottom_threshold,
        )

        if resolved_policy == "hide" or not filtered_labels:
            return None

        max_items = config.legend.max_items
        if max_items is not None and len(filtered_labels) > max_items:
            return None

        if resolved_policy == "inside":
            legend_kwargs: dict[str, Any] = {}
            if config.legend.loc is not None:
                legend_kwargs["loc"] = config.legend.loc
            return ax.legend(filtered_handles, filtered_labels, **legend_kwargs)

        if resolved_policy == "outside_right":
            self._freeze_axes_layout(ax)
            anchor_x = self._outside_anchor_beyond_decorations(ax, side="right")
            legend_obj = ax.legend(
                filtered_handles,
                filtered_labels,
                loc="center left",
                bbox_to_anchor=(anchor_x, 0.5),
                borderaxespad=0.0,
            )
            self._expand_figure_for_outside_legend(ax, legend_obj)
            return legend_obj

        # resolved_policy == "outside_bottom"
        self._freeze_axes_layout(ax)
        anchor_y = self._outside_anchor_beyond_decorations(ax, side="bottom")
        legend_obj = ax.legend(
            filtered_handles,
            filtered_labels,
            loc="upper center",
            bbox_to_anchor=(0.5, anchor_y),
            ncol=config.legend.ncol or DEFAULT_OUTSIDE_LEGEND_NCOL,
        )
        self._expand_figure_for_outside_legend(ax, legend_obj)
        return legend_obj

    def _outside_anchor_beyond_decorations(
        self,
        ax: Any,
        side: Literal["right", "bottom"],
    ) -> float:
        """Compute an axes-fraction anchor just outside the axes decorations.

        Tick labels and axis labels spill past the axes edge, so a fixed
        anchor offset (e.g. 1.02) can overlap them. Measure the actual
        decoration extent and place the legend beyond it, never closer to
        the axes than the fixed default offset.
        """
        default = 1.02 if side == "right" else -0.12
        fig = ax.figure
        canvas = getattr(fig, "canvas", None)
        if canvas is None:
            return default
        try:
            renderer = canvas.get_renderer()
        except AttributeError:
            return default

        axes_bbox = ax.get_window_extent(renderer=renderer)
        tight_bbox = ax.get_tightbbox(renderer)
        if tight_bbox is None or axes_bbox.width <= 0 or axes_bbox.height <= 0:
            return default

        if side == "right":
            spill = max(tight_bbox.x1 - axes_bbox.x1, 0.0)
            return max(1.0 + spill / axes_bbox.width + 0.02, default)

        spill = max(axes_bbox.y0 - tight_bbox.y0, 0.0)
        return min(-(spill / axes_bbox.height) - 0.02, default)

    def _freeze_axes_layout(self, ax: Any) -> None:
        """Finalize the axes geometry before an outside legend is added.

        tight_layout re-runs on every draw and includes the legend in the
        axes decorations it tries to fit into the fixed figure size, which
        crushes the plot area when a large legend sits outside the axes.
        Drawing once while no legend exists locks in the geometry derived
        from labels/titles only; disabling the layout engine afterwards
        keeps the plot area at that size.
        """
        fig = ax.figure
        canvas = getattr(fig, "canvas", None)
        if canvas is not None:
            canvas.draw()
        fig.set_layout_engine("none")

    def _expand_figure_for_outside_legend(self, ax: Any, legend_obj: Any) -> None:
        """Grow the figure by the legend overflow instead of shrinking the axes.

        The legend is anchored to the axes, so enlarging the canvas and
        shifting the subplot fractions by the same physical amount keeps
        both the plot area size and the legend-to-axes attachment intact.
        """
        fig = ax.figure
        renderer = self._prepare_renderer(ax, legend_obj)
        if renderer is None:
            return

        bbox = legend_obj.get_window_extent(renderer=renderer)
        dpi = fig.dpi
        fig_w, fig_h = fig.get_size_inches()
        overflows = (
            max(-bbox.x0 / dpi, 0.0),           # left
            max(bbox.x1 / dpi - fig_w, 0.0),    # right
            max(-bbox.y0 / dpi, 0.0),           # bottom
            max(bbox.y1 / dpi - fig_h, 0.0),    # top
        )
        if not any(overflows):
            return

        extra_left, extra_right, extra_bottom, extra_top = (
            overflow + OUTSIDE_LEGEND_MARGIN_INCHES if overflow else 0.0
            for overflow in overflows
        )
        new_w = fig_w + extra_left + extra_right
        new_h = fig_h + extra_bottom + extra_top
        subplot_pars = fig.subplotpars
        fig.set_size_inches(new_w, new_h)
        fig.subplots_adjust(
            left=(subplot_pars.left * fig_w + extra_left) / new_w,
            right=(subplot_pars.right * fig_w + extra_left) / new_w,
            bottom=(subplot_pars.bottom * fig_h + extra_bottom) / new_h,
            top=(subplot_pars.top * fig_h + extra_bottom) / new_h,
        )

    def _render_legend_legacy(
        self,
        ax: Any,
        filtered_handles: list[Any],
        filtered_labels: list[str],
        config: _LegendSource,
    ) -> Any:
        """Preserve the pre-#497 legend behavior driven by loc/max_items only."""
        if not filtered_labels:
            return None

        show_threshold = len(filtered_labels) > 1
        if config.legend.loc is not None:
            show_threshold = True

        max_items = config.legend.max_items
        within_limit = max_items is None or len(filtered_labels) <= max_items

        if not (show_threshold and within_limit):
            return None

        legend_kwargs: dict[str, Any] = {}
        if config.legend.loc is not None:
            legend_kwargs["loc"] = config.legend.loc
        return ax.legend(filtered_handles, filtered_labels, **legend_kwargs)

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

    @staticmethod
    def _apply_log_axis_formatting(axis: Any) -> None:
        """Use decade-only major ticks with mathtext formatting for log axes."""
        axis.set_major_locator(LogLocator(base=10, subs=(1.0,)))
        axis.set_minor_locator(NullLocator())
        axis.set_major_formatter(LogFormatterMathtext(base=10, labelOnlyBase=True))
        axis.set_minor_formatter(NullFormatter())

    @staticmethod
    def _apply_linear_axis_formatting(
        axis: Any,
        scilimits: tuple[int, int] = (-3, 4),
    ) -> None:
        """Readable tick labels regardless of data magnitude."""
        formatter = ScalarFormatter(useMathText=True)
        formatter.set_powerlimits(scilimits)   # out-of-range magnitudes use ×10^n notation
        axis.set_major_formatter(formatter)
        axis.set_major_locator(MaxNLocator(nbins=6))
        offset = axis.get_offset_text()
        offset.set_fontsize(plt.rcParams.get("xtick.labelsize", 20))

    @staticmethod
    def _uses_non_numeric_units(axis: Any) -> bool:
        """Return True when the axis carries categorical or date units.

        Matplotlib installs a unit converter (and its own formatter/locator)
        when string or datetime data is plotted, so this must be called after
        the data is on the axis. Numeric converters (e.g. Decimal) are not
        exempted because ScalarFormatter is still the right formatter there.

        Args:
            axis: A Matplotlib ``Axis`` (``ax.xaxis`` / ``ax.yaxis``).

        Returns:
            True if the axis converter is categorical or date based.
        """
        get_converter = getattr(axis, "get_converter", None)
        # Matplotlib < 3.10 exposes the converter only as an attribute.
        converter = get_converter() if callable(get_converter) else getattr(axis, "converter", None)
        if converter is None:
            return False
        if isinstance(converter, (StrCategoryConverter, mdates.DateConverter)):
            return True
        # Date converters such as _SwitchableDateConverter do not subclass
        # DateConverter, so fall back to the defining module.
        return type(converter).__module__ == mdates.__name__

    @staticmethod
    def _apply_tick_formatting(axis: Any, axis_config: AxisConfig) -> None:
        """Apply tick formatter based on AxisConfig.tick_format.

        ``"auto"`` (the default) formats numeric axes only: when Matplotlib has
        attached categorical (string) or date units to the axis, its own
        formatter and locator are kept so sample names and timestamps stay
        readable. The explicit formats ``"plain"``, ``"sci"`` and ``"eng"``
        express user intent and are applied to every non-log axis, including
        categorical and date axes.

        Args:
            axis: A Matplotlib ``Axis`` that already holds the plotted data.
            axis_config: Axis configuration carrying ``tick_format`` and
                ``scilimits``.
        """
        tick_format = axis_config.tick_format
        if tick_format == "plain":
            formatter = ScalarFormatter(useMathText=True)
            formatter.set_scientific(False)
            formatter.set_useOffset(False)
            axis.set_major_formatter(formatter)
            axis.set_major_locator(MaxNLocator(nbins=6))
        elif tick_format == "sci":
            formatter = ScalarFormatter(useMathText=True)
            formatter.set_powerlimits((0, 0))
            axis.set_major_formatter(formatter)
            axis.set_major_locator(MaxNLocator(nbins=6))
            offset = axis.get_offset_text()
            offset.set_fontsize(plt.rcParams.get("xtick.labelsize", 20))
        elif tick_format == "eng":
            axis.set_major_formatter(EngFormatter(unit=axis_config.unit or ""))
            axis.set_major_locator(MaxNLocator(nbins=6))
        elif not MatplotlibRenderer._uses_non_numeric_units(axis):  # "auto"
            MatplotlibRenderer._apply_linear_axis_formatting(axis, axis_config.scilimits)

    @staticmethod
    def _compose_axis_label(axis_config: AxisConfig, default_label: str) -> str:
        """Compose axis label with unit suffix, avoiding double-composition."""
        label = axis_config.label or default_label
        unit = axis_config.unit
        if not unit:
            return label
        # Already contains the unit (e.g. derived label already has "(V)") -> no-op
        if f"({unit})" in label:
            return label
        return f"{label} ({unit})"


def _mark_kwargs(plan: PlotPlan) -> dict[str, Any]:
    """Line width applies to lines only; on a scatter it would change the marker edges."""
    return {"linewidth": _LINE_WIDTH} if plan.mark == "line" else {}


def _axis_config(axis: AxisSpec, label: str) -> AxisConfig:
    """The axis settings of a spec-API figure in the shape the tick helpers read."""
    return AxisConfig(
        label=label,
        scale=axis.scale,
        grid=axis.grid,
        invert=axis.invert,
        lim=axis.limits,
        tick_format=axis.tick_format,
    )


def _individual_figure(plan: PlotPlan, y_col_index: int, series_position: int | None) -> FigurePlan:
    """The planned individual figure of a legacy ``render_individual`` call."""
    if series_position is None:
        position = next((entry_position for entry_position, entry in enumerate(plan.series) if entry.y_index == y_col_index), None)
        if position is None:
            msg = f"y column {y_col_index} is not a planned series"
            raise ValueError(msg)
    else:
        position = series_position
    if not 0 <= position < len(plan.series):
        msg = f"series position {position} is out of range for {len(plan.series)} planned series"
        raise ValueError(msg)
    entry = plan.series[position]
    if entry.y_index != y_col_index:
        msg = f"y column {y_col_index} does not match planned series {position} (column {entry.y_index})"
        raise ValueError(msg)
    return next(figure for figure in plan.figures if figure.kind == "individual" and figure.figure_id == entry.series_id)
