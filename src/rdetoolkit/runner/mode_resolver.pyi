from enum import Enum
from pathlib import Path

from rdetoolkit.report.events import EventSink
from rdetoolkit.types import RdeConfig

class ModeKind(Enum):
    invoice = ...
    excelinvoice = ...
    multidatatile = ...
    smarttable = ...
    rdeformat = ...

def resolve_mode(
    config: RdeConfig,
    inputdata_path: Path,
    unpacked_dir_path: Path,
    event_sink: EventSink,
    run_id: str,
) -> ModeKind: ...
