"""Appendix M migration-only structural contracts for rdetoolkit v2."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from typing_extensions import Protocol, runtime_checkable

from rdetoolkit.types import InputPaths, InvoiceData, Metadata, OutputContext


@runtime_checkable
class FileReader(Protocol):
    """Migration-only contract for v1-style file-reader classes.

    New code should use templates (Design §5.2) or plain functions (Design §3).
    """

    def read(self, paths: InputPaths) -> tuple[Metadata, pd.DataFrame]:
        """Read metadata and structured data from input paths."""
        ...


@runtime_checkable
class MetadataExtractor(Protocol):
    """Migration-only contract for v1-style metadata extractors.

    New code should use templates (Design §5.2) or plain functions (Design §3).
    """

    def extract(self, df: pd.DataFrame, invoice: InvoiceData) -> Metadata:
        """Extract metadata from structured data and invoice content."""
        ...


@runtime_checkable
class DataProcessor(Protocol):
    """Migration-only contract for v1-style data processors.

    New code should use templates (Design §5.2) or plain functions (Design §3).
    """

    def process(self, df: pd.DataFrame, meta: Metadata) -> pd.DataFrame:
        """Process structured data using extracted metadata."""
        ...


@runtime_checkable
class ResultWriter(Protocol):
    """Migration-only contract for v1-style result writers.

    New code should use templates (Design §5.2) or plain functions (Design §3).
    """

    def write(self, df: pd.DataFrame, meta: Metadata, out: OutputContext) -> None:
        """Write structured data and metadata to an output context."""
        ...


@runtime_checkable
class Visualizer(Protocol):
    """Migration-only contract for v1-style visualizers.

    New code should use templates (Design §5.2) or plain functions (Design §3).
    """

    def visualize(self, df: pd.DataFrame, out: OutputContext) -> list[Path]:
        """Render visualizations and return their output paths."""
        ...


__all__ = [
    "FileReader",
    "MetadataExtractor",
    "DataProcessor",
    "ResultWriter",
    "Visualizer",
]
