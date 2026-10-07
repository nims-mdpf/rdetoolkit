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
    TC-UM-*-CB-ENTRY-OK/USERERR/VALERR: the same three outcomes with the
        **public** entry point as the SUT — ``workflows.run(custom_dataset_function=
        ...)`` executed in a subprocess so its ``sys.exit`` and its CWD-relative
        inputs are observable (Session J2 / I7, ruling #2;
        tests/v2/contract/entry_observation.py). The expectation is the same
        frozen v1 observation, compared key by key for OK (``legacy_return``
        included — this is the H1 verification point) and for USERERR; VALERR
        follows the front-loaded-validation divergence rule (contracts.md §J2 D4).
    TC-UM-*-CB-OBS: the callback entry point's **observability** equals the flow
        entry point's (Session J1 / I8, ADR-023 decision 5). One callback calling
        one ``@node`` is compared with a ``@flow`` calling the same ``@node``:
        event-name sequence, ``node_calls`` columns, the
        ``parent_flow == RunReport.flow_id`` invariant, RunReport shape, and the
        ``graph`` / ``report show`` / ``repro export`` surfaces (matrix columns
        6/7/8/12). A negative-control cell reinstates the pre-J1 recorder-less
        invoker to prove the five cells detect the difference.

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
    TC-UM-MDT-FLOW-SIGTERM: a two-tile MultiDataTile run terminated between
        tiles; the flush contract is RunReport ``failed`` 3004, ``job.failed``
        ``ErrorCode=3004``, ``run.completed{failed}``, and tile 0's artifacts
        surviving (Session J2, ruling #5).
    TC-UM-MDT-CB-ENTRY-SIGTERM: the same termination through the public entry
        point, whose return code is 1 because a failed run exits non-zero.

All expected callback values are static JSON produced by ``_generate.py`` at
the ``source.commit`` recorded in each snapshot. The tests execute v1 only as
the SUT; they never create an expected value at test time.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pytest
from typer.testing import CliRunner

from rdetoolkit.api.request import FlowTarget, LegacyCallbackTarget, RunRequest
from rdetoolkit.cli.app import app
from rdetoolkit.compat.v1.callback import accepts_unified_argument, to_legacy_dataset_paths
from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.domain.artifacts import ImageArtifactService, RawArtifactService
from rdetoolkit.domain.invoice_service import InvoiceService
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.report.events import FileEventSink
from rdetoolkit.runner.execute import ExecutionResult
from rdetoolkit.runner.executor import TileExecutor
from rdetoolkit.runner.invoker import InvokerRegistry
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths, InvoiceData, IterationInfo
from tests.v2.contract.entry_observation import (
    entry_parity_view,
    execute_entry_observation,
    frontload_gap_kind,
    has_rdesys_log,
    tree_entries,
)
from tests.v2.contract.fixtures import _generate
from tests.v2.contract.observe import observe_v2_run, parity_pair, parity_view, pending_freeze_view
from tests.v2.contract.provenance_parity import (
    archive_listing,
    event_names,
    expected_event_names,
    graph_iterations,
    node_call_columns,
    node_event_ids,
    read_events,
    recorded_parent_flows,
    report_shape,
    run_report_path,
)
from tests.v2.contract.flow_error_table import (
    FAILED_EXIT_CODE,
    INVOICE_SCHEMA_INVALID_CODE,
    VALIDATION_REASON,
    MessageRule,
    expected_cb_v2_iteration_count,
    expected_divided_indices,
    expected_iteration_count,
    flow_error_cell,
)

#: Repository root, put on the child interpreters' ``PYTHONPATH`` so the SIGTERM
#: subprocesses can import the fixture generator's ``oracle_config``.
_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

#: ``ERROR_CATALOG`` code for an interrupted run (Design §6.3).
_RUN_INTERRUPTED_CODE = 3004

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
    # (UPDATED Session J-REVIEW ruling #2 / contracts.md §J-REVIEW D9: a legacy
    # callback target whose every tile failed under continue is "partial", as
    # v1's ignore_errors run was, and publishes no job.failed)
    assert report.status == "partial"
    assert not (root / "data" / "job.failed").exists()
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


# --------------------------------------------------------------------------
# CB-ENTRY matrix (Session J2 / I7, ruling #2)
#
# The CB cells run v1's loop; the CB-V2 cells run the Runner through a
# ``RunRequest`` a test built. Neither runs the thing a deployed structured
# program calls: ``rdetoolkit.workflows.run(custom_dataset_function=...)``.
# These fifteen cells make that public entry the subject under test, in a
# subprocess, because its failure contract is ``sys.exit(1)`` and its inputs
# come from the process CWD.
# --------------------------------------------------------------------------


def _cb_entry_observation(mode: str, outcome: str, root: Path) -> dict[str, Any]:
    """Materialize one static case and observe the public entry point on it."""
    _generate.materialize_sut_case(mode, root)
    return execute_entry_observation(mode, outcome, root)


@pytest.mark.parametrize(
    "mode",
    [pytest.param(mode, id=f"TC-UM-{_MODE_IDS[mode]}-CB-ENTRY-OK") for mode in _MODES],
)
def test_public_entry_success_matches_the_frozen_v1_observation(
    mode: str,
    tmp_path: Path,
) -> None:
    """CB-ENTRY OK cells: every observed key equals the frozen v1 one.

    ``legacy_return`` is included deliberately: this is where
    ``RunReport.to_legacy_statuses()`` is proven to reproduce v1's
    ``WorkflowResultManager.to_json()`` through a real run rather than through a
    hand-built aggregator (the H1 contract, Phase J ruling #2).
    """
    # Given: the frozen v1 observation of a successful callback run
    expected = _frozen(mode, "ok")["observed"]

    # When: the public v1 entry point runs the same callback on the same input
    actual = _cb_entry_observation(mode, "ok", tmp_path / mode)

    # Then: the complete observation matches, log directory contents aside
    assert entry_parity_view(actual) == entry_parity_view(expected)

    # And: the run succeeded, calling the callback once per frozen tile
    assert actual["exit_code"] == 0
    assert actual["callback_count"] == expected["callback_count"]

    # And: both entry points published the v1 rdesys log (Phase J ruling #3).
    # The equality above cannot see it -- data/logs contents are the one
    # contractually asymmetric region -- so it is asserted here explicitly.
    assert has_rdesys_log(actual)
    assert has_rdesys_log(expected)


@pytest.mark.parametrize(
    "mode",
    [pytest.param(mode, id=f"TC-UM-{_MODE_IDS[mode]}-CB-ENTRY-USERERR") for mode in _MODES],
)
def test_public_entry_user_error_matches_the_frozen_v1_observation(
    mode: str,
    tmp_path: Path,
) -> None:
    """CB-ENTRY USERERR cells: a raising callback reproduces v1 exactly.

    Ruling #2 only requires ``exit_code`` / ``legacy_return`` / ``job_failed_text``
    / ``callback_count`` / tree / raw / artifact here. The measured result is full
    equality of every key, so that is what is asserted — a strictly stronger
    expectation than the ruling's floor, with the named fields spelled out below
    so a regression names itself.
    """
    # Given: the frozen v1 observation of a StructuredError(999) callback
    cell = flow_error_cell(mode, "usererr")
    expected = _frozen(mode, "usererr")["observed"]

    # When: the public v1 entry point runs that callback
    actual = _cb_entry_observation(mode, "usererr", tmp_path / mode)

    # Then: the complete observation matches, log directory contents aside
    assert entry_parity_view(actual) == entry_parity_view(expected)

    # And: the v1 exit and return contract holds -- v1 never returned a value
    # from a failed run, and neither does the unified entry point
    assert actual["exit_code"] == FAILED_EXIT_CODE
    assert actual["legacy_return"] is None

    # And: job.failed is byte-identical, carrying the user's own ecode
    assert actual["job_failed_text"] == expected["job_failed_text"]
    assert actual["job_failed_error_code"] == f"ErrorCode={cell.v1_code}"

    # And: fail_fast stopped the run where v1 stopped
    assert actual["callback_count"] == cell.v1_callback_count
    assert has_rdesys_log(actual)


@pytest.mark.parametrize(
    "mode",
    [pytest.param(mode, id=f"TC-UM-{_MODE_IDS[mode]}-CB-ENTRY-VALERR") for mode in _MODES],
)
def test_public_entry_validation_error_is_frontloaded(
    mode: str,
    tmp_path: Path,
) -> None:
    """CB-ENTRY VALERR cells: the invoice defect is reported before tile 0 exists.

    This is the one deliberate divergence of the public entry point
    (contracts.md §J2 D4): v1 validated mid-pipeline, so it had already created
    the twelve per-tile directories, unpacked its inputs into ``data/temp`` and
    -- for three of five modes -- run the callback. The unified Runner validates
    in ``pre_validate`` and reports catalog code 4001 with nothing built.

    The comparison therefore pins "v2 fails EARLIER", not merely "v2 produces
    less": the observed tree must be a strict subset of the frozen one, and every
    missing entry must classify as a tile artifact, an unpacked input or the
    invoice backup.
    """
    # Given: the frozen v1 observation of the same invalid invoice
    expected = _frozen(mode, "valerr")["observed"]

    # When: the public v1 entry point runs on it
    actual = _cb_entry_observation(mode, "valerr", tmp_path / mode)

    # Then: the run exits 1 having validated before any user code ran
    assert actual["exit_code"] == FAILED_EXIT_CODE
    assert actual["callback_count"] == 0
    assert actual["legacy_return"] is None
    assert actual["job_failed_error_code"] == f"ErrorCode={INVOICE_SCHEMA_INVALID_CODE}"
    assert VALIDATION_REASON in actual["job_failed_text"]
    assert has_rdesys_log(actual)

    # And: nothing but the failure marker was produced
    assert actual["raw_sha256"] == {}
    assert sorted(actual["artifact_sha256"]) == ["data/job.failed"]
    assert actual["invoice_backup_exists"] is False
    assert actual["invoice_backup"] is None
    assert actual["invoices"] == expected["invoices"]

    # And: the tree is a strict subset of v1's, missing exactly the artifacts v1
    # built before it validated
    observed_entries = tree_entries(entry_parity_view(actual))
    frozen_entries = tree_entries(entry_parity_view(expected))
    assert observed_entries < frozen_entries
    gap = frozen_entries - observed_entries
    unclassified = sorted(path for path in gap if frontload_gap_kind(path) is None)
    assert unclassified == []
    assert "tile-artifact" in {frontload_gap_kind(path) for path in gap}


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


# --------------------------------------------------------------------------
# SIGTERM cells (Session J2, ruling #4/#5; contract_matrix open item #2)
#
# v1 installed no handler at all: SIGTERM killed the process outright, leaving
# no job.failed and no record of how far the run got. The unified Runner turns
# it into catalog code 3004 and flushes both artifacts -- an intentional
# improvement over v1, stated as divergence D7 in contracts.md §J2.
#
# Determinism comes from two markers rather than from sleeping: the target
# writes TILE_0_MARKER while handling tile 0 and TILE_1_MARKER immediately
# before blocking in tile 1, and the parent only signals once the second marker
# exists. Tile 0 is therefore provably complete -- tile 1's pre-invoke stages
# have already run -- when the signal is delivered.
# --------------------------------------------------------------------------

#: Written while tile 0 is handled.
_SIGTERM_TILE_0_MARKER = "tile-0-done"

#: Written immediately before tile 1 blocks, i.e. the signal window opens.
_SIGTERM_TILE_1_MARKER = "tile-1-blocking"

#: Seconds tile 1 blocks for. Long enough that the parent always wins the race,
#: short enough that a harness defect fails the test instead of hanging the run.
_SIGTERM_BLOCK_SECONDS = 30

#: Exit status a SIGTERM-interrupted run reports from each entry point. The
#: Runner's own lifecycle returns the failed report and the process ends
#: normally (0); the public v1 entry point turns a failed report into
#: ``sys.exit(1)``, so the same interruption is observed as 1 there.
_SIGTERM_FLOW_RETURN_CODE = 0
_SIGTERM_ENTRY_RETURN_CODE = 1

_SIGTERM_TARGET_PREAMBLE = f"""
import json
import sys
import time
from pathlib import Path

root = Path.cwd()
tile_0_marker = root / {_SIGTERM_TILE_0_MARKER!r}
tile_1_marker = root / {_SIGTERM_TILE_1_MARKER!r}


def block_on_second_tile():
    if not tile_0_marker.exists():
        tile_0_marker.write_text("done", encoding="utf-8")
        return
    tile_1_marker.write_text("blocking", encoding="utf-8")
    time.sleep({_SIGTERM_BLOCK_SECONDS})


from tests.v2.contract.fixtures._generate import oracle_config

config = oracle_config("multidatatile")
"""

_SIGTERM_FLOW_SCRIPT = _SIGTERM_TARGET_PREAMBLE + """
from rdetoolkit.api.request import FlowTarget, RunRequest
from rdetoolkit.core.flow import flow
from rdetoolkit.report.events import FileEventSink
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths


@flow
def pipeline(paths: InputPaths) -> None:
    block_on_second_tile()


Runner(
    root=root,
    inputdata_path=root / "data" / "inputdata",
    unpacked_dir_path=root / "data" / "temp",
    event_sink=FileEventSink(root / "data" / "logs"),
    run_id_factory=lambda: "sigterm-run",
).run(RunRequest(root=root, target=FlowTarget(function=pipeline), config_source=config))
"""

_SIGTERM_ENTRY_SCRIPT = _SIGTERM_TARGET_PREAMBLE + """
from rdetoolkit.workflows import run


def dataset_callback(srcpaths, resource_paths):
    block_on_second_tile()


run(custom_dataset_function=dataset_callback, config=config)
"""


def _run_until_sigterm(script: str, root: Path) -> int:
    """Start a two-tile run, terminate it inside tile 1, and return its status.

    Args:
        script: Child program source; it runs with ``root`` as its CWD.
        root: Already-materialized MultiDataTile run root.

    Returns:
        The child's process return code.
    """
    environment = os.environ.copy()
    # The child needs ``tests.v2.contract.fixtures._generate`` for the frozen
    # oracle config; ``rdetoolkit`` itself comes from the installed package, so
    # the child measures exactly what the test session measures.
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(_REPOSITORY_ROOT), environment.get("PYTHONPATH", "")],
    ).rstrip(os.pathsep)
    process = subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", script],
        cwd=root,
        env=environment,
    )
    marker = root / _SIGTERM_TILE_1_MARKER
    deadline = time.monotonic() + 60
    while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    assert marker.exists(), f"child never reached tile 1 (exit={process.poll()})"
    # The marker is written immediately before the blocking call, so a short
    # settle keeps the signal inside it rather than racing its first instruction.
    time.sleep(0.25)
    process.send_signal(signal.SIGTERM)
    return process.wait(timeout=60)


