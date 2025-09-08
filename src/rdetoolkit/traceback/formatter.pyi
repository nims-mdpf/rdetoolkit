from _typeshed import Incomplete
from rdetoolkit.models.config import TracebackSettings as TracebackSettings
from rdetoolkit.traceback.masking import SecretsSanitizer as SecretsSanitizer

class CompactTraceFormatter:
    config: Incomplete
    masker: Incomplete
    def __init__(self, config: TracebackSettings | None = None) -> None: ...
    def format(self, exc: Exception) -> str: ...
