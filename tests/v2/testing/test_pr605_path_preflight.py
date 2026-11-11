"""PR605 review EP/BV: validate file roles and the inputdata boundary before writes.

EP table
| API / partition | Expected | Test ID |
|---|---|---|
| parent and descendant file names, both orders, list / generator | RdeConfigError 1003; no fixture tree created | R605-NEG-001 |
| normalized aliases or lexical parents used as file names | RdeConfigError 1003; no fixture tree created | R605-NEG-001 |
| an existing file needed as a parent directory | RdeConfigError 1003; existing tree unchanged | R605-NEG-002 |
| inputdata links to its root or an adjacent directory within the root | RdeConfigError 1003; content and mtimes unchanged | R605-NEG-003 |
| duplicate file names or equivalent spellings | retain request order and duplicates | R605-BV-001 |
| directory symlink contained within a real inputdata directory | allowed | R605-EP-001 |

BV table
| Boundary | Expected | Test ID |
|---|---|---|
| one ancestor and one descendant | reject in either order | R605-NEG-001 |
| zero requested files with an inputdata symlink | still reject the invalid boundary | R605-NEG-003 |
| exactly two occurrences of the same destination | both appear in rawfiles | R605-BV-001 |
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from pathlib import Path

import pytest

from rdetoolkit.errors import ERROR_CATALOG, RdeConfigError
from rdetoolkit.testing import make_input_paths


def _assert_invalid_path(error: RdeConfigError) -> None:
    assert error.code == 1003
    assert error.name == ERROR_CATALOG[1003].name == "InvalidTestInputPath"


@pytest.mark.parametrize("generator", [False, True], ids=["list", "generator"])
@pytest.mark.parametrize("names", [
    ["a", "a/b"],
    ["a/b", "a"],
    ["nested/../a", "a/b"],
    ["a/b", "nested/../a"],
    ["a", "a/../b"],
    ["a/../b", "a"],
])
def test_conflicting_file_roles_create_nothing__r605_neg_001(tmp_path: Path, names: list[str], generator: bool) -> None:
    """R605-NEG-001: all requested file/directory roles are checked before creation."""
    # Given: conflicting names under an input root that does not exist
    root = tmp_path / "data"
    files: Iterable[str] = (name for name in names) if generator else names
    before = tuple(tmp_path.iterdir())
    # When: requesting one file that another entry needs as a directory
    with pytest.raises(RdeConfigError) as raised:
        make_input_paths(root, files=files)
    # Then: the registered usage error leaves no partial directories or files
    _assert_invalid_path(raised.value)
    assert not root.exists()
    assert tuple(tmp_path.iterdir()) == before


@pytest.mark.parametrize("names", [["valid.txt", "a/b"], ["a/b", "valid.txt"]])
def test_existing_parent_file_is_rejected_before_writes__r605_neg_002(tmp_path: Path, names: list[str]) -> None:
    """R605-NEG-002: a pre-existing parent file cannot cause partial fixture creation."""
    # Given: a protected file where a requested input needs a directory
    root = tmp_path / "data"
    inputdata = root / "inputdata"
    inputdata.mkdir(parents=True)
    protected = inputdata / "a"
    protected.write_bytes(b"original")
    os.utime(protected, ns=(1_000_000_000, 1_000_000_000))
    before_root_mtime = root.stat().st_mtime_ns
    before_input_mtime = inputdata.stat().st_mtime_ns
    # When: building the conflicting batch
    with pytest.raises(RdeConfigError) as raised:
        make_input_paths(root, files=names)
    # Then: neither existing files nor directory structure or mtimes change
    _assert_invalid_path(raised.value)
    assert sorted(path.name for path in root.iterdir()) == ["inputdata"]
    assert sorted(path.name for path in inputdata.iterdir()) == ["a"]
    assert protected.read_bytes() == b"original"
    assert protected.stat().st_mtime_ns == 1_000_000_000
    assert root.stat().st_mtime_ns == before_root_mtime
    assert inputdata.stat().st_mtime_ns == before_input_mtime


@pytest.mark.skipif(sys.platform == "win32", reason="Creating symlinks requires Windows privileges.")
@pytest.mark.parametrize("target_kind", ["root", "sibling"])
@pytest.mark.parametrize("files", [["protected.txt"], []], ids=["one-file", "zero-files"])
def test_inputdata_symlink_never_redefines_boundary__r605_neg_003(tmp_path: Path, target_kind: str, files: list[str]) -> None:
    """R605-NEG-003: linking inputdata to another directory cannot authorize writes."""
    # Given: inputdata points at its root or a sibling containing a protected file
    root = tmp_path / "data"
    root.mkdir()
    target = root if target_kind == "root" else root / "sibling"
    target.mkdir(exist_ok=True)
    protected = target / "protected.txt"
    protected.write_bytes(b"original")
    os.utime(protected, ns=(1_000_000_000, 1_000_000_000))
    (root / "inputdata").symlink_to(target, target_is_directory=True)
    before_names = sorted(path.name for path in root.iterdir())
    before_root_mtime = root.stat().st_mtime_ns
    before_target_mtime = target.stat().st_mtime_ns
    # When: building through the substituted boundary, even with no requested files
    with pytest.raises(RdeConfigError) as raised:
        make_input_paths(root, files=files)
    # Then: the root, target, protected content and mtimes are all unchanged
    _assert_invalid_path(raised.value)
    assert sorted(path.name for path in root.iterdir()) == before_names
    assert protected.read_bytes() == b"original"
    assert protected.stat().st_mtime_ns == 1_000_000_000
    assert root.stat().st_mtime_ns == before_root_mtime
    assert target.stat().st_mtime_ns == before_target_mtime


@pytest.mark.parametrize("names", [["same.txt", "same.txt"], ["nested/../same.txt", "same.txt"]])
def test_duplicate_destinations_remain_allowed__r605_bv_001(tmp_path: Path, names: list[str]) -> None:
    """R605-BV-001: set validation does not discard or reject duplicate destinations."""
    # Given: two entries referring to the same file
    # When: building the requested fixture
    paths = make_input_paths(tmp_path, files=names)
    # Then: both occurrences remain visible in request order and name real files
    assert paths.rawfiles == tuple(paths.inputdata / name for name in names)
    assert len(paths.rawfiles) == 2
    assert paths.rawfiles[0].resolve() == paths.rawfiles[1].resolve()
    assert all(path.is_file() for path in paths.rawfiles)


@pytest.mark.skipif(sys.platform == "win32", reason="Creating symlinks requires Windows privileges.")
def test_contained_directory_symlink_remains_allowed__r605_ep_001(tmp_path: Path) -> None:
    """R605-EP-001: only replacing inputdata itself is rejected for an inward link."""
    # Given: a real inputdata directory containing a link to one of its directories
    root = tmp_path / "data"
    inputdata = root / "inputdata"
    actual = inputdata / "actual"
    actual.mkdir(parents=True)
    (inputdata / "alias").symlink_to(actual, target_is_directory=True)
    # When: creating a file through that contained directory link
    paths = make_input_paths(root, files=["alias/sample.txt"])
    # Then: the path spelling is retained and the file stays within inputdata
    assert paths.rawfiles == (inputdata / "alias/sample.txt",)
    assert (actual / "sample.txt").is_file()
