"""Golden directory-tree parity tests (TC-GOLD-001/003..006).

Design authority: local/develop/v2/Design.md §6.3, §6.4
Session authority: local/develop/v2/tasks/session_b2.md (B2.3)

Golden test principle (non-negotiable, Design §6.4 / session_b2.md):
    The "expected" directory set is produced by running v1 code, never by a
    hand-written snapshot directory list. Until Session K1 the v1 run happened
    here (the v1 orchestration loop / ``generate_folder_paths_iterator`` over a
    fixture under ``tmp_path``). Session K1 ruling #4 retired those live runs:
    the expectation is now the output tree ``_generate.py`` froze from the v1
    oracle for the matching contract case (``tests/v2/contract/frozen.py``), so
    it is still v1-produced, and a case whose snapshot awaits the freeze ritual
    skips as "pending freeze".

    TC-GOLD-002 (an ExcelInvoice cell whose "v1" side was a directory-contract
    stub, not a v1 run) was deleted by the same ruling; real ExcelInvoice tree
    parity is the frozen-corpus comparison of the unified matrix
    (TC-UM-XLS-FLOW-OK / CB-V2-OK / CB-ENTRY-OK).
"""
from __future__ import annotations

from pathlib import Path

from rdetoolkit.runner.paths import resolve_tile_paths
from tests.v2.contract.frozen import frozen_observed

# v1 RdeOutputResourcePath field -> on-disk directory basename
# (rdetoolkit.types.OutputContext docstring "v1 field coverage" table).
_OUTPUT_FIELD_TO_DIRNAME = {
    "struct": "structured",
    "meta": "meta",
    "main_image": "main_image",
    "other_image": "other_image",
    "thumbnail": "thumbnail",
    "attachment": "attachment",
    "nonshared_raw": "nonshared_raw",
    "raw": "raw",
    "invoice": "invoice",
    "logs": "logs",
}


def _frozen_directories(case_id: str) -> set[str]:
    """Return the ``data``-relative directories v1 created for a frozen case."""
    return set(frozen_observed(case_id)["output_tree"]["directories"])


def _tile_relative(idx: int) -> str:
    return "data" if idx == 0 else f"data/divided/{idx:04d}"


class TestDirTreeParityInvoiceMode:
    """TC-GOLD-001 / TC-GOLD-004 / TC-GOLD-005: invoice mode, single tile (idx=0)."""

    def test_invoice_mode_v2_paths_match_v1_directory_set(self, tmp_path: Path) -> None:
        """Every v2 resolve_tile_paths(idx=0) field must equal the v1-created path.

        TC-GOLD-004: the expected tree is the one v1 created for the frozen
        ``invoice/ok`` contract run, never a hand-written list of directory names.
        TC-GOLD-005: idx=0 paths must contain no "divided" segment, identical
        to the v1 base-tile layout.
        """
        # Given: the directories v1 created for a single-tile invoice run
        v1_directories = _frozen_directories("v1/invoice/ok")

        # When: resolving the v2 paths of tile 0
        resource_paths = resolve_tile_paths(tmp_path / "data", 0)

        # Then: every field names the directory v1 created, outside divided/
        for field, dirname in _OUTPUT_FIELD_TO_DIRNAME.items():
            assert f"data/{dirname}/" in v1_directories, f"v1 must have produced data/{dirname}/"
            v2_path = getattr(resource_paths, field)
            assert "divided" not in str(v2_path), f"idx=0 must not use divided/: {field} -> {v2_path}"
            assert v2_path == tmp_path / "data" / dirname, f"{field}: v2 path {v2_path} != v1 path data/{dirname}"


class TestDirTreeParityMultidatatitleMode:
    """TC-GOLD-003: multidatatile mode (3 tiles), divided/ directory set parity."""

    def test_multidatatile_mode_v2_paths_match_v1_directory_set(self, tmp_path: Path) -> None:
        """MultiDataTile mode (3 tiles) must produce matching divided/ directory sets.

        The expected tree is the one v1 created for the frozen three-tile
        MultiDataTile family under ``ignore_errors`` -- a frozen three-tile run
        in which v1 reached every tile even though tile 1 failed
        (``multidatatile/ok__three_inputs`` is the all-success counterpart;
        TC-GOLD-004 principle).
        """
        # Given: the directories v1 created for three MultiDataTile tiles
        v1_directories = _frozen_directories("v1/multidatatile/tilefail__ignore_errors")

        # When / Then: every v2 tile path is a directory v1 created
        for idx in range(3):
            resource_paths = resolve_tile_paths(tmp_path / "data", idx)
            expected_root = tmp_path / _tile_relative(idx)
            for field, dirname in _OUTPUT_FIELD_TO_DIRNAME.items():
                assert f"{_tile_relative(idx)}/{dirname}/" in v1_directories, (
                    f"v1 must have produced {_tile_relative(idx)}/{dirname}/"
                )
                assert getattr(resource_paths, field) == expected_root / dirname
        # And: v1 numbered the later tiles from 0001, never 0000
        assert "data/divided/0000/" not in v1_directories


class TestDirTreeParityDividedSubdirectory:
    """TC-GOLD-006: idx>=1 paths match the v1 divided/{n:04d}/ subdirectory layout."""

    def test_idx_ge_1_matches_v1_divided_subdirectory(self, tmp_path: Path) -> None:
        """The v1 divided/0001/ tree must match resolve_tile_paths(idx=1).

        The expected tree is the one v1 created for the frozen two-tile
        ``multidatatile/ok`` contract run, whose second tile is ``divided/0001``.
        """
        # Given: the directories v1 created for a two-tile run
        v1_directories = _frozen_directories("v1/multidatatile/ok")

        # When: resolving the v2 paths of tile 1
        resource_paths = resolve_tile_paths(tmp_path / "data", 1)

        # Then: every field names the divided/0001 directory v1 created
        for field, dirname in _OUTPUT_FIELD_TO_DIRNAME.items():
            assert f"data/divided/0001/{dirname}/" in v1_directories, f"v1 must have produced data/divided/0001/{dirname}/"
            assert getattr(resource_paths, field) == tmp_path / "data" / "divided" / "0001" / dirname
