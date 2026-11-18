"""GE-13 (#719): one-sided axis limits, consistent across every plotting entry point.

Intentional behaviour change IC-4 (versioned tests end in ``_v2_0``): a one-sided
``xlim``/``ylim`` such as ``(0, None)`` is applied (only the given side is fixed, the
other side keeps Matplotlib's automatic limit) instead of being silently dropped, and
invalid limits (non-finite, equal bounds, a bound ``<= 0`` on a log axis) raise
``PlotRequestError(reason="invalid_axis_limits")`` instead of being ignored by
Matplotlib with a warning. Reversed bounds stay accepted and invert the axis, as
``plot_lines`` does. ``config.normalize_axis_limits`` is unchanged (ruling C-01).

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| validate_axis_limits | None / (None, None) | None (fully automatic) | TC-GE13-EP-001 |
| validate_axis_limits | one-sided, full, reversed, int/numpy bounds, positive log | float pair, None side kept | TC-GE13-EP-002 |
| validate_axis_limits | NaN / +-inf bound | PlotRequestError(invalid_axis_limits), axis + value named | TC-GE13-EP-003 |
| validate_axis_limits | log axis, bound 0 or negative (either side) | PlotRequestError(invalid_axis_limits), "log" named | TC-GE13-EP-004 |
| validate_axis_limits | non-numeric / bool bound, wrong length, not a pair | PlotRequestError(invalid_axis_limits) | TC-GE13-EP-005 |
| plot_from_dataframe | (axis, side) one-sided | given side == bound, other side == automatic | TC-GE13-EP-006 |
| plot_from_dataframe / render_graph | full limits / no limits / (None, None) | unchanged legacy output | TC-GE13-EP-007 |
| plot_from_dataframe | invalid limits, save and return_fig | raises, output dir absent | TC-GE13-EP-008 |
| csv2graph | one-sided limits on every saved figure | given side == bound, other side automatic | TC-GE13-EP-009 |
| render_graph / build_plot_plan | one-sided / invalid AxisSpec.limits | applied (plan keeps them as given) / raises before rendering | TC-GE13-EP-010 |
| CLI plot | --xmin/--xmax/--ymin/--ymax | one-sided limit applied, exit 0 | TC-GE13-EP-011 |
| CLI plot | --xmin with --xlim, invalid/log bounds | exit 2, option named, nothing written | TC-GE13-EP-012 |
| plot_lines parity | same frame and limits | same fixed side, same automatic side | TC-GE13-EP-013 |
| normalize_axis_limits | one-sided input (C-01) | still None | TC-GE13-EP-014 |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| validate_axis_limits | equal bounds (1, 1) / (0, 0) | invalid_axis_limits | TC-GE13-BV-001 |
| validate_axis_limits | reversed (10, 0) | accepted, order kept | TC-GE13-BV-002 |
| validate_axis_limits | log bound just above 0 (1e-300) / exactly 0 | accepted / rejected | TC-GE13-BV-003 |
| validate_axis_limits | linear bound 0 / negative | accepted | TC-GE13-BV-004 |
| plot_from_dataframe | reversed limits | axis inverted | TC-GE13-BV-005 |
| plot_from_dataframe | log axis one-sided positive | given side fixed on the log scale | TC-GE13-BV-006 |
"""

from __future__ import annotations

import math
import shutil
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from rdetoolkit.graph import engine
from rdetoolkit.graph.api.csv2graph import csv2graph, plot_from_dataframe
from rdetoolkit.graph.config import normalize_axis_limits
from rdetoolkit.graph.exceptions import PlotConfigError, PlotRequestError
from rdetoolkit.graph.plan import build_plot_plan
from rdetoolkit.graph.spec import AxisSpec, GraphSpec
from rdetoolkit.graph.validation import validate_axis_limits
from rdetoolkit.nodes import plot_lines
from rdetoolkit.testing import make_output_context

# Rich colours usage errors when the runner forces a terminal (as CI does), which splits
# option names with escape codes; assertions read the text without them.
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_CLI_ENV = {"COLUMNS": "200"}

