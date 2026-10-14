"""EarlyExit validates before it completes (Session I-REVIEW-A, ruling #6 / R5).

v1's ``SmartTableEarlyExitProcessor`` runs first in the SmartTable pipeline: for
the tile whose raw input is the original table it copies the table, **validates
that tile**, and only then raises ``SkipRemainingProcessorsError``. A validation
failure there aborts the run before any dataset callback runs.

v2 recorded the pre-completed tile as ``completed`` immediately and left the
validation to ``post_validate``, which runs once after *all* tiles. Review R5's
counterexample: with a broken ``meta/metadata.json`` and an explicit fail-fast
policy, v1 failed with 0 callbacks while v2 executed every row's flow first.

The per-tile validation is now a domain function used by both the executor's
pre-completion check and ``post_validate``.

Session K0-iii UPDATED every cell to the v1.7.1 layout (#503): with
``save_table_file`` the original table is tile 1 (``divided/0001``, registered
first) and the last data row is tile 0 (``data/``). The table tile is therefore
reached after exactly one row callback, and the property under test becomes
"no tile after the failing EarlyExit tile runs" -- ``divided/0002`` is never
materialized and the callback count stays at the one row before it. Both
counterexamples were pinned against the live v1.7.1 oracle; Session K1 froze
those two v1 runs as the generator cases
``smarttable/valerr__broken_metadata__save_table_file`` (ruling #6 item 8) and
``smarttable/valerr__data_name_too_long__save_table_file``, whose builders live
in ``_generate.py``.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-IRA-6-EP-040 | pre-completion | broken metadata on the table tile | the tile fails with 4002 |
| TC-IRA-6-EP-041 | oracle | same input, frozen v1 run | v1 also fails after the one row before the table tile |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-IRA-6-EV-042 | fail_fast | same input | only the tile-0 row flow ran, no later-tile artifacts |
| TC-IRA-6-EV-043 | healthy tile | untouched fixture | the pre-completed tile still completes |
| TC-IRA-6-EV-044 | invoice | tile invoice invalidated by the EarlyExit rewrite | the table tile fails with 4001, iterations == 2, = frozen v1 run |
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.core.flow import flow
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths
from tests.v2.contract.fixtures import _generate
from tests.v2.contract.frozen import frozen_observed

_FLOW_CALLS: list[int] = []

_BROKEN_METADATA_CASE = "v1/smarttable/valerr__broken_metadata__save_table_file"
_LONG_DATA_NAME_CASE = "v1/smarttable/valerr__data_name_too_long__save_table_file"


@flow
def _counting_flow(paths: InputPaths) -> None:
    """Record that a tile's user flow ran at all."""
    assert paths.inputdata.is_dir()
    _FLOW_CALLS.append(1)


def _overrides() -> dict[str, Any]:
    return {
        "system": {
            "extended_mode": "invoice",
            "save_raw": True,
            "save_nonshared_raw": True,
            "save_thumbnail_image": False,
            "magic_variable": False,
        },
        "execution": {"on_iteration_error": "fail_fast"},
        "smarttable": {"save_table_file": True},
    }


def _materialize(case_id: str, root: Path) -> None:
    """Materialize the registered case's input, defect included."""
    _generate.materialize_case(_generate.oracle_case(case_id), root)


def _divided(observed: dict[str, Any]) -> list[str]:
    """Return the ``divided/NNNN`` tile directories of one frozen observation."""
    return sorted(
        {
            path.split("/")[2]
            for path in observed["output_tree"]["directories"]
            if path.startswith("data/divided/") and path.count("/") >= 3
        },
    )


def _run_v2(root: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.chdir(root)
    _FLOW_CALLS.clear()
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
    )
    return runner.run(_counting_flow, **_overrides())


def test_broken_table_metadata_fails_the_tile__tc_ira_6_ep_040_ev_042(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-IRA-6-EP-040/EV-042: the EarlyExit tile is validated before completing."""
    # Given: a SmartTable case whose table tile carries broken metadata
    root = tmp_path / "smarttable"
    _materialize(_BROKEN_METADATA_CASE, root)

    # When: running with save_table_file and an explicit fail-fast policy
    report = _run_v2(root, monkeypatch)

    # Then: the run failed on the metadata contract, with the v2 catalog code
    assert report.status == "failed"
    job_failed = (root / "data" / "job.failed").read_text(encoding="utf-8")
    assert job_failed.splitlines()[0] == "ErrorCode=4002"

    # And: only the row registered before the table tile ran its flow, and no
    # later tile produced artifacts
    assert _FLOW_CALLS == [1]
    assert not (root / "data" / "divided" / "0002").exists()


def test_v1_also_fails_after_the_row_before_the_table__tc_ira_6_ep_041() -> None:
    """TC-IRA-6-EP-041: the oracle confirms v1 fails on the table tile after one row (v1.7 order)."""
    # Given / When: v1's frozen run of the identical broken case
    observed = frozen_observed(_BROKEN_METADATA_CASE)

    # Then: v1 fails on the table tile, after the one row before it, and never
    # reaches divided/0002
    assert observed["exit_code"] == 1
    assert observed["callback_count"] == 1
    assert _divided(observed) == ["0001"]


def test_healthy_table_tile_still_completes__tc_ira_6_ev_043(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-IRA-6-EV-043: adding validation must not fail a healthy EarlyExit tile."""
    # Given: the untouched SmartTable case
    root = tmp_path / "smarttable"
    _generate.materialize_sut_case("smarttable", root)

    # When: running with save_table_file enabled
    report = _run_v2(root, monkeypatch)

    # Then: the run succeeds and every row tile still executed its flow
    assert report.status == "success", report.error
    assert len(_FLOW_CALLS) == len(report.iterations) - 1


def test_invoice_invalidated_by_early_exit_fails_the_tile__tc_ira_6_ev_044(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-IRA-6-EV-044: the tile invoice is validated on the same boundary.

    The counterexample is specific to the *pre-completion* boundary: the run's
    source invoice is valid, so ``Runner.pre_validate`` passes and one tile is
    planned. v1's EarlyExit rewrite of ``basic.dataName`` is what makes the
    tile invalid, and the check now happens before the tile is recorded as
    completed -- so no row tile's flow ever runs.
    """
    # Given: a SmartTable case whose EarlyExit rewrite will break its own tile
    root = tmp_path / "smarttable"
    _materialize(_LONG_DATA_NAME_CASE, root)

    # When: running with save_table_file and fail-fast
    report = _run_v2(root, monkeypatch)

    # Then: the table tile -- not the run-level pre-validation -- failed
    assert report.status == "failed"
    assert [iteration["status"] for iteration in report.iterations] == ["completed", "failed"]
    assert report.iterations[1]["index"] == 1
    assert report.iterations[1]["error"]["code"] == 4001

    # And: only the row before the table ran its flow; no later tile was materialized
    assert _FLOW_CALLS == [1]
    assert not (root / "data" / "divided" / "0002").exists()
    job_failed = (root / "data" / "job.failed").read_text(encoding="utf-8")
    assert job_failed.splitlines()[0] == "ErrorCode=4001"

    # And: v1.7.1 stops at the same tile with the same callback count
    observed = frozen_observed(_LONG_DATA_NAME_CASE)
    assert observed["exit_code"] == 1
    assert observed["callback_count"] == len(_FLOW_CALLS)
    assert _divided(observed) == ["0001"]
