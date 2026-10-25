"""K4-F4: archive extraction order is independent of the filesystem's listing order.

The v1 archive parsers returned the extracted files in directory-listing order
(``Path.glob`` / ``os.walk``). That order differs between filesystems — the
GitHub runner image moving from ubuntu-24.04 to ubuntu-26.04 flipped it — and
in ExcelInvoice mode the tile's first raw file is what ``${filename}`` expands
to, so the same input produced a different invoice on a different machine
(frozen oracle ``v1/excelinvoice/structfail`` vs. CI). The parsers now sort.

| ID | Kind | Scenario | Expected |
|----|------|----------|----------|
| TC-K4F4-EP-001 | EP | flat archive, listings reversed | files sorted by path |
| TC-K4F4-EP-002 | EP | folder archive, listings reversed | dirs and files sorted by path |
| TC-K4F4-EP-003 | EP | ExcelInvoice checker, listings reversed | tile 1 raw files start with test_child1.txt |
"""

from __future__ import annotations

import os
import pathlib
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from rdetoolkit.impl import compressed_controller
from rdetoolkit.impl.input_controller import ExcelInvoiceChecker
from tests.v2.contract.fixtures import _generate


class _ReversedListing:
    """Context that reverses every directory listing the parsers may use."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mp = monkeypatch

    def __enter__(self) -> _ReversedListing:
        orig_glob, orig_scandir = pathlib.Path.glob, os.scandir

        def reversed_glob(self: Path, *args: Any, **kwargs: Any) -> Any:
            return iter(list(orig_glob(self, *args, **kwargs))[::-1])

        class ReversedScandir:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                with orig_scandir(*args, **kwargs) as it:
                    self._items = list(it)[::-1]

            def __enter__(self) -> ReversedScandir:
                return self

            def __exit__(self, *exc: object) -> None:
                return None

            def __iter__(self) -> ReversedScandir:
                return self

            def __next__(self) -> Any:
                if not self._items:
                    raise StopIteration
                return self._items.pop(0)

            def close(self) -> None:
                return None

        self._mp.setattr(pathlib.Path, "glob", reversed_glob)
        self._mp.setattr(os, "scandir", ReversedScandir)
        return self

    def __exit__(self, *exc: object) -> None:
        self._mp.undo()


def _zip(path: Path, members: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, body in members.items():
            archive.writestr(name, body)


def _names(groups: list[tuple[Path, ...]], root: Path) -> list[list[str]]:
    return [[p.relative_to(root).as_posix() for p in group] for group in groups]


def test_flat_archive_order_is_sorted_under_reversed_listing__tc_k4f4_ep_001(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K4F4-EP-001: the flat parser returns the sheet's files sorted by path."""
    # Given: a flat archive and a sheet naming its files
    archive = tmp_path / "files.zip"
    _zip(archive, {"b.txt": "b", "a.txt": "a", "c.txt": "c"})
    sheet = pd.DataFrame({"data_file_names/name": ["c.txt", "a.txt", "b.txt"]})
    parser = compressed_controller.CompressedFlatFileParser(sheet)

    # When: reading with every listing reversed
    with _ReversedListing(monkeypatch):
        groups = parser.read(archive, tmp_path / "out")

    # Then: the order follows the sheet, and the unpacked listing itself was sorted
    assert _names(groups, tmp_path / "out") == [["c.txt"], ["a.txt"], ["b.txt"]]
    with _ReversedListing(monkeypatch):
        unpacked = parser._unpacked(archive, tmp_path / "out2")  # noqa: SLF001
    assert [p.name for p in unpacked] == ["a.txt", "b.txt", "c.txt"]


def test_folder_archive_order_is_sorted_under_reversed_listing__tc_k4f4_ep_002(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K4F4-EP-002: folder groups and their files come back sorted by path."""
    # Given: a folder archive with two directories and unsorted members
    archive = tmp_path / "folders.zip"
    _zip(archive, {"two/z.txt": "z", "two/y.txt": "y", "one/b.txt": "b", "one/a.txt": "a"})
    parser = compressed_controller.CompressedFolderParser(pd.DataFrame({"basic/dataName": ["one", "two"]}))

    # When: reading with every listing reversed
    with _ReversedListing(monkeypatch):
        groups = parser.read(archive, tmp_path / "out")

    # Then: directories and the files inside each are sorted
    assert _names(groups, tmp_path / "out") == [["one/a.txt", "one/b.txt"], ["two/y.txt", "two/z.txt"]]


def test_excelinvoice_first_raw_file_is_stable__tc_k4f4_ep_003(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-K4F4-EP-003: the frozen structfail input yields the same first raw file on any listing order.

    This is the CI failure: ``${filename}`` of the first tile became
    ``test_child2.txt`` on ubuntu-26.04 while the frozen v1 oracle (and
    ubuntu-24.04) had ``test_child1.txt``.
    """
    # Given: the registered ExcelInvoice structfail input
    _generate.materialize_case(_generate.oracle_case("v1/excelinvoice/structfail"), tmp_path)
    checker = ExcelInvoiceChecker(tmp_path / "data" / "temp")

    # When: parsing with every listing reversed
    with _ReversedListing(monkeypatch):
        rawfiles, _ = checker.parse(tmp_path / "data" / "inputdata")

    # Then: every tile's first raw file is the sorted first member
    assert [group[0].name for group in rawfiles] == ["test_child1.txt", "test_child1.txt"]
