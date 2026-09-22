"""Config passthrough to the legacy input checkers (Session I6-1, ruling #6).

``domain.mode.selected_input_checker`` accepts a v1 ``Config`` and reads
``config.smarttable.save_table_file`` from it. The v2 iterator passed ``None``,
so that setting was unreachable and the SmartTable tile layout could never
follow the configuration. This session only transports the value; the
SmartTable-specific consequences belong to Session I6-C.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-I6-1-EP-040 | default | ``save_table_file=False`` | tile layout identical to ``config=None`` |
| TC-I6-1-EP-041 | enabled | ``save_table_file=True`` | table file becomes tile 0, tiles = rows + 1 |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-I6-1-EV-042 | omitted | ``config`` not supplied | unchanged legacy behavior |
| TC-I6-1-EV-043 | other mode | invoice mode with the flag on | tile layout unaffected |
| TC-I6-1-EV-044 | planning | plan created for smarttable | the planner forwards the run config |
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rdetoolkit.api.request import FlowTarget, RunRequest
from rdetoolkit.core.flow import flow
from rdetoolkit.domain.invoice_service import InvoiceService
from rdetoolkit.runner.iterator import iterate_tiles
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.planner import RunPlanner
from rdetoolkit.types import InputPaths, RdeConfig
from tests.v2.contract.fixtures import _generate

_SMARTTABLE_ROWS = 3


@flow
def _noop_flow(paths: InputPaths) -> None:
    """Consume one tile without writing anything."""
    assert paths.inputdata.is_dir()


def _tiles(root: Path, mode: ModeKind, config: RdeConfig | None, *, suffix: str) -> list[tuple[Path, ...]]:
    """Enumerate rawfile tuples for one mode under an isolated output root."""
    data = root / "data"
    return [
        paths.rawfiles
        for _info, paths, _out in iterate_tiles(
            mode,
            data / "inputdata",
            data / f"temp{suffix}",
            data,
            config=config,
        )
    ]


def _prepare(tmp_path: Path, mode: str) -> Path:
    root = tmp_path / mode
    _generate.materialize_sut_case(mode, root)
    return root


def _config(*, save_table_file: bool) -> RdeConfig:
    return RdeConfig(smarttable={"save_table_file": save_table_file})


def test_default_config_keeps_the_legacy_layout__tc_i6_1_ep_040(tmp_path: Path) -> None:
    """TC-I6-1-EP-040: the default configuration changes nothing."""
    # Given: a SmartTable fixture enumerated without a config
    root = _prepare(tmp_path, "smarttable")
    baseline = _tiles(root, ModeKind.smarttable, None, suffix="_none")

    # When: enumerating with the default configuration
    with_default = _tiles(root, ModeKind.smarttable, _config(save_table_file=False), suffix="_default")

    # Then: the tile layout is unchanged
    assert [len(tile) for tile in with_default] == [len(tile) for tile in baseline]
    assert len(with_default) == _SMARTTABLE_ROWS
    assert all(tile[0].name.startswith("fsmarttable_") for tile in with_default)


def test_save_table_file_reaches_the_checker__tc_i6_1_ep_041(tmp_path: Path) -> None:
    """TC-I6-1-EP-041: save_table_file=True changes the SmartTable tile layout."""
    # Given: a SmartTable fixture
    root = _prepare(tmp_path, "smarttable")

    # When: enumerating with save_table_file enabled
    tiles = _tiles(root, ModeKind.smarttable, _config(save_table_file=True), suffix="_on")

    # Then: the original table occupies tile 0 and the rows follow
    assert len(tiles) == _SMARTTABLE_ROWS + 1
    assert tiles[0][0].name == "smarttable_full.xlsx"
    assert all(tile[0].name.startswith("fsmarttable_") for tile in tiles[1:])


def test_config_argument_is_optional__tc_i6_1_ev_042(tmp_path: Path) -> None:
    """TC-I6-1-EV-042: omitting config keeps the pre-I6-1 call signature working."""
    # Given: a SmartTable fixture
    root = _prepare(tmp_path, "smarttable")
    data = root / "data"

    # When: calling the iterator positionally, without a config
    tiles = list(iterate_tiles(ModeKind.smarttable, data / "inputdata", data / "temp", data))

    # Then: the legacy tile layout is produced
    assert len(tiles) == _SMARTTABLE_ROWS


def test_other_modes_ignore_the_smarttable_flag__tc_i6_1_ev_043(tmp_path: Path) -> None:
    """TC-I6-1-EV-043: the SmartTable flag does not leak into other modes."""
    # Given: an invoice fixture
    root = _prepare(tmp_path, "invoice")

    # When: enumerating invoice tiles with the SmartTable flag enabled
    enabled = _tiles(root, ModeKind.invoice, _config(save_table_file=True), suffix="_on")
    disabled = _tiles(root, ModeKind.invoice, _config(save_table_file=False), suffix="_off")

    # Then: the invoice layout is identical either way
    assert [len(tile) for tile in enabled] == [len(tile) for tile in disabled]
    assert len(enabled) == 1


def test_planner_forwards_the_run_config__tc_i6_1_ev_044(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-1-EV-044: the planner hands the effective config to tile creation."""
    # Given: a SmartTable fixture and a plan built with save_table_file enabled
    root = _prepare(tmp_path, "smarttable")
    monkeypatch.chdir(root)
    data = root / "data"
    planner = RunPlanner(
        inputdata_path=data / "inputdata",
        unpacked_dir_path=data / "temp",
        run_id_factory=lambda: "run",
        invoice_service=InvoiceService(),
    )
    config = _config(save_table_file=True)

    # When: creating a plan and consuming its tiles
    plan = planner.create(
        RunRequest(root=root, target=FlowTarget(function=_noop_flow), config_source=config),
        config=config,
        mode=ModeKind.smarttable,
        data_root=data,
    )
    tiles = list(plan.tiles)

    # Then: the plan reflects the configured SmartTable layout
    assert len(tiles) == _SMARTTABLE_ROWS + 1
    assert tiles[0].paths.rawfiles[0].name == "smarttable_full.xlsx"