def _sigterm_report(root: Path) -> dict[str, Any]:
    """Return the single run report a terminated run flushed."""
    reports = sorted((root / "data" / "logs").glob("run_report_*.json"))
    assert len(reports) == 1, f"expected exactly one flushed run report, got {reports}"
    return cast(dict[str, Any], json.loads(reports[0].read_text(encoding="utf-8")))


def _assert_interrupted_flush(root: Path) -> None:
    """Assert the shared 3004 flush contract both SIGTERM cells require."""
    # The RunReport is on disk and names the interruption
    report = _sigterm_report(root)
    assert report["status"] == "failed"
    assert report["error"]["code"] == _RUN_INTERRUPTED_CODE
    assert report["error"]["name"] == "RunInterrupted"
    assert "Remediation:" in report["error"]["message"]

    # job.failed carries the same catalog code, which v1 never wrote at all
    job_failed = (root / "data" / "job.failed").read_text(encoding="utf-8")
    assert job_failed.splitlines()[0] == f"ErrorCode={_RUN_INTERRUPTED_CODE}"

    # Tile 0's artifacts survive the interruption
    assert (root / "data" / "raw" / "tile_00.txt").is_file()
    assert (root / "data" / "invoice" / "invoice.json").is_file()

    # Tile 1 kept only its pre-invoke artifacts: it never finished
    interrupted_tile = _tile_files(root / "data" / "divided" / "0001")
    assert interrupted_tile.count("invoice/invoice.json") == 1
    assert [path for path in interrupted_tile if path.startswith("structured/")] == []


