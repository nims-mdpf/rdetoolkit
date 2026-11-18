from pathlib import Path
from typing import Final

from rdetoolkit.graph.exceptions import AmbiguousFormatError
from rdetoolkit.graph.readers.base import DetectionDecision as DetectionDecision, FormatCandidate as FormatCandidate

SNIFF_MAX_BYTES: Final[int]
SNIFF_MAX_ROWS: Final[int]
DEFAULT_MAX_TABLE_BYTES: Final[int]
SELECT_MIN_CONFIDENCE: Final[float]
SELECT_MIN_MARGIN: Final[float]

def detect_table_format(path: str | Path, *, max_bytes: int = ...) -> DetectionDecision: ...
def ambiguity_error(path: Path, decision: DetectionDecision) -> AmbiguousFormatError: ...
def require_selection(path: Path, decision: DetectionDecision) -> str: ...

__all__ = ['DEFAULT_MAX_TABLE_BYTES', 'SELECT_MIN_CONFIDENCE', 'SELECT_MIN_MARGIN', 'SNIFF_MAX_BYTES', 'SNIFF_MAX_ROWS', 'DetectionDecision', 'FormatCandidate', 'ambiguity_error', 'detect_table_format', 'require_selection']
