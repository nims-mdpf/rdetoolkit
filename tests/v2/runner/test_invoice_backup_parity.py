"""Regression tests for v1-compatible run-level invoice backup selection.

Equivalence partitions (EP):

| API | Partition | Rationale | Expected | Test ID |
| --- | --- | --- | --- | --- |
| ``Runner.iterate`` | excelinvoice | existing positive control | temp backup exists | TC-G0-BACKUP-001 |
| ``Runner.iterate`` | rdeformat | missing v2 delegation | temp backup exists | TC-G0-BACKUP-002 |
| ``Runner.iterate`` | multidatatile | missing v2 delegation | temp backup exists | TC-G0-BACKUP-003 |
| ``Runner.iterate`` | invoice | excluded mode | temp backup absent | TC-G0-BACKUP-004 |
| ``Runner.iterate`` | smarttable | excluded mode | temp backup absent | TC-G0-BACKUP-005 |
| ``Runner.iterate`` | nested layout | legacy data-root layout | backup content equals source | TC-GR-BACKUP-006 |
| ``Runner.iterate`` | flat layout | public flat-root layout | backup content equals source | TC-GR-BACKUP-006 |
| ``Runner.iterate`` | cwd equals root | legacy caller placement | backup content equals source | TC-GR-BACKUP-006 |
| ``Runner.iterate`` | cwd differs from root | public root independence | backup content equals source | TC-GR-BACKUP-006 |
| ``Runner.iterate`` | excel/rdeformat/multidatatile | three v1 backup modes | backup content equals source | TC-GR-BACKUP-006 |
| flat invoice helper | explicit invoice path | mode-independent path copy | TC-GR-BACKUP-007 |
| ``Runner.run`` | rdeformat + unpack root data/temp | backup must not become a raw input | TC-I6-1-EV-070 |
| ``create_common_tiles`` | zero tiles | v1 backs up regardless of tile count | TC-I6-1-EV-071 |

Boundary values (BV):

| API | Boundary | Rationale | Expected | Test ID |
| --- | --- | --- | --- | --- |
| ``Runner.iterate`` | one tile | minimum run that prepares an invoice source | mode contract holds | TC-G0-BACKUP-001..005 |
| ``Runner.iterate`` | 2 layouts x 2 cwd relations x 3 modes | complete backup path boundary | all 12 cells preserve content | TC-GR-BACKUP-006 |
| flat invoice helper | no mode argument | narrow helper signature | TC-GR-BACKUP-007 |

NOTE (2026-07-15): reconstructed from the surviving pytest ``.pyc`` after the
original working tree was wiped before commit (see session_g0.md). Semantics,
test ids and assertions are preserved from the verified original.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rdetoolkit.runner.execute import ExecutionResult
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.paths import resolve_tile_paths
from rdetoolkit.runner.planner import TilePreparation, _flat_layout_invoice_source
from rdetoolkit.types import InputPaths, IterationInfo, OutputContext, RdeConfig

_CASES = [
    pytest.param(ModeKind.excelinvoice, True, id="excelinvoice"),
    pytest.param(ModeKind.rdeformat, True, id="rdeformat"),
    pytest.param(ModeKind.multidatatile, True, id="multidatatile"),
    pytest.param(ModeKind.invoice, False, id="invoice"),
    pytest.param(ModeKind.smarttable, False, id="smarttable"),
]

_LAYOUT_CWD_MODE_CASES = [
    pytest.param(layout, cwd_relation, mode, id=f"{layout}-{cwd_relation}-{mode.value}")
    for layout in ("nested", "flat")
    for cwd_relation in ("same", "different")
    for mode in (ModeKind.excelinvoice, ModeKind.rdeformat, ModeKind.multidatatile)
]


def test_flat_layout_invoice_source_has_mode_independent_signature__tc_gr_backup_007(
    tmp_path: Path,
) -> None:
    """TC-GR-BACKUP-007: The flat helper needs only its explicit invoice path."""
    # Given: a flat-layout source invoice
    invoice_org = tmp_path / "invoice" / "invoice.json"
    invoice_org.parent.mkdir(parents=True)
    source = {"datasetId": "flat", "basic": {"dataName": "mode-independent"}}
    invoice_org.write_text(json.dumps(source), encoding="utf-8")

    # When: backing it up without an unused mode argument
    backup_path = _flat_layout_invoice_source(invoice_org=invoice_org)

    # Then: the explicit path rule preserves the source content
    assert backup_path == tmp_path / "temp" / "invoice_org.json"
    assert json.loads(backup_path.read_text(encoding="utf-8")) == source


@pytest.mark.parametrize(("mode", "expects_backup"), _CASES)
def test_run_level_invoice_backup_matches_v1_mode_contract__tc_g0_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: ModeKind,
    expects_backup: bool,
) -> None:
    """TC-G0-BACKUP-001..005: only the three v1 modes create a temp backup."""
    # Given: a minimal data tree with a run-level source invoice
    data_root = tmp_path / "data"
    inputdata = data_root / "inputdata"
    invoice_dir = data_root / "invoice"
    tasksupport = data_root / "tasksupport"
    unpacked = data_root / "temp"
    for path in (inputdata, invoice_dir, tasksupport, unpacked):
        path.mkdir(parents=True)
    source = {"datasetId": "source", "basic": {"dataName": "original"}}
    source_path = invoice_dir / "invoice.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")
    rawfile = inputdata / ("source.xlsx" if mode is ModeKind.excelinvoice else "source.dat")
    rawfile.write_text("placeholder", encoding="utf-8")

    # And: tile machinery stubbed so only the run-level invoice-source
    # preparation (the behavior under test) touches the real filesystem
    info = IterationInfo(index=0, total=1, mode=mode.value)
    paths = InputPaths(
        inputdata=inputdata,
        invoice=invoice_dir,
        tasksupport=tasksupport,
        raw=rawfile,
        rawfiles=(rawfile,),
    )
    # A complete OutputContext: the Runner now injects artifact services, so a
    # partial double would hide the per-tile publication path from this test.
    out = OutputContext.from_resource_paths(resolve_tile_paths(data_root, 0))
    monkeypatch.setattr(
        "rdetoolkit.runner.planner.iterate_tiles",
        lambda *args, **kwargs: iter([(info, paths, out)]),
    )
    monkeypatch.setattr(
        "rdetoolkit.runner.planner._tile_invoice",
        lambda *args, **kwargs: TilePreparation(),
    )
    monkeypatch.setattr(
        "rdetoolkit.runner.invoker.run_tile",
        lambda *args, **kwargs: ExecutionResult(
            iteration_index=0,
            status="completed",
            call_records=(),
            outputs=(),
            datatile_id="source",
        ),
    )

    # When: one Runner iteration executes in the given mode
    monkeypatch.chdir(tmp_path)
    runner = Runner(
        root=tmp_path,
        inputdata_path=inputdata,
        unpacked_dir_path=unpacked,
        run_id_factory=lambda: f"backup-{mode.value}",
    )
    runner.run_id = f"backup-{mode.value}"
    report = runner.iterate(lambda: None, mode, RdeConfig())
    backup_path = data_root / "temp" / "invoice_org.json"

    # Then: the v1 mode contract decides whether the temp backup exists
    assert report.status == "success"
    assert backup_path.exists() is expects_backup
    if expects_backup:
        assert json.loads(backup_path.read_text(encoding="utf-8")) == source


@pytest.mark.parametrize(("layout", "cwd_relation", "mode"), _LAYOUT_CWD_MODE_CASES)
def test_invoice_backup_is_root_relative_across_layout_cwd_mode_matrix__tc_gr_backup_006(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    layout: str,
    cwd_relation: str,
    mode: ModeKind,
) -> None:
    """TC-GR-BACKUP-006: every backup mode preserves content independently of cwd."""
    # Given: a flat or nested run tree containing one source invoice and input
    root = tmp_path / "run"
    data_root = root / "data" if layout == "nested" else root
    inputdata = data_root / "inputdata"
    invoice_dir = data_root / "invoice"
    tasksupport = data_root / "tasksupport"
    unpacked = data_root / "temp"
    for path in (inputdata, invoice_dir, tasksupport, unpacked):
        path.mkdir(parents=True)
    source = {"datasetId": f"{layout}-{cwd_relation}", "basic": {"dataName": mode.value}}
    (invoice_dir / "invoice.json").write_text(json.dumps(source), encoding="utf-8")
    rawfile = inputdata / ("source.xlsx" if mode is ModeKind.excelinvoice else "source.dat")
    rawfile.write_text("placeholder", encoding="utf-8")

    # And: one successful tile isolates run-level invoice-source preparation
    info = IterationInfo(index=0, total=1, mode=mode.value)
    paths = InputPaths(
        inputdata=inputdata,
        invoice=invoice_dir,
        tasksupport=tasksupport,
        raw=rawfile,
        rawfiles=(rawfile,),
    )
    # A complete OutputContext: the Runner now injects artifact services, so a
    # partial double would hide the per-tile publication path from this test.
    out = OutputContext.from_resource_paths(resolve_tile_paths(data_root, 0))
    monkeypatch.setattr(
        "rdetoolkit.runner.planner.iterate_tiles",
        lambda *args, **kwargs: iter([(info, paths, out)]),
    )
    monkeypatch.setattr(
        "rdetoolkit.runner.planner._tile_invoice",
        lambda *args, **kwargs: TilePreparation(),
    )
    monkeypatch.setattr(
        "rdetoolkit.runner.invoker.run_tile",
        lambda *args, **kwargs: ExecutionResult(
            iteration_index=0,
            status="completed",
            call_records=(),
            outputs=(),
            datatile_id="source",
        ),
    )
    caller = root if cwd_relation == "same" else tmp_path / "caller"
    caller.mkdir(exist_ok=True)
    monkeypatch.chdir(caller)

    # When: the Runner prepares the run-level invoice source
    runner = Runner(
        root=root,
        inputdata_path=inputdata,
        unpacked_dir_path=unpacked,
        run_id_factory=lambda: f"backup-{layout}-{cwd_relation}-{mode.value}",
    )
    runner.run_id = f"backup-{layout}-{cwd_relation}-{mode.value}"
    report = runner.iterate(lambda: None, mode, RdeConfig())
    backup_path = data_root / "temp" / "invoice_org.json"

    # Then: the backup exists at the run root and contains the exact source JSON
    assert report.status == "success"
    assert backup_path.exists()
    assert json.loads(backup_path.read_text(encoding="utf-8")) == source


def test_backup_is_not_ingested_as_an_rdeformat_rawfile__tc_i6_1_ev_070(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-1-EV-070: the run-level backup never enters the RDEFormat rawfiles.

    v1 backs the invoice up after ``check_files`` (workflows.py), so
    ``data/temp/invoice_org.json`` does not exist while the RDEFormat checker
    globs ``data/temp/**``. With the v2 unpack root at ``data/temp`` the same
    ordering has to hold, otherwise the backup is registered as raw data.
    """
    # Given: the frozen RDEFormat fixture and the flow entry contract
    from rdetoolkit.core.flow import flow
    from rdetoolkit.types import InputPaths
    from tests.v2.contract.fixtures import _generate

    seen: list[tuple[Path, ...]] = []

    @flow
    def _capture(paths: InputPaths) -> None:
        seen.append(paths.rawfiles)

    root = tmp_path / "rdeformat"
    _generate.materialize_sut_case("rdeformat", root)
    monkeypatch.chdir(root)
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
    )

    # When: running with both raw destinations enabled
    report = runner.run(
        _capture,
        system={"extended_mode": "rdeformat", "save_raw": True, "save_nonshared_raw": True},
    )

    # Then: the backup exists, but no tile saw it and no raw copy contains it
    assert report.status == "success", report.error
    assert (root / "data" / "temp" / "invoice_org.json").exists()
    assert seen
    assert all("invoice_org.json" not in {path.name for path in rawfiles} for rawfiles in seen)
    assert not (root / "data" / "raw" / "invoice_org.json").exists()
    assert not (root / "data" / "nonshared_raw" / "invoice_org.json").exists()


