"""Unified callback/flow compatibility matrix for ADR-023.

EP table:
    TC-UM-*-CB-OK: v1 callback SUT succeeds and matches its frozen observation.
    TC-UM-*-CB-USERERR: callback StructuredError exits with frozen job.failed.
    TC-UM-*-CB-VALERR: invalid invoice exits with frozen validation artifact.
    TC-UM-*-FLOW-OK: eager v2 Runner succeeds against the same static input.
        For the modes listed in ``_FULL_PARITY_MODES`` this compares the full
        frozen artifact observation (output tree minus data/logs/ contents, raw
        digests, and written invoices) through tests/v2/contract/observe.py.
    TC-UM-*-CANARY-FLOW-OK: the same full parity comparison against the frozen
        observation of imported real RDE material (expected/canary/), which
        covers artifacts the synthetic inputs never produce, thumbnails
        included. Modes are enabled through ``_CANARY_FLOW_MODES``.
    TC-UM-*-FLOW-USERERR/VALERR: v2 flow errors follow the I6-0 translation
        table (tests/v2/contract/flow_error_table.py, contracts.md §I6-0).
    TC-UM-*-CB-V2-OK/USERERR/VALERR: the same three outcomes with the **unified
        Runner** as the SUT — ``Runner.run(RunRequest(target=
        LegacyCallbackTarget(...)))`` driving ``LegacyCallbackInvoker`` — still
        compared with the frozen v1 observation (Session I-REVIEW-B, review F5).
        The CB cells above deliberately stay v1-versus-v1 pins.
    TC-UM-*-CB-OBS: callback Events/Provenance/RunReport columns are Phase J xfails.

BV table:
    TC-UM-XLS/MDT/SMT-FLOW-FAIL-FAST: a three-tile family whose tile 1 raises
        StructuredError(999); compared with a live v1 oracle (v1's default
        ``ignore_errors=False`` is fail-fast) on tree, raw, artifact content,
        invoices and job.failed.
    TC-UM-MDT-FLOW-CONTINUE-PARTIAL: same family with
        ``multidata_tile.ignore_errors=true``, the only continue policy v1 has;
        compared with a live v1 oracle.
    TC-UM-XLS/SMT-FLOW-CONTINUE-PARTIAL: v2-only contract — v1 re-raises from
        these modes, so there is no oracle (contracts.md §I-REVIEW-B).
    TC-UM-MDT-FLOW-SIGTERM: representative termination flush contract xfail.

All expected callback values are static JSON produced by ``_generate.py`` at
the ``source.commit`` recorded in each snapshot. The tests execute v1 only as
the SUT; they never create an expected value at test time.
"""

from __future__ import annotations

import json
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from rdetoolkit.api.request import FlowTarget, LegacyCallbackTarget, RunRequest
from rdetoolkit.compat.v1.callback import accepts_unified_argument
from rdetoolkit.core.flow import flow
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths, InvoiceData, IterationInfo
from tests.v2.contract.fixtures import _generate
from tests.v2.contract.observe import observe_v2_run, parity_pair, parity_view, pending_freeze_view
from tests.v2.contract.flow_error_table import (
    FAILED_EXIT_CODE,
    VALIDATION_REASON,
    MessageRule,
    expected_cb_v2_iteration_count,
    expected_divided_indices,
    expected_iteration_count,
    flow_error_cell,
)

_MODES = ("invoice", "excelinvoice", "multidatatile", "rdeformat", "smarttable")
_MODE_IDS = {
    "invoice": "INV",
    "excelinvoice": "XLS",
    "multidatatile": "MDT",
    "rdeformat": "RDF",
    "smarttable": "SMT",
}
_FLOW_INVOICES: list[dict] = []
#: Modes whose FLOW-OK cell compares the complete frozen artifact observation.
#: Session I6-1 proves the shared Core wiring with invoice and multidatatile;
#: excelinvoice and smarttable were measured to match exactly once that wiring
#: existed, and are pinned here so I6-A/B/C cannot regress them silently.
#: Session I6-A added rdeformat once its component-dispatching copy semantics
#: (``RDEFormatFileCopier``) were ported into ``modes/rdeformat.py``, so all
#: five modes now compare the complete observation.
_FULL_PARITY_MODES = frozenset({"invoice", "multidatatile", "excelinvoice", "smarttable", "rdeformat"})

#: Modes whose real-canary FLOW cell is proven against ``expected/canary/``.
#: The cell body below is mode-agnostic, so a session that finishes its mode
#: adds exactly one entry here (I6-A: invoice + rdeformat; I6-B: excelinvoice +
#: multidatatile, both already matching without any mode-handler change;
#: I6-C: smarttable, whose tile invoices are now built by the ported v2 builder
#: in ``modes/smarttable.py``).
_CANARY_FLOW_MODES = ("excelinvoice", "invoice", "multidatatile", "rdeformat", "smarttable")


