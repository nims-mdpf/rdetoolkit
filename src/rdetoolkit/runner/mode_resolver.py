"""Target-specific mode resolution for the unified Runner."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from rdetoolkit.domain.mode_selection import ModeDecision, ModeKind, decide_mode
from rdetoolkit.errors import WARNING_CATALOG
from rdetoolkit.report.events import Event, EventSink, _best_effort_stderr
from rdetoolkit.types import RdeConfig

__all__ = ["ModeDecision", "ModeKind", "resolve_mode", "resolve_mode_decision"]


def resolve_mode_decision(config: RdeConfig, inputdata_path: Path, event_sink: EventSink, run_id: str, *, contract: Literal["v1", "v2"] = "v2") -> ModeDecision:
    """Resolve one decision and publish compatibility warnings.

    Args:
        config: Effective run configuration.
        inputdata_path: Input snapshot directory.
        event_sink: Run warning sink.
        run_id: Active run identifier.
        contract: Selection policy determined by the execution target.

    Returns:
        Immutable mode decision shared with Runner diagnostics.
    """
    decision = decide_mode(config, inputdata_path, contract=contract)
    for code in decision.warning_codes:
        definition = WARNING_CATALOG[code]
        message = definition.message_template.format(mode=decision.chosen_mode.value)
        event_sink.emit(Event.warning(run_id=run_id, code=code, message=message))
        _best_effort_stderr(f"{definition.name}: {message}\n")
    return decision


def resolve_mode(config: RdeConfig, inputdata_path: Path, unpacked_dir_path: Path, event_sink: EventSink, run_id: str, *, contract: Literal["v1", "v2"] = "v2") -> ModeKind:
    """Resolve the strict v2 mode or the callback compatibility mode.

    Args:
        config: Effective run configuration.
        inputdata_path: Input snapshot directory.
        unpacked_dir_path: Compatibility argument; selection never unpacks inputs.
        event_sink: Run warning sink.
        run_id: Active run identifier.
        contract: Strict v2 by default; callbacks select the v1 contract.

    Returns:
        Effective canonical mode.
    """
    _ = unpacked_dir_path
    return resolve_mode_decision(config, inputdata_path, event_sink, run_id, contract=contract).chosen_mode
