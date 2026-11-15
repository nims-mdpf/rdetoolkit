"""Mode-specific artifact stage order (Session I-REVIEW-A, ruling #5 / review R3).

``InvoiceService.apply_config`` ran structured -> magic -> description for every
mode, and the mode seam was a ``frozenset`` — a set cannot express an order.
contracts.md claimed the difference was unobservable because the three steps
touch disjoint state. Review R3 falsified that: when the framework's own
magic-variable expansion fails, the *order* decides which artifacts a failed
tile leaves behind.

v1's pipelines (``processing/factories.py``):

* invoice / SmartTable: Thumbnail -> StructuredInvoiceSaver -> VariableApplier
  -> DescriptionUpdater
* MultiDataTile / ExcelInvoice: VariableApplier -> Thumbnail ->
  StructuredInvoiceSaver -> DescriptionUpdater
* RDEFormat: Thumbnail -> DescriptionUpdater (no structured export, no magic)

The v1 side of every failure cell is the frozen generator case
``<mode>/magicfail`` / ``<mode>/structfail`` (Session K1 ruling #6 item 9); until
K1 it was a live v1 run in a worker process. The scenario builders (magic
template injection, the structured-sabotaging callback) live in ``_generate.py``.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-IRA-5-EP-030 | handler order | 5 modes | the v1 stage sequence, ordered |
| TC-IRA-5-EP-031 | magic failure | multidatatile | frozen v1: no ``structured/invoice.json`` |
| TC-IRA-5-EP-032 | magic failure | excelinvoice | frozen v1: no ``structured/invoice.json`` |
| TC-IRA-5-EP-033 | magic failure | invoice | frozen v1: ``structured/invoice.json`` present |
| TC-IRA-5-EP-036 | structured failure | multidatatile | frozen v1: magic already expanded in the tile invoice |
| TC-IRA-5-EP-037 | structured failure | excelinvoice | frozen v1: magic already expanded in the tile invoice |
| TC-IRA-5-EP-038 | structured failure | invoice | frozen v1: magic never ran (structured comes first) |
| TC-MV-STAGE-001 | strict missing source | same 3 modes | code 4006 with the same mode-owned artifact order |
| TC-MV-STAGE-002 | strict structured failure | same 3 modes | explicit invoice source resolves before the later stage |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-IRA-5-EV-034 | API | ``modes.protocol`` | ``invoice_stage_steps`` is gone |
| TC-IRA-5-EV-035 | default | no provider | the invoice order is the default |
| TC-MV-STAGE-003 | grouped Excel filename | multiple raw inputs | code 4006 before invoice replacement or structured export |
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.api.request import ExecutionTarget, FlowTarget, LegacyCallbackTarget, RunRequest
from rdetoolkit.core.flow import flow
from rdetoolkit.fileops import readf_json, writef_json
from rdetoolkit.models.rde2types import RdeDatasetPaths
from rdetoolkit.runner.executor import artifact_stage_order
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths, OutputContext
from tests.v2.contract.fixtures import _generate
from tests.v2.contract.frozen import frozen_observed
from tests.v2.contract.observe import observe_v2_run

@flow
def _noop_flow(paths: InputPaths) -> None:
    """Succeed on every tile so only artifact publication can fail."""
    assert paths.inputdata.is_dir()


def _noop_callback(paths: RdeDatasetPaths) -> None:
    """Use the frozen callback entry without changing the registration inputs."""
    assert paths.inputdata.is_dir()


def _v2_overrides(mode: str) -> dict[str, Any]:
    extended_mode = {"multidatatile": "MultiDataTile", "rdeformat": "rdeformat"}.get(mode)
    return {
        "system": {
            "extended_mode": extended_mode or "invoice",
            "save_raw": True,
            "save_nonshared_raw": True,
            "save_thumbnail_image": False,
            "magic_variable": True,
            "save_invoice_to_structured": True,
        },
        "execution": {"on_iteration_error": "fail_fast"},
        "smarttable": {"save_table_file": False},
    }


def _structured_invoices(observation: dict[str, Any]) -> list[str]:
    """Return the ``structured/invoice.json`` exports of one observation's tree."""
    return [path for path in observation["output_tree"]["files"] if path.endswith("structured/invoice.json")]


def _invoice_data_names(observation: dict[str, Any]) -> dict[str, Any]:
    """Return ``basic.dataName`` per written tile invoice of one observation."""
    return {path: invoice["basic"]["dataName"] for path, invoice in observation["invoices"].items()}


