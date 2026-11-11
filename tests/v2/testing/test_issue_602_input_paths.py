"""Issue 602: input builders expose requested files without writing outside inputdata.

EP table
| Partition | Expected | Test ID |
|---|---|---|
| file names as a list or one-shot generator | rawfiles preserves the requested order, excluding other files | I602-EP-001 |
| relative root | returned paths preserve the root's spelling | I602-EP-002 |
| absolute existing or missing file | RdeConfigError 1003; external file unchanged or absent | I602-NEG-001 |
| a valid name followed by an invalid name | RdeConfigError 1003 before any tree or file is created | I602-NEG-002 |
| outward file, directory or inputdata symlink | RdeConfigError 1003; external tree unchanged | I602-NEG-003 |
| existing directory used as a file | RdeConfigError 1003; directory remains intact | I602-NEG-004 |

BV table
| Boundary | Expected | Test ID |
|---|---|---|
| no requested files | rawfiles is empty, invoice_org retains the PR 594 default | I602-BV-001 |
| contained parent component | allowed; requested file appears in rawfiles | I602-BV-002 |
| explicit invoice_org plus one raw file | both fields are populated, invoice source is not touched | I602-BV-003 |
| empty name, dot, parent or traversal beyond inputdata | RdeConfigError 1003 before creating the tree | I602-NEG-005 |
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
def test_requested_files_are_rawfiles__i602_ep_001(tmp_path: Path, generator: bool) -> None:
    """I602-EP-001: only the requested files populate rawfiles in iterable order."""
    # Given: an existing unrequested file and two requested names in reverse order
    root = tmp_path / "data"
    existing = root / "inputdata" / "existing.txt"
    existing.parent.mkdir(parents=True)
    existing.write_text("keep", encoding="utf-8")
    names = ["z.txt", "nested/a.txt"]
    files: Iterable[str] = (name for name in names) if generator else names
    # When: creating the input bundle through the public helper
    paths = make_input_paths(root, files=files)
    # Then: rawfiles names the created files without scanning unrelated inputs
    assert paths.rawfiles == tuple(root / "inputdata" / name for name in names)
    assert all(path.is_file() and path.read_bytes() == b"" for path in paths.rawfiles)
    assert paths.invoice_org == root / "invoice" / "invoice.json"
    assert existing.read_text(encoding="utf-8") == "keep"


def test_relative_root_preserves_paths__i602_ep_002(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """I602-EP-002: rawfiles uses the same relative spelling as inputdata."""
    # Given: a root addressed relative to the caller's working directory
    monkeypatch.chdir(tmp_path)
    # When: building one input file
    paths = make_input_paths(Path("data"), files=["sample.txt"])
    # Then: both the input directory and the raw file remain relative
    assert paths.inputdata == Path("data/inputdata")
    assert paths.rawfiles == (Path("data/inputdata/sample.txt"),)
    assert paths.rawfiles[0].is_file()


def test_no_requested_files_keeps_defaults__i602_bv_001(tmp_path: Path) -> None:
    """I602-BV-001: an empty request does not infer rawfiles from existing inputs."""
    # Given: an existing input tree with a file not requested by the caller
    root = tmp_path / "data"
    existing = root / "inputdata" / "existing.txt"
    existing.parent.mkdir(parents=True)
    existing.touch()
    # When: requesting no files
    paths = make_input_paths(root)
    # Then: the empty boundary and PR 594 invoice default are preserved
    assert paths.rawfiles == ()
    assert paths.invoice_org == root / "invoice" / "invoice.json"
    assert not paths.invoice_org.exists()


def test_contained_parent_component_is_allowed__i602_bv_002(tmp_path: Path) -> None:
    """I602-BV-002: a parent component is valid when it stays inside inputdata."""
    # Given: a relative name whose normalized location remains inside inputdata
    name = "nested/../sample.txt"
    # When: creating that file
    paths = make_input_paths(tmp_path, files=[name])
    # Then: the file exists and retains the caller's relative spelling
    assert paths.rawfiles == (tmp_path / "inputdata" / name,)
    assert paths.rawfiles[0].is_file()


def test_explicit_invoice_source_is_preserved__i602_bv_003(tmp_path: Path) -> None:
    """I602-BV-003: filling rawfiles does not replace an explicit invoice_org."""
    # Given: a caller-selected run-level source that does not exist
    source = tmp_path / "backup" / "invoice.json"
    # When: creating a bundle with one raw file and that source
    paths = make_input_paths(tmp_path / "data", files=["sample.txt"], invoice_org=source)
    # Then: both fields are populated and the source file is not created
    assert paths.rawfiles == (tmp_path / "data" / "inputdata" / "sample.txt",)
    assert paths.invoice_org == source
    assert not source.exists()


@pytest.mark.parametrize("exists", [True, False], ids=["existing", "missing"])
def test_absolute_file_is_rejected_without_touching_it__i602_neg_001(tmp_path: Path, exists: bool) -> None:
    """I602-NEG-001: absolute input names cannot create or retimestamp external files."""
    # Given: an external absolute file with a stable modification time, or a missing one
    external = tmp_path / "external.txt"
    if exists:
        external.write_bytes(b"original")
        os.utime(external, ns=(1_000_000_000, 1_000_000_000))
    root = tmp_path / "data"
    # When: requesting an absolute path through files
    with pytest.raises(RdeConfigError) as raised:
        make_input_paths(root, files=[str(external)])
    # Then: the cataloged error leaves both the external path and input tree unchanged
    _assert_invalid_path(raised.value)
    assert not root.exists()
    assert external.exists() is exists
    if exists:
        assert external.read_bytes() == b"original"
        assert external.stat().st_mtime_ns == 1_000_000_000


def test_invalid_batch_creates_no_partial_tree__i602_neg_002(tmp_path: Path) -> None:
    """I602-NEG-002: validate a one-shot iterable before creating its first file."""
    # Given: a valid name followed by an absolute path in a generator
    root = tmp_path / "data"
    external = tmp_path / "external.txt"
    files = (name for name in ["valid.txt", str(external)])
    # When: building the invalid batch
    with pytest.raises(RdeConfigError) as raised:
        make_input_paths(root, files=files)
    # Then: rejection occurs before either the valid tree or external file is created
    _assert_invalid_path(raised.value)
    assert not root.exists()
    assert not external.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="Creating symlinks requires Windows privileges.")
@pytest.mark.parametrize("kind", ["file", "directory", "inputdata"])
def test_outward_symlinks_are_rejected__i602_neg_003(tmp_path: Path, kind: str) -> None:
    """I602-NEG-003: file and ancestor symlinks cannot redirect fixture writes."""
    # Given: an external file with a fixed mtime and a symlink from the input tree
    outside = tmp_path / "outside"
    outside.mkdir()
    external = outside / "existing.txt"
    external.write_bytes(b"original")
    os.utime(external, ns=(1_000_000_000, 1_000_000_000))
    root = tmp_path / "data"
    root.mkdir()
    inputdata = root / "inputdata"
    if kind == "inputdata":
        inputdata.symlink_to(outside, target_is_directory=True)
        filename = "new.txt"
    else:
        inputdata.mkdir()
        if kind == "file":
            (inputdata / "linked.txt").symlink_to(external)
            filename = "linked.txt"
        else:
            (inputdata / "linked").symlink_to(outside, target_is_directory=True)
            filename = "linked/new.txt"
    # When: a requested file resolves through that outward symlink
    with pytest.raises(RdeConfigError) as raised:
        make_input_paths(root, files=[filename])
    # Then: the cataloged error preserves the external tree and mtime
    _assert_invalid_path(raised.value)
    assert sorted(path.name for path in outside.iterdir()) == ["existing.txt"]
    assert external.read_bytes() == b"original"
    assert external.stat().st_mtime_ns == 1_000_000_000


def test_existing_directory_is_not_a_file__i602_neg_004(tmp_path: Path) -> None:
    """I602-NEG-004: directory entries fail with the same public error contract."""
    # Given: an existing directory under inputdata
    directory = tmp_path / "inputdata" / "directory"
    directory.mkdir(parents=True)
    # When: requesting that directory as a file
    with pytest.raises(RdeConfigError) as raised:
        make_input_paths(tmp_path, files=["directory"])
    # Then: it remains a directory and the error carries its registered integer code
    _assert_invalid_path(raised.value)
    assert directory.is_dir()


@pytest.mark.parametrize("name", ["", ".", "..", "../outside.txt", "nested/../../outside.txt", "../../outside.txt"])
def test_invalid_relative_names_create_nothing__i602_neg_005(tmp_path: Path, name: str) -> None:
    """I602-NEG-005: root, empty and escaping names never become file writes."""
    # Given: an input root that does not exist and an invalid relative name
    root = tmp_path / "data"
    # When: creating the invalid fixture
    with pytest.raises(RdeConfigError) as raised:
        make_input_paths(root, files=[name])
    # Then: the registered error is raised before creating the tree
    _assert_invalid_path(raised.value)
    assert not root.exists()