@flow
def _contract_noop_flow(paths: InputPaths, invoice: InvoiceData) -> None:
    """Exercise flow-boundary injection without changing v1-owned artifacts."""
    assert paths.inputdata.is_dir()
    _FLOW_INVOICES.append(deepcopy(invoice.raw))


# Byte-identical to fixtures/_generate.py::_oracle_callback_usererr so the v2
# flow entry raises exactly what the frozen v1 observation recorded.
_USERERR_MESSAGE = (
    "Contract callback failed. Remediation: inspect the fixture callback "
    "and correct its input."
)


@flow
def _contract_usererr_flow(paths: InputPaths, invoice: InvoiceData) -> None:
    """Fail the tile the way the frozen v1 callback oracle fails."""
    assert paths.inputdata.is_dir()
    _FLOW_INVOICES.append(deepcopy(invoice.raw))
    raise StructuredError(_USERERR_MESSAGE, ecode=999)


def _frozen(mode: str, outcome: str) -> dict:
    path = _generate.EXPECTED_ROOT / mode / f"{outcome}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _v2_overrides(mode: str) -> dict:
    """Return the v2 config that reproduces the frozen v1 observation.

    The frozen snapshots were generated by ``_generate.oracle_config``; the
    Runner therefore has to receive the same five artifact switches, otherwise
    a tree comparison would measure a configuration difference instead of an
    implementation difference (ruling #8).
    """
    extended_mode = {
        "multidatatile": "MultiDataTile",
        "rdeformat": "rdeformat",
    }.get(mode)
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


def _expected_invoice_sequence(invoices: dict[str, object]) -> list[object]:
    def _tile_index(path: str) -> int:
        if path == "data/invoice/invoice.json":
            return 0
        return int(Path(path).parts[2]) + 1

    return [value for path, value in sorted(invoices.items(), key=lambda item: _tile_index(item[0]))]


@pytest.mark.parametrize(
    ("mode", "outcome"),
    [
        pytest.param(mode, outcome, id=f"TC-UM-{_MODE_IDS[mode]}-CB-{outcome.upper()}")
        for mode in _MODES
        for outcome in ("ok", "usererr", "valerr")
    ],
)
def test_callback_entry_matches_frozen_v1_contract(mode: str, outcome: str) -> None:
    """Callback matrix cells compare the v1 SUT with static generated expectations."""
    # Given: the immutable snapshot generated from v1 at its recorded source.commit
    expected = _frozen(mode, outcome)["observed"]

    # When: executing the same v1 path as the subject under test in isolation
    actual = _generate.run_v1_sut(mode, outcome)

    # Then: all frozen artifacts and legacy return fields remain compatible.
    # ``artifact_sha256`` is observed but not yet frozen (ruling #1 ritual step
    # (a)); it starts being compared the moment the re-freeze lands.
    assert pending_freeze_view(actual, expected) == expected
    if outcome == "ok":
        assert actual["exit_code"] == 0
        assert actual["callback_count"] >= 1
        assert actual["job_failed_error_code"] is None
    else:
        assert actual["exit_code"] == 1
        assert actual["job_failed_error_code"].startswith("ErrorCode=")


