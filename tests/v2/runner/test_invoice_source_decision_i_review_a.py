"""One run, one invoice source (Session I-REVIEW-A, ruling #3 / review R2).

``resolve_invoice_source`` picked the run's ``invoice_org`` from the *presence*
of ``data/temp/invoice_org.json``. A backup left behind by an earlier run on
the same root therefore became the source of the next run: the structured
export, the ``${invoice:...}`` magic variables and the v1 callback's
``invoice_org`` all pointed at a stale invoice, and the run still succeeded.

v1 never asks the filesystem. ``invoicefile._description.backup_invoice_json_files``
decides from the mode alone — ExcelInvoice / MultiDataTile / RDEFormat read the
backup, invoice / SmartTable read ``data/invoice/invoice.json`` — so the planner
now decides once and publishes the answer on ``ExecutionPlan.invoice_source``.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-IRA-3-EP-010 | mode rule | 5 modes | the v1 ``backup_invoice_json_files`` selection |
| TC-IRA-3-EP-011 | plan | invoice mode with a stale backup | ``plan.invoice_source`` is the current invoice |
| TC-IRA-3-EP-012 | plan | multidatatile | ``plan.invoice_source`` is the backup |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-IRA-3-EV-013 | structured export | invoice mode + stale backup | ``structured/invoice.json`` is the current invoice |
| TC-IRA-3-EV-014 | magic variable | ``${invoice:basic:dataOwnerId}`` + stale backup | resolves from the current invoice |
| TC-IRA-3-EV-015 | v1 callback | stale backup | ``invoice_org`` is the current invoice |
| TC-IRA-3-EV-016 | API | ``domain.invoice_service`` | ``resolve_invoice_source`` no longer exists |
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.api.request import FlowTarget, LegacyCallbackTarget, RunRequest
from rdetoolkit.core.flow import flow
from rdetoolkit.domain.invoice_service import InvoiceService, invoice_source_for
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.planner import RunPlanner
from rdetoolkit.types import InputPaths, InvoiceData, RdeConfig
from tests.v2.contract.fixtures import _generate

#: Owner ids are the discriminator: they are schema-valid 56-character strings,
#: and ``${invoice:basic:dataOwnerId}`` resolves them from whichever invoice the
#: run selected as its ``invoice_org``.
_STALE = "0" * 55 + "9"
_CURRENT = "0" * 55 + "1"


@flow
def _noop_flow(paths: InputPaths, invoice: InvoiceData) -> None:
    """Consume one tile without writing anything the Runner does not own."""
    assert paths.inputdata.is_dir()
    assert invoice.raw


def _seed_invoice(marker: str) -> dict[str, Any]:
    return {
        "datasetId": "stale-backup-fixture",
        "basic": {
            "dateSubmitted": "2026-09-14",
            "dataOwnerId": marker,
            "dataName": "${invoice:basic:dataOwnerId}",
        },
    }


def _prepare_invoice_case_with_stale_backup(tmp_path: Path) -> Path:
    """Materialize an invoice case whose ``temp/`` still holds an old backup."""
    root = tmp_path / "invoice"
    _generate.materialize_sut_case("invoice", root)
    data_root = root / "data"
    (data_root / "invoice" / "invoice.json").write_text(
        json.dumps(_seed_invoice(_CURRENT)),
        encoding="utf-8",
    )
    backup = data_root / "temp" / "invoice_org.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(json.dumps(_seed_invoice(_STALE)), encoding="utf-8")
    return root


def _overrides() -> dict[str, Any]:
    return {
        "system": {
            "extended_mode": "invoice",
            "save_raw": True,
            "save_nonshared_raw": True,
            "save_thumbnail_image": False,
            "magic_variable": True,
            "save_invoice_to_structured": True,
        },
    }


@pytest.mark.parametrize(
    ("mode", "expected_relative"),
    [
        pytest.param(ModeKind.invoice, "invoice/invoice.json", id="TC-IRA-3-EP-010-invoice"),
        pytest.param(ModeKind.smarttable, "invoice/invoice.json", id="TC-IRA-3-EP-010-smarttable"),
        pytest.param(ModeKind.excelinvoice, "temp/invoice_org.json", id="TC-IRA-3-EP-010-excelinvoice"),
        pytest.param(ModeKind.multidatatile, "temp/invoice_org.json", id="TC-IRA-3-EP-010-multidatatile"),
        pytest.param(ModeKind.rdeformat, "temp/invoice_org.json", id="TC-IRA-3-EP-010-rdeformat"),
    ],
)
def test_invoice_source_follows_the_v1_mode_rule__tc_ira_3_ep_010(
    mode: ModeKind,
    expected_relative: str,
    tmp_path: Path,
) -> None:
    """TC-IRA-3-EP-010: the selection is the v1 mode branch, not a file probe."""
    # Given: a data root that holds neither file yet
    data_root = tmp_path / "data"

    # When: asking for this mode's run-level invoice source
    actual = invoice_source_for(mode, data_root=data_root)

    # Then: the answer is v1's, and it does not depend on what exists on disk
    assert actual == data_root / expected_relative


def test_plan_ignores_a_stale_backup_in_invoice_mode__tc_ira_3_ep_011(tmp_path: Path) -> None:
    """TC-IRA-3-EP-011: a leftover backup never becomes an invoice-mode source."""
    # Given: an invoice case with a stale backup from a previous run
    root = _prepare_invoice_case_with_stale_backup(tmp_path)
    data_root = root / "data"
    planner = RunPlanner(
        inputdata_path=data_root / "inputdata",
        unpacked_dir_path=data_root / "temp",
        run_id_factory=lambda: "stale-backup",
        invoice_service=InvoiceService(),
    )

    # When: planning an invoice-mode run
    plan = planner.create(
        RunRequest(root=root, target=FlowTarget(function=_noop_flow)),
        config=RdeConfig(),
        mode=ModeKind.invoice,
        data_root=data_root,
    )

    # Then: the run-level source is this run's invoice, not the leftover
    assert plan.invoice_source == data_root / "invoice" / "invoice.json"


def test_plan_selects_the_backup_for_multidatatile__tc_ira_3_ep_012(tmp_path: Path) -> None:
    """TC-IRA-3-EP-012: backup modes still read the backup, as v1 does."""
    # Given: a MultiDataTile case
    root = tmp_path / "multidatatile"
    _generate.materialize_sut_case("multidatatile", root)
    data_root = root / "data"
    planner = RunPlanner(
        inputdata_path=data_root / "inputdata",
        unpacked_dir_path=data_root / "temp",
        run_id_factory=lambda: "mdt-backup",
        invoice_service=InvoiceService(),
    )

    # When: planning a MultiDataTile run
    plan = planner.create(
        RunRequest(root=root, target=FlowTarget(function=_noop_flow)),
        config=RdeConfig(),
        mode=ModeKind.multidatatile,
        data_root=data_root,
    )

    # Then: the backup is the run-level source
    assert plan.invoice_source == data_root / "temp" / "invoice_org.json"


def test_structured_export_and_magic_ignore_the_stale_backup__tc_ira_3_ev_013_014(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-IRA-3-EV-013/014: no artifact of this run may carry the old invoice."""
    # Given: an invoice case whose temp/ still holds the previous run's backup
    root = _prepare_invoice_case_with_stale_backup(tmp_path)
    data_root = root / "data"
    monkeypatch.chdir(root)
    runner = Runner(
        root=root,
        inputdata_path=data_root / "inputdata",
        unpacked_dir_path=data_root / "temp",
    )

    # When: running the flow with the structured export and magic variable on
    report = runner.run(_noop_flow, **_overrides())

    # Then: the structured export is this run's invoice, not the leftover
    assert report.status == "success", report.error
    structured = json.loads((data_root / "structured" / "invoice.json").read_text(encoding="utf-8"))
    assert structured["basic"]["dataOwnerId"] == _CURRENT

    # And: the magic variable resolved against this run's invoice
    tile_invoice = json.loads((data_root / "invoice" / "invoice.json").read_text(encoding="utf-8"))
    assert tile_invoice["basic"]["dataName"] == _CURRENT


