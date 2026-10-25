"""Property-based tests for rdetoolkit.graph.renderers.matplotlib_renderer._resolve_legend_policy.

Tests invariants of the pure legend-policy resolution function using Hypothesis.
This complements the example-based tests in tests/test_matplotlib_renderer.py.
"""

from __future__ import annotations

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, strategies as st

from rdetoolkit.graph.renderers.matplotlib_renderer import _resolve_legend_policy

_NON_AUTO_POLICIES = ("legacy", "inside", "outside_right", "outside_bottom", "hide")


@pytest.mark.property
class TestResolveLegendPolicyProperties:
    @given(
        policy=st.sampled_from(_NON_AUTO_POLICIES),
        count=st.integers(min_value=0, max_value=1000),
        threshold=st.integers(min_value=0, max_value=100),
        max_items=st.one_of(st.none(), st.integers(min_value=0, max_value=1000)),
    )
    def test_non_auto_is_always_pass_through(self, policy, count, threshold, max_items):
        """Property: any non-"auto" policy is returned unchanged."""
        # Given: a concrete (non-"auto") policy and arbitrary count/threshold/max_items
        # When: resolving
        result = _resolve_legend_policy(policy, count, threshold, max_items)
        # Then: the input policy is echoed back verbatim
        assert result == policy

    @given(
        count=st.integers(min_value=0, max_value=1000),
        threshold=st.integers(min_value=0, max_value=100),
        max_items=st.one_of(st.none(), st.integers(min_value=0, max_value=1000)),
    )
    def test_auto_without_bottom_threshold_never_resolves_to_outside_bottom(self, count, threshold, max_items):
        """Property: with bottom_threshold unset, "auto" never picks "outside_bottom"."""
        # Given: policy="auto" with arbitrary count/threshold/max_items and the
        #        default bottom_threshold (None = bottom switch disabled)
        # When: resolving
        result = _resolve_legend_policy("auto", count, threshold, max_items)
        # Then: result is one of the three placements reachable without the switch
        assert result in ("inside", "outside_right", "hide")

    @given(
        count=st.integers(min_value=0, max_value=1000),
        threshold=st.integers(min_value=0, max_value=100),
        max_items=st.one_of(st.none(), st.integers(min_value=0, max_value=1000)),
        bottom_threshold=st.one_of(st.none(), st.integers(min_value=0, max_value=1000)),
    )
    def test_auto_always_resolves_to_concrete_policy(self, count, threshold, max_items, bottom_threshold):
        """Property: "auto" always resolves to a concrete, non-"auto" policy."""
        # Given: policy="auto" with arbitrary parameters
        # When: resolving
        result = _resolve_legend_policy(
            "auto", count, threshold, max_items, bottom_threshold=bottom_threshold,
        )
        # Then: result is a concrete placement
        assert result in ("inside", "outside_right", "outside_bottom", "hide")

    @given(
        count=st.integers(min_value=1, max_value=1000),
        threshold=st.integers(min_value=0, max_value=100),
        bottom_threshold=st.integers(min_value=1, max_value=1000),
    )
    def test_auto_at_or_above_bottom_threshold_is_outside_bottom(self, count, threshold, bottom_threshold):
        """Property: reaching bottom_threshold resolves to "outside_bottom" (no cap)."""
        # Given: count at or above the bottom threshold and no max_items cap
        if count < bottom_threshold:
            return
        # When: resolving
        result = _resolve_legend_policy(
            "auto", count, threshold, None, bottom_threshold=bottom_threshold,
        )
        # Then: legend goes below the graph regardless of outside_threshold
        assert result == "outside_bottom"

    @given(
        count=st.integers(min_value=0, max_value=1000),
        threshold=st.integers(min_value=0, max_value=100),
    )
    def test_auto_zero_items_always_hides(self, count, threshold):
        """Property: zero legend items always resolve to "hide", regardless of max_items."""
        # Given: no filtered labels
        # When: resolving with any threshold and no cap
        result = _resolve_legend_policy("auto", 0, threshold, None)
        # Then: hidden
        assert result == "hide"

    @given(
        count=st.integers(min_value=1, max_value=1000),
        threshold=st.integers(min_value=0, max_value=100),
        max_items=st.integers(min_value=0, max_value=1000),
    )
    def test_auto_respects_max_items_cap(self, count, threshold, max_items):
        """Property: exceeding max_items always hides, even below the outside threshold."""
        # Given: count exceeds the configured cap
        if count <= max_items:
            return
        # When: resolving
        result = _resolve_legend_policy("auto", count, threshold, max_items)
        # Then: hidden regardless of threshold
        assert result == "hide"
