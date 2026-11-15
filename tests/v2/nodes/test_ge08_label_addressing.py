"""Fix round 1 / R-1: plot nodes address columns by exact label, also for int labels.

Before the Graph Engine, ``plot_lines`` / ``plot_scatter`` read ``df[x]`` and
``df[y]``: a column was always addressed by its label. Routing the nodes through
``GraphSpec`` (where an ``int`` is a 0-based position) must not turn an integer
label into a position. Labels are resolved by the one planner helper
``graph.plan.column_position`` (exact label -> ``unknown_column`` /
``ambiguous_column``); the node keeps no resolver of its own.

EP table:
| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-FIX1-R1-EP-001 | plot_lines, int labels | columns 1, 0, 5; x=1, y=[0] | label-0 values drawn against label-1 values, labels "1" / "0" |
| TC-FIX1-R1-EP-002 | plot_lines, int label beyond the column count | x=1, y=[5] | label-5 values drawn (5 is not a position) |
| TC-FIX1-R1-EP-003 | plot_scatter, int labels | x=1, y=0 and x=1, y=5 | offsets are (label-1, label-0) / (label-1, label-5) |
| TC-FIX1-R1-EP-004 | plot_lines, pairs of int labels over two frames with different column order | pairs=[(1, 0)] | each frame draws its own label-0 against label-1 |
| TC-FIX1-R1-EP-005 | plan helper | column_position(frame, 5, "y") | 2 |

Negative table:
| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-FIX1-R1-NEG-001 | plot_lines, int that is a position but not a label | columns 1, 0, 5; y=[2] | PlotRequestError unknown_column, nothing written |
| TC-FIX1-R1-NEG-002 | plot_scatter, int that is a position but not a label | x=2 | PlotRequestError unknown_column, nothing written |
| TC-FIX1-R1-NEG-003 | plot_lines, duplicated int label | columns 0, 0 | PlotRequestError ambiguous_column |
| TC-FIX1-R1-NEG-004 | plan helper, missing / duplicated label | column_position | PlotRequestError unknown_column / ambiguous_column |
| TC-FIX1-R1-NEG-005 | plan helper, bool vs int label | label True on column 1 | unknown_column (True is not the label 1) |
| TC-FIX1-R1-NEG-007 | plan helper, a label whose == cannot be a bool | columns pd.NA, "a" | the NA column is skipped, "a" resolves; NA itself is unknown |
| TC-FIX1-R1-NEG-006 | source | nodes/plot.py | resolves through graph.plan.column_position only |
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from matplotlib.axes import Axes

import rdetoolkit.nodes.plot as plot_module
from rdetoolkit.graph import PlotRequestError
from rdetoolkit.graph.plan import column_position
from rdetoolkit.nodes import plot_lines, plot_scatter
from rdetoolkit.testing import make_output_context


def _int_frame() -> pd.DataFrame:
    return pd.DataFrame({1: [10, 11, 12], 0: [20, 21, 22], 5: [30, 31, 32]})


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


def _xy(line: Any) -> tuple[list[float], list[float]]:
    return [float(v) for v in line.get_xdata()], [float(v) for v in line.get_ydata()]


def _files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file())


@pytest.mark.parametrize(("y", "expected_y"), [(0, [20.0, 21.0, 22.0]), (5, [30.0, 31.0, 32.0])])
def test_plot_lines_int_labels_are_labels__tc_fix1_r1_ep_001_002(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, y: int, expected_y: list[float],
) -> None:
    """TC-FIX1-R1-EP-001/002: an int x / y names the column carrying that label."""
    # Given: a frame whose labels (1, 0, 5) differ from their positions
    observed = _record_axes(monkeypatch)
    # When: plotting label y against label 1
    path = plot_lines(_int_frame(), make_output_context(tmp_path), "a.png", x=1, y=[y])  # type: ignore[arg-type]
    # Then: the label columns are drawn, and the default labels name them
    (line,) = observed[-1].lines
    assert _xy(line) == ([10.0, 11.0, 12.0], expected_y)
    assert line.get_label() == str(y)
    assert observed[-1].get_xlabel() == "1"
    assert observed[-1].get_ylabel() == str(y)
    assert _files(tmp_path) == [path]


@pytest.mark.parametrize(("y", "expected_y"), [(0, [20.0, 21.0, 22.0]), (5, [30.0, 31.0, 32.0])])
def test_plot_scatter_int_labels_are_labels__tc_fix1_r1_ep_003(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, y: int, expected_y: list[float],
) -> None:
    """TC-FIX1-R1-EP-003: plot_scatter addresses int labels the same way."""
    # Given: the int-labelled frame
    observed = _record_axes(monkeypatch)
    # When: scattering label y against label 1
    plot_scatter(_int_frame(), make_output_context(tmp_path), "s.png", x=1, y=y)  # type: ignore[arg-type]
    # Then: the offsets are (label-1, label-y) and the axis labels name the labels
    axes = observed[-1]
    offsets = axes.collections[0].get_offsets()
    assert [list(map(float, row)) for row in offsets] == [[x, v] for x, v in zip([10.0, 11.0, 12.0], expected_y, strict=True)]
    assert (axes.get_xlabel(), axes.get_ylabel()) == ("1", str(y))


def test_plot_lines_int_label_pairs_resolve_per_frame__tc_fix1_r1_ep_004(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-FIX1-R1-EP-004: each frame resolves the labels in its own column order."""
    # Given: two frames carrying labels 1 and 0 in different positions
    first = _int_frame()
    second = pd.DataFrame({0: [7, 8], 1: [1, 2]})
    observed = _record_axes(monkeypatch)
    # When: plotting the pair (1, 0) of both frames
    plot_lines([first, second], make_output_context(tmp_path), "p.png", pairs=[(1, 0)])  # type: ignore[list-item]
    # Then: frame-major, each frame's label-0 against its label-1
    assert [_xy(line) for line in observed[-1].lines] == [
        ([10.0, 11.0, 12.0], [20.0, 21.0, 22.0]),
        ([1.0, 2.0], [7.0, 8.0]),
    ]


