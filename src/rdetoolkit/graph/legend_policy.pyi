from typing import Literal

LegendPolicy = Literal['legacy', 'auto', 'inside', 'outside_right', 'outside_bottom', 'hide']
ResolvedLegendPolicy = Literal['legacy', 'inside', 'outside_right', 'outside_bottom', 'hide']

VALID_LEGEND_POLICIES: tuple[str, ...]

def resolve_legend_policy(
    policy: LegendPolicy,
    filtered_label_count: int,
    outside_threshold: int,
    max_items: int | None,
    bottom_threshold: int | None = None,
) -> ResolvedLegendPolicy: ...
