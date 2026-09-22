"""RDEFormat raw publication and invoice-stage selection (Session I6-A).

RDEFormat is the one mode whose v1 pipeline does not copy raw inputs "per
tile": ``processing/processors/files.py::RDEFormatFileCopier`` dispatches every
raw file to the output directory named by a *path component* of that file, with
no configuration gate at all. The generic ``RawArtifactService`` cannot express
this, so Session I6-1 installed the ``raw_copy_strategy`` seam and this session
fills it (ruling #1).

The same v1 pipeline (``processing/factories.py::RDEFormatPipelineBuilder``)
has neither ``StructuredInvoiceSaver`` nor ``VariableApplier``, so the mode also
narrows the post-invoke invoice stage (ruling #2).

EP table (component routing — one row per v1 destination):
| TC | Class | Input rawfile | Expected destination |
|----|-------|---------------|----------------------|
| TC-I6-A-EP-001 | raw | ``temp/0000/raw/first.txt`` | ``<tile>/raw/first.txt`` |
| TC-I6-A-EP-002 | main_image | ``temp/0000/main_image/1.jpg`` | ``<tile>/main_image/1.jpg`` |
| TC-I6-A-EP-003 | other_image | ``temp/0000/other_image/2.jpg`` | ``<tile>/other_image/2.jpg`` |
| TC-I6-A-EP-004 | meta | ``temp/0000/meta/metadata.json`` | ``<tile>/meta/metadata.json`` |
| TC-I6-A-EP-005 | structured | ``temp/0000/structured/result.csv`` | ``<tile>/structured/result.csv`` |
| TC-I6-A-EP-006 | logs | ``temp/0000/logs/run.log`` | ``<tile>/logs/run.log`` |
| TC-I6-A-EP-007 | nonshared_raw | ``temp/0000/nonshared_raw/n.txt`` | ``<tile>/nonshared_raw/n.txt`` |
| TC-I6-A-EP-008 | seam | ``RdeFormatModeHandler.raw_copy_strategy`` | an RDEFormat strategy, not ``None`` |
| TC-I6-A-EP-009 | invoice stage | ``RdeFormatModeHandler.artifact_stage_order`` | ``(thumbnail, description)`` -- ``description`` only, of the three invoice steps |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-I6-A-EV-010 | no component | ``inputdata/plain.txt`` | copied nowhere; every destination stays empty |
| TC-I6-A-EV-011 | first match wins | ``meta/raw/x.txt`` and ``raw/meta/y.txt`` | both land in ``raw/`` (v1 dict order) |
| TC-I6-A-EV-012 | no config gate | ``save_raw`` and ``save_nonshared_raw`` both false | both files are still copied |
| TC-I6-A-EV-013 | no duplication | one ``raw/`` input | ``nonshared_raw/`` stays empty |
| TC-I6-A-EV-014 | missing destination | destination directory deleted | ``RdeExecutionError`` 3001 |
| TC-I6-A-EV-015 | directory input | a directory below ``raw/`` | ``RdeExecutionError`` 3001 (v1 ``shutil.copy``) |
| TC-I6-A-EV-016 | smarttable flag | ``smarttable=True`` with a table-looking input | still copied; RDEFormat has no filter |
| TC-I6-A-EV-017 | empty input | no source files | nothing written anywhere |
| TC-I6-A-EV-018 | basename collision | same basename under two components | one file per component directory |
| TC-I6-A-EV-019 | invoice stage | selected steps | excludes ``structured`` and ``magic`` |
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from rdetoolkit.domain.invoice_service import (
    INVOICE_STEP_DESCRIPTION,
    INVOICE_STEP_MAGIC,
    INVOICE_STEP_STRUCTURED,
    INVOICE_STEPS,
)
from rdetoolkit.errors import RdeExecutionError
from rdetoolkit.modes.rdeformat import RdeFormatModeHandler, RdeFormatRawCopyStrategy
from rdetoolkit.types import RdeConfig

_COPY_FAILED_CODE = 3001

#: The twelve directories the Runner creates per tile (runner/paths.py).
_TILE_DIRNAMES = (
    "structured",
    "meta",
    "main_image",
    "other_image",
    "thumbnail",
    "attachment",
    "nonshared_raw",
    "raw",
    "invoice",
    "logs",
    "temp",
    "invoice_patch",
)


def _tile_root(tmp_path: Path) -> Path:
    """Create one tile's output directories the way the Runner does."""
    tile = tmp_path / "data"
    for name in _TILE_DIRNAMES:
        (tile / name).mkdir(parents=True, exist_ok=True)
    return tile


