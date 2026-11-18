"""Fix round 2 / F2: ``render_individual`` without a position keeps the v1 x column.

v1 (develop/v2 8dea93cc, probed with ``git archive 8dea93cc src``) read an omitted
``series_position`` as position 0 for both the x column and the direction column,
whatever ``y_col_index`` was. Every pinned row below is the base output of
``MatplotlibRenderer().render_individual(df, config, column, position)`` on the
frame of ``_frame()`` (title, x label, y label, drawn lines).

EP table (explicit positions and single-x controls, unchanged by the fix):
| TC | Partition | config / column / position | Expected (base) |
|----|-----------|----------------------------|-----------------|
| TC-FIX2-F2-EP-001 | multi-x, explicit position 0 | x=[0,1], y=[2,3] / 3 / 0 | x = column 0 |
| TC-FIX2-F2-EP-002 | multi-x, explicit position 1 | x=[0,1], y=[2,3] / 3 / 1 | x = column 1 |
| TC-FIX2-F2-EP-003 | multi-x, planned pair | x=[0,1], y=[2,3] / 2 / 1 | x = column 1 |
| TC-FIX2-F2-EP-004 | single x, omitted / explicit | x=0, y=[2,3] / 3 / None, 1 | x = column 0 |
| TC-FIX2-F2-EP-005 | direction of an explicit position | dirs=[None,4] / 3 / 1 | split by column 4 |
| TC-FIX2-F2-EP-006 | csv2graph-style strategy call | IndividualStrategy, x=[0,1] | figure n uses x column n (explicit positions) |

Negative table (omitted position must not search the plan for the column):
| TC | Partition | config / column / position | Expected (base) |
|----|-----------|----------------------------|-----------------|
| TC-FIX2-F2-NEG-001 | multi-x, omitted, column planned at position 1 | x=[0,1], y=[2,3] / 3 / None | x = column 0, not column 1 |
| TC-FIX2-F2-NEG-002 | multi-x, omitted, column planned at position 0 | x=[0,1], y=[2,3] / 2 / None | x = column 0 |
| TC-FIX2-F2-NEG-003 | direction, omitted, column planned at position 1 | dirs=[None,4] / 3 / None | no direction split (position 0 has none) |
| TC-FIX2-F2-NEG-004 | omitted position with three x columns | x=[0,1,5], y=[2,3,6] / 6 / None | x = column 0 |
"""

from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import pytest

from rdetoolkit.graph.models import PlotConfig
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer
from rdetoolkit.graph.strategies.individual import IndividualStrategy

_MULTI = PlotConfig(x_col=[0, 1], y_cols=[2, 3])
_DIRS = PlotConfig(x_col=0, y_cols=[2, 3], direction_cols=[None, 4])


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {"x1": [1, 2, 3], "x2": [10, 20, 30], "y1": [4, 5, 6], "y2": [7, 8, 9], "d": ["Charge", "Charge", "Discharge"]},
    )


def _drawn(fig: Any) -> tuple[str, str, str, list[tuple[list[float], list[float]]]]:
    ax = fig.axes[0]
    lines = [([float(v) for v in line.get_xdata()], [float(v) for v in line.get_ydata()]) for line in ax.lines]
    plt.close(fig)
    return ax.get_title(), ax.get_xlabel(), ax.get_ylabel(), lines


_X0_Y2 = ("Plot - Y2", "X", "Y", [([1, 2, 3], [7, 8, 9])])
_X1_Y2 = ("Plot - Y2", "X", "Y", [([10, 20, 30], [7, 8, 9])])


@pytest.mark.parametrize(
    ("config", "column", "position", "expected"),
    [
        (_MULTI, 3, 0, _X0_Y2),
        (_MULTI, 3, 1, _X1_Y2),
        (_MULTI, 2, 1, ("Plot - Y1", "X", "Y", [([10, 20, 30], [4, 5, 6])])),
        (PlotConfig(x_col=0, y_cols=[2, 3]), 3, None, _X0_Y2),
        (PlotConfig(x_col=0, y_cols=[2, 3]), 3, 1, _X0_Y2),
        (_DIRS, 3, 1, ("Plot - Y2", "X", "Y", [([1, 2], [7, 8]), ([3], [9])])),
    ],
    ids=["ep001", "ep002", "ep003", "ep004-none", "ep004-explicit", "ep005"],
)
def test_explicit_positions_and_single_x_match_base__tc_fix2_f2_ep_001_005(
    config: PlotConfig, column: int, position: int | None, expected: tuple[Any, ...],
) -> None:
    """TC-FIX2-F2-EP-001..005: unchanged base outputs."""
    # Given/When
    drawn = _drawn(MatplotlibRenderer().render_individual(_frame(), config, column, position))
    # Then
    assert drawn == expected


def test_strategy_passes_explicit_positions__tc_fix2_f2_ep_006() -> None:
    """TC-FIX2-F2-EP-006: the csv2graph path pairs figure n with x column n."""
    # Given: the legacy individual strategy with two x columns
    strategy = IndividualStrategy(MatplotlibRenderer())
    # When
    results = strategy.render(_frame(), _MULTI)
    # Then
    assert results is not None
    assert [_drawn(item.figure)[3] for item in results] == [[([1, 2, 3], [4, 5, 6])], [([10, 20, 30], [7, 8, 9])]]


@pytest.mark.parametrize(
    ("config", "column", "expected"),
    [
        (_MULTI, 3, _X0_Y2),
        (_MULTI, 2, ("Plot - Y1", "X", "Y", [([1, 2, 3], [4, 5, 6])])),
        (_DIRS, 3, _X0_Y2),
    ],
    ids=["neg001", "neg002", "neg003"],
)
def test_omitted_position_means_position_zero__tc_fix2_f2_neg_001_003(
    config: PlotConfig, column: int, expected: tuple[Any, ...],
) -> None:
    """TC-FIX2-F2-NEG-001..003: ``None`` is position 0 for x and direction, always."""
    # Given/When
    drawn = _drawn(MatplotlibRenderer().render_individual(_frame(), config, column))
    # Then
    assert drawn == expected


def test_omitted_position_with_three_x_columns__tc_fix2_f2_neg_004() -> None:
    """TC-FIX2-F2-NEG-004: the last planned column is still drawn against x column 0."""
    frame = _frame().assign(x3=[100, 200, 300], y3=[0, 1, 0])
    config = PlotConfig(x_col=[0, 1, 5], y_cols=[2, 3, 6])
    _, _, _, lines = _drawn(MatplotlibRenderer().render_individual(frame, config, 6))
    assert lines == [([1, 2, 3], [0, 1, 0])]