def test_multidatatile_flow_sigterm_flushes_the_failure_contract__tc_um_mdt_flow_sigterm(
    tmp_path: Path,
) -> None:
    """TC-UM-MDT-FLOW-SIGTERM: a terminated flow run flushes 3004 everywhere.

    Replaces the Phase J xfail placeholder (contract_matrix open item #2) by
    applying the TC-E0-001 subprocess harness to the real MultiDataTile matrix
    fixture, configured from the same ``oracle_config`` the other cells use.
    """
    # Given: the two-tile MultiDataTile fixture
    root = tmp_path / "multidatatile"
    _generate.materialize_sut_case("multidatatile", root)

    # When: the run is terminated while tile 1 is executing
    return_code = _run_until_sigterm(_SIGTERM_FLOW_SCRIPT, root)

    # Then: shutdown is orderly -- the Runner returns its failed report
    assert return_code == _SIGTERM_FLOW_RETURN_CODE

    # And: every persisted failure artifact agrees on 3004
    _assert_interrupted_flush(root)

    # And: the event log records the terminal status
    assert any(
        record["name"] == "run.completed" and record["payload"] == {"status": "failed"}
        for record in read_events(root / "data" / "logs", "sigterm-run")
    )


def test_multidatatile_public_entry_sigterm_exits_1__tc_um_mdt_cb_entry_sigterm(
    tmp_path: Path,
) -> None:
    """TC-UM-MDT-CB-ENTRY-SIGTERM: the public entry exits 1 on interruption.

    Same termination, same 3004 flush, but through
    ``workflows.run(custom_dataset_function=...)``: a failed report is
    ``sys.exit(1)`` there (Phase J ruling #2b), so the process status differs
    from the flow cell above by design. v1 would have died on the signal with
    no ``job.failed`` and no report at all (divergence D7).
    """
    # Given: the two-tile MultiDataTile fixture
    root = tmp_path / "multidatatile"
    _generate.materialize_sut_case("multidatatile", root)

    # When: the run is terminated while tile 1's callback is executing
    return_code = _run_until_sigterm(_SIGTERM_ENTRY_SCRIPT, root)

    # Then: the v1 entry contract turns the failed run into a non-zero exit
    assert return_code == _SIGTERM_ENTRY_RETURN_CODE

    # And: the same flush contract holds as for the flow entry point
    _assert_interrupted_flush(root)

    # And: the v1 rdesys log was still configured before the run started
    rdesys_logs = sorted(path.name for path in (root / "data" / "logs").glob("rdesys_*.log"))
    assert len(rdesys_logs) >= 1, f"the public entry must configure the v1 file logger; found {rdesys_logs}"


