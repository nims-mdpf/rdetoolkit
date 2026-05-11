"""Backward-compatible re-exports for mode processing.

The implementation lives in :mod:`rdetoolkit.domain.mode`.
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

if __name__ == "rdetoolkit.modeproc":
    _sys.modules[__name__] = _mode