@pytest.mark.parametrize(
    "mode",
    [pytest.param(mode, id=f"TC-UM-{_MODE_IDS[mode]}-FLOW-OK") for mode in _MODES],
)
def test_flow_entry_success_matches_frozen_v1_primary_contract(
    mode: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flow OK cells preserve tile counts and invoice values from frozen v1 output.

    For the modes in ``_FULL_PARITY_MODES`` the comparison is the complete
    artifact observation (output tree, raw digests, written invoices), which is
    what Session I6-1 proves; the remaining modes keep the narrower comparison
    until I6-A/B/C port their mode-specific v1 behavior.
    """
    # Given: a static mode fixture and its v1 callback-success snapshot
    root = tmp_path / mode
    _generate.materialize_sut_case(mode, root)
    monkeypatch.chdir(root)
    _FLOW_INVOICES.clear()
    expected = _frozen(mode, "ok")["observed"]
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        # The flow entry contract unpacks into data/temp exactly like
        # ``workflows.run(flow=...)`` and v1 itself (ruling #1).
        unpacked_dir_path=root / "data" / "temp",
    )

    # When: running the eager flow through the v2 Runner
    report = runner.run(_contract_noop_flow, **_v2_overrides(mode))

    # Then: success, tile count, and primary invoice artifacts match frozen v1
    assert report.status == "success"
    assert len(report.iterations) == expected["callback_count"]
    assert _generate.normalize_snapshot(_FLOW_INVOICES, roots=(root,)) == _expected_invoice_sequence(expected["invoices"])

    # And: the proven modes reproduce every frozen artifact observation
    if mode in _FULL_PARITY_MODES:
        actual, expected_view = parity_pair(root, expected)
        assert actual == expected_view


# --------------------------------------------------------------------------
# CB-V2 matrix (Session I-REVIEW-B, review F5)
#
# The CB cells above re-run *v1's own loop* and compare it with the snapshot v1
# produced: they pin the oracle, not the unification. The cells below make the
# subject under test the thing the review asked for -- the unified Runner
# driving ``LegacyCallbackInvoker`` through a ``LegacyCallbackTarget`` -- while
# keeping the same frozen v1 observation as the expectation.
# --------------------------------------------------------------------------


def _callback_count(root: Path) -> int:
    """Count invocations the shared oracle callback recorded under ``root``."""
    marker = root / _generate.CALLBACK_MARKER_NAME
    if not marker.exists():
        return 0
    return len(marker.read_text(encoding="utf-8").splitlines())


def _cb_v2_runner(root: Path) -> Runner:
    """Build the Runner a v1-compatible caller gets from ``workflows.run``."""
    return Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
    )


def _cb_v2_request(root: Path, mode: str, callback: Any) -> RunRequest:
    """Build the legacy-callback request for one CB-V2 cell.

    ``config_source`` is deliberately the v1 ``Config`` object the frozen
    snapshot was generated with, not a mapping of the same switches:
    ``ConfigNormalizer._convert_v1`` seeds ``on_iteration_error: fail_fast``
    from a v1 source, and that policy -- v1's own -- is what makes the observed
    callback counts comparable with the frozen v1 ones at all.
    """
    return RunRequest(
        root=root,
        target=LegacyCallbackTarget(function=callback),
        config_source=_generate.oracle_config(mode),
    )


def _run_cb_v2(root: Path, mode: str, callback: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Materialize one static case and run it through the v2 callback path."""
    _generate.materialize_sut_case(mode, root)
    # The oracle callbacks record their invocations relative to the process
    # CWD, exactly as they did inside the v1 worker that froze the snapshots.
    monkeypatch.chdir(root)
    return _cb_v2_runner(root).run(_cb_v2_request(root, mode, callback))


def _job_failed_text(root: Path) -> str:
    return str(
        _generate.normalize_snapshot(
            (root / "data" / "job.failed").read_text(encoding="utf-8"),
            roots=(root,),
        ),
    )


@pytest.mark.parametrize(
    "mode",
    [pytest.param(mode, id=f"TC-UM-{_MODE_IDS[mode]}-CB-V2-OK") for mode in _MODES],
)
def test_callback_target_success_matches_frozen_v1_artifacts(
    mode: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CB-V2 OK cells: the v2 callback path reproduces the frozen v1 artifacts."""
    # Given: the static mode fixture and the v1 snapshot of a successful run
    expected = _frozen(mode, "ok")["observed"]
    root = tmp_path / mode

    # When: running the v1 dataset callback through the unified Runner
    report = _run_cb_v2(root, mode, _generate._oracle_callback_ok, monkeypatch)  # noqa: SLF001 -- the generator owns the oracle callback

    # Then: the run succeeds having called the callback once per frozen tile
    assert report.status == "success"
    assert _callback_count(root) == expected["callback_count"]
    assert len(report.iterations) == expected["callback_count"]

    # And: every observed artifact equals the frozen v1 observation, content
    # included -- this is the comparison review F4 found missing
    actual, expected_view = parity_pair(root, expected)
    assert actual == expected_view

    # And: the SUT exercised the legacy two-argument signature rule
    assert accepts_unified_argument(_generate._oracle_callback_ok) is False  # noqa: SLF001


@pytest.mark.parametrize(
    "mode",
    [pytest.param(mode, id=f"TC-UM-{_MODE_IDS[mode]}-CB-V2-USERERR") for mode in _MODES],
)
def test_callback_target_user_error_matches_frozen_v1_job_failed(
    mode: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CB-V2 USERERR cells: ``StructuredError`` reaches job.failed verbatim.

    The v1 ``Config`` seeds ``fail_fast``, so the v2 run must stop where v1
    stopped: one callback call, one iteration, and -- for the multi-tile modes
    -- no artifact from the tiles v1 never reached.
    """
    # Given: the frozen v1 user-error observation and its translation row
    cell = flow_error_cell(mode, "usererr")
    expected = _frozen(mode, "usererr")["observed"]
    tile_count = int(_frozen(mode, "ok")["observed"]["callback_count"])
    root = tmp_path / mode

    # When: the v1 callback raises StructuredError(999) inside the v2 Runner
    report = _run_cb_v2(root, mode, _generate._oracle_callback_usererr, monkeypatch)  # noqa: SLF001

    # Then: the run fails and job.failed is byte-identical to the v1 artifact
    assert report.status == "failed"
    assert _job_failed_text(root) == expected["job_failed_text"]
    assert _job_failed_text(root).splitlines()[0] == f"ErrorCode={cell.v1_code}"

    # And: fail_fast stopped the run exactly where v1 stopped
    assert _callback_count(root) == cell.cb_v2_callback_count
    assert _callback_count(root) == expected["callback_count"]
    assert len(report.iterations) == expected_cb_v2_iteration_count(cell, tile_count)
    assert [iteration["status"] for iteration in report.iterations] == ["failed"]

    # And: the tree and the raw copies v1 left behind are reproduced. Invoices
    # and post-invoke artifacts are not compared here: v1 aborts mid-pipeline,
    # and the pipeline position of the abort is pinned by the tree itself.
    observed = observe_v2_run(root)
    frozen_view = parity_view(expected)
    assert observed["output_tree"] == frozen_view["output_tree"]
    assert observed["raw_sha256"] == frozen_view["raw_sha256"]


@pytest.mark.parametrize(
    "mode",
    [pytest.param(mode, id=f"TC-UM-{_MODE_IDS[mode]}-CB-V2-VALERR") for mode in _MODES],
)
def test_callback_target_validation_error_is_frontloaded(
    mode: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CB-V2 VALERR cells: the invoice defect is caught before any callback runs.

    This is the one deliberate divergence from v1 (contracts.md §I6-0): v1
    reported a mode-specific downstream symptom -- and for three of five modes
    only *after* the callback had run -- while the unified Runner validates the
    source invoice in ``pre_validate`` and reports catalog code 4001.
    """
    # Given: the translation row and a fixture whose invoice violates its schema
    cell = flow_error_cell(mode, "valerr")
    root = tmp_path / mode
    _generate.materialize_sut_case(mode, root)
    _generate._invalidate_invoice(root)  # noqa: SLF001 -- the generator owns the defect
    monkeypatch.chdir(root)

    # When: running the v1 dataset callback through the unified Runner
    report = _cb_v2_runner(root).run(
        _cb_v2_request(root, mode, _generate._oracle_callback_ok),  # noqa: SLF001
    )

    # Then: the run fails with the v2 validation code and its reason
    assert report.status == "failed"
    job_failed = _job_failed_text(root)
    assert job_failed.splitlines()[0] == f"ErrorCode={cell.v2_code}"
    assert VALIDATION_REASON in job_failed

    # And: no tile and therefore no user callback ever ran
    assert _callback_count(root) == cell.cb_v2_callback_count
    assert report.iterations == []
    assert len(report.iterations) == expected_cb_v2_iteration_count(cell, 0)


def test_callback_target_smarttable_row_material_matches_the_v1_oracle__tc_um_smt_cb_v2_rowdata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The SmartTable row dictionary the callback receives equals v1's.

    ``smarttable_row_data`` is the one callback argument the v2 Runner rebuilds
    from its own plan (``TileMaterial``, review F1), so a frozen artifact
    comparison cannot see a regression in it. The expectation is therefore a
    live v1 run of the same fixture rather than a snapshot.
    """
    # Given: a live v1 oracle run recording what each callback invocation got
    v1_root = tmp_path / "v1"
    _generate.materialize_sut_case("smarttable", v1_root)
    oracle = _generate._execute_v1_observation("smarttable", "ok", v1_root)  # noqa: SLF001
    assert oracle["exit_code"] == 0
    expected_rows = _generate.read_callback_row_data(v1_root)

    # When: the same callback runs on the same fixture through the v2 Runner
    v2_root = tmp_path / "v2"
    report = _run_cb_v2(v2_root, "smarttable", _generate._oracle_callback_ok, monkeypatch)  # noqa: SLF001

    # Then: every invocation received exactly the v1 row dictionary
    assert report.status == "success"
    observed_rows = _generate.read_callback_row_data(v2_root)
    assert observed_rows == expected_rows

    # And: the material is genuinely populated, so equality is not two empties
    assert len(observed_rows) == oracle["callback_count"]
    assert all(row for row in observed_rows)
    assert {row["basic/dataName"] for row in observed_rows} == {
        "smarttable_value_0",
        "smarttable_value_1",
        "smarttable_value_2",
    }


def test_callback_target_error_policy_comes_from_the_v1_config__tc_um_mdt_cb_v2_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The v1 ``Config`` object -- not the switches it carries -- seeds fail_fast.

    Falsification of the CB-V2 USERERR cells: if they passed the same five
    switches as a mapping, the run would take the v2 default ``continue``
    policy, every tile would be attempted, and the callback count would stop
    matching v1's. This cell pins that the difference is real and observable,
    so a CB-V2 cell cannot be "fixed" by loosening its configuration source.
    """
    # Given: the MultiDataTile fixture, whose two tiles make the policy visible
    mode = "multidatatile"
    frozen_callbacks = int(_frozen(mode, "usererr")["observed"]["callback_count"])
    tile_count = int(_frozen(mode, "ok")["observed"]["callback_count"])
    assert frozen_callbacks < tile_count

    # When: running the same failing callback with a v2 mapping configuration
    root = tmp_path / mode
    _generate.materialize_sut_case(mode, root)
    monkeypatch.chdir(root)
    report = _cb_v2_runner(root).run(
        RunRequest(
            root=root,
            target=LegacyCallbackTarget(function=_generate._oracle_callback_usererr),  # noqa: SLF001
            config_source=_v2_overrides(mode),
        ),
    )

    # Then: the v2 continue policy attempts every tile, unlike v1
    assert report.status == "failed"
    assert len(report.iterations) == tile_count
    assert _callback_count(root) == tile_count
    assert _callback_count(root) != frozen_callbacks


def test_callback_target_accepts_the_unified_signature__tc_um_inv_cb_v2_signature(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both v1 callback signatures reach the same artifacts through the v2 path.

    v1's ``DatasetRunner`` accepts ``(srcpaths, resource_paths)`` and the unified
    ``RdeDatasetPaths``; the CB-V2 cells above exercise the first. This cell
    exercises the second against the same frozen observation so a regression in
    ``accepts_unified_argument`` cannot hide behind one signature.
    """
    # Given: a unified-signature wrapper over the shared oracle callback
    def unified_callback(dataset_paths: Any) -> None:
        srcpaths, resource_paths = dataset_paths.as_legacy_args()
        _generate._oracle_callback_ok(srcpaths, resource_paths)  # noqa: SLF001

    assert accepts_unified_argument(unified_callback) is True
    expected = _frozen("invoice", "ok")["observed"]
    root = tmp_path / "invoice"

    # When: running it through the unified Runner
    report = _run_cb_v2(root, "invoice", unified_callback, monkeypatch)

    # Then: the artifacts are the frozen v1 ones, as with the legacy signature
    assert report.status == "success"
    assert _callback_count(root) == expected["callback_count"]
    actual, expected_view = parity_pair(root, expected)
    assert actual == expected_view


def _frozen_canary(mode: str) -> dict:
    path = _generate.CANARY_EXPECTED_ROOT / mode / "ok.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "mode",
    [pytest.param(mode, id=f"TC-UM-{_MODE_IDS[mode]}-CANARY-FLOW-OK") for mode in _CANARY_FLOW_MODES],
)
def test_canary_flow_entry_matches_frozen_real_input_observation(
    mode: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Canary FLOW cells reproduce the frozen v1 observation of real RDE material.

    The static matrix fixtures are minimal by construction; the canary family is
    imported production material, so it exercises artifacts the synthetic cases
    never produce — RDEFormat's ``data/thumbnail/1.jpg`` above all. The
    comparison is therefore the same full parity view as the FLOW-OK cells,
    thumbnails included.
    """
    # Given: the assembled canary inputs and their frozen v1 observation
    frozen = _frozen_canary(mode)
    expected = frozen["observed"]
    root = tmp_path / mode
    _generate._materialize_canary_case(mode, root)  # noqa: SLF001 -- frozen v1 assembly is the contract
    monkeypatch.chdir(root)
    _FLOW_INVOICES.clear()
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        # Same flow-entry contract as the FLOW-OK cells (ruling #1).
        unpacked_dir_path=root / "data" / "temp",
    )

    # When: running the eager flow with no overrides at all (ruling #4)
    report = runner.run(_contract_noop_flow)

    # Then: the run succeeds with the tile count v1 observed
    assert report.status == "success"
    assert len(report.iterations) == expected["callback_count"]

    # And: every observed artifact matches, including generated thumbnails
    actual, expected_view = parity_pair(root, expected)
    assert actual == expected_view


@pytest.mark.parametrize(
    ("mode", "outcome"),
    [
        pytest.param(mode, outcome, id=f"TC-UM-{_MODE_IDS[mode]}-FLOW-{outcome.upper()}")
        for mode in _MODES
        for outcome in ("usererr", "valerr")
    ],
)
def test_flow_error_cells_match_the_i6_0_translation_table(
    mode: str,
    outcome: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flow error cells follow the contracted v1 -> v2 error translation.

    The frozen v1 observation is checked against the table first, so the table
    can never silently drift away from the oracle it documents.
    """
    # Given: the contracted translation row and the frozen v1 observation
    cell = flow_error_cell(mode, outcome)
    expected = _frozen(mode, outcome)["observed"]
    assert expected["job_failed_error_code"] == f"ErrorCode={cell.v1_code}"
    assert expected["callback_count"] == cell.v1_callback_count
    assert expected["exit_code"] == FAILED_EXIT_CODE
    assert expected["legacy_return"] is None

    root = tmp_path / mode
    _generate.materialize_sut_case(mode, root)
    if outcome == "valerr":
        _generate._invalidate_invoice(root)
    monkeypatch.chdir(root)
    _FLOW_INVOICES.clear()
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        # One flow-entry contract: the unpack root is data/temp for every cell
        # of the matrix, exactly as v1 and workflows.run(flow=...) use it.
        unpacked_dir_path=root / "data" / "temp",
    )
    target = _contract_usererr_flow if outcome == "usererr" else _contract_noop_flow

    # When: running the eager flow through the v2 Runner on the same input
    report = runner.run(target, **_v2_overrides(mode))

    # Then: the run fails, and job.failed carries the contracted code
    assert report.status == "failed"
    job_failed = _generate.normalize_snapshot(
        (root / "data" / "job.failed").read_text(encoding="utf-8"),
        roots=(root,),
    )
    assert job_failed.splitlines()[0] == f"ErrorCode={cell.v2_code}"

    # And: the message follows this cell's rule
    if cell.v2_message is MessageRule.V1_VERBATIM:
        assert job_failed == expected["job_failed_text"]
    else:
        assert VALIDATION_REASON in job_failed
        assert cell.v2_code != cell.v1_code

    # And: the flow ran exactly once per tile, or not at all
    tile_count = int(_frozen(mode, "ok")["observed"]["callback_count"])
    assert len(report.iterations) == expected_iteration_count(cell, tile_count)
    assert [iteration["status"] for iteration in report.iterations] == ["failed"] * len(report.iterations)
    assert len(_FLOW_INVOICES) == len(report.iterations)

    # And: only the attempted tiles left a divided/ tree behind
    divided = root / "data" / "divided"
    actual_divided = tuple(sorted(path.name for path in divided.iterdir())) if divided.exists() else ()
    assert actual_divided == expected_divided_indices(cell, tile_count)


# --------------------------------------------------------------------------
# Multi-tile error policy cells (Session I-REVIEW-B, review F7)
#
# These six cells were ``pytest.fail()`` placeholders. Every one of them now
# runs a three-tile family whose tile index 1 raises StructuredError(999):
# that is the smallest shape in which ``continue`` and ``fail_fast`` are
# distinguishable, because a later tile must remain to be either run or
# skipped. The FAIL-FAST cells and the MultiDataTile CONTINUE cell compare a
# live v1 oracle; ExcelInvoice and SmartTable have no v1 continue policy at all
# (v1 honors ``ignore_errors`` only in MultiDataTile, ``workflows._process_mode``),
# so their CONTINUE cells state a v2-only contract.
# --------------------------------------------------------------------------

#: The three modes whose input families can produce more than one tile.
_POLICY_MODES = ("excelinvoice", "multidatatile", "smarttable")

#: Tiles each policy family produces. Three is the contract, not an accident:
#: with two tiles a fail-fast run and a continue run are indistinguishable.
_POLICY_TILE_COUNT = 3

_POLICY_FLOW_CALLS: list[int] = []


@flow
def _policy_flow(paths: InputPaths, iteration: IterationInfo) -> None:
    """Fail tile :data:`_generate.FAILING_TILE_INDEX` and no other tile."""
    assert paths.inputdata.is_dir()
    _POLICY_FLOW_CALLS.append(iteration.index)
    if iteration.index == _generate.FAILING_TILE_INDEX:
        raise StructuredError(_USERERR_MESSAGE, ecode=999)


def _extend_excelinvoice_to_three_rows(inputdata: Path) -> None:
    """Grow the two-row ExcelInvoice fixture into a three-tile family.

    The committed workbook is read back and one data row is appended rather
    than rebuilt from the fixture constants, so this helper cannot drift away
    from the sheet layout ``_generate._write_excelinvoice`` produces. The file
    archive is rewritten with deterministic member metadata for the same reason
    the generator does: a timestamp in a ZIP entry would make the input
    non-reproducible.

    Args:
        inputdata: The materialized ``data/inputdata`` directory.
    """
    workbook = inputdata / "contract_excel_invoice.xlsx"
    sheets = pd.read_excel(workbook, sheet_name=None, header=None)
    form = sheets["invoice_form"]
    owner_id = form.iloc[-1].tolist()[2]
    form.loc[len(form)] = ["test_child3.txt", "test3", owner_id]
    with pd.ExcelWriter(workbook) as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False, header=False)
    with zipfile.ZipFile(inputdata / "excelinvoice_files.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index in range(1, _POLICY_TILE_COUNT + 1):
            info = zipfile.ZipInfo(f"test_child{index}.txt", date_time=(2026, 7, 15, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, f"excelinvoice child {index}\n".encode())


def _materialize_policy_case(mode: str, root: Path) -> None:
    """Materialize the three-tile input family for one policy cell.

    The SmartTable fixture already carries three rows; the other two families
    are grown here so all three modes share one tile shape.

    Args:
        mode: One of :data:`_POLICY_MODES`.
        root: Run root to materialize into.
    """
    _generate.materialize_sut_case(mode, root)
    if mode == "multidatatile":
        (root / "data" / "inputdata" / "tile_02.txt").write_text("third tile\n", encoding="utf-8")
    elif mode == "excelinvoice":
        _extend_excelinvoice_to_three_rows(root / "data" / "inputdata")


def _run_policy_v1_oracle(mode: str, root: Path, *, ignore_errors: bool = False) -> dict[str, Any]:
    """Run the live v1 oracle over one policy family in its own process."""
    _materialize_policy_case(mode, root)
    return _generate._execute_v1_observation(  # noqa: SLF001 -- the generator owns the isolated worker
        mode,
        "tilefail",
        root,
        ignore_errors=ignore_errors,
    )


def _run_policy_v2(
    mode: str,
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    config_source: Any,
) -> Any:
    """Run the same policy family through the v2 Runner's flow entry."""
    _materialize_policy_case(mode, root)
    monkeypatch.chdir(root)
    _POLICY_FLOW_CALLS.clear()
    return _cb_v2_runner(root).run(
        RunRequest(root=root, target=FlowTarget(function=_policy_flow), config_source=config_source),
    )


def _continue_overrides(mode: str, *, structured: bool = False) -> dict[str, Any]:
    """Return the v2 configuration for a continue-policy cell.

    Args:
        mode: One of :data:`_POLICY_MODES`.
        structured: Enable ``save_invoice_to_structured``. The v2-only cells
            switch it on so a completed tile carries a post-invoke artifact the
            failed tile must not have; without it the two tiles are
            indistinguishable and the contract would be unobservable.

    Returns:
        A v2 configuration mapping, which takes the v2 ``continue`` policy.
    """
    overrides = deepcopy(_v2_overrides(mode))
    overrides["execution"] = {"on_iteration_error": "continue"}
    if structured:
        overrides["system"]["save_invoice_to_structured"] = True
    return overrides


def _tile_files(tile_root: Path) -> list[str]:
    """Return the tile-relative POSIX paths of every file below one tile."""
    if not tile_root.exists():
        return []
    return sorted(path.relative_to(tile_root).as_posix() for path in tile_root.rglob("*") if path.is_file())


@pytest.mark.parametrize(
    "mode",
    [pytest.param(mode, id=f"TC-UM-{_MODE_IDS[mode]}-FLOW-FAIL-FAST") for mode in _POLICY_MODES],
)
def test_multitile_fail_fast_matches_the_v1_oracle(
    mode: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FAIL-FAST cells: the run stops at tile 1 exactly where v1 stopped.

    The expectation is a live v1 run of the same three-tile family, because v1
    has no frozen multi-tile partial-failure snapshot (the corpus is 16 + 5
    single-failure cases). v1's default ``ignore_errors=False`` *is* fail-fast,
    so the oracle needs no special configuration -- only the v1 ``Config``
    object, which seeds the same policy on the v2 side.

    That the skipped tile really exists is proven by this mode's
    CONTINUE-PARTIAL cell, which runs three iterations over the same fixture.
    """
    # Given: v1 executed over the three-tile family with its own fail-fast policy
    oracle = _run_policy_v1_oracle(mode, tmp_path / "v1")
    assert oracle["exit_code"] == FAILED_EXIT_CODE
    assert oracle["callback_count"] == _generate.FAILING_TILE_INDEX + 1
    assert oracle["job_failed_text"] is not None

    # When: the v2 Runner runs the same family with the same v1 configuration
    root = tmp_path / "v2"
    report = _run_policy_v2(mode, root, monkeypatch, config_source=_generate.oracle_config(mode))

    # Then: two tiles were attempted and the run failed
    assert report.status == "failed"
    assert [iteration["status"] for iteration in report.iterations] == ["completed", "failed"]
    assert _POLICY_FLOW_CALLS == [0, _generate.FAILING_TILE_INDEX]

    # And: every artifact, its content included, equals what v1 left behind
    assert observe_v2_run(root) == parity_view(oracle)
    assert _job_failed_text(root) == oracle["job_failed_text"]

    # And: the tile after the failing one was never created on either side
    assert not (root / "data" / "divided" / "0002").exists()


@pytest.mark.parametrize(
    "mode",
    [pytest.param("multidatatile", id="TC-UM-MDT-FLOW-CONTINUE-PARTIAL")],
)
def test_multitile_continue_partial_matches_the_v1_oracle(
    mode: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CONTINUE-PARTIAL cell with a v1 counterpart: MultiDataTile.

    ``multidata_tile.ignore_errors: true`` is the only continue policy v1 has,
    so MultiDataTile is the only mode whose partial run can be measured against
    a live oracle. v1 exits 0 and writes no ``job.failed`` for a partial run;
    v2's ``finalize`` writes ``job.failed`` only for ``failed``, so the two
    agree without any Core change.
    """
    # Given: v1 executed with its continue policy over the three-tile family
    oracle = _run_policy_v1_oracle(mode, tmp_path / "v1", ignore_errors=True)
    assert oracle["exit_code"] == 0
    assert oracle["callback_count"] == _POLICY_TILE_COUNT
    assert oracle["job_failed_text"] is None
    assert [status["status"] for status in oracle["legacy_return"]["statuses"]] == [
        "success",
        "failed",
        "success",
    ]

    # When: the v2 Runner runs the same family with on_iteration_error=continue
    root = tmp_path / "v2"
    report = _run_policy_v2(mode, root, monkeypatch, config_source=_continue_overrides(mode))

    # Then: the later tile still ran and the run is partial, not failed
    assert report.status == "partial"
    assert [iteration["status"] for iteration in report.iterations] == ["completed", "failed", "completed"]
    assert _POLICY_FLOW_CALLS == [0, 1, 2]

    # And: every artifact, its content included, equals what v1 left behind
    assert observe_v2_run(root) == parity_view(oracle)

    # And: a partial run leaves no job.failed, exactly as v1 measured
    assert not (root / "data" / "job.failed").exists()
    assert report.warnings == [
        {"code": 3001, "message": "1 iteration(s) failed", "failed_count": 1},
    ]


@pytest.mark.parametrize(
    "mode",
    [
        pytest.param(mode, id=f"TC-UM-{_MODE_IDS[mode]}-FLOW-CONTINUE-PARTIAL")
        for mode in ("excelinvoice", "smarttable")
    ],
)
def test_multitile_continue_partial_is_a_v2_only_contract(
    mode: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CONTINUE-PARTIAL cells with no v1 counterpart: ExcelInvoice and SmartTable.

    v1 re-raises from every mode except MultiDataTile, so there is no v1
    observation to compare against and the contract is stated on the v2 side
    only (contracts.md §I-REVIEW-B): the run continues past the failing tile,
    reports ``partial``, warns with the failure count, writes no ``job.failed``,
    and leaves the failed tile with its pre-invoke artifacts only.
    """
    # Given: the three-tile family and the v2 continue policy
    root = tmp_path / mode

    # When: tile 1 fails while tiles 0 and 2 succeed
    report = _run_policy_v2(
        mode,
        root,
        monkeypatch,
        config_source=_continue_overrides(mode, structured=True),
    )

    # Then: the run is partial with one failed tile between two completed ones
    assert report.status == "partial"
    assert [iteration["status"] for iteration in report.iterations] == ["completed", "failed", "completed"]
    assert _POLICY_FLOW_CALLS == [0, 1, 2]
    assert report.warnings == [
        {"code": 3001, "message": "1 iteration(s) failed", "failed_count": 1},
    ]

    # And: a partial run is not a failed run, so no job.failed is written
    assert not (root / "data" / "job.failed").exists()

    # And: the failed tile kept its pre-invoke artifacts and gained no
    # post-invoke one, while the tile after it is complete
    failed_tile = _tile_files(root / "data" / "divided" / "0001")
    completed_tile = _tile_files(root / "data" / "divided" / "0002")
    assert [path for path in failed_tile if path.startswith("raw/")]
    assert failed_tile.count("invoice/invoice.json") == 1
    assert [path for path in failed_tile if path.startswith("structured/")] == []
    assert "structured/invoice.json" in completed_tile


@pytest.mark.xfail(strict=False, reason="Phase J: deterministic SIGTERM flush integration is not wired")
def test_multidatatile_sigterm_cell_is_placed__tc_um_mdt_flow_sigterm() -> None:
    """TC-UM-MDT-FLOW-SIGTERM reserves RunReport/job.failed signal flushing."""
    # Given: the representative MultiDataTile termination contract
    signal_name = "SIGTERM"
    # When/Then: Phase J must wire and verify deterministic signal flushing
    assert signal_name == "SIGTERM"
    pytest.fail("Phase J must implement SIGTERM RunReport/job.failed flushing")


@pytest.mark.xfail(strict=False, reason="Phase J: callback observability is unavailable before unification")
@pytest.mark.parametrize(
    "mode",
    [pytest.param(mode, id=f"TC-UM-{_MODE_IDS[mode]}-CB-OBS") for mode in _MODES],
)
def test_callback_observability_columns_are_placed(mode: str) -> None:
    """Callback Events, Provenance, and RunReport columns remain visible for Phase J."""
    # Given: a legacy callback execution with no unified observability artifacts
    expected_columns = {"events", "provenance", "run_report"}
    assert mode in _MODES
    # When/Then: Phase J must populate every declared comparison column
    assert expected_columns
    pytest.fail("Phase J must add callback Events/Provenance/RunReport parity")