# --------------------------------------------------------------------------
# CB-OBS matrix (Session J1 / I8, ruling #3)
#
# The question these five cells answer is not "does the callback path work?" --
# the CB-V2 cells above already pin its artifacts against frozen v1. It is
# "does a v1 callback user get the same *observability* a @flow user gets?",
# i.e. matrix columns 6 (RunReport), 7 (Events), 8 (Provenance) and 12 (repro /
# graph / report show). Each cell runs the same mode fixture twice -- once with a
# callback that calls one @node, once with a @flow that calls the same @node the
# same number of times -- and compares the normalized observations.
#
# Both runs are configured from the same v1 ``oracle_config(mode)``, so both
# inherit ``on_iteration_error: fail_fast`` from the v1 origin: a configuration
# difference cannot be mistaken for an observability difference.
# --------------------------------------------------------------------------

#: Shared between the two entry points, so the node-identity comparison is real.
_CB_OBS_NODE_ID = "tests.v2.contract.cb_obs_probe"

#: Modes whose ``oracle_config`` declares no ``extended_mode`` while their input
#: is detected as a non-invoice mode, so ``resolve_mode`` publishes W1001 once
#: per run (Design §8.1 ``warning``). Listed here rather than derived from the
#: run, so the canonical event sequence stays an expectation independent of the
#: subject under test. Both entry points share the resolution step, so the value
#: is the same on both sides by construction.
_CB_OBS_MODE_OVERRIDE_MODES = frozenset({"excelinvoice", "smarttable"})


