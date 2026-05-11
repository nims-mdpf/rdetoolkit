"""Type stubs for rdetoolkit.protocols.protocols module."""

from typing import Any

from typing_extensions import Protocol, runtime_checkable

from rdetoolkit.result import Result

@runtime_checkable
class FileReader(Protocol):
    """Protocol for file reading implementations."""

    def read(self, path: str) -> bytes: ...

@runtime_checkable
class MetadataExtractor(Protocol):
    """Protocol for metadata extraction from binary data."""

    def extract(self, data: bytes) -> dict[str, object]: ...

@runtime_checkable
class DataValidator(Protocol):
    """Protocol for data validation."""

    def validate(self, data: dict[str, object]) -> bool: ...

@runtime_checkable
class NodeRunner(Protocol):
    """Protocol for node execution in DAG workflows."""

    def run(self, context: Any) -> Result[Any, Exception]: ...

@runtime_checkable
class FormatHandler(Protocol):
    """Protocol for file format detection and handling."""

    def can_handle(self, path: str) -> bool: ...
    def read(self, path: str) -> bytes: ...

__all__: list[str]
