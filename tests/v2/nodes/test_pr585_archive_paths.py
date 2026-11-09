"""PR585 ZIP regression: validate and return the actual extraction destination."""

import zipfile
import ntpath
from types import SimpleNamespace
from pathlib import Path

import pytest

from rdetoolkit.nodes import unzip_inputs
from rdetoolkit.nodes import io as io_nodes


@pytest.mark.parametrize("member", ["nested/../data.txt", "a/b/../../data.txt", "nested/./data.txt", "nested//data.txt"])
def test_returned_paths_match_archive_extraction__r585_zip_1(tmp_path: Path, member: str) -> None:
    """R585-ZIP-1: normalized member spellings cannot produce nonexistent paths."""
    # Given: a ZIP member whose logical path differs from zipfile's sanitization
    source = tmp_path / "input.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(member, "measured")
    destination = tmp_path / "output"
    # When: extracting through the public node
    extracted = unzip_inputs(source, destination)
    # Then: every reported path is the actual file on disk
    assert len(extracted) == 1
    assert extracted[0].is_file()
    assert extracted[0].read_text() == "measured"
    assert extracted == list(destination.rglob("data.txt"))


def test_sanitized_destination_cannot_escape_via_link__r585_zip_2(tmp_path: Path) -> None:
    """R585-ZIP-2: containment checks cover the path zipfile actually writes."""
    # Given: the sanitized member traverses a link absent from its resolved spelling
    destination = tmp_path / "output"
    (destination / "nested").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (destination / "nested/link").symlink_to(outside, target_is_directory=True)
    source = tmp_path / "input.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("nested/../link/data.txt", "unsafe")
    # When: sanitization removes the .. component instead of traversing it
    extracted = unzip_inputs(source, destination)
    # Then: no outward link is written or returned
    assert extracted == []
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("member", ["C:/nested:part./.././data.txt", "C:/nested:part. /.././data.txt"])
def test_windows_member_sanitization__r585_zip_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, member: str) -> None:
    """R585-ZIP-3: validation follows drive, separator and illegal-name handling."""
    # Given: Windows path semantics, including an illegal character and trailing dot
    monkeypatch.setattr(io_nodes, "os", SimpleNamespace(path=ntpath))
    # When: computing the destination that zipfile will sanitize before extraction
    destination = io_nodes._zip_destination(tmp_path, member)
    # Then: validation resolves exactly the sanitized member spelling
    assert destination == tmp_path / "nested_part" / "data.txt"
