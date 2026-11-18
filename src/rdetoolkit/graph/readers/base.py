"""Reader contract of the graph engine: ``TableReader``, ``TableData`` and the selection record (GE-04).

A reader turns one file into a ``TableData``: the frame plus where each column name
came from. ``DetectionDecision`` records which reader was selected and why, so the
selection is inspectable after the fact.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Protocol, runtime_checkable

import pandas as pd

ColumnSource = Literal["header", "generated", "metadata"]


@dataclass(frozen=True, slots=True)
class ColumnProvenance:
    """Where one column name of a ``TableData`` frame came from.

    Attributes:
        name: The column name in the frame.
        source: ``"header"`` (read from the file), ``"generated"`` (made up by the
            reader, for example ``Column_0``) or ``"metadata"`` (built from a
            metadata block).
        source_index: The column (or, for transposed input, the row) in the file.
    """

    name: str
    source: ColumnSource
    source_index: int


@dataclass(frozen=True, slots=True, eq=False)
class TableData:
    """One table read from a file.

    Attributes:
        frame: The table; columns are addressed by position.
        reader_id: Id of the reader that produced it.
        columns: One provenance entry per frame column, in column order.
        metadata: Read-only extra information (for example ``{"title": ...}``).
    """

    frame: pd.DataFrame
    reader_id: str
    columns: tuple[ColumnProvenance, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Freeze the provenance and metadata and check they describe the frame.

        Raises:
            ValueError: If ``reader_id`` is empty or the provenance count differs from
                the number of frame columns.
        """
        if not self.reader_id:
            msg = "TableData.reader_id must be a non-empty string"
            raise ValueError(msg)
        object.__setattr__(self, "columns", tuple(self.columns))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        width = self.frame.shape[1]
        if len(self.columns) != width:
            msg = f"TableData has {len(self.columns)} column provenance entries for {width} frame columns"
            raise ValueError(msg)


@runtime_checkable
class TableReader(Protocol):
    """A file-format adapter usable by ``render_graph``, ``read_table`` and ``csv2graph``.

    Implementations need no base class: any object with these members qualifies.
    """

    @property
    def reader_id(self) -> str:
        """Unique id, for example ``"vendor.instrument"`` (``"auto"`` is reserved)."""
        ...

    @property
    def extensions(self) -> tuple[str, ...]:
        """Lower-case suffixes with a dot this reader claims under ``"auto"``; ``()`` claims none."""
        ...

    def read(self, path: Path) -> TableData:
        """Read ``path`` into a ``TableData``."""
        ...


@dataclass(frozen=True, slots=True)
class FormatCandidate:
    """One reader considered for a file.

    Attributes:
        reader_id: The reader.
        confidence: ``0.0`` .. ``1.0``.
        evidence: Human-readable reasons, most important first.
    """

    reader_id: str
    confidence: float
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DetectionDecision:
    """Which reader was selected for a file and why.

    Attributes:
        selected: The chosen reader id; ``None`` when the choice was ambiguous.
        forced: ``True`` when the caller named the reader (id or instance).
        candidates: Readers considered, by confidence (descending) then id.
        encoding: Detected text encoding, when content was sniffed.
        delimiter: Detected delimiter, when content was sniffed.
        sampled_bytes: Bytes read to decide.
        sampled_rows: Rows read to decide.
        truncated: ``True`` when the file is larger than the sample.
        preview_columns: Column names the selected reader would produce, when known.
        data_rows: Exact data-row count when known.
    """

    selected: str | None
    forced: bool
    candidates: tuple[FormatCandidate, ...]
    encoding: str | None = None
    delimiter: str | None = None
    sampled_bytes: int = 0
    sampled_rows: int = 0
    truncated: bool = False
    preview_columns: tuple[str, ...] = ()
    data_rows: int | None = None

    def explain(self) -> str:
        """Describe the decision as text, one line per fact.

        Returns:
            The selection (or ``"none (ambiguous)"``); for a sniffed decision the
            encoding, delimiter, sample size, previewed columns and row count; then
            every candidate with its confidence and evidence.
        """
        how = "forced" if self.forced else "auto"
        lines = [f"selected: {self.selected} ({how})" if self.selected is not None else "selected: none (ambiguous)"]
        lines.extend(self._sample_lines())
        for candidate in self.candidates:
            lines.append(f"candidate {candidate.reader_id} ({candidate.confidence:.2f})")
            lines.extend(f"  - {reason}" for reason in candidate.evidence)
        return "\n".join(lines)

    def _sample_lines(self) -> list[str]:
        """Facts about the content sample; nothing for a decision made without reading the file."""
        if not self.sampled_bytes:
            return []
        delimiter = "undetermined" if self.delimiter is None else repr(self.delimiter)
        extent = "truncated" if self.truncated else "complete"
        lines = [
            f"encoding: {self.encoding or 'undetermined'}",
            f"delimiter: {delimiter}",
            f"sampled: {self.sampled_bytes} bytes, {self.sampled_rows} rows ({extent})",
        ]
        if self.preview_columns:
            lines.append("columns: " + ", ".join(self.preview_columns))
        if self.data_rows is not None:
            lines.append(f"data rows: {self.data_rows}")
        return lines
