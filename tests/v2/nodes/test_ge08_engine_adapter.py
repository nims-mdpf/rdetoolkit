"""GE-08 (#714): the builtin plot nodes are thin adapters over the Graph Engine.

``plot_lines`` and ``plot_scatter`` resolve columns, pairs, frames and series labels
through ``build_plot_plan`` and draw through ``mpl_runtime.draw_series``; axis limits
go through ``validate_axis_limits``. ``save_figure`` stays the caller-owned escape
hatch. Node figures stay pyplot-managed (``plt.subplots`` + ``plt.close``) because
existing node contracts observe ``figure.number``; the node applies none of the
csv2graph house style (``plan.style`` is not applied).

Parity scope (orchestrator ruling 2): the node and ``render_graph`` /
``build_plot_plan`` with ``label_style="raw"`` agree on series order, series labels,
plotted data and, for a single y series, the axis labels. With several y series the
node's default y label still joins the distinct y names (node presentation rule),
while the plan's overlay label names the first series only; that difference is
intended and not asserted as parity.

| API | Partition / boundary | Expected | Test ID |
|-----|----------------------|----------|---------|
| plot_lines vs render_graph | same frame, x + several y | same series order, labels, x/y data | GE08-EP-1 |
| plot_lines vs build_plot_plan | default selection against the index | same series order, labels, data | GE08-EP-2 |
| plot_lines vs render_graph | single y | same x / y axis labels | GE08-EP-3 |
| plot_scatter vs render_graph | mark="scatter" | same offsets and axis labels | GE08-EP-4 |
| plot_lines | several frames, pairs / labels= / default | labels in frame-major order | GE08-EP-5 |
| plot_lines | kind= other_image / thumbnail | exactly one artifact, only under that kind | GE08-EP-6 |
| save_figure | caller-owned figure | not closed, not restyled, same artists | GE08-EP-7 |
| plot_lines / plot_scatter | same request as the pre-GE-08 code path | byte-identical PNG | GE08-EP-8 |
| node registry | plot node specs | ids, tags, version, idempotent, inputs unchanged | GE08-EP-9 |
| call log | flow using plot_lines + plot_scatter | two records, same ids / inputs / outputs | GE08-EP-10 |
| plot_lines | repeated call | same path and bytes (idempotent) | GE08-EP-11 |
| plot_lines | engine shared | build_plot_plan once, draw_series once per series | GE08-EP-12 |
| plot_lines | house style | rcParams unchanged, figure size = rcParams default | GE08-EP-13 |
| plot_lines | y columns with different units (V, A), as before GE-11 | drawn on one axis, no unit_mismatch | GE08-BV-4 |
| plot_lines | reversed limits | axis inverted | GE08-BV-1 |
| plot_lines | log axis, (None, None) / tiny positive bound | accepted | GE08-BV-2 |
| plot_lines | xscale="symlog", negative bound | accepted (only "log" is checked as log) | GE08-BV-3 |
| plot_lines | unknown x / y / pair column | PlotRequestError unknown_column, nothing written | GE08-NEG-1 |
| plot_scatter | unknown x / y | PlotRequestError unknown_column, nothing written | GE08-NEG-2 |
| plot_lines | log axis with a bound <= 0 | PlotRequestError invalid_axis_limits, no figure | GE08-NEG-3 |
| plot_lines | equal / non-finite / non-numeric bound | PlotRequestError invalid_axis_limits | GE08-NEG-4 |
| plot_lines | pairs=[] / y=[] | ValueError, never "plot every column" | GE08-NEG-5 |
| plot_lines | a frame contributing no series | ValueError, nothing written | GE08-NEG-6 |
| plot_lines | duplicated column addressed by name | PlotRequestError ambiguous_column | GE08-NEG-7 |
| plot_lines | x column missing in the second frame only | PlotRequestError unknown_column, nothing written | GE08-NEG-8 |
| plot_lines | labelled pairs + labels= | ValueError "not both" | GE08-NEG-9 |
| save_figure | unsafe filename | error, caller figure still open | GE08-NEG-10 |
| source | nodes/plot.py | no private column/label resolver left | GE08-NEG-11 |
"""

