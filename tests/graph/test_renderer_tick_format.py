"""Renderer tick-format dispatch and axis-label unit composition tests.

Equivalence Partitioning Table
| API                                | Input/State Partition                                  | Rationale                                                       | Expected Outcome                                                    | Test ID   |
| ----------------------------------- | ------------------------------------------------------- | ---------------------------------------------------------------- | -------------------------------------------------------------------- | --------- |
| MatplotlibRenderer.render_overlay  | tick_format="plain" with large-magnitude values          | Plain mode must never show ×10^n offset regardless of magnitude | Offset text is empty, ScalarFormatter._scientific is False           | TC-EP-001 |
| MatplotlibRenderer.render_overlay  | tick_format="sci" with normal-magnitude values           | Sci mode must always force scientific offset notation           | Offset text is non-empty                                             | TC-EP-002 |
| MatplotlibRenderer.render_overlay  | tick_format="eng"                                        | Eng mode must use EngFormatter                                  | Major formatter is an EngFormatter instance                          | TC-EP-003 |
| MatplotlibRenderer.render_overlay  | tick_format="auto" (default) with normal-magnitude values | auto must reuse Task 01 behavior (no regression)                | Offset text is empty (plain, same as Phase 1 regression test)        | TC-EP-004 |
| MatplotlibRenderer.render_overlay  | AxisConfig.scilimits custom value                        | Custom scilimits must be forwarded to ScalarFormatter            | formatter._powerlimits == custom scilimits                           | TC-EP-005 |
| MatplotlibRenderer.render_overlay  | AxisConfig.unit set, label without unit suffix           | Unit must be composed into the axis label                       | ax.get_ylabel() == "IonSource (mPa)"                                  | TC-EP-006 |
| MatplotlibRenderer.render_overlay  | AxisConfig.unit set, label already containing unit suffix| Unit must not be double-composed                                | ax.get_ylabel() == "Voltage (V)"                                      | TC-EP-007 |
| MatplotlibRenderer.render_overlay  | tick_format="plain" with large additive offset values     | Plain mode must also suppress additive offset (+1e6) notation   | formatter.get_useOffset() is False, offset text is empty             | TC-EP-008 |

Pytest Execution Commands:
- Direct: PYTHONPATH=src pytest -q --maxfail=1 --cov=rdetoolkit --cov-branch --cov-report=term-missing --cov-report=html tests/graph/test_renderer_tick_format.py
- Via tox: tox -e py312-module -- tests/graph/test_renderer_tick_format.py
"""

from __future__ import annotations

from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import EngFormatter, ScalarFormatter
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


def test_matplotlib_renderer_plain_format_suppresses_offset__tc_ep_001() -> None:
    # Given: tick_format="plain" with data spanning a large magnitude range
    df = pd.DataFrame({"x": [0, 1, 2], "y": [0, 1.8e6, 3.6e6]})
    config = build_config(y_axis=AxisConfig(label="y", scale="linear", tick_format="plain"))

    # When: rendering the overlay plot
    fig = MatplotlibRenderer().render_overlay(df, config)
    try:
        fig.canvas.draw()
        ax = fig.axes[0]

        # Then: no scientific offset is shown and the formatter is non-scientific
        formatter = ax.yaxis.get_major_formatter()
        assert isinstance(formatter, ScalarFormatter)
        assert formatter._scientific is False
        offset_text = ax.yaxis.get_offset_text()
        assert offset_text.get_text() == ""
    finally:
        plt.close(fig)


def test_matplotlib_renderer_plain_format_suppresses_additive_offset__tc_ep_008() -> None:
    # Given: tick_format="plain" with values sharing a large additive offset
    # (small spread around 1e6 triggers ScalarFormatter's useOffset behavior)
    df = pd.DataFrame({"x": [0, 1, 2], "y": [1_000_000, 1_000_001, 1_000_002]})
    config = build_config(y_axis=AxisConfig(label="y", scale="linear", tick_format="plain"))

    # When: rendering the overlay plot
    fig = MatplotlibRenderer().render_overlay(df, config)
    try:
        fig.canvas.draw()
        ax = fig.axes[0]

        # Then: no additive offset (e.g. "+1e6") is shown and tick labels stay plain
        formatter = ax.yaxis.get_major_formatter()
        assert isinstance(formatter, ScalarFormatter)
        assert formatter.get_useOffset() is False
        offset_text = ax.yaxis.get_offset_text()
        assert offset_text.get_text() == ""
    finally:
        plt.close(fig)


