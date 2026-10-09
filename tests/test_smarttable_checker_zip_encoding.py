"""Regression tests for issue #515: mojibake in SmartTable zip extraction.

``SmartTableChecker._unpacked_smarttable()`` (src/rdetoolkit/impl/input_controller.py)
delegates to ``shutil.unpack_archive()``, which in turn uses ``zipfile`` without any
encoding awareness. ``zipfile`` decodes a filename as cp437 whenever the UTF-8
language-encoding flag (general purpose bit 11, ``0x800``) is absent on the entry.
Zips produced by legacy Windows tools in a Japanese locale store filenames as cp932
(Shift_JIS) *without* setting that flag, so ``zipfile``'s cp437 decoding turns them
into mojibake (e.g. ``'2θ_θ.TXT'.encode('cp932').decode('cp437')`` ->
``'2â╞_â╞.TXT'``).

These tests fix the *observable* behavior (extracted filenames must match the
original text) as a regression harness, independent of whichever fix strategy
Task 03 selects (hardcoded cp932, ``charset_normalizer`` detection, or
``metadata_encoding``).

Fixture construction:
    ``zipfile.ZipInfo``/``zipfile.ZipFile.write()`` cannot be used to build the
    cp932-without-flag fixture: CPython's ``ZipInfo._encodeFilenameFlags()``
    unconditionally forces UTF-8 encoding + the ``0x800`` flag for any filename
    that is not pure ASCII, even if ``flag_bits`` is cleared beforehand (verified
    manually; see task log). Therefore this module builds STORED-method ZIP
    archives directly at the byte level via ``_build_raw_zip``/``_write_raw_zip``,
    which gives full control over the general-purpose flag bits and the raw
    filename bytes per entry. No binary fixtures are committed to the repository.

Equivalence Partitioning:
| API | Input/State Partition | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| ``_unpacked_smarttable`` | cp932-encoded filename, UTF-8 flag unset | legacy Windows zip (bug repro) | extracted filename matches original Japanese text | TC-EP-ZIPENC-001 |
| ``_unpacked_smarttable`` | UTF-8-encoded filename, UTF-8 flag set | modern zip tools / Python zipfile default | extracted filename unchanged (no regression) | TC-EP-ZIPENC-002 |
| ``_unpacked_smarttable`` | ASCII-only filename | common case | extracted filename unchanged | TC-EP-ZIPENC-003 |
| ``_unpacked_smarttable`` | zip mixing a UTF-8-flagged entry and a cp932-unflagged entry | real-world archives may mix tools | both filenames correctly resolved | TC-EP-ZIPENC-004 |
| ``_unpacked`` | explicit target differs from configured temp directory | caller-provided extraction contract | extracts, cleans, and lists files from target | TC-EP-ZIPENC-007 |

Validation commands:
Direct: ``uv run pytest tests/test_smarttable_checker_zip_encoding.py -v``
Tox: ``tox -e py312-module -- tests/test_smarttable_checker_zip_encoding.py``
"""

from __future__ import annotations

import io
import struct
import zipfile
import zlib
from pathlib import Path

import pytest

from rdetoolkit.impl.input_controller import MultiFileChecker, RDEFormatChecker, SmartTableChecker


def _build_raw_zip(entries: list[tuple[bytes, bytes, bool]]) -> bytes:
    """Build a minimal STORED-method ZIP archive with full per-entry control.

    Controls the general-purpose flag bits and raw filename bytes per entry.
    This bypasses ``zipfile.ZipInfo._encodeFilenameFlags()``, which always
    forces UTF-8 + the language-encoding flag (bit 11 / ``0x800``) for any
    filename that cannot be encoded as ASCII. That behavior makes it
    impossible to reproduce a "cp932 bytes without the UTF-8 flag" ZIP (as
    produced by legacy Windows zip tools) via the public ``zipfile`` API.

    Only the STORED (uncompressed) method is supported, which is sufficient
    for test fixtures; ``zipfile`` reads STORED entries without issue.

    Args:
        entries: List of ``(raw_filename_bytes, file_data_bytes,
            use_utf8_flag)`` triples. ``use_utf8_flag`` controls whether the
            UTF-8 language-encoding flag (bit 11) is set for that specific
            entry, allowing a single archive to mix flagged and unflagged
            entries.

    Returns:
        bytes: The complete ZIP archive contents.
    """
    buf = io.BytesIO()
    offsets: list[int] = []
    flags: list[int] = []

    for filename_bytes, data, use_utf8_flag in entries:
        flag = 0x0800 if use_utf8_flag else 0x0000
        flags.append(flag)
        offsets.append(buf.tell())
        crc = zlib.crc32(data) & 0xFFFFFFFF
        size = len(data)
        buf.write(struct.pack(
            "<IHHHHHIIIHH",
            0x04034B50, 20, flag, 0, 0, 0,
            crc, size, size, len(filename_bytes), 0,
        ))
        buf.write(filename_bytes)
        buf.write(data)

    central_start = buf.tell()
    for (filename_bytes, data, _use_utf8_flag), offset, flag in zip(entries, offsets, flags, strict=True):
        crc = zlib.crc32(data) & 0xFFFFFFFF
        size = len(data)
        buf.write(struct.pack(
            "<IHHHHHHIIIHHHHHII",
            0x02014B50, 20, 20, flag, 0, 0, 0,
            crc, size, size, len(filename_bytes), 0, 0, 0, 0, 0,
            offset,
        ))
        buf.write(filename_bytes)
    central_size = buf.tell() - central_start

    buf.write(struct.pack(
        "<IHHHHIIH",
        0x06054B50, 0, 0, len(entries), len(entries),
        central_size, central_start, 0,
    ))
    return buf.getvalue()


