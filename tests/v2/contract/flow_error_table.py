"""Session I6-0 flow error translation table (v1 observed -> v2 expected).

This module is the single source of truth for the FLOW-USERERR / FLOW-VALERR
matrix cells. ``local/develop/v2/merge_v1/contracts.md`` §I6-0 transcribes it;
the tests read it directly so the contract, the documentation, and the
assertions cannot drift apart.

Three translation rules cover all ten cells:

``MessageRule.V1_VERBATIM``
    User code raised the v1 public ``StructuredError``. Its ``ecode`` and
    ``emsg`` reach ``job.failed`` unchanged, so v2 is byte-identical to the
    frozen v1 observation (Design §6.3, 2026-09-07 addendum).

``MessageRule.V2_VALIDATION``
    Non-table flows reject the source invoice before execution (4001).
    Legacy callbacks validate final outputs instead (#647).

``MessageRule.V2_PREPARATION``
    Table modes defer source content validation. The malformed ``basic: null``
    fixture fails during tile construction, before user code: ExcelInvoice's
    ordinary exception maps to 3001; SmartTable preserves StructuredError(1).
    This fixture does not represent a repairable missing custom field; those
    cases are covered in test_invoice_validation_timing_647.py.

The CB-V2 column records callback counts and final report iterations under the
v1 configuration. Run-level output validation replaces the iteration report on
failure, so callbacks may have run even when the final report has no iterations.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

#: v2 catalog code for a source invoice that violates its schema.
INVOICE_SCHEMA_INVALID_CODE = 4001

#: The defect non-table source/final invoice validation reports.
VALIDATION_REASON = "'basic' is a required property"

#: A failed run maps to v1 exit code 1 (Design §9.3).
FAILED_EXIT_CODE = 1


class MessageRule(Enum):
    """How a v2 ``job.failed`` message relates to the frozen v1 observation."""

    V1_VERBATIM = "v1-verbatim"
    V2_VALIDATION = "v2-validation"
    V2_PREPARATION = "v2-preparation"


class IterationRule(Enum):
    """How many iterations the final run report retains."""

    #: Default ``on_iteration_error: continue`` — every tile runs and fails.
    EVERY_TILE = "every-tile"
    #: Run-level validation failure: no iterations in the final failed report.
    #: Source validation stops before iteration; output validation replaces the
    #: iteration report at the run failure boundary.
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
    #: FLOW column; timing and counts differ because callbacks may complete
    #: invoices and the v1 configuration seeds the fail-fast policy.
    cb_v2_iterations: IterationRule = IterationRule.FIRST_TILE
    cb_v2_callback_count: int = 1


_USER_PASSTHROUGH = (
    "user StructuredError(ecode=999) passes through verbatim; v1 stops at the "
    "first failing tile (fail-fast) while v2 attempts every tile under the "
    "default continue policy"
)
_VALIDATION_CATALOGUED = (
    "the flow entry's pre_validate rejects the source invoice before the flow "
    "runs and the v1 callback entry's post_validate rejects the final invoice, "
    "so the v2 catalog code replaces the v1 mode-specific downstream symptom"
)

FLOW_ERROR_TABLE: tuple[FlowErrorCell, ...] = (
    FlowErrorCell("invoice", "usererr", 999, 1, 999, MessageRule.V1_VERBATIM, IterationRule.EVERY_TILE, _USER_PASSTHROUGH),
    FlowErrorCell("excelinvoice", "usererr", 999, 1, 999, MessageRule.V1_VERBATIM, IterationRule.EVERY_TILE, _USER_PASSTHROUGH),
    FlowErrorCell("multidatatile", "usererr", 999, 1, 999, MessageRule.V1_VERBATIM, IterationRule.EVERY_TILE, _USER_PASSTHROUGH),
    FlowErrorCell("rdeformat", "usererr", 999, 1, 999, MessageRule.V1_VERBATIM, IterationRule.EVERY_TILE, _USER_PASSTHROUGH),
    FlowErrorCell("smarttable", "usererr", 999, 1, 999, MessageRule.V1_VERBATIM, IterationRule.EVERY_TILE, _USER_PASSTHROUGH),
    FlowErrorCell("invoice", "valerr", 999, 1, INVOICE_SCHEMA_INVALID_CODE, MessageRule.V2_VALIDATION, IterationRule.NONE, _VALIDATION_CATALOGUED, IterationRule.NONE, 1),
    FlowErrorCell("excelinvoice", "valerr", 1, 0, 3001, MessageRule.V2_PREPARATION, IterationRule.EVERY_TILE, "basic: null prevents Excel row merging before invocation", IterationRule.FIRST_TILE, 0),
    FlowErrorCell("multidatatile", "valerr", 999, 1, INVOICE_SCHEMA_INVALID_CODE, MessageRule.V2_VALIDATION, IterationRule.NONE, _VALIDATION_CATALOGUED, IterationRule.NONE, 2),
    FlowErrorCell("rdeformat", "valerr", 999, 1, INVOICE_SCHEMA_INVALID_CODE, MessageRule.V2_VALIDATION, IterationRule.NONE, _VALIDATION_CATALOGUED, IterationRule.NONE, 2),
    FlowErrorCell("smarttable", "valerr", 1, 0, 1, MessageRule.V2_PREPARATION, IterationRule.EVERY_TILE, "basic: null prevents SmartTable row merging before invocation", IterationRule.FIRST_TILE, 0),
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
