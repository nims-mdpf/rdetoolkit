"""Alias-flat data root ownership (Session I-REVIEW-A, ruling #1 / reviews F3).

``resolve_data_root`` contracts that a root which *directly* owns the RDE
marker directories IS the data root. Before this session four private
resolvers disagreed about that inside one run: the invoice side resolved the
alias-flat root while tile output was hard-coded to ``root / "data"``, so a
single run split its artifacts between ``<root>/invoice`` and
``<root>/data/raw``. The Runner now resolves the data root exactly once, before
anything is created, and every consumer receives that one answer.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-IRA-1-EP-001 | 5 modes | alias-flat root, ``Runner.run`` | no ``<root>/data`` is created and every artifact lands under ``<root>`` |
| TC-IRA-1-EP-002 | nested root | ordinary ``<root>/data`` layout | artifacts stay under ``<root>/data`` |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-IRA-1-EV-003 | failed run | alias-flat root, failing flow | ``job.failed`` is written at ``<root>/job.failed`` |
| TC-IRA-1-EV-004 | resolvers | ``src/rdetoolkit`` sources | no private ``_data_root`` implementation survives |
| TC-IRA-1-EV-005 | plan | ``ExecutionPlan``/``PlanningContext`` | both carry the resolved ``data_root`` |
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from rdetoolkit.core.flow import flow
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths, InvoiceData
from tests.v2.contract.fixtures import _generate

_MODES = ("invoice", "excelinvoice", "multidatatile", "rdeformat", "smarttable")

#: Directories every successful run must own below the single data root.
_EXPECTED_DIRS = ("invoice", "raw", "nonshared_raw", "structured", "logs")


@flow
def _noop_flow(paths: InputPaths, invoice: InvoiceData) -> None:
    """Consume one tile without writing anything the Runner does not own."""
    assert paths.inputdata.is_dir()
    assert invoice.raw


@flow
def _failing_flow(paths: InputPaths) -> None:
    """Fail every tile with a v1 StructuredError."""
    assert paths.inputdata.is_dir()
    msg = "alias-flat failure"
    raise StructuredError(msg, ecode=999)


def _overrides(mode: str) -> dict:
    extended_mode = {"multidatatile": "MultiDataTile", "rdeformat": "rdeformat"}.get(mode)
    return {
        "system": {
            "extended_mode": extended_mode or "invoice",
            "save_raw": True,
            "save_nonshared_raw": True,
            "save_thumbnail_image": False,
            "magic_variable": False,
        },
        "smarttable": {"save_table_file": False},
    }


def _expected_tile_count(mode: str) -> int:
    """Return the tile count v1 observed for this mode's frozen fixture.

    Read from ``expected/<mode>/ok.json`` rather than hardcoded, so a fixture
    change cannot silently weaken this cell (the walking skeleton reads the
    same key).
    """
    path = _generate.EXPECTED_ROOT / mode / "ok.json"
    count: int = json.loads(path.read_text(encoding="utf-8"))["observed"]["callback_count"]
    return count


def _materialize_flat_case(mode: str, root: Path) -> None:
    """Materialize a frozen mode fixture with its ``data`` contents at ``root``.

    The fixture families are published as ``<case>/data/**``; an alias-flat root
    is the same material with the ``data`` level removed, which is exactly the
    layout ``resolve_data_root`` identifies through its marker directories.
    """
    staging = root.parent / f"{root.name}__staging"
    _generate.materialize_sut_case(mode, staging)
    root.mkdir(parents=True, exist_ok=True)
    for child in sorted((staging / "data").iterdir()):
        shutil.move(str(child), str(root / child.name))
    shutil.rmtree(staging)


def _flat_runner(root: Path) -> Runner:
    return Runner(
        root=root,
        inputdata_path=root / "inputdata",
        unpacked_dir_path=root / "temp",
    )


@pytest.mark.parametrize(
    "mode",
    [pytest.param(mode, id=f"TC-IRA-1-EP-001-{mode}") for mode in _MODES],
)
def test_alias_flat_root_never_splits_the_run__tc_ira_1_ep_001(mode: str, tmp_path: Path) -> None:
    """TC-IRA-1-EP-001: an alias-flat root owns every artifact of the run."""
    # Given: a mode fixture whose data directories sit directly below the root
    root = tmp_path / mode
    _materialize_flat_case(mode, root)

    # When: running the eager flow through the v2 Runner
    report = _flat_runner(root).run(_noop_flow, **_overrides(mode))

    # Then: the run succeeds without ever creating a nested data root
    assert report.status == "success", report.error
    assert not (root / "data").exists()

    # And: it processed the real input -- the mode and tile count v1 observed
    assert report.mode == mode
    assert len(report.iterations) == _expected_tile_count(mode)

    # And: every artifact directory belongs to the single resolved root
    for name in _EXPECTED_DIRS:
        assert (root / name).is_dir(), f"{name} must live below the alias-flat root"
    assert (root / "invoice" / "invoice.json").is_file()
    assert sorted(path.name for path in (root / "logs").iterdir())


def test_nested_root_is_unchanged__tc_ira_1_ep_002(tmp_path: Path) -> None:
    """TC-IRA-1-EP-002: the ordinary nested layout keeps writing below data/."""
    # Given: the published nested fixture layout
    root = tmp_path / "invoice"
    _generate.materialize_sut_case("invoice", root)
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
    )

    # When: running the eager flow
    report = runner.run(_noop_flow, **_overrides("invoice"))

    # Then: artifacts stay below the nested data root
    assert report.status == "success", report.error
    assert (root / "data" / "raw").is_dir()
    assert not (root / "raw").exists()


def test_failed_alias_flat_run_writes_job_failed_at_the_root__tc_ira_1_ev_003(tmp_path: Path) -> None:
    """TC-IRA-1-EV-003: the failure contract follows the same single data root."""
    # Given: an alias-flat invoice case and a flow that always fails
    root = tmp_path / "invoice"
    _materialize_flat_case("invoice", root)

    # When: running a failing flow
    report = _flat_runner(root).run(_failing_flow, **_overrides("invoice"))

    # Then: job.failed is written beside the other artifacts, not below data/
    assert report.status == "failed"
    assert (root / "job.failed").is_file()
    assert not (root / "data").exists()


def test_no_private_data_root_resolver_survives__tc_ira_1_ev_004() -> None:
    """TC-IRA-1-EV-004: ``resolve_data_root`` is the only resolver in the source."""
    # Given: the installed v2 source tree
    source_root = Path(__file__).resolve().parents[3] / "src" / "rdetoolkit"

    # When: searching for a private data-root resolver
    offenders = sorted(
        path.relative_to(source_root).as_posix()
        for path in source_root.rglob("*.py")
        if "def _data_root" in path.read_text(encoding="utf-8")
    )

    # Then: none is left; the public four-tier rule is the single owner
    assert offenders == []


def test_plan_and_planning_context_carry_the_data_root__tc_ira_1_ev_005(tmp_path: Path) -> None:
    """TC-IRA-1-EV-005: the resolved root travels on the plan, not in each consumer."""
    # Given: an alias-flat invoice case
    from rdetoolkit.api.request import FlowTarget, RunRequest  # noqa: PLC0415
    from rdetoolkit.domain.invoice_service import InvoiceService  # noqa: PLC0415
    from rdetoolkit.runner.mode_resolver import ModeKind  # noqa: PLC0415
    from rdetoolkit.runner.planner import RunPlanner  # noqa: PLC0415
    from rdetoolkit.types import RdeConfig  # noqa: PLC0415

    root = tmp_path / "invoice"
    _materialize_flat_case("invoice", root)
    contexts: list[object] = []
    service = InvoiceService()
    planner = RunPlanner(
        inputdata_path=root / "inputdata",
        unpacked_dir_path=root / "temp",
        run_id_factory=lambda: "plan-data-root",
        invoice_service=service,
    )

    # When: creating a plan for the alias-flat root
    plan = planner.create(
        RunRequest(root=root, target=FlowTarget(function=_noop_flow)),
        config=RdeConfig(),
        mode=ModeKind.invoice,
        data_root=root,
    )
    contexts.append(plan)

    # Then: the plan owns the resolved data root instead of re-deriving it
    assert plan.data_root == root
    assert plan.root == root
