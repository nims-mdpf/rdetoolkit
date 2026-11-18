"""Unit normalization and grouping for overlay figures (GE-11).

Unit policy (documented and testable):

* Units come from the column header (``"voltage (V)"``) or from ``SeriesSpec.unit``.
  They are compared as normalized text only: there is no conversion and no
  dimension registry, so ``"mV"`` and ``"V"`` are different units and nothing is
  ever rescaled.
* Normalization is NFKC (so the micro sign and the Greek mu compare equal), trimming
  and collapsing inner white space. An empty unit is unknown (``None``). Common
  spellings of arbitrary units (``"a.u"``, ``"arb."``, ``"arb. units"``,
  ``"arbitrary units"``, ...) become ``"a.u."``. A bare ``"au"`` is left alone because
  it is also the astronomical unit. Letter case is kept otherwise: ``"mV"`` and
  ``"MV"`` are different units.
* A series without a unit is *unknown*. It never causes a mismatch and joins the
  first unit group; the planner reports it when it shares an overlay axis with a
  known unit (``unit_unknown``, "assumed compatible, no conversion performed").
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from typing import Final

__all__ = ["ARBITRARY_UNIT", "group_units", "normalize_unit"]

ARBITRARY_UNIT: Final = "a.u."

_SPACES = re.compile(r"\s+")
# Compared after case folding and removing spaces, so "Arb. Units" and "arb.units" match.
_ARBITRARY_SPELLINGS: Final = frozenset({
    "a.u.",
    "a.u",
    "arb",
    "arb.",
    "arb.u",
    "arb.u.",
    "arb.unit",
    "arb.units",
    "arbunit",
    "arbunits",
    "arbitraryunit",
    "arbitraryunits",
})


def normalize_unit(unit: str | None) -> str | None:
    r"""Normalize a unit string for comparison, without converting anything.

    Args:
        unit: Unit text from a header or ``SeriesSpec.unit``; ``None`` = unknown.

    Returns:
        The NFKC-normalized unit with trimmed and collapsed white space,
        ``"a.u."`` for spellings of arbitrary units, or ``None`` when the unit is
        missing or blank.

    Examples:
        >>> normalize_unit(" m  V ")
        'm V'
        >>> normalize_unit("µA") == normalize_unit("μA")
        True
        >>> normalize_unit("arb. units")
        'a.u.'
        >>> normalize_unit("") is None
        True
    """
    if unit is None:
        return None
    text = _SPACES.sub(" ", unicodedata.normalize("NFKC", unit)).strip()
    if not text:
        return None
    if text.casefold().replace(" ", "") in _ARBITRARY_SPELLINGS:
        return ARBITRARY_UNIT
    return text


def group_units(units: Sequence[str | None]) -> tuple[tuple[int, ...], tuple[str | None, ...]]:
    """Group series by their (already normalized) unit.

    Known units form groups in first-appearance order. Unknown units (``None``)
    join the first group; when no unit is known there is a single group whose
    unit is ``None``.

    Args:
        units: One normalized unit per series, in plan order.

    Returns:
        The group index of every series, and the unit of every group.

    Examples:
        >>> group_units(["V", None, "A", "V"])
        ((0, 0, 1, 0), ('V', 'A'))
        >>> group_units([None, None])
        ((0, 0), (None,))
        >>> group_units([])
        ((), ())
    """
    if not units:
        return (), ()
    known: list[str] = []
    for unit in units:
        if unit is not None and unit not in known:
            known.append(unit)
    group_unit: tuple[str | None, ...] = tuple(known) if known else (None,)
    indices = tuple(0 if unit is None else known.index(unit) for unit in units)
    return indices, group_unit
