"""Fix round 1 / R-2, R-3, R-4, R-6: legacy plotting behaviour restored after review.

The base for every pinned value is develop/v2 before the Graph Engine (merge-base
a76838ec), probed with ``git archive`` of that tree.

* R-2: datetime-like axis bounds (``pd.Timestamp``, ``np.datetime64``,
  ``datetime.datetime``, ``datetime.date``) are accepted again and passed through
  unchanged; only numbers are converted and checked against the log-axis rule.
* R-3: on the legacy facade, when the overlay does not mix units (IC-6 does not
  apply), every individual figure keeps the base y label (the first y column's
  label); IC-6 still labels mixed-unit individual figures after their own column.
* R-4: ``MatplotlibRenderer.render_individual(df, config, y_col_index)`` draws any
  column against the x (and direction) of ``series_position`` (default 0), as base did.
* R-6: the mixed-unit ``GraphUserWarning`` is emitted only when an overlay figure is
  produced, once per call (also with ``html=True``).

EP table:
| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-FIX1-R2-EP-001 | datetime-like bounds | Timestamp / datetime64 / datetime / date pairs, one-sided | returned unchanged (same objects) |
| TC-FIX1-R2-EP-002 | plot_from_dataframe, datetime x | xlim of Timestamps | figure x limits == date2num(bounds) |
| TC-FIX1-R2-EP-003 | plot_lines node, datetime x | xlim of datetimes | file written, x limits applied |
| TC-FIX1-R3-EP-001 | same unit / unit-less / duplicate header / multi-x / unit-less + unit | individual y labels | base label (first y column) on every figure |
| TC-FIX1-R3-EP-002 | mixed units (IC-6, control) | V + A | overlay joined, individual own column |
| TC-FIX1-R4-EP-001 | column outside y_cols | y_cols=[1], y_col_index=2 | column 2 vs x, title "T - B", y label "Y" |
| TC-FIX1-R4-EP-002 | position / column not paired as planned | (2, 0), (1, 1), (2, 5) | x of the position (first x beyond the list), base titles |
| TC-FIX1-R4-EP-003 | direction of the position | direction_cols=[4], y_col_index=2 | column 2 split by the direction column |
| TC-FIX1-R6-EP-001 | overlay with mixed units | mode overlay, png / png + html | exactly one GraphUserWarning per call |

BV table:
| TC | Boundary | Input | Expected |
|----|----------|-------|----------|
| TC-FIX1-R2-BV-001 | datetime bound on a log axis | (Timestamp, None), scale log | accepted (the log rule is for numbers) |
| TC-FIX1-R3-BV-001 | explicit y_label | y_label="Signal" | every figure uses it (unchanged) |

Negative table:
| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-FIX1-R2-NEG-001 | equal datetime bounds | (t, t) for each datetime-like type | invalid_axis_limits |
| TC-FIX1-R2-NEG-002 | NaT bound | pd.NaT / np.datetime64("NaT") | invalid_axis_limits |
| TC-FIX1-R2-NEG-003 | still rejected | bool, str, inf, nan, complex | invalid_axis_limits |
| TC-FIX1-R4-NEG-001 | no y_cols / no x_col | y_cols=None / x_col=None | ValueError, no figure left open |
| TC-FIX1-R4-NEG-002 | column outside the frame | y_col_index=9 | error before a figure exists |
| TC-FIX1-R6-NEG-001 | individual mode, mixed units | mode="individual" (png and html) | no GraphUserWarning |
| TC-FIX1-R6-NEG-002 | same-unit overlay | V + V | no GraphUserWarning |
| TC-FIX1-R6-NEG-003 | collect_render_results, individual mode | mixed units | no GraphUserWarning |
"""

from __future__ import annotations

import datetime as dt
import math
import warnings
from pathlib import Path
from typing import Any

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from rdetoolkit.graph.api.csv2graph import plot_from_dataframe
from rdetoolkit.graph.exceptions import GraphUserWarning, PlotRequestError
from rdetoolkit.graph.models import AxisConfig, PlotConfig, PlotMode
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer
from rdetoolkit.graph.strategies import collect_render_results
from rdetoolkit.graph.validation import validate_axis_limits
from rdetoolkit.nodes import plot_lines
from rdetoolkit.testing import make_output_context

