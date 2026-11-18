"""Issue 623: remove or replace the Runner's raw / nonshared_raw copy of an input.

EP table
========

================  ====================================  =====================================  =============
API               Partition                             Expected                               Test ID
================  ====================================  =====================================  =============
remove_raw_copy   both kinds enabled                    both copies removed, paths returned    I623-EP-001
remove_raw_copy   one kind enabled                      only that kind touched                 I623-EP-002
remove_raw_copy   directory copy                        removed with its contents              I623-EP-003
replace_raw_copy  archive members, both kinds           members copied, archive removed        I623-EP-004
replace_raw_copy  member named like the copy            copy replaced in place                 I623-EP-005
replace_raw_copy  directory member                      tree copied                            I623-EP-006
replace_raw_copy  same path given twice                 copied once                            I623-EP-007
Runner run        flow replaces an uploaded zip         raw/ and nonshared_raw/ hold members   I623-EP-008
Runner run        flow removes an input                 copy gone, node in call log            I623-EP-009
================  ====================================  =====================================  =============

BV / negative table
===================

================  ====================================  =====================================  =============
API               Boundary                              Expected                               Test ID
================  ====================================  =====================================  =============
both              both kinds disabled                   no-op, empty list                      I623-BV-001
both              nested / traversal filename           ValueError, nothing changed            I623-NEG-001
both              enabled kind has no copy              FileNotFoundError, nothing changed     I623-NEG-002
replace_raw_copy  member missing                        FileNotFoundError, nothing changed     I623-NEG-003
replace_raw_copy  two members share a name              ValueError, nothing changed            I623-NEG-004
replace_raw_copy  member collides with another input    FileExistsError, nothing changed       I623-NEG-005
================  ====================================  =====================================  =============
"""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path

import pytest

from rdetoolkit import flow, workflows
from rdetoolkit.nodes import remove_raw_copy, replace_raw_copy, unzip_inputs
from rdetoolkit.types import InputPaths, OutputContext, RdeConfig

BOTH = RdeConfig.model_validate({"system": {"save_raw": True, "save_nonshared_raw": True}})
RAW_ONLY = RdeConfig.model_validate({"system": {"save_raw": True, "save_nonshared_raw": False}})
NONSHARED_ONLY = RdeConfig.model_validate({"system": {"save_raw": False, "save_nonshared_raw": True}})
NEITHER = RdeConfig.model_validate({"system": {"save_raw": False, "save_nonshared_raw": False}})


def _seed(out: OutputContext, name: str, content: bytes = b"copy") -> None:
    for directory in (out.raw, out.nonshared_raw):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_bytes(content)


def _tree(out: OutputContext) -> dict[str, list[str]]:
    return {
        kind: sorted(p.relative_to(directory).as_posix() for p in directory.rglob("*"))
        for kind, directory in (("raw", out.raw), ("nonshared_raw", out.nonshared_raw))
    }


def _members(tmp_path: Path, *names: str) -> list[Path]:
    source = tmp_path / "members"
    source.mkdir(exist_ok=True)
    paths = []
    for name in names:
        path = source / name
        path.write_text(name, encoding="utf-8")
        paths.append(path)
    return paths


class TestRemoveRawCopy:
    def test_both_kinds_removed__i623_ep_001(self, output_context: OutputContext) -> None:
        """I623-EP-001: both enabled copies are removed and returned raw first."""
        # Given: the Runner's copies in both kinds
        _seed(output_context, "sample_meta.json")
        _seed(output_context, "keep.txt")
        # When: removing one of them
        removed = remove_raw_copy(output_context, BOTH, "sample_meta.json")
        # Then: only that input is gone, in both kinds
        assert removed == [output_context.raw / "sample_meta.json", output_context.nonshared_raw / "sample_meta.json"]
        assert _tree(output_context) == {"raw": ["keep.txt"], "nonshared_raw": ["keep.txt"]}

    @pytest.mark.parametrize(("config", "kept"), [(RAW_ONLY, "nonshared_raw"), (NONSHARED_ONLY, "raw")])
    def test_disabled_kind_untouched__i623_ep_002(self, output_context: OutputContext, config: RdeConfig, kept: str) -> None:
        """I623-EP-002: a disabled kind keeps whatever it holds."""
        # Given: files in both directories, one kind disabled
        _seed(output_context, "a.json")
        # When: removing the copy
        removed = remove_raw_copy(output_context, config, "a.json")
        # Then: only the enabled kind lost it
        assert len(removed) == 1
        assert _tree(output_context)[kept] == ["a.json"]
        assert not removed[0].exists()

    def test_directory_copy_removed__i623_ep_003(self, output_context: OutputContext) -> None:
        """I623-EP-003: a directory input copied by the Runner is removed with its contents."""
        # Given: a copied directory in the raw directory
        (output_context.raw / "scan" / "sub").mkdir(parents=True)
        (output_context.raw / "scan" / "sub" / "x.txt").write_text("x", encoding="utf-8")
        # When: removing it
        remove_raw_copy(output_context, RAW_ONLY, "scan")
        # Then: nothing of it is left
        assert not (output_context.raw / "scan").exists()


