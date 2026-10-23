"""Shared helpers for extracting ZIP archives whose filenames are not UTF-8.

The ZIP specification only guarantees the filename encoding when general purpose
bit 11 (the language encoding flag, ``0x800``) is set, in which case the name is
UTF-8. When the flag is absent, :mod:`zipfile` falls back to decoding the raw
bytes as cp437 for historical reasons. Archives produced on Japanese Windows
store filenames as cp932, so cp437 decoding turns ``2θ_θ.TXT`` into
``2â╞_â╞.TXT``.

Because cp437 maps every byte to a character, that mis-decoding is lossless and
therefore reversible: re-encoding the mojibake string as cp437 recovers the
original bytes, which can then be decoded with the true encoding.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Final

import charset_normalizer

from rdetoolkit.rdelogger import get_logger

logger = get_logger(__name__)

# ZIP general purpose bit flag 11: filenames are UTF-8 when set.
LANG_ENC_FLAG: Final = 0x800

# Encoding zipfile uses for filenames when LANG_ENC_FLAG is absent.
FALLBACK_ENCODING: Final = "cp437"

# Tried before statistical detection: RDE archives originate on Japanese Windows,
# and charset_normalizer misreads short cp932 filenames (see resolve_filename).
PREFERRED_ENCODING: Final = "cp932"


def resolve_filename(zip_info: zipfile.ZipInfo) -> str:
    """Recover the true filename for a ZIP entry.

    ``zipfile`` has already decoded ``zip_info.filename`` by the time this is
    called: as UTF-8 when the language encoding flag is set, otherwise as cp437.
    This function decides whether that decoding can be trusted and, when it
    cannot, re-decodes the name using the encoding the bytes are actually in.

    cp932 is tried before statistical detection because
    ``charset_normalizer.detect()`` needs more data than a filename carries to be
    reliable: it reads ``NB1_800_20220214_2θ_θ.TXT`` as cp949 and ``データ.txt``
    as utf_16_le, corrupting both. Detection is kept only for names cp932 cannot
    decode at all.

    Args:
        zip_info (zipfile.ZipInfo): Entry metadata as parsed by :mod:`zipfile`.

    Returns:
        str: The filename to extract the entry under. Falls back to the name
            :mod:`zipfile` produced when the true encoding cannot be determined.
    """
    # The spec guarantees UTF-8 here, so zipfile already decoded it correctly.
    # Running detection anyway risks corrupting a name that is already right.
    if zip_info.flag_bits & LANG_ENC_FLAG:
        return zip_info.filename

    # cp437 maps all 256 byte values, so this round-trips back to the raw bytes.
    raw = zip_info.filename.encode(FALLBACK_ENCODING)

    try:
        return raw.decode(PREFERRED_ENCODING)
    except UnicodeDecodeError:
        pass

    detected = charset_normalizer.detect(raw)
    encoding = detected.get("encoding") or FALLBACK_ENCODING
    try:
        return raw.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        # Detection is heuristic; one unreadable name must not abort the archive.
        logger.warning(
            f"Failed to decode zip entry filename as {encoding!r}; extracting as {zip_info.filename!r}",
        )
        return zip_info.filename


def extract_zip_with_encoding(zip_path: Path | str, extract_path: Path | str) -> None:
    """Extract a ZIP archive, repairing filenames that are not UTF-8.

    Each entry's name is resolved via :func:`resolve_filename` before extraction,
    so archives created on non-UTF-8 platforms (notably cp932 on Japanese
    Windows) land on disk under their original names instead of mojibake.

    Args:
        zip_path (Path | str): Path to the ZIP archive to extract.
        extract_path (Path | str): Directory to extract the archive into.

    Example:
        >>> extract_zip_with_encoding("archive.zip", "outdir")
    """
    base_dir = Path(extract_path).resolve()

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        for zip_info in zip_ref.infolist():
            resolved = resolve_filename(zip_info)
            destination = (base_dir / resolved).resolve()

            if destination != base_dir and base_dir not in destination.parents:
                logger.warning(
                    f"Skipping unsafe zip entry {resolved!r}: path resolves outside {str(base_dir)!r}",
                )
                continue

            if resolved != zip_info.filename:
                zip_info.filename = resolved

            zip_ref.extract(zip_info, base_dir)
