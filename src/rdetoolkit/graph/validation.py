"""Request validation shared by every graph entry point.

Validation runs on the normalized request before any column resolution, rendering
or filesystem access, so an invalid request never leaves partial output behind.
"""

from __future__ import annotations

from typing import Final

from rdetoolkit.graph.exceptions import PlotRequestError

SUPPORTED_MODES: Final[tuple[str, ...]] = ("overlay", "individual")


def validate_plot_request(*, mode: str, no_individual: bool | None) -> None:
    """Reject unsupported plot modes and contradictory switch combinations.

    Args:
        mode: Requested plotting mode; must be exactly ``"overlay"`` or ``"individual"``.
        no_individual: Request to skip individual plots (``None`` = automatic).

    Raises:
        PlotRequestError: ``reason="invalid_mode"`` for any other mode value, or
            ``reason="contradictory_switches"`` for ``mode="individual"`` with
            ``no_individual=True`` (that combination can never produce a figure).
    """
    # isinstance guard first: non-str values (None, ints) must not be compared by
    # equality with the supported strings and fall through as "valid".
    if not isinstance(mode, str) or mode not in SUPPORTED_MODES:
        msg = f"Invalid mode: {mode!r}. Choose from {list(SUPPORTED_MODES)}"
        raise PlotRequestError(msg, reason="invalid_mode")
    if mode == "individual" and no_individual is True:
        msg = (
            "mode='individual' with no_individual=True would produce no figure; "
            "drop no_individual or use mode='overlay'"
        )
        raise PlotRequestError(msg, reason="contradictory_switches")