@node(id=_CB_OBS_NODE_ID)
def _cb_obs_probe(label: str) -> str:
    """The one recorded unit of work both CB-OBS entry points perform."""
    return label


def _cb_obs_callback(srcpaths: object, resource_paths: object) -> None:
    """v1 two-argument dataset callback whose only work is one ``@node`` call."""
    del srcpaths, resource_paths
    _cb_obs_probe("cb-obs")


@flow
def _cb_obs_flow(paths: InputPaths) -> None:
    """The same ``@node``, called the same number of times, from a ``@flow``."""
    assert paths.inputdata.is_dir()
    _cb_obs_probe("cb-obs")


def _run_cb_obs(mode: str, root: Path, target: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Run one CB-OBS side, writing a real JSONL event log next to the report."""
    _generate.materialize_sut_case(mode, root)
    monkeypatch.chdir(root)
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
        event_sink=FileEventSink(root / "data" / "logs"),
    )
    return runner.run(
        RunRequest(root=root, target=target, config_source=_generate.oracle_config(mode)),
    )


def _cb_obs_cli_views(root: Path, report_path: Path) -> tuple[str, str, set[str]]:
    """Return the ``graph`` / ``report show`` output and the repro archive listing."""
    cli = CliRunner()
    graph = cli.invoke(app, ["graph", str(report_path), "--format", "json"])
    assert graph.exit_code == 0, graph.output
    show = cli.invoke(app, ["report", "show", str(report_path)])
    assert show.exit_code == 0, show.output
    archive = root / "repro.zip"
    export = cli.invoke(app, ["repro", "export", str(report_path), "--output", str(archive)])
    assert export.exit_code == 0, export.output
    return graph.output, show.output, archive_listing(archive, report_name=report_path.name)


@pytest.mark.parametrize(
    "mode",
    [pytest.param(mode, id=f"TC-UM-{_MODE_IDS[mode]}-CB-OBS") for mode in _MODES],
)
def test_callback_observability_matches_the_flow_entry(
    mode: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CB-OBS cells: the callback entry point is observable exactly like a flow.

    Columns compared (contract_matrix §2): 6 RunReport, 7 Events, 8 Provenance,
    12 repro archive plus ``graph`` / ``report show`` usability. ``flow_id`` is
    the one value that legitimately differs -- it identifies the callback on one
    side and the flow on the other -- and the invariant that replaces equality is
    ``parent_flow == flow_id`` on **both** sides (ruling #1).
    """
    # Given: the frozen v1 tile count for this mode, and two run roots
    tiles = int(_frozen(mode, "ok")["observed"]["callback_count"])
    cb_root = tmp_path / "cb"
    flow_root = tmp_path / "flow"

    # When: running the same fixture through both entry points
    cb_report = _run_cb_obs(mode, cb_root, LegacyCallbackTarget(function=_cb_obs_callback), monkeypatch)
    flow_report = _run_cb_obs(mode, flow_root, FlowTarget(function=_cb_obs_flow), monkeypatch)

    # Then (column 7): the event-name sequence is identical and canonical
    cb_logs = cb_root / "data" / "logs"
    flow_logs = flow_root / "data" / "logs"
    cb_names = event_names(cb_logs, cb_report.run_id)
    assert cb_names == event_names(flow_logs, flow_report.run_id)
    assert cb_names == expected_event_names(
        tiles=tiles,
        run_warnings=1 if mode in _CB_OBS_MODE_OVERRIDE_MODES else 0,
    )

    # And: the node events name the same node, in the same order, on both sides
    cb_node_events = node_event_ids(cb_logs, cb_report.run_id)
    assert cb_node_events == node_event_ids(flow_logs, flow_report.run_id)
    assert {node_id for _, node_id in cb_node_events} == {_CB_OBS_NODE_ID}

    # Then (column 8): the recorded call columns are identical
    assert node_call_columns(cb_report) == node_call_columns(flow_report)
    assert node_call_columns(cb_report) == [[(_CB_OBS_NODE_ID, 1, "completed")] for _ in range(tiles)]

    # And: every record's parent flow is its own run's reported flow_id
    assert recorded_parent_flows(cb_root / "data") == {cb_report.flow_id}
    assert recorded_parent_flows(flow_root / "data") == {flow_report.flow_id}

    # And: the two flow_ids differ, so the invariant above is not trivially true
    assert cb_report.flow_id != flow_report.flow_id
    assert cb_report.flow_id == f"{_cb_obs_callback.__module__}.{_cb_obs_callback.__qualname__}"

    # Then (column 6): the RunReport shape matches
    assert cb_report.status == "success"
    assert report_shape(cb_report) == report_shape(flow_report)
    assert len(cb_report.iterations) == tiles

    # Then (column 12): both runs are equally consumable by the CLI
    cb_report_path = run_report_path(cb_root / "data", cb_report.run_id)
    flow_report_path = run_report_path(flow_root / "data", flow_report.run_id)
    cb_graph, cb_show, cb_archive = _cb_obs_cli_views(cb_root, cb_report_path)
    flow_graph, flow_show, flow_archive = _cb_obs_cli_views(flow_root, flow_report_path)
    assert cb_archive == flow_archive
    assert "data/logs/<RUN_REPORT>" in cb_archive

    # And: ``graph`` renders the recorded calls instead of the empty placeholder
    for rendered in (cb_graph, flow_graph):
        assert _CB_OBS_NODE_ID in rendered
        assert "No recorded calls" not in rendered
    assert graph_iterations(cb_graph) == graph_iterations(flow_graph)

    # And: ``report show`` is non-empty and identical once the run id line is
    # dropped. It prints failed call ids only, so a successful run shows no node
    # id there by design; ``graph`` above is what carries the node identity.
    assert cb_show.splitlines()[1:] == flow_show.splitlines()[1:]
    assert f"iterations: {tiles}" in cb_show


def test_callback_observability_seats_detect_the_pre_j1_behaviour__tc_um_cb_obs_control(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negative control for the five CB-OBS cells (ruling #3, last bullet).

    Before Session J1 the callback was invoked *outside* any recorder context, so
    its ``@node`` calls were plain function calls: ``node_calls`` was empty, no
    ``node.*`` event existed, and ``graph`` printed "No recorded calls". This cell
    reinstates that behaviour through an invoker substituted at the registry
    boundary and asserts the difference is visible -- without it, the five cells
    above could be satisfied by an implementation that records nothing on either
    side.
    """

    # Given: an invoker reproducing the pre-J1 *observable effect*
    class _PreJ1Invoker:
        """Reproduce the pre-J1 observability: no recorder, no events, no records.

        This is deliberately not a copy of the Session I5 ``invoke`` body. It
        hard-codes the legacy two-argument call instead of running
        ``accepts_unified_argument``'s dispatch (the probe callback below has that
        signature), and it derives ``datatile_id`` from the iteration index rather
        than the raw-file stem. Neither is under test here: the control exists to
        establish that *absence of the recorder context* is what collapses the
        CB-OBS columns, so only that absence is reproduced.
        """

        def invoke(
            self,
            target: Any,
            context: Any,
            *,
            event_sink: Any,
            run_id: str,
            config: Any,
            material: Any,
        ) -> ExecutionResult:
            del event_sink, run_id, config
            srcpaths, resource_paths = to_legacy_dataset_paths(context, material=material).as_legacy_args()
            target.function(srcpaths, resource_paths)
            return ExecutionResult(
                iteration_index=context.iteration.index,
                status="completed",
                call_records=(),
                outputs=(),
                datatile_id=str(context.iteration.index),
            )

    root = tmp_path / "control"
    _generate.materialize_sut_case("invoice", root)
    monkeypatch.chdir(root)
    invoice_service = InvoiceService()
    sink = FileEventSink(root / "data" / "logs")
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
        event_sink=sink,
        invoice_service=invoice_service,
        executor=TileExecutor(
            event_sink=sink,
            flow_invoker=InvokerRegistry(legacy_invoker=_PreJ1Invoker()),
            raw_artifact_service=RawArtifactService(),
            image_artifact_service=ImageArtifactService(),
            invoice_service=invoice_service,
        ),
    )

    # When: the same callback runs without a recorder context
    report = runner.run(
        RunRequest(
            root=root,
            target=LegacyCallbackTarget(function=_cb_obs_callback),
            config_source=_generate.oracle_config("invoice"),
        ),
    )

    # Then: the run still succeeds -- the regression is invisible in the artifacts
    assert report.status == "success"

    # And: every CB-OBS column collapses, which is what the five cells detect
    assert node_call_columns(report) == [[]]
    assert "node.started" not in event_names(root / "data" / "logs", report.run_id)
    assert recorded_parent_flows(root / "data") == set()
    rendered = CliRunner().invoke(
        app,
        ["graph", str(run_report_path(root / "data", report.run_id)), "--format", "mermaid"],
    )
    assert rendered.exit_code == 0, rendered.output
    assert "No recorded calls" in rendered.output
    assert _CB_OBS_NODE_ID not in rendered.output
