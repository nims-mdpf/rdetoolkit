"""MultiDataTile mode-specific v1 compatibility for Session I6-B (ruling #3).

The frozen MultiDataTile fixture registers exactly two inputs, which cannot
show the empty-inputdata fallback, the ``divided/`` numbering beyond one tile,
or how the mode reacts to an ExcelInvoice workbook appearing in ``inputdata``.
Those branches live in ``impl/input_controller.MultiFileChecker`` and in mode
resolution, so this module runs v1 itself as a **dynamic oracle**: every
scenario is materialized twice, observed once through the isolated v1 worker
(``_generate._execute_v1_observation``) and once through the v2 Runner, and the
two observations are compared. No fixture under ``fixtures/expected/`` is read
or written here.

Session I6-B changed no MultiDataTile production code: the shared Core wiring
installed by Session I6-1 already reproduces each scenario, and these tests
exist so a later change cannot regress it silently.

The ``multidata_tile.ignore_errors`` projection is pinned as it stands today
(TC-EV-032/033). Whether v1's default and v2's default agree is an open
question owned by Session I7 (session_i5.md audit F3), and the multi-tile
policy seats themselves belong to Phase J; the tests below only fix the
translation, not the default.

Known asymmetry, verified bounded here: v1 creates ``data/temp``
unconditionally before running any input checker
(``workflows.check_files_result``), while v2 creates it only when a tile exists
or an archive is unpacked. On a scenario rejected before that point the whole
observable difference is that one directory entry, and TC-EV-034 asserts the
difference set exactly.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-I6-B-EP-030 | empty inputdata | no input files | one tile with ``rawfiles=()``, full v1 parity |
| TC-I6-B-EP-031 | divided numbering | three input files | ``data/`` + ``divided/0001`` + ``divided/0002``, full v1 parity |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-I6-B-EV-032 | policy projection | ``ignore_errors=True`` | ``execution.on_iteration_error == "continue"``, round-trips |
| TC-I6-B-EV-033 | policy projection | ``ignore_errors=False`` | ``execution.on_iteration_error == "fail_fast"``, round-trips |
| TC-I6-B-EV-034 | mode precedence | ``*_excel_invoice.xlsx`` in inputdata | file detection wins over the configured mode, v1-identically |
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.compat.v1.callback import to_legacy_config
from rdetoolkit.config.normalize import ConfigNormalizer
from rdetoolkit.core.flow import flow
from rdetoolkit.models.config import Config, MultiDataTileSettings, SystemSettings
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths
from tests.v2.contract.fixtures import _generate
from tests.v2.contract.observe import observe_v2_run, parity_view

_MODE = "multidatatile"
#: v1's ``StructuredError`` default code, published verbatim by v2 (§I6-0).
_STRUCTURED_ERROR_CODE = 1
#: The single directory v1 creates before parsing and v2 does not (see module docstring).
_UNPACK_DIRECTORY_GAP = frozenset({"data/temp/"})

#: The five artifact switches ``_generate.oracle_config`` freezes fixtures with
#: (contracts.md §I6-1 ruling #8).
_V2_OVERRIDES: dict[str, Any] = {
    "system": {
        "extended_mode": "MultiDataTile",
        "save_raw": True,
        "save_nonshared_raw": True,
        "save_thumbnail_image": False,
        "magic_variable": False,
    },
    "smarttable": {"save_table_file": False},
}

CaseBuilder = Callable[[Path], None]


@flow
def _noop_flow(paths: InputPaths) -> None:
    """Consume the tile without writing anything the Runner does not own."""
    assert paths.inputdata.is_dir()


# --------------------------------------------------------------------------
# Scenario construction
# --------------------------------------------------------------------------
def _base_case(root: Path) -> None:
    _generate._materialize_oracle_case(_MODE, root)  # noqa: SLF001 -- shared case assembly


def _build_empty_inputdata(root: Path) -> None:
    _base_case(root)
    for path in sorted((root / "data" / "inputdata").iterdir()):
        path.unlink()


def _build_three_inputs(root: Path) -> None:
    _base_case(root)
    (root / "data" / "inputdata" / "tile_02.txt").write_text("third tile\n", encoding="utf-8")


def _build_with_excel_workbook(root: Path) -> None:
    _base_case(root)
    shutil.copy2(
        _generate.INPUT_ROOT / "excelinvoice" / "data" / "inputdata" / "excelinvoice_multi.xlsx",
        root / "data" / "inputdata" / "stray_excel_invoice.xlsx",
    )


# --------------------------------------------------------------------------
# Oracle / subject harness
# --------------------------------------------------------------------------
def _observe_v1(build: CaseBuilder) -> dict[str, Any]:
    """Run the scenario through the isolated v1 worker and observe it."""
    with tempfile.TemporaryDirectory(prefix="i6b-mdt-oracle-") as temporary:
        root = Path(temporary) / "case"
        root.mkdir()
        build(root)
        # The same worker that froze the static fixtures; reusing it keeps the
        # oracle's config, normalization and observation identical to theirs.
        return _generate._execute_v1_observation(_MODE, "ok", root)  # noqa: SLF001


def _observe_v2(
    build: CaseBuilder,
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Any, dict[str, Any]]:
    """Run the same scenario through the v2 Runner and observe it."""
    root.mkdir()
    build(root)
    monkeypatch.chdir(root)
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        # The flow entry unpacks into data/temp, as v1 does (contracts.md §I6-1).
        unpacked_dir_path=root / "data" / "temp",
    )
    return runner.run(_noop_flow, **_V2_OVERRIDES), observe_v2_run(root)


def _tree_divergence(observed: dict[str, Any], oracle: dict[str, Any]) -> set[str]:
    """Return every output-tree entry present on exactly one side."""
    expected = parity_view(oracle)["output_tree"]
    actual = observed["output_tree"]
    return {
        entry
        for group in ("directories", "files")
        for entry in set(actual[group]) ^ set(expected[group])
    }


def _job_failed(root: Path) -> str:
    return _generate.normalize_snapshot(
        (root / "data" / "job.failed").read_text(encoding="utf-8"),
        roots=(root,),
    )


# --------------------------------------------------------------------------
# EP cases
# --------------------------------------------------------------------------
def test_empty_inputdata_still_yields_one_tile__tc_i6_b_ep_030(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-B-EP-030: v1's ``[()]`` fallback runs the flow once with no raw input."""
    # Given: a MultiDataTile case whose inputdata directory is empty
    oracle = _observe_v1(_build_empty_inputdata)
    assert oracle["exit_code"] == 0
    assert oracle["callback_count"] == 1

    # When: running the identical input through the v2 Runner
    report, observed = _observe_v2(_build_empty_inputdata, tmp_path / _MODE, monkeypatch)

    # Then: exactly one tile ran, published nothing, and matches v1 everywhere
    assert report.status == "success"
    assert len(report.iterations) == 1
    assert observed["raw_sha256"] == {}
    assert observed == parity_view(oracle)