INVALID = "invalid_axis_limits"
T0, T1 = pd.Timestamp("2024-01-01"), pd.Timestamp("2024-03-01")


def _graph_warnings(records: list[warnings.WarningMessage]) -> list[str]:
    return [str(record.message) for record in records if issubclass(record.category, GraphUserWarning)]


def _labels(figures: list[Any]) -> list[tuple[str, str]]:
    return [(artifact.filename, artifact.figure.axes[0].get_ylabel()) for artifact in figures]


def _figures(df: pd.DataFrame, tmp_path: Path, **kwargs: Any) -> list[Any]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", GraphUserWarning)
        result = plot_from_dataframe(df, tmp_path, return_fig=True, **kwargs)
    assert result is not None
    return result


# --- R-2: datetime-like axis bounds ---------------------------------------------------


@pytest.mark.parametrize(
    "limits",
    [
        (T0, T1),
        (np.datetime64("2024-01-01"), np.datetime64("2024-03-01")),
        (dt.datetime(2024, 1, 1), dt.datetime(2024, 3, 1)),  # noqa: DTZ001 - naive like the data
        (dt.date(2024, 1, 1), dt.date(2024, 3, 1)),
        (T0, None),
        (None, dt.date(2024, 3, 1)),
        (T1, T0),
    ],
)
def test_datetime_bounds_pass_through__tc_fix1_r2_ep_001(limits: tuple[Any, Any]) -> None:
    """TC-FIX1-R2-EP-001: datetime-like bounds are accepted and returned unchanged."""
    # Given/When: datetime-like limits on a linear axis
    result = validate_axis_limits(limits, scale="linear", axis="x")
    # Then: the very same bound objects come back (no float conversion)
    assert result is not None
    assert all(got is given for got, given in zip(result, limits, strict=True))


def test_plot_from_dataframe_applies_datetime_xlim__tc_fix1_r2_ep_002(tmp_path: Path) -> None:
    """TC-FIX1-R2-EP-002: the legacy facade applies Timestamp limits as base did."""
    # Given: a datetime x column
    df = pd.DataFrame({"time": pd.date_range("2024-01-15", periods=3, freq="D"), "v (V)": [1.0, 2.0, 3.0]})
    # When: plotting with Timestamp x limits
    figures = _figures(df, tmp_path, xlim=(T0, T1))
    # Then: every figure has exactly those limits
    expected = (mdates.date2num(T0), mdates.date2num(T1))
    assert [artifact.figure.axes[0].get_xlim() for artifact in figures] == [expected] * len(figures)


def test_plot_lines_applies_datetime_xlim__tc_fix1_r2_ep_003(tmp_path: Path) -> None:
    """TC-FIX1-R2-EP-003: plot_lines accepts datetime limits as base did."""
    # Given: a datetime x column
    df = pd.DataFrame({"time": pd.date_range("2024-01-15", periods=3, freq="D"), "v": [1.0, 2.0, 3.0]})
    seen: list[tuple[float, float]] = []
    original = plt.Axes.set_xlim

    def record(axes: Any, *args: Any, **kwargs: Any) -> Any:
        value = original(axes, *args, **kwargs)
        seen.append(axes.get_xlim())
        return value

    # When: plotting with datetime limits
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(plt.Axes, "set_xlim", record)
        path = plot_lines(df, make_output_context(tmp_path), "t.png", x="time", y="v", xlim=(dt.datetime(2024, 1, 1), None))  # type: ignore[arg-type]  # noqa: DTZ001
    # Then: the image exists and the lower bound was applied
    assert path.is_file()
    assert seen and seen[-1][0] == mdates.date2num(dt.datetime(2024, 1, 1))  # noqa: DTZ001


def test_datetime_bound_on_log_axis_is_not_number_checked__tc_fix1_r2_bv_001() -> None:
    """TC-FIX1-R2-BV-001: the log-axis rule only applies to numeric bounds."""
    # Given/When/Then
    assert validate_axis_limits((T0, None), scale="log", axis="x") == (T0, None)