def test_v1_callback_receives_this_runs_invoice_org__tc_ira_3_ev_015(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-IRA-3-EV-015: the v1 callback adapter uses the plan's decision."""
    # Given: an invoice case with a stale backup and a recording v1 callback
    root = _prepare_invoice_case_with_stale_backup(tmp_path)
    data_root = root / "data"
    monkeypatch.chdir(root)
    seen: list[Path] = []

    def _callback(srcpaths: Any, resource_paths: Any) -> None:
        del srcpaths
        seen.append(resource_paths.invoice_org)

    runner = Runner(
        root=root,
        inputdata_path=data_root / "inputdata",
        unpacked_dir_path=data_root / "temp",
    )

    # When: running the legacy callback entry point
    report = runner.run(
        RunRequest(
            root=root,
            target=LegacyCallbackTarget(function=_callback),
            config_source=_overrides(),
        ),
    )

    # Then: the callback saw this run's invoice, never the leftover backup
    assert report.status == "success", report.error
    assert seen == [data_root / "invoice" / "invoice.json"]


def test_filesystem_probing_resolver_is_gone__tc_ira_3_ev_016() -> None:
    """TC-IRA-3-EV-016: the presence-based resolver has no successor."""
    # Given / When: the invoice service module
    import rdetoolkit.domain.invoice_service as module  # noqa: PLC0415

    # Then: nothing can re-decide the source from what happens to exist
    assert not hasattr(module, "resolve_invoice_source")