class TestReplaceRawCopy:
    def test_archive_replaced_by_members__i623_ep_004(self, output_context: OutputContext, tmp_path: Path) -> None:
        """I623-EP-004: the archive copy becomes its extracted members in both kinds."""
        # Given: an uploaded archive copied by the Runner and its extracted members
        archive = tmp_path / "upload.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("image.tif", b"tif")
            zf.writestr("nested/data.txt", b"txt")
        _seed(output_context, "upload.zip", archive.read_bytes())
        members = unzip_inputs(archive, tmp_path / "extracted")
        # When: replacing the archive copy
        copied = replace_raw_copy(output_context, BOTH, "upload.zip", members)
        # Then: the members are stored by name and the archive is gone
        assert copied == [
            output_context.raw / "image.tif",
            output_context.raw / "data.txt",
            output_context.nonshared_raw / "image.tif",
            output_context.nonshared_raw / "data.txt",
        ]
        assert _tree(output_context) == {"raw": ["data.txt", "image.tif"], "nonshared_raw": ["data.txt", "image.tif"]}
        assert (output_context.nonshared_raw / "data.txt").read_bytes() == b"txt"

    def test_member_with_same_name_replaces_in_place__i623_ep_005(self, output_context: OutputContext, tmp_path: Path) -> None:
        """I623-EP-005: a member named like the copy overwrites it instead of being removed."""
        # Given: a copy and a corrected file with the same name
        _seed(output_context, "data.csv", b"old")
        (fixed,) = _members(tmp_path, "data.csv")
        # When: replacing the copy with it
        copied = replace_raw_copy(output_context, BOTH, "data.csv", [fixed])
        # Then: the copy holds the new content
        assert copied == [output_context.raw / "data.csv", output_context.nonshared_raw / "data.csv"]
        assert (output_context.raw / "data.csv").read_text(encoding="utf-8") == "data.csv"
        assert (output_context.nonshared_raw / "data.csv").read_text(encoding="utf-8") == "data.csv"

    def test_directory_member_copied_as_tree__i623_ep_006(self, output_context: OutputContext, tmp_path: Path) -> None:
        """I623-EP-006: a directory member keeps its tree."""
        # Given: an extracted directory
        _seed(output_context, "upload.zip")
        tree = tmp_path / "scan"
        (tree / "sub").mkdir(parents=True)
        (tree / "sub" / "x.txt").write_text("x", encoding="utf-8")
        # When: replacing the archive with the directory
        replace_raw_copy(output_context, NONSHARED_ONLY, "upload.zip", [tree])
        # Then: the tree is stored under the member name
        assert _tree(output_context)["nonshared_raw"] == ["scan", "scan/sub", "scan/sub/x.txt"]

    def test_repeated_member_copied_once__i623_ep_007(self, output_context: OutputContext, tmp_path: Path) -> None:
        """I623-EP-007: unzip_inputs' repeated members do not fail as a name clash."""
        # Given: the same member path listed twice
        _seed(output_context, "upload.zip")
        (member,) = _members(tmp_path, "a.txt")
        # When: replacing with the repeated list
        copied = replace_raw_copy(output_context, RAW_ONLY, "upload.zip", [member, member])
        # Then: one copy per kind
        assert copied == [output_context.raw / "a.txt"]


