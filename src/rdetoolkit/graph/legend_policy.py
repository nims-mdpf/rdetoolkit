"""Legend placement policy resolution shared by all renderers."""

from __future__ import annotations

from typing import Literal

LegendPolicy = Literal["legacy", "auto", "inside", "outside_right", "outside_bottom", "hide"]
ResolvedLegendPolicy = Literal["legacy", "inside", "outside_right", "outside_bottom", "hide"]

VALID_LEGEND_POLICIES: tuple[str, ...] = (
    "legacy",
    "auto",
    "inside",
    "outside_right",
    "outside_bottom",
    "hide",
)


def resolve_legend_policy(
    policy: LegendPolicy,
    filtered_label_count: int,
    outside_threshold: int,
    max_items: int | None,
    bottom_threshold: int | None = None,
) -> ResolvedLegendPolicy:
    """Resolve a legend policy into a concrete, non-"auto" placement.

    Args:
        policy: Requested legend policy. Values other than "auto" are
            returned unchanged (pass-through), including "legacy".
        filtered_label_count: Number of de-duplicated, visible legend
            labels that would be rendered.
        outside_threshold: Item-count threshold above which "auto"
            switches to "outside_right" placement.
        max_items: Maximum number of legend items to display. When the
            item count exceeds this value, "auto" resolves to "hide".
            None means no upper bound.
        bottom_threshold: Item count at or above which "auto" switches to
            "outside_bottom" placement. None disables the bottom switch,
            in which case "auto" behaves as before (inside/outside_right).

    Returns:
        A concrete policy: "legacy", "inside", "outside_right",
        "outside_bottom", or "hide". Never returns "auto".

    Note:
        Precedence for "auto" resolution (checked in order):
        1. filtered_label_count == 0 -> "hide"
        2. max_items is not None and filtered_label_count > max_items -> "hide"
        3. bottom_threshold is not None and
           filtered_label_count >= bottom_threshold -> "outside_bottom"
        4. filtered_label_count > outside_threshold -> "outside_right"
        5. otherwise -> "inside"

        With the defaults (outside_threshold=8, bottom_threshold=21):
        1-8 items -> inside, 9-20 items -> outside_right,
        21+ items -> outside_bottom.

    Example:
        >>> resolve_legend_policy("auto", 3, outside_threshold=8, max_items=None)
        'inside'
        >>> resolve_legend_policy("auto", 12, outside_threshold=8, max_items=None)
        'outside_right'
        >>> resolve_legend_policy(
        ...     "auto", 25, outside_threshold=8, max_items=None, bottom_threshold=21)
        'outside_bottom'
        >>> resolve_legend_policy("auto", 25, outside_threshold=8, max_items=20)
        'hide'
        >>> resolve_legend_policy("outside_bottom", 3, outside_threshold=8, max_items=20)
        'outside_bottom'
    """
    if policy != "auto":
        return policy

    if filtered_label_count == 0:
        return "hide"
    if max_items is not None and filtered_label_count > max_items:
        return "hide"
    if bottom_threshold is not None and filtered_label_count >= bottom_threshold:
        return "outside_bottom"
    if filtered_label_count > outside_threshold:
        return "outside_right"
    return "inside"
