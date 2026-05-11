"""Structural protocol definitions for rdetoolkit v2.

This module defines the core protocols used throughout the v2 DAG-based workflow engine.
Protocols use typing_extensions.Protocol with @runtime_checkable to enable isinstance()
checks at runtime while maintaining structural typing semantics.
"""

from __future__ import annotations

from typing import Any

from typing_extensions import Protocol, runtime_checkable

from rdetoolkit.result import Result


@runtime_checkable
class FileReader(Protocol):
    """Protocol for file reading implementations.

    Defines the interface for any object capable of reading binary file data
    from a file path.
    """

    def read(self, path: str) -> bytes:
        """Read binary data from file path.

        Args:
            path: File path to read from.

        Returns:
            Binary file contents as bytes.
        """
        ...


@runtime_checkable
class MetadataExtractor(Protocol):
    """Protocol for metadata extraction from binary data.

    Defines the interface for any object capable of parsing and extracting
    metadata from binary data.
    """

    def extract(self, data: bytes) -> dict[str, object]:
        """Extract metadata from binary data.

        Args:
            data: Binary data to extract metadata from.

        Returns:
            Dictionary containing extracted metadata with string keys and
            object values (open dict pattern).
        """
        ...


@runtime_checkable
class DataValidator(Protocol):
    """Protocol for data validation.

    Defines the interface for any object capable of validating structured data.
    """

    def validate(self, data: dict[str, object]) -> bool:
        """Validate data dictionary.

        Args:
            data: Data dictionary to validate.

        Returns:
            True if data is valid, False otherwise.
        """
        ...


@runtime_checkable
class NodeRunner(Protocol):
    """Protocol for node execution in DAG workflows.

    Defines the interface for any object capable of executing a workflow node
    with a given execution context.
    """

    def run(self, context: Any) -> Result[Any, Exception]:
        """Run node with execution context.

        Args:
            context: Execution context (type to be defined in Phase 1.5).

        Returns:
            Result wrapping either a success value or an Exception.
        """
        ...


@runtime_checkable
class FormatHandler(Protocol):
    """Protocol for file format detection and handling.

    Defines the interface for any object capable of detecting whether it can
    handle a specific file format and reading files in that format.
    """

    def can_handle(self, path: str) -> bool:
        """Check if handler can process file at path.

        Args:
            path: File path to check.

        Returns:
            True if handler supports the file format, False otherwise.
        """
        ...

    def read(self, path: str) -> bytes:
        """Read file in supported format.

        Args:
            path: File path to read.

        Returns:
            Binary file contents as bytes.
        """
        ...


__all__ = [
    "FileReader",
    "MetadataExtractor",
    "DataValidator",
    "NodeRunner",
    "FormatHandler",
]