class TestBoundariesAndErrors:
    def test_both_disabled_is_noop__i623_bv_001(self, output_context: OutputContext, tmp_path: Path) -> None:
        """I623-BV-001: with both kinds disabled nothing is checked or changed."""
        # Given: no raw copies at all
        (member,) = _members(tmp_path, "a.txt")
        # When / Then: both nodes return an empty list
        assert remove_raw_copy(output_context, NEITHER, "absent.zip") == []
        assert replace_raw_copy(output_context, NEITHER, "absent.zip", [member]) == []
        assert _tree(output_context) == {"raw": [], "nonshared_raw": []}

    @pytest.mark.parametrize("filename", ["../a.zip", "sub/a.zip", "..", ""])
    def test_unsafe_filename_rejected__i623_neg_001(self, output_context: OutputContext, tmp_path: Path, filename: str) -> None:
        """I623-NEG-001: only simple filenames inside the raw directories are accepted."""
        # Given: a copy that must survive
        _seed(output_context, "a.zip")
        (member,) = _members(tmp_path, "m.txt")
        # When / Then: both nodes reject the name and change nothing
        with pytest.raises(ValueError, match="simple basename"):
            remove_raw_copy(output_context, BOTH, filename)
        with pytest.raises(ValueError, match="simple basename"):
            replace_raw_copy(output_context, BOTH, filename, [member])
        assert _tree(output_context) == {"raw": ["a.zip"], "nonshared_raw": ["a.zip"]}

    def test_missing_copy_in_enabled_kind__i623_neg_002(self, output_context: OutputContext, tmp_path: Path) -> None:
        """I623-NEG-002: a misspelt name or an absent copy is an error and removes nothing."""
        # Given: a copy only in raw/ while both kinds are enabled
        output_context.raw.mkdir(parents=True, exist_ok=True)
        (output_context.raw / "a.zip").write_bytes(b"zip")
        (member,) = _members(tmp_path, "m.txt")
        # When / Then: both nodes name the missing path
        with pytest.raises(FileNotFoundError, match="nonshared_raw"):
            remove_raw_copy(output_context, BOTH, "a.zip")
        with pytest.raises(FileNotFoundError, match="nonshared_raw"):
            replace_raw_copy(output_context, BOTH, "a.zip", [member])
        assert _tree(output_context) == {"raw": ["a.zip"], "nonshared_raw": []}

    def test_missing_member__i623_neg_003(self, output_context: OutputContext, tmp_path: Path) -> None:
        """I623-NEG-003: a member that does not exist stops before any change."""
        # Given: an archive copy and one missing member
        _seed(output_context, "a.zip")
        (member,) = _members(tmp_path, "m.txt")
        # When / Then
        with pytest.raises(FileNotFoundError, match="absent.txt"):
            replace_raw_copy(output_context, BOTH, "a.zip", [member, tmp_path / "absent.txt"])
        assert _tree(output_context) == {"raw": ["a.zip"], "nonshared_raw": ["a.zip"]}

    def test_member_name_clash__i623_neg_004(self, output_context: OutputContext, tmp_path: Path) -> None:
        """I623-NEG-004: two different members with one name would overwrite each other."""
        # Given: same basename from two archive subdirectories
        _seed(output_context, "a.zip")
        first, second = tmp_path / "x" / "data.txt", tmp_path / "y" / "data.txt"
        for path in (first, second):
            path.parent.mkdir()
            path.write_text(str(path), encoding="utf-8")
        # When / Then
        with pytest.raises(ValueError, match="same name 'data.txt'"):
            replace_raw_copy(output_context, BOTH, "a.zip", [first, second])
        assert _tree(output_context) == {"raw": ["a.zip"], "nonshared_raw": ["a.zip"]}

    def test_member_collides_with_other_input__i623_neg_005(self, output_context: OutputContext, tmp_path: Path) -> None:
        """I623-NEG-005: a member never overwrites the copy of another input."""
        # Given: another input's copy with a member's name
        _seed(output_context, "a.zip")
        _seed(output_context, "m.txt", b"other input")
        (member,) = _members(tmp_path, "m.txt")
        # When / Then
        with pytest.raises(FileExistsError, match="m.txt"):
            replace_raw_copy(output_context, BOTH, "a.zip", [member])
        assert (output_context.raw / "m.txt").read_bytes() == b"other input"
        assert _tree(output_context) == {"raw": ["a.zip", "m.txt"], "nonshared_raw": ["a.zip", "m.txt"]}


