"""SmartTable real-canary FLOW parity for Session I6-C (ruling #5).

The synthetic SmartTable FLOW-OK cell is already pinned to full artifact parity
in ``tests/v2/contract/test_unified_matrix.py``. This module extends the same
comparison to the imported real-canary family (a battery-electrolyte structured
program), which exercises material the synthetic fixture cannot: a real
``smarttable_*.csv`` alongside a zip of measurement files, a Japanese schema,
and an ``rdeconfig.yaml`` shipped inside ``data/tasksupport``. It is also the
end-to-end proof that the ported invoice builder (this session) produces the
same ``invoice.json`` v1 produced on real input.

Session I-REVIEW-A (review F2) made this cell run with **no overrides at all**:
production discovery now reaches ``data_root/tasksupport/rdeconfig.yaml``, so
the canary is configured by the file the structured program ships, exactly as a
real RDE run is.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-I6-C-EP-050 | canary FLOW | real SmartTable canary + its effective config | observation equals ``expected/canary/smarttable/ok.json`` |
| TC-I6-C-EP-051 | canary invoice | same run | the row values reached ``data/invoice/invoice.json`` |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-I6-C-EV-052 | config removed | same canary without ``data/tasksupport/rdeconfig.yaml`` | observation differs — discovery is load-bearing |
| TC-I6-C-EV-053 | projection | frozen ``case.effective_config`` | the recorded v1 config is reproducible and non-default |
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rdetoolkit.config.normalize import ConfigNormalizer
from rdetoolkit.runner.lifecycle import Runner
from tests.v2.contract.fixtures import _generate
from tests.v2.modes.canary_support import (
    canary_flow,
    discovered_config,
    frozen_canary,
    run_canary,
)
from tests.v2.contract.observe import observe_v2_run, parity_pair

_MODE = "smarttable"
#: Tiles the frozen canary observation records for this family (one row).
_CANARY_TILE_COUNT = 1


def test_canary_flow_matches_the_frozen_v1_observation__tc_i6_c_ep_050(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-C-EP-050: the real SmartTable canary reaches full artifact parity."""
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


def test_canary_tile_invoice_carries_the_row_values__tc_i6_c_ep_051(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-C-EP-051: the ported builder wrote v1's invoice for the real row."""
    # Given: the frozen invoice v1 produced for the single canary row
    root = tmp_path / _MODE
    root.mkdir()
    expected_invoices = frozen_canary(_MODE)["observed"]["invoices"]

    # When: running the same input through the v2 Runner
    run_canary(_MODE, root, monkeypatch)

    # Then: the tile invoice is byte-equal to the frozen v1 one
    observed = observe_v2_run(root)["invoices"]
    assert list(observed) == list(expected_invoices)
    assert observed == expected_invoices


def test_removing_the_tasksupport_config_breaks_parity__tc_i6_c_ev_052(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-C-EV-052 (UPDATED, ruling #4): the discovered config is load-bearing.

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


def test_recorded_effective_config_is_reproducible__tc_i6_c_ev_053() -> None:
    """TC-I6-C-EV-053: the frozen record round-trips and is not the default."""
    # Given: the provenance the generator froze alongside the observation
    record = frozen_canary(_MODE)["case"]["effective_config"]
    assert record["source"]["path"] == "data/tasksupport/rdeconfig.yaml"

    # When: re-deriving it from the committed canary configuration file
    rederived = _generate.canary_effective_config_record(_MODE)

    # Then: the record is reproducible and carries non-default switches
    assert rederived == record
    # And: production discovery of the shipped file reproduces those switches
    discovered = discovered_config(_MODE)
    assert discovered.system.save_nonshared_raw is False
    assert discovered.smarttable.save_table_file is False
    assert discovered != ConfigNormalizer().normalize(None, root=Path("/nonexistent"), origin="v2")
