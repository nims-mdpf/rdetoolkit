from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from rdetoolkit.graph.readers.base import DetectionDecision, TableData, TableReader

READER_ENTRY_POINT_GROUP: Final[str]
AUTO: Final[str]

@dataclass(frozen=True, slots=True)
class _PendingEntry:
    name: str
    value: str
    load: Callable[[], object]

class ReaderRegistry:
    def __init__(self, readers: Iterable[TableReader] = ()) -> None: ...
    def register(self, reader: TableReader, *, replace: bool = False) -> None: ...
    def __contains__(self, reader_id: object) -> bool: ...
    def get(self, reader_id: str) -> TableReader: ...
    def ids(self) -> tuple[str, ...]: ...
    def origin(self, reader_id: str) -> str: ...
    def for_extension(self, suffix: str) -> tuple[TableReader, ...]: ...

class _DiscoveredRegistry(ReaderRegistry):
    def __init__(self, entries: Iterable[_PendingEntry]) -> None: ...

def builtin_readers() -> ReaderRegistry: ...
def discover_readers() -> ReaderRegistry: ...
def resolve_reader(
    reader: str | TableReader,
    path: Path,
    *,
    readers: ReaderRegistry | None = None,
) -> tuple[TableReader, DetectionDecision]: ...
def _load_table(
    path: str | Path,
    *,
    reader: str | TableReader = "auto",
    readers: ReaderRegistry | None = None,
) -> tuple[TableData, DetectionDecision]: ...
def read_table(
    path: str | Path,
    *,
    reader: str | TableReader = "auto",
    readers: ReaderRegistry | None = None,
) -> TableData: ...