_INVOICE = {
    "datasetId": "ds",
    "basic": {"dateSubmitted": "2024-01-01", "dataOwnerId": "a" * 56, "dataName": "n", "experimentId": None, "description": None},
    "custom": None,
}


def _data_root(tmp_path: Path, inputs: dict[str, bytes]) -> Path:
    data = tmp_path / "data"
    (data / "inputdata").mkdir(parents=True)
    for name, content in inputs.items():
        (data / "inputdata" / name).write_bytes(content)
    (data / "invoice").mkdir()
    (data / "invoice" / "invoice.json").write_text(json.dumps(_INVOICE), encoding="utf-8")
    (data / "tasksupport").mkdir()
    (data / "tasksupport" / "invoice.schema.json").write_text(json.dumps({"properties": {}}), encoding="utf-8")
    (data / "tasksupport" / "metadata-def.json").write_text(json.dumps({"constant": {}, "variable": []}), encoding="utf-8")
    return data


RUN_CONFIG = {"system": {"save_raw": True, "save_nonshared_raw": True, "save_thumbnail_image": False}}


class TestThroughRunner:
    def test_flow_replaces_uploaded_zip__i623_ep_008(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """I623-EP-008: the Runner's copies exist before the flow, which turns them into the members."""
        # Given: an uploaded zip and a flow storing its members as the raw data
        buffer = tmp_path / "upload.zip"
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("spectrum.txt", b"1,2")
            zf.writestr("photo.jpg", b"jpg")
        data = _data_root(tmp_path, {"upload.zip": buffer.read_bytes()})
        monkeypatch.chdir(tmp_path)
        seen_before: list[bool] = []

        @flow
        def pipeline(paths: InputPaths, out: OutputContext, config: RdeConfig) -> None:
            seen_before.append((out.raw / "upload.zip").is_file() and (out.nonshared_raw / "upload.zip").is_file())
            (archive,) = paths.rawfiles
            with tempfile.TemporaryDirectory() as tmp:
                replace_raw_copy(out, config, archive.name, unzip_inputs(archive, Path(tmp)))

        # When: running it
        report = workflows.run(flow=pipeline, config=RUN_CONFIG)
        # Then: both raw directories hold the members, and the call log shows the node
        assert report.status == "success", report.error
        assert seen_before == [True]
        assert sorted(p.name for p in (data / "raw").iterdir()) == ["photo.jpg", "spectrum.txt"]
        assert sorted(p.name for p in (data / "nonshared_raw").iterdir()) == ["photo.jpg", "spectrum.txt"]
        node_ids = [call["node_id"] for call in report.iterations[0]["node_calls"]]
        assert any(node_id.endswith("replace_raw_copy") for node_id in node_ids)

    def test_flow_removes_input_copy__i623_ep_009(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """I623-EP-009: an input moved to meta/ is no longer stored as raw data."""
        # Given: a data file and a metadata file uploaded together
        data = _data_root(tmp_path, {"sample.txt": b"x", "sample_meta.json": b"{}"})
        monkeypatch.chdir(tmp_path)

        @flow
        def pipeline(out: OutputContext, config: RdeConfig) -> None:
            remove_raw_copy(out, config, "sample_meta.json")

        # When: running it
        report = workflows.run(flow=pipeline, config=RUN_CONFIG)
        # Then: only the data file is stored, and the removal is a recorded node call
        assert report.status == "success", report.error
        assert [p.name for p in (data / "raw").iterdir()] == ["sample.txt"]
        assert [p.name for p in (data / "nonshared_raw").iterdir()] == ["sample.txt"]
        calls = report.iterations[0]["node_calls"]
        assert [call["status"] for call in calls] == ["completed"]
        assert calls[0]["node_id"].endswith("remove_raw_copy")