def _write_raw_zip(path: Path, entries: list[tuple[str, bytes, str, bool]]) -> None:
    """Write a raw ZIP file where each filename is encoded per-entry.

    Args:
        path: Destination ``.zip`` path.
        entries: List of ``(filename, file_content_bytes, encoding,
            use_utf8_flag)`` tuples. ``encoding`` is the codec used to turn
            ``filename`` into the raw bytes stored in the ZIP (e.g.
            ``"cp932"``, ``"utf-8"``, ``"ascii"``); ``use_utf8_flag``
            controls whether that entry's general-purpose flag advertises
            UTF-8.
    """
    raw_entries = [
        (name.encode(encoding), data, use_utf8_flag)
        for name, data, encoding, use_utf8_flag in entries
    ]
    path.write_bytes(_build_raw_zip(raw_entries))


def test_build_raw_zip_fixture_has_no_utf8_flag_and_raw_cp932_bytes(tmp_path: Path) -> None:
    """Given/When/Then: guard the fixture helper itself.

    Given a cp932-encoded filename written via ``_write_raw_zip`` with
    ``use_utf8_flag=False``.
    When the resulting archive is inspected with ``zipfile.ZipInfo``.
    Then the stored general-purpose flag must NOT have bit 11 (``0x800``)
    set, and re-encoding the (cp437-mis-decoded) stored name as cp437 must
    round-trip back to the original cp932 bytes. This proves the fixture
    genuinely reproduces a flag-less legacy-Windows zip rather than silently
    being UTF-8-flagged (which would make the reproduction test pass
    vacuously).
    """
    name = "NB1_800_20220214_2θ_θ.TXT"
    zip_path = tmp_path / "guard.zip"

    _write_raw_zip(zip_path, [(name, b"dummy", "cp932", False)])

    with zipfile.ZipFile(zip_path) as zf:
        info = zf.infolist()[0]
        # The UTF-8 language-encoding flag (bit 11) must be unset.
        assert info.flag_bits & 0x800 == 0
        # zipfile decoded the raw bytes as cp437 (its default for unflagged
        # entries); re-encoding as cp437 must recover the original cp932 bytes.
        assert info.filename.encode("cp437") == name.encode("cp932")


class TestSmartTableCheckerZipEncoding:
    """Regression tests for issue #515: mojibake in SmartTable zip extraction."""

    def test_cp932_filename_without_utf8_flag_is_decoded_correctly(self, tmp_path: Path) -> None:
        """TC-EP-ZIPENC-001: cp932 filename without the UTF-8 flag (bug repro)."""
        # Given: a zip whose filename is cp932-encoded without the UTF-8 flag,
        # reproducing an exact filename reported in issue #515.
        zip_path = tmp_path / "inputdata_hoge.zip"
        _write_raw_zip(
            zip_path,
            [("NB1_800_20220214_2θ_θ.TXT", b"dummy", "cp932", False)],
        )
        out_dir = tmp_path / "temp"
        out_dir.mkdir()
        checker = SmartTableChecker(out_dir)

        # When: extracting via the same code path SmartTable mode uses.
        extracted = checker._unpacked_smarttable(zip_path)

        # Then: the extracted filename must match the original text, not mojibake.
        names = [f.name for f in extracted]
        assert "NB1_800_20220214_2θ_θ.TXT" in names
        assert "NB1_800_20220214_2â╞_â╞.TXT" not in names  # the observed mojibake

    def test_utf8_flagged_filename_still_works(self, tmp_path: Path) -> None:
        """TC-EP-ZIPENC-002: UTF-8-flagged filename must not regress."""
        # Given: a zip written the "normal" way (Python zipfile auto-sets
        # the UTF-8 flag for non-ASCII names) — must not regress.
        zip_path = tmp_path / "utf8.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("日本語ファイル.txt", "dummy")
        out_dir = tmp_path / "temp"
        out_dir.mkdir()
        checker = SmartTableChecker(out_dir)

        # When: extracting via the same code path SmartTable mode uses.
        extracted = checker._unpacked_smarttable(zip_path)

        # Then: the extracted filename is unchanged.
        assert "日本語ファイル.txt" in [f.name for f in extracted]

    def test_ascii_filename_unaffected(self, tmp_path: Path) -> None:
        """TC-EP-ZIPENC-003: pure-ASCII filenames are unaffected either way."""
        # Given: an ASCII-only filename, unflagged (as real unflagged zips are).
        zip_path = tmp_path / "ascii.zip"
        _write_raw_zip(zip_path, [("data.txt", b"dummy", "ascii", False)])
        out_dir = tmp_path / "temp"
        out_dir.mkdir()
        checker = SmartTableChecker(out_dir)

        # When: extracting via the same code path SmartTable mode uses.
        extracted = checker._unpacked_smarttable(zip_path)

        # Then: the extracted filename is unchanged.
        assert "data.txt" in [f.name for f in extracted]

    def test_mixed_flagged_and_unflagged_entries_in_same_zip(self, tmp_path: Path) -> None:
        """TC-EP-ZIPENC-004: a single archive mixing both encodings.

        Real-world archives can be assembled from files added by different
        tools/eras, so one entry may carry the UTF-8 flag while another
        (e.g. added by a legacy Windows zip tool) does not. Both filenames
        must resolve correctly from the same extraction call, using the
        second reported issue #515 filename for the unflagged entry.
        """
        # Given: one entry written the "normal" (UTF-8 flagged) way and one
        # entry that is cp932-encoded without the flag, combined into a
        # single archive.
        zip_path = tmp_path / "mixed.zip"
        _write_raw_zip(
            zip_path,
            [
                ("日本語ファイル.txt", b"dummy", "utf-8", True),
                ("20211014T5高圧_2θ_θ.TXT", b"dummy", "cp932", False),
            ],
        )
        out_dir = tmp_path / "temp"
        out_dir.mkdir()
        checker = SmartTableChecker(out_dir)

        # When: extracting via the same code path SmartTable mode uses.
        extracted = checker._unpacked_smarttable(zip_path)

        # Then: both filenames are correctly resolved.
        names = [f.name for f in extracted]
        assert "日本語ファイル.txt" in names
        assert "20211014T5高圧_2θ_θ.TXT" in names


