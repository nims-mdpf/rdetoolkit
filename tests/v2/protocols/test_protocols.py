"""Tests for rdetoolkit v2 Protocols -- 付録M migration-only set (Session F1,
TC-F1-PROTO-*).

REPLACES the pre-F1 file wholesale (see
``local/develop/v2/tasks/session_f1.md``'s UPDATE table -- this is a
sanctioned, documented strengthening, not a weakening: the 5 retired
Protocols (``FileReader``/``MetadataExtractor`` with pre-R5 placeholder
signatures, ``DataValidator``, ``NodeRunner``, ``FormatHandler``) are
replaced by 付録M's exact 5 Protocols, checked against real v2 domain types
(``InputPaths``, ``Metadata``, ``InvoiceData``, ``pd.DataFrame``,
``OutputContext``, ``Path``) instead of ``Any``/``dict[str, object]``/
``bytes`` placeholders. Every deleted symbol name
(``DataValidator``/``NodeRunner``/``FormatHandler``) must be recorded in a
new root-level ``CHANGELOG_v2.md`` -- verified separately by the
orchestrator's grep guard #10, not re-checked here.

Pinned signatures (this file's binding contract, per the Current-State
Survey + UPDATE table + [GOAL CONTRACT] DONE clause):

    FileReader.read(self, paths: InputPaths) -> tuple[Metadata, pd.DataFrame]
    MetadataExtractor.extract(self, df: pd.DataFrame, invoice: InvoiceData) -> Metadata
    DataProcessor.process(self, df: pd.DataFrame, meta: Metadata) -> pd.DataFrame
    ResultWriter.write(self, df: pd.DataFrame, meta: Metadata, out: OutputContext) -> None
    Visualizer.visualize(self, df: pd.DataFrame, out: OutputContext) -> list[Path]

All 5 names are imported together in one top-level statement (mirroring the
pre-F1 file's own style) -- this is deliberate: it means the entire file
collection-errors as a single unit until ALL 5 names exist simultaneously
(``protocols/protocols.py`` is a wholesale, atomic replacement per this
session's scope, not an incremental one-protocol-at-a-time change), exactly
mirroring the whole-file collection-error pattern already established for
``tests/v2/nodes/*.py`` in this same session.

Each Protocol must also document its migration-only status (Design §5.1
constraint: "Protocol は DI に使わない。正面ドキュメントに載せない" and the
Goal Contract's explicit docstring requirement) -- checked mechanically
below via a case-insensitive "migration" substring search on each class's
``__doc__``, not by pinning exact wording.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from rdetoolkit.protocols import (
    DataProcessor,
    FileReader,
    MetadataExtractor,
    ResultWriter,
    Visualizer,
)
from rdetoolkit.types import InputPaths, InvoiceData, Metadata, OutputContext


class TestFileReaderProtocol:
    """TC-F1-PROTO-FILEREADER-*."""

    def test_filereader_is_runtime_checkable(self) -> None:
        """FileReader protocol supports isinstance() checks at runtime."""
        isinstance(object(), FileReader)

    def test_filereader_isinstance_complete(self) -> None:
        """A class implementing read(paths: InputPaths) -> tuple[Metadata, pd.DataFrame] passes isinstance."""

        class ConcreteFileReader:
            def read(self, paths: InputPaths) -> tuple[Metadata, pd.DataFrame]:
                return Metadata(), pd.DataFrame()

        assert isinstance(ConcreteFileReader(), FileReader)

    def test_filereader_isinstance_partial(self) -> None:
        """A class missing read() fails isinstance."""

        class IncompleteFileReader:
            def other_method(self) -> None:
                pass

        assert not isinstance(IncompleteFileReader(), FileReader)


class TestMetadataExtractorProtocol:
    """TC-F1-PROTO-METADATAEXTRACTOR-*."""

    def test_metadata_extractor_is_runtime_checkable(self) -> None:
        """MetadataExtractor protocol supports isinstance() checks."""
        isinstance(object(), MetadataExtractor)

    def test_metadata_extractor_isinstance_complete(self) -> None:
        """A class implementing extract(df, invoice) -> Metadata passes isinstance."""

        class ConcreteMetadataExtractor:
            def extract(self, df: pd.DataFrame, invoice: InvoiceData) -> Metadata:
                return Metadata()

        assert isinstance(ConcreteMetadataExtractor(), MetadataExtractor)

    def test_metadata_extractor_isinstance_partial(self) -> None:
        """A class missing extract() fails isinstance."""

        class IncompleteMetadataExtractor:
            def other_method(self) -> None:
                pass

        assert not isinstance(IncompleteMetadataExtractor(), MetadataExtractor)


class TestDataProcessorProtocol:
    """TC-F1-PROTO-DATAPROCESSOR-* (new in 付録M)."""

    def test_data_processor_is_runtime_checkable(self) -> None:
        """DataProcessor protocol supports isinstance() checks."""
        isinstance(object(), DataProcessor)

    def test_data_processor_isinstance_complete(self) -> None:
        """A class implementing process(df, meta) -> pd.DataFrame passes isinstance."""

        class ConcreteDataProcessor:
            def process(self, df: pd.DataFrame, meta: Metadata) -> pd.DataFrame:
                return df

        assert isinstance(ConcreteDataProcessor(), DataProcessor)

    def test_data_processor_isinstance_partial(self) -> None:
        """A class missing process() fails isinstance."""

        class IncompleteDataProcessor:
            def other_method(self) -> None:
                pass

        assert not isinstance(IncompleteDataProcessor(), DataProcessor)


class TestResultWriterProtocol:
    """TC-F1-PROTO-RESULTWRITER-* (new in 付録M)."""

    def test_result_writer_is_runtime_checkable(self) -> None:
        """ResultWriter protocol supports isinstance() checks."""
        isinstance(object(), ResultWriter)

    def test_result_writer_isinstance_complete(self) -> None:
        """A class implementing write(df, meta, out) -> None passes isinstance."""

        class ConcreteResultWriter:
            def write(self, df: pd.DataFrame, meta: Metadata, out: OutputContext) -> None:
                return None

        assert isinstance(ConcreteResultWriter(), ResultWriter)

    def test_result_writer_isinstance_partial(self) -> None:
        """A class missing write() fails isinstance."""

        class IncompleteResultWriter:
            def other_method(self) -> None:
                pass

        assert not isinstance(IncompleteResultWriter(), ResultWriter)


class TestVisualizerProtocol:
    """TC-F1-PROTO-VISUALIZER-* (new in 付録M)."""

    def test_visualizer_is_runtime_checkable(self) -> None:
        """Visualizer protocol supports isinstance() checks."""
        isinstance(object(), Visualizer)

    def test_visualizer_isinstance_complete(self) -> None:
        """A class implementing visualize(df, out) -> list[Path] passes isinstance."""

        class ConcreteVisualizer:
            def visualize(self, df: pd.DataFrame, out: OutputContext) -> list[Path]:
                return []

        assert isinstance(ConcreteVisualizer(), Visualizer)

    def test_visualizer_isinstance_partial(self) -> None:
        """A class missing visualize() fails isinstance."""

        class IncompleteVisualizer:
            def other_method(self) -> None:
                pass

        assert not isinstance(IncompleteVisualizer(), Visualizer)


class TestProtocolsDocumentMigrationOnlyStatus:
    """TC-F1-PROTO-DOCS-001: every one of the 5 Protocols must document that
    it is migration-only, not a front-facing DI mechanism (Design §5.1 /
    [GOAL CONTRACT] docstring requirement) -- checked mechanically, not by
    pinning exact wording."""

    @pytest.mark.parametrize(
        "protocol_cls",
        [FileReader, MetadataExtractor, DataProcessor, ResultWriter, Visualizer],
        ids=["FileReader", "MetadataExtractor", "DataProcessor", "ResultWriter", "Visualizer"],
    )
    def test_docstring_mentions_migration_only_status(self, protocol_cls: type[Any]) -> None:
        doc = protocol_cls.__doc__ or ""
        assert "migration" in doc.lower(), f"{protocol_cls.__name__}.__doc__ must document migration-only status: {doc!r}"


class TestOldRetiredProtocolsAreGone:
    """TC-F1-PROTO-RETIRED-001: the 3 deleted symbols must no longer be
    importable from rdetoolkit.protocols (DataValidator, NodeRunner,
    FormatHandler -- retired, recorded in CHANGELOG_v2.md per grep guard #10)."""

    def test_data_validator_no_longer_exported(self) -> None:
        import rdetoolkit.protocols as protocols_pkg

        assert not hasattr(protocols_pkg, "DataValidator")

    def test_node_runner_no_longer_exported(self) -> None:
        import rdetoolkit.protocols as protocols_pkg

        assert not hasattr(protocols_pkg, "NodeRunner")

    def test_format_handler_no_longer_exported(self) -> None:
        import rdetoolkit.protocols as protocols_pkg

        assert not hasattr(protocols_pkg, "FormatHandler")