from __future__ import annotations

import inspect
from io import BytesIO
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from matplotlib.axes import Axes

import rdetoolkit.nodes.plot as plot_module
from rdetoolkit.core.calllog import CallLogRecorder
from rdetoolkit.core.flow import flow
from rdetoolkit.graph import GraphSpec, PlotRequestError, SeriesSpec, build_plot_plan, render_graph
from rdetoolkit.nodes import plot_lines, plot_scatter, save_figure
from rdetoolkit.testing import make_output_context
from rdetoolkit.types import OutputContext


def _record_axes(monkeypatch: pytest.MonkeyPatch) -> list[Axes]:
    observed: list[Axes] = []
    for name in ("plot", "scatter"):
        original = getattr(Axes, name)

        def record(axes: Axes, *args: Any, _original: Any = original, **kwargs: Any) -> Any:
            if not observed or observed[-1] is not axes:
                observed.append(axes)
            return _original(axes, *args, **kwargs)

        monkeypatch.setattr(Axes, name, record)
    return observed


def _frame() -> pd.DataFrame:
    return pd.DataFrame({"t": [0.0, 1.0, 2.0], "a": [1.0, 3.0, 2.0], "b": [5.0, 4.0, 6.0]})


def _all_outputs(tmp_path: Path) -> list[Path]:
    return sorted(path for path in tmp_path.rglob("*") if path.is_file())


def _xy(line: Any) -> tuple[list[float], list[float]]:
    return [float(value) for value in line.get_xdata()], [float(value) for value in line.get_ydata()]


# --- parity with the engine ---------------------------------------------------------


def test_plot_lines_matches_render_graph_series__ge08_ep_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GE08-EP-1: same frame through the node and render_graph -> same series."""
    # Given: the same frame and selection for both APIs
    frame = _frame()
    result = render_graph(frame, GraphSpec(x="t", series=(SeriesSpec(y="a"), SeriesSpec(y="b")), layout="overlay", label_style="raw"))
    observed = _record_axes(monkeypatch)
    # When: plotting with the node
    plot_lines(frame, make_output_context(tmp_path), "lines.png", x="t", y=["a", "b"])
    # Then: series order, labels and data are identical
    node_lines = observed[-1].lines
    engine_lines = result.artifacts[0].figure.axes[0].lines
    assert [line.get_label() for line in node_lines] == [entry.label for entry in result.plan.series] == ["a", "b"]
    assert [_xy(line) for line in node_lines] == [_xy(line) for line in engine_lines]


def test_plot_lines_default_selection_matches_plan__ge08_ep_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GE08-EP-2: every column against the index, as the raw index plan selects it."""
    # Given: a frame plotted without any selection
    frame = _frame()
    plan = build_plot_plan(frame, GraphSpec(x_default="index", layout="overlay", label_style="raw"))
    observed = _record_axes(monkeypatch)
    # When: plotting with the node
    plot_lines(frame, make_output_context(tmp_path), "lines.png")
    # Then: one line per planned series, same label and same y data, x = index
    lines = observed[-1].lines
    assert [line.get_label() for line in lines] == [entry.label for entry in plan.series] == ["t", "a", "b"]
    assert [_xy(line)[1] for line in lines] == [list(frame.iloc[:, entry.y_index]) for entry in plan.series]
    assert all(_xy(line)[0] == [0.0, 1.0, 2.0] for line in lines)


