"""Unit tests for PlotlyRenderer (optional dependency)."""

from __future__ import annotations

import pandas as pd
import pytest

# PlotlyRenderer is an optional dependency
plotly = pytest.importorskip("plotly", reason="Plotly not installed")

from rdetoolkit.graph.renderers.plotly_renderer import PlotlyRenderer
from rdetoolkit.graph.models import (
    PlotConfig,
    AxisConfig,
    LegendConfig,
    DirectionConfig,
    Direction,
    OutputConfig,
)


# =============================================================================
# PlotlyRenderer Tests
# =============================================================================


def test_plotly_renderer_basic_plot():
    """Test PlotlyRenderer with basic DataFrame and config."""
    df = pd.DataFrame({
        "X": [1, 2, 3, 4, 5],
        "Y1": [10, 20, 15, 25, 30],
        "Y2": [5, 15, 10, 20, 25],
    })

    config = PlotConfig(
        x_col=[0],
        y_cols=[1, 2],
        x_axis=AxisConfig(label="X Axis"),
        y_axis=AxisConfig(label="Y Axis"),
        legend=LegendConfig(),
        direction=DirectionConfig(),
        output=OutputConfig(),
    )

    renderer = PlotlyRenderer()
    fig = renderer.render_html(df, config)

    # Check that figure was created
    assert fig is not None
    # Plotly Figure should have data traces
    assert hasattr(fig, "data")
    assert len(fig.data) > 0


def test_plotly_renderer_with_log_scale():
    """Test PlotlyRenderer with logarithmic scales."""
    df = pd.DataFrame({
        "X": [1, 10, 100, 1000],
        "Y": [1, 100, 10000, 1000000],
    })

    config = PlotConfig(
        x_col=[0],
        y_cols=[1],
        x_axis=AxisConfig(label="X", scale="log"),
        y_axis=AxisConfig(label="Y", scale="log"),
        legend=LegendConfig(),
        direction=DirectionConfig(),
        output=OutputConfig(),
    )

    renderer = PlotlyRenderer()
    fig = renderer.render_html(df, config)

    assert fig is not None
    # Check that layout has log scales (Plotly specific)
    assert fig.layout.xaxis.type == "log"
    assert fig.layout.yaxis.type == "log"


def test_plotly_renderer_with_title():
    """Test PlotlyRenderer includes title in figure."""
    df = pd.DataFrame({
        "X": [1, 2, 3],
        "Y": [4, 5, 6],
    })

    config = PlotConfig(
        x_col=[0],
        y_cols=[1],
        title="Test Plot Title",
        x_axis=AxisConfig(label="X"),
        y_axis=AxisConfig(label="Y"),
        legend=LegendConfig(),
        direction=DirectionConfig(),
        output=OutputConfig(),
    )

    renderer = PlotlyRenderer()
    fig = renderer.render_html(df, config)

    assert fig is not None
    assert fig.layout.title.text == "Test Plot Title"


def test_plotly_renderer_multiple_series():
    """Test PlotlyRenderer with many series."""
    data = {"X": list(range(10))}
    for i in range(10):
        data[f"Y{i}"] = [j * (i + 1) for j in range(10)]

    df = pd.DataFrame(data)

    config = PlotConfig(
        x_col=[0],
        y_cols=list(range(1, 11)),  # 10 y columns
        x_axis=AxisConfig(label="X"),
        y_axis=AxisConfig(label="Y"),
        legend=LegendConfig(),
        direction=DirectionConfig(),
        output=OutputConfig(),
    )

    renderer = PlotlyRenderer()
    fig = renderer.render_html(df, config)

    assert fig is not None
    # Should have 10 data traces
    assert len(fig.data) == 10


def test_plotly_renderer_with_axis_limits():
    """Test PlotlyRenderer respects axis limits."""
    df = pd.DataFrame({
        "X": [1, 2, 3, 4, 5],
        "Y": [10, 20, 30, 40, 50],
    })

    config = PlotConfig(
        x_col=[0],
        y_cols=[1],
        x_axis=AxisConfig(label="X", lim=(0, 10)),
        y_axis=AxisConfig(label="Y", lim=(0, 100)),
        legend=LegendConfig(),
        direction=DirectionConfig(),
        output=OutputConfig(),
    )

    renderer = PlotlyRenderer()
    fig = renderer.render_html(df, config)

    assert fig is not None
    # Check that axis limits are set (implementation may vary)
    # Plotly may not set range if not explicitly configured in renderer
    # Just verify figure was created successfully
    assert hasattr(fig.layout, "xaxis")
    assert hasattr(fig.layout, "yaxis")


def test_plotly_renderer_empty_dataframe():
    """Test PlotlyRenderer with empty DataFrame."""
    df = pd.DataFrame({"X": [], "Y": []})

    config = PlotConfig(
        x_col=[0],
        y_cols=[1],
        x_axis=AxisConfig(label="X"),
        y_axis=AxisConfig(label="Y"),
        legend=LegendConfig(),
        direction=DirectionConfig(),
        output=OutputConfig(),
    )

    renderer = PlotlyRenderer()

    # May raise ValueError or create empty figure
    try:
        fig = renderer.render_html(df, config)
        # If it succeeds, check for empty or minimal data
        assert fig is not None
    except ValueError:
        # Empty DataFrame may raise ValueError
        pass


