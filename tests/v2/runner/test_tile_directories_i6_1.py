"""Per-tile directory contract for Session I6-1 (Design §6.3 addendum).

v1 ``workflows.generate_folder_paths_iterator`` creates twelve directories per
tile; the v2 iterator created only ten, so ``temp/`` and ``invoice_patch/``
were missing from every frozen output tree. The expected directory names are
never hand-written here: they are observed by running the v1 iterator itself,
which keeps this test a golden comparison rather than a snapshot.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-I6-1-EP-001 | tile 0 | ``resolve_tile_paths(data, 0)`` created | exactly the v1 root-tile directory set (12) |
| TC-I6-1-EP-002 | tile >= 1 | ``resolve_tile_paths(data, 1)`` created | exactly the v1 ``divided/0001`` set (12) |
| TC-I6-1-EP-003 | 5 modes | ``iterate_tiles`` over each real fixture | the iterator creates exactly the 12 per tile |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-I6-1-EV-004 | API surface | ``OutputContext`` | no ``temp`` / ``invoice_patch`` attribute (ruling #3) |
| TC-I6-1-EV-005 | API surface | ``OutputContext.from_resource_paths`` | accepts the 12-field bundle without leaking the 2 |
| TC-I6-1-EV-006 | tile isolation | tile 0 vs tile 1 | new directories differ and never create ``divided/0000`` |
| TC-I6-1-EV-007 | idempotence | ``iterate_tiles`` run twice | no failure and no extra directory |
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from rdetoolkit.runner.iterator import iterate_tiles
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.paths import TileOutputPaths, resolve_tile_paths
from rdetoolkit.types import OutputContext
from tests.v2.contract.fixtures import _generate

_MODES = {
    "invoice": ModeKind.invoice,
    "excelinvoice": ModeKind.excelinvoice,
    "multidatatile": ModeKind.multidatatile,
    "rdeformat": ModeKind.rdeformat,
    "smarttable": ModeKind.smarttable,
}
_V1_TILE_DIRECTORY_COUNT = 12


def _observe_v1_tile_directories(root: Path) -> tuple[frozenset[str], frozenset[str]]:
    """Return the v1 per-tile directory names for tile 0 and tile 1.

    The v1 iterator creates its directories as a side effect of resolving
    ``DirectoryOps`` paths, so running it is the only faithful way to learn
    which directories the contract requires.
    """
    from rdetoolkit.workflows import generate_folder_paths_iterator  # noqa: PLC0415 -- v1 oracle

    data_root = root / "data"
    (data_root / "invoice").mkdir(parents=True)
    (data_root / "tasksupport").mkdir(parents=True)
    invoice_org = data_root / "invoice" / "invoice.json"
    invoice_org.write_text("{}", encoding="utf-8")
    schema = data_root / "tasksupport" / "invoice.schema.json"
    schema.write_text("{}", encoding="utf-8")

    previous = Path.cwd()
    os.chdir(root)
    try:
        list(generate_folder_paths_iterator([(), ()], invoice_org, schema))
    finally:
        os.chdir(previous)

    root_tile = frozenset(
        path.name
        for path in data_root.iterdir()
        if path.is_dir() and path.name not in {"invoice", "tasksupport", "divided"}
    ) | {"invoice"}
    divided_tile = frozenset(path.name for path in (data_root / "divided" / "0001").iterdir() if path.is_dir())
    return root_tile, divided_tile


def _created_directories(base: Path, tile_root: Path) -> frozenset[str]:
    return frozenset(path.name for path in tile_root.iterdir() if path.is_dir()) if tile_root.exists() else frozenset()


def _tile_root(base_output: Path, idx: int) -> Path:
    return base_output if idx == 0 else base_output / "divided" / f"{idx:04d}"


def _create_all(paths: TileOutputPaths) -> None:
    for name in TileOutputPaths.__dataclass_fields__:
        getattr(paths, name).mkdir(parents=True, exist_ok=True)


def test_root_tile_directories_match_the_v1_set__tc_i6_1_ep_001(tmp_path: Path) -> None:
    """TC-I6-1-EP-001: tile 0 owns exactly the twelve v1 directories."""
    # Given: the directory set observed from the v1 iterator itself
    expected, _ = _observe_v1_tile_directories(tmp_path / "v1")

    # When: creating every directory the v2 tile path bundle exposes
    base_output = tmp_path / "v2" / "data"
    _create_all(resolve_tile_paths(base_output, 0))

    # Then: the sets are equal and the contract size is twelve
    assert _created_directories(base_output, base_output) == expected
    assert len(expected) == _V1_TILE_DIRECTORY_COUNT


def test_divided_tile_directories_match_the_v1_set__tc_i6_1_ep_002(tmp_path: Path) -> None:
    """TC-I6-1-EP-002: tile 1 owns the same twelve directories under divided/0001."""
    # Given: the divided-tile directory set observed from v1
    _, expected = _observe_v1_tile_directories(tmp_path / "v1")

    # When: creating the v2 tile-1 directories
    base_output = tmp_path / "v2" / "data"
    _create_all(resolve_tile_paths(base_output, 1))

    # Then: the divided tile mirrors the v1 set
    assert _created_directories(base_output, _tile_root(base_output, 1)) == expected
    assert len(expected) == _V1_TILE_DIRECTORY_COUNT


@pytest.mark.parametrize("mode", sorted(_MODES))
def test_every_mode_creates_twelve_tile_directories__tc_i6_1_ep_003(mode: str, tmp_path: Path) -> None:
    """TC-I6-1-EP-003: all five modes create exactly the v1 twelve-directory tile.

    The comparison is an equality on the directories the *iterator* creates:
    a fixture's own input directories (``inputdata``, ``tasksupport``, ...)
    already exist beforehand and ``divided`` is a container, not a tile
    directory, so both are subtracted before comparing.
    """
    # Given: a real mode fixture and the v1 directory set
    expected, _ = _observe_v1_tile_directories(tmp_path / "v1")
    root = tmp_path / mode
    _generate.materialize_sut_case(mode, root)
    base_output = root / "data"
    preexisting = _created_directories(base_output, base_output)

    # When: enumerating tiles through the v2 iterator
    tiles = list(
        iterate_tiles(
            _MODES[mode],
            base_output / "inputdata",
            base_output / "temp",
            base_output,
        ),
    )

    # Then: every tile owns exactly the twelve v1 directories
    assert tiles
    for info, _paths, _out in tiles:
        tile_root = _tile_root(base_output, info.index)
        created = _created_directories(base_output, tile_root)
        before = preexisting if info.index == 0 else frozenset()
        assert (created - before) - {"divided"} == expected - before
        assert expected <= created


def test_output_context_does_not_expose_the_two_new_directories__tc_i6_1_ev_004() -> None:
    """TC-I6-1-EV-004: the directories are a contract, the fields are not (ruling #3)."""
    # Given: the canonical output context type
    fields = set(OutputContext.__dataclass_fields__)

    # When/Then: temp and invoice_patch stay off the public API surface
    assert "temp" not in fields
    assert "invoice_patch" not in fields
    assert not hasattr(OutputContext, "temp")
    assert not hasattr(OutputContext, "invoice_patch")


def test_output_context_factory_ignores_the_two_new_directories__tc_i6_1_ev_005(tmp_path: Path) -> None:
    """TC-I6-1-EV-005: the factory accepts the 12-field bundle and exposes 10."""
    # Given: a full v2 tile path bundle
    paths = resolve_tile_paths(tmp_path / "data", 0)
    assert {"temp", "invoice_patch"} <= set(TileOutputPaths.__dataclass_fields__)

    # When: adapting it to the public output context
    out = OutputContext.from_resource_paths(paths)

    # Then: the two directories are unreachable through the context
    assert not hasattr(out, "temp")
    assert not hasattr(out, "invoice_patch")
    assert out.raw == paths.raw


def test_tile_zero_and_one_do_not_share_new_directories__tc_i6_1_ev_006(tmp_path: Path) -> None:
    """TC-I6-1-EV-006: divided tiles own their own temp/invoice_patch, and 0000 is never created."""
    # Given: the tile 0 and tile 1 path bundles
    base_output = tmp_path / "data"
    tile0 = resolve_tile_paths(base_output, 0)
    tile1 = resolve_tile_paths(base_output, 1)

    # When: creating both tiles
    _create_all(tile0)
    _create_all(tile1)

    # Then: the new directories are distinct and no divided/0000 exists
    assert tile0.temp != tile1.temp
    assert tile0.invoice_patch != tile1.invoice_patch
    assert tile1.temp == base_output / "divided" / "0001" / "temp"
    assert not (base_output / "divided" / "0000").exists()


def test_repeated_iteration_creates_no_extra_directory__tc_i6_1_ev_007(tmp_path: Path) -> None:
    """TC-I6-1-EV-007: re-running the iterator is idempotent for tile directories."""
    # Given: an invoice fixture already iterated once
    root = tmp_path / "invoice"
    _generate.materialize_sut_case("invoice", root)
    base_output = root / "data"
    args = (ModeKind.invoice, base_output / "inputdata", base_output / "temp", base_output)
    first = list(iterate_tiles(*args))
    snapshot = _created_directories(base_output, base_output)

    # When: iterating a second time over the same root
    second = list(iterate_tiles(*args))

    # Then: neither the tile count nor the directory set changed
    assert len(second) == len(first)
    assert _created_directories(base_output, base_output) == snapshot
