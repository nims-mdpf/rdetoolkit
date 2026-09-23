"""Registry for incrementally installed v2 mode handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rdetoolkit.modes.protocol import ModeHandler

if TYPE_CHECKING:
    from rdetoolkit.runner.mode_resolver import ModeKind


_HANDLERS: dict[ModeKind, ModeHandler] = {}


def register(mode: ModeKind, handler: ModeHandler) -> None:
    """Register a mode handler for subsequent plans.

    Args:
        mode: Resolved mode used as the registry key.
        handler: Tile-planning handler for that mode.
    """
    _HANDLERS[mode] = handler


def clear() -> None:
    """Remove every registered handler.

    This exists so a caller can return to the pre-installation state without
    reaching into registry internals; production code installs handlers through
    ``rdetoolkit.modes.install.install_default_handlers()``.
    """
    _HANDLERS.clear()


def handler_for(mode: ModeKind) -> ModeHandler | None:
    """Return the registered handler for a mode, when installed.

    Args:
        mode: Resolved mode to look up.

    Returns:
        Registered handler, or ``None`` while the legacy planner fallback owns
        that mode.
    """
    return _HANDLERS.get(mode)