def _observe_v2(case_id: str, root: Path, monkeypatch: pytest.MonkeyPatch, target: ExecutionTarget) -> dict[str, Any]:
    """Observe either entry contract through the same Runner and registered input."""
    case = _generate.oracle_case(case_id)
    _generate.materialize_case(case, root)
    original_owner = readf_json(root / "data" / "invoice" / "invoice.json")["basic"]["dataOwnerId"]
    monkeypatch.chdir(root)
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
    )
    report = runner.run(RunRequest(root=root, target=target, config_source=_v2_overrides(case.mode)))
    job_failed = root / "data" / "job.failed"
    return {
        "status": report.status,
        "error_code": (report.error or {}).get("code"),
        "original_owner": original_owner,
        "job_failed_code": (
            job_failed.read_text(encoding="utf-8").splitlines()[0] if job_failed.exists() else None
        ),
        **observe_v2_run(root),
    }


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        pytest.param(
            "invoice",
            ("thumbnail", "structured", "magic", "description"),
            id="TC-IRA-5-EP-030-invoice",
        ),
        pytest.param(
            "smarttable",
            ("thumbnail", "structured", "magic", "description"),
            id="TC-IRA-5-EP-030-smarttable",
        ),
        pytest.param(
            "multidatatile",
            ("magic", "thumbnail", "structured", "description"),
            id="TC-IRA-5-EP-030-multidatatile",
        ),
        pytest.param(
            "excelinvoice",
            ("magic", "thumbnail", "structured", "description"),
            id="TC-IRA-5-EP-030-excelinvoice",
        ),
        pytest.param(
            "rdeformat",
            ("thumbnail", "description"),
            id="TC-IRA-5-EP-030-rdeformat",
        ),
    ],
)
def test_stage_order_matches_the_v1_pipeline__tc_ira_5_ep_030(
    mode: str,
    expected: tuple[str, ...],
    tmp_path: Path,
) -> None:
    """TC-IRA-5-EP-030: each mode publishes its artifacts in v1's order."""
    # Given: a plan for one mode
    from rdetoolkit.modes.install import install_default_handlers  # noqa: PLC0415
    from rdetoolkit.runner.mode_resolver import ModeKind  # noqa: PLC0415
    from tests.v2.runner.stage_order_helpers import make_plan  # noqa: PLC0415

    install_default_handlers()
    plan = make_plan(ModeKind(mode), tmp_path)

    # When: asking the executor for this mode's artifact stage sequence
    actual = artifact_stage_order(plan)

    # Then: the sequence is v1's, in order
    assert actual == expected