def test_plot_lines_single_y_axis_labels_match_plan__ge08_ep_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GE08-EP-3: with one y series the default axis labels equal the plan's."""
    # Given: one y series
    frame = _frame()
    plan = build_plot_plan(frame, GraphSpec(x="t", series=(SeriesSpec(y="b"),), layout="overlay", label_style="raw"))
    observed = _record_axes(monkeypatch)
    # When: plotting with the node
    plot_lines(frame, make_output_context(tmp_path), "lines.png", x="t", y="b")
    # Then: x and y labels are those of the overlay figure plan
    axes = observed[-1]
    assert (axes.get_xlabel(), axes.get_ylabel()) == (plan.figures[0].x_label, plan.figures[0].y_label) == ("t", "b")


def test_plot_scatter_matches_render_graph__ge08_ep_4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GE08-EP-4: plot_scatter and a scatter spec draw the same points and labels."""
    # Given: a scatter request through the spec API
    frame = _frame()
    result = render_graph(frame, GraphSpec(x="a", series=(SeriesSpec(y="b"),), mark="scatter", layout="overlay", label_style="raw"))
    observed = _record_axes(monkeypatch)
    # When: plotting with the node
    plot_scatter(frame, make_output_context(tmp_path), "scatter.png", x="a", y="b")
    # Then: same offsets, and labels equal to the figure plan
    node_offsets = observed[-1].collections[0].get_offsets()
    engine_offsets = result.artifacts[0].figure.axes[0].collections[0].get_offsets()
    assert np.array_equal(np.asarray(node_offsets), np.asarray(engine_offsets))
    assert (observed[-1].get_xlabel(), observed[-1].get_ylabel()) == (result.plan.figures[0].x_label, result.plan.figures[0].y_label)


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ({"pairs": [("x", "y", "signal")]}, ["signal", "signal"]),
        ({"x": "x", "y": "y", "labels": ["low", "high"]}, ["low", "high"]),
        ({"x": "x"}, ["y", "z", "y"]),
    ],
    ids=["labelled-pair", "labels", "default"],
)
def test_plot_lines_multi_frame_labels__ge08_ep_5(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, options: dict[str, Any], expected: list[str],
) -> None:
    """GE08-EP-5: labels follow frame-major order across several frames."""
    # Given: two frames, the first with an extra column
    frames = [pd.DataFrame({"x": [1, 2], "y": [3, 4], "z": [5, 6]}), pd.DataFrame({"x": [7, 8, 9], "y": [1, 2, 3]})]
    if "pairs" in options or "labels" in options:
        frames = [frame[["x", "y"]] for frame in frames]
    observed = _record_axes(monkeypatch)
    # When: plotting both frames in one image
    plot_lines(frames, make_output_context(tmp_path), "frames.png", **options)
    # Then: the series carry the expected labels in order, and the legend lists them
    axes = observed[-1]
    assert [line.get_label() for line in axes.lines] == expected
    legend = axes.get_legend()
    assert legend is not None
    assert [text.get_text() for text in legend.get_texts()] == expected


@pytest.mark.parametrize("kind", ["other_image", "thumbnail"])
def test_plot_lines_kind_routing__ge08_ep_6(tmp_path: Path, kind: str) -> None:
    """GE08-EP-6: kind= decides the OutputContext directory and nothing else is written."""
    # Given: an output context
    out = make_output_context(tmp_path)
    # When: plotting into a non-default kind
    path = plot_lines(_frame(), out, "lines.png", x="t", kind=kind)  # type: ignore[arg-type]
    # Then: exactly one artifact exists, under that kind
    assert path == getattr(out, kind) / "lines.png"
    assert _all_outputs(tmp_path) == [path]
    assert path.read_bytes().startswith(b"\x89PNG")


def test_save_figure_leaves_caller_figure_untouched__ge08_ep_7(tmp_path: Path) -> None:
    """GE08-EP-7: the caller-owned figure is neither closed nor restyled."""
    # Given: a caller-owned figure with a known state
    figure, axes = plt.subplots(figsize=(3, 2))
    axes.plot([1, 2], [3, 4], label="mine")
    axes.set_title("caller")
    state = (tuple(figure.get_size_inches()), figure.dpi, figure.get_layout_engine(), len(axes.lines), axes.get_title())
    rc_before = dict(mpl.rcParams)
    try:
        # When: saving it twice through the node
        first = save_figure(figure, make_output_context(tmp_path), "fig.png", dpi=50)
        second = save_figure(figure, make_output_context(tmp_path), "fig.png", dpi=50)
        # Then: it is still open and unchanged, and both saves are equal
        assert plt.fignum_exists(figure.number)
        assert (tuple(figure.get_size_inches()), figure.dpi, figure.get_layout_engine(), len(axes.lines), axes.get_title()) == state
        assert dict(mpl.rcParams) == rc_before
        assert first.read_bytes() == second.read_bytes()
    finally:
        plt.close(figure)


def _legacy_lines_png(frame: pd.DataFrame, x: str, ys: list[str]) -> bytes:
    # The pre-GE-08 plot_lines code path, spelled out with plain Matplotlib.
    fig, ax = plt.subplots(figsize=(4, 3))
    try:
        for column in ys:
            ax.plot(frame[x], frame[column], label=column)
        ax.set_xlabel(x)
        ax.set_ylabel(", ".join(ys))
        ax.set(title="", xscale="linear", yscale="linear")
        ax.legend()
        buffer = BytesIO()
        fig.savefig(buffer, format="png", dpi=80, bbox_inches="tight", pad_inches=None)
        return buffer.getvalue()
    finally:
        plt.close(fig)


def _legacy_scatter_png(frame: pd.DataFrame, x: str, y: str) -> bytes:
    fig, ax = plt.subplots()
    try:
        ax.scatter(frame[x], frame[y])
        ax.set_xlabel(x, fontsize=10)
        ax.set_ylabel(y, fontsize=10)
        buffer = BytesIO()
        fig.savefig(buffer, format="png", dpi=150, bbox_inches="tight", pad_inches=None)
        return buffer.getvalue()
    finally:
        plt.close(fig)


def test_node_images_are_byte_identical_to_pre_ge08__ge08_ep_8(tmp_path: Path) -> None:
    """GE08-EP-8: routing through the engine does not change a pixel."""
    # Given: the same frame
    frame = _frame()
    out = make_output_context(tmp_path)
    # When: plotting with the nodes
    lines = plot_lines(frame, out, "lines.png", x="t", y=["a", "b"], figsize=(4, 3), dpi=80)
    scatter = plot_scatter(frame, out, "scatter.png", x="a", y="b")
    # Then: the bytes equal the pre-GE-08 code path
    assert lines.read_bytes() == _legacy_lines_png(frame, "t", ["a", "b"])
    assert scatter.read_bytes() == _legacy_scatter_png(frame, "a", "b")


_LINE_INPUTS = {
    "df": None, "out": None, "filename": None, "x": "None", "y": "None", "pairs": "None", "labels": "None",
    "title": "None", "xlabel": "None", "ylabel": "None", "xscale": "'linear'", "yscale": "'linear'", "xlim": "None",
    "ylim": "None", "legend": "True", "grid": "False", "label_fontsize": "None", "figsize": "None", "dpi": "150",
    "bbox_inches": "'tight'", "pad_inches": "None", "kind": "'main_image'",
}
_EXPECTED_SPECS = {
    "plot_lines": _LINE_INPUTS,
    "plot_scatter": {"df": None, "out": None, "filename": None, "x": None, "y": None},
    "save_figure": {"fig": None, "out": None, "filename": None, "kind": "'main_image'", "dpi": "150", "bbox_inches": "'tight'", "pad_inches": "None"},
    "save_html_figure": {
        "fig": None, "out": None, "filename": None, "kind": "'struct'", "include_plotlyjs": "'cdn'", "full_html": "True", "div_id": "None",
    },
}


@pytest.mark.parametrize("name", sorted(_EXPECTED_SPECS))
def test_plot_node_specs_unchanged__ge08_ep_9(name: str) -> None:
    """GE08-EP-9: registration metadata of every plot node is unchanged (snapshot taken before GE-08)."""
    # Given / When: the registered spec
    spec = getattr(plot_module, name).__node_spec__
    # Then: id, tags, version, idempotence, source and inputs match the pre-GE-08 snapshot
    assert spec.id == f"rdetoolkit.nodes.plot.{name}"
    assert spec.tags == ("builtin", "plot")
    assert spec.version == "2.0.0"
    assert spec.idempotent is True
    assert spec.output_schema == ("pathlib.Path",)
    assert spec.source_location == f"rdetoolkit.nodes.plot:{name}"
    assert {key: entry["default_repr"] for key, entry in spec.input_schema.items()} == _EXPECTED_SPECS[name]
    assert list(spec.input_schema) == list(_EXPECTED_SPECS[name])


@flow
def _plotting_flow(df: pd.DataFrame, out: OutputContext) -> None:
    plot_lines(df, out, "a.png", x="t")
    plot_scatter(df, out, "b.png", x="t", y="a")


def test_call_log_of_plot_flow_unchanged__ge08_ep_10(tmp_path: Path) -> None:
    """GE08-EP-10: a flow using the nodes records the same two calls as before GE-08."""
    # Given: a recorder around a flow that plots twice
    out = make_output_context(tmp_path)
    # When: running the flow
    with CallLogRecorder() as recorder:
        _plotting_flow(_frame(), out)
    # Then: exactly the two node calls are recorded, with unchanged ids, inputs and outputs
    records = recorder.records
    assert [record.node_id for record in records] == ["rdetoolkit.nodes.plot.plot_lines", "rdetoolkit.nodes.plot.plot_scatter"]
    assert [record.call_id for record in records] == ["rdetoolkit.nodes.plot.plot_lines#1", "rdetoolkit.nodes.plot.plot_scatter#2"]
    assert all(record.status == "completed" and record.error is None for record in records)
    assert all(record.parent_flow == _plotting_flow.__flow_spec__.id for record in records)  # type: ignore[attr-defined]
    assert [list(record.inputs) for record in records] == [["df", "out", "filename", "x"], ["df", "out", "filename", "x", "y"]]
    assert [[summary.type_name for summary in record.outputs] for record in records] == [["pathlib.PosixPath"], ["pathlib.PosixPath"]]


def test_plot_lines_is_idempotent__ge08_ep_11(tmp_path: Path) -> None:
    """GE08-EP-11: the same call twice gives the same path and the same bytes."""
    # Given: one output context
    out = make_output_context(tmp_path)
    # When: plotting the same request twice
    first = plot_lines(_frame(), out, "lines.png", x="t")
    first_bytes = first.read_bytes()
    second = plot_lines(_frame(), out, "lines.png", x="t")
    # Then: one artifact, identical content
    assert first == second
    assert second.read_bytes() == first_bytes
    assert _all_outputs(tmp_path) == [first]


def test_plot_lines_uses_planner_and_shared_primitive__ge08_ep_12(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GE08-EP-12: one plan per call, one draw_series call per planned series."""
    # Given: spies on the shared engine functions as the node looks them up
    calls: dict[str, list[Any]] = {"plan": [], "draw": []}
    original_plan = plot_module.build_plot_plan
    original_draw = plot_module.draw_series

    def spy_plan(*args: Any, **kwargs: Any) -> Any:
        plan = original_plan(*args, **kwargs)
        calls["plan"].append(plan)
        return plan

    def spy_draw(*args: Any, **kwargs: Any) -> Any:
        calls["draw"].append(args[2].series_id)
        return original_draw(*args, **kwargs)

    monkeypatch.setattr(plot_module, "build_plot_plan", spy_plan)
    monkeypatch.setattr(plot_module, "draw_series", spy_draw)
    # When: plotting two frames with two y columns each
    plot_lines([_frame(), _frame()], make_output_context(tmp_path), "lines.png", x="t")
    # Then: the plan is built once and every planned series is drawn once, in order
    assert len(calls["plan"]) == 1
    assert calls["draw"] == ["s000", "s001", "s002", "s003"]
    assert calls["plan"][0].x_axis.limits is None


