"""Builtin table readers: thin adapters over the legacy parser classes (GE-04).

Each reader delegates to the parser that ``ParserFactory`` / ``CSVParser`` already use,
so frames are exactly what the legacy formats produce; the adapter only adds column
provenance. Builtins claim no file suffix: they are chosen by id or by content.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pandas as pd

from rdetoolkit.graph.parsers.base import CSVParser
from rdetoolkit.graph.parsers.noheader_parser import NoHeaderParser
from rdetoolkit.graph.parsers.standard_parser import StandardParser
from rdetoolkit.graph.parsers.transpose_parser import TransposeParser
from rdetoolkit.graph.readers.base import ColumnProvenance, ColumnSource, TableData

#: pandas names an empty header cell ``"Unnamed: <n>"``.
_PANDAS_UNNAMED_PREFIX: Final = "Unnamed: "
#: ``TransposeParser`` names the label column ``"index"`` when the corner cell is empty.
_TRANSPOSE_UNNAMED: Final = "index"


def _provenance(frame: pd.DataFrame, sources: list[ColumnSource]) -> tuple[ColumnProvenance, ...]:
    return tuple(ColumnProvenance(name=str(name), source=source, source_index=index) for index, (name, source) in enumerate(zip(frame.columns, sources, strict=True)))


class StandardReader:
    """Header row, then data rows (``csv_format="standard"``)."""

    reader_id: Final = "standard"
    extensions: Final[tuple[str, ...]] = ()

    def read(self, path: Path) -> TableData:
        """Read ``path`` with ``StandardParser``.

        Args:
            path: The CSV file.

        Returns:
            The frame; empty header cells are marked ``"generated"``.
        """
        frame = StandardParser().parse(path)
        sources: list[ColumnSource] = ["generated" if str(name).startswith(_PANDAS_UNNAMED_PREFIX) else "header" for name in frame.columns]
        return TableData(frame=frame, reader_id=self.reader_id, columns=_provenance(frame, sources))


class TransposeReader:
    """One series per row, labels in the first column (``csv_format="transpose"``)."""

    reader_id: Final = "transpose"
    extensions: Final[tuple[str, ...]] = ()

    def read(self, path: Path) -> TableData:
        """Read ``path`` with ``TransposeParser``.

        Args:
            path: The CSV file.

        Returns:
            The transposed frame; ``source_index`` is the row in the file.
        """
        frame = TransposeParser().parse(path)
        sources: list[ColumnSource] = ["header"] * frame.shape[1]
        if sources and str(frame.columns[0]) == _TRANSPOSE_UNNAMED:
            sources[0] = "generated"
        return TableData(frame=frame, reader_id=self.reader_id, columns=_provenance(frame, sources))


class NoHeaderReader:
    """Data rows only; names are generated (``csv_format="noheader"``)."""

    reader_id: Final = "noheader"
    extensions: Final[tuple[str, ...]] = ()

    def read(self, path: Path) -> TableData:
        """Read ``path`` with ``NoHeaderParser``.

        Args:
            path: The CSV file.

        Returns:
            The frame with generated ``Column_<n>`` names.
        """
        frame = NoHeaderParser().parse(path)
        return TableData(frame=frame, reader_id=self.reader_id, columns=_provenance(frame, ["generated"] * frame.shape[1]))


class MetaBlockReader:
    """Leading ``#`` metadata lines, then data (the legacy ``CSVParser`` meta-block format)."""

    reader_id: Final = "meta_block"
    extensions: Final[tuple[str, ...]] = ()

    def read(self, path: Path) -> TableData:
        """Read ``path`` with ``CSVParser.parse`` and keep its metadata.

        Args:
            path: The CSV file.

        Returns:
            The frame, with column names built from the metadata block.
        """
        frame, metadata = CSVParser.parse(path)
        columns = _provenance(frame, ["metadata"] * frame.shape[1])
        return TableData(frame=frame, reader_id=self.reader_id, columns=columns, metadata=metadata)


#: Builtin reader types in id order; instances are created per registry.
BUILTIN_READER_TYPES: Final = (MetaBlockReader, NoHeaderReader, StandardReader, TransposeReader)