def _source(tmp_path: Path, relative: str, content: str = "payload\n") -> Path:
    """Materialize one unpacked RDEFormat input below ``data/temp``."""
    path = tmp_path / "data" / "temp" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _copy(
    tile: Path,
    sources: tuple[Path, ...],
    *,
    config: RdeConfig | None = None,
    smarttable: bool = False,
    data_root: Path | None = None,
) -> None:
    """Run the strategy with the executor's keyword contract.

    ``data_root`` bounds the component classification (Session I-REVIEW-A
    ruling #7); the tile directory *is* the data root in these fixtures.
    """
    RdeFormatRawCopyStrategy().copy(
        sources,
        raw_dir=tile / "raw",
        nonshared_raw_dir=tile / "nonshared_raw",
        config=config if config is not None else RdeConfig(),
        smarttable=smarttable,
        data_root=data_root if data_root is not None else tile,
    )


def _names(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir()) if directory.exists() else []


#: ``temp`` holds the unpacked RDEFormat inputs, so it is an input directory
#: that happens to live beside the outputs; every other tile directory is a
#: publication destination and must stay empty unless the strategy wrote to it.
_OUTPUT_DIRNAMES = tuple(name for name in _TILE_DIRNAMES if name != "temp")


def _populated(tile: Path) -> dict[str, list[str]]:
    """Return only the tile output directories that received something."""
    return {name: _names(tile / name) for name in _OUTPUT_DIRNAMES if _names(tile / name)}


@pytest.mark.parametrize(
    ("component", "filename", "case_id"),
    [
        pytest.param("raw", "first.txt", "TC-I6-A-EP-001", id="TC-I6-A-EP-001-raw"),
        pytest.param("main_image", "1.jpg", "TC-I6-A-EP-002", id="TC-I6-A-EP-002-main_image"),
        pytest.param("other_image", "2.jpg", "TC-I6-A-EP-003", id="TC-I6-A-EP-003-other_image"),
        pytest.param("meta", "metadata.json", "TC-I6-A-EP-004", id="TC-I6-A-EP-004-meta"),
        pytest.param("structured", "result.csv", "TC-I6-A-EP-005", id="TC-I6-A-EP-005-structured"),
        pytest.param("logs", "run.log", "TC-I6-A-EP-006", id="TC-I6-A-EP-006-logs"),
        pytest.param("nonshared_raw", "n.txt", "TC-I6-A-EP-007", id="TC-I6-A-EP-007-nonshared_raw"),
    ],
)
def test_each_v1_component_routes_to_its_own_directory(
    component: str,
    filename: str,
    case_id: str,
    tmp_path: Path,
) -> None:
    """TC-I6-A-EP-001..007: every v1 destination component keeps its own route."""
    # Given: one unpacked input below the component directory v1 dispatches on
    assert case_id.startswith("TC-I6-A-EP-")
    tile = _tile_root(tmp_path)
    source = _source(tmp_path, f"0000/{component}/{filename}")

    # When: publishing the tile's raw inputs through the RDEFormat strategy
    _copy(tile, (source,))

    # Then: exactly the matching component directory received the file
    assert _populated(tile) == {component: [filename]}
    assert (tile / component / filename).read_text(encoding="utf-8") == "payload\n"


def test_handler_installs_the_rdeformat_strategy__tc_i6_a_ep_008() -> None:
    """TC-I6-A-EP-008: the handler no longer defers to the generic service."""
    # Given: the production RDEFormat handler, resolved through the live module.
    # TC-EP-I5-003 reloads every mode module, which rebinds the class objects;
    # an identity check has to read both names after that, not at import time.
    from rdetoolkit.modes import rdeformat as module

    handler = module.RdeFormatModeHandler()

    # When: the executor asks for this mode's raw publication strategy
    strategy = handler.raw_copy_strategy(None)  # type: ignore[arg-type]

    # Then: RDEFormat owns raw publication instead of RawArtifactService
    assert isinstance(strategy, module.RdeFormatRawCopyStrategy)