def test_plot_lines_applies_no_house_style__ge08_ep_13(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GE08-EP-13: plain Matplotlib defaults; no rcParams leak and no csv2graph figure size."""
    # Given: default rcParams
    with mpl.rc_context():
        mpl.rcdefaults()
        before = dict(mpl.rcParams)
        observed = _record_axes(monkeypatch)
        # When: plotting without a figure size
        plot_lines(_frame(), make_output_context(tmp_path), "lines.png", x="t")
        # Then: rcParams are untouched and the figure has the rcParams size, not (8.85, 8)
        assert dict(mpl.rcParams) == before
        assert tuple(observed[-1].figure.get_size_inches()) == tuple(mpl.rcParams["figure.figsize"])
        assert observed[-1].xaxis.label.get_fontsize() == pytest.approx(mpl.rcParams["font.size"])


# --- boundaries ---------------------------------------------------------------------


def test_plot_lines_reversed_limits_invert_axis__ge08_bv_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GE08-BV-1: min > max is accepted and inverts the axis."""
    # Given / When: reversed limits
    observed = _record_axes(monkeypatch)
    plot_lines(_frame(), make_output_context(tmp_path), "rev.png", x="t", xlim=(2, 0))
    # Then: the axis runs backwards
    assert observed[-1].get_xlim() == (2.0, 0.0)
    assert observed[-1].xaxis_inverted()


@pytest.mark.parametrize("xlim", [(None, None), (1e-300, None)], ids=["both-auto", "tiny-positive"])
def test_plot_lines_log_axis_valid_bounds__ge08_bv_2(tmp_path: Path, xlim: tuple[float | None, float | None]) -> None:
    """GE08-BV-2: a log axis accepts automatic sides and any positive bound."""
    # Given / When / Then: the plot is written
    path = plot_lines(pd.DataFrame({"x": [1.0, 10.0], "y": [1.0, 2.0]}), make_output_context(tmp_path), "log.png", x="x", xscale="log", xlim=xlim)
    assert path.is_file()


def test_plot_lines_symlog_negative_bound_accepted__ge08_bv_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GE08-BV-3: only xscale="log" is validated as a log axis."""
    # Given / When: a symlog axis with a negative lower bound
    observed = _record_axes(monkeypatch)
    plot_lines(_frame(), make_output_context(tmp_path), "symlog.png", x="t", xscale="symlog", xlim=(-1, 3))
    # Then: the bound is applied on the symlog axis
    assert observed[-1].get_xscale() == "symlog"
    assert observed[-1].get_xlim() == (-1.0, 3.0)


# --- negative cases -----------------------------------------------------------------


def _assert_nothing_written(tmp_path: Path, before: set[int]) -> None:
    assert _all_outputs(tmp_path) == []
    assert set(plt.get_fignums()) == before


@pytest.mark.parametrize(
    "options",
    [{"x": "missing"}, {"x": "t", "y": "missing"}, {"x": "t", "y": ["a", "missing"]}, {"pairs": [("t", "missing")]}, {"pairs": [("missing", "a")]}],
    ids=["x", "y", "y-list", "pair-y", "pair-x"],
)
def test_plot_lines_unknown_column_raises_plot_request_error_v2_0__ge08_neg_1(tmp_path: Path, options: dict[str, Any]) -> None:
    """GE08-NEG-1 (IC-12): an unknown column is a PlotRequestError, not a KeyError."""
    # Given: a frame without the requested column
    before = set(plt.get_fignums())
    # When / Then: the engine's typed error is raised before any figure or file exists
    with pytest.raises(PlotRequestError) as caught:
        plot_lines(_frame(), make_output_context(tmp_path), "bad.png", **options)
    assert caught.value.reason == "unknown_column"
    assert isinstance(caught.value, ValueError)
    assert not isinstance(caught.value, KeyError)
    assert "missing" in str(caught.value)
    _assert_nothing_written(tmp_path, before)


@pytest.mark.parametrize(("x", "y"), [("missing", "a"), ("t", "missing")])
def test_plot_scatter_unknown_column_raises_plot_request_error_v2_0__ge08_neg_2(tmp_path: Path, x: str, y: str) -> None:
    """GE08-NEG-2 (IC-12): plot_scatter reports unknown columns the same way."""
    # Given: a frame without the requested column
    before = set(plt.get_fignums())
    # When / Then: PlotRequestError(unknown_column), nothing written
    with pytest.raises(PlotRequestError) as caught:
        plot_scatter(_frame(), make_output_context(tmp_path), "bad.png", x=x, y=y)
    assert caught.value.reason == "unknown_column"
    _assert_nothing_written(tmp_path, before)


@pytest.mark.parametrize(
    "options",
    [{"xscale": "log", "xlim": (0, 10)}, {"xscale": "log", "xlim": (None, -1)}, {"yscale": "log", "ylim": (-5, 5)}],
    ids=["x-zero", "x-negative-upper", "y-negative"],
)
def test_plot_lines_log_axis_rejects_nonpositive_bound__ge08_neg_3(tmp_path: Path, options: dict[str, Any]) -> None:
    """GE08-NEG-3 (IC-4): a bound <= 0 on a log axis fails before drawing."""
    # Given: a log axis with a non-positive bound
    before = set(plt.get_fignums())
    # When / Then: invalid_axis_limits naming the log axis, nothing written
    with pytest.raises(PlotRequestError, match="log") as caught:
        plot_lines(_frame(), make_output_context(tmp_path), "bad.png", x="t", **options)
    assert caught.value.reason == "invalid_axis_limits"
    _assert_nothing_written(tmp_path, before)


@pytest.mark.parametrize(
    "options",
    [{"xlim": (1, 1)}, {"ylim": (0, float("inf"))}, {"xlim": (float("nan"), None)}, {"ylim": ("0", 1)}, {"xlim": (0, 1, 2)}],
    ids=["equal", "infinite", "nan", "string", "triple"],
)
def test_plot_lines_rejects_invalid_limits__ge08_neg_4(tmp_path: Path, options: dict[str, Any]) -> None:
    """GE08-NEG-4 (IC-4): the shared limit validator rejects malformed limits."""
    # Given: malformed limits
    before = set(plt.get_fignums())
    # When / Then: invalid_axis_limits, nothing written
    with pytest.raises(PlotRequestError) as caught:
        plot_lines(_frame(), make_output_context(tmp_path), "bad.png", x="t", **options)
    assert caught.value.reason == "invalid_axis_limits"
    _assert_nothing_written(tmp_path, before)


@pytest.mark.parametrize("options", [{"pairs": []}, {"y": []}, {"x": "t", "y": []}], ids=["pairs", "y", "x-and-y"])
def test_plot_lines_empty_selection_never_plots_everything__ge08_neg_5(tmp_path: Path, options: dict[str, Any]) -> None:
    """GE08-NEG-5: an empty selection is an error, not the engine's 'every column' default."""
    # Given: an explicitly empty selection
    before = set(plt.get_fignums())
    # When / Then: the node's argument error, nothing written
    with pytest.raises(ValueError, match="at least one measurement series"):
        plot_lines(_frame(), make_output_context(tmp_path), "bad.png", **options)
    _assert_nothing_written(tmp_path, before)


def test_plot_lines_frame_without_series_rejected__ge08_neg_6(tmp_path: Path) -> None:
    """GE08-NEG-6: every frame must contribute a series, as before GE-08."""
    # Given: a second frame that only has the x column
    frames = [_frame(), pd.DataFrame({"t": [1.0, 2.0]})]
    before = set(plt.get_fignums())
    # When / Then: rejected, nothing written
    with pytest.raises(ValueError, match="at least one measurement series"):
        plot_lines(frames, make_output_context(tmp_path), "bad.png", x="t")
    _assert_nothing_written(tmp_path, before)


def test_plot_lines_ambiguous_column_name__ge08_neg_7(tmp_path: Path) -> None:
    """GE08-NEG-7: a duplicated header addressed by name is ambiguous."""
    # Given: two columns labelled "y"
    frame = pd.DataFrame([[1, 2, 3], [4, 5, 6]], columns=["x", "y", "y"])
    before = set(plt.get_fignums())
    # When / Then: ambiguous_column, nothing written
    with pytest.raises(PlotRequestError) as caught:
        plot_lines(frame, make_output_context(tmp_path), "bad.png", x="x", y="y")
    assert caught.value.reason == "ambiguous_column"
    _assert_nothing_written(tmp_path, before)


def test_plot_lines_x_missing_in_second_frame__ge08_neg_8(tmp_path: Path) -> None:
    """GE08-NEG-8: every frame is resolved before anything is drawn."""
    # Given: the x column only exists in the first frame
    frames = [_frame(), pd.DataFrame({"u": [1.0], "a": [2.0]})]
    before = set(plt.get_fignums())
    # When / Then: unknown_column, nothing written
    with pytest.raises(PlotRequestError) as caught:
        plot_lines(frames, make_output_context(tmp_path), "bad.png", x="t", y="a")
    assert caught.value.reason == "unknown_column"
    _assert_nothing_written(tmp_path, before)


def test_plot_lines_labelled_pairs_and_labels__ge08_neg_9(tmp_path: Path) -> None:
    """GE08-NEG-9: one label spelling only; the node's message is kept."""
    # Given / When / Then
    with pytest.raises(ValueError, match="not both"):
        plot_lines(_frame(), make_output_context(tmp_path), "bad.png", pairs=[("t", "a", "A")], labels=["again"])
    assert _all_outputs(tmp_path) == []


def test_save_figure_failure_keeps_caller_figure__ge08_neg_10(tmp_path: Path) -> None:
    """GE08-NEG-10: a rejected filename neither writes nor closes the caller's figure."""
    # Given: a caller-owned figure
    figure, axes = plt.subplots()
    axes.plot([1, 2], [3, 4])
    try:
        # When / Then: an escaping filename fails
        with pytest.raises(ValueError):
            save_figure(figure, make_output_context(tmp_path / "out"), "../escape.png")
        assert plt.fignum_exists(figure.number)
        assert not (tmp_path / "escape.png").exists()
    finally:
        plt.close(figure)


@pytest.mark.parametrize("name", ["_line_selections", "_line_columns", "_line_labels", "_pair_selection"])
def test_no_private_column_resolver_left__ge08_neg_11(name: str) -> None:
    """GE08-NEG-11: the node module keeps no second copy of the column/label resolution."""
    # Given / When / Then: the former helpers are gone and no frame is indexed by column name
    assert not hasattr(plot_module, name)
    source = inspect.getsource(plot_module)
    assert "frame[" not in source
    assert "df[x]" not in source
    assert "df[y]" not in source


def test_plot_lines_mixed_units_still_drawn__ge08_bv_4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: the caller names y columns whose headers carry different units
    frame = pd.DataFrame({"t (s)": [0.0, 1.0, 2.0], "voltage (V)": [1.0, 2.0, 3.0], "current (A)": [0.1, 0.2, 0.3]})
    out = make_output_context(tmp_path)
    observed = _record_axes(monkeypatch)
    # When: plotting them with plot_lines (an explicit selection is the caller's acknowledgment)
    path = plot_lines(frame, out, "mixed.png", x="t (s)", y=["voltage (V)", "current (A)"])
    # Then: both series are drawn on one axis instead of failing with unit_mismatch
    assert path.is_file()
    assert [line.get_label() for line in observed[0].get_lines()] == ["voltage (V)", "current (A)"]
