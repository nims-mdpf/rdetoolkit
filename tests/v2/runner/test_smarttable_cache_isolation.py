"""Regression tests for run-scoped SmartTable base-invoice caching.

Equivalence partitions (EP):

| API | Partition | Rationale | Expected | Test ID |
| --- | --- | --- | --- | --- |
| ``Runner.run`` | same source path, changed content | stale process cache | second run uses changed content | TC-G0-CACHE-001 |

Boundary values (BV):

| API | Boundary | Rationale | Expected | Test ID |
| --- | --- | --- | --- | --- |
| ``Runner.run`` | two consecutive runs | minimum cross-run sequence | cache is isolated at run boundary | TC-G0-CACHE-001 |

NOTE (2026-07-15): reconstructed from the surviving pytest ``.pyc`` after the
original working tree was wiped before commit (see session_g0.md). Semantics,
test ids and assertions are preserved from the verified original.

UPDATE (2026-09-07, Session I6-C): the base invoice is now owned by the run's
``InvoiceService`` instead of a v1 process-global class cache, so this file no
longer imports the v1 processor and no longer needs a cache-clearing fixture.
The asserted property is unchanged and the probe was strengthened: it prepares
the tile through ``InvoiceService.prepare_tile`` — the production call site —
rather than calling the builder helper directly, so the run boundary
(``begin_run``/``end_run``) is part of the subject under test.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rdetoolkit.domain.invoice_service import InvoiceService
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import InputPaths, RdeConfig

_OWNER_ID = "0" * 56

_INVOICE_SCHEMA: dict[str, Any] = {
    "required": ["sample"],
    "properties": {
        "sample": {
            "type": "object",
            "label": {"ja": "サンプル", "en": "Sample"},
            "properties": {},
        },
    },
}


class _SmartTableProbeRunner(Runner):
    """Run the real SmartTable invoice builder through the Runner boundary."""

    def __init__(self, *, root: Path) -> None:
        # The service is held explicitly so the probe drives the production
        # call site instead of reaching into the Runner's private collaborator.
        self.service = InvoiceService()
        super().__init__(root=root, invoice_service=self.service)

    def load_config(self, overrides: dict[str, Any] | None = None) -> RdeConfig:
        return RdeConfig()

    def resolve_mode(self, config: RdeConfig) -> ModeKind:
        return ModeKind.smarttable

    def pre_validate(self, config: RdeConfig) -> None:
        return None

    def iterate(
        self,
        flow_fn: Callable[..., Any],
        mode: ModeKind,
        config: RdeConfig,
    ) -> RunReport:
        data_root = self.root / "data"
        rowfile = data_root / "inputdata" / "fsmarttable_row_0.csv"
        self.service.prepare_tile(
            ModeKind.smarttable,
            paths=InputPaths(
                inputdata=data_root / "inputdata",
                invoice=data_root / "invoice",
                tasksupport=data_root / "tasksupport",
                rawfiles=(rowfile,),
            ),
            invoice_dir=data_root / "output" / "invoice",
            iteration_index=0,
            invariant_invoice=None,
            invoice_source=data_root / "invoice" / "invoice.json",
        )
        return RunReport(
            run_id=self.run_id,
            status="success",
            flow_id="tests.smarttable_probe",
            mode=mode.value,
            started_at="2026-07-15T00:00:00",
            duration_ms=0.0,
            config_digest="sha256:test",
            iterations=[],
            warnings=[],
        )

    def post_validate(self, config: RdeConfig, report: RunReport) -> None:
        return None

    def finalize(self, report: RunReport, config: RdeConfig) -> None:
        return None


def _write_source_invoice(path: Path, data_name: str) -> None:
    payload = {
        "datasetId": "seed-dataset",
        "basic": {
            "dateSubmitted": "2026-07-15",
            "dataOwnerId": _OWNER_ID,
            "dataName": data_name,
        },
        "sample": {"sampleId": "00000000-0000-0000-0000-000000000001"},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_changed_base_invoice_is_reloaded_on_second_run__tc_g0_cache_001(
    tmp_path: Path,
) -> None:
    """TC-G0-CACHE-001: each run reads a fresh SmartTable base invoice."""
    # Given: a data tree whose base invoice.json changes between two runs
    data_root = tmp_path / "data"
    (data_root / "inputdata").mkdir(parents=True)
    (data_root / "invoice").mkdir()
    (data_root / "tasksupport").mkdir()
    row_path = data_root / "inputdata" / "fsmarttable_row_0.csv"
    row_path.write_text("basic/dateSubmitted\n2026-07-15\n", encoding="utf-8")
    (data_root / "tasksupport" / "invoice.schema.json").write_text(
        json.dumps(_INVOICE_SCHEMA),
        encoding="utf-8",
    )

    source_path = data_root / "invoice" / "invoice.json"
    _write_source_invoice(source_path, "first-run")

    # When: two consecutive same-process runs read the same source path
    first_report = _SmartTableProbeRunner(root=tmp_path).run(lambda: None)
    _write_source_invoice(source_path, "second-run")
    second_report = _SmartTableProbeRunner(root=tmp_path).run(lambda: None)
    generated = json.loads(
        (data_root / "output" / "invoice" / "invoice.json").read_text(encoding="utf-8"),
    )

    # Then: the second run must observe the changed base invoice, not a stale
    # process-global cache entry left behind by the first run.
    assert first_report.status == "success"
    assert second_report.status == "success"
    assert generated["basic"]["dataName"] == "second-run"

    # And: one Runner reused for two runs reloads at the run boundary too,
    # which is the property the removed process-wide cache eviction provided.
    reused = _SmartTableProbeRunner(root=tmp_path)
    assert reused.run(lambda: None).status == "success"
    _write_source_invoice(source_path, "third-run")
    assert reused.run(lambda: None).status == "success"
    reloaded = json.loads(
        (data_root / "output" / "invoice" / "invoice.json").read_text(encoding="utf-8"),
    )
    assert reloaded["basic"]["dataName"] == "third-run"
