"""Tile material handed to v1 callbacks (Session I6-1, ruling #3 and S14).

Session I5 left ``temp``, ``invoice_patch``, ``smarttable_rowfile`` and
``smarttable_row_data`` as ``None`` on the ``RdeOutputResourcePath`` given to a
v1 callback, so a migrated program could not reach material v1 always provided.
The rules ported here are v1's own: ``workflows.generate_folder_paths_iterator``
(per-tile ``temp``/``invoice_patch``), ``workflows._select_smarttable_rowfile``
(row CSV selection) and ``SmartTableInvoiceInitializer`` (the row dictionary,
which is now returned by value).

Session K0-iii (v1.7 #503) UPDATED EP-052 and EV-054/056/057: v1 no longer
infers the row CSV from ``rawfiles`` (``_select_smarttable_rowfile`` was
deleted); the tile carries it explicitly and the callback reads it as
``smarttable_rawfile``. The cells now read the canonical name (the alias would
raise v1's DeprecationWarning) and pin that nothing is inferred.

Session I-REVIEW-A (ruling #2) moved the row-dictionary cells out of this
module: TC-I6-1-EP-053 and TC-I6-1-EV-058 tested a process-global handoff that
no longer exists. Their replacements are strictly stronger and live in
``tests/v2/compat/test_tile_material_handoff_i_review_a.py`` (TC-IRA-2-EP-020 /
EP-021 prove the by-value handoff, TC-IRA-2-EV-022 proves a concurrent run on
the same root cannot erase it, TC-IRA-2-EV-024 proves the global is gone).

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-I6-1-EP-050 | tile 0 | invoice-mode context | ``temp``/``invoice_patch`` are the tile-0 directories |
| TC-I6-1-EP-051 | divided tile | tile 1 context | both point below ``divided/0001`` |
| TC-I6-1-EP-052 | SmartTable | row CSV carried by ``InputPaths.smarttable_rawfile`` | ``smarttable_rawfile`` is that CSV, ``rawfiles`` untouched, no DeprecationWarning |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-I6-1-EV-054 | non-SmartTable | plain rawfiles | both SmartTable fields stay ``None`` |
| TC-I6-1-EV-055 | divided tile | tile 1, run-level source on the material | ``invoice_org`` stays run-level |
| TC-I6-1-EV-056 | row-CSV-shaped or other first rawfile | nothing on ``smarttable_rawfile`` | ``smarttable_rawfile`` stays ``None`` (no inference, v1.7) |
| TC-I6-1-EV-057 | empty tile | no rawfiles | both SmartTable fields stay ``None`` |
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

from rdetoolkit.compat.v1.callback import to_legacy_dataset_paths
from rdetoolkit.core.context import RunContext
from rdetoolkit.domain.invoice_service import InvoiceService
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.paths import resolve_tile_paths
from rdetoolkit.runner.planner import TileMaterial
from rdetoolkit.types import InputPaths, IterationInfo, OutputContext, RdeConfig
from tests.v2.contract.fixtures import _generate


def _material(root: Path, *, invoice_source: Path | None = None) -> TileMaterial:
    """Build the run-owned material the Runner hands to the callback adapter."""
    return TileMaterial(invoice_source=invoice_source or root / "data" / "invoice" / "invoice.json")


def _context(
    root: Path,
    *,
    idx: int = 0,
    rawfiles: tuple[Path, ...] = (),
    smarttable_rawfile: Path | None = None,
) -> RunContext:
    data_root = root / "data"
    for name in ("inputdata", "invoice", "tasksupport"):
        (data_root / name).mkdir(parents=True, exist_ok=True)
    tile = resolve_tile_paths(data_root, idx)
    return RunContext(
        paths=InputPaths(
            inputdata=data_root / "inputdata",
            invoice=data_root / "invoice",
            tasksupport=data_root / "tasksupport",
            raw=rawfiles[0] if len(rawfiles) == 1 else None,
            rawfiles=rawfiles,
            smarttable_rawfile=smarttable_rawfile,
        ),
        out=OutputContext.from_resource_paths(tile),
        config=RdeConfig(),
        iteration=IterationInfo(index=idx, total=idx + 1, mode="invoice"),
    )


def test_root_tile_exposes_temp_and_invoice_patch__tc_i6_1_ep_050(tmp_path: Path) -> None:
    """TC-I6-1-EP-050: tile 0 receives the real data/temp and data/invoice_patch."""
    # Given: a tile-0 context
    context = _context(tmp_path)

    # When: converting to v1 dataset paths
    legacy = to_legacy_dataset_paths(context, material=_material(tmp_path))

    # Then: both directories are the tile-0 paths, not None
    assert legacy.output_paths.temp == tmp_path / "data" / "temp"
    assert legacy.output_paths.invoice_patch == tmp_path / "data" / "invoice_patch"


def test_divided_tile_exposes_its_own_directories__tc_i6_1_ep_051(tmp_path: Path) -> None:
    """TC-I6-1-EP-051: a divided tile owns divided/0001/temp and invoice_patch."""
    # Given: a tile-1 context
    context = _context(tmp_path, idx=1)

    # When: converting to v1 dataset paths
    legacy = to_legacy_dataset_paths(context, material=_material(tmp_path))

    # Then: the divided tile's own directories are exposed
    assert legacy.output_paths.temp == tmp_path / "data" / "divided" / "0001" / "temp"
    assert legacy.output_paths.invoice_patch == tmp_path / "data" / "divided" / "0001" / "invoice_patch"


def test_smarttable_rowfile_follows_the_v1_rule__tc_i6_1_ep_052(tmp_path: Path) -> None:
    """TC-I6-1-EP-052 (UPDATED, K0-iii): the tile's row CSV reaches the callback as v1.7 hands it."""
    # Given: a SmartTable tile carrying its row CSV explicitly and one user file
    rowfile = tmp_path / "data" / "temp" / "fsmarttable_full_0001.csv"
    rowfile.parent.mkdir(parents=True, exist_ok=True)
    rowfile.write_text("a,b\n1,2\n", encoding="utf-8")
    other = tmp_path / "data" / "temp" / "measurement.txt"
    other.write_text("data", encoding="utf-8")
    context = _context(tmp_path, rawfiles=(other,), smarttable_rawfile=rowfile)

    # When: converting to v1 dataset paths
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        legacy = to_legacy_dataset_paths(context, material=_material(tmp_path))
        exposed = legacy.output_paths.smarttable_rawfile

    # Then: the row CSV is exposed under the canonical name without the deprecated keyword
    assert exposed == rowfile
    # And: rawfiles is handed over unchanged -- the row CSV never enters it
    assert legacy.output_paths.rawfiles == (other,)


