"""V2 type definitions for rdetoolkit.

This module defines the core data types used across the v2 DAG-based workflow engine.

Note:
    This file is append-only. Do not modify existing v1 definitions.
"""

from __future__ import annotations

import json
import shutil
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
    """Immutable output path context with method-based API for saving artifacts.

    Provides both directory paths and convenience methods for writing
    processed data to the correct output locations.

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

    def save_csv(self, df: Any, filename: str) -> Path:
        """Save a DataFrame as CSV to the structured data directory.

        Args:
            df: A pandas-like DataFrame with a ``to_csv`` method.
            filename: Target filename (e.g. ``"normalized.csv"``).

        Returns:
            Path to the written CSV file.
        """
        self.struct.mkdir(parents=True, exist_ok=True)
        dest = self.struct / filename
        df.to_csv(dest, index=False)
        return dest

    def save_meta(self, metadata: Any) -> None:
        """Save metadata as JSON to the metadata directory.

        Args:
            metadata: A ``Metadata`` instance (with a ``.custom`` dict attribute)
                or a plain dict.
        """
        self.meta.mkdir(parents=True, exist_ok=True)
        dest = self.meta / "metadata.json"
        data = metadata.custom if hasattr(metadata, "custom") else metadata
        dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_graph(self, fig: Any, filename: str) -> Path:
        """Save a figure/graph to the main image directory.

        Args:
            fig: A figure object with a ``savefig`` or ``write_image`` method.
            filename: Target filename (e.g. ``"plot.png"``).

        Returns:
            Path to the written file.
        """
        self.main_image.mkdir(parents=True, exist_ok=True)
        dest = self.main_image / filename
        if hasattr(fig, "write_image"):
            fig.write_image(str(dest))
        elif hasattr(fig, "savefig"):
            fig.savefig(str(dest))
        else:
            msg = f"Unsupported figure type: {type(fig)}"
            raise TypeError(msg)
        return dest

    def save_file(self, content: bytes, filename: str) -> Path:
        """Save raw bytes to the structured data directory.

        Args:
            content: Binary content to write.
            filename: Target filename.

        Returns:
            Path to the written file.
        """
        self.struct.mkdir(parents=True, exist_ok=True)
        dest = self.struct / filename
        dest.write_bytes(content)
        return dest

    def save_thumbnail(self, image_path: Path) -> Path:
        """Copy an image to the thumbnail directory.

        Args:
            image_path: Source image file path.

        Returns:
            Path to the copied file in the thumbnail directory.
        """
        self.thumbnail.mkdir(parents=True, exist_ok=True)
        dest = self.thumbnail / image_path.name
        shutil.copy2(image_path, dest)
        return dest

    def save_main_image(self, image_path: Path) -> Path:
        """Copy an image to the main image directory.

        Args:
            image_path: Source image file path.

        Returns:
            Path to the copied file in the main image directory.
        """
        self.main_image.mkdir(parents=True, exist_ok=True)
        dest = self.main_image / image_path.name
        shutil.copy2(image_path, dest)
        return dest

    def save_raw(self, source_path: Path) -> Path:
        """Copy a file to the raw data directory.

        Args:
            source_path: Source file path.

        Returns:
            Path to the copied file in the raw directory.
        """
        self.raw.mkdir(parents=True, exist_ok=True)
        dest = self.raw / source_path.name
        shutil.copy2(source_path, dest)
        return dest


@dataclass(slots=True)
class Metadata:
    """Mutable metadata container with custom and basic sections.

    Attributes:
        custom: User-defined metadata key-value pairs.
        basic: Optional basic/system metadata.
    """

    custom: dict[str, Any] = field(default_factory=dict)
    basic: dict[str, Any] | None = None

    def set(self, key: str, value: Any) -> None:
        """Set a custom metadata entry.

        Args:
            key: Metadata key.
            value: Metadata value.
        """
        self.custom[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a custom metadata entry.

        Args:
            key: Metadata key.
            default: Value to return if key is not found.

        Returns:
            The value for the key, or *default*.
        """
        return self.custom.get(key, default)


@dataclass(frozen=True, slots=True)
class InvoiceData:
    """Container for parsed invoice data injected by the Runner.

    Attributes:
        raw: The raw invoice content dict.
        mode: Processing mode (e.g. ``"invoice"``, ``"excelinvoice"``).
        schema: Optional JSON schema for the invoice.
    """

    raw: dict[str, Any] = field(default_factory=dict)
    mode: str = ""
    schema: dict[str, Any] | None = None

    def get_field(self, key: str, default: Any = None) -> Any:
        """Get a top-level field from the raw invoice data.

        Args:
            key: Field name.
            default: Value to return if key is not found.

        Returns:
            The value for the key, or *default*.
        """
        return self.raw.get(key, default)

    def get_custom_fields(self) -> dict[str, Any]:
        """Extract custom (non-system) fields from the raw invoice data.

        Returns:
            Dict of fields whose keys do not start with ``"_"``.
        """
        return {k: v for k, v in self.raw.items() if not k.startswith("_")}


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