def test_matplotlib_renderer_sci_format_forces_offset__tc_ep_002() -> None:
    # Given: tick_format="sci" with data within the normal magnitude range
    df = pd.DataFrame({"x": [0, 1, 2], "y": [0, 50, 100]})
    config = build_config(y_axis=AxisConfig(label="y", scale="linear", tick_format="sci"))

    # When: rendering the overlay plot
    fig = MatplotlibRenderer().render_overlay(df, config)
    try:
        fig.canvas.draw()
        ax = fig.axes[0]

        # Then: an offset (scientific notation) is always shown, even in the normal range
        offset_text = ax.yaxis.get_offset_text()
        assert offset_text.get_text() != ""
    finally:
        plt.close(fig)


def test_matplotlib_renderer_eng_format_uses_eng_formatter__tc_ep_003() -> None:
    # Given: tick_format="eng"
    df = pd.DataFrame({"x": [0, 1, 2], "y": [0, 50, 100]})
    config = build_config(y_axis=AxisConfig(label="y", scale="linear", tick_format="eng"))

    # When: rendering the overlay plot
    fig = MatplotlibRenderer().render_overlay(df, config)
    try:
        fig.canvas.draw()
        ax = fig.axes[0]

        # Then: the y-axis major formatter is an EngFormatter instance
        formatter = ax.yaxis.get_major_formatter()
        assert isinstance(formatter, EngFormatter)
    finally:
        plt.close(fig)


def test_matplotlib_renderer_auto_format_matches_phase1_regression__tc_ep_004() -> None:
    # Given: tick_format left at its default ("auto") with normal-magnitude data
    df = pd.DataFrame({"x": [0, 1, 2], "y": [0, 50, 100]})
    config = build_config(y_axis=AxisConfig(label="y", scale="linear"))

    # When: rendering the overlay plot
    fig = MatplotlibRenderer().render_overlay(df, config)
    try:
        fig.canvas.draw()
        ax = fig.axes[0]

        # Then: behavior matches Task 01's Phase 1 regression test (plain, no offset)
        formatter = ax.yaxis.get_major_formatter()
        assert isinstance(formatter, ScalarFormatter)
        offset_text = ax.yaxis.get_offset_text()
        assert offset_text.get_text() == ""
    finally:
        plt.close(fig)


def test_matplotlib_renderer_custom_scilimits_forwarded__tc_ep_005() -> None:
    # Given: a custom scilimits value on the AxisConfig
    df = pd.DataFrame({"x": [0, 1, 2], "y": [0, 50, 100]})
    config = build_config(y_axis=AxisConfig(label="Y", scilimits=(-2, 2)))

    # When: rendering the overlay plot
    fig = MatplotlibRenderer().render_overlay(df, config)
    try:
        fig.canvas.draw()
        ax = fig.axes[0]

        # Then: the custom scilimits are forwarded to the ScalarFormatter
        formatter = ax.yaxis.get_major_formatter()
        assert isinstance(formatter, ScalarFormatter)
        assert formatter._powerlimits == (-2, 2)
    finally:
        plt.close(fig)


def test_matplotlib_renderer_unit_composed_into_label__tc_ep_006() -> None:
    # Given: a unit is set and the label does not already include it
    df = pd.DataFrame({"x": [0, 1, 2], "y": [0, 50, 100]})
    config = build_config(y_axis=AxisConfig(label="IonSource", unit="mPa"))

    # When: rendering the overlay plot
    fig = MatplotlibRenderer().render_overlay(df, config)
    try:
        fig.canvas.draw()
        ax = fig.axes[0]

        # Then: the unit is composed onto the label
        assert ax.get_ylabel() == "IonSource (mPa)"
    finally:
        plt.close(fig)


def test_matplotlib_renderer_unit_not_double_composed__tc_ep_007() -> None:
    # Given: the label already contains the unit suffix
    df = pd.DataFrame({"x": [0, 1, 2], "y": [0, 50, 100]})
    config = build_config(y_axis=AxisConfig(label="Voltage (V)", unit="V"))

    # When: rendering the overlay plot
    fig = MatplotlibRenderer().render_overlay(df, config)
    try:
        fig.canvas.draw()
        ax = fig.axes[0]

        # Then: the label is left untouched (no double composition)
        assert ax.get_ylabel() == "Voltage (V)"
    finally:
        plt.close(fig)
