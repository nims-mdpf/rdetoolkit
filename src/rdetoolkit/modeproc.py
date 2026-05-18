"""Backward-compatible alias for mode processing.

The implementation lives in :mod:`rdetoolkit.domain.mode` (Phase 2.2 Direct
Refactor). This module is a *full alias* of ``rdetoolkit.domain.mode``: it
swaps itself in :data:`sys.modules` so that all attribute access goes to the
domain module directly.

Rationale for the :data:`sys.modules` swap (Phase 2.2 design decision):

* v1 tests (e.g. ``tests/test_modeproc_result.py``,
  ``tests/test_save_behavior.py``) patch internals via
  ``@patch("rdetoolkit.modeproc.PipelineFactory")`` / ``selected_input_checker``
  / etc.
* v1 implementation (``workflows.py``) calls these symbols via attribute access
  on this module (``from rdetoolkit.modeproc import X``).
* A plain ``from rdetoolkit.domain.mode import X`` re-export would create a
  *separate binding* in this module's namespace. Patches against
  ``rdetoolkit.modeproc.X`` would then only mutate that binding and NOT the
  one that the actual implementation in ``rdetoolkit.domain.mode`` resolves
  internally. Tests would silently lose their mocks.
* By swapping ``sys.modules["rdetoolkit.modeproc"]`` to the domain module
  itself, every ``rdetoolkit.modeproc.<name>`` access — including
  ``unittest.mock.patch`` targets — operates directly on
  ``rdetoolkit.domain.mode``. This preserves v1 test/patch semantics without
  modifying any v1 test file (per AGENTS.md "do not modify v1 tests" rule).

Safeguards / known limitations:

* This is intentionally narrow: the swap runs only when this file is imported
  as the canonical ``rdetoolkit.modeproc`` module. Re-imports under aliases
  remain no-ops.
* The explicit ``from rdetoolkit.domain.mode import (...)`` block below keeps
  every public symbol statically discoverable by tooling (mypy, ruff,
  importchecker) before the swap takes effect.
* Once v2 fully owns ``workflows.py`` (Phase 3.17) and v1 patch targets can
  migrate to ``rdetoolkit.domain.mode``, this alias module can be deleted.
"""

from __future__ import annotations

import sys as _sys

from rdetoolkit.domain import mode as _mode
from rdetoolkit.domain.mode import (  # noqa: F401
    ExcelInvoiceChecker,
    Failure,
    IInputFileChecker,
    InvoiceChecker,
    MultiFileChecker,
    PipelineFactory,
    ProcessingContext,
    RDEFormatChecker,
    Result,
    SmartTableChecker,
    Success,
    copy_input_to_rawfile,
    copy_input_to_rawfile_for_rdeformat,
    excel_invoice_mode_process,
    excel_invoice_mode_process_result,
    invoice_mode_process,
    invoice_mode_process_result,
    multifile_mode_process,
    multifile_mode_process_result,
    rdeformat_mode_process,
    rdeformat_mode_process_result,
    selected_input_checker,
    smarttable_invoice_mode_process,
    smarttable_invoice_mode_process_result,
)

# See module docstring for the rationale of this swap.
if __name__ == "rdetoolkit.modeproc":
    _sys.modules[__name__] = _mode
