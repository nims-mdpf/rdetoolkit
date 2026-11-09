"""Builtin input nodes for text, tabular files, and ZIP archives."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any, cast

import pandas as pd
from charset_normalizer import detect

from rdetoolkit.core.node import node
from rdetoolkit.rdelogger import get_logger

_UTF8_FLAG = 0x800

logger = get_logger(__name__)


def _detect_encoding(path: Path) -> str:
    detected = cast(dict[str, Any], detect(path.read_bytes()))
    encoding = detected.get("encoding")
    return str(encoding or "utf-8")


@node(tags=["builtin", "io"], version="2.0.0", idempotent=True)
def read_text(path: Path) -> str:
    """Read a text file using detected character encoding.

    Ported from ``rde2util.CharDecEncoding.detect_text_file_encoding``.

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

    Encoding detection follows the v1 ``rde2util.CharDecEncoding`` behavior.

    Args:
        path: CSV file to read.

    Returns:
        Parsed data frame with the first row used as its header.
    """
    source = Path(path)
    return pd.read_csv(source, encoding=_detect_encoding(source))


@node(tags=["builtin", "io"], version="2.0.0", idempotent=True)
def read_excel(path: Path) -> pd.DataFrame:
    """Read the first worksheet of an Excel workbook.

    This is the node form of the pandas-backed Excel reads used by v1 RDE
    processing code.

    Args:
        path: Excel workbook to read.

    Returns:
        Parsed data frame.
    """
    return pd.read_excel(Path(path))


@node(tags=["builtin", "io"], version="2.0.0", idempotent=False)
def unzip_inputs(src_zip: Path, dst_dir: Path) -> None:
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
    """
    base_dir = Path(dst_dir).resolve()
    with zipfile.ZipFile(Path(src_zip)) as archive:
        for member in archive.infolist():
            if not member.flag_bits & _UTF8_FLAG:
                member.filename = member.filename.encode("cp437").decode("cp932")
            destination = (base_dir / member.filename).resolve()
            if destination != base_dir and base_dir not in destination.parents:
                logger.warning(
                    f"Skipping unsafe zip entry {member.filename!r}: path resolves outside {str(base_dir)!r}",
                )
                continue
            archive.extract(member, base_dir)
