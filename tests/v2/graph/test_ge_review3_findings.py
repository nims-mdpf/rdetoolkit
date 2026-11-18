"""Fix round 3 (PR #753 review): three spec-API defects found through ``render_graph``.

F1 -- an unusable destination is rejected while planning, before any file is written.
``DirectorySink`` / ``OutputContextSink`` resolve every artifact before rendering; a
destination that is an existing directory, or whose output directory has an existing
non-directory ancestor, raises ``OutputPathError`` there, so no earlier artifact is
written (or overwritten) before the failure.

F2 -- direction filters and direction colours use the data-cell rule. A ``Direction``
member (a ``str`` subclass) normalizes to its value (``"Charge"``), not to
``str(member)`` (``"Direction.CHARGE"``), so it matches the cells.

F3 -- ``AxisSpec.grid`` and ``AxisSpec.tick_format`` reach the HTML axes of the spec
API, as they reach the Matplotlib axes. The legacy ``render_html`` adapter keeps the
v1 HTML axes (Plotly defaults; v1 never read these fields).

EP table:
| TC | Partition | Expected |
|----|-----------|----------|
| TC-FIX3-F1-EP-001 | individual destination is an existing directory, overlay file exists | OutputPathError; overlay bytes unchanged, nothing new written |
| TC-FIX3-F1-EP-002 | output dir below an existing regular file | OutputPathError; no file written |
| TC-FIX3-F1-EP-003 | OutputContextSink, destination is an existing directory | OutputPathError |
| TC-FIX3-F2-EP-001 | direction_filter=(Direction.CHARGE,) | one line drawn (the Charge rows) |
| TC-FIX3-F2-EP-002 | direction_colors={Direction.CHARGE: "red"} | the Charge line is red |
| TC-FIX3-F3-EP-001 | grid True / False per axis | showgrid follows each axis |
| TC-FIX3-F3-EP-002 | tick_format plain / sci / eng | exponentformat none / power / SI |
| TC-FIX3-F3-EP-003 | PNG + HTML of one spec | HTML showgrid equals Matplotlib grid visibility |

Negative table:
| TC | Partition | Expected |
|----|-----------|----------|
| TC-FIX3-F1-NEG-001 | destination does not exist yet | accepted, written |
| TC-FIX3-F2-NEG-001 | direction_filter=("Charge",) | unchanged: one line |
| TC-FIX3-F3-NEG-001 | tick_format="auto" | no exponentformat set |
| TC-FIX3-F3-NEG-002 | log axis with tick_format="eng" | log formatting kept (exponentformat power) |
| TC-FIX3-F3-NEG-003 | legacy render_html with grid / tick_format | showgrid and exponentformat unset (v1 HTML) |
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import pytest
from matplotlib.colors import to_rgba

from rdetoolkit.graph.engine import render_graph
from rdetoolkit.graph.exceptions import OutputPathError
from rdetoolkit.graph.models import AxisConfig, Direction, PlotConfig
from rdetoolkit.graph.outputs import DirectorySink, OutputContextSink
from rdetoolkit.graph.plan import PlotData, build_plot_plan
from rdetoolkit.graph.spec import AxisSpec, GraphSpec, OutputSpec, SeriesSpec
from rdetoolkit.testing import make_output_context

plotly = pytest.importorskip("plotly")

from rdetoolkit.graph.renderers.plotly_renderer import PlotlyRenderer  # noqa: E402


def _xy() -> pd.DataFrame:
    return pd.DataFrame({"x": [1, 2], "y": [2, 4]})


def _directed() -> pd.DataFrame:
    return pd.DataFrame({"x": [1, 2, 3, 4], "y": [2, 4, 3, 1], "direction": ["Charge", "Charge", "Discharge", "Discharge"]})


def _files(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


# --- F1: destinations -------------------------------------------------------


def test_existing_directory_destination_fails_before_any_write__tc_fix3_f1_ep_001(tmp_path: Path) -> None:
    # Given: the individual destination is a directory and the overlay file exists
    (tmp_path / "plot_y.png").mkdir()
    (tmp_path / "plot.png").write_bytes(b"previous")
    # When / Then: planning rejects it
    with pytest.raises(OutputPathError, match="plot_y.png"):
        render_graph(_xy(), GraphSpec(layout="both"), output=OutputSpec(DirectorySink(tmp_path)))
    # And: the existing overlay was not overwritten and nothing else was written
    assert (tmp_path / "plot.png").read_bytes() == b"previous"
    assert _files(tmp_path) == ["plot.png"]
    assert plt.get_fignums() == []


def test_non_directory_ancestor_fails_before_any_write__tc_fix3_f1_ep_002(tmp_path: Path) -> None:
    # Given: the individual directory would be created below a regular file
    (tmp_path / "blocker").write_text("file", encoding="utf-8")
    sink = DirectorySink(tmp_path / "blocker" / "images", main_image_dir=tmp_path / "main")
    # When / Then
    with pytest.raises(OutputPathError, match="not a directory"):
        render_graph(_xy(), GraphSpec(layout="both"), output=OutputSpec(sink))
    assert _files(tmp_path) == ["blocker"]


def test_output_context_sink_rejects_directory_destination__tc_fix3_f1_ep_003(tmp_path: Path) -> None:
    # Given: an OutputContext whose main image destination is a directory
    context = make_output_context(tmp_path)
    target = OutputContextSink(context).resolve("main_image", "plot.png")
    target.mkdir(parents=True)
    # When / Then
    with pytest.raises(OutputPathError, match="plot.png"):
        OutputContextSink(context).resolve("main_image", "plot.png")


def test_fresh_destination_is_accepted__tc_fix3_f1_neg_001(tmp_path: Path) -> None:
    result = render_graph(_xy(), GraphSpec(layout="both"), output=OutputSpec(DirectorySink(tmp_path / "new")))
    assert [a.path.name for a in result.artifacts] == ["plot.png", "plot_y.png"]


# --- F2: direction keys -----------------------------------------------------


def _lines(spec: GraphSpec) -> list[object]:
    result = render_graph(_directed(), spec)
    lines = list(result.artifacts[0].figure.axes[0].get_lines())
    plt.close("all")
    return lines


@pytest.mark.parametrize("value", [Direction.CHARGE, "Charge"])
def test_direction_filter_matches_enum_and_string__tc_fix3_f2_ep_001(value: object) -> None:
    spec = GraphSpec(layout="overlay", series=(SeriesSpec(y="y", direction="direction"),), direction_filter=(value,))  # type: ignore[arg-type]
    lines = _lines(spec)
    assert len(lines) == 1
    assert list(lines[0].get_ydata()) == [2, 4]


def test_direction_colors_accept_enum_keys__tc_fix3_f2_ep_002() -> None:
    spec = GraphSpec(
        layout="overlay",
        series=(SeriesSpec(y="y", direction="direction"),),
        direction_colors={Direction.CHARGE: "red"},
    )
    assert dict(spec.direction_colors) == {"Charge": "red"}
    lines = _lines(spec)
    charge = next(line for line in lines if list(line.get_ydata()) == [2, 4])
    assert to_rgba(charge.get_color()) == to_rgba("red")


# --- F3: HTML axis style ----------------------------------------------------


def _plotly_axes(x_axis: AxisSpec, y_axis: AxisSpec) -> tuple[object, object]:
    frame = _xy()
    plan = build_plot_plan(frame, GraphSpec(layout="overlay", x_axis=x_axis, y_axis=y_axis))
    fig = PlotlyRenderer().render(plan, plan.figures[0], PlotData(frames=(frame,)))
    return fig.layout.xaxis, fig.layout.yaxis


def test_grid_follows_each_axis__tc_fix3_f3_ep_001() -> None:
    x_axis, y_axis = _plotly_axes(AxisSpec(grid=True), AxisSpec(grid=False))
    assert (x_axis.showgrid, y_axis.showgrid) == (True, False)


@pytest.mark.parametrize(("tick_format", "expected"), [("plain", "none"), ("sci", "power"), ("eng", "SI"), ("auto", None)])
def test_tick_format_maps_to_exponentformat__tc_fix3_f3_ep_002(tick_format: str, expected: str | None) -> None:
    x_axis, y_axis = _plotly_axes(AxisSpec(tick_format=tick_format), AxisSpec(tick_format=tick_format))  # type: ignore[arg-type]
    assert (x_axis.exponentformat, y_axis.exponentformat) == (expected, expected)


def test_log_axis_keeps_log_formatting__tc_fix3_f3_neg_002() -> None:
    x_axis, _ = _plotly_axes(AxisSpec(scale="log", tick_format="eng"), AxisSpec())
    assert x_axis.exponentformat == "power"
    assert x_axis.dtick == 1


def test_png_and_html_agree_on_grid__tc_fix3_f3_ep_003(tmp_path: Path) -> None:
    spec = GraphSpec(layout="overlay", x_axis=AxisSpec(grid=True), y_axis=AxisSpec(grid=False))
    png = render_graph(_xy(), spec)
    ax = png.artifacts[0].figure.axes[0]
    mpl_grid = (any(line.get_visible() for line in ax.xaxis.get_gridlines()), any(line.get_visible() for line in ax.yaxis.get_gridlines()))
    plt.close("all")
    x_axis, y_axis = _plotly_axes(spec.x_axis, spec.y_axis)
    assert (x_axis.showgrid, y_axis.showgrid) == mpl_grid == (True, False)


def test_legacy_render_html_keeps_v1_axes__tc_fix3_f3_neg_003() -> None:
    config = PlotConfig(x_col=0, y_cols=[1], x_axis=AxisConfig(label="X", grid=True, tick_format="eng"), y_axis=AxisConfig(label="Y", grid=False, tick_format="sci"))
    fig = PlotlyRenderer().render_html(_xy(), config)
    for axis in (fig.layout.xaxis, fig.layout.yaxis):
        assert axis.showgrid is None
        assert axis.exponentformat is None