@pytest.mark.parametrize(
    "bound",
    [T0, np.datetime64("2024-01-01"), dt.datetime(2024, 1, 1), dt.date(2024, 1, 1)],  # noqa: DTZ001
)
def test_equal_datetime_bounds_rejected__tc_fix1_r2_neg_001(bound: Any) -> None:
    """TC-FIX1-R2-NEG-001: equal bounds stay an empty range for datetimes too."""
    with pytest.raises(PlotRequestError) as info:
        validate_axis_limits((bound, bound), scale="linear", axis="x")
    assert info.value.reason == INVALID


@pytest.mark.parametrize("limits", [(pd.NaT, T1), (T0, np.datetime64("NaT"))])
def test_nat_bound_rejected__tc_fix1_r2_neg_002(limits: tuple[Any, Any]) -> None:
    """TC-FIX1-R2-NEG-002: NaT is the datetime NaN and is not a bound."""
    with pytest.raises(PlotRequestError) as info:
        validate_axis_limits(limits, scale="linear", axis="x")
    assert info.value.reason == INVALID


@pytest.mark.parametrize("limits", [(True, 1), (0, "10"), (0, math.inf), (math.nan, 1), (0, 1j), ("2024-01-01", None)])
def test_non_datetime_non_numbers_still_rejected__tc_fix1_r2_neg_003(limits: tuple[Any, Any]) -> None:
    """TC-FIX1-R2-NEG-003: widening to datetimes does not admit anything else."""
    with pytest.raises(PlotRequestError) as info:
        validate_axis_limits(limits, scale="linear", axis="x")
    assert info.value.reason == INVALID


# --- R-3: legacy individual y labels -----------------------------------------------------

# Base (a76838ec) labels, probed through plot_from_dataframe(return_fig=True).
BASE_LABEL_CASES = [
    ("same_unit", pd.DataFrame({"t (s)": [0, 1, 2], "a (V)": [1, 2, 3], "b (V)": [3, 2, 1]}), {},
     [("plot.png", "A (V)"), ("plot_a_(v).png", "A (V)"), ("plot_b_(v).png", "A (V)")]),
    ("unitless", pd.DataFrame({"x": [0, 1, 2], "a": [1, 2, 3], "b": [3, 2, 1]}), {},
     [("plot.png", "A"), ("plot_a.png", "A"), ("plot_b.png", "A")]),
    ("unitless_and_unit", pd.DataFrame({"t (s)": [0, 1, 2], "a": [1, 2, 3], "b (V)": [3, 2, 1]}), {},
     [("plot.png", "A"), ("plot_a.png", "A"), ("plot_b_(v).png", "A")]),
    ("multi_x", pd.DataFrame({"t1 (s)": [0, 1, 2], "a (V)": [1, 2, 3], "t2 (s)": [0, 1, 2], "b (V)": [3, 2, 1]}),
     {"x_col": [0, 2], "y_cols": [1, 3]},
     [("plot.png", "A (V)"), ("plot_a_(v).png", "A (V)"), ("plot_b_(v).png", "A (V)")]),
    ("multi_x_unitless", pd.DataFrame({"t1": [0, 1, 2], "a": [1, 2, 3], "t2": [0, 1, 2], "b": [3, 2, 1]}),
     {"x_col": [0, 2], "y_cols": [1, 3]},
     [("plot.png", "A"), ("plot_a.png", "A"), ("plot_b.png", "A")]),
    # Base rejected duplicate headers by name; positions give the same single label.
    ("duplicate_header", pd.DataFrame([[0, 1, 3, 5], [1, 2, 2, 6]], columns=["t (s)", "v (V)", "v (V)", "w (V)"]),
     {"x_col": 0, "y_cols": [1, 2, 3]},
     [("plot.png", "V (V)"), ("plot_v_(v)_s000.png", "V (V)"), ("plot_v_(v)_s001.png", "V (V)"), ("plot_w_(v).png", "V (V)")]),
]


@pytest.mark.parametrize(("name", "df", "kwargs", "expected"), BASE_LABEL_CASES, ids=[case[0] for case in BASE_LABEL_CASES])
def test_individual_y_labels_match_base__tc_fix1_r3_ep_001(
    tmp_path: Path, name: str, df: pd.DataFrame, kwargs: dict[str, Any], expected: list[tuple[str, str]],
) -> None:
    """TC-FIX1-R3-EP-001: without mixed units every figure keeps the base y label."""
    # Given/When: the legacy facade without y_label
    figures = _figures(df, tmp_path / name, **kwargs)
    # Then: base file names and y labels
    assert _labels(figures) == expected


