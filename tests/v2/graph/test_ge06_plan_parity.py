"""GE-06 (#712): one normalized series plan for Matplotlib and Plotly.

Both renderers consume the same ``PlotPlan`` (``render(plan, figure, data)``); the
legacy ``render_overlay`` / ``render_individual`` / ``render_html(df, config)``
methods are adapters that build that plan with ``compat.plan_from_config`` and keep
their backend-specific legacy labels (ruling C-12, open item O-7). Column, label and
direction resolution happen once, at plan creation, so an invalid selection fails
before any figure exists. Semantic parity is asserted on drawn artists and traces
(series count, labels, data, colours, legend roles), never on images.

Intentional behaviour change IC-11 (versioned tests end in ``_v2_0``): a direct
``PlotlyRenderer.render_html`` pads a short ``direction_cols`` list (it raised), and
duplicate column labels plot through the legacy facade when they are addressed by
position or by the default selection (they raised "resolved to a slice"). Duplicate
legend labels are listed once and colours follow the series position in both backends.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| render(plan) mpl + plotly | single x, two series | lines == traces == plan: count, labels, data, colours | TC-GE06-EP-001 |
| render(plan) mpl + plotly | paired x (one x per series) | each series drawn against its own x column | TC-GE06-EP-002 |
| render(plan) mpl + plotly | direction column with NA cells | NA rows dropped, one segment per direction, same rows | TC-GE06-EP-003 |
| render(plan) mpl + plotly | duplicate legend labels | one legend entry / one showlegend trace; colours by position | TC-GE06-EP-004 |
| render(plan) mpl + plotly | duplicate column labels (default selection) | both columns drawn with their own data | TC-GE06-EP-005 |
| render(plan) mpl + plotly | several frames | frame-major series, both backends | TC-GE06-EP-006 |
| render(plan) mpl + plotly | individual figure | only that series drawn | TC-GE06-EP-007 |
| plan_from_config | short direction list | padded with None; both backends equal | TC-GE06-EP-008 |
| plan_from_config | legacy label functions (C-12) | mpl humanized, plotly not; one label per series each | TC-GE06-EP-009 |
| spec API | label_style humanized | identical labels for both backends | TC-GE06-EP-010 |
| render_overlay / render_html | legacy adapters | draw exactly the plan_from_config plan | TC-GE06-EP-011 |
| render_individual x N | one legacy call | plan built once; a mutated config rebuilds it; no reuse outside a call | TC-GE06-EP-012 |
| renderers | data access | rows come only from PlotData.segments; columns addressed by plan position | TC-GE06-EP-013 |
| renderers | deleted resolution helpers | no competing column/label/direction resolution left | TC-GE06-EP-014 |
| plot_from_dataframe | duplicate column labels, default selection (IC-11) | overlay + one figure per column written | TC-GE06-EP-015 |
| render_html | short direction_cols (IC-11) | padded, no ValueError | TC-GE06-EP-016 |
| render_graph | artifact labels | equal to the drawn legend labels | TC-GE06-EP-017 |

Negative table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| build_plot_plan | unknown label / position out of range / ambiguous label | PlotRequestError(unknown_column / ambiguous_column), no figure | TC-GE06-NEG-001 |
| render_overlay / render_individual / render_html | unknown y column in config | PlotRequestError before a figure exists | TC-GE06-NEG-002 |
| plan_from_config | x/y count mismatch | ValueError "must be equal", no figure | TC-GE06-NEG-003 |
| plan_from_config | direction list longer than y | ValueError "cannot exceed", no figure | TC-GE06-NEG-004 |
| plan_from_config | x_col or y_cols None | ValueError "must be specified", no figure | TC-GE06-NEG-005 |
| plot_from_dataframe | ambiguous label addressed by name | PlotRequestError(ambiguous_column), nothing written | TC-GE06-NEG-006 |
| plot_from_dataframe | unknown y name / out-of-range position | ColumnNotFoundError (legacy type), nothing written | TC-GE06-NEG-007 |
| render_individual | y column not a planned series / position out of range | drawn as v1 (column vs the x of the position), one figure | TC-GE06-NEG-008 |
| render(plan) mpl + plotly | direction filter removes every row | no line, no trace, no legend entry, series not in legend | TC-GE06-NEG-009 |
| plot_from_dataframe | direction list longer than y | ValueError "cannot exceed", nothing written | TC-GE06-NEG-010 |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| plan_from_config | one x for N y / N x for N y | broadcast / paired | TC-GE06-BV-001 |
| render(plan) | 11 series (palette wraps at 10) | colour index wraps identically in both backends | TC-GE06-BV-002 |
| render(plan) | first series of a duplicate label draws nothing | the next series with that label owns the legend entry | TC-GE06-BV-003 |
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import pytest
from matplotlib.colors import to_hex

from rdetoolkit.graph import compat, engine
from rdetoolkit.graph.api.csv2graph import plot_from_dataframe
from rdetoolkit.graph.exceptions import ColumnNotFoundError, PlotRequestError
from rdetoolkit.graph.models import AxisConfig, DirectionConfig, LegendConfig, OutputConfig, PlotConfig, PlotMode
from rdetoolkit.graph.plan import PlotData, PlotPlan, build_plot_plan
from rdetoolkit.graph.renderers import matplotlib_renderer as mr
from rdetoolkit.graph.renderers import plotly_renderer as pr
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer
from rdetoolkit.graph.renderers.plotly_renderer import DEFAULT_PLOTLY_COLORS, PlotlyRenderer
from rdetoolkit.graph.spec import GraphSpec, LegendSpec, SeriesSpec

pytest.importorskip("plotly")

# The legacy legend policy hides a single-entry legend; "inside" always draws it.
_SHOWN = LegendSpec(policy="inside")
_TAB10 = [to_hex(color) for color in plt.cm.tab10.colors]  # type: ignore[attr-defined]


# --- helpers -------------------------------------------------------------------------


def _values(values: Any) -> list[Any]:
    return [value.item() if hasattr(value, "item") else value for value in list(values)]


def _mpl_lines(fig: Any) -> list[tuple[list[Any], list[Any], str]]:
    """(x, y, colour) of every drawn line, in drawing order."""
    ax = fig.axes[0]
    return [(_values(line.get_xdata()), _values(line.get_ydata()), to_hex(line.get_color())) for line in ax.lines]


def _mpl_legend(fig: Any) -> list[str]:
    legend = fig.axes[0].get_legend()
    return [] if legend is None else [text.get_text() for text in legend.get_texts()]


def _plotly_traces(fig: Any) -> list[tuple[list[Any], list[Any], str]]:
    return [(_values(trace.x), _values(trace.y), to_hex(trace.line.color)) for trace in fig.data]


def _plotly_legend(fig: Any) -> list[str]:
    return [trace.name for trace in fig.data if trace.showlegend is not False]


def _expected_segments(plan: PlotPlan, data: PlotData, figure_index: int = 0) -> list[tuple[list[Any], list[Any]]]:
    figure = plan.figures[figure_index]
    by_id = {entry.series_id: entry for entry in plan.series}
    rows: list[tuple[list[Any], list[Any]]] = []
    for series_id in figure.series_ids:
        rows.extend((_values(x), _values(y)) for _, x, y in data.segments(by_id[series_id]))
    return rows


def _both(plan: PlotPlan, data: PlotData, figure_index: int = 0) -> tuple[Any, Any]:
    figure = plan.figures[figure_index]
    return MatplotlibRenderer().render(plan, figure, data), PlotlyRenderer().render(plan, figure, data)


def _legacy_config(**overrides: Any) -> PlotConfig:
    config = PlotConfig(
        mode=PlotMode.OVERLAY,
        x_col=0,
        y_cols=[1],
        x_axis=AxisConfig(label="time"),
        y_axis=AxisConfig(label="value"),
        legend=LegendConfig(),
        direction=DirectionConfig(),
        output=OutputConfig(),
    )
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def _two_series() -> pd.DataFrame:
    return pd.DataFrame({"t (s)": [0, 1, 2], "volt_a (V)": [1.0, 2.0, 3.0], "volt_b (V)": [3.0, 2.0, 1.0]})


# --- EP: cross-backend parity --------------------------------------------------------


def test_single_x_two_series_parity__tc_ge06_ep_001() -> None:
    # Given: one x column and two y series planned once
    frame = _two_series()
    plan = build_plot_plan(frame, GraphSpec(layout="overlay"))
    data = PlotData(frames=(frame,))
    # When: both backends render the overlay figure
    mpl_fig, plotly_fig = _both(plan, data)
    # Then: lines == traces == plan series (count, data, labels, position colours)
    expected = _expected_segments(plan, data)
    assert [(x, y) for x, y, _ in _mpl_lines(mpl_fig)] == expected
    assert [(x, y) for x, y, _ in _plotly_traces(plotly_fig)] == expected
    assert _mpl_legend(mpl_fig) == _plotly_legend(plotly_fig) == [entry.label for entry in plan.series] == ["Volt A", "Volt B"]
    assert [color for *_, color in _mpl_lines(mpl_fig)] == _TAB10[:2]
    assert [color for *_, color in _plotly_traces(plotly_fig)] == [c.lower() for c in DEFAULT_PLOTLY_COLORS[:2]]
    assert _TAB10[:2] == [c.lower() for c in DEFAULT_PLOTLY_COLORS[:2]]


def test_paired_x_parity__tc_ge06_ep_002() -> None:
    # Given: every y has its own x column
    frame = pd.DataFrame({"xa": [0, 1, 2], "ya": [5, 6, 7], "xb": [10, 20, 30], "yb": [1, 2, 3]})
    spec = GraphSpec(layout="overlay", series=(SeriesSpec(y="ya", x="xa"), SeriesSpec(y=3, x=2)))
    plan = build_plot_plan(frame, spec)
    data = PlotData(frames=(frame,))
    # When
    mpl_fig, plotly_fig = _both(plan, data)
    # Then: each series is drawn against its own x column in both backends
    expected = [([0, 1, 2], [5, 6, 7]), ([10, 20, 30], [1, 2, 3])]
    assert [(x, y) for x, y, _ in _mpl_lines(mpl_fig)] == expected
    assert [(x, y) for x, y, _ in _plotly_traces(plotly_fig)] == expected
    assert [(entry.x_index, entry.y_index) for entry in plan.series] == [(0, 1), (2, 3)]


def test_direction_with_missing_cells_parity__tc_ge06_ep_003() -> None:
    # Given: a direction column with NA cells and a custom colour for one direction
    frame = pd.DataFrame({
        "t": [0, 1, 2, 3, 4, 5],
        "v": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        "dir": ["Charge", None, "Discharge", "Charge", float("nan"), "Discharge"],
    })
    spec = GraphSpec(layout="overlay", legend=_SHOWN, series=(SeriesSpec(y=1, direction=2),), direction_colors={"Charge": "#ff0000"})
    plan = build_plot_plan(frame, spec)
    data = PlotData(frames=(frame,))
    # When
    mpl_fig, plotly_fig = _both(plan, data)
    # Then: NA rows are dropped and each direction is one segment in both backends
    expected = [([0, 3], [1.0, 4.0]), ([2, 5], [3.0, 6.0])]
    assert plan.series[0].directions == ("Charge", "Discharge")
    assert [(x, y) for x, y, _ in _mpl_lines(mpl_fig)] == expected
    assert [(x, y) for x, y, _ in _plotly_traces(plotly_fig)] == expected
    # Then: the custom colour wins, the uncoloured direction keeps the series colour
    assert [color for *_, color in _mpl_lines(mpl_fig)] == ["#ff0000", _TAB10[0]]
    assert [color for *_, color in _plotly_traces(plotly_fig)] == ["#ff0000", _TAB10[0]]
    # Then: one legend entry for the series, owned by its first segment
    assert _mpl_legend(mpl_fig) == _plotly_legend(plotly_fig) == ["V"]


def test_duplicate_legend_labels_parity__tc_ge06_ep_004() -> None:
    # Given: two series with the same explicit label
    frame = _two_series()
    spec = GraphSpec(layout="overlay", legend=_SHOWN, series=(SeriesSpec(y=1, label="cell"), SeriesSpec(y=2, label="cell")))
    plan = build_plot_plan(frame, spec)
    # When
    mpl_fig, plotly_fig = _both(plan, PlotData(frames=(frame,)))
    # Then: both are drawn, listed once, coloured by position in both backends
    assert [entry.show_in_legend for entry in plan.series] == [True, False]
    assert len(_mpl_lines(mpl_fig)) == len(_plotly_traces(plotly_fig)) == 2
    assert _mpl_legend(mpl_fig) == _plotly_legend(plotly_fig) == ["cell"]
    assert [c for *_, c in _mpl_lines(mpl_fig)] == [c for *_, c in _plotly_traces(plotly_fig)] == _TAB10[:2]
    assert [trace.name for trace in plotly_fig.data] == ["cell", "cell"]


def test_duplicate_column_labels_parity__tc_ge06_ep_005() -> None:
    # Given: two columns carrying the same header, selected by default
    frame = pd.DataFrame([[0, 1, 10], [1, 2, 20]], columns=["x", "y", "y"])
    plan = build_plot_plan(frame, GraphSpec(layout="overlay", legend=_SHOWN))
    # When
    mpl_fig, plotly_fig = _both(plan, PlotData(frames=(frame,)))
    # Then: both columns are drawn with their own data
    expected = [([0, 1], [1, 2]), ([0, 1], [10, 20])]
    assert [(x, y) for x, y, _ in _mpl_lines(mpl_fig)] == expected
    assert [(x, y) for x, y, _ in _plotly_traces(plotly_fig)] == expected
    assert _mpl_legend(mpl_fig) == _plotly_legend(plotly_fig) == ["Y"]


def test_several_frames_parity__tc_ge06_ep_006() -> None:
    # Given: two frames with the same layout
    first = pd.DataFrame({"t": [0, 1], "a": [1, 2]})
    second = pd.DataFrame({"t": [5, 6], "a": [7, 8]})
    plan = build_plot_plan([first, second], GraphSpec(layout="overlay"))
    # When
    mpl_fig, plotly_fig = _both(plan, PlotData(frames=(first, second)))
    # Then: frame-major series, identical in both backends
    expected = [([0, 1], [1, 2]), ([5, 6], [7, 8])]
    assert [entry.frame for entry in plan.series] == [0, 1]
    assert [(x, y) for x, y, _ in _mpl_lines(mpl_fig)] == expected
    assert [(x, y) for x, y, _ in _plotly_traces(plotly_fig)] == expected


def test_individual_figure_parity__tc_ge06_ep_007() -> None:
    # Given: a plan with individual figures
    frame = _two_series()
    plan = build_plot_plan(frame, GraphSpec(layout="individual"))
    data = PlotData(frames=(frame,))
    # When: the second individual figure is rendered by both backends
    mpl_fig, plotly_fig = _both(plan, data, figure_index=1)
    # Then: only that series is drawn
    expected = [([0, 1, 2], [3.0, 2.0, 1.0])]
    assert [(x, y) for x, y, _ in _mpl_lines(mpl_fig)] == expected
    assert [(x, y) for x, y, _ in _plotly_traces(plotly_fig)] == expected
    assert [trace.name for trace in plotly_fig.data] == ["Volt B"]
    assert mpl_fig.axes[0].get_title() == plan.figures[1].title == "Plot - Volt B"


def test_short_direction_list_is_padded__tc_ge06_ep_008() -> None:
    # Given: a legacy config with one direction column for two y columns
    frame = pd.DataFrame({"t": [0, 1, 2], "a": [1, 2, 3], "d": ["A", "B", "A"], "b": [4, 5, 6]})
    config = _legacy_config(y_cols=[1, 3], direction_cols=[2])
    # When
    plan = compat.plan_from_config(frame, config, label_of=compat.legacy_mpl_label)
    mpl_fig, plotly_fig = _both(plan, PlotData(frames=(frame,)))
    # Then: the second series has no direction column; both backends agree
    assert [entry.direction_index for entry in plan.series] == [2, None]
    expected = [([0, 2], [1, 3]), ([1], [2]), ([0, 1, 2], [4, 5, 6])]
    assert [(x, y) for x, y, _ in _mpl_lines(mpl_fig)] == expected
    assert [(x, y) for x, y, _ in _plotly_traces(plotly_fig)] == expected


@pytest.mark.parametrize(
    ("header", "humanize", "mpl_label", "plotly_label"),
    [
        ("value", False, "Value", "value"),
        ("total:intensity", False, "Total", "total"),
        ("series_0", False, "Series 0", "series_0"),
        ("series_one: current (mA)", True, "Series One", "Series One"),
        ("raw_name", True, "Raw Name", "Raw Name"),
        ("Value", True, "Value", "Value"),
    ],
)
def test_legacy_labels_stay_backend_specific__tc_ge06_ep_009(
    header: str, humanize: bool, mpl_label: str, plotly_label: str,
) -> None:
    # Given: a legacy config (C-12: the two legacy paths are pinned to different labels)
    frame = pd.DataFrame({"t": [0, 1], header: [1, 2]})
    config = _legacy_config(humanize=humanize)
    # When: each legacy adapter builds its plan
    mpl_plan = compat.plan_from_config(frame, config, label_of=compat.legacy_mpl_label)
    plotly_plan = compat.plan_from_config(frame, config, label_of=compat.legacy_plotly_label)
    # Then: one final label per series, per legacy rule; label origins stay "derived"
    assert [entry.label for entry in mpl_plan.series] == [mpl_label]
    assert [entry.label for entry in plotly_plan.series] == [plotly_label]
    assert mpl_plan.origins["series[s000].label"] == "derived"
    # Then: the legacy adapters draw exactly those labels
    assert _mpl_legend(MatplotlibRenderer().render_overlay(frame, _legacy_config(humanize=humanize, legend=LegendConfig(loc="best")))) == [mpl_label]
    assert [trace.name for trace in PlotlyRenderer().render_html(frame, config).data] == [plotly_label]


def test_spec_api_labels_equal_across_backends__tc_ge06_ep_010() -> None:
    # Given: headers that the two legacy rules label differently
    frame = pd.DataFrame({"t": [0, 1], "total:intensity": [1, 2], "series_0": [3, 4]})
    plan = build_plot_plan(frame, GraphSpec(layout="overlay"))
    # When
    mpl_fig, plotly_fig = _both(plan, PlotData(frames=(frame,)))
    # Then: one label rule for every backend
    assert _mpl_legend(mpl_fig) == _plotly_legend(plotly_fig) == ["Total", "Series 0"]


def test_legacy_adapters_draw_the_compat_plan__tc_ge06_ep_011() -> None:
    # Given: a legacy config with paired x, directions, a filter and custom colours
    frame = pd.DataFrame({
        "xa": [0, 1, 2, 3], "ya": [1, 2, 3, 4], "d": ["A", "B", "A", "B"], "xb": [9, 8, 7, 6], "yb": [4, 3, 2, 1],
    })
    direction = DirectionConfig(filters=[None, "A", "A"], use_custom_colors=True)  # type: ignore[list-item]
    direction.colors.update({"A": "#00ff00"})
    config = _legacy_config(x_col=[0, 3], y_cols=[1, 4], direction_cols=[2, None], direction=direction)
    data = PlotData(frames=(frame,))
    # When: the legacy adapters render, and the plan is rendered directly
    mpl_plan = compat.plan_from_config(frame, config, label_of=compat.legacy_mpl_label)
    # Then: None filter entries are dropped and duplicates collapse
    assert mpl_plan.series[0].directions == ("A",)
    plotly_plan = compat.plan_from_config(
        frame, config, label_of=compat.legacy_plotly_label, axis_label_of=compat.legacy_plotly_axis_label,
    )
    legacy_mpl = MatplotlibRenderer().render_overlay(frame, config)
    legacy_plotly = PlotlyRenderer().render_html(frame, config)
    # Then: the adapters draw exactly the plan
    assert _mpl_lines(legacy_mpl) == _mpl_lines(MatplotlibRenderer().render(mpl_plan, mpl_plan.figures[0], data))
    assert _plotly_traces(legacy_plotly) == _plotly_traces(PlotlyRenderer().render(plotly_plan, plotly_plan.figures[0], data))
    assert _mpl_lines(legacy_mpl) == [([0, 2], [1, 3], "#00ff00"), ([9, 8, 7, 6], [4, 3, 2, 1], _TAB10[1])]
    assert _plotly_traces(legacy_plotly) == _mpl_lines(legacy_mpl)
    assert legacy_mpl.axes[0].get_xlabel() == mpl_plan.figures[0].x_label == "time"
    assert legacy_plotly.layout.xaxis.title.text == plotly_plan.figures[0].x_label == "time"


def test_render_individual_builds_the_plan_once__tc_ge06_ep_012(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a counting plan builder seen by the renderer
    calls: list[int] = []
    original = compat.plan_from_config

    def counting(*args: Any, **kwargs: Any) -> PlotPlan:
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(compat, "plan_from_config", counting)
    frame = _two_series()
    config = _legacy_config(y_cols=[1, 2])
    renderer = MatplotlibRenderer()
    # When: one overlay and two individual figures are rendered in one legacy call
    with compat.legacy_call():
        figures = [renderer.render_overlay(frame, config)]
        figures += [renderer.render_individual(frame, config, column, position) for position, column in enumerate([1, 2])]
    # Then: the plan was built once and every figure follows it
    assert len(calls) == 1
    assert [_mpl_lines(fig)[0][1] for fig in figures[1:]] == [[1.0, 2.0, 3.0], [3.0, 2.0, 1.0]]
    # When: the config is mutated in place
    config.title = "changed"
    figure = renderer.render_individual(frame, config, 2, 1)
    # Then: the plan is rebuilt and reflects the change
    assert len(calls) == 2
    assert figure.axes[0].get_title() == "changed - Volt B"
    # And: outside a legacy call no plan is reused (fix round 1, R-5), even unchanged
    renderer.render_individual(frame, config, 2, 1)
    assert len(calls) == 3


def test_renderers_read_rows_only_through_plan_positions__tc_ge06_ep_013(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a plan built on one frame, rendered on data whose headers were renamed
    frame = _two_series()
    plan = build_plot_plan(frame, GraphSpec(layout="overlay"))
    renamed = frame.set_axis(["a", "b", "c"], axis=1)
    seen: list[str] = []
    original = PlotData.segments

    def spy(self: PlotData, series: Any) -> Any:
        seen.append(series.series_id)
        return original(self, series)

    monkeypatch.setattr(PlotData, "segments", spy)
    # When
    mpl_fig, plotly_fig = _both(plan, PlotData(frames=(renamed,)))
    # Then: rows come from the plan's positions and labels from the plan, not the headers
    assert seen == ["s000", "s001", "s000", "s001"]
    assert [y for _, y, _ in _mpl_lines(mpl_fig)] == [[1.0, 2.0, 3.0], [3.0, 2.0, 1.0]]
    assert _mpl_legend(mpl_fig) == _plotly_legend(plotly_fig) == ["Volt A", "Volt B"]


def test_no_competing_column_resolution_left__tc_ge06_ep_014() -> None:
    # Given/When: the renderer modules after GE-06
    # Then: the duplicated resolution helpers are gone (C-18)
    for name in ("_resolve_overlay_columns", "_resolve_x_column_index", "_resolve_direction_column_index", "_build_series_label"):
        assert not hasattr(MatplotlibRenderer, name), name
    for name in ("_resolve_column_index", "_resolve_column_indices"):
        assert not hasattr(mr, name), name
    for name in ("_validate_plot_columns", "_resolve_series_name", "_prepare_direction_filters"):
        assert not hasattr(PlotlyRenderer, name), name
    assert not hasattr(pr, "_PlotlyColorContext")
    assert not hasattr(engine, "_PlanRenderer")
    assert not hasattr(engine, "_plan_to_legacy_config")


def test_plot_from_dataframe_plots_duplicate_column_labels_v2_0__tc_ge06_ep_015(tmp_path: Path) -> None:
    # Given: two y columns sharing one header (v1: "resolved to a slice")
    frame = pd.DataFrame([[0, 1, 10], [1, 2, 20]], columns=["x", "y", "y"])
    out = tmp_path / "out"
    # When: plotting with the default selection
    figures = plot_from_dataframe(frame, out, name="dup", return_fig=True)
    # Then: overlay + one individual figure per column, each with its own data
    assert figures is not None
    assert [artifact.filename for artifact in figures] == ["dup.png", "dup_y_s000.png", "dup_y_s001.png"]
    assert [line[1] for line in _mpl_lines(figures[0].figure)] == [[1, 2], [10, 20]]
    assert [_mpl_lines(artifact.figure)[0][1] for artifact in figures[1:]] == [[1, 2], [10, 20]]


def test_render_html_pads_short_direction_list_v2_0__tc_ge06_ep_016() -> None:
    # Given: one direction column for two y columns (v1 Plotly: ValueError)
    frame = pd.DataFrame({"t": [0, 1], "a": [1, 2], "d": ["A", "A"], "b": [3, 4]})
    config = _legacy_config(y_cols=[1, 3], direction_cols=[2])
    # When
    fig = PlotlyRenderer().render_html(frame, config)
    # Then: the second series is drawn without directions
    assert [(x, y) for x, y, _ in _plotly_traces(fig)] == [([0, 1], [1, 2]), ([0, 1], [3, 4])]


def test_render_graph_artifact_labels_match_the_drawing__tc_ge06_ep_017() -> None:
    # Given/When: an in-memory render through the engine
    result = engine.render_graph(_two_series(), GraphSpec(layout="overlay"))
    # Then: the artifact labels are the labels drawn from the plan
    artifact = result.artifacts[0]
    assert list(artifact.labels) == _mpl_legend(artifact.figure) == ["Volt A", "Volt B"]


# --- negative ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("spec", "reason"),
    [
        (GraphSpec(series=(SeriesSpec(y="missing"),)), "unknown_column"),
        (GraphSpec(series=(SeriesSpec(y=9),)), "unknown_column"),
        (GraphSpec(series=(SeriesSpec(y=1, direction="nope"),)), "unknown_column"),
        (GraphSpec(series=(SeriesSpec(y="y"),)), "ambiguous_column"),
    ],
)
def test_invalid_selection_fails_at_plan_creation__tc_ge06_neg_001(spec: GraphSpec, reason: str) -> None:
    # Given: a frame with a duplicated header
    frame = pd.DataFrame([[0, 1, 2]], columns=["x", "y", "y"])
    before = set(plt.get_fignums())
    # When/Then: the plan rejects the selection; no figure was created
    with pytest.raises(PlotRequestError) as excinfo:
        build_plot_plan(frame, spec)
    assert excinfo.value.reason == reason
    assert isinstance(excinfo.value, ValueError)
    assert set(plt.get_fignums()) == before


@pytest.mark.parametrize("call", ["overlay", "individual", "html"])
def test_legacy_adapters_reject_unknown_columns_before_drawing__tc_ge06_neg_002(call: str) -> None:
    # Given: a config naming a column the frame does not have
    frame = _two_series()
    config = _legacy_config(y_cols=["missing"])
    before = set(plt.get_fignums())
    # When/Then
    with pytest.raises(PlotRequestError) as excinfo:
        if call == "overlay":
            MatplotlibRenderer().render_overlay(frame, config)
        elif call == "individual":
            MatplotlibRenderer().render_individual(frame, config, 1, 0)
        else:
            PlotlyRenderer().render_html(frame, config)
    assert excinfo.value.reason == "unknown_column"
    assert set(plt.get_fignums()) == before


@pytest.mark.parametrize("label_of", [compat.legacy_mpl_label, compat.legacy_plotly_label])
def test_plan_from_config_rejects_count_mismatch__tc_ge06_neg_003(label_of: Any) -> None:
    # Given: two x columns for one y column
    frame = pd.DataFrame({"x1": [0, 1], "x2": [2, 3], "y": [4, 5]})
    config = _legacy_config(x_col=[0, 1], y_cols=[2])
    before = set(plt.get_fignums())
    # When/Then
    with pytest.raises(ValueError, match="must be equal"):
        compat.plan_from_config(frame, config, label_of=label_of)
    with pytest.raises(ValueError, match="must be equal"):
        MatplotlibRenderer().render_overlay(frame, config)
    assert set(plt.get_fignums()) == before


def test_plan_from_config_rejects_too_many_directions__tc_ge06_neg_004() -> None:
    # Given: two direction columns for one y column
    frame = pd.DataFrame({"t": [0, 1], "y": [1, 2], "d": ["A", "B"], "e": ["C", "D"]})
    config = _legacy_config(y_cols=[1], direction_cols=[2, 3])
    before = set(plt.get_fignums())
    # When/Then: the same error for both legacy adapters (the split of v1 is gone)
    with pytest.raises(ValueError, match="cannot exceed"):
        MatplotlibRenderer().render_overlay(frame, config)
    with pytest.raises(ValueError, match="cannot exceed"):
        PlotlyRenderer().render_html(frame, config)
    assert set(plt.get_fignums()) == before


@pytest.mark.parametrize("overrides", [{"x_col": None}, {"y_cols": None}])
def test_plan_from_config_requires_columns__tc_ge06_neg_005(overrides: dict[str, Any]) -> None:
    # Given: a config without x or y columns
    config = _legacy_config(**overrides)
    before = set(plt.get_fignums())
    # When/Then
    with pytest.raises(ValueError, match="must be specified"):
        compat.plan_from_config(_two_series(), config, label_of=compat.legacy_mpl_label)
    with pytest.raises(ValueError, match="must be specified"):
        PlotlyRenderer().render_html(_two_series(), config)
    assert set(plt.get_fignums()) == before


def test_plot_from_dataframe_rejects_ambiguous_name__tc_ge06_neg_006(tmp_path: Path) -> None:
    # Given: a duplicated header addressed by name
    frame = pd.DataFrame([[0, 1, 2]], columns=["x", "y", "y"])
    out = tmp_path / "out"
    # When/Then
    with pytest.raises(PlotRequestError) as excinfo:
        plot_from_dataframe(frame, out, y_cols="y")
    assert excinfo.value.reason == "ambiguous_column"
    assert not out.exists()


@pytest.mark.parametrize("selection", [{"y_cols": "missing"}, {"y_cols": [5]}, {"x_col": "nope"}, {"direction_cols": "nope"}])
def test_plot_from_dataframe_unknown_column_keeps_legacy_type__tc_ge06_neg_007(tmp_path: Path, selection: dict[str, Any]) -> None:
    # Given: an unknown column reference
    out = tmp_path / "out"
    before = set(plt.get_fignums())
    # When/Then: the legacy error type is kept and nothing is written
    with pytest.raises(ColumnNotFoundError):
        plot_from_dataframe(_two_series(), out, **selection)
    assert not out.exists()
    assert set(plt.get_fignums()) == before


@pytest.mark.parametrize(("column", "position"), [(1, 1), (0, None), (1, 5)])
def test_render_individual_draws_unplanned_series_as_v1__tc_ge06_neg_008(column: int, position: int | None) -> None:
    # Given: y column / position pairs that name no planned series (fix round 1, R-4:
    # v1 drew any column against the x column of the position, the first x beyond it)
    config = _legacy_config(y_cols=[1, 2])
    frame = _two_series()
    before = set(plt.get_fignums())
    # When
    fig = MatplotlibRenderer().render_individual(frame, config, column, position)
    # Then: exactly one new caller-owned figure with that column against column 0
    assert set(plt.get_fignums()) == before | {fig.number}
    (line,) = fig.axes[0].lines
    assert list(line.get_xdata()) == list(frame.iloc[:, 0])
    assert list(line.get_ydata()) == list(frame.iloc[:, column])
    assert fig.axes[0].get_ylabel() == "value"


def test_filter_removing_every_row_draws_nothing__tc_ge06_neg_009() -> None:
    # Given: a direction filter that matches no row
    frame = pd.DataFrame({"t": [0, 1], "v": [1, 2], "d": ["A", "B"]})
    spec = GraphSpec(layout="overlay", series=(SeriesSpec(y=1, direction=2),), direction_filter=("Z",))
    plan = build_plot_plan(frame, spec)
    # When
    mpl_fig, plotly_fig = _both(plan, PlotData(frames=(frame,)))
    # Then: nothing drawn, no legend entry, the series has no legend role
    assert plan.series[0].directions == ()
    assert plan.series[0].show_in_legend is False
    assert _mpl_lines(mpl_fig) == _plotly_traces(plotly_fig) == []
    assert _mpl_legend(mpl_fig) == _plotly_legend(plotly_fig) == []


def test_plot_from_dataframe_rejects_too_many_directions__tc_ge06_neg_010(tmp_path: Path) -> None:
    # Given: more direction columns than y columns
    frame = pd.DataFrame({"t": [0, 1], "y": [1, 2], "d": ["A", "B"]})
    out = tmp_path / "out"
    # When/Then
    with pytest.raises(ValueError, match="cannot exceed"):
        plot_from_dataframe(frame, out, y_cols=[1], direction_cols=[2, 2])
    assert not out.exists()


# --- boundary ------------------------------------------------------------------------


@pytest.mark.parametrize(("x_col", "expected"), [(0, [(0, 1), (0, 2)]), ([0, 0], [(0, 1), (0, 2)]), ([2, 1], [(2, 1), (1, 2)])])
def test_plan_from_config_broadcasts_or_pairs_x__tc_ge06_bv_001(x_col: Any, expected: list[tuple[int, int]]) -> None:
    # Given/When
    plan = compat.plan_from_config(_two_series(), _legacy_config(x_col=x_col, y_cols=[1, 2]), label_of=compat.legacy_mpl_label)
    # Then
    assert [(entry.x_index, entry.y_index) for entry in plan.series] == expected


def test_palette_wraps_identically__tc_ge06_bv_002() -> None:
    # Given: eleven series (the ten-colour palette wraps)
    frame = pd.DataFrame({"t": [0, 1], **{f"s{index:02d}": [index, index + 1] for index in range(11)}})
    plan = build_plot_plan(frame, GraphSpec(layout="overlay", legend=dataclasses.replace(GraphSpec().legend, max_items=None)))
    # When
    mpl_fig, plotly_fig = _both(plan, PlotData(frames=(frame,)))
    # Then
    mpl_colours = [c for *_, c in _mpl_lines(mpl_fig)]
    assert mpl_colours == [c for *_, c in _plotly_traces(plotly_fig)]
    assert mpl_colours[10] == mpl_colours[0] == _TAB10[0]


def test_duplicate_label_owner_must_draw__tc_ge06_bv_003() -> None:
    # Given: the first series of a duplicated label is filtered away entirely
    frame = pd.DataFrame({"t": [0, 1], "a": [1, 2], "d": ["B", "B"], "b": [3, 4]})
    spec = GraphSpec(
        layout="overlay",
        legend=_SHOWN,
        series=(SeriesSpec(y=1, direction=2, label="cell"), SeriesSpec(y=3, label="cell")),
        direction_filter=("A",),
    )
    plan = build_plot_plan(frame, spec)
    # When
    mpl_fig, plotly_fig = _both(plan, PlotData(frames=(frame,)))
    # Then: the series that draws owns the legend entry in both backends
    assert [entry.show_in_legend for entry in plan.series] == [False, True]
    assert _mpl_legend(mpl_fig) == _plotly_legend(plotly_fig) == ["cell"]
    # Then: relabelling keeps the rule
    assert [entry.show_in_legend for entry in plan.with_labels(["same", "same"]).series] == [False, True]
