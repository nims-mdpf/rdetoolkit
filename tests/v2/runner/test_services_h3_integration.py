"""Runner integration contracts for Phase H3 domain services.

Session I-REVIEW-A ruling #1 moved ownership of the run boundary: the Runner —
not the planner — opens and closes the invoice service, exactly once per run,
against the single data root it resolved before anything was created. The
planner used to call ``begin_run`` a second time with a *different* root
argument, which reset the run-owned SmartTable builder in the middle of
planning.

Equivalence partitions (EP):

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``RunPlanner.create`` | injected invoice service | the planner never opens the run | TC-H3-INT-001 |
| ``RunPlanner`` | invalid implicit global service | no process-wide cache clear | TC-H3-INT-002 |
| ``Runner.run`` | one run | ``begin_run``/``end_run`` called exactly once each | TC-H3-INT-004 |

Boundary values (BV):

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| ``RunPlanner.create`` | zero tiles (lazy plan) | the plan carries the resolved data root | TC-H3-INT-003 |
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.api.request import FlowTarget, RunRequest
from rdetoolkit.core.flow import flow
from rdetoolkit.domain.invoice_service import InvoiceService
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.planner import RunPlanner
from rdetoolkit.types import InputPaths, RdeConfig
from tests.v2.contract.fixtures import _generate


class _InvoiceServiceProbe:
    """Record the run boundary without touching invoice files."""

    def __init__(self) -> None:
        self.opened = 0

    def begin_run(self) -> None:
        self.opened += 1

    def invariant_invoice(self, mode: ModeKind, *, data_root: Path) -> None:
        return None

    def backup(self, mode: ModeKind, **kwargs: Any) -> Path:
        return Path(kwargs["data_root"]) / "invoice" / "invoice.json"

    def prepare_tile(self, mode: ModeKind, **kwargs: Any) -> None:
        return None


class _CountingInvoiceService(InvoiceService):
    """A real invoice service that counts its run-boundary calls."""

    def __init__(self) -> None:
        super().__init__()
        self.begun = 0
        self.ended = 0

    def begin_run(self) -> None:
        self.begun += 1
        super().begin_run()

    def end_run(self) -> None:
        self.ended += 1
        super().end_run()


@flow
def _noop_flow(paths: InputPaths) -> None:
    """Consume one tile without writing anything the Runner does not own."""
    assert paths.inputdata.is_dir()


def test_planner_does_not_own_the_run_boundary__tc_h3_int_001_003(
    tmp_path: Path,
) -> None:
    """TC-H3-INT-001/003: planning opens no run; it consumes the Runner's decisions."""
    # Given: a planner with an injected service and a root whose tiles stay lazy
    service = _InvoiceServiceProbe()
    planner = RunPlanner(
        inputdata_path=tmp_path / "inputdata",
        unpacked_dir_path=tmp_path / "temp",
        run_id_factory=lambda: "h3-run",
        invoice_service=service,
    )
    request = RunRequest(root=tmp_path, target=FlowTarget(function=lambda: None))

    # When: creating, but not enumerating, an execution plan
    plan = planner.create(request, config=RdeConfig(), mode=ModeKind.invoice, data_root=tmp_path)

    # Then: the plan carries the Runner's decisions and opened no second run
    assert plan.run_id == "h3-run"
    assert plan.data_root == tmp_path
    assert service.opened == 0


def test_runner_opens_and_closes_the_run_exactly_once__tc_h3_int_004(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-H3-INT-004: the Runner is the single owner of the run boundary."""
    # Given: a real invoice-mode case and a service recording its boundary calls
    root = tmp_path / "invoice"
    _generate.materialize_sut_case("invoice", root)
    monkeypatch.chdir(root)
    service = _CountingInvoiceService()
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
        invoice_service=service,
    )

    # When: executing one run
    report = runner.run(_noop_flow)

    # Then: the boundary is crossed exactly once in each direction
    assert report.status == "success", report.error
    assert service.begun == 1
    assert service.ended == 1
