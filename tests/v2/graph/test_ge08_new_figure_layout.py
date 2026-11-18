"""GE-08 (#714) regression: ``new_figure(tight_layout=False)`` means "no house tight layout".

``matplotlib.figure.Figure(tight_layout=False)`` selects the tight layout engine
(any non-``None`` value does), so passing the flag straight through made
``tight_layout=False`` behave like ``True``. ``False`` now leaves the layout to
rcParams, exactly like ``plt.figure()`` / ``plt.subplots()``.

| API | Partition / boundary | Expected | Test ID |
|-----|----------------------|----------|---------|
| new_figure | default (tight_layout=True) | TightLayoutEngine (unchanged) | TC-GE08-RT-EP-001 |
| new_figure | tight_layout=False, default rcParams | no layout engine | TC-GE08-RT-NEG-001 |
| new_figure | tight_layout=False, figure.autolayout=True | follows rcParams like plt.subplots | TC-GE08-RT-NEG-002 |
| new_figure | tight_layout=False | PNG identical to plt.subplots, not to a tight figure | TC-GE08-RT-NEG-003 |
"""

from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.layout_engine import TightLayoutEngine

from rdetoolkit.graph.renderers.mpl_runtime import export_figure, new_figure


def _draw(ax: object) -> None:
    ax.plot([0, 1, 2], [3.0, 1.0, 2.0])  # type: ignore[attr-defined]
    ax.set_xlabel("a long x label that the tight layout would make room for")  # type: ignore[attr-defined]


def test_new_figure_default_is_tight__tc_ge08_rt_ep_001() -> None:
    """TC-GE08-RT-EP-001: the engine default stays the tight layout."""
    # Given / When
    fig, _ = new_figure((4.0, 3.0))
    # Then
    assert isinstance(fig.get_layout_engine(), TightLayoutEngine)


def test_new_figure_without_tight_layout_has_no_engine__tc_ge08_rt_neg_001() -> None:
    """TC-GE08-RT-NEG-001: tight_layout=False must not select the tight engine."""
    # Given / When: default rcParams (figure.autolayout is False)
    fig, _ = new_figure((4.0, 3.0), tight_layout=False)
    # Then: no layout engine, like plt.subplots
    assert fig.get_layout_engine() is None
    assert plt.get_fignums() == []


def test_new_figure_without_tight_layout_follows_rcparams__tc_ge08_rt_neg_002() -> None:
    """TC-GE08-RT-NEG-002: with figure.autolayout the layout follows rcParams, as pyplot does."""
    # Given: rcParams asking for an automatic layout
    with mpl.rc_context({"figure.autolayout": True}):
        # When
        fig, _ = new_figure((4.0, 3.0), tight_layout=False)
        reference, _ = plt.subplots(figsize=(4.0, 3.0))
        # Then: the same engine type as a pyplot figure
        assert type(fig.get_layout_engine()) is type(reference.get_layout_engine())
        plt.close(reference)


def test_new_figure_without_tight_layout_renders_like_subplots__tc_ge08_rt_neg_003() -> None:
    """TC-GE08-RT-NEG-003: the image equals plt.subplots and differs from a tight figure."""
    # Given: the same drawing on three figures
    loose, loose_ax = new_figure((4.0, 3.0), tight_layout=False)
    tight, tight_ax = new_figure((4.0, 3.0))
    reference, reference_ax = plt.subplots(figsize=(4.0, 3.0))
    for ax in (loose_ax, tight_ax, reference_ax):
        _draw(ax)
    # When: exporting the full canvas
    images = [export_figure(fig, "png", dpi=50, bbox_inches=None) for fig in (loose, tight, reference)]
    plt.close(reference)
    # Then
    assert images[0] == images[2]
    assert images[0] != images[1]
