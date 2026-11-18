from pathlib import Path
from typing import Literal
from rdetoolkit.domain.mode_selection import ModeDecision as ModeDecision, ModeKind as ModeKind
from rdetoolkit.report.events import EventSink
from rdetoolkit.types import RdeConfig

def resolve_mode_decision(config: RdeConfig, inputdata_path: Path, event_sink: EventSink, run_id: str, *, contract: Literal["v1", "v2"] = "v2") -> ModeDecision: ...
def resolve_mode(config: RdeConfig, inputdata_path: Path, unpacked_dir_path: Path, event_sink: EventSink, run_id: str, *, contract: Literal["v1", "v2"] = "v2") -> ModeKind: ...
