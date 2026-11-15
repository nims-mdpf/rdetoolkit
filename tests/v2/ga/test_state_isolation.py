"""GA gate (#698): no state survives from one run into the next.

Two shapes, each on 2 entries x 5 modes:

* **success after prior failure** -- a failing run, then a successful run of
  the same input in a fresh root, in the same process. The second run must be
  indistinguishable from a first run: full frozen v1 parity, v1's callback
  count, no ``job.failed`` and no sidecar. A leak in any in-process state
  (call log, registry, mode or invoice caches) breaks one of these.
* **rerun in the same root** -- the same failing-then-successful pair on one
  data root, which is what a re-executed RDE job sees. The second run's own
  state is clean: its report, its per-tile files and its (absent) sidecar,
  and ``report explain`` does not borrow the earlier run's diagnostics. Two
  artifacts are *deliberately* kept, as v1 kept them, and are asserted as
  such: ``job.failed`` (TC-K3-HYG-002, v1 never removed it) and the earlier
  run's run-scoped logs (TC-K3-HYG-003).

EP table:
| TC | Shape | Expected |
|----|-------|----------|
| GA-*-SUCCESS-AFTER-PRIOR-FAILURE | fresh root after a failure | full frozen v1 parity; v1 callback count; no job.failed, no sidecar |
| GA-*-RERUN-NO-STALE-STATE | same root after a failure | report clean; iteration files = this run's tiles only; no sidecar for this run; explain says success; invoices = frozen v1; job.failed + old logs kept (v1 contract) |
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.v2.contract.frozen import frozen_observed
from tests.v2.contract.observe import observe_v2_run, parity_pair, parity_view
from tests.v2.ga import _harness as ga
from tests.v2.ga._harness import cells


def _success_function(entry: str) -> object:
    return ga.USER_CODE["ok"]["callback"] if entry == "callback" else ga.USER_CODE["inflight"]["flow"]


@pytest.mark.parametrize(("entry", "mode"), cells("success_after_prior_failure"))
def test_success_after_prior_failure_in_a_fresh_root(
    entry: str, mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GA-*-SUCCESS-AFTER-PRIOR-FAILURE: a failed run leaves nothing for the next run to inherit."""
    # Given: a failed run of this input
    failed = ga.run_case(entry, mode, tmp_path / "first", monkeypatch, function=ga.USER_CODE["structured_error"][entry])
    assert failed.report.status == "failed"

    # When: the same process runs the input again, successfully, in a new root
    run = ga.run_case(entry, mode, tmp_path / "second", monkeypatch, function=_success_function(entry))  # type: ignore[arg-type]

    # Then: the second run is exactly a first successful run
    expected = ga.frozen_ok(mode)
    assert run.report.status == "success"
    assert run.report.error is None
    assert run.report.run_id != failed.report.run_id
    assert [iteration["status"] for iteration in run.report.iterations] == ["completed"] * expected["callback_count"]
    if entry == "callback":
        assert run.callback_count() == expected["callback_count"]
    else:
        # ``seq`` is run-global: it restarts at 1 for a new run, never continues the old one.
        assert [
            [call["seq"] for call in iteration["node_calls"]] for iteration in run.report.iterations
        ] == [[index + 1] for index in range(expected["callback_count"])]
    actual, expected_view = parity_pair(run.root, expected)
    assert actual == expected_view
    assert run.job_failed() is None
    assert run.sidecar() is None


@pytest.mark.parametrize(("entry", "mode"), cells("rerun_no_stale_state"))
def test_rerun_in_the_same_root_has_no_stale_run_state(
    entry: str, mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GA-*-RERUN-NO-STALE-STATE: the rerun's own artifacts describe the rerun only."""
    # Given: a failed run in this root
    root = tmp_path / mode
    failed = ga.run_case(entry, mode, root, monkeypatch, function=ga.USER_CODE["structured_error"][entry])
    first_job_failed = failed.job_failed()
    assert failed.sidecar() is not None
    # Callback markers count invocations of the second run only.
    (root / ".callback_calls").unlink(missing_ok=True)

    # When: the job is re-executed successfully on the same root
    run = ga.run_case(entry, mode, root, monkeypatch, function=_success_function(entry), materialize=False)  # type: ignore[arg-type]

    # Then: the rerun's report describes the rerun only
    tiles = ga.tile_count(mode)
    assert run.report.status == "success"
    assert run.report.error is None
    assert run.report.warnings == []
    assert [iteration["index"] for iteration in run.report.iterations] == list(range(tiles))
    assert [iteration["status"] for iteration in run.report.iterations] == ["completed"] * tiles
    if entry == "callback":
        assert run.callback_count() == tiles

    # And: the per-tile files are this run's, one per tile
    iteration_files = sorted(path.name for path in (run.logs / "iterations").iterdir())
    assert iteration_files == [f"iteration_{index}.json" for index in range(tiles)]
    for name in iteration_files:
        detail = json.loads((run.logs / "iterations" / name).read_text(encoding="utf-8"))
        assert detail["status"] == "completed", detail

    # And: no diagnostics are attributed to the rerun, and explain does not borrow them
    assert run.sidecar() is None
    assert failed.sidecar_path.exists(), "run-scoped logs are kept (TC-K3-HYG-003)"
    explanation = run.explain()
    assert (explanation["run_id"], explanation["run_status"], explanation["explanations"]) == (
        run.report.run_id, "success", [],
    )

    # And: the published invoices are v1's, not the failed run's leftovers
    assert observe_v2_run(root)["invoices"] == parity_view(ga.frozen_ok(mode))["invoices"]

    # And: job.failed is deliberately left in place, as v1 left it (TC-K3-HYG-002)
    assert first_job_failed == frozen_observed(f"v1/{mode}/usererr")["job_failed_text"]
    assert run.job_failed() == first_job_failed
