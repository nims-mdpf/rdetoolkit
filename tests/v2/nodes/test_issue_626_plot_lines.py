"""Issue #626: ``plot_lines`` axis limits, x scale and series from several frames.

| API | Partition / boundary | Expected | Test ID |
|-----|----------------------|----------|---------|
| ``plot_lines`` | ``xlim`` / ``ylim`` with both bounds | axes use exactly those limits | I626-EP-1 |
| ``plot_lines`` | one ``None`` bound | that bound stays automatic, the other is fixed | I626-BV-1 |
| ``plot_lines`` | limits / scale omitted | same limits and scale as before (auto, linear) | I626-EP-2 |
| ``plot_lines`` | ``xscale="log"`` | logarithmic x axis | I626-EP-3 |
| ``plot_lines`` | sequence of frames, ``x`` / ``y`` | one series per frame and y column, own x and length | I626-EP-4 |
| ``plot_lines`` | sequence of frames, ``pairs`` | pairs applied to every frame | I626-EP-5 |
| ``plot_lines`` | sequence of frames, ``labels`` | labels name the series in order | I626-EP-6 |
| ``plot_lines`` | sequence of frames, default axis labels | x column / repeated y columns named once | I626-EP-7 |
| ``plot_lines`` | empty sequence / frame without columns | ValueError, no figure leaked | I626-BV-2 |
| ``plot_lines`` | labels count across frames wrong | ValueError | I626-BV-3 |
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import pytest
from matplotlib.axes import Axes
from PIL import Image

from rdetoolkit.nodes import plot_lines
from rdetoolkit.testing import make_output_context


def _record_axes(monkeypatch: pytest.MonkeyPatch) -> dict[str, Axes]:
    observed: dict[str, Axes] = {}
    original = Axes.plot

    def record(axes: Axes, *args: Any, **kwargs: Any) -> Any:
        observed["axes"] = axes
        return original(axes, *args, **kwargs)

    monkeypatch.setattr(Axes, "plot", record)
    return observed


def _gaussian() -> pd.DataFrame:
    return pd.DataFrame({"q": [0.5, 1.0, 1.5, 2.0], "fit": [0.2, 1.0, 0.6, 0.1]})


def _regions() -> list[pd.DataFrame]:
    # Two regions of a multi-region XRD scan: own x values, own length.
    return [
        pd.DataFrame({"2theta": [10.0, 11.0, 12.0], "intensity": [5.0, 7.0, 6.0]}),
        pd.DataFrame({"2theta": [30.0, 31.0, 32.0, 33.0, 34.0], "intensity": [2.0, 9.0, 4.0, 3.0, 1.0]}),
    ]


# --- 1. axis limits and x scale ----------------------------------------------


def test_plot_lines_fixed_axis_limits__i626_ep_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """I626-EP-1: xlim / ylim with both bounds fix the axis range."""
    # Given: a fitted curve and a hook on the created axes
    observed = _record_axes(monkeypatch)
    # When: fixing both axis ranges
    path = plot_lines(_gaussian(), make_output_context(tmp_path), "fixed.png", x="q", xlim=(0, 3), ylim=(0, 1.5))
    # Then: the axes keep exactly those limits and an image is written
    axes = observed["axes"]
    assert axes.get_xlim() == (0, 3)
    assert axes.get_ylim() == (0, 1.5)
    with Image.open(path) as image:
        assert image.width > 10


@pytest.mark.parametrize(("option", "fixed_index"), [("xlim", 0), ("ylim", 1)])
@pytest.mark.parametrize("fixed_side", [0, 1])
def test_plot_lines_partial_axis_limits__i626_bv_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, option: str, fixed_index: int, fixed_side: int,
) -> None:
    """I626-BV-1: a None bound keeps matplotlib's automatic limit for that side."""
    # Given: the automatic limits of the same plot
    observed = _record_axes(monkeypatch)
    out = make_output_context(tmp_path)
    plot_lines(_gaussian(), out, "auto.png", x="q")
    auto = (observed["axes"].get_xlim(), observed["axes"].get_ylim())[fixed_index]
    # When: fixing only one side of one axis
    bound = -1.0 if fixed_side == 0 else 5.0
    limits = (bound, None) if fixed_side == 0 else (None, bound)
    plot_lines(_gaussian(), out, "partial.png", x="q", **{option: limits})
    # Then: that side is fixed and the other stays automatic
    partial = (observed["axes"].get_xlim(), observed["axes"].get_ylim())[fixed_index]
    assert partial[fixed_side] == bound
    assert partial[1 - fixed_side] == pytest.approx(auto[1 - fixed_side])