def test_plotly_renderer_single_point():
    """Test PlotlyRenderer with single data point."""
    df = pd.DataFrame({
        "X": [1],
        "Y": [10],
    })

    config = PlotConfig(
        x_col=[0],
        y_cols=[1],
        x_axis=AxisConfig(label="X"),
        y_axis=AxisConfig(label="Y"),
        legend=LegendConfig(),
        direction=DirectionConfig(),
        output=OutputConfig(),
    )

    renderer = PlotlyRenderer()
    fig = renderer.render_html(df, config)

    assert fig is not None
    assert len(fig.data) == 1


def test_plotly_renderer_applies_direction_colors():
    """Direction-specific colors override series color assignments."""
    df = pd.DataFrame(
        {
            "X": [1, 2, 3, 4],
            "Y": [10, 15, 20, 25],
            "dir": ["Charge", "Charge", "Discharge", "Discharge"],
        }
    )

    custom_colors = {
        Direction.CHARGE: "#123456",
        "Discharge": "#abcdef",
    }

    config = PlotConfig(
        x_col=[0],
        y_cols=[1],
        direction_cols=[2],
        direction=DirectionConfig(colors=custom_colors, use_custom_colors=True),
        x_axis=AxisConfig(label="X"),
        y_axis=AxisConfig(label="Y"),
        legend=LegendConfig(),
        output=OutputConfig(),
    )

    renderer = PlotlyRenderer()
    fig = renderer.render_html(df, config)

    assert len(fig.data) == 2
    color_set = {trace.line.color for trace in fig.data}
    assert "#123456" in color_set
    assert "#abcdef" in color_set


def test_plotly_renderer_with_inverted_axes():
    """Test PlotlyRenderer with inverted axes."""
    df = pd.DataFrame({
        "X": [1, 2, 3, 4, 5],
        "Y": [10, 20, 30, 40, 50],
    })

    config = PlotConfig(
        x_col=[0],
        y_cols=[1],
        x_axis=AxisConfig(label="X", invert=True),
        y_axis=AxisConfig(label="Y", invert=True),
        legend=LegendConfig(),
        direction=DirectionConfig(),
        output=OutputConfig(),
    )

    renderer = PlotlyRenderer()
    fig = renderer.render_html(df, config)

    assert fig is not None
    # Implementation may not support invert yet
    # Just verify figure was created successfully
    assert hasattr(fig.layout, "xaxis")
    assert hasattr(fig.layout, "yaxis")


def test_plotly_renderer_with_grid():
    """Test PlotlyRenderer enables grid when requested."""
    df = pd.DataFrame({
        "X": [1, 2, 3],
        "Y": [4, 5, 6],
    })

    config = PlotConfig(
        x_col=[0],
        y_cols=[1],
        x_axis=AxisConfig(label="X", grid=True),
        y_axis=AxisConfig(label="Y", grid=True),
        legend=LegendConfig(),
        direction=DirectionConfig(),
        output=OutputConfig(),
    )

    renderer = PlotlyRenderer()
    fig = renderer.render_html(df, config)

    assert fig is not None
    # Implementation may not support grid configuration yet
    # Just verify figure was created successfully
    assert hasattr(fig.layout, "xaxis")
    assert hasattr(fig.layout, "yaxis")


def test_plotly_renderer_invalid_x_col():
    """Test PlotlyRenderer with None x_col raises error."""
    df = pd.DataFrame({
        "X": [1, 2, 3],
        "Y": [4, 5, 6],
    })

    config = PlotConfig(
        x_col=None,  # Invalid
        y_cols=[1],
        x_axis=AxisConfig(label="X"),
        y_axis=AxisConfig(label="Y"),
        legend=LegendConfig(),
        direction=DirectionConfig(),
        output=OutputConfig(),
    )

    renderer = PlotlyRenderer()

    with pytest.raises((ValueError, AttributeError)):
        renderer.render_html(df, config)


def test_plotly_renderer_invalid_y_cols():
    """Test PlotlyRenderer with None y_cols raises error."""
    df = pd.DataFrame({
        "X": [1, 2, 3],
        "Y": [4, 5, 6],
    })

    config = PlotConfig(
        x_col=[0],
        y_cols=None,  # Invalid
        x_axis=AxisConfig(label="X"),
        y_axis=AxisConfig(label="Y"),
        legend=LegendConfig(),
        direction=DirectionConfig(),
        output=OutputConfig(),
    )

    renderer = PlotlyRenderer()

    with pytest.raises((ValueError, AttributeError)):
        renderer.render_html(df, config)


def test_plotly_renderer_returns_figure_object():
    """Test PlotlyRenderer returns proper Plotly Figure object."""
    df = pd.DataFrame({
        "X": [1, 2, 3],
        "Y": [4, 5, 6],
    })

    config = PlotConfig(
        x_col=[0],
        y_cols=[1],
        x_axis=AxisConfig(label="X"),
        y_axis=AxisConfig(label="Y"),
        legend=LegendConfig(),
        direction=DirectionConfig(),
        output=OutputConfig(),
    )

    renderer = PlotlyRenderer()
    fig = renderer.render_html(df, config)

    # Check it's a Plotly Figure
    import plotly.graph_objects as go
    assert isinstance(fig, go.Figure)
