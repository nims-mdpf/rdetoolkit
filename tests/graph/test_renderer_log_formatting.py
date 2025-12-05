"""Renderer legend/log-scale regression tests.

Equivalence Partitioning Table
| API                           | Input/State Partition                   | Rationale                                           | Expected Outcome                                   | Test ID      |
| ----------------------------- | --------------------------------------- | --------------------------------------------------- | -------------------------------------------------- | ------------ |
| PlotlyRenderer.render_html    | Series header includes ':' suffix       | Legend should ignore suffix details                 | Legend names drop suffix after ':'                 | TC-EP-001    |
| PlotlyRenderer.render_html    | x_col and y_cols length mismatch        | Validation should reject inconsistent axis specs    | ValueError raised                                   | TC-EP-002    |
| PlotlyRenderer.render_html    | direction_cols longer than y_cols       | Extra direction specs are invalid                   | ValueError raised                                   | TC-EP-003    |
| MatplotlibRenderer.render_overlay | Log-scale axes with plotted data     | Log ticks should hide intermediate values           | Ticks show only power-of-ten marks                  | TC-EP-004    |
| MatplotlibRenderer.render_overlay | Missing y_cols configuration         | Renderer must enforce required configuration        | ValueError raised                                   | TC-EP-005    |
| MatplotlibRenderer.render_overlay | x_col/y_cols counts disagree         | Overlay renderer should fail fast on mismatch       | ValueError raised                                   | TC-EP-006    |

Boundary Value Table
| API                           | Boundary                                | Rationale                                           | Expected Outcome                                   | Test ID      |
| ----------------------------- | --------------------------------------- | --------------------------------------------------- | -------------------------------------------------- | ------------ |
| PlotlyRenderer.render_html    | Single decade span on log axis          | Ensure tick formatting applies on minimal log range | Axis layout uses dtick=1 and power exponents        | TC-BV-001    |
| MatplotlibRenderer.render_overlay | Data exactly on decade boundaries    | Formatter must label only decade ticks without minors | Major tick labels rendered as 10^n with no minor ticks | TC-BV-002 |

Pytest Execution Commands:
- Direct: PYTHONPATH=src pytest -q --maxfail=1 --cov=rdetoolkit --cov-branch --cov-report=term-missing --cov-report=html tests/graph/test_renderer_log_formatting.py
- Via tox: tox
"""

from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator
import pandas as pd
import pytest

import rdetoolkit.graph.renderers.plotly_renderer as pr
from rdetoolkit.graph.models import AxisConfig, DirectionConfig, LegendConfig, OutputConfig, PlotConfig, PlotMode
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer
from rdetoolkit.graph.renderers.plotly_renderer import PlotlyRenderer
from tests.test_renderers import AttrDict, StubFigure, StubLayout, StubScatter


