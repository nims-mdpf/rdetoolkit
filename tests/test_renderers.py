from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from pathlib import Path

import pandas as pd
import pytest

from rdetoolkit.graph.config import PlotConfigBuilder
from rdetoolkit.graph.io.file_writer import FileWriter
from rdetoolkit.graph.io.path_validator import PathValidator
from rdetoolkit.graph.models import (
    PlotConfig,
    AxisConfig,
    LegendConfig,
    DirectionConfig,
    OutputConfig,
    PlotMode,
)
from rdetoolkit.graph.renderers import plotly_renderer as pr
from rdetoolkit.graph.renderers.plotly_renderer import PlotlyRenderer
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer
from rdetoolkit.graph.api.csv2graph import RenderCollections, RenderResult, _save_render_results



class AttrDict(dict):
    """Dictionary with attribute access for test stubs."""

    def __getattr__(self, item: str) -> Any:  # pragma: no cover - simple delegation
        return self[item]

    def __setattr__(self, key: str, value: Any) -> None:  # pragma: no cover
        self[key] = value


@dataclass
class StubScatter:
    """Simplified stand-in for plotly.graph_objs.Scatter."""

    kwargs: dict[str, Any]

    def __init__(self, **kwargs: Any) -> None:
        object.__setattr__(self, "kwargs", kwargs)
        for key, value in kwargs.items():
            object.__setattr__(self, key, value)


class StubLayout:
    """Simplified layout container replicating attribute access."""

    def __init__(self, *, title: str | None = None, xaxis: dict[str, Any] | None = None, yaxis: dict[str, Any] | None = None, showlegend: bool = True, updatemenus: list[dict[str, Any]] | None = None) -> None:
        self.title = AttrDict({"text": title})
        self.xaxis = AttrDict(xaxis or {})
        self.yaxis = AttrDict(yaxis or {})
        self.showlegend = showlegend
        self.updatemenus = updatemenus or []


class StubFigure:
    """Mimics plotly.graph_objs.Figure for renderer tests."""

    def __init__(self, data: list[Any] | None = None, layout: StubLayout | None = None) -> None:
        self.data: list[Any] = list(data) if data is not None else []
        self.layout = layout or StubLayout()
        self.annotations: list[dict[str, Any]] = []

    def add_annotation(self, **kwargs: Any) -> None:
        self.annotations.append(kwargs)


@pytest.fixture(autouse=True)
def stub_plotly(monkeypatch: pytest.MonkeyPatch) -> None:
    """Automatically replace Plotly bindings with lightweight stubs for tests."""

    stub_go = SimpleNamespace(
        Scatter=StubScatter,
        Layout=StubLayout,
        Figure=StubFigure,
    )
    monkeypatch.setattr(pr, "go", stub_go)


def build_config(**overrides: Any) -> PlotConfig:
    """Helper to build PlotConfig with sensible defaults for tests."""

    config = PlotConfig(
        x_col=[0],
        y_cols=[1],
        x_axis=AxisConfig(label="Time", scale="linear"),
        y_axis=AxisConfig(label="Value", scale="linear"),
        legend=LegendConfig(),
        direction=DirectionConfig(),
        output=OutputConfig(),
    )
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def test_plotly_renderer_creates_traces_with_colors() -> None:
    df = pd.DataFrame({
        "X": [0, 1, 2, 3],
        "Y1": [1, 2, 3, 4],
        "Y2": [4, 3, 2, 1],
    })
    config = build_config(y_cols=[1, 2])

    renderer = PlotlyRenderer()
    fig = renderer.render_html(df, config)

    assert isinstance(fig, StubFigure)
    assert len(fig.data) == 2
    names = {trace.name for trace in fig.data}
    assert names == {"Y1", "Y2"}
    colors = {trace.line["color"] for trace in fig.data}
    assert len(colors) == 2  # 異なる色が割り当てられる


def test_plotly_renderer_applies_log_scale_and_updatemenus() -> None:
    df = pd.DataFrame({"X": [1, 10], "Y": [2, 20]})
    config = build_config(
        x_axis=AxisConfig(label="X", scale="log"),
        y_axis=AxisConfig(label="Y", scale="log"),
    )

    fig = PlotlyRenderer().render_html(df, config)

    assert fig.layout.xaxis.type == "log"
    assert fig.layout.yaxis.type == "log"
    assert len(fig.layout.updatemenus) == 2
    buttons = fig.layout.updatemenus[0]["buttons"]
    assert {btn["label"] for btn in buttons} == {"X Linear", "X Log"}


def test_plotly_renderer_adds_annotations_when_legend_info_present() -> None:
    df = pd.DataFrame({"X": [0, 1], "Y": [1, 2]})
    config = build_config()
    config.legend.info = "Line1"

    fig = PlotlyRenderer().render_html(df, config)

    assert len(fig.annotations) == 1
    assert fig.annotations[0]["text"] == "Line1"


def test_plotly_renderer_respects_direction_filtering() -> None:
    df = pd.DataFrame({
        "X": [0, 1, 2, 3],
        "Y": [1, 2, 3, 4],
        "Dir": ["A", "B", "A", "B"],
    })
    config = build_config(
        direction=DirectionConfig(filters=["A"]),
        direction_cols=[2],
    )

    fig = PlotlyRenderer().render_html(df, config)

    assert len(fig.data) == 1
    trace = fig.data[0]
    assert list(trace.x) == [0, 2]
    assert list(trace.y) == [1, 3]
    assert trace.showlegend is True


def test_plotly_renderer_no_plotly_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pr, "go", None)
    renderer = PlotlyRenderer()
    df = pd.DataFrame({"X": [0, 1], "Y": [1, 2]})
    config = build_config()

    with pytest.raises(ImportError):
        renderer.render_html(df, config)


def test_overlay_strategy_html_output(tmp_path):
    df = pd.DataFrame({'time': [0, 1], 'value': [1, 2]})
    builder = PlotConfigBuilder()
    builder.set_mode(PlotMode.OVERLAY)
    builder.set_columns(x_col=0, y_cols=[1])
    builder.set_output(OutputConfig(base_name='plot', formats=['png', 'html'], return_fig=False, main_image_dir=tmp_path / 'main'))
    config = builder.build()
    renderer = MatplotlibRenderer()
    collections = RenderCollections(
        overlay=[
            RenderResult(figure=renderer.render_overlay(df, config), filename='plot.png', format='png'),
            RenderResult(figure=renderer.render_overlay(df, config), filename='plot.html', format='html')
        ],
        individual=[]
    )
    PathValidator.ensure_directory = lambda self, p: Path(p)
    saved = []
    def fake_save(self, figure, output_dir, filename, format_type, **kwargs):
        saved.append((Path(output_dir), filename, format_type))
    FileWriter.save_figure = fake_save
    _save_render_results(collections, tmp_path, tmp_path / 'main')
    assert saved[0][0] == tmp_path / 'main'
    assert saved[1][0] == tmp_path

