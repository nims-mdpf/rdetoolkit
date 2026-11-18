from typing import Final, Literal

from rdetoolkit.graph.spec import AxisLimits, StyleSpec

SUPPORTED_MODES: Final[tuple[str, ...]]
INVALID_AXIS_LIMITS: Final[str]
INVALID_FIGURE_SIZE: Final[str]
INVALID_RC_PARAM: Final[str]
DENIED_RC_PARAMS: Final[frozenset[str]]

def validate_plot_request(*, mode: str, no_individual: bool | None) -> None: ...
def validate_axis_limits(
    limits: AxisLimits | None,
    *,
    scale: Literal["linear", "log"],
    axis: str,
) -> AxisLimits | None: ...
def validate_style(style: StyleSpec) -> StyleSpec: ...
