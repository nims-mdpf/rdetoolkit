"""Branch contracts for path-based artifact services.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| raw copy | shared only | copies only to raw | TC-EP-HR-F6-201 |
| raw copy | directory and missing path | copies directory and skips missing | TC-EP-HR-F6-202 |
| raw copy | copy failure | raises catalogued execution error | TC-EP-HR-F6-203 |
| SmartTable selection | original table retained | save_table_file branch selected | TC-EP-HR-F6-204 |
| image generation | disabled | converter is not called | TC-EP-HR-F6-205 |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| raw copy | one missing source | no artifact and no failure | TC-BV-HR-F6-201 |
"""

from pathlib import Path

import pytest

from rdetoolkit.domain.artifacts import ImageArtifactService, RawArtifactService
from rdetoolkit.errors import RdeExecutionError
from rdetoolkit.types import RdeConfig


def test_raw_copy_shared_only__tc_ep_hr_f6_201(tmp_path: Path) -> None:
    """TC-EP-HR-F6-201: save_raw and save_nonshared_raw branch independently."""
    # Given: one source and shared-only artifact configuration
    source = tmp_path / "source.txt"
    source.write_text("raw", encoding="utf-8")
    raw = tmp_path / "raw"
    nonshared = tmp_path / "nonshared"
    config = RdeConfig(system={"save_raw": True, "save_nonshared_raw": False})

    # When: copying configured raw artifacts
    RawArtifactService().copy((source,), raw_dir=raw, nonshared_raw_dir=nonshared, config=config)

    # Then: only the enabled destination is populated
    assert (raw / source.name).read_text(encoding="utf-8") == "raw"
    assert not nonshared.exists()


def test_raw_copy_directory_and_skips_missing__tc_ep_hr_f6_202_bv_201(tmp_path: Path) -> None:
    """TC-EP/BV-HR-F6-202/201: directory and neither-file-nor-dir branches are total."""
    # Given: one directory source and one nonexistent boundary source
    source_dir = tmp_path / "source-dir"
    source_dir.mkdir()
    (source_dir / "nested.txt").write_text("nested", encoding="utf-8")
    missing = tmp_path / "missing"
    destination = tmp_path / "nonshared"

    # When: copying with the default nonshared policy
    RawArtifactService().copy(
        (source_dir, missing),
        raw_dir=tmp_path / "raw",
        nonshared_raw_dir=destination,
        config=RdeConfig(),
    )

    # Then: the directory is copied and the missing entry is skipped
    assert (destination / source_dir.name / "nested.txt").read_text(encoding="utf-8") == "nested"
    assert not (destination / missing.name).exists()


def test_raw_copy_failure_is_catalogued__tc_ep_hr_f6_203(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-EP-HR-F6-203: filesystem copy failures retain catalog semantics."""
    # Given: a file source whose copy operation fails
    source = tmp_path / "source.txt"
    source.write_text("raw", encoding="utf-8")
    monkeypatch.setattr("rdetoolkit.domain.artifacts.shutil.copy2", lambda source, target: (_ for _ in ()).throw(OSError("full")))

    # When / Then: the service raises a code-3001 execution error
    with pytest.raises(RdeExecutionError) as exc_info:
        RawArtifactService().copy(
            (source,),
            raw_dir=tmp_path / "raw",
            nonshared_raw_dir=tmp_path / "nonshared",
            config=RdeConfig(),
        )
    assert exc_info.value.code == 3001


def test_smarttable_selection_retains_original_when_configured__tc_ep_hr_f6_204(tmp_path: Path) -> None:
    """TC-EP-HR-F6-204: save_table_file retains the original table only."""
    # Given: original, generated-row, and ordinary SmartTable inputs
    inputdata = tmp_path / "inputdata"
    original = inputdata / "smarttable_source.xlsx"
    generated = tmp_path / "fsmarttable_0000.csv"
    ordinary = tmp_path / "sample.txt"
    config = RdeConfig(smarttable={"save_table_file": True})

    # When: applying SmartTable source selection
    selected = RawArtifactService._selected_files(
        (generated, ordinary, original),
        config=config,
        smarttable=True,
    )

    # Then: generated rows are excluded while the original table is retained
    assert selected == tuple(sorted((ordinary, original)))


def test_image_generation_disabled_skips_converter__tc_ep_hr_f6_205(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-EP-HR-F6-205: the disabled boundary has no converter side effect."""
    # Given: a converter that would fail if called and thumbnail generation disabled
    monkeypatch.setattr(
        "rdetoolkit.domain.artifacts.img2thumb.copy_images_to_thumbnail",
        lambda thumbnail, main: (_ for _ in ()).throw(AssertionError("called")),
    )

    # When: generating optional image artifacts
    ImageArtifactService().generate(
        main_image_dir=tmp_path / "main",
        thumbnail_dir=tmp_path / "thumb",
        config=RdeConfig(),
    )

    # Then: returning successfully proves the converter was skipped