def test_plot_lines_default_limits_and_scale_unchanged__i626_ep_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """I626-EP-2: omitted limits and scale keep the automatic range and linear axes."""
    # Given: a reference figure drawn directly with matplotlib
    frame = _gaussian()
    reference_figure, reference = plt.subplots()
    reference.plot(frame["q"], frame["fit"])
    observed = _record_axes(monkeypatch)
    # When: plotting with the defaults and with explicit None limits
    out = make_output_context(tmp_path)
    plot_lines(frame, out, "default.png", x="q")
    default_axes = observed["axes"]
    plot_lines(frame, out, "none.png", x="q", xlim=None, ylim=None)
    none_axes = observed["axes"]
    # Then: both match matplotlib's automatic limits on linear axes
    try:
        for axes in (default_axes, none_axes):
            assert axes.get_xlim() == pytest.approx(reference.get_xlim())
            assert axes.get_ylim() == pytest.approx(reference.get_ylim())
            assert axes.get_xscale() == "linear"
            assert axes.get_yscale() == "linear"
    finally:
        plt.close(reference_figure)


def test_plot_lines_log_x_scale__i626_ep_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """I626-EP-3: xscale selects the horizontal axis scale, independent of yscale."""
    # Given: a hook on the created axes
    observed = _record_axes(monkeypatch)
    # When: plotting on a logarithmic x axis with a fixed lower bound
    plot_lines(_gaussian(), make_output_context(tmp_path), "logx.png", x="q", xscale="log", xlim=(0.1, None))
    # Then: only the x axis is logarithmic and the limit applies on that scale
    axes = observed["axes"]
    assert axes.get_xscale() == "log"
    assert axes.get_yscale() == "linear"
    assert axes.get_xlim()[0] == pytest.approx(0.1)


# --- 2. several frames -------------------------------------------------------


def test_plot_lines_frames_keep_own_x_and_length__i626_ep_4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """I626-EP-4: each frame contributes its own series with its own x values and length."""
    # Given: two regions of different length and x range
    regions = _regions()
    observed = _record_axes(monkeypatch)
    before = set(plt.get_fignums())
    # When: plotting the regions in one image
    path = plot_lines(regions, make_output_context(tmp_path), "regions.png", x="2theta", y="intensity")
    # Then: one line per region holds that region's data unchanged
    axes = observed["axes"]
    assert len(axes.lines) == len(regions)
    for line, region in zip(axes.lines, regions, strict=True):
        assert list(line.get_xdata()) == list(region["2theta"])
        assert list(line.get_ydata()) == list(region["intensity"])
    with Image.open(path) as image:
        assert image.width > 10
    assert set(plt.get_fignums()) == before


def test_plot_lines_frames_with_several_y_columns__i626_ep_4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """I626-EP-4: automatic y selection applies to each frame, in frame then column order."""
    # Given: frames whose y columns are chosen automatically
    frames = [pd.DataFrame({"x": [1, 2], "a": [3, 4], "b": [5, 6]}), pd.DataFrame({"x": [7, 8, 9], "a": [1, 2, 3]})]
    observed = _record_axes(monkeypatch)
    # When: plotting without a y selection
    plot_lines(frames, make_output_context(tmp_path), "auto_y.png", x="x")
    # Then: the series follow frame order, then column order
    assert [list(line.get_ydata()) for line in observed["axes"].lines] == [[3, 4], [5, 6], [1, 2, 3]]


