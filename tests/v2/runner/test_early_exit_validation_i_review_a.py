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

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-IRA-6-EP-040 | pre-completion | broken metadata on the table tile | the tile fails with 4002 |
| TC-IRA-6-EP-041 | oracle | same input through v1 | v1 also fails with zero callbacks |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-IRA-6-EV-042 | fail_fast | same input | no flow call and no later-tile artifacts |
| TC-IRA-6-EV-043 | healthy tile | untouched fixture | the pre-completed tile still completes |
| TC-IRA-6-EV-044 | invoice | tile invoice invalidated by the EarlyExit rewrite | the tile fails with 4001, iterations == 1 |
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.core.flow import flow
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths
from tests.v2.contract.fixtures import _generate

_FLOW_CALLS: list[int] = []

_V1_ORACLE_WORKER = """
import json, os, sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, os.getcwd())
from rdetoolkit.models.config import Config, MultiDataTileSettings, SmartTableSettings, SystemSettings
from rdetoolkit.workflows import run as v1_run

calls = []
config = Config(
    system=SystemSettings(
        extended_mode=None,
        save_raw=True,
        save_nonshared_raw=True,
        save_thumbnail_image=False,
        magic_variable=False,
    ),
    multidata_tile=MultiDataTileSettings(ignore_errors=False),
    smarttable=SmartTableSettings(save_table_file=True),
)

os.chdir(root)
exit_code = 0
try:
    v1_run(custom_dataset_function=lambda a, b: calls.append(1), config=config)
except SystemExit as error:
    exit_code = int(error.code or 0)

data_root = root / "data"
job_failed = data_root / "job.failed"
observation = {
    "exit_code": exit_code,
    "callback_count": len(calls),
    "job_failed_code": (
        job_failed.read_text(encoding="utf-8").splitlines()[0] if job_failed.exists() else None
    ),
    "divided": sorted(path.name for path in (data_root / "divided").iterdir())
    if (data_root / "divided").exists()
    else [],
}
(root / ".early_exit_observation.json").write_text(json.dumps(observation), encoding="utf-8")
"""


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


def _break_table_tile_metadata(root: Path) -> None:
    """Leave a schema-invalid ``meta/metadata.json`` on the EarlyExit tile.

    With ``save_table_file`` on, the SmartTable checker registers the original
    table as tile 0, so ``data/meta`` is that tile's metadata directory.
    """
    metadata = root / "data" / "meta" / "metadata.json"
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(json.dumps({"constant": {}, "variable": "not-a-list"}), encoding="utf-8")


#: Longest ``basic.dataName`` the constrained fixture schema accepts. The seed
#: invoice's ``"test-dataset"`` (12) fits; the table filename
#: ``"smarttable_full.xlsx"`` (20) does not.
_DATA_NAME_MAX_LENGTH = 15


def _constrain_data_name(root: Path) -> None:
    """Make the EarlyExit rewrite -- and only it -- produce an invalid tile.

    The run's source invoice is valid, so ``Runner.pre_validate`` passes. v1's
    EarlyExit then rewrites ``basic.dataName`` to the table's filename, which
    this schema rejects: the tile becomes invalid *between* run-level
    validation and the tile's completion, which is exactly the boundary
    ruling #6 moved.
    """
    schema_path = root / "data" / "tasksupport" / "invoice.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["properties"]["basic"] = {
        "type": "object",
        "properties": {"dataName": {"type": "string", "maxLength": _DATA_NAME_MAX_LENGTH}},
    }
    schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")


def _run_v2(root: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.chdir(root)
    _FLOW_CALLS.clear()
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
    )
    return runner.run(_counting_flow, **_overrides())


def _observe_v1(root: Path) -> dict[str, Any]:
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _V1_ORACLE_WORKER, str(root)],
        cwd=_generate.REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    observation_path = root / ".early_exit_observation.json"
    if not observation_path.exists():
        message = f"v1 EarlyExit oracle failed: {completed.stderr[-1500:]}"
        raise RuntimeError(message)
    result: dict[str, Any] = json.loads(observation_path.read_text(encoding="utf-8"))
    return result


def test_broken_table_metadata_fails_the_tile__tc_ira_6_ep_040_ev_042(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-IRA-6-EP-040/EV-042: the EarlyExit tile is validated before completing."""
    # Given: a SmartTable case whose table tile carries broken metadata
    root = tmp_path / "smarttable"
    _generate.materialize_sut_case("smarttable", root)
    _break_table_tile_metadata(root)

    # When: running with save_table_file and an explicit fail-fast policy
    report = _run_v2(root, monkeypatch)

    # Then: the run failed on the metadata contract, with the v2 catalog code
    assert report.status == "failed"
    job_failed = (root / "data" / "job.failed").read_text(encoding="utf-8")
    assert job_failed.splitlines()[0] == "ErrorCode=4002"

    # And: no user flow ran, and no later tile produced artifacts
    assert _FLOW_CALLS == []
    assert not (root / "data" / "divided").exists()


def test_v1_also_fails_with_zero_callbacks__tc_ira_6_ep_041(tmp_path: Path) -> None:
    """TC-IRA-6-EP-041: the oracle confirms v1 never reaches a callback."""
    # Given: the identical broken case
    root = tmp_path / "v1"
    _generate.materialize_sut_case("smarttable", root)
    _break_table_tile_metadata(root)

    # When: running v1 itself in an isolated process
    observed = _observe_v1(root)

    # Then: v1 fails before any dataset callback and leaves no divided tiles
    assert observed["exit_code"] == 1
    assert observed["callback_count"] == 0
    assert observed["divided"] == []


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
    _generate.materialize_sut_case("smarttable", root)
    _constrain_data_name(root)

    # When: running with save_table_file and fail-fast
    report = _run_v2(root, monkeypatch)

    # Then: the tile -- not the run-level pre-validation -- failed
    assert report.status == "failed"
    assert len(report.iterations) == 1
    assert report.iterations[0]["status"] == "failed"
    assert report.iterations[0]["error"]["code"] == 4001

    # And: no user flow ran and no later tile was materialized
    assert _FLOW_CALLS == []
    assert not (root / "data" / "divided").exists()
    job_failed = (root / "data" / "job.failed").read_text(encoding="utf-8")
    assert job_failed.splitlines()[0] == "ErrorCode=4001"