def test_mixed_units_keep_ic6_labels__tc_fix1_r3_ep_002(tmp_path: Path) -> None:
    """TC-FIX1-R3-EP-002 (control): IC-6 still applies to mixed units."""
    # Given: V + A
    df = pd.DataFrame({"t (s)": [0, 1, 2], "a (V)": [1, 2, 3], "b (A)": [3, 2, 1]})
    # When/Then: joined overlay label, own-column individual labels
    assert _labels(_figures(df, tmp_path)) == [("plot.png", "A (V) / B (A)"), ("plot_a_(v).png", "A (V)"), ("plot_b_(a).png", "B (A)")]


def test_explicit_y_label_used_everywhere__tc_fix1_r3_bv_001(tmp_path: Path) -> None:
    """TC-FIX1-R3-BV-001: an explicit y_label is used on every figure."""
    df = pd.DataFrame({"t (s)": [0, 1, 2], "a (V)": [1, 2, 3], "b (A)": [3, 2, 1]})
    assert [label for _, label in _labels(_figures(df, tmp_path, y_label="Signal"))] == ["Signal"] * 3


# --- R-4: render_individual for any column ----------------------------------------------


def _frame_r4() -> pd.DataFrame:
    return pd.DataFrame(
        {"t (s)": [0, 1, 2], "a (V)": [1, 2, 3], "b (V)": [3, 2, 1], "t2 (s)": [5, 6, 7], "d": ["Charge", "Charge", "Discharge"]},
    )


def _drawn(fig: Any) -> tuple[str, str, str, list[tuple[list[float], list[float]]]]:
    ax = fig.axes[0]
    lines = [([float(v) for v in line.get_xdata()], [float(v) for v in line.get_ydata()]) for line in ax.lines]
    return ax.get_title(), ax.get_xlabel(), ax.get_ylabel(), lines


@pytest.mark.parametrize(
    ("config", "column", "position", "expected"),
    [
        (PlotConfig(x_col=0, y_cols=[1], title="T"), 2, None, ("T - B", "X", "Y", [([0, 1, 2], [3, 2, 1])])),
        (PlotConfig(x_col=0, y_cols=[1], y_axis=AxisConfig(label="Volt", unit="V")), 2, None, ("Plot - B", "X", "Volt (V)", [([0, 1, 2], [3, 2, 1])])),
    ],
)
def test_render_individual_draws_column_outside_y_cols__tc_fix1_r4_ep_001(
    config: PlotConfig, column: int, position: int | None, expected: tuple[Any, ...],
) -> None:
    """TC-FIX1-R4-EP-001: base drew any column whenever x_col was set."""
    # Given/When
    fig = MatplotlibRenderer().render_individual(_frame_r4(), config, column, position)
    # Then: base title, labels and data
    assert _drawn(fig) == expected


@pytest.mark.parametrize(
    ("column", "position", "expected"),
    [
        (2, 0, ("Plot - B", "X", "Y", [([0, 1, 2], [3, 2, 1])])),
        (1, 1, ("Plot - A", "X", "Y", [([5, 6, 7], [1, 2, 3])])),
        (2, 5, ("Plot - B", "X", "Y", [([0, 1, 2], [3, 2, 1])])),
    ],
)
def test_render_individual_uses_the_x_of_the_position__tc_fix1_r4_ep_002(column: int, position: int, expected: tuple[Any, ...]) -> None:
    """TC-FIX1-R4-EP-002: x follows series_position, the first x beyond the x list."""
    # Given: two x columns paired with two y columns
    config = PlotConfig(x_col=[0, 3], y_cols=[1, 2])
    # When
    fig = MatplotlibRenderer().render_individual(_frame_r4(), config, column, position)
    # Then
    assert _drawn(fig) == expected


