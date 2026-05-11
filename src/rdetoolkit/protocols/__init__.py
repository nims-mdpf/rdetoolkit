"""Structural protocol definitions for rdetoolkit v2.

This package exports the core protocols used throughout the v2 DAG-based workflow engine.
All protocols support runtime isinstance() checks via @runtime_checkable decorator.
"""

from rdetoolkit.protocols.protocols import (
    DataValidator,
    FileReader,
    FormatHandler,
    MetadataExtractor,
    NodeRunner,
)

__all__ = [
    "FileReader",
    "MetadataExtractor",
    "DataValidator",
    "NodeRunner",
    "FormatHandler",
]
