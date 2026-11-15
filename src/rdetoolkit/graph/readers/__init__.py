"""Table readers for the graph engine (GE-04).

Importing this package registers nothing: registries are created on demand with
``ReaderRegistry(...)``, ``builtin_readers()`` or ``discover_readers()``.
"""

from rdetoolkit.graph.readers.base import ColumnProvenance, DetectionDecision, FormatCandidate, TableData, TableReader
from rdetoolkit.graph.readers.registry import (
    READER_ENTRY_POINT_GROUP,
    ReaderRegistry,
    builtin_readers,
    discover_readers,
    read_table,
    resolve_reader,
)

__all__ = [
    "READER_ENTRY_POINT_GROUP",
    "ColumnProvenance",
    "DetectionDecision",
    "FormatCandidate",
    "ReaderRegistry",
    "TableData",
    "TableReader",
    "builtin_readers",
    "discover_readers",
    "read_table",
    "resolve_reader",
]
