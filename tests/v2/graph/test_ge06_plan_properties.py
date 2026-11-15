"""GE-06 (#712): property-based invariants of the normalized series plan.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| build_plot_plan | 1..3 frames x 2..5 columns, default selection | series count = frames x selections, frame-major, ids in order | TC-GE06-PBT-001 |
| PlotData.segments | direction cells drawn from {A, B, C, NA}, any filter | segment rows partition the kept rows (disjoint, complete, in order) | TC-GE06-PBT-002 |
| PlotPlan.to_dict | any generated plan | two builds give identical dicts and identical JSON | TC-GE06-PBT-003 |
| show_in_legend | labels drawn from a small alphabet | exactly one legend owner per distinct label among drawing series | TC-GE06-PBT-004 |
| compat.plan_from_config | random y selections and direction lists not longer than y | same series positions as the equivalent GraphSpec plan | TC-GE06-PBT-005 |

Negative table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| compat.plan_from_config | direction list longer than y | ValueError "cannot exceed" | TC-GE06-PBT-NEG-001 |
| compat.plan_from_config | x list neither 1 nor len(y) | ValueError "must be equal" | TC-GE06-PBT-NEG-002 |
"""

from __future__ import annotations

import json

import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from rdetoolkit.graph import compat
from rdetoolkit.graph.models import AxisConfig, PlotConfig
from rdetoolkit.graph.plan import PlotData, build_plot_plan
from rdetoolkit.graph.spec import GraphSpec, SeriesSpec

pytestmark = pytest.mark.property

_SETTINGS = settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])


def _frame(columns: int, rows: int = 3, offset: int = 0) -> pd.DataFrame:
    return pd.DataFrame({f"c{index}": [offset + index * 10 + row for row in range(rows)] for index in range(columns)})


@_SETTINGS
@given(frames=st.integers(min_value=1, max_value=3), columns=st.integers(min_value=2, max_value=5))
def test_series_count_is_frames_times_selections__tc_ge06_pbt_001(frames: int, columns: int) -> None:
    # Given: several frames of the same shape, default selection
    data = [_frame(columns, offset=100 * index) for index in range(frames)]
    # When
    plan = build_plot_plan(data, GraphSpec(layout="overlay"))
    # Then: frames x selections, frame-major, ids follow the position
    assert len(plan.series) == frames * (columns - 1)
    assert [entry.frame for entry in plan.series] == [index for index in range(frames) for _ in range(columns - 1)]
    assert [entry.series_id for entry in plan.series] == [f"s{index:03d}" for index in range(len(plan.series))]
    assert [entry.color_index for entry in plan.series] == list(range(len(plan.series)))


_CELLS = st.sampled_from(["A", "B", "C", None])


@_SETTINGS
@given(cells=st.lists(_CELLS, min_size=1, max_size=12), keep=st.lists(st.sampled_from(["A", "B", "C"]), max_size=3, unique=True))
def test_segments_partition_the_kept_rows__tc_ge06_pbt_002(cells: list[str | None], keep: list[str]) -> None:
    # Given: a direction column with random cells and a random filter
    frame = pd.DataFrame({"t": list(range(len(cells))), "v": [float(index) for index in range(len(cells))], "d": cells})
    plan = build_plot_plan(frame, GraphSpec(series=(SeriesSpec(y=1, direction=2),), direction_filter=tuple(keep)))
    # When
    segments = PlotData(frames=(frame,)).segments(plan.series[0])
    # Then: one segment per planned direction, in first-appearance order
    assert tuple(direction for direction, _, _ in segments) == plan.series[0].directions
    kept = [index for index, cell in enumerate(cells) if cell is not None and (not keep or cell in keep)]
    drawn = [int(x) for _, xs, _ in segments for x in xs]
    # Then: disjoint and complete, each segment keeps row order
    assert sorted(drawn) == kept
    assert len(drawn) == len(set(drawn))
    for direction, xs, ys in segments:
        assert [cells[int(x)] for x in xs] == [direction] * len(xs)
        assert list(ys) == [float(x) for x in xs]
        assert list(xs) == sorted(xs)


