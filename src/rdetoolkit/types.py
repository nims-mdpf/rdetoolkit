"""V2 type definitions for rdetoolkit.

This module defines the core data types used across the v2 DAG-based workflow engine.
All types are frozen dataclasses for immutability and safety.

Note:
    This file is append-only. Do not modify existing definitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class InputPaths:
    """Immutable input directory paths for v2 workflow processing.

    Mirrors the v1 RdeInputDirPaths structure with a simplified interface.

    Attributes:
        inputdata: Path to the input data directory.
        invoice: Path to the invoice directory.
        tasksupport: Path to the task support directory.
    """

    inputdata: Path
    invoice: Path
    tasksupport: Path


@dataclass(frozen=True, slots=True)
class OutputContext:
    """Immutable output path context for v2 workflow processing.

    Provides access to output directories where processed data is written.

    Attributes:
        raw: Path to the raw data directory.
        struct: Path to the structured data directory.
        main_image: Path to the main image directory.
        other_image: Path to the other image directory.
        meta: Path to the metadata directory.
        thumbnail: Path to the thumbnail directory.
        logs: Path to the logs directory.
    """

    raw: Path
    struct: Path
    main_image: Path
    other_image: Path
    meta: Path
    thumbnail: Path
    logs: Path


@dataclass(frozen=True, slots=True)
class Metadata:
    """Container for metadata key-value pairs.

    Attributes:
        data: Dictionary of metadata entries.
    """

    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class InvoiceData:
    """Container for invoice schema and content.

    Attributes:
        schema: JSON schema definition for the invoice.
        content: Invoice content data.
    """

    schema: dict[str, Any] = field(default_factory=dict)
    content: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IterationInfo:
    """Information about the current processing iteration.

    Attributes:
        index: Zero-based iteration index.
        total: Total number of iterations.
        mode: Processing mode name (e.g. 'invoice', 'excelinvoice').
    """

    index: int
    total: int
    mode: str
