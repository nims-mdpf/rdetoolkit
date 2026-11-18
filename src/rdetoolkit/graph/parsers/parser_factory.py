from __future__ import annotations

import importlib
from pathlib import Path
from typing import Final

import pandas as pd

from rdetoolkit.graph.parsers.base import CSVParser, CSVParserProtocol
from rdetoolkit.graph.parsers.noheader_parser import NoHeaderParser
from rdetoolkit.graph.parsers.standard_parser import StandardParser
from rdetoolkit.graph.parsers.transpose_parser import TransposeParser


#: The detector lives in ``rdetoolkit.graph.readers``, which imports this package; it is
#: loaded on first use so either package can be imported first.
_DETECTION_MODULE: Final = "rdetoolkit.graph.readers.detection"


class _MetaBlockParser:
    """``CSVParserProtocol`` view of the legacy meta-block format (the frame of ``CSVParser.parse``)."""

    def parse(self, csv_path: Path) -> pd.DataFrame:
        """Parse ``csv_path`` with ``CSVParser.parse`` and drop the metadata."""
        return CSVParser.parse(csv_path)[0]


_DETECTED_PARSERS: Final[dict[str, type[StandardParser | TransposeParser | NoHeaderParser]]] = {
    "standard": StandardParser,
    "transpose": TransposeParser,
    "noheader": NoHeaderParser,
}


class ParserFactory:
    """Factory for creating CSV parsers.

    Supports:
        - Explicit format selection
        - Conservative auto-detection (``rdetoolkit.graph.readers.detection``)

    Example:
        >>> factory = ParserFactory()
        >>> parser = factory.create("standard")
        >>> df = parser.parse(Path("data.csv"))
    """

    @staticmethod
    def create(format_type: str) -> CSVParserProtocol:
        """Create parser for specified format.

        Args:
            format_type: CSV format type
                - "standard": Standard CSV with column headers
                - "transpose": Transposed CSV (row-oriented)
                - "noheader": CSV without headers

        Returns:
            Appropriate CSVParser implementation

        Raises:
            ValueError: If format_type is not supported

        Example:
            >>> parser = ParserFactory.create("standard")
            >>> isinstance(parser, StandardParser)
            True
        """
        format_lower = format_type.lower()

        if format_lower == "standard":
            return StandardParser()
        if format_lower == "transpose":
            return TransposeParser()
        if format_lower == "noheader":
            return NoHeaderParser()

        msg = (
            f"Unsupported CSV format: {format_type!r}. "
            f"Supported formats: 'standard', 'transpose', 'noheader'"
        )
        raise ValueError(msg)

    @staticmethod
    def auto_detect(csv_path: Path) -> CSVParserProtocol:
        """Detect the CSV format and return a parser configured for it.

        Uses ``detect_table_format``: a bounded, read-only sample decides the encoding,
        delimiter, metadata block, header row and transposed layout. Nothing is guessed:
        a file whose format is not clear raises instead of being read as headerless.

        Args:
            csv_path: Path to CSV file

        Returns:
            The parser of the detected format, reading with the detected encoding and
            delimiter (a metadata block is parsed like ``CSVParser.parse``).

        Raises:
            FileNotFoundError: If CSV file doesn't exist
            InvalidCSVFormatError: If the file is empty or too large to sniff
            AmbiguousFormatError: If the format is ambiguous; the message names the
                candidates and suggests ``--csv-format`` / ``create(<format>)``
        """
        detection = importlib.import_module(_DETECTION_MODULE)
        path = Path(csv_path)
        decision = detection.detect_table_format(path)
        reader_id: str = detection.require_selection(path, decision)
        if reader_id not in _DETECTED_PARSERS:
            return _MetaBlockParser()
        return _DETECTED_PARSERS[reader_id](encoding=decision.encoding, delimiter=decision.delimiter)