@pytest.mark.parametrize(
    "mode",
    [
        pytest.param("multidatatile", id="TC-IRA-5-EP-031"),
        pytest.param("excelinvoice", id="TC-IRA-5-EP-032"),
        pytest.param("invoice", id="TC-IRA-5-EP-033"),
    ],
)
@pytest.mark.parametrize("entry", ["legacy", "strict-v2"])
def test_magic_failure_leaves_the_v1_artifacts__tc_ira_5_ep_031_032_033(
    mode: str,
    entry: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-IRA-5-EP-031/032/033, TC-MV-STAGE-001: failures retain stage order.

    This is review R3's counterexample. For MultiDataTile and ExcelInvoice v1
    expands the magic variable *first*, so the structured export never happens;
    for invoice mode the export precedes it and therefore survives.
    """
    # Given: v1's frozen run of the same input with an unresolvable magic variable
    expected = frozen_observed(f"v1/{mode}/magicfail")

    # When: the selected versioned entry executes the same missing-source case
    target = LegacyCallbackTarget(function=_noop_callback) if entry == "legacy" else FlowTarget(function=_noop_flow)
    actual = _observe_v2(f"v1/{mode}/magicfail", tmp_path / "v2", monkeypatch, target)

    # Then: each contract retains its error code and the frozen artifact ordering
    assert expected["job_failed_error_code"] is not None
    assert actual["status"] == "failed"
    if entry == "legacy":
        assert actual["job_failed_code"] == expected["job_failed_error_code"]
        assert actual["error_code"] == 1
    else:
        assert actual["job_failed_code"] == "ErrorCode=4006"
        assert actual["error_code"] == 4006
    assert _structured_invoices(actual) == _structured_invoices(expected)
    assert (mode == "invoice") is bool(_structured_invoices(expected))


#: The frozen callback selects the first raw file; strict flows instead use an
#: explicit invoice field so grouped Excel input cannot make the source ambiguous.
_FILENAME_TEMPLATE = _generate.FILENAME_TEMPLATE
_STRICT_TEMPLATE = "${invoice:basic:dataOwnerId}"


@flow
def _structured_sabotaging_flow(paths: InputPaths, out: OutputContext) -> None:
    """Use an unambiguous strict source, then sabotage the later structured stage."""
    assert paths.inputdata.is_dir()
    invoice_path = out.invoice / "invoice.json"
    invoice = readf_json(invoice_path)
    invoice["basic"]["dataName"] = _STRICT_TEMPLATE
    writef_json(invoice_path, invoice)
    shutil.rmtree(out.struct)
    out.struct.write_text("not a directory", encoding="utf-8")


def _structured_sabotaging_callback(paths: RdeDatasetPaths) -> None:
    """Reproduce the frozen v1 structured-directory failure unchanged."""
    shutil.rmtree(paths.struct)
    paths.struct.write_text("not a directory", encoding="utf-8")


@pytest.mark.parametrize(
    ("mode", "magic_completed"),
    [
        pytest.param("multidatatile", True, id="TC-IRA-5-EP-036"),
        pytest.param("excelinvoice", True, id="TC-IRA-5-EP-037"),
        pytest.param("invoice", False, id="TC-IRA-5-EP-038"),
    ],
)
@pytest.mark.parametrize("entry", ["legacy", "strict-v2"])
def test_structured_failure_after_magic_keeps_the_expanded_invoice__tc_ira_5_ep_036_037_038(
    mode: str,
    magic_completed: bool,
    entry: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-IRA-5-EP-036/037/038, TC-MV-STAGE-002: later failure retains expansion.

    Review R3's required test, the other direction: when the *structured*
    export fails, the tile invoice must already carry the expanded magic
    variable for MultiDataTile / ExcelInvoice (magic runs first there), and
    must still carry the raw template for invoice mode (structured runs first).
    The run fails either way; v1 and v2 attribute the framework error with
    different catalog codes by contract, so only the presence of ``job.failed``
    is compared.
    """
    # Given: v1's frozen run with a callback that sabotages the structured directory
    expected = frozen_observed(f"v1/{mode}/structfail")

    # When: either entry sabotages the structured directory after its invocation
    target = LegacyCallbackTarget(function=_structured_sabotaging_callback) if entry == "legacy" else FlowTarget(function=_structured_sabotaging_flow)
    actual = _observe_v2(f"v1/{mode}/structfail", tmp_path / "v2", monkeypatch, target)

    # Then: both runs failed and left the same invoices, structured export absent
    assert expected["exit_code"] == 1
    assert expected["job_failed_text"] is not None
    assert actual["status"] == "failed"
    assert actual["job_failed_code"] is not None
    assert actual["error_code"] == 3006
    assert _structured_invoices(actual) == _structured_invoices(expected) == []
    if entry == "legacy":
        assert _invoice_data_names(actual) == _invoice_data_names(expected)

    # And: whether magic completed before the failure is exactly v1's order
    data_names = set(_invoice_data_names(actual).values())
    assert data_names
    template = _FILENAME_TEMPLATE if entry == "legacy" else _STRICT_TEMPLATE
    if magic_completed:
        assert template not in data_names
        if entry == "strict-v2":
            assert data_names == {actual["original_owner"]}
    else:
        assert data_names == {template}


def test_strict_grouped_filename_fails_before_publication__tc_mv_stage_003(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-MV-STAGE-003: strict Excel filename cannot select an implicit first file."""
    # Given: the frozen Excel case requests filename for a group with several inputs
    target = FlowTarget(function=_noop_flow)
    # When: the successful flow reaches the strict magic stage
    actual = _observe_v2("v1/excelinvoice/structfail", tmp_path / "strict", monkeypatch, target)
    # Then: source ambiguity fails before either invoice replacement or structured export
    assert actual["status"] == "failed"
    assert actual["error_code"] == 4006
    assert actual["job_failed_code"] == "ErrorCode=4006"
    assert _structured_invoices(actual) == []
    assert set(_invoice_data_names(actual).values()) == {_FILENAME_TEMPLATE}


def test_frozenset_seam_is_gone__tc_ira_5_ev_034() -> None:
    """TC-IRA-5-EV-034: the order-blind seam has no successor."""
    # Given / When: the mode protocol module
    import rdetoolkit.modes.protocol as module  # noqa: PLC0415

    # Then: nothing can express artifact selection without an order again
    assert not hasattr(module, "InvoiceStageProvider")
    assert not hasattr(module.ModeHandler, "invoice_stage_steps")


def test_default_order_is_the_invoice_pipeline__tc_ira_5_ev_035(tmp_path: Path) -> None:
    """TC-IRA-5-EV-035: a handler without the capability gets the v1 invoice order."""
    # Given: a plan for a mode with no registered handler
    from rdetoolkit.modes.registry import clear  # noqa: PLC0415
    from rdetoolkit.runner.mode_resolver import ModeKind  # noqa: PLC0415
    from tests.v2.runner.stage_order_helpers import make_plan  # noqa: PLC0415

    clear()
    plan = make_plan(ModeKind.invoice, tmp_path)

    # When / Then: the default sequence is the v1 invoice pipeline's
    assert artifact_stage_order(plan) == ("thumbnail", "structured", "magic", "description")