def test_invoice_stage_runs_description_only__tc_i6_a_ep_009() -> None:
    """TC-I6-A-EP-009: the v1 RDEFormat pipeline's invoice stage is description-only."""
    # Given: the production RDEFormat handler
    handler = RdeFormatModeHandler()

    # When: the executor asks for this mode's artifact stage sequence
    order = handler.artifact_stage_order(None)  # type: ignore[arg-type]

    # Then: of the three invoice steps only the DescriptionUpdater survives
    assert order is not None
    assert frozenset(order) & INVOICE_STEPS == frozenset({INVOICE_STEP_DESCRIPTION})
    # And: the sequence is ordered, thumbnail first, as the v1 pipeline is
    assert order == ("thumbnail", INVOICE_STEP_DESCRIPTION)


def test_unmatched_component_is_not_published__tc_i6_a_ev_010(tmp_path: Path) -> None:
    """TC-I6-A-EV-010: a file with no destination component is silently skipped."""
    # Given: an input whose path names no v1 destination directory
    tile = _tile_root(tmp_path)
    source = tmp_path / "data" / "inputdata" / "plain.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("payload\n", encoding="utf-8")

    # When: publishing it through the RDEFormat strategy
    _copy(tile, (source,))

    # Then: v1 copies it nowhere, so neither does v2
    assert _populated(tile) == {}


@pytest.mark.parametrize(
    ("relative", "case_id"),
    [
        pytest.param("0000/meta/raw/x.txt", "TC-I6-A-EV-011a", id="TC-I6-A-EV-011-meta-then-raw"),
        pytest.param("0000/raw/meta/y.txt", "TC-I6-A-EV-011b", id="TC-I6-A-EV-011-raw-then-meta"),
    ],
)
def test_first_matching_component_wins__tc_i6_a_ev_011(
    relative: str,
    case_id: str,
    tmp_path: Path,
) -> None:
    """TC-I6-A-EV-011: ambiguity resolves by v1's destination order, not by depth."""
    # Given: an input whose path names two destination components
    assert case_id.startswith("TC-I6-A-EV-011")
    tile = _tile_root(tmp_path)
    source = _source(tmp_path, relative)

    # When: publishing it through the RDEFormat strategy
    _copy(tile, (source,))

    # Then: ``raw`` precedes ``meta`` in v1's dict, so ``raw`` claims the file
    assert _populated(tile) == {"raw": [Path(relative).name]}


def test_config_gates_do_not_apply__tc_i6_a_ev_012(tmp_path: Path) -> None:
    """TC-I6-A-EV-012: RDEFormat ignores save_raw / save_nonshared_raw."""
    # Given: both raw gates disabled, which would silence the generic service
    tile = _tile_root(tmp_path)
    config = RdeConfig(system={"save_raw": False, "save_nonshared_raw": False})
    raw_source = _source(tmp_path, "0000/raw/first.txt")
    nonshared_source = _source(tmp_path, "0000/nonshared_raw/n.txt")

    # When: publishing through the RDEFormat strategy
    _copy(tile, (raw_source, nonshared_source), config=config)

    # Then: v1's RDEFormatFileCopier has no gate, so both files are published
    assert _populated(tile) == {"nonshared_raw": ["n.txt"], "raw": ["first.txt"]}


def test_raw_input_is_not_mirrored_to_nonshared_raw__tc_i6_a_ev_013(tmp_path: Path) -> None:
    """TC-I6-A-EV-013: one input reaches exactly one destination."""
    # Given: a single ``raw/`` input and both gates enabled
    tile = _tile_root(tmp_path)
    config = RdeConfig(system={"save_raw": True, "save_nonshared_raw": True})
    source = _source(tmp_path, "0000/raw/first.txt")

    # When: publishing through the RDEFormat strategy
    _copy(tile, (source,), config=config)

    # Then: unlike RawArtifactService, nothing is mirrored into nonshared_raw
    assert _populated(tile) == {"raw": ["first.txt"]}


