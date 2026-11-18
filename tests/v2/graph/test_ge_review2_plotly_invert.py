"""Fix round 2 / F4 (IC-16): ``AxisSpec(invert=True)`` reverses the HTML axes too.

v1 (develop/v2 8dea93cc) never read ``invert`` in the Plotly renderer, so HTML
output kept the axes in their normal direction while the images were inverted.
v2 reverses the Plotly axis with the same plan: no limits -> ``autorange="reversed"``;
both limits -> the reversed ``range``; one limit -> the reversed partial range with
the automatic side named by ``autorange`` (``"max reversed"`` / ``"min reversed"``),
so a ``None`` side stays automatic. Log-axis bounds stay in log10 units (IC-14).

EP table:
| TC | Partition | x axis / y axis | Expected layout (autorange, range) |
|----|-----------|-----------------|------------------------------------|
| TC-FIX2-F4-EP-001 | both inverted, no limits | invert / invert | ("reversed", None) on both |
| TC-FIX2-F4-EP-002 | both inverted, both limits | (0.5, 2.5) / (3.0, 3.5) | (None, (2.5, 0.5)) / (None, (3.5, 3.0)) |
| TC-FIX2-F4-EP-003 | inverted, one-sided limits | (1.0, None) / (None, 4.0) | ("max reversed", (None, 1.0)) / ("min reversed", (4.0, None)) |
| TC-FIX2-F4-EP-004 | inverted log axis | log (1, 100) / log, no limits | (None, (2.0, 0.0)) / ("reversed", None) |
| TC-FIX2-F4-EP-005 | inverted log axis, one-sided | log (None, 10) | ("min reversed", (1.0, None)) |
| TC-FIX2-F4-EP-006 | only x inverted | invert / plain | x reversed, y untouched |
| TC-FIX2-F4-EP-007 | legacy facade | plot_from_dataframe(html=True, invert_x, invert_y, ylim) | HTML JSON reversed on both axes |

Negative table:
| TC | Partition | x axis / y axis | Expected |
|----|-----------|-----------------|----------|
| TC-FIX2-F4-NEG-001 | not inverted, no limits | plain / plain | autorange and range unset |
| TC-FIX2-F4-NEG-002 | not inverted, both limits | (0.5, 2.5) | range as given, autorange unset |
| TC-FIX2-F4-NEG-003 | not inverted, one-sided | (1.0, None) | range [1.0, None], autorange unset |
| TC-FIX2-F4-NEG-004 | legacy facade without invert | plot_from_dataframe(html=True) | no "reversed" in the HTML |
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from rdetoolkit.graph.api.csv2graph import plot_from_dataframe
from rdetoolkit.graph.plan import PlotData, build_plot_plan
from rdetoolkit.graph.renderers.plotly_renderer import PlotlyRenderer
from rdetoolkit.graph.spec import AxisSpec, GraphSpec

pytest.importorskip("plotly")


def _frame() -> pd.DataFrame:
    return pd.DataFrame({"x": [1.0, 2.0, 3.0], "y": [3.0, 3.2, 3.4]})


_NEW_PLOT = re.compile(r'Plotly\.newPlot\(\s*"[^"]+",\s*')


def _html_axes(html: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """The x/y axis layout of the figure JSON in an HTML artifact (not the bundled plotly.js)."""
    match = _NEW_PLOT.search(html)
    assert match is not None
    decoder = json.JSONDecoder()
    _, end = decoder.raw_decode(html, match.end())
    layout_start = html.index("{", end)
    layout, _ = decoder.raw_decode(html, layout_start)
    return layout["xaxis"], layout["yaxis"]


def _axes(x_axis: AxisSpec, y_axis: AxisSpec) -> tuple[tuple[Any, Any], tuple[Any, Any]]:
    frame = _frame()
    plan = build_plot_plan(frame, GraphSpec(layout="overlay", x_axis=x_axis, y_axis=y_axis))
    fig = PlotlyRenderer().render(plan, plan.figures[0], PlotData(frames=(frame,)))
    return (fig.layout.xaxis.autorange, fig.layout.xaxis.range), (fig.layout.yaxis.autorange, fig.layout.yaxis.range)


@pytest.mark.parametrize(
    ("x_axis", "y_axis", "x_expected", "y_expected"),
    [
        (AxisSpec(invert=True), AxisSpec(invert=True), ("reversed", None), ("reversed", None)),
        (AxisSpec(invert=True, limits=(0.5, 2.5)), AxisSpec(invert=True, limits=(3.0, 3.5)), (None, (2.5, 0.5)), (None, (3.5, 3.0))),
        (AxisSpec(invert=True, limits=(1.0, None)), AxisSpec(invert=True, limits=(None, 4.0)), ("max reversed", (None, 1.0)), ("min reversed", (4.0, None))),
        (AxisSpec(scale="log", invert=True, limits=(1.0, 100.0)), AxisSpec(scale="log", invert=True), (None, (2.0, 0.0)), ("reversed", None)),
        (AxisSpec(scale="log", invert=True, limits=(None, 10.0)), AxisSpec(), ("min reversed", (1.0, None)), (None, None)),
        (AxisSpec(invert=True), AxisSpec(), ("reversed", None), (None, None)),
    ],
    ids=["ep001", "ep002", "ep003", "ep004", "ep005", "ep006"],
)
def test_inverted_axes_are_reversed_in_html_v2_0__tc_fix2_f4_ep_001_006(
    x_axis: AxisSpec, y_axis: AxisSpec, x_expected: tuple[Any, Any], y_expected: tuple[Any, Any],
) -> None:
    """TC-FIX2-F4-EP-001..006 (IC-16): Plotly reverses what Matplotlib inverts."""
    # Given/When
    x_layout, y_layout = _axes(x_axis, y_axis)
    # Then
    assert x_layout == x_expected
    assert y_layout == y_expected


def test_legacy_facade_html_is_reversed_v2_0__tc_fix2_f4_ep_007(tmp_path: Path) -> None:
    """TC-FIX2-F4-EP-007 (IC-16): invert_x / invert_y reach the HTML through the facade."""
    # Given/When
    plot_from_dataframe(_frame(), tmp_path, html=True, invert_x=True, invert_y=True, ylim=(None, 4.0), name="cell")
    # Then: x fully automatic and reversed, y reversed with the upper bound fixed
    x_layout, y_layout = _html_axes((tmp_path / "cell.html").read_text(encoding="utf-8"))
    assert (x_layout.get("autorange"), x_layout.get("range")) == ("reversed", None)
    assert (y_layout.get("autorange"), y_layout.get("range")) == ("min reversed", [4.0, None])
    assert sorted(path.name for path in tmp_path.iterdir()) == ["cell.html", "cell.png"]


@pytest.mark.parametrize(
    ("x_axis", "x_expected"),
    [
        (AxisSpec(), (None, None)),
        (AxisSpec(limits=(0.5, 2.5)), (None, (0.5, 2.5))),
        (AxisSpec(limits=(1.0, None)), (None, (1.0, None))),
    ],
    ids=["neg001", "neg002", "neg003"],
)
def test_axes_without_invert_are_unchanged__tc_fix2_f4_neg_001_003(x_axis: AxisSpec, x_expected: tuple[Any, Any]) -> None:
    """TC-FIX2-F4-NEG-001..003: no inversion, no autorange; limits as before (IC-14)."""
    x_layout, y_layout = _axes(x_axis, AxisSpec())
    assert x_layout == x_expected
    assert y_layout == (None, None)


def test_legacy_facade_without_invert_has_no_reversed_axis__tc_fix2_f4_neg_004(tmp_path: Path) -> None:
    """TC-FIX2-F4-NEG-004: the facade's HTML stays unreversed unless asked."""
    plot_from_dataframe(_frame(), tmp_path, html=True, ylim=(None, 4.0), name="cell")
    x_layout, y_layout = _html_axes((tmp_path / "cell.html").read_text(encoding="utf-8"))
    assert (x_layout.get("autorange"), x_layout.get("range")) == (None, None)
    assert (y_layout.get("autorange"), y_layout.get("range")) == (None, [None, 4.0])