FIXTURES = Path(__file__).parent / "fixtures"
INVALID = "invalid_axis_limits"
# Bounds outside the automatic range of ``_frame()`` on both axes, so a dropped
# bound is distinguishable from an applied one.
LOWER, UPPER = 0.0, 20.0
CASES = [("x", 0), ("x", 1), ("y", 0), ("y", 1)]


def _frame() -> pd.DataFrame:
    return pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "a": [2.0, 4.0, 6.0, 8.0], "b": [1.0, 3.0, 5.0, 7.0]})


def _one_sided(side: int) -> tuple[float | None, float | None]:
    return (LOWER, None) if side == 0 else (None, UPPER)


def _limit_kwargs(axis: str, limits: Any) -> dict[str, Any]:
    return {f"{axis}lim": limits}


def _limits(fig: Figure, axis: str) -> tuple[float, float]:
    ax = fig.axes[0]
    return ax.get_xlim() if axis == "x" else ax.get_ylim()


def _returned_figures(**kwargs: Any) -> list[Figure]:
    artifacts = plot_from_dataframe(_frame(), output_dir="unused", return_fig=True, **kwargs)
    assert artifacts is not None
    return [artifact.figure for artifact in artifacts]


def _record_saved_limits(monkeypatch: pytest.MonkeyPatch) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Record (xlim, ylim) of the first axes of every figure as it is saved."""
    recorded: list[tuple[tuple[float, float], tuple[float, float]]] = []
    original = Figure.savefig

    def spy(fig: Figure, *args: Any, **kwargs: Any) -> Any:
        recorded.append((fig.axes[0].get_xlim(), fig.axes[0].get_ylim()))
        return original(fig, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", spy)
    return recorded


def _files(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir())


def _write_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "data.csv"
    _frame().to_csv(csv_path, index=False)
    return csv_path


# --- validate_axis_limits ---------------------------------------------------------------


@pytest.mark.parametrize("limits", [None, (None, None), [None, None]])
@pytest.mark.parametrize("scale", ["linear", "log"])
def test_validate_axis_limits_automatic__tc_ge13_ep_001(limits: Any, scale: Any) -> None:
    # Given: no limit at all, or both sides automatic
    # When: validating
    result = validate_axis_limits(limits, scale=scale, axis="x")
    # Then: there is nothing to apply
    assert result is None


@pytest.mark.parametrize(
    ("limits", "scale", "expected"),
    [
        ((0, None), "linear", (0.0, None)),
        ((None, 10), "linear", (None, 10.0)),
        ((0.5, 10.0), "linear", (0.5, 10.0)),
        ((-5, -1), "linear", (-5.0, -1.0)),
        ((10, 0), "linear", (10.0, 0.0)),
        ([1, 2], "linear", (1.0, 2.0)),
        ((np.float64(0.1), None), "log", (0.1, None)),
        ((None, np.int64(100)), "log", (None, 100.0)),
        ((1e-300, None), "log", (1e-300, None)),
        ((100.0, 0.1), "log", (100.0, 0.1)),
    ],
)
def test_validate_axis_limits_accepts__tc_ge13_ep_002(limits: Any, scale: Any, expected: Any) -> None:
    # Given: valid one-sided, full, reversed or log limits (BV-002/003/004 included)
    # When: validating
    result = validate_axis_limits(limits, scale=scale, axis="y")
    # Then: a float pair is returned and a None side stays None
    assert result == expected
    assert all(bound is None or type(bound) is float for bound in result or ())


@pytest.mark.parametrize("limits", [(math.nan, None), (None, math.inf), (-math.inf, 1.0), (0.0, math.nan)])
def test_validate_axis_limits_rejects_non_finite__tc_ge13_ep_003(limits: Any) -> None:
    # Given: a non-finite bound
    # When / Then: the request is rejected, naming the axis and the bound
    with pytest.raises(PlotRequestError) as info:
        validate_axis_limits(limits, scale="linear", axis="x")
    assert info.value.reason == INVALID
    assert "x" in str(info.value)
    assert "finite" in str(info.value)


@pytest.mark.parametrize(
    ("limits", "bad"),
    [((0, 10), "0"), ((-1, None), "-1"), ((None, 0), "0"), ((None, -5.5), "-5.5"), ((0.0, None), "0")],
)
def test_validate_axis_limits_rejects_nonpositive_log__tc_ge13_ep_004_v2_0(limits: Any, bad: str) -> None:
    # Given: a bound <= 0 on a log axis (BV-003: exactly 0 is rejected)
    # When / Then: the request is rejected with an actionable message
    with pytest.raises(PlotRequestError) as info:
        validate_axis_limits(limits, scale="log", axis="y")
    message = str(info.value)
    assert info.value.reason == INVALID
    assert "y" in message
    assert "log" in message
    assert bad in message
    assert "None" in message  # tells the caller how to keep the side automatic


@pytest.mark.parametrize(
    "limits",
    [("a", None), (None, "10"), (True, None), (None, False), (1.0,), (1.0, 2.0, 3.0), 5, "0,10", (1, 1), (0.0, 0.0)],
)
def test_validate_axis_limits_rejects_malformed__tc_ge13_ep_005(limits: Any) -> None:
    # Given: a non-numeric/bool bound, a wrong-length sequence, a non-pair, or equal bounds (BV-001)
    # When / Then: the request is rejected as invalid limits (a ValueError and PlotConfigError too)
    with pytest.raises(PlotRequestError) as info:
        validate_axis_limits(limits, scale="linear", axis="x")
    assert info.value.reason == INVALID
    assert isinstance(info.value, ValueError)
    assert isinstance(info.value, PlotConfigError)


def test_validate_axis_limits_equal_bounds_message__tc_ge13_bv_001() -> None:
    # Given: equal bounds
    # When / Then: the message names the problem
    with pytest.raises(PlotRequestError, match="equal"):
        validate_axis_limits((1.0, 1.0), scale="linear", axis="x")


# --- legacy facade: plot_from_dataframe ------------------------------------------------


@pytest.mark.parametrize(("axis", "side"), CASES)
def test_plot_from_dataframe_one_sided__tc_ge13_ep_006_v2_0(axis: str, side: int) -> None:
    # Given: the automatic limits of the same plot
    auto = [_limits(fig, axis) for fig in _returned_figures()]
    # When: fixing only one side
    figures = _returned_figures(**_limit_kwargs(axis, _one_sided(side)))
    # Then: on every figure the given side equals the bound and the other side is automatic
    assert len(figures) == len(auto) == 3
    for fig, reference in zip(figures, auto, strict=True):
        observed = _limits(fig, axis)
        assert observed[side] == (LOWER, UPPER)[side]
        assert observed[1 - side] == pytest.approx(reference[1 - side])


@pytest.mark.parametrize("limits", [None, (None, None)])
def test_plot_from_dataframe_no_limits_unchanged__tc_ge13_ep_007(limits: Any) -> None:
    # Given: the default call
    auto = [(_limits(fig, "x"), _limits(fig, "y")) for fig in _returned_figures()]
    # When: passing no limits explicitly
    figures = _returned_figures(xlim=limits, ylim=limits)
    # Then: the automatic limits are kept on both axes
    assert [(_limits(fig, "x"), _limits(fig, "y")) for fig in figures] == pytest.approx(auto)


def test_plot_from_dataframe_full_limits_unchanged__tc_ge13_ep_007() -> None:
    # Given/When: both bounds on both axes
    figures = _returned_figures(xlim=(0.5, 5.0), ylim=(-1.0, 9.0))
    # Then: exactly those limits, as before
    for fig in figures:
        assert _limits(fig, "x") == (0.5, 5.0)
        assert _limits(fig, "y") == (-1.0, 9.0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"logx": True, "xlim": (0, 10)},
        {"logy": True, "ylim": (None, -1)},
        {"xlim": (2.0, 2.0)},
        {"ylim": (math.nan, None)},
        {"xlim": ("left", None)},
    ],
)
@pytest.mark.parametrize("return_fig", [False, True])
def test_plot_from_dataframe_invalid_limits_raise__tc_ge13_ep_008_v2_0(
    tmp_path: Path, kwargs: dict[str, Any], return_fig: bool,
) -> None:
    # Given: an output directory that does not exist yet
    out = tmp_path / "out"
    # When / Then: invalid limits raise before anything is written
    with pytest.raises(PlotRequestError) as info:
        plot_from_dataframe(_frame(), output_dir=out, return_fig=return_fig, **kwargs)
    assert info.value.reason == INVALID
    assert not out.exists()


def test_plot_from_dataframe_reversed_inverts__tc_ge13_bv_005() -> None:
    # Given/When: reversed bounds
    figures = _returned_figures(xlim=(5.0, 0.0), ylim=(None, -1.0))
    # Then: the x axis is inverted with exactly those bounds; the y upper side is below the lower side
    for fig in figures:
        assert _limits(fig, "x") == (5.0, 0.0)
        assert fig.axes[0].xaxis_inverted()
        assert _limits(fig, "y")[1] == -1.0
        assert fig.axes[0].yaxis_inverted()


@pytest.mark.parametrize(("axis", "side", "bound"), [("x", 0, 0.5), ("y", 1, 1000.0)])
def test_plot_from_dataframe_log_one_sided__tc_ge13_bv_006(axis: str, side: int, bound: float) -> None:
    # Given: a log axis and its automatic limits
    log_kwargs = {f"log{axis}": True}
    auto = [_limits(fig, axis) for fig in _returned_figures(**log_kwargs)]
    limits = (bound, None) if side == 0 else (None, bound)
    # When: fixing one positive side
    figures = _returned_figures(**log_kwargs, **_limit_kwargs(axis, limits))
    # Then: the given side is applied on the log scale; the other stays automatic
    for fig, reference in zip(figures, auto, strict=True):
        ax = fig.axes[0]
        assert (ax.get_xscale() if axis == "x" else ax.get_yscale()) == "log"
        assert _limits(fig, axis)[side] == pytest.approx(bound)
        assert _limits(fig, axis)[1 - side] == pytest.approx(reference[1 - side])


# --- legacy facade: csv2graph (save path) ------------------------------------------------


@pytest.mark.parametrize(("axis", "side"), CASES)
def test_csv2graph_one_sided__tc_ge13_ep_009_v2_0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, axis: str, side: int) -> None:
    # Given: a CSV copied to tmp and the automatic limits of each saved figure
    csv_path = _write_csv(tmp_path)
    recorded = _record_saved_limits(monkeypatch)
    csv2graph(csv_path, output_dir=tmp_path / "auto")
    auto = list(recorded)
    recorded.clear()
    # When: saving with one side fixed
    csv2graph(csv_path, output_dir=tmp_path / "limited", **_limit_kwargs(axis, _one_sided(side)))
    # Then: same files; every saved figure has the bound on the given side only
    assert _files(tmp_path / "limited") == _files(tmp_path / "auto") == ["data.png", "data_a.png", "data_b.png"]
    index = 0 if axis == "x" else 1
    assert len(recorded) == len(auto) == 3
    for observed, reference in zip(recorded, auto, strict=True):
        assert observed[index][side] == (LOWER, UPPER)[side]
        assert observed[index][1 - side] == pytest.approx(reference[index][1 - side])
        assert observed[1 - index] == pytest.approx(reference[1 - index])


def test_csv2graph_log_nonpositive_raises_nothing_written__tc_ge13_ep_009_v2_0(tmp_path: Path) -> None:
    # Given: a fixture CSV in tmp
    csv_path = tmp_path / "simple.csv"
    shutil.copyfile(FIXTURES / "simple.csv", csv_path)
    # When / Then: a log axis with a zero bound fails and nothing is written
    with pytest.raises(PlotRequestError) as info:
        csv2graph(csv_path, output_dir=tmp_path / "out", logx=True, xlim=(0, None))
    assert info.value.reason == INVALID
    assert not (tmp_path / "out").exists()
    assert _files(tmp_path) == ["simple.csv"]


# --- spec API ---------------------------------------------------------------------------


@pytest.mark.parametrize(("axis", "side"), CASES)
def test_render_graph_one_sided__tc_ge13_ep_010(axis: str, side: int) -> None:
    # Given: the automatic limits of the spec-API figures
    auto = [_limits(a.figure, axis) for a in engine.render_graph(_frame()).artifacts]
    limited_axis = AxisSpec(limits=_one_sided(side))
    spec = GraphSpec(x_axis=limited_axis) if axis == "x" else GraphSpec(y_axis=limited_axis)
    # When: rendering with one side fixed
    result = engine.render_graph(_frame(), spec)
    # Then: the given side equals the bound on every figure, the other side is automatic
    assert len(result.artifacts) == len(auto) == 3
    for artifact, reference in zip(result.artifacts, auto, strict=True):
        observed = _limits(artifact.figure, axis)
        assert observed[side] == (LOWER, UPPER)[side]
        assert observed[1 - side] == pytest.approx(reference[1 - side])


@pytest.mark.parametrize("limits", [(None, None), (0, None), (None, 5.0), (5.0, 1.0)])
def test_build_plot_plan_validates_and_keeps_limits__tc_ge13_ep_010(limits: Any) -> None:
    # Given: valid limits on both axes (TC-GE03-BV-005 pins that the plan records them as given)
    spec = GraphSpec(x_axis=AxisSpec(limits=limits), y_axis=AxisSpec(limits=limits))
    # When: planning
    plan = build_plot_plan(_frame(), spec)
    # Then: validation passes and the plan keeps the limits unchanged
    assert plan.x_axis.limits == plan.y_axis.limits == limits


def test_render_graph_both_sides_none_is_automatic__tc_ge13_ep_007() -> None:
    # Given: the automatic limits of the spec-API figures
    auto = [(_limits(a.figure, "x"), _limits(a.figure, "y")) for a in engine.render_graph(_frame()).artifacts]
    # When: rendering with (None, None) on both axes
    spec = GraphSpec(x_axis=AxisSpec(limits=(None, None)), y_axis=AxisSpec(limits=(None, None)))
    result = engine.render_graph(_frame(), spec)
    # Then: the limits are the automatic ones
    assert [(_limits(a.figure, "x"), _limits(a.figure, "y")) for a in result.artifacts] == pytest.approx(auto)


@pytest.mark.parametrize(
    "axis_spec",
    [AxisSpec(scale="log", limits=(0, None)), AxisSpec(limits=(1.0, 1.0)), AxisSpec(limits=(None, math.inf))],
)
@pytest.mark.parametrize("axis", ["x", "y"])
def test_build_plot_plan_rejects_invalid_limits__tc_ge13_ep_010_v2_0(axis_spec: AxisSpec, axis: str) -> None:
    # Given: an invalid AxisSpec on one axis
    spec = GraphSpec(x_axis=axis_spec) if axis == "x" else GraphSpec(y_axis=axis_spec)
    # When / Then: planning (and therefore render_graph) fails before any figure exists
    for call in (lambda: build_plot_plan(_frame(), spec), lambda: engine.render_graph(_frame(), spec)):
        with pytest.raises(PlotRequestError) as info:
            call()
        assert info.value.reason == INVALID
        assert axis in str(info.value)


# --- CLI ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("option", "axis", "side"),
    [("--xmin", "x", 0), ("--xmax", "x", 1), ("--ymin", "y", 0), ("--ymax", "y", 1)],
)
def test_cli_one_sided_options__tc_ge13_ep_011(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, option: str, axis: str, side: int,
) -> None:
    # Given: a CSV and the automatic limits of the same CLI plot
    csv_path = _write_csv(tmp_path)
    recorded = _record_saved_limits(monkeypatch)
    assert CliRunner().invoke(app, ["plot", str(csv_path), "-o", str(tmp_path / "auto")]).exit_code == 0
    auto = list(recorded)
    recorded.clear()
    bound = (LOWER, UPPER)[side]
    # When: passing one bound option
    result = CliRunner().invoke(app, ["plot", str(csv_path), "-o", str(tmp_path / "lim"), option, str(bound)])
    # Then: success; only that side is fixed on every saved figure
    assert result.exit_code == 0, result.output
    index = 0 if axis == "x" else 1
    assert len(recorded) == len(auto) == 3
    for observed, reference in zip(recorded, auto, strict=True):
        assert observed[index][side] == bound
        assert observed[index][1 - side] == pytest.approx(reference[index][1 - side])


def test_cli_min_and_max_combine__tc_ge13_ep_011(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a CSV
    csv_path = _write_csv(tmp_path)
    recorded = _record_saved_limits(monkeypatch)
    # When: giving both --ymin and --ymax, and --xlim alone
    args = ["plot", str(csv_path), "-o", str(tmp_path / "o"), "--ymin", "-1", "--ymax", "9", "--xlim", "0", "5"]
    result = CliRunner().invoke(app, args)
    # Then: both bounds apply exactly
    assert result.exit_code == 0, result.output
    assert recorded
    assert all(x == (0.0, 5.0) and y == (-1.0, 9.0) for x, y in recorded)


@pytest.mark.parametrize(
    ("args", "hint"),
    [
        (["--xlim", "0", "5", "--xmin", "1"], "--xmin"),
        (["--ylim", "0", "5", "--ymax", "1"], "--ymax"),
        (["--logx", "--xmin", "0"], "--xmin"),
        (["--logy", "--ylim", "-1", "10"], "--ylim"),
        (["--xmin", "nan"], "--xmin"),
        (["--xmin", "2", "--xmax", "2"], "--xmax"),
    ],
)
def test_cli_invalid_limits_exit_2__tc_ge13_ep_012_v2_0(tmp_path: Path, args: list[str], hint: str) -> None:
    # Given: a CSV and an output directory
    csv_path = _write_csv(tmp_path)
    out = tmp_path / "out"
    # When: invoking with conflicting or invalid limits
    result = CliRunner().invoke(app, ["plot", str(csv_path), "--output-dir", str(out), *args], env=_CLI_ENV)
    # Then: usage error naming the option; nothing is written
    assert result.exit_code == 2, result.output
    output = _ANSI_ESCAPE.sub("", result.output)
    assert hint in output
    assert "No such option" not in output  # the option exists; the value is what is rejected
    assert not out.exists()
    assert _files(tmp_path) == ["data.csv"]


# --- parity with plot_lines and the pinned legacy helper ----------------------------------


@pytest.mark.parametrize(("axis", "side"), CASES)
def test_parity_with_plot_lines__tc_ge13_ep_013(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, axis: str, side: int) -> None:
    # Given: the same frame and the same one-sided limit for plot_lines and the facade
    limits = _limit_kwargs(axis, _one_sided(side))
    recorded = _record_saved_limits(monkeypatch)
    plot_lines(_frame(), make_output_context(tmp_path), "auto.png", x="x")
    plot_lines(_frame(), make_output_context(tmp_path), "lim.png", x="x", **limits)
    node_auto, node_limited = recorded
    # When: the facade draws the overlay with the same limit
    overlay = _returned_figures(**limits)[0]
    facade_auto = _returned_figures()[0]
    # Then: both fix the same side to the bound and keep their own automatic other side.
    # (The legacy renderer draws x without margins while plot_lines keeps Matplotlib's
    # default margin, so the automatic values themselves differ by design.)
    index = 0 if axis == "x" else 1
    assert node_limited[index][side] == _limits(overlay, axis)[side] == (LOWER, UPPER)[side]
    assert node_limited[index][1 - side] == pytest.approx(node_auto[index][1 - side])
    assert _limits(overlay, axis)[1 - side] == pytest.approx(_limits(facade_auto, axis)[1 - side])
    assert node_limited[1 - index] == pytest.approx(node_auto[1 - index])


@pytest.mark.parametrize("limits", [(None, 10.0), (0.0, None)])
def test_normalize_axis_limits_unchanged__tc_ge13_ep_014(limits: Any) -> None:
    # Given/When: the pinned legacy helper with one-sided input (ruling C-01)
    # Then: it still returns None; the facade no longer uses it
    assert normalize_axis_limits(limits) is None