def test_missing_destination_directory_is_catalogued__tc_i6_a_ev_014(tmp_path: Path) -> None:
    """TC-I6-A-EV-014: directory creation stays owned by the Runner."""
    # Given: a tile whose meta/ directory was never created
    tile = _tile_root(tmp_path)
    shutil.rmtree(tile / "meta")
    source = _source(tmp_path, "0000/meta/metadata.json")

    # When/Then: the copy fails as a catalogued execution error, not silently
    with pytest.raises(RdeExecutionError) as excinfo:
        _copy(tile, (source,))
    assert excinfo.value.code == _COPY_FAILED_CODE
    assert "metadata.json" in str(excinfo.value)


def test_directory_input_is_catalogued__tc_i6_a_ev_015(tmp_path: Path) -> None:
    """TC-I6-A-EV-015: v1 uses ``shutil.copy``, which cannot copy a tree."""
    # Given: a directory (not a file) below a destination component
    tile = _tile_root(tmp_path)
    source = tmp_path / "data" / "temp" / "0000" / "raw" / "nested"
    source.mkdir(parents=True, exist_ok=True)

    # When/Then: the failure is catalogued instead of producing a partial tree
    with pytest.raises(RdeExecutionError) as excinfo:
        _copy(tile, (source,))
    assert excinfo.value.code == _COPY_FAILED_CODE


def test_smarttable_flag_is_ignored__tc_i6_a_ev_016(tmp_path: Path) -> None:
    """TC-I6-A-EV-016: SmartTable filtering is not part of the RDEFormat contract."""
    # Given: an input the SmartTable filter would drop, under raw/
    tile = _tile_root(tmp_path)
    source = _source(tmp_path, "0000/raw/fsmarttable_x_0000.csv")

    # When: publishing with the executor's SmartTable flag forced on
    _copy(tile, (source,), smarttable=True)

    # Then: RDEFormat publishes it, because v1 applies no SmartTable rule here
    assert _populated(tile) == {"raw": ["fsmarttable_x_0000.csv"]}


def test_empty_input_publishes_nothing__tc_i6_a_ev_017(tmp_path: Path) -> None:
    """TC-I6-A-EV-017: a tile with no raw inputs leaves the tree untouched."""
    # Given: a prepared tile and no source files
    tile = _tile_root(tmp_path)

    # When: publishing an empty input tuple
    _copy(tile, ())

    # Then: no directory received anything
    assert _populated(tile) == {}


def test_same_basename_under_two_components__tc_i6_a_ev_018(tmp_path: Path) -> None:
    """TC-I6-A-EV-018: routing is by component, so equal basenames do not collide."""
    # Given: one ``data.txt`` below raw/ and another below meta/
    tile = _tile_root(tmp_path)
    raw_source = _source(tmp_path, "0000/raw/data.txt", content="raw\n")
    meta_source = _source(tmp_path, "0000/meta/data.txt", content="meta\n")

    # When: publishing both through the RDEFormat strategy
    _copy(tile, (raw_source, meta_source))

    # Then: each component directory holds its own copy
    assert _populated(tile) == {"meta": ["data.txt"], "raw": ["data.txt"]}
    assert (tile / "raw" / "data.txt").read_text(encoding="utf-8") == "raw\n"
    assert (tile / "meta" / "data.txt").read_text(encoding="utf-8") == "meta\n"


def test_invoice_stage_excludes_structured_and_magic__tc_i6_a_ev_019() -> None:
    """TC-I6-A-EV-019: the two absent v1 processors must stay unselected."""
    # Given: the production RDEFormat handler
    handler = RdeFormatModeHandler()

    # When: the executor asks for this mode's artifact stage sequence
    order = handler.artifact_stage_order(None)  # type: ignore[arg-type]

    # Then: neither StructuredInvoiceSaver nor VariableApplier is selected
    assert order is not None
    assert INVOICE_STEP_STRUCTURED not in order
    assert INVOICE_STEP_MAGIC not in order
