from pathlib import Path
from typing import Final

from rdetoolkit.graph.readers.base import TableData, TableReader

class StandardReader:
    reader_id: Final[str]
    extensions: Final[tuple[str, ...]]
    encoding: str | None
    delimiter: str | None
    def __init__(self, *, encoding: str | None = None, delimiter: str | None = None) -> None: ...
    def read(self, path: Path) -> TableData: ...

class TransposeReader:
    reader_id: Final[str]
    extensions: Final[tuple[str, ...]]
    encoding: str | None
    delimiter: str | None
    def __init__(self, *, encoding: str | None = None, delimiter: str | None = None) -> None: ...
    def read(self, path: Path) -> TableData: ...

class NoHeaderReader:
    reader_id: Final[str]
    extensions: Final[tuple[str, ...]]
    encoding: str | None
    delimiter: str | None
    def __init__(self, *, encoding: str | None = None, delimiter: str | None = None) -> None: ...
    def read(self, path: Path) -> TableData: ...

class MetaBlockReader:
    reader_id: Final[str]
    extensions: Final[tuple[str, ...]]
    def read(self, path: Path) -> TableData: ...

BUILTIN_READER_TYPES: Final[tuple[type[MetaBlockReader], type[NoHeaderReader], type[StandardReader], type[TransposeReader]]]

def configured_builtin_reader(reader_id: str, *, encoding: str | None = None, delimiter: str | None = None) -> TableReader: ...
