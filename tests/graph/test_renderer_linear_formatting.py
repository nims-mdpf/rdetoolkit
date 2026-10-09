"""Renderer linear-scale axis formatting regression tests.

Equivalence Partitioning Table
| API                                | Input/State Partition                        | Rationale                                                    | Expected Outcome                                                | Test ID      |
| ----------------------------------- | --------------------------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------- | ------------ |
| MatplotlibRenderer.render_overlay  | Large-magnitude linear-scale y values          | Large values should use ScalarFormatter with mathtext offset | y-axis major formatter is ScalarFormatter with matching offset font size | TC-EP-001 |
| MatplotlibRenderer.render_overlay  | Small-magnitude linear-scale y values          | Small values should also use ScalarFormatter consistently     | y-axis major formatter is ScalarFormatter with matching offset font size | TC-EP-002 |
| MatplotlibRenderer.render_overlay  | Normal-magnitude linear-scale y values (0-100) | Values within powerlimits must remain plain (no regression)  | Offset text is empty string                                    | TC-EP-003 |

Boundary Value Table
| API                                | Boundary                                       | Rationale                                                    | Expected Outcome                                               | Test ID      |
| ----------------------------------- | ----------------------------------------------- | -------------------------------------------------------------- | -------------------------------------------------------------- | ------------ |
| MatplotlibRenderer.render_overlay  | Major tick count for large-magnitude values     | MaxNLocator(nbins=6) must cap the number of major ticks       | len(ax.get_yticks()) <= 6                                      | TC-BV-001    |
| MatplotlibRenderer.render_overlay  | Major tick count for small-magnitude values     | MaxNLocator(nbins=6) must cap the number of major ticks       | len(ax.get_yticks()) <= 6                                      | TC-BV-002    |
| MatplotlibRenderer.render_overlay  | Major tick count for normal-magnitude values    | MaxNLocator(nbins=6) must cap the number of major ticks       | len(ax.get_yticks()) <= 6                                      | TC-BV-003    |

Pytest Execution Commands:
- Direct: PYTHONPATH=src pytest -q --maxfail=1 --cov=rdetoolkit --cov-branch --cov-report=term-missing --cov-report=html tests/graph/test_renderer_linear_formatting.py
- Via tox: tox -e py312-module -- tests/graph/test_renderer_linear_formatting.py
"""

from __future__ import annotations

from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
import pandas as pd

from rdetoolkit.graph.models import AxisConfig, DirectionConfig, LegendConfig, OutputConfig, PlotConfig, PlotMode
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer


def build_config(**overrides: Any) -> PlotConfig:
    """Construct a PlotConfig with sensible defaults for tests."""
    config = PlotConfig(
        mode=PlotMode.OVERLAY,
        x_col=[0],
        y_cols=[1],
        x_axis=AxisConfig(label="X", scale="linear"),
        y_axis=AxisConfig(label="Y", scale="linear"),
        legend=LegendConfig(),
        direction=DirectionConfig(),
        output=OutputConfig(),
    )
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def test_matplotlib_renderer_large_values_use_scalar_formatter__tc_ep_001() -> None:
    # Given: linear-scale data spanning a large magnitude range
    df = pd.DataFrame({"x": [0, 1, 2], "y": [0, 1.8e6, 3.6e6]})
    config = build_config(y_axis=AxisConfig(label="y", scale="linear"))

    # When: rendering the overlay plot
    fig = MatplotlibRenderer().render_overlay(df, config)
    try:
        fig.canvas.draw()
        ax = fig.axes[0]

        # Then: the y-axis uses a ScalarFormatter with mathtext, offset font matching tick labels
        formatter = ax.yaxis.get_major_formatter()
        assert isinstance(formatter, ScalarFormatter)
        offset_text = ax.yaxis.get_offset_text()
        assert offset_text.get_fontsize() == plt.rcParams["xtick.labelsize"]
    finally:
        plt.close(fig)


