"""Tests for MatplotlibRenderer and related plotting strategies."""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # pragma: no cover

import matplotlib.pyplot as plt
import pandas as pd
import pytest

from rdetoolkit.graph.config import PlotConfigBuilder
from rdetoolkit.graph.models import (
    AxisConfig,
    DirectionConfig,
    LegendConfig,
    OutputConfig,
    PlotConfig,
    PlotMode,
)
from rdetoolkit.graph.renderers.matplotlib_renderer import (
    MatplotlibRenderer,
    _resolve_legend_policy,
)
from rdetoolkit.graph.strategies.all_graphs import OverlayStrategy
from rdetoolkit.graph.strategies.individual import IndividualStrategy


@pytest.fixture
def direction_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": [1, 2, 3, 4],
            "value": [1.0, 1.5, 2.0, 2.5],
            "direction": ["A", "B", "A", "B"],
        }
    )


def build_overlay_config(**overrides):
    builder = PlotConfigBuilder()
    builder.set_mode(PlotMode.OVERLAY)
    builder.set_columns(x_col=0, y_cols=[1], direction_cols=[2])
    builder.set_x_axis(AxisConfig(label="time"))
    builder.set_y_axis(AxisConfig(label="value"))
    builder.set_legend(LegendConfig(loc="upper right"))
    direction_cfg = DirectionConfig(use_custom_colors=True)
    direction_cfg.colors.update({"A": "#ff0000", "B": "#00ff00"})
    builder.set_direction(direction_cfg)
    builder.set_output(OutputConfig(base_name="case", return_fig=True))
    config = builder.build()
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def close_fig(fig):
    if fig is not None:
        plt.close(fig)


def test_matplotlib_renderer_direction_custom_colors(direction_df: pd.DataFrame) -> None:
    config = build_overlay_config()

    renderer = MatplotlibRenderer()
    fig = renderer.render_overlay(direction_df, config)
    try:
        ax = fig.axes[0]
        line_colors = [line.get_color() for line in ax.lines]
        assert line_colors == ["#ff0000", "#00ff00"]
        legend = ax.get_legend()
        assert legend is not None
        legend_labels = [text.get_text() for text in legend.get_texts()]
        assert legend_labels == ["Value"]
    finally:
        close_fig(fig)


def test_matplotlib_renderer_individual_direction_filter(direction_df: pd.DataFrame) -> None:
    direction_cfg = DirectionConfig(filters=["A"], use_custom_colors=False)
    builder = PlotConfigBuilder()
    builder.set_mode(PlotMode.INDIVIDUAL)
    builder.set_columns(x_col=0, y_cols=[1], direction_cols=[2])
    builder.set_direction(direction_cfg)
    builder.set_output(OutputConfig(base_name="case", return_fig=True))
    config = builder.build()

    renderer = MatplotlibRenderer()
    results = IndividualStrategy(renderer).render(direction_df, config)
    assert results is not None
    fig = results[0].figure
    try:
        ax = fig.axes[0]
        assert len(ax.lines) == 1
        line = ax.lines[0]
        assert list(line.get_xdata()) == [1, 3]
        assert list(line.get_ydata()) == [1.0, 2.0]
    finally:
        close_fig(fig)


def test_matplotlib_renderer_axis_options(direction_df: pd.DataFrame) -> None:
    builder = PlotConfigBuilder()
    builder.set_mode(PlotMode.OVERLAY)
    builder.set_columns(x_col=0, y_cols=[1])
    builder.set_x_axis(AxisConfig(label="time", scale="log", grid=True, invert=False))
    builder.set_y_axis(AxisConfig(label="value", scale="log", invert=False))
    builder.set_output(OutputConfig(base_name="case", return_fig=True))
    config = builder.build()

    fig = MatplotlibRenderer().render_overlay(direction_df, config)
    try:
        ax = fig.axes[0]
        assert ax.get_xscale() == "log"
        assert ax.get_yscale() == "log"
        assert ax.xaxis.get_label_text() == "time"
        assert ax.yaxis.get_label_text() == "value"
    finally:
        close_fig(fig)


