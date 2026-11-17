"""ZIP layout EP/BV partitions for the pre-mutation mode boundary.

| ID | Partition | Expected |
|----|-----------|----------|
| ZIP-N1 | file/directory, directory-case, file-case collision | 1007 before temp |
| ZIP-N2 | parent traversal or backslash directory | 1007 before temp |
| ZIP-B1 | one ordinary file under one directory | valid rdeformat decision |
"""

from pathlib import Path
from zipfile import ZipFile

import pytest

from rdetoolkit.domain.mode_selection import ModeKind, decide_mode
from rdetoolkit.errors import RdeConfigError
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import RdeConfig
from tests.v2.contract.fixtures import _generate


@pytest.mark.parametrize("members", [["a/", "a"], ["Foo/a.txt", "foo/b.txt"], ["a", "A/child.txt"], ["a.txt", "A.txt"], ["../outside/"], ["bad\\directory/"]])
def test_invalid_layout_fails_before_temp__zip_n1_n2(tmp_path: Path, members: list[str]) -> None:
    # Given: a valid project with archive names that cannot be safely materialized.
    _generate.materialize_case(_generate.oracle_case("v1/rdeformat/ok"), tmp_path)
    inputdata = tmp_path / "data/inputdata"
    for existing in inputdata.iterdir():
        existing.unlink()
    with ZipFile(inputdata / "input.zip", "w") as archive:
        for name in members:
            archive.writestr(name, "content")
    temporary = tmp_path / "data/temp"
    runner = Runner(root=tmp_path, inputdata_path=inputdata, unpacked_dir_path=temporary)
    # When: strict execution selects its mode before preparing output directories.
    with pytest.raises(RdeConfigError) as caught:
        decide_mode(RdeConfig(system={"extended_mode": "rdeformat"}), inputdata)
    report = runner.run(lambda: None, system={"extended_mode": "rdeformat"})
    # Then: the catalog ambiguity identifies the archive before any extraction directory.
    assert caught.value.code == 1007
    assert "input.zip" in str(caught.value)
    assert report.error is not None and report.error["code"] == 1007
    assert not temporary.exists()


def test_one_archive_directory_is_valid__zip_b1(tmp_path: Path) -> None:
    # Given: a single file with an explicit parent directory.
    with ZipFile(tmp_path / "input.zip", "w") as archive:
        archive.writestr("raw/", "")
        archive.writestr("raw/data.txt", "content")
    # When: inspecting the strict mode boundary.
    decision = decide_mode(RdeConfig(system={"extended_mode": "rdeformat"}), tmp_path)
    # Then: valid directories preserve the explicit format choice without extraction.
    assert decision.chosen_mode is ModeKind.rdeformat
    assert [path.name for path in tmp_path.iterdir()] == ["input.zip"]