@pytest.mark.parametrize("checker_cls", [RDEFormatChecker, MultiFileChecker])
class TestOtherCheckersZipEncoding:
    """Issue #515 sibling defects: the same mojibake in RDEFormat/MultiFile modes.

    ``RDEFormatChecker._unpacked`` and ``MultiFileChecker._unpacked`` used the
    identical ``shutil.unpack_archive()`` pattern as the SmartTable defect that
    issue #515 reported, so the same legacy Windows zip garbles filenames in
    those modes too. These were fixed alongside the reported mode; these tests
    pin that down.
    """

    def test_cp932_filename_without_utf8_flag_is_decoded_correctly(
        self,
        checker_cls: type[RDEFormatChecker | MultiFileChecker],
        tmp_path: Path,
    ) -> None:
        """TC-EP-ZIPENC-005: cp932 filename without the UTF-8 flag."""
        # Given: a zip whose filename is cp932-encoded without the UTF-8 flag.
        zip_path = tmp_path / "inputdata_hoge.zip"
        _write_raw_zip(
            zip_path,
            [("NB1_800_20220214_2θ_θ.TXT", b"dummy", "cp932", False)],
        )
        out_dir = tmp_path / "temp"
        out_dir.mkdir()
        checker = checker_cls(out_dir)

        # When: extracting via the code path this mode uses.
        extracted = checker._unpacked(zip_path, out_dir)

        # Then: the extracted filename must match the original text, not mojibake.
        names = [f.name for f in extracted]
        assert "NB1_800_20220214_2θ_θ.TXT" in names
        assert "NB1_800_20220214_2â╞_â╞.TXT" not in names

    def test_utf8_flagged_filename_still_works(
        self,
        checker_cls: type[RDEFormatChecker | MultiFileChecker],
        tmp_path: Path,
    ) -> None:
        """TC-EP-ZIPENC-006: UTF-8-flagged filenames keep working."""
        # Given: a zip written the modern way (UTF-8 flag set).
        zip_path = tmp_path / "modern.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("日本語ファイル.txt", b"dummy")
        out_dir = tmp_path / "temp"
        out_dir.mkdir()
        checker = checker_cls(out_dir)

        # When: extracting via the code path this mode uses.
        extracted = checker._unpacked(zip_path, out_dir)

        # Then: the filename is unchanged.
        assert [f.name for f in extracted] == ["日本語ファイル.txt"]

    def test_explicit_target_directory_is_used__tc_ep_zipenc_007(
        self,
        checker_cls: type[RDEFormatChecker | MultiFileChecker],
        tmp_path: Path,
    ) -> None:
        """TC-EP-ZIPENC-007: extraction honors the caller-provided target."""
        # Given: a checker configured with a different directory from the target.
        zip_path = tmp_path / "input.zip"
        with zipfile.ZipFile(zip_path, "w") as zip_ref:
            zip_ref.writestr("data.txt", b"dummy")
        configured_dir = tmp_path / "configured"
        target_dir = tmp_path / "target"
        checker = checker_cls(configured_dir)

        # When: extracting to the explicit target directory.
        extracted = checker._unpacked(zip_path, target_dir)

        # Then: extraction and returned paths use the explicit target only.
        assert extracted == [target_dir / "data.txt"]
        assert not configured_dir.exists()
