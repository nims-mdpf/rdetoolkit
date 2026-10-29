"""MultiDataTile real-canary FLOW parity for Session I6-B (ruling #1).

The synthetic MultiDataTile FLOW-OK cell is pinned to full artifact parity by
Session I6-1. This module extends the same comparison to the imported
real-canary family (a battery structured program), whose ``tasksupport2``
material overlays ``system.extended_mode: MultiDataTile`` and enables the magic
variable and thumbnail switches the synthetic fixture leaves off.

Session I-REVIEW-A (review F2) made this cell run with **no overrides at all**:
production discovery now reaches ``data_root/tasksupport/rdeconfig.yaml``, so
the canary is configured by the file the structured program ships, exactly as a
real RDE run is.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-I6-B-EP-010 | canary FLOW | real MultiDataTile canary + its effective config | observation equals ``expected/canary/multidatatile/ok.json`` |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-I6-B-EV-011 | config removed | same canary without ``data/tasksupport/rdeconfig.yaml`` | observation differs — discovery is load-bearing |
| TC-I6-B-EV-012 | projection | frozen ``case.effective_config`` | record reproduces, ``ignore_errors=False`` projects to ``fail_fast`` |
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rdetoolkit.runner.lifecycle import Runner
from tests.v2.contract.fixtures import _generate
from tests.v2.modes.canary_support import (
    canary_flow,
    discovered_config,
    frozen_canary,
    run_canary,
)
from tests.v2.contract.observe import parity_pair

_MODE = "multidatatile"
#: Tiles the frozen canary observation records for this family.
_CANARY_TILE_COUNT = 1


def test_canary_flow_matches_the_frozen_v1_observation__tc_i6_b_ep_010(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-B-EP-010: the real MultiDataTile canary reaches full artifact parity."""
    # Given: the imported canary family and the configuration v1 ran it with
    root = tmp_path / _MODE
    root.mkdir()
    expected = frozen_canary(_MODE)["observed"]

    # When: running the eager flow through the v2 Runner
    report = run_canary(_MODE, root, monkeypatch)

    # Then: every compared artifact key equals the frozen v1 observation
    assert report.status == "success"
    assert len(report.iterations) == _CANARY_TILE_COUNT
    actual, expected_view = parity_pair(root, expected)
    assert actual == expected_view


def test_removing_the_tasksupport_config_breaks_parity__tc_i6_b_ev_011(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-B-EV-011 (UPDATED, ruling #4): the discovered config is load-bearing.

    The previous version proved that *overrides* were load-bearing, which only
    held because a v2 flow entry could not find ``data/tasksupport`` at all
    (review F2). Now that discovery is production behavior, the equivalent
    falsification is to delete the file the program ships: parity must break.
    """
    # Given: the same canary family with its tasksupport configuration removed
    root = tmp_path / _MODE
    root.mkdir()
    expected = frozen_canary(_MODE)["observed"]
    _generate._materialize_canary_case(_MODE, root)  # noqa: SLF001 -- shared canary assembly
    (root / "data" / "tasksupport" / "rdeconfig.yaml").unlink()
    monkeypatch.chdir(root)
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
    )

    # When: running the eager flow without the program's own configuration
    report = runner.run(canary_flow)

    # Then: the run still succeeds but its artifacts are not the v1 ones
    assert report.status == "success", report.error
    actual, expected_view = parity_pair(root, expected)
    assert actual != expected_view


def test_recorded_effective_config_is_reproducible__tc_i6_b_ev_012() -> None:
    """TC-I6-B-EV-012: the frozen record round-trips and projects its error policy."""
    # Given: the provenance the generator froze alongside the observation
    record = frozen_canary(_MODE)["case"]["effective_config"]
    assert record["source"]["path"] == "data/tasksupport/rdeconfig.yaml"
    assert record["config"]["multidata_tile"]["ignore_errors"] is False

    # When: re-deriving it from the committed canary configuration file
    rederived = _generate.canary_effective_config_record(_MODE)

    # Then: the record is reproducible and its v1 switches survive the projection
    assert rederived == record
    # And: production discovery of the shipped file reproduces those switches
    discovered = discovered_config(_MODE)
    assert discovered.system.extended_mode == "MultiDataTile"
    assert discovered.system.magic_variable is True
    # ignore_errors=False is the v1 fail-fast policy (contracts.md §I6-B).
    assert discovered.execution.on_iteration_error == "fail_fast"
