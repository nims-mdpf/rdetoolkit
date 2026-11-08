"""Containment tests for ``unzip_inputs`` (Session RC1-INT-CLI, review item C01).

``unzip_inputs`` followed a symlink that already existed in the destination,
so a member named like that link overwrote a file outside ``dst_dir``. The
node now resolves each destination (symlinks included) and skips members that
land outside ``dst_dir`` with a logged warning -- the same policy as
``impl._zip_encoding.extract_zip_with_encoding`` -- while keeping its
cp437 -> cp932 member-name repair.

EP table:
    TC-RC1-C01-EP-001 | pre-existing outward file symlink, same-name member | skipped, outside unchanged, warning
    TC-RC1-C01-EP-002 | pre-existing outward directory symlink, member below it | skipped, nothing written outside, warning
    TC-RC1-C01-EP-003 | outward symlink beside a safe member | unsafe skipped, safe member still extracted
    TC-RC1-C01-EP-004 | plain ASCII member | extracted unchanged, no warning
    TC-RC1-C01-EP-005 | cp932 member name without the UTF-8 flag | extracted under the repaired name
    TC-RC1-C01-EP-006 | non-ASCII member name with the UTF-8 flag | extracted under its own name, not re-decoded

BV table:
    TC-RC1-C01-BV-001 | symlink in dst that resolves inside dst | not skipped (containment is by resolved target)
    TC-RC1-C01-BV-002 | member resolving exactly to a nested dir inside dst | extracted
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

import pytest

from rdetoolkit.nodes.io import unzip_inputs
from tests.v2.nodes.conftest import FIXTURES_DIR


def _zip(path: Path, members: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return path


def test_outward_file_symlink_member_is_skipped__tc_rc1_c01_ep_001(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """TC-RC1-C01-EP-001: a same-name member never writes through an outward file link."""
    # Given: a destination holding a link to a file outside it
    destination = tmp_path / "dst"
    destination.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("ORIGINAL", encoding="utf-8")
    (destination / "link.txt").symlink_to(outside)
    archive = _zip(tmp_path / "a.zip", {"link.txt": "REPLACED"})

    # When: the archive is extracted
    with caplog.at_level(logging.WARNING):
        unzip_inputs(archive, destination)

    # Then: the outside file is unchanged and the skip is logged
    assert outside.read_text(encoding="utf-8") == "ORIGINAL"
    assert "Skipping unsafe zip entry 'link.txt'" in caplog.text


def test_outward_directory_symlink_member_is_skipped__tc_rc1_c01_ep_002(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """TC-RC1-C01-EP-002: a member below an outward directory link is not written."""
    # Given: a destination holding a link to a directory outside it
    destination = tmp_path / "dst"
    destination.mkdir()
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    (destination / "linkdir").symlink_to(outside_dir, target_is_directory=True)
    archive = _zip(tmp_path / "a.zip", {"linkdir/planted.txt": "PLANTED"})

    # When: the archive is extracted
    with caplog.at_level(logging.WARNING):
        unzip_inputs(archive, destination)

    # Then: nothing is created outside and the skip is logged
    assert list(outside_dir.iterdir()) == []
    assert "Skipping unsafe zip entry 'linkdir/planted.txt'" in caplog.text


def test_unsafe_member_does_not_abort_safe_siblings__tc_rc1_c01_ep_003(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """TC-RC1-C01-EP-003: skipping one member keeps extracting the rest."""
    # Given: an outward link and an archive with an unsafe and a safe member
    destination = tmp_path / "dst"
    destination.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("ORIGINAL", encoding="utf-8")
    (destination / "link.txt").symlink_to(outside)
    archive = _zip(tmp_path / "a.zip", {"link.txt": "REPLACED", "safe.txt": "SAFE"})

    # When: the archive is extracted
    with caplog.at_level(logging.WARNING):
        unzip_inputs(archive, destination)

    # Then: only the unsafe member was skipped
    assert outside.read_text(encoding="utf-8") == "ORIGINAL"
    assert (destination / "safe.txt").read_text(encoding="utf-8") == "SAFE"
    assert caplog.text.count("Skipping unsafe zip entry") == 1


def test_plain_member_is_extracted_without_warning__tc_rc1_c01_ep_004(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """TC-RC1-C01-EP-004: an ordinary archive extracts as before."""
    # Given: an archive with an ordinary nested member and a fresh destination
    archive = _zip(tmp_path / "a.zip", {"sub/data.txt": "DATA"})
    destination = tmp_path / "fresh"

    # When: the archive is extracted
    with caplog.at_level(logging.WARNING):
        unzip_inputs(archive, destination)

    # Then: the member lands under the destination and no skip is logged
    assert (destination / "sub" / "data.txt").read_text(encoding="utf-8") == "DATA"
    assert "Skipping unsafe zip entry" not in caplog.text


def test_cp932_member_name_is_still_repaired__tc_rc1_c01_ep_005(tmp_path: Path) -> None:
    """TC-RC1-C01-EP-005: the cp437 -> cp932 member-name repair is kept."""
    # Given: the flag-less cp932 fixture archive
    destination = tmp_path / "sjis"

    # When: the archive is extracted
    unzip_inputs(FIXTURES_DIR / "sample_sjis.zip", destination)

    # Then: the Japanese name is restored, not left as cp437 mojibake
    names = {path.name for path in destination.rglob("*.txt")}
    assert "日本語ファイル.txt" in names, names


def test_utf8_flagged_member_name_is_kept__tc_rc1_c01_ep_006(tmp_path: Path) -> None:
    """TC-RC1-C01-EP-006: a member already flagged UTF-8 skips the cp932 repair and stays contained."""
    # Given: an archive whose non-ASCII member name zipfile stores with the UTF-8 flag
    archive = _zip(tmp_path / "a.zip", {"資料/データ.txt": "DATA"})
    with zipfile.ZipFile(archive) as opened:
        assert opened.infolist()[0].flag_bits & 0x800

    # When: the archive is extracted
    destination = tmp_path / "utf8"
    unzip_inputs(archive, destination)

    # Then: the member lands under its UTF-8 name inside the destination
    assert (destination / "資料" / "データ.txt").read_text(encoding="utf-8") == "DATA"


def test_inward_symlink_is_not_skipped__tc_rc1_c01_bv_001(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """TC-RC1-C01-BV-001: a link resolving inside dst is contained, so it is not skipped."""
    # Given: a destination link pointing at a file inside the destination
    destination = tmp_path / "dst"
    (destination / "real").mkdir(parents=True)
    inside = destination / "real" / "target.txt"
    inside.write_text("OLD", encoding="utf-8")
    (destination / "link.txt").symlink_to(inside)
    archive = _zip(tmp_path / "a.zip", {"link.txt": "NEW"})

    # When: the archive is extracted
    with caplog.at_level(logging.WARNING):
        unzip_inputs(archive, destination)

    # Then: the write stays inside the destination and nothing is skipped
    assert inside.read_text(encoding="utf-8") == "NEW"
    assert "Skipping unsafe zip entry" not in caplog.text


def test_directory_member_inside_destination_is_created__tc_rc1_c01_bv_002(tmp_path: Path) -> None:
    """TC-RC1-C01-BV-002: an explicit directory entry inside dst is still extracted."""
    # Given: an archive holding an explicit directory entry
    archive_path = tmp_path / "a.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(zipfile.ZipInfo("emptydir/"), b"")
    destination = tmp_path / "dst"

    # When: the archive is extracted
    unzip_inputs(archive_path, destination)

    # Then: the directory exists under the destination
    assert (destination / "emptydir").is_dir()
