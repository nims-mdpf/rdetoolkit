from typing import Final, Literal

from rdetoolkit.graph.spec import AxisLimits

SUPPORTED_MODES: Final[tuple[str, ...]]
INVALID_AXIS_LIMITS: Final[str]

def validate_plot_request(*, mode: str, no_individual: bool | None) -> None: ...
def validate_axis_limits(
    limits: AxisLimits | None,
    *,
    scale: Literal["linear", "log"],
    axis: str,
) -> AxisLimits | None: ...
