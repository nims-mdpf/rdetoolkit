"""GA gate (#698): per-mode artifact contracts, error policy and test helpers.

The success cells compare the complete frozen v1 artifact observation (tree,
raw digests, invoices, artifact digests) and the callback count, then assert
the GA observability of a clean run: no ``job.failed``, no diagnostics sidecar,
and a ``report explain`` that fabricates no cause. The test-helper cells run
the opt-in pytest plugin end to end (``rde_case`` in a pytest subprocess) on
each mode's contract input, with the expected files taken from the frozen v1
invoice set rather than from a v2 run.

EP table:
| TC | Outcome | Input | Expected |
|----|---------|-------|----------|
| GA-*-SUCCESS | success, 2 entries x 5 modes | no-op user code | success; v1 tile/callback count; full frozen parity; no job.failed / sidecar; explain has no cause |
| GA-FLOW-RDF-CONTINUE-PARTIAL | continue on RDEFormat (v2-only) | tile 0 of 2 fails | partial; [failed, completed]; warning 3001; no job.failed; sidecar run_status partial for tile 0 |
| GA-FLOW-*-RDE-CASE | rde_case on every mode | marker in a pytest subprocess | success case and failure case (999, node_execution) both pass |

BV / negative table:
| TC | Boundary | Expected |
|----|----------|----------|
| GA-FLOW-*-RDE-CASE (neg) | wrong expect_phase in the same subprocess | that item FAILS with the recorded phase in the message |
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests.v2.contract.fixtures import _generate
from tests.v2.contract.observe import parity_pair
from tests.v2.ga import _harness as ga
from tests.v2.ga._harness import cells


@pytest.mark.parametrize(("entry", "mode"), cells("success"))
def test_success_matches_frozen_v1_and_fabricates_no_cause(
    entry: str, mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GA-*-SUCCESS: v1's artifacts, v1's tile count, and a clean bill of health."""
    # Given: the frozen v1 observation of a successful run of this input
    expected = ga.frozen_ok(mode)

    # When: no-op user code runs through the entry
    function = ga.USER_CODE["ok"][entry] if entry == "callback" else ga.USER_CODE["inflight"][entry]
    run = ga.run_case(entry, mode, tmp_path / mode, monkeypatch, function=function)

    # Then: success over exactly the tiles v1 ran
    assert run.report.status == "success"
    assert run.report.error is None
    assert len(run.report.iterations) == expected["callback_count"]
    assert [iteration["status"] for iteration in run.report.iterations] == ["completed"] * expected["callback_count"]
    if entry == "callback":
        assert run.callback_count() == expected["callback_count"]

    # And: every artifact v1 produced, content included
    actual, expected_view = parity_pair(run.root, expected)
    assert actual == expected_view

    # And: nothing claims a failure
    assert run.job_failed() is None
    assert run.sidecar() is None
    explanation = run.explain()
    assert (explanation["run_status"], explanation["explanations"]) == ("success", [])


@pytest.mark.parametrize(("entry", "mode"), cells("continue_partial", entries=("flow",), modes=("rdeformat",)))
def test_rdeformat_continue_policy_is_partial(
    entry: str, mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GA-FLOW-RDF-CONTINUE-PARTIAL: the v2 continue policy on the two-tile RDEFormat input.

    v1 has no continue policy outside MultiDataTile, so this is a v2-only
    contract (the excelinvoice / smarttable counterparts are
    TC-UM-*-FLOW-CONTINUE-PARTIAL).
    """
    # Given: tile 0 fails, tile 1 succeeds, on_iteration_error=continue
    config = ga.v2_config(mode, on_iteration_error="continue")
    assert ga.tile_count(mode) == 2

    # When
    run = ga.run_case(entry, mode, tmp_path / mode, monkeypatch, function=ga.first_tile_fails_flow, config=config)

    # Then: the later tile still ran; the run is partial, not failed
    assert run.report.status == "partial"
    assert [iteration["status"] for iteration in run.report.iterations] == ["failed", "completed"]
    assert run.report.warnings == [{"code": 3001, "message": "1 iteration(s) failed", "failed_count": 1}]
    assert run.job_failed() is None

    # And: the failed tile is diagnosed in a partial sidecar
    diagnostic = ga.only(run.diagnostics())
    assert (diagnostic["phase"], diagnostic["code"], diagnostic["iteration_index"]) == (
        "node_execution", ga.STRUCTURED_CODE, 0,
    )
    assert diagnostic["node_id"] == "tests.v2.ga.fail_tile_zero"


_RDE_CASE_MODULE = '''
from pathlib import Path

from rdetoolkit.testing import RdeTestResult, rde_case
from tests.v2.ga._harness import probe_flow, structured_flow, v2_config

PROJECT = Path({project!r})
MODE = {mode!r}
CONFIG = v2_config(MODE)
TILES = {tiles!r}


@rde_case(flow=probe_flow, project=PROJECT, config=CONFIG, expect_files={expected_files!r})
def test_success(rde_run: RdeTestResult) -> None:
    assert rde_run.report.mode == MODE
    assert [summary.status for summary in rde_run.iterations] == ["completed"] * TILES
    assert rde_run.diagnostics_path is None


@rde_case(
    flow=structured_flow, project=PROJECT, config=CONFIG, expect_status="failed",
    expect_error_code={code!r}, expect_phase="node_execution", expect_files=("job.failed",),
)
def test_failure(rde_run: RdeTestResult) -> None:
    assert rde_run.diagnostics_path is not None


@rde_case(flow=structured_flow, project=PROJECT, config=CONFIG, expect_status="failed", expect_phase="post_validate")
def test_wrong_phase(rde_run: RdeTestResult) -> None:
    raise AssertionError("the case must fail at setup")
'''


@pytest.mark.parametrize(("entry", "mode"), cells("test_helpers", entries=("flow",)))
def test_rde_case_marker_runs_on_every_mode(entry: str, mode: str, tmp_path: Path) -> None:
    """GA-FLOW-*-RDE-CASE: the pytest plugin's marker, end to end, on each mode."""
    # Given: the mode's contract input as a nested project, and the files v1
    # wrote invoices to, relative to the data root
    assert entry == "flow"
    project = tmp_path / "project"
    _generate.materialize_sut_case(mode, project)
    expected_files = tuple(sorted(path.removeprefix("data/") for path in ga.frozen_ok(mode)["invoices"]))
    assert expected_files
    module = tmp_path / "cases" / f"test_ga_rde_case_{mode}.py"
    module.parent.mkdir()
    module.write_text(
        textwrap.dedent(_RDE_CASE_MODULE).format(
            project=str(project), mode=mode, tiles=ga.tile_count(mode), expected_files=expected_files, code=ga.STRUCTURED_CODE,
        ),
        encoding="utf-8",
    )

    # When: pytest runs the generated cases
    environment = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(_generate.REPOSITORY_ROOT), os.environ.get("PYTHONPATH")]))}
    completed = subprocess.run(  # noqa: S603 -- fixed interpreter and arguments
        [
            sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "--strict-markers", "-o", "addopts=", "-rA",
            "--basetemp", str(tmp_path / "basetemp"), str(module),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )

    # Then: the success and failure cases pass; the wrong phase is reported
    output = completed.stdout
    assert f"PASSED {module.relative_to(tmp_path).as_posix()}::test_success" in output, output
    assert f"PASSED {module.relative_to(tmp_path).as_posix()}::test_failure" in output, output
    assert "test_wrong_phase" in output
    assert "expected diagnostic phase 'post_validate'; the sidecar records ['node_execution']" in output, output
    assert completed.returncode == 1, output
