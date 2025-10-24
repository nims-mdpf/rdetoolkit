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
    PlotMode,
)
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer
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
