"""Builtin input nodes for text, tabular files, and ZIP archives."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any, cast

import pandas as pd
from charset_normalizer import detect

from rdetoolkit.core.node import node

_UTF8_FLAG = 0x800


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

    Args:
        src_zip: ZIP archive to extract.
        dst_dir: Destination directory.
    """
    with zipfile.ZipFile(Path(src_zip)) as archive:
        for member in archive.infolist():
            if not member.flag_bits & _UTF8_FLAG:
                member.filename = member.filename.encode("cp437").decode("cp932")
            archive.extract(member, Path(dst_dir))