def test_matplotlib_renderer_small_values_use_scalar_formatter__tc_ep_002() -> None:
    # Given: linear-scale data spanning a very small magnitude range
    df = pd.DataFrame({"x": [0, 1, 2], "y": [0, 1.75e-6, 3.5e-6]})
    config = build_config(y_axis=AxisConfig(label="y", scale="linear"))

    # When: rendering the overlay plot
    fig = MatplotlibRenderer().render_overlay(df, config)
    try:
        fig.canvas.draw()
        ax = fig.axes[0]

        # Then: the y-axis uses a ScalarFormatter with offset font matching tick labels
        formatter = ax.yaxis.get_major_formatter()
        assert isinstance(formatter, ScalarFormatter)
        offset_text = ax.yaxis.get_offset_text()
        assert offset_text.get_fontsize() == plt.rcParams["xtick.labelsize"]
    finally:
        plt.close(fig)


def test_matplotlib_renderer_normal_values_stay_plain__tc_ep_003() -> None:
    # Given: linear-scale data within the default powerlimits (-3, 4)
    df = pd.DataFrame({"x": [0, 1, 2], "y": [0, 50, 100]})
    config = build_config(y_axis=AxisConfig(label="y", scale="linear"))

    # When: rendering the overlay plot
    fig = MatplotlibRenderer().render_overlay(df, config)
    try:
        fig.canvas.draw()
        ax = fig.axes[0]

        # Then: no scientific offset is shown, preserving legacy plain output
        offset_text = ax.yaxis.get_offset_text()
        assert offset_text.get_text() == ""
    finally:
        plt.close(fig)


def test_matplotlib_renderer_large_values_tick_count_capped__tc_bv_001() -> None:
    # Given: linear-scale data spanning a large magnitude range
    df = pd.DataFrame({"x": [0, 1, 2], "y": [0, 1.8e6, 3.6e6]})
    config = build_config(y_axis=AxisConfig(label="y", scale="linear"))

    # When: rendering the overlay plot
    fig = MatplotlibRenderer().render_overlay(df, config)
    try:
        fig.canvas.draw()
        ax = fig.axes[0]

        # Then: MaxNLocator(nbins=6) caps the number of major ticks visible on the axis
        y_min, y_max = ax.get_ylim()
        visible_ticks = [tick for tick in ax.get_yticks() if y_min <= tick <= y_max]
        assert len(visible_ticks) <= 6
    finally:
        plt.close(fig)


def test_matplotlib_renderer_small_values_tick_count_capped__tc_bv_002() -> None:
    # Given: linear-scale data spanning a very small magnitude range
    df = pd.DataFrame({"x": [0, 1, 2], "y": [0, 1.75e-6, 3.5e-6]})
    config = build_config(y_axis=AxisConfig(label="y", scale="linear"))

    # When: rendering the overlay plot
    fig = MatplotlibRenderer().render_overlay(df, config)
    try:
        fig.canvas.draw()
        ax = fig.axes[0]

        # Then: MaxNLocator(nbins=6) caps the number of major ticks visible on the axis
        y_min, y_max = ax.get_ylim()
        visible_ticks = [tick for tick in ax.get_yticks() if y_min <= tick <= y_max]
        assert len(visible_ticks) <= 6
    finally:
        plt.close(fig)


def test_matplotlib_renderer_normal_values_tick_count_capped__tc_bv_003() -> None:
    # Given: linear-scale data within the default powerlimits (-3, 4)
    df = pd.DataFrame({"x": [0, 1, 2], "y": [0, 50, 100]})
    config = build_config(y_axis=AxisConfig(label="y", scale="linear"))

    # When: rendering the overlay plot
    fig = MatplotlibRenderer().render_overlay(df, config)
    try:
        fig.canvas.draw()
        ax = fig.axes[0]

        # Then: MaxNLocator(nbins=6) caps the number of major ticks visible on the axis
        y_min, y_max = ax.get_ylim()
        visible_ticks = [tick for tick in ax.get_yticks() if y_min <= tick <= y_max]
        assert len(visible_ticks) <= 6
    finally:
        plt.close(fig)