def test_non_smarttable_tiles_keep_the_fields_empty__tc_i6_1_ev_054(tmp_path: Path) -> None:
    """TC-I6-1-EV-054: an ordinary tile exposes no SmartTable material."""
    # Given: a tile whose raw file is an ordinary input
    rawfile = tmp_path / "data" / "inputdata" / "sample.txt"
    rawfile.parent.mkdir(parents=True, exist_ok=True)
    rawfile.write_text("raw", encoding="utf-8")
    context = _context(tmp_path, rawfiles=(rawfile,))

    # When: converting to v1 dataset paths
    legacy = to_legacy_dataset_paths(context, material=_material(tmp_path))

    # Then: both SmartTable fields stay empty
    assert legacy.output_paths.smarttable_rawfile is None
    assert legacy.output_paths.smarttable_row_data is None


def test_divided_tile_keeps_the_run_level_invoice_org__tc_i6_1_ev_055(tmp_path: Path) -> None:
    """TC-I6-1-EV-055 (UPDATED, ruling #3): a divided tile uses the plan's source.

    The previous version put a backup on disk and required the adapter to
    *discover* it. That presence rule is review R2's defect — a leftover from an
    earlier run won the same way. The invariant worth keeping is that the
    run-level source is run-level: a divided tile must not fall back to its own
    ``divided/0001/temp/invoice_org.json``.
    """
    # Given: a plan whose run-level source is the backup, and a divided tile
    backup = tmp_path / "data" / "temp" / "invoice_org.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text("{}", encoding="utf-8")
    tile_local = tmp_path / "data" / "divided" / "0001" / "temp" / "invoice_org.json"
    tile_local.parent.mkdir(parents=True, exist_ok=True)
    tile_local.write_text("{}", encoding="utf-8")
    context = _context(tmp_path, idx=1)

    # When: converting to v1 dataset paths
    legacy = to_legacy_dataset_paths(context, material=_material(tmp_path, invoice_source=backup))

    # Then: the tile's own temp directory never shadows the run-level source
    assert legacy.output_paths.invoice_org == backup
    assert legacy.output_paths.invoice_org != tile_local


@pytest.mark.parametrize(
    "filename",
    [
        "other_0000.csv",
        "fsmarttable_full.csv",
        "fsmarttable_full_abcd.csv",
        "fsmarttable_full_0000.txt",
        "fsmarttable_full_0001.csv",
    ],
)
def test_non_matching_first_rawfile_is_not_a_rowfile__tc_i6_1_ev_056(tmp_path: Path, filename: str) -> None:
    """TC-I6-1-EV-056 (UPDATED, K0-iii): no first raw file is ever promoted to the row CSV.

    v1.7 removed the ``rawfiles[0]`` inference, so even a name matching the
    former v1 pattern (the last parameter) is not advertised.
    """
    # Given: a first raw file and no explicitly carried row CSV
    candidate = tmp_path / "data" / "temp" / filename
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text("x", encoding="utf-8")
    context = _context(tmp_path, rawfiles=(candidate,))

    # When: converting to v1 dataset paths
    legacy = to_legacy_dataset_paths(context, material=_material(tmp_path))

    # Then: no row file is advertised
    assert legacy.output_paths.smarttable_rawfile is None


def test_empty_tile_exposes_no_smarttable_material__tc_i6_1_ev_057(tmp_path: Path) -> None:
    """TC-I6-1-EV-057: a tile without raw files exposes no SmartTable material."""
    # Given: a tile with no raw files
    context = _context(tmp_path)

    # When: converting to v1 dataset paths
    legacy = to_legacy_dataset_paths(context, material=_material(tmp_path))

    # Then: both SmartTable fields stay empty
    assert legacy.output_paths.smarttable_rawfile is None
    assert legacy.output_paths.smarttable_row_data is None