def test_matplotlib_renderer_no_direction_legend_suppressed():
    df = pd.DataFrame({'time': [0, 1], 'value': [1, 2]})
    builder = PlotConfigBuilder()
    builder.set_mode(PlotMode.OVERLAY)
    builder.set_columns(x_col=0, y_cols=[1])
    builder.set_legend(LegendConfig(max_items=0))
    builder.set_output(OutputConfig(base_name='case', return_fig=True))
    config = builder.build()
    fig = MatplotlibRenderer().render_overlay(df, config)
    try:
        ax = fig.axes[0]
        assert ax.get_legend() is None
    finally:
        plt.close(fig)


class TestResolveLegendPolicy:
    """EP/BV tests for _resolve_legend_policy()."""

    def test_non_auto_policies_pass_through(self):
        """Non-auto policies resolve to themselves unchanged."""
        for policy in ("legacy", "inside", "outside_right", "outside_bottom", "hide"):
            assert _resolve_legend_policy(policy, 5, outside_threshold=8, max_items=20) == policy

    def test_auto_zero_items_hides(self):
        """Auto policy with zero legend items resolves to hide."""
        assert _resolve_legend_policy("auto", 0, outside_threshold=8, max_items=20) == "hide"

    def test_auto_below_threshold_is_inside(self):
        """Auto policy at or below the outside threshold resolves to inside."""
        assert _resolve_legend_policy("auto", 8, outside_threshold=8, max_items=20) == "inside"

    def test_auto_above_threshold_is_outside_right(self):
        """Auto policy above the outside threshold resolves to outside_right."""
        assert _resolve_legend_policy("auto", 9, outside_threshold=8, max_items=20) == "outside_right"

    def test_auto_exceeding_max_items_hides(self):
        """Auto policy exceeding max_items resolves to hide."""
        assert _resolve_legend_policy("auto", 21, outside_threshold=8, max_items=20) == "hide"

    def test_auto_max_items_none_never_hides_for_count(self):
        """Auto policy with max_items=None never hides based on item count alone."""
        assert _resolve_legend_policy("auto", 1000, outside_threshold=8, max_items=None) == "outside_right"

    def test_auto_max_items_precedence_over_threshold(self):
        """max_items cap takes precedence over outside_threshold when both would apply."""
        # max_items smaller than outside_threshold: cap still wins.
        assert _resolve_legend_policy("auto", 6, outside_threshold=8, max_items=5) == "hide"

    def test_auto_boundary_matrix_with_bottom_threshold(self):
        """BV: defaults (outside=8, bottom=21) split counts into inside/right/bottom."""
        expectations = {
            8: "inside",
            9: "outside_right",
            20: "outside_right",
            21: "outside_bottom",
            30: "outside_bottom",
        }
        for count, expected in expectations.items():
            result = _resolve_legend_policy(
                "auto", count, outside_threshold=8, max_items=None, bottom_threshold=21,
            )
            assert result == expected, f"count={count}"

    def test_auto_bottom_threshold_none_disables_bottom_switch(self):
        """bottom_threshold=None keeps the pre-existing auto behavior (never bottom)."""
        result = _resolve_legend_policy(
            "auto", 30, outside_threshold=8, max_items=None, bottom_threshold=None,
        )
        assert result == "outside_right"

    def test_auto_max_items_precedence_over_bottom_threshold(self):
        """Exceeding max_items hides the legend even past the bottom threshold."""
        result = _resolve_legend_policy(
            "auto", 25, outside_threshold=8, max_items=20, bottom_threshold=21,
        )
        assert result == "hide"


