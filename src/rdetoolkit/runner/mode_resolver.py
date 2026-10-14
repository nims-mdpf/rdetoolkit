"""Mode resolution wrapper for the v2 Runner."""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path

from rdetoolkit.domain.input_checker import selected_input_checker
from rdetoolkit.errors import WARNING_CATALOG
from rdetoolkit.impl.input_controller import (
    ExcelInvoiceChecker,
    InvoiceChecker,
    MultiFileChecker,
    RDEFormatChecker,
    SmartTableChecker,
)
from rdetoolkit.models.rde2types import RdeInputDirPaths
from rdetoolkit.report.events import Event, EventSink
from rdetoolkit.types import RdeConfig


class ModeKind(Enum):
    """Lowercase internal mode names for v2 Runner reports."""

    invoice = "invoice"
    excelinvoice = "excelinvoice"
    multidatatile = "multidatatile"
    smarttable = "smarttable"
    rdeformat = "rdeformat"


def resolve_mode(
    config: RdeConfig,
    inputdata_path: Path,
    unpacked_dir_path: Path,
    event_sink: EventSink,
    run_id: str,
) -> ModeKind:
    """Resolve the effective v2 mode using the v1-compatible detector.

    File detection priority is delegated to ``domain.input_checker.selected_input_checker``.
    If file detection overrides an explicitly configured mode, W1001 is emitted
    to both the event sink and stderr.

    Args:
        config: Effective v2 Runner configuration.
        inputdata_path: Directory containing input files.
        unpacked_dir_path: Directory used by legacy input checkers.
        event_sink: Open event sink for warnings.
        run_id: Current run identifier.

    Returns:
        Effective internal mode.
    """
    configured_mode = _configured_mode(config)
    src_paths = RdeInputDirPaths(
        inputdata=inputdata_path,
        invoice=inputdata_path.parent / "invoice",
        tasksupport=inputdata_path.parent / "tasksupport",
    )
    checker = selected_input_checker(
        src_paths,
        unpacked_dir_path,
        _mode_for_legacy_detector(configured_mode),
    )
    detected_mode = _mode_from_checker(checker)
    # W1001 is scoped to conflicts with an EXPLICITLY configured mode (Design
    # §6.2); file-based detection over the implicit default is normal operation.
    mode_explicitly_configured = "extended_mode" in config.system.model_fields_set
    if (
        mode_explicitly_configured
        and detected_mode != configured_mode
        and _file_detection_overrode_config(detected_mode)
    ):
        _emit_mode_override_warning(
            event_sink=event_sink,
            run_id=run_id,
            detected_mode=detected_mode,
        )
    return detected_mode


def _configured_mode(config: RdeConfig) -> ModeKind:
    raw_mode = config.system.extended_mode
    if raw_mode == "MultiDataTile":
        return ModeKind.multidatatile
    if raw_mode == "rdeformat":
        return ModeKind.rdeformat
    return ModeKind.invoice


def _mode_for_legacy_detector(mode: ModeKind) -> str | None:
    if mode is ModeKind.multidatatile:
        return "MultiDataTile"
    if mode is ModeKind.rdeformat:
        return "rdeformat"
    return None


def _mode_from_checker(checker: object) -> ModeKind:
    if isinstance(checker, SmartTableChecker):
        return ModeKind.smarttable
    if isinstance(checker, ExcelInvoiceChecker):
        return ModeKind.excelinvoice
    if isinstance(checker, RDEFormatChecker):
        return ModeKind.rdeformat
    if isinstance(checker, MultiFileChecker):
        return ModeKind.multidatatile
    if isinstance(checker, InvoiceChecker):
        return ModeKind.invoice
    msg = f"Unsupported input checker type: {type(checker).__name__}"
    raise TypeError(msg)


def _file_detection_overrode_config(mode: ModeKind) -> bool:
    return mode in {ModeKind.smarttable, ModeKind.excelinvoice}


def _emit_mode_override_warning(
    *,
    event_sink: EventSink,
    run_id: str,
    detected_mode: ModeKind,
) -> None:
    warning_def = WARNING_CATALOG[1001]
    message = warning_def.message_template.format(mode=detected_mode.value)
    event_sink.emit(Event.warning(run_id=run_id, code=1001, message=message))
    sys.stderr.write(f"{warning_def.name}: {message}\n")
