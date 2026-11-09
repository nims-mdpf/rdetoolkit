"""GA576 ZIP EP/BV: extraction exposes exactly the safe files it writes."""

from pathlib import Path
import zipfile

import pytest

from rdetoolkit.nodes import unzip_inputs


@pytest.mark.parametrize("members", [[], [("nested/", "")], [("nested/", ""), ("nested/測定.txt", "one"), ("b.txt", "two")], [("same.txt", "one"), ("same.txt", "two")]])
def test_unzip_returns_extracted_files__ga576_zip_ep_1_bv_1(tmp_path: Path, members: list[tuple[str, str]]) -> None:
    """GA576-ZIP-EP-1/BV-1: files are returned in member order with duplicates retained."""
    # Given: an archive that may be empty, directory-only, nested or duplicated
    source = tmp_path / "input.zip"
    with zipfile.ZipFile(source, "w") as archive:
        for name, content in members:
            archive.writestr(name, content)
    destination = tmp_path / "extracted"
    # When: invoking the public built-in directly
    paths = unzip_inputs(source, destination)
    # Then: safe file paths are useful to the caller and point at extracted data
    assert paths == [(destination / name).resolve() for name, _ in members if not name.endswith("/")]
    assert all(path.is_file() for path in paths)


@pytest.mark.parametrize("unsafe", ["../outside.txt", "/outside.txt", "linked/outside.txt"])
def test_unzip_never_returns_unsafe_members__ga576_zip_neg_1(tmp_path: Path, unsafe: str) -> None:
    """GA576-ZIP-NEG-1: unsafe members cannot escape containment through returned paths."""
    # Given: an outward directory symlink and an archive with a safe sibling
    destination = tmp_path / "extracted"
    destination.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (destination / "linked").symlink_to(outside, target_is_directory=True)
    source = tmp_path / "input.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(unsafe, "unsafe")
        archive.writestr("safe.txt", "safe")
    # When: extracting with the existing traversal and symlink protection
    paths = unzip_inputs(source, destination)
    # Then: the return value contains only the file actually accepted
    assert paths == [destination / "safe.txt"]
    assert list(outside.iterdir()) == []
    assert not (tmp_path / "outside.txt").exists()


@pytest.mark.parametrize("missing", [True, False])
def test_unzip_preserves_read_errors__ga576_zip_neg_2(tmp_path: Path, missing: bool) -> None:
    """GA576-ZIP-NEG-2: direct calls retain the original read exception type."""
    # Given: an absent or corrupt ZIP
    source = tmp_path / "bad.zip"
    if not missing:
        source.write_text("not a zip", encoding="utf-8")
    # When / Then: the plain node preserves the underlying file error
    with pytest.raises(FileNotFoundError if missing else zipfile.BadZipFile):
        unzip_inputs(source, tmp_path / "output")


def test_flow_consumes_extracted_paths__ga576_zip_ep_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA576-ZIP-EP-1: a strict public flow can consume the built-in return value."""
    from rdetoolkit import flow, workflows
    from rdetoolkit.nodes import read_text, save_text
    from rdetoolkit.types import InputPaths, OutputContext
    from tests.v2.runner.test_event_log_robustness_k4 import _build_tree

    # Given: a real dataset with one ZIP input
    _build_tree(tmp_path / "data")
    (tmp_path / "data/inputdata/file_0.txt").unlink()
    with zipfile.ZipFile(tmp_path / "data/inputdata/input.zip", "w") as archive:
        archive.writestr("measurement.txt", "measured")
    monkeypatch.chdir(tmp_path)

    @flow
    def pipeline(paths: InputPaths, out: OutputContext) -> None:
        extracted = unzip_inputs(paths.rawfiles[0], out.struct / "unpacked")
        save_text(read_text(extracted[0]), out, "measurement.txt")

    # When: recording and type-checking the public built-in calls
    report = workflows.run(flow=pipeline, config={"execution": {"type_check": "strict"}})
    # Then: the returned path produces a measured v2 artifact
    assert report.status == "success", report.error
    assert (tmp_path / "data/structured/measurement.txt").read_text() == "measured"