def test_column_position_resolves_exact_label__tc_fix1_r1_ep_005() -> None:
    """TC-FIX1-R1-EP-005: the shared helper maps a label to its position."""
    # Given/When/Then: label 5 sits at position 2, label "1"-free frame keeps str labels
    assert column_position(_int_frame(), 5, "y") == 2
    assert column_position(pd.DataFrame({"t": [0], "v": [1]}), "v", "y") == 1


def test_plot_lines_position_is_not_a_label__tc_fix1_r1_neg_001(tmp_path: Path) -> None:
    """TC-FIX1-R1-NEG-001: 2 is a valid position but no column is labelled 2."""
    # Given/When
    with pytest.raises(PlotRequestError) as info:
        plot_lines(_int_frame(), make_output_context(tmp_path), "a.png", x=1, y=[2])  # type: ignore[arg-type]
    # Then
    assert info.value.reason == "unknown_column"
    assert _files(tmp_path) == []


def test_plot_scatter_position_is_not_a_label__tc_fix1_r1_neg_002(tmp_path: Path) -> None:
    """TC-FIX1-R1-NEG-002: plot_scatter rejects a bare position too."""
    # Given/When
    with pytest.raises(PlotRequestError) as info:
        plot_scatter(_int_frame(), make_output_context(tmp_path), "s.png", x=2, y=0)  # type: ignore[arg-type]
    # Then
    assert info.value.reason == "unknown_column"
    assert _files(tmp_path) == []


def test_plot_lines_duplicated_int_label_is_ambiguous__tc_fix1_r1_neg_003(tmp_path: Path) -> None:
    """TC-FIX1-R1-NEG-003: a label carried by several columns is ambiguous."""
    # Given: two columns labelled 0
    frame = pd.DataFrame([[1, 2, 3]], columns=[1, 0, 0])
    # When/Then
    with pytest.raises(PlotRequestError) as info:
        plot_lines(frame, make_output_context(tmp_path), "a.png", x=1, y=[0])  # type: ignore[arg-type]
    assert info.value.reason == "ambiguous_column"
    assert _files(tmp_path) == []


@pytest.mark.parametrize(
    ("columns", "label", "reason"),
    [([1, 0, 5], 2, "unknown_column"), (["a", "b"], "c", "unknown_column"), ([0, 0], 0, "ambiguous_column"), (["v", "v"], "v", "ambiguous_column")],
)
def test_column_position_rejects_missing_and_duplicate__tc_fix1_r1_neg_004(columns: list[Any], label: Any, reason: str) -> None:
    """TC-FIX1-R1-NEG-004: no position fallback, no guessing between duplicates."""
    # Given: a frame with the given labels
    frame = pd.DataFrame([list(range(len(columns)))], columns=columns)
    # When/Then
    with pytest.raises(PlotRequestError) as info:
        column_position(frame, label, "y")
    assert info.value.reason == reason


def test_column_position_bool_is_not_int_label__tc_fix1_r1_neg_005() -> None:
    """TC-FIX1-R1-NEG-005: True == 1 in Python, but True is not the label 1."""
    # Given: a frame labelled 0, 1
    frame = pd.DataFrame([[1, 2]], columns=[0, 1])
    # When/Then
    with pytest.raises(PlotRequestError) as info:
        column_position(frame, True, "y")
    assert info.value.reason == "unknown_column"


def test_column_position_skips_incomparable_labels__tc_fix1_r1_neg_007() -> None:
    """TC-FIX1-R1-NEG-007: ``pd.NA == "a"`` has no truth value; such a column never matches."""
    # Given: a frame whose first label is pd.NA
    frame = pd.DataFrame([[1, 2]], columns=pd.Index([pd.NA, "a"], dtype=object))
    # When/Then: the other label still resolves, and NA is not addressable by label
    assert column_position(frame, "a", "y") == 1
    with pytest.raises(PlotRequestError) as info:
        column_position(frame, pd.NA, "y")
    assert info.value.reason == "unknown_column"


def test_nodes_resolve_through_the_planner_helper__tc_fix1_r1_neg_006() -> None:
    """TC-FIX1-R1-NEG-006: one resolver, owned by the planner."""
    # Given: the node module source
    source = inspect.getsource(plot_module)
    # When/Then: it uses the planner helper and indexes no column by name itself
    assert plot_module.column_position is column_position
    assert "frame[" not in source
    assert ".get_loc(" not in source
    assert "columns.index(" not in source