class TestApplyLegendPolicies:
    """Behavioral tests for MatplotlibRenderer._apply_legend() policy branches."""

    def _build_config(self, legend: LegendConfig, y_cols: list[int]) -> PlotConfig:
        builder = PlotConfigBuilder()
        builder.set_columns(x_col=0, y_cols=y_cols)
        builder.set_legend(legend)
        return builder.build()

    def _multi_series_df(self, n_series: int) -> pd.DataFrame:
        data = {"x": [0, 1, 2]}
        for i in range(n_series):
            data[f"series_{i}"] = [i, i + 1, i + 2]
        return pd.DataFrame(data)

    def _axes_size_inches(self, fig) -> tuple[float, float]:
        """Return the physical (width, height) of the plot area in inches."""
        fig.canvas.draw()
        position = fig.axes[0].get_position()
        fig_w, fig_h = fig.get_size_inches()
        return position.width * fig_w, position.height * fig_h

    def test_legacy_policy_matches_pre_497_behavior(self):
        """policy="legacy" (default) preserves existing single-legend rendering."""
        df = self._multi_series_df(3)
        config = self._build_config(LegendConfig(), y_cols=[1, 2, 3])
        renderer = MatplotlibRenderer()
        fig = renderer.render_overlay(df, config)
        try:
            ax = fig.axes[0]
            legend = ax.get_legend()
            assert legend is not None
            assert [t.get_text() for t in legend.get_texts()] == ["Series 0", "Series 1", "Series 2"]
        finally:
            close_fig(fig)

    def test_hide_policy_suppresses_legend(self):
        """policy="hide" always suppresses the legend."""
        df = self._multi_series_df(3)
        config = self._build_config(
            LegendConfig(policy="hide"), y_cols=[1, 2, 3],
        )
        renderer = MatplotlibRenderer()
        fig = renderer.render_overlay(df, config)
        try:
            assert fig.axes[0].get_legend() is None
        finally:
            close_fig(fig)

    def test_inside_policy_uses_legend_loc(self):
        """policy="inside" renders the legend using the configured loc."""
        df = self._multi_series_df(2)
        config = self._build_config(
            LegendConfig(policy="inside", loc="upper left"), y_cols=[1, 2],
        )
        renderer = MatplotlibRenderer()
        fig = renderer.render_overlay(df, config)
        try:
            legend = fig.axes[0].get_legend()
            assert legend is not None
        finally:
            close_fig(fig)

    def test_inside_policy_shows_single_series_legend(self):
        """Unlike "legacy", explicit "inside" shows the legend even for 1 series."""
        df = self._multi_series_df(1)
        config = self._build_config(LegendConfig(policy="inside"), y_cols=[1])
        renderer = MatplotlibRenderer()
        fig = renderer.render_overlay(df, config)
        try:
            assert fig.axes[0].get_legend() is not None
        finally:
            close_fig(fig)

    def test_outside_right_policy_places_legend_outside_axes(self):
        """policy="outside_right" grows the figure and puts the legend right of the axes."""
        df = self._multi_series_df(10)
        config = self._build_config(
            LegendConfig(policy="outside_right"), y_cols=list(range(1, 11)),
        )
        renderer = MatplotlibRenderer()
        fig = renderer.render_overlay(df, config)
        try:
            ax = fig.axes[0]
            legend = ax.get_legend()
            assert legend is not None
            # figure expands beyond the default 8.85in width instead of shrinking axes
            assert fig.get_size_inches()[0] > 8.85
            fig.canvas.draw()
            legend_bbox = legend.get_window_extent(fig.canvas.get_renderer())
            axes_bbox = ax.get_window_extent(fig.canvas.get_renderer())
            assert legend_bbox.x0 >= axes_bbox.x1
            # legend fully inside the enlarged canvas
            assert legend_bbox.x1 <= fig.get_size_inches()[0] * fig.dpi + 1
        finally:
            close_fig(fig)

    def test_outside_bottom_policy_uses_ncol(self):
        """policy="outside_bottom" places the legend below the axes with the configured ncol."""
        df = self._multi_series_df(6)
        config = self._build_config(
            LegendConfig(policy="outside_bottom", ncol=3), y_cols=list(range(1, 7)),
        )
        renderer = MatplotlibRenderer()
        fig = renderer.render_overlay(df, config)
        try:
            ax = fig.axes[0]
            legend = ax.get_legend()
            assert legend is not None
            assert legend._ncols == 3  # noqa: SLF001 - matplotlib exposes ncol via private attr
            # figure expands beyond the default 8in height instead of shrinking axes
            assert fig.get_size_inches()[1] > 8.0
            fig.canvas.draw()
            legend_bbox = legend.get_window_extent(fig.canvas.get_renderer())
            axes_bbox = ax.get_window_extent(fig.canvas.get_renderer())
            assert legend_bbox.y1 <= axes_bbox.y0
            assert legend_bbox.y0 >= -1
        finally:
            close_fig(fig)

    def test_outside_policies_preserve_plot_area_size(self):
        """Acceptance: outside legends must not crush the plot area (issue #497 follow-up).

        The plot area of a 30-series graph with an outside legend must keep
        (approximately) the same physical size as the same graph without a
        legend; the extra legend space is added to the figure instead.
        """
        n_series = 30
        df = self._multi_series_df(n_series)
        y_cols = list(range(1, n_series + 1))
        renderer = MatplotlibRenderer()

        baseline_fig = renderer.render_overlay(
            df, self._build_config(LegendConfig(policy="hide"), y_cols=y_cols),
        )
        try:
            baseline_w, baseline_h = self._axes_size_inches(baseline_fig)
        finally:
            close_fig(baseline_fig)

        for policy in ("outside_right", "outside_bottom"):
            fig = renderer.render_overlay(
                df,
                self._build_config(
                    LegendConfig(policy=policy, max_items=None), y_cols=y_cols,
                ),
            )
            try:
                axes_w, axes_h = self._axes_size_inches(fig)
                assert axes_w == pytest.approx(baseline_w, abs=0.05), policy
                assert axes_h == pytest.approx(baseline_h, abs=0.05), policy
            finally:
                close_fig(fig)

    def test_auto_policy_resolves_to_outside_right_when_many_items(self):
        """policy="auto" resolves to outside_right once item count exceeds the threshold."""
        df = self._multi_series_df(12)
        config = self._build_config(
            LegendConfig(policy="auto", outside_threshold=8),
            y_cols=list(range(1, 13)),
        )
        renderer = MatplotlibRenderer()
        fig = renderer.render_overlay(df, config)
        try:
            ax = fig.axes[0]
            legend = ax.get_legend()
            assert legend is not None
            fig.canvas.draw()
            legend_bbox = legend.get_window_extent(fig.canvas.get_renderer())
            axes_bbox = ax.get_window_extent(fig.canvas.get_renderer())
            assert legend_bbox.x0 >= axes_bbox.x1
        finally:
            close_fig(fig)

    def test_auto_policy_resolves_to_outside_bottom_at_bottom_threshold(self):
        """policy="auto" switches to outside_bottom once the bottom threshold is reached."""
        n_series = 21
        df = self._multi_series_df(n_series)
        config = self._build_config(
            LegendConfig(
                policy="auto",
                outside_threshold=8,
                bottom_threshold=21,
                max_items=None,
                ncol=7,
            ),
            y_cols=list(range(1, n_series + 1)),
        )
        renderer = MatplotlibRenderer()
        fig = renderer.render_overlay(df, config)
        try:
            ax = fig.axes[0]
            legend = ax.get_legend()
            assert legend is not None
            assert legend._ncols == 7  # noqa: SLF001 - matplotlib exposes ncol via private attr
            fig.canvas.draw()
            legend_bbox = legend.get_window_extent(fig.canvas.get_renderer())
            axes_bbox = ax.get_window_extent(fig.canvas.get_renderer())
            assert legend_bbox.y1 <= axes_bbox.y0
        finally:
            close_fig(fig)

    def test_auto_policy_bottom_threshold_none_keeps_outside_right(self):
        """bottom_threshold=None keeps auto resolving to outside_right for many items."""
        n_series = 25
        df = self._multi_series_df(n_series)
        config = self._build_config(
            LegendConfig(
                policy="auto",
                outside_threshold=8,
                bottom_threshold=None,
                max_items=None,
            ),
            y_cols=list(range(1, n_series + 1)),
        )
        renderer = MatplotlibRenderer()
        fig = renderer.render_overlay(df, config)
        try:
            ax = fig.axes[0]
            legend = ax.get_legend()
            assert legend is not None
            fig.canvas.draw()
            legend_bbox = legend.get_window_extent(fig.canvas.get_renderer())
            axes_bbox = ax.get_window_extent(fig.canvas.get_renderer())
            assert legend_bbox.x0 >= axes_bbox.x1
        finally:
            close_fig(fig)

    def test_auto_policy_resolves_to_hide_when_exceeding_max_items(self):
        """policy="auto" resolves to hide once item count exceeds max_items."""
        df = self._multi_series_df(12)
        config = self._build_config(
            LegendConfig(policy="auto", outside_threshold=8, max_items=10),
            y_cols=list(range(1, 13)),
        )
        renderer = MatplotlibRenderer()
        fig = renderer.render_overlay(df, config)
        try:
            assert fig.axes[0].get_legend() is None
        finally:
            close_fig(fig)

    def test_legend_not_clipped_when_saved_outside_right(self, tmp_path):
        """Acceptance: legend placed outside the axes is not clipped when saved."""
        from rdetoolkit.graph.io.file_writer import FileWriter

        df = self._multi_series_df(10)
        config = self._build_config(
            LegendConfig(policy="outside_right"), y_cols=list(range(1, 11)),
        )
        renderer = MatplotlibRenderer()
        fig = renderer.render_overlay(df, config)
        try:
            writer = FileWriter()
            for fmt in ("png", "svg"):
                saved_path = writer.save_figure(fig, tmp_path, f"legend_outside.{fmt}", fmt)
                assert saved_path.exists()
                assert saved_path.stat().st_size > 0
        finally:
            close_fig(fig)

    def test_max_items_caps_explicit_inside_policy(self):
        """max_items remains a hard cap even for an explicitly requested (non-auto) policy."""
        df = self._multi_series_df(5)
        config = self._build_config(
            LegendConfig(policy="inside", max_items=3), y_cols=list(range(1, 6)),
        )
        renderer = MatplotlibRenderer()
        fig = renderer.render_overlay(df, config)
        try:
            assert fig.axes[0].get_legend() is None
        finally:
            close_fig(fig)

    def test_max_items_caps_explicit_outside_bottom_policy(self):
        """max_items remains a hard cap for outside_bottom too."""
        df = self._multi_series_df(5)
        config = self._build_config(
            LegendConfig(policy="outside_bottom", max_items=3), y_cols=list(range(1, 6)),
        )
        renderer = MatplotlibRenderer()
        fig = renderer.render_overlay(df, config)
        try:
            assert fig.axes[0].get_legend() is None
        finally:
            close_fig(fig)

    def test_legacy_policy_with_no_legend_entries_renders_nothing(self):
        """policy="legacy" with zero filtered legend entries returns None (no crash)."""
        df = pd.DataFrame({"x": [0, 1, 2], "y": [0, 1, 2]})
        builder = PlotConfigBuilder()
        builder.set_columns(x_col=0, y_cols=[1])
        builder.set_legend(LegendConfig())
        config = builder.build()
        renderer = MatplotlibRenderer()
        # Directly exercise the legacy branch with no handles/labels at all.
        fig = renderer.render_overlay(df, config)
        try:
            ax = fig.axes[0]
            legend_obj = renderer._render_legend_legacy(ax, [], [], config)  # noqa: SLF001 - unit-level branch coverage
            assert legend_obj is None
        finally:
            close_fig(fig)