def test_backup_is_written_even_without_tiles__tc_i6_1_ev_071(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-1-EV-071: an input set with no tiles still gets the v1 backup.

    v1 calls ``backup_invoice_json_files`` unconditionally after
    ``check_files``, so the deferral introduced for the RDEFormat glob must not
    turn the backup into something only tiles trigger.
    """
    # Given: a MultiDataTile root whose checker yields no tile at all
    from rdetoolkit.domain.invoice_service import InvoiceService
    from rdetoolkit.modes.protocol import PlanningContext
    from rdetoolkit.runner.planner import create_common_tiles

    data_root = tmp_path / "data"
    for name in ("inputdata", "invoice", "tasksupport", "temp"):
        (data_root / name).mkdir(parents=True)
    source = {"basic": {"dataName": "seed"}}
    (data_root / "invoice" / "invoice.json").write_text(json.dumps(source), encoding="utf-8")
    monkeypatch.setattr("rdetoolkit.runner.planner.iterate_tiles", lambda *args: iter(()))
    context = PlanningContext(
        root=tmp_path,
        inputdata_path=data_root / "inputdata",
        unpacked_dir_path=data_root / "temp",
        invoice_service=InvoiceService(),
        data_root=data_root,
    )

    # When: planning the run
    tiles = list(create_common_tiles(ModeKind.multidatatile, context))

    # Then: no tile is produced, and the backup exists with the source content
    assert tiles == []
    backup = data_root / "temp" / "invoice_org.json"
    assert json.loads(backup.read_text(encoding="utf-8")) == source
