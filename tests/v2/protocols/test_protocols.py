"""Tests for rdetoolkit v2 Protocols.

This module tests that Protocol definitions correctly support runtime_checkable
interface checking using isinstance() on concrete implementations.
"""

from __future__ import annotations

from typing import Any

import pytest

from rdetoolkit.protocols import (
    DataValidator,
    FileReader,
    FormatHandler,
    MetadataExtractor,
    NodeRunner,
)
from rdetoolkit.result import Failure, Success


class TestFileReaderProtocol:
    """Tests for FileReader protocol."""

    def test_filereader_is_runtime_checkable(self) -> None:
        """FileReader protocol supports isinstance() checks at runtime."""
        # Behavioral check: a non-runtime_checkable Protocol raises TypeError
        # in isinstance(). Passing without raise means runtime_checkable is applied.
        isinstance(object(), FileReader)

    def test_filereader_isinstance_complete(self) -> None:
        """Class implementing all FileReader methods passes isinstance check."""

        class ConcreteFileReader:
            """Concrete implementation of FileReader."""

            def read(self, path: str) -> bytes:
                """Read binary data from file."""
                return b"test data"

        instance = ConcreteFileReader()
        assert isinstance(instance, FileReader)

    def test_filereader_isinstance_partial(self) -> None:
        """Class missing FileReader.read() fails isinstance check."""

        class IncompleteFileReader:
            """Missing read() method."""

            def other_method(self) -> None:
                pass

        instance = IncompleteFileReader()
        assert not isinstance(instance, FileReader)


class TestMetadataExtractorProtocol:
    """Tests for MetadataExtractor protocol."""

    def test_metadata_extractor_is_runtime_checkable(self) -> None:
        """MetadataExtractor protocol supports isinstance() checks."""
        isinstance(object(), MetadataExtractor)

    def test_metadata_extractor_isinstance_complete(self) -> None:
        """Class implementing MetadataExtractor methods passes isinstance."""

        class ConcreteMetadataExtractor:
            """Concrete implementation of MetadataExtractor."""

            def extract(self, data: bytes) -> dict[str, object]:
                """Extract metadata from binary data."""
                return {"key": "value"}

        instance = ConcreteMetadataExtractor()
        assert isinstance(instance, MetadataExtractor)

    def test_metadata_extractor_isinstance_partial(self) -> None:
        """Class missing MetadataExtractor.extract() fails isinstance."""

        class IncompleteMetadataExtractor:
            """Missing extract() method."""

            def other_method(self) -> None:
                pass

        instance = IncompleteMetadataExtractor()
        assert not isinstance(instance, MetadataExtractor)


class TestDataValidatorProtocol:
    """Tests for DataValidator protocol."""

    def test_data_validator_is_runtime_checkable(self) -> None:
        """DataValidator protocol supports isinstance() checks."""
        isinstance(object(), DataValidator)

    def test_data_validator_isinstance_complete(self) -> None:
        """Class implementing DataValidator methods passes isinstance."""

        class ConcreteDataValidator:
            """Concrete implementation of DataValidator."""

            def validate(self, data: dict[str, object]) -> bool:
                """Validate data dictionary."""
                return True

        instance = ConcreteDataValidator()
        assert isinstance(instance, DataValidator)

    def test_data_validator_isinstance_partial(self) -> None:
        """Class missing DataValidator.validate() fails isinstance."""

        class IncompleteDataValidator:
            """Missing validate() method."""

            def other_method(self) -> None:
                pass

        instance = IncompleteDataValidator()
        assert not isinstance(instance, DataValidator)


class TestNodeRunnerProtocol:
    """Tests for NodeRunner protocol."""

    def test_node_runner_is_runtime_checkable(self) -> None:
        """NodeRunner protocol supports isinstance() checks."""
        isinstance(object(), NodeRunner)

    def test_node_runner_isinstance_complete(self) -> None:
        """Class implementing NodeRunner methods passes isinstance."""

        class ConcreteNodeRunner:
            """Concrete implementation of NodeRunner."""

            def run(self, context: Any) -> Success[Any] | Failure[Exception]:
                """Run node with context."""
                return Success(None)

        instance = ConcreteNodeRunner()
        assert isinstance(instance, NodeRunner)

    def test_node_runner_isinstance_partial(self) -> None:
        """Class missing NodeRunner.run() fails isinstance."""

        class IncompleteNodeRunner:
            """Missing run() method."""

            def other_method(self) -> None:
                pass

        instance = IncompleteNodeRunner()
        assert not isinstance(instance, NodeRunner)


class TestFormatHandlerProtocol:
    """Tests for FormatHandler protocol."""

    def test_format_handler_is_runtime_checkable(self) -> None:
        """FormatHandler protocol supports isinstance() checks."""
        isinstance(object(), FormatHandler)

    def test_format_handler_isinstance_complete(self) -> None:
        """Class implementing all FormatHandler methods passes isinstance."""

        class ConcreteFormatHandler:
            """Concrete implementation of FormatHandler."""

            def can_handle(self, path: str) -> bool:
                """Check if handler can process file."""
                return path.endswith(".bin")

            def read(self, path: str) -> bytes:
                """Read file in specific format."""
                return b"binary data"

        instance = ConcreteFormatHandler()
        assert isinstance(instance, FormatHandler)

    def test_format_handler_isinstance_missing_can_handle(self) -> None:
        """Class missing FormatHandler.can_handle() fails isinstance."""

        class PartialFormatHandler:
            """Missing can_handle() method."""

            def read(self, path: str) -> bytes:
                return b"data"

        instance = PartialFormatHandler()
        assert not isinstance(instance, FormatHandler)

    def test_format_handler_isinstance_missing_read(self) -> None:
        """Class missing FormatHandler.read() fails isinstance."""

        class PartialFormatHandler:
            """Missing read() method."""

            def can_handle(self, path: str) -> bool:
                return True

        instance = PartialFormatHandler()
        assert not isinstance(instance, FormatHandler)

    def test_format_handler_isinstance_missing_both(self) -> None:
        """Class missing all FormatHandler methods fails isinstance."""

        class EmptyFormatHandler:
            """Missing both methods."""

            def other_method(self) -> None:
                pass

        instance = EmptyFormatHandler()
        assert not isinstance(instance, FormatHandler)