def test_plot_lines_frames_with_pairs__i626_ep_5(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """I626-EP-5: pairs are applied to every frame."""
    # Given: frames with the same pair columns but different lengths
    frames = [pd.DataFrame({"x": [1, 2], "y": [3, 4]}), pd.DataFrame({"x": [5, 6, 7], "y": [8, 9, 10]})]
    observed = _record_axes(monkeypatch)
    # When: selecting the series as a labelled pair
    plot_lines(frames, make_output_context(tmp_path), "pairs.png", pairs=[("x", "y", "signal")])
    # Then: every frame contributes one line from that pair
    lines = observed["axes"].lines
    assert [list(line.get_xdata()) for line in lines] == [[1, 2], [5, 6, 7]]
    assert [line.get_label() for line in lines] == ["signal", "signal"]


def test_plot_lines_frames_labels_in_order__i626_ep_6(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """I626-EP-6: labels name the series across frames in order."""
    # Given: two regions
    observed = _record_axes(monkeypatch)
    # When: labelling each region
    plot_lines(_regions(), make_output_context(tmp_path), "labelled.png", x="2theta", y="intensity", labels=["low", "high"])
    # Then: lines and legend carry the labels in frame order
    axes = observed["axes"]
    assert [line.get_label() for line in axes.lines] == ["low", "high"]
    legend = axes.get_legend()
    assert legend is not None
    assert [text.get_text() for text in legend.get_texts()] == ["low", "high"]


def test_plot_lines_frames_default_axis_labels__i626_ep_7(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """I626-EP-7: the default axis labels name the x column and each y column once."""
    # Given: regions that repeat the same y column
    observed = _record_axes(monkeypatch)
    # When: plotting without axis labels
    plot_lines(_regions(), make_output_context(tmp_path), "axes.png", x="2theta", y="intensity")
    # Then: the y column is not repeated per frame, and series labels default to it
    axes = observed["axes"]
    assert axes.get_xlabel() == "2theta"
    assert axes.get_ylabel() == "intensity"
    assert [line.get_label() for line in axes.lines] == ["intensity", "intensity"]


def test_plot_lines_single_frame_in_list_matches_frame__i626_ep_4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """I626-EP-4: a one-element list plots like the frame itself."""
    # Given: one frame with two y columns
    frame = pd.DataFrame({"x": [1, 2], "a": [3, 4], "b": [5, 6]})
    observed = _record_axes(monkeypatch)
    out = make_output_context(tmp_path)
    # When: plotting the frame and a list holding it
    plot_lines(frame, out, "frame.png", x="x")
    direct = observed["axes"]
    plot_lines([frame], out, "list.png", x="x")
    listed = observed["axes"]
    # Then: series, labels and axis labels are the same
    assert [line.get_label() for line in listed.lines] == [line.get_label() for line in direct.lines]
    assert (listed.get_xlabel(), listed.get_ylabel()) == (direct.get_xlabel(), direct.get_ylabel())


@pytest.mark.parametrize("frames", [[], [pd.DataFrame({"x": [1], "y": [2]}), pd.DataFrame()]], ids=["empty-sequence", "frame-without-columns"])
def test_plot_lines_rejects_empty_frames__i626_bv_2(tmp_path: Path, frames: list[pd.DataFrame]) -> None:
    """I626-BV-2: no frames, or a frame without columns, is rejected before plotting."""
    # Given: an inconsistent frame sequence
    before = set(plt.get_fignums())
    # When / Then: plot_lines raises and leaves no figure open
    with pytest.raises(ValueError, match="column|frame"):
        plot_lines(frames, make_output_context(tmp_path), "bad.png")
    assert set(plt.get_fignums()) == before


def test_plot_lines_rejects_label_count_across_frames__i626_bv_3(tmp_path: Path) -> None:
    """I626-BV-3: labels count every series of every frame."""
    # Given: two regions (two series) and a single label
    # When / Then: the mismatch is reported
    with pytest.raises(ValueError, match="1 labels for 2 series"):
        plot_lines(_regions(), make_output_context(tmp_path), "bad.png", x="2theta", y="intensity", labels=["only"])
