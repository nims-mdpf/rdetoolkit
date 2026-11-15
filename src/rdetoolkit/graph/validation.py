"""Request validation shared by every graph entry point.

Validation runs on the normalized request before any column resolution, rendering
or filesystem access, so an invalid request never leaves partial output behind.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Any, Final, Literal

from rdetoolkit.graph.exceptions import PlotRequestError
from rdetoolkit.graph.spec import AxisLimits

SUPPORTED_MODES: Final[tuple[str, ...]] = ("overlay", "individual")
INVALID_AXIS_LIMITS: Final[str] = "invalid_axis_limits"
_KEEP_AUTO_HINT: Final[str] = "use None for a side that should stay automatic"


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


def validate_axis_limits(
    limits: AxisLimits | None,
    *,
    scale: Literal["linear", "log"],
    axis: str,
) -> AxisLimits | None:
    """Validate and normalize ``(min, max)`` axis limits for every entry point.

    A ``None`` side stays automatic (Matplotlib keeps its own limit for it), so
    ``(0, None)`` fixes only the lower bound. Reversed bounds (``min > max``) are
    accepted and invert the axis, matching Matplotlib and ``plot_lines``.

    Args:
        limits: ``None`` or a ``(min, max)`` pair whose items are real numbers or ``None``.
        scale: Scale of the axis the limits apply to.
        axis: Axis name used in error messages (``"x"`` or ``"y"``).

    Returns:
        ``None`` when nothing is fixed (``None`` or ``(None, None)``), otherwise the
        pair with every given bound converted to ``float``.

    Raises:
        PlotRequestError: ``reason="invalid_axis_limits"`` when ``limits`` is not a
            pair, a bound is not a finite real number, both bounds are equal, or a
            bound is ``<= 0`` on a log axis.
    """
    if limits is None:
        return None
    pair = _as_pair(limits, axis)
    bounds = (_bound(pair[0], axis, "lower"), _bound(pair[1], axis, "upper"))
    if bounds == (None, None):
        return None
    if bounds[0] is not None and bounds[0] == bounds[1]:
        msg = f"Invalid {axis}-axis limits {tuple(pair)!r}: lower and upper bounds are equal; give a non-empty range or {_KEEP_AUTO_HINT}"
        raise PlotRequestError(msg, reason=INVALID_AXIS_LIMITS)
    if scale == "log":
        _check_log_bounds(bounds, axis)
    return bounds


def _as_pair(limits: object, axis: str) -> tuple[Any, ...]:
    # Strings are sequences too, but "0,10" is a typo for a pair, never a pair.
    if isinstance(limits, (tuple, list)) and len(limits) == 2:  # noqa: PLR2004 - (min, max) pair
        return tuple(limits)
    msg = f"Invalid {axis}-axis limits {limits!r}: expected a (min, max) pair; {_KEEP_AUTO_HINT}"
    raise PlotRequestError(msg, reason=INVALID_AXIS_LIMITS)


def _bound(value: object, axis: str, side: str) -> float | None:
    if value is None:
        return None
    # bool is a Real subclass, but True/False as an axis bound is always a mistake.
    if isinstance(value, bool) or not isinstance(value, Real):
        msg = f"Invalid {axis}-axis {side} bound {value!r}: expected a number; {_KEEP_AUTO_HINT}"
        raise PlotRequestError(msg, reason=INVALID_AXIS_LIMITS)
    bound = float(value)
    if not math.isfinite(bound):
        msg = f"Invalid {axis}-axis {side} bound {bound!r}: bounds must be finite; {_KEEP_AUTO_HINT}"
        raise PlotRequestError(msg, reason=INVALID_AXIS_LIMITS)
    return bound


def _check_log_bounds(bounds: tuple[float | None, float | None], axis: str) -> None:
    for side, bound in zip(("lower", "upper"), bounds, strict=True):
        if bound is not None and bound <= 0:
            msg = (
                f"Invalid {axis}-axis {side} bound {bound:g} on a log-scale {axis} axis: "
                f"log-axis bounds must be > 0; pass a positive bound, {_KEEP_AUTO_HINT}, "
                "or use a linear axis"
            )
            raise PlotRequestError(msg, reason=INVALID_AXIS_LIMITS)
