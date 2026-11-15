"""Request validation shared by every graph entry point.

Validation runs on the normalized request before any column resolution, rendering
or filesystem access, so an invalid request never leaves partial output behind.
"""

from __future__ import annotations

import datetime as dt
import difflib
import math
from collections.abc import Mapping
from numbers import Real
from typing import Any, Final, Literal, cast

import matplotlib as mpl
import numpy as np
import pandas as pd

from rdetoolkit.graph.exceptions import PlotRequestError
from rdetoolkit.graph.spec import AxisLimits, StyleSpec

SUPPORTED_MODES: Final[tuple[str, ...]] = ("overlay", "individual")
INVALID_AXIS_LIMITS: Final[str] = "invalid_axis_limits"
_KEEP_AUTO_HINT: Final[str] = "use None for a side that should stay automatic"
INVALID_FIGURE_SIZE: Final[str] = "invalid_figure_size"
INVALID_RC_PARAM: Final[str] = "invalid_rc_param"
# Real rcParams that would switch the backend or the interactive UI: a plot style must
# never change how (or whether) Matplotlib draws for the rest of the process.
DENIED_RC_PARAMS: Final[frozenset[str]] = frozenset({"backend", "backend_fallback", "interactive", "toolbar"})


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
    Datetime-like bounds (``datetime.date``/``datetime.datetime``, ``pd.Timestamp``,
    ``np.datetime64``) for a date axis are accepted as in v1 and returned unchanged;
    the log-axis rule only applies to numeric bounds.

    Args:
        limits: ``None`` or a ``(min, max)`` pair whose items are real numbers,
            datetime-like values or ``None``.
        scale: Scale of the axis the limits apply to.
        axis: Axis name used in error messages (``"x"`` or ``"y"``).

    Returns:
        ``None`` when nothing is fixed (``None`` or ``(None, None)``), otherwise the
        pair with every numeric bound converted to ``float`` (datetime-like bounds
        are kept as given).

    Raises:
        PlotRequestError: ``reason="invalid_axis_limits"`` when ``limits`` is not a
            pair, a bound is neither a finite real number nor a datetime-like value
            (``NaT`` included), both bounds are equal, or a numeric bound is ``<= 0``
            on a log axis.
    """
    if limits is None:
        return None
    pair = _as_pair(limits, axis)
    bounds = (_bound(pair[0], axis, "lower"), _bound(pair[1], axis, "upper"))
    if bounds == (None, None):
        return None
    if bounds[0] is not None and _equal_bounds(bounds[0], bounds[1]):
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


def _equal_bounds(lower: object, upper: object) -> bool:
    # Bounds are numbers or datetime-like scalars here; a datetime never equals a
    # number, and NaT was rejected, so == is a plain bool comparison.
    return bool(lower == upper)


def _is_datetime_like(value: object) -> bool:
    # pd.Timestamp (and pd.NaT) are datetime subclasses; datetime is a date subclass.
    return isinstance(value, (dt.date, np.datetime64))


def _datetime_bound(value: object, axis: str, side: str) -> float | None:
    if pd.isna(value):
        msg = f"Invalid {axis}-axis {side} bound {value!r}: NaT is not a bound; {_KEEP_AUTO_HINT}"
        raise PlotRequestError(msg, reason=INVALID_AXIS_LIMITS)
    # Matplotlib converts date bounds itself (v1 passed them through); the value is
    # carried unchanged, the float annotation only describes the numeric case.
    return cast(float, value)


def _bound(value: object, axis: str, side: str) -> float | None:
    if value is None:
        return None
    if _is_datetime_like(value):
        return _datetime_bound(value, axis, side)
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
        # Datetime-like bounds are not numbers; the log rule does not apply to them.
        if isinstance(bound, Real) and bound <= 0:
            msg = (
                f"Invalid {axis}-axis {side} bound {bound:g} on a log-scale {axis} axis: "
                f"log-axis bounds must be > 0; pass a positive bound, {_KEEP_AUTO_HINT}, "
                "or use a linear axis"
            )
            raise PlotRequestError(msg, reason=INVALID_AXIS_LIMITS)


def validate_style(style: StyleSpec) -> StyleSpec:
    """Validate figure size and rcParams of a style before anything is drawn.

    The builder setters accept any value (ruling C-10); this is where a style is
    checked, when a plan is built.

    Args:
        style: The requested style.

    Returns:
        The style with each figure size component converted to ``float``; the
        rcParams are returned as given.

    Raises:
        PlotRequestError: ``reason="invalid_figure_size"`` when a size component is
            not a finite real number ``> 0``; ``reason="invalid_rc_param"`` when a key
            is not a Matplotlib rcParam (the message suggests close matches), is on
            the deny-list (``backend``, ``backend_fallback``, ``interactive``,
            ``toolbar``), or its value is rejected by the rcParam's validator.
    """
    for key, value in style.rc_params.items():
        _check_rc_param(key, value)
    if style.figure_size is None:
        return style
    width, height = (_size_component(value, name) for value, name in zip(style.figure_size, ("width", "height"), strict=True))
    return StyleSpec(figure_size=(width, height), rc_params=style.rc_params)


def _size_component(value: object, name: str) -> float:
    # bool is a Real subclass, but True as a width is always a mistake.
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)) or float(value) <= 0:
        msg = f"Invalid figure {name} {value!r}: figure_size must be a (width, height) pair of finite numbers > 0 (inches)"
        raise PlotRequestError(msg, reason=INVALID_FIGURE_SIZE)
    return float(value)


def _check_rc_param(key: object, value: object) -> None:
    rc_validators = cast("Mapping[str, Any]", mpl.RcParams.validate)
    if not isinstance(key, str) or key not in rc_validators:
        suggestions = difflib.get_close_matches(str(key), sorted(rc_validators), n=3)
        hint = f"; did you mean {suggestions}?" if suggestions else ""
        msg = f"Unknown Matplotlib rcParam {key!r}{hint}"
        raise PlotRequestError(msg, reason=INVALID_RC_PARAM)
    if key in DENIED_RC_PARAMS:
        msg = f"rcParam {key!r} cannot be set through a plot style (it changes the backend or the UI, not the figure)"
        raise PlotRequestError(msg, reason=INVALID_RC_PARAM)
    try:
        rc_validators[key](value)
    except (TypeError, ValueError) as exc:
        msg = f"Invalid value {value!r} for rcParam {key!r}: {exc}"
        raise PlotRequestError(msg, reason=INVALID_RC_PARAM) from exc
