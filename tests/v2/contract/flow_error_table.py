"""Session I6-0 flow error translation table (v1 observed -> v2 expected).

This module is the single source of truth for the FLOW-USERERR / FLOW-VALERR
matrix cells. ``local/develop/v2/merge_v1/contracts.md`` §I6-0 transcribes it;
the tests read it directly so the contract, the documentation, and the
assertions cannot drift apart.

Two translation rules cover all ten cells:

``MessageRule.V1_VERBATIM``
    User code raised the v1 public ``StructuredError``. Its ``ecode`` and
    ``emsg`` reach ``job.failed`` unchanged, so v2 is byte-identical to the
    frozen v1 observation (Design §6.3, 2026-09-07 addendum).

``MessageRule.V2_VALIDATION``
    The failure is an invoice-schema violation. v2 detects it in
    ``pre_validate`` — before the flow runs — and reports the v2 catalog code
    4001 with the underlying defect, where v1 reported a mode-specific
    downstream symptom after the callback had already run. This divergence was
    ruled intentional in session_h2.md Conflict #2 and is pinned here.

Session I-REVIEW-B (review F5) added the **CB-V2 column**: the same ten cells
executed through ``Runner.run(RunRequest(target=LegacyCallbackTarget(...)))``,
i.e. the unified Runner driving the new ``LegacyCallbackInvoker`` rather than
v1's own loop. The translation rules are unchanged — a user ``StructuredError``
still passes through verbatim and an invalid source invoice is still frontloaded
to 4001 — but the *iteration* column differs from the FLOW column, because a
v1 ``Config`` handed to ``config_source`` seeds ``on_iteration_error:
fail_fast`` (``ConfigNormalizer._convert_v1``) where a v2 flow cell takes the v2
default ``continue``. That is what makes the CB-V2 callback counts equal to the
frozen v1 ones instead of equal to the tile count.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

#: v2 catalog code for a source invoice that violates its schema.
INVOICE_SCHEMA_INVALID_CODE = 4001

#: The actual invoice defect ``_invalidate_invoice`` introduces. Every mode
#: reports it in v2 because pre_validate inspects the source invoice itself.
VALIDATION_REASON = "'basic' is a required property"

#: A failed run maps to v1 exit code 1 (Design §9.3).
FAILED_EXIT_CODE = 1


class MessageRule(Enum):
    """How a v2 ``job.failed`` message relates to the frozen v1 observation."""

    V1_VERBATIM = "v1-verbatim"
    V2_VALIDATION = "v2-validation"


class IterationRule(Enum):
    """How many tiles the v2 Runner attempts before the run fails."""

    #: Default ``on_iteration_error: continue`` — every tile runs and fails.
    EVERY_TILE = "every-tile"
    #: ``pre_validate`` rejects the run, so ``iterate`` is never entered.
    NONE = "none"
    #: ``fail_fast`` aborts at the first failing tile, so exactly one tile runs.
    FIRST_TILE = "first-tile"


@dataclass(frozen=True)
class FlowErrorCell:
    """One (mode, outcome) row of the translation table."""

    mode: str
    outcome: str
    v1_code: int
    v1_callback_count: int
    v2_code: int
    v2_message: MessageRule
    v2_iterations: IterationRule
    rationale: str
    #: CB-V2 column: the same cell executed through the unified Runner with a
    #: ``LegacyCallbackTarget``. The code and message rules are shared with the
    #: FLOW column; only the iteration and callback counts differ, because the
    #: v1 ``Config`` the cell passes seeds the fail-fast policy.
    cb_v2_iterations: IterationRule = IterationRule.FIRST_TILE
    cb_v2_callback_count: int = 1


_USER_PASSTHROUGH = (
    "user StructuredError(ecode=999) passes through verbatim; v1 stops at the "
    "first failing tile (fail-fast) while v2 attempts every tile under the "
    "default continue policy"
)
_VALIDATION_FRONTLOADED = (
    "v2 pre_validate rejects the source invoice before the flow runs, so the "
    "v2 catalog code replaces the v1 mode-specific downstream symptom"
)

FLOW_ERROR_TABLE: tuple[FlowErrorCell, ...] = (
    FlowErrorCell("invoice", "usererr", 999, 1, 999, MessageRule.V1_VERBATIM, IterationRule.EVERY_TILE, _USER_PASSTHROUGH),
    FlowErrorCell("excelinvoice", "usererr", 999, 1, 999, MessageRule.V1_VERBATIM, IterationRule.EVERY_TILE, _USER_PASSTHROUGH),
    FlowErrorCell("multidatatile", "usererr", 999, 1, 999, MessageRule.V1_VERBATIM, IterationRule.EVERY_TILE, _USER_PASSTHROUGH),
    FlowErrorCell("rdeformat", "usererr", 999, 1, 999, MessageRule.V1_VERBATIM, IterationRule.EVERY_TILE, _USER_PASSTHROUGH),
    FlowErrorCell("smarttable", "usererr", 999, 1, 999, MessageRule.V1_VERBATIM, IterationRule.EVERY_TILE, _USER_PASSTHROUGH),
    FlowErrorCell("invoice", "valerr", 999, 1, INVOICE_SCHEMA_INVALID_CODE, MessageRule.V2_VALIDATION, IterationRule.NONE, _VALIDATION_FRONTLOADED, IterationRule.NONE, 0),
    FlowErrorCell("excelinvoice", "valerr", 1, 0, INVOICE_SCHEMA_INVALID_CODE, MessageRule.V2_VALIDATION, IterationRule.NONE, _VALIDATION_FRONTLOADED, IterationRule.NONE, 0),
    FlowErrorCell("multidatatile", "valerr", 999, 1, INVOICE_SCHEMA_INVALID_CODE, MessageRule.V2_VALIDATION, IterationRule.NONE, _VALIDATION_FRONTLOADED, IterationRule.NONE, 0),
    FlowErrorCell("rdeformat", "valerr", 999, 1, INVOICE_SCHEMA_INVALID_CODE, MessageRule.V2_VALIDATION, IterationRule.NONE, _VALIDATION_FRONTLOADED, IterationRule.NONE, 0),
    FlowErrorCell("smarttable", "valerr", 1, 0, INVOICE_SCHEMA_INVALID_CODE, MessageRule.V2_VALIDATION, IterationRule.NONE, _VALIDATION_FRONTLOADED, IterationRule.NONE, 0),
)

_BY_CASE = {(cell.mode, cell.outcome): cell for cell in FLOW_ERROR_TABLE}


def flow_error_cell(mode: str, outcome: str) -> FlowErrorCell:
    """Return the contracted translation for one matrix cell.

    Args:
        mode: One of the five unified execution modes.
        outcome: ``"usererr"`` or ``"valerr"``.

    Returns:
        The frozen translation row for that cell.

    Raises:
        KeyError: If the table has no row for this cell.
    """
    return _BY_CASE[(mode, outcome)]


def expected_iteration_count(cell: FlowErrorCell, tile_count: int) -> int:
    """Return how many iterations the v2 run report must contain.

    Args:
        cell: Translation row under test.
        tile_count: Tiles this mode produces, taken from the frozen OK oracle.

    Returns:
        The contracted iteration count for this cell.
    """
    return tile_count if cell.v2_iterations is IterationRule.EVERY_TILE else 0


def expected_cb_v2_iteration_count(cell: FlowErrorCell, tile_count: int) -> int:
    """Return how many iterations the CB-V2 run report must contain.

    Args:
        cell: Translation row under test.
        tile_count: Tiles this mode produces, taken from the frozen OK oracle.

    Returns:
        The contracted iteration count for this cell's CB-V2 column.
    """
    if cell.cb_v2_iterations is IterationRule.NONE:
        return 0
    if cell.cb_v2_iterations is IterationRule.FIRST_TILE:
        return 1
    return tile_count


def expected_divided_indices(cell: FlowErrorCell, tile_count: int) -> tuple[str, ...]:
    """Return the ``data/divided`` subdirectories the v2 run must leave behind.

    The directory contract (Design §6.4) gives tile 0 the flat ``data/`` tree
    and every later tile a ``divided/000N`` tree, so the attempted-tile count
    determines this set. The frozen v1 usererr trees contain no ``divided/`` at
    all because v1 aborts at the first failing tile; v2 attempts them all under
    the default ``continue`` policy.

    Args:
        cell: Translation row under test.
        tile_count: Tiles this mode produces, taken from the frozen OK oracle.

    Returns:
        Sorted ``divided`` subdirectory names, empty when none is expected.
    """
    attempted = expected_iteration_count(cell, tile_count)
    return tuple(f"{index:04d}" for index in range(1, attempted))
