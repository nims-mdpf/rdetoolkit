"""Explicit installation of the built-in mode handlers.

Registration is a function call, never an import side effect: importing a mode
module must leave the registry untouched so the planner fallback stays
reachable and tests can start from an empty registry.
"""

from __future__ import annotations

from rdetoolkit.modes.excelinvoice import ExcelInvoiceModeHandler
from rdetoolkit.modes.invoice import InvoiceModeHandler
from rdetoolkit.modes.multidatatile import MultiDataTileModeHandler
from rdetoolkit.modes.protocol import ModeHandler
from rdetoolkit.modes.rdeformat import RdeFormatModeHandler
from rdetoolkit.modes.registry import handler_for, register
from rdetoolkit.modes.smarttable import SmartTableModeHandler


def install_default_handlers() -> None:
    """Register the built-in handler for every mode that has none yet.

    The Runner calls this while it is constructed, so installation must not
    overwrite a handler the caller registered deliberately: a mode keeps
    whatever handler it already has. ``registry.clear()`` followed by this call
    still restores the pristine built-in set, which is how tests reset it.
    """
    handlers: tuple[ModeHandler, ...] = (
        InvoiceModeHandler(),
        ExcelInvoiceModeHandler(),
        MultiDataTileModeHandler(),
        RdeFormatModeHandler(),
        SmartTableModeHandler(),
    )
    for handler in handlers:
        if handler_for(handler.kind) is None:
            register(handler.kind, handler)