@_SETTINGS
@given(columns=st.integers(min_value=2, max_value=5), layout=st.sampled_from(["auto", "overlay", "individual", "both"]))
def test_to_dict_is_deterministic__tc_ge06_pbt_003(columns: int, layout: str) -> None:
    # Given/When: the same request planned twice
    first = build_plot_plan(_frame(columns), GraphSpec(layout=layout))  # type: ignore[arg-type]
    second = build_plot_plan(_frame(columns), GraphSpec(layout=layout))  # type: ignore[arg-type]
    # Then
    assert first.to_dict() == second.to_dict()
    assert json.dumps(first.to_dict(), sort_keys=True) == json.dumps(second.to_dict(), sort_keys=True)
    assert first == second


@_SETTINGS
@given(
    labels=st.lists(st.sampled_from(["a", "b", "c"]), min_size=1, max_size=6),
    filtered=st.lists(st.booleans(), min_size=6, max_size=6),
)
def test_one_legend_owner_per_label__tc_ge06_pbt_004(labels: list[str], filtered: list[bool]) -> None:
    # Given: series with repeated labels; some lose every row to the direction filter
    frame = pd.DataFrame({"t": [0, 1], "y": [1, 2], "keep": ["A", "A"], "drop": ["B", "B"]})
    series = tuple(
        SeriesSpec(y=1, direction=3 if filtered[index] else 2, label=label) for index, label in enumerate(labels)
    )
    # When
    plan = build_plot_plan(frame, GraphSpec(layout="overlay", series=series, direction_filter=("A",)))
    # Then: exactly the first drawing series of each label owns the legend entry
    owners: dict[str, str] = {}
    for entry in plan.series:
        if entry.directions and entry.label not in owners:
            owners[entry.label] = entry.series_id
    assert {entry.series_id for entry in plan.series if entry.show_in_legend} == set(owners.values())
    relabelled = plan.with_labels(list(reversed(labels)))
    assert sum(entry.show_in_legend for entry in relabelled.series) == len(
        {entry.label for entry in relabelled.series if entry.directions},
    )


def _config(y_cols: list[int], direction_cols: list[int | None] | None, x_col: object = 0) -> PlotConfig:
    return PlotConfig(x_col=x_col, y_cols=y_cols, direction_cols=direction_cols, x_axis=AxisConfig(label="x"), y_axis=AxisConfig(label="y"))  # type: ignore[arg-type]


@_SETTINGS
@given(data=st.data())
def test_compat_plan_matches_the_spec_plan__tc_ge06_pbt_005(data: st.DataObject) -> None:
    # Given: a random legacy selection on a five-column frame
    y_cols = data.draw(st.lists(st.integers(min_value=1, max_value=4), min_size=1, max_size=4))
    directions = data.draw(st.lists(st.one_of(st.none(), st.integers(min_value=1, max_value=4)), max_size=len(y_cols)))
    frame = _frame(5)
    # When: the compat plan and the equivalent spec plan are built
    plan = compat.plan_from_config(frame, _config(y_cols, directions or None), label_of=compat.legacy_mpl_label)
    padded = [*directions, *([None] * (len(y_cols) - len(directions)))]
    spec = GraphSpec(layout="both", series=tuple(SeriesSpec(y=y, x=0, direction=d) for y, d in zip(y_cols, padded, strict=True)))
    expected = build_plot_plan(frame, spec)
    # Then: identical series positions and directions
    def key(entry: object) -> tuple[object, ...]:
        return (entry.x_index, entry.y_index, entry.direction_index, entry.directions)  # type: ignore[attr-defined]

    assert [key(entry) for entry in plan.series] == [key(entry) for entry in expected.series]


@_SETTINGS
@given(y_count=st.integers(min_value=1, max_value=3), extra=st.integers(min_value=1, max_value=2))
def test_compat_rejects_too_many_directions__tc_ge06_pbt_neg_001(y_count: int, extra: int) -> None:
    # Given/When/Then
    config = _config([1] * y_count, [2] * (y_count + extra))
    with pytest.raises(ValueError, match="cannot exceed"):
        compat.plan_from_config(_frame(4), config, label_of=compat.legacy_mpl_label)


@_SETTINGS
@given(y_count=st.integers(min_value=1, max_value=3), x_count=st.integers(min_value=2, max_value=5))
def test_compat_rejects_unpaired_x__tc_ge06_pbt_neg_002(y_count: int, x_count: int) -> None:
    # Given: an x list that is neither one column nor one per y
    if x_count == y_count:
        x_count += 1
    config = _config([1] * y_count, None, x_col=[0] * x_count)
    # When/Then
    with pytest.raises(ValueError, match="must be equal"):
        compat.plan_from_config(_frame(4), config, label_of=compat.legacy_mpl_label)
