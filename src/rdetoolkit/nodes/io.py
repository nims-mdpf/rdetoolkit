"""Builtin input nodes for text, tabular files, and ZIP archives."""

from __future__ import annotations

import zipfile
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
from charset_normalizer import detect

from rdetoolkit.core.node import node
from rdetoolkit.rdelogger import get_logger
from rdetoolkit.rde2util import CharDecEncoding

_UTF8_FLAG = 0x800

logger = get_logger(__name__)


def _detect_encoding(path: Path) -> str:
    # The legacy usual-codec set omits CP932 and can replace it with MacCyrillic.
    primary = detect(path.read_bytes()).get("encoding")
    if primary is not None and primary.lower() == "cp932":
        return primary
    return CharDecEncoding.detect_text_file_encoding(path) or "utf-8"


def _zip_destination(base_dir: Path, filename: str) -> Path:
    """Mirror zipfile's member sanitization before checking existing symlinks."""
    name = filename.replace("/", os.path.sep)
    if os.path.altsep:
        name = name.replace(os.path.altsep, os.path.sep)
    name = os.path.splitdrive(name)[1]
    parts = [part for part in name.split(os.path.sep) if part not in {"", ".", ".."}]
    if os.path.sep == "\\":
        translation = str.maketrans(':<>|"?*', "_______")
        parts = [part.translate(translation).rstrip(" .") for part in parts]
    return base_dir.joinpath(*parts).resolve()


@node(tags=["builtin", "io"], version="2.0.0", idempotent=True)
def read_text(path: Path) -> str:
    """Read a text file using detected character encoding.

    Uses the legacy encoding preference while retaining primary CP932 detection.

    Args:
        path: Text file to read.

    Returns:
        Decoded text content.
    """
    source = Path(path)
    return source.read_text(encoding=_detect_encoding(source))


@node(tags=["builtin", "io"], version="2.0.0", idempotent=True)
def read_csv_with_header(path: Path) -> pd.DataFrame:
    """Read a CSV whose first row contains its column names.

    Uses the legacy encoding preference while retaining primary CP932 detection.

    Args:
        path: CSV file to read.

    Returns:
        Parsed data frame with the first row used as its header.
    """
    source = Path(path)
    return pd.read_csv(source, encoding=_detect_encoding(source))


@node(tags=["builtin", "io"], version="2.0.0", idempotent=True)
def read_excel(
    path: Path, *, sheet_name: str | int = 0, header: int | list[int] | None = 0,
    skiprows: int | list[int] | None = None, nrows: int | None = None,
    usecols: str | list[int] | list[str] | None = None, **pandas_kwargs: object,
) -> pd.DataFrame:
    """Read a selected worksheet using pandas row and column options.

    This is the node form of the pandas-backed Excel reads used by v1 RDE
    processing code.

    Args:
        path: Excel workbook to read.
        sheet_name: Worksheet name or zero-based position.
        header: Header row positions, or None for unlabelled source data.
        skiprows: Number or positions of rows to skip.
        nrows: Maximum number of data rows to read.
        usecols: pandas column selection.
        pandas_kwargs: Additional pandas Excel reader options.

    Returns:
        Parsed data frame.
    """
    return pd.read_excel(Path(path), sheet_name=sheet_name, header=header, skiprows=skiprows, nrows=nrows, usecols=usecols, **pandas_kwargs)


@node(tags=["builtin", "io"], version="2.0.0", idempotent=True)
def read_json(path: Path) -> Any:
    """Read JSON using legacy encoding preferences with primary CP932 support.

    Args:
        path: JSON file to read.

    Returns:
        The decoded JSON value.

    Raises:
        OSError: If the source cannot be read.
        json.JSONDecodeError: If the source is not valid JSON.
    """
    source = Path(path)
    return json.loads(source.read_text(encoding=_detect_encoding(source)))


@node(tags=["builtin", "io"], version="2.0.0", idempotent=False)
def unzip_inputs(src_zip: Path, dst_dir: Path) -> list[Path]:
    """Extract a ZIP archive while repairing Shift-JIS member names.

    Ported from ``rde2util.unzip_japanese_zip`` and its filename decoder.
    Each member's destination is resolved -- symlinks already present in
    ``dst_dir`` included -- and a member that would land outside ``dst_dir``
    is skipped with a warning, the containment policy of
    ``impl._zip_encoding.extract_zip_with_encoding``. Without it a member named
    like a pre-existing outward link overwrote the file behind the link.

    Args:
        src_zip: ZIP archive to extract.
        dst_dir: Destination directory.

    Returns:
        Extracted file paths in archive order, including repeated members.
        Directory entries and unsafe destinations are excluded. Paths are
        absolute, matching the resolved extraction directory.
    """
    base_dir = Path(dst_dir).resolve()
    extracted: list[Path] = []
    with zipfile.ZipFile(Path(src_zip)) as archive:
        for member in archive.infolist():
            if not member.flag_bits & _UTF8_FLAG:
                member.filename = member.filename.encode("cp437").decode("cp932")
            destination = (base_dir / member.filename).resolve()
            sanitized = _zip_destination(base_dir, member.filename)
            if not destination.is_relative_to(base_dir) or not sanitized.is_relative_to(base_dir):
                logger.warning(
                    f"Skipping unsafe zip entry {member.filename!r}: path resolves outside {str(base_dir)!r}",
                )
                continue
            extracted_path = archive.extract(member, base_dir)
            if not member.is_dir():
                extracted.append(Path(extracted_path))
    return extracted