def test_render_individual_uses_the_direction_of_the_position__tc_fix1_r4_ep_003() -> None:
    """TC-FIX1-R4-EP-003: the direction column of the position splits the series."""
    config = PlotConfig(x_col=0, y_cols=[1], direction_cols=[4])
    title, _, _, lines = _drawn(MatplotlibRenderer().render_individual(_frame_r4(), config, 2, 0))
    assert title == "Plot - B"
    assert lines == [([0, 1], [3, 2]), ([2], [1])]


@pytest.mark.parametrize(("config", "match"), [(PlotConfig(x_col=0, y_cols=None), "y_cols"), (PlotConfig(x_col=None, y_cols=[1]), "x_col")])
def test_render_individual_requires_columns__tc_fix1_r4_neg_001(config: PlotConfig, match: str) -> None:
    """TC-FIX1-R4-NEG-001: x_col and y_cols stay required, nothing left open."""
    before = set(plt.get_fignums())
    with pytest.raises(ValueError, match=match):
        MatplotlibRenderer().render_individual(_frame_r4(), config, 1)
    assert set(plt.get_fignums()) == before


def test_render_individual_column_outside_frame__tc_fix1_r4_neg_002_v2_0() -> None:
    """TC-FIX1-R4-NEG-002 (IC-15): a column the frame does not have fails before a figure exists.

    v1 raised ``IndexError`` from pandas; v2 raises ``PlotRequestError`` (a ``ValueError``).
    """
    before = set(plt.get_fignums())
    with pytest.raises(PlotRequestError) as info:
        MatplotlibRenderer().render_individual(_frame_r4(), PlotConfig(x_col=0, y_cols=[1]), 9)
    assert info.value.reason == "unknown_column"
    assert set(plt.get_fignums()) == before


# --- R-6: one mixed-unit warning, only with an overlay ------------------------------------


def _mixed() -> pd.DataFrame:
    return pd.DataFrame({"t (s)": [0, 1, 2], "a (V)": [1, 2, 3], "b (A)": [3, 2, 1]})


@pytest.mark.parametrize("html", [False, True])
def test_overlay_warns_once_per_call__tc_fix1_r6_ep_001(tmp_path: Path, html: bool) -> None:
    """TC-FIX1-R6-EP-001: one warning per call, also when the overlay is drawn twice (png + html)."""
    pytest.importorskip("plotly")
    with warnings.catch_warnings(record=True) as records:
        warnings.simplefilter("always")
        plot_from_dataframe(_mixed(), tmp_path, html=html)
    graph = _graph_warnings(records)
    assert len(graph) == 1
    assert "share one overlay y axis" in graph[0]


@pytest.mark.parametrize("html", [False, True])
def test_individual_mode_does_not_warn__tc_fix1_r6_neg_001(tmp_path: Path, html: bool) -> None:
    """TC-FIX1-R6-NEG-001: no overlay figure, no overlay warning."""
    pytest.importorskip("plotly")
    with warnings.catch_warnings(record=True) as records:
        warnings.simplefilter("always")
        plot_from_dataframe(_mixed(), tmp_path, mode="individual", html=html)
    assert _graph_warnings(records) == []
    assert sorted(path.name for path in tmp_path.iterdir()) == ["plot_a_(v).png", "plot_b_(a).png"]


def test_same_unit_overlay_does_not_warn__tc_fix1_r6_neg_002(tmp_path: Path) -> None:
    """TC-FIX1-R6-NEG-002: nothing mixes, nothing to warn about."""
    df = pd.DataFrame({"t (s)": [0, 1, 2], "a (V)": [1, 2, 3], "b (V)": [3, 2, 1]})
    with warnings.catch_warnings(record=True) as records:
        warnings.simplefilter("always")
        plot_from_dataframe(df, tmp_path)
    assert _graph_warnings(records) == []


def test_collect_individual_mode_does_not_warn__tc_fix1_r6_neg_003() -> None:
    """TC-FIX1-R6-NEG-003: the coordinator in individual mode produces no overlay."""
    with warnings.catch_warnings(record=True) as records:
        warnings.simplefilter("always")
        collections = collect_render_results(_mixed(), PlotConfig(x_col=0, y_cols=[1, 2]), PlotMode.INDIVIDUAL)
    assert collections.overlay == []
    assert len(collections.individual) == 2
    assert _graph_warnings(records) == []