@pytest.fixture(autouse=True)
def stub_plotly(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace plotly with lightweight stubs."""
    stub_go = SimpleNamespace(
        Scatter=StubScatter,
        Layout=StubLayout,
        Figure=StubFigure,
    )
    monkeypatch.setattr(pr, "go", stub_go)


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


def test_plotly_renderer_render_html_drops_suffix__tc_ep_001() -> None:
    # Given: a dataframe with a colon-separated header for the series
    df = pd.DataFrame({"time": [0, 1], "total:intensity": [1.0, 2.0]})
    config = build_config()

    # When: rendering the HTML plot
    fig = PlotlyRenderer().render_html(df, config)

    # Then: the legend shows only the prefix before the colon
    assert {trace.name for trace in fig.data} == {"total"}


def test_plotly_renderer_mismatched_columns_raise__tc_ep_002() -> None:
    # Given: a config where x_col length exceeds y_cols length
    df = pd.DataFrame({"x1": [0, 1], "x2": [2, 3], "y": [4, 5]})
    config = build_config(x_col=[0, 1], y_cols=[2])

    # When: rendering is attempted with mismatched axes
    # Then: the renderer rejects the invalid configuration
    with pytest.raises(ValueError):
        PlotlyRenderer().render_html(df, config)


def test_plotly_renderer_direction_length_mismatch__tc_ep_003() -> None:
    # Given: direction columns specified for more series than provided
    df = pd.DataFrame({"time": [0, 1], "y": [1, 2], "dir": ["A", "B"], "extra": ["C", "D"]})
    config = build_config(y_cols=[1], direction_cols=[2, 3])

    # When: rendering is attempted with excess direction columns
    # Then: the renderer raises a validation error
    with pytest.raises(ValueError):
        PlotlyRenderer().render_html(df, config)


def test_plotly_renderer_log_layout_uses_decades__tc_bv_001() -> None:
    # Given: log-scale axes covering a single decade
    df = pd.DataFrame({"time": [1, 10], "value": [1, 10]})
    config = build_config(
        x_axis=AxisConfig(label="time", scale="log"),
        y_axis=AxisConfig(label="value", scale="log"),
    )

    # When: building the HTML plot
    fig = PlotlyRenderer().render_html(df, config)

    # Then: the axis layout uses decade ticks and power-of-ten formatting
    assert fig.layout.xaxis["dtick"] == 1
    assert fig.layout.xaxis["exponentformat"] == "power"
    assert fig.layout.xaxis["showexponent"] == "all"


def test_matplotlib_renderer_log_ticks_use_decades__tc_ep_004() -> None:
    # Given: log-scale axes with values across multiple decades
    df = pd.DataFrame({"x": [1, 10, 100], "y": [1, 10, 100]})
    config = build_config(
        x_axis=AxisConfig(label="x", scale="log"),
        y_axis=AxisConfig(label="y", scale="log"),
    )

    # When: rendering the overlay plot
    fig = MatplotlibRenderer().render_overlay(df, config)
    try:
        fig.canvas.draw()
        ax = fig.axes[0]
        x_labels = [tick.get_text() for tick in ax.get_xticklabels() if tick.get_text()]
        y_labels = [tick.get_text() for tick in ax.get_yticklabels() if tick.get_text()]

        # Then: only decade ticks are labeled and minor ticks are suppressed
        assert isinstance(ax.xaxis.get_minor_locator(), NullLocator)
        assert isinstance(ax.yaxis.get_minor_locator(), NullLocator)
        assert x_labels and y_labels
        assert all("10^" in label for label in x_labels)
        assert all("10^" in label for label in y_labels)
        assert all(label not in {"2", "5"} for label in x_labels)
        assert all(label not in {"2", "5"} for label in y_labels)
    finally:
        plt.close(fig)


def test_matplotlib_renderer_missing_ycols_errors__tc_ep_005() -> None:
    # Given: a configuration without y_cols specified
    df = pd.DataFrame({"x": [0, 1], "y": [1, 2]})
    config = build_config(y_cols=None)

    # When: rendering is attempted without required y_cols
    # Then: a ValueError is raised
    with pytest.raises(ValueError):
        MatplotlibRenderer().render_overlay(df, config)


def test_matplotlib_renderer_mismatched_columns_errors__tc_ep_006() -> None:
    # Given: a configuration where x_col entries outnumber y_cols
    df = pd.DataFrame({"x1": [0, 1], "x2": [1, 2], "y": [2, 3]})
    config = build_config(x_col=[0, 1], y_cols=[2])

    # When: rendering overlay with mismatched columns
    # Then: the renderer rejects the configuration
    with pytest.raises(ValueError):
        MatplotlibRenderer().render_overlay(df, config)


def test_matplotlib_renderer_ticks_snap_to_decades__tc_bv_002() -> None:
    # Given: data points that lie exactly on decade boundaries
    df = pd.DataFrame({"x": [0.1, 1, 10, 100], "y": [0.01, 0.1, 1, 10]})
    config = build_config(
        x_axis=AxisConfig(label="x", scale="log"),
        y_axis=AxisConfig(label="y", scale="log"),
    )

    # When: rendering the overlay plot
    fig = MatplotlibRenderer().render_overlay(df, config)
    try:
        fig.canvas.draw()
        ax = fig.axes[0]
        x_ticks = ax.get_xticks()
        y_ticks = ax.get_yticks()

        # Then: every tick is an exact power of ten with no intermediate markers
        assert all(math.isclose(math.log10(tick), round(math.log10(tick)), abs_tol=1e-9) for tick in x_ticks if tick > 0)
        assert all(math.isclose(math.log10(tick), round(math.log10(tick)), abs_tol=1e-9) for tick in y_ticks if tick > 0)
    finally:
        plt.close(fig)