def test_three_inputs_number_the_divided_tiles__tc_i6_b_ep_031(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-B-EP-031: tile 0 stays flat while later tiles take ``divided/000N``."""
    # Given: a MultiDataTile case with three input files
    oracle = _observe_v1(_build_three_inputs)
    assert oracle["callback_count"] == 3

    # When: running the identical input through the v2 Runner
    report, observed = _observe_v2(_build_three_inputs, tmp_path / _MODE, monkeypatch)

    # Then: the divided numbering and every artifact match v1
    assert report.status == "success"
    assert len(report.iterations) == 3
    directories = observed["output_tree"]["directories"]
    assert "data/divided/0001/" in directories
    assert "data/divided/0002/" in directories
    assert "data/divided/0000/" not in directories
    assert observed == parity_view(oracle)


# --------------------------------------------------------------------------
# BV / negative cases
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("ignore_errors", "policy", "case_id"),
    [
        pytest.param(True, "continue", "TC-I6-B-EV-032", id="TC-I6-B-EV-032"),
        pytest.param(False, "fail_fast", "TC-I6-B-EV-033", id="TC-I6-B-EV-033"),
    ],
)
def test_ignore_errors_projects_onto_the_iteration_policy(
    ignore_errors: bool,
    policy: str,
    case_id: str,
) -> None:
    """``multidata_tile.ignore_errors`` is the only source of the v2 error policy.

    This pins the translation as it stands. Whether the two implementations
    agree on the *default* is Session I7 business, and the multi-tile policy
    behaviour itself is Phase J; neither is asserted here.
    """
    # Given: a v1 configuration that differs from the default only in this flag
    legacy = Config(
        system=SystemSettings(extended_mode="MultiDataTile"),
        multidata_tile=MultiDataTileSettings(ignore_errors=ignore_errors),
    )

    # When: projecting it forward and back through the production normalizers
    canonical = ConfigNormalizer().normalize(legacy, root=Path("/nonexistent"), origin="v1")
    round_tripped = to_legacy_config(canonical)

    # Then: the flag survives both directions under its v2 spelling
    assert canonical.execution.on_iteration_error == policy, case_id
    assert round_tripped.multidata_tile is not None
    assert round_tripped.multidata_tile.ignore_errors is ignore_errors


def test_excel_workbook_overrides_the_configured_mode__tc_i6_b_ev_034(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-B-EV-034: file detection outranks ``extended_mode``, exactly as in v1.

    A ``*_excel_invoice.xlsx`` in ``inputdata`` switches both implementations to
    the ExcelInvoice checker, which then rejects the MultiDataTile inputs. The
    contract is that v2 fails the same way rather than quietly staying in
    MultiDataTile mode.
    """
    # Given: a MultiDataTile case that also carries an ExcelInvoice workbook
    oracle = _observe_v1(_build_with_excel_workbook)
    assert oracle["exit_code"] == 1
    assert oracle["callback_count"] == 0
    assert oracle["job_failed_text"] == (
        f"ErrorCode={_STRUCTURED_ERROR_CODE}\nErrorMessage=ERROR: input file should be EXCEL or ZIP file\n"
    )

    # When: running the identical input through the v2 Runner
    root = tmp_path / _MODE
    report, observed = _observe_v2(_build_with_excel_workbook, root, monkeypatch)

    # Then: v2 fails before any tile with v1's byte-identical job.failed
    assert report.status == "failed"
    assert report.iterations == []
    assert report.error is not None
    assert report.error["code"] == _STRUCTURED_ERROR_CODE
    assert _job_failed(root) == oracle["job_failed_text"]

    # And: the artifacts agree, up to the one directory v1 pre-creates
    assert observed["raw_sha256"] == parity_view(oracle)["raw_sha256"]
    assert observed["invoices"] == parity_view(oracle)["invoices"]
    assert _tree_divergence(observed, oracle) == set(_UNPACK_DIRECTORY_GAP)
