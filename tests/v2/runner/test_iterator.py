"""Tests for rdetoolkit v2 tile iterators (TC-ITER-001..020) — Session D1.

Written before implementation (TDD Red phase).
Target: make all tests pass in codex-worker Green phase.

Design authority: local/develop/v2/Design.md v2.1 §7.1-7.5, §6.4, §2.2 (step 4a)
Session authority: local/develop/v2/tasks/session_d1.md
  ("D1 implementation scope: runner/iterator.py") and
  local/develop/v2/decisions_pre_D.md (Decision D1-A: InputPaths.rawfiles)

Target import (fails until implementation exists — expected in Red phase):
    from rdetoolkit.runner.iterator import iterate_tiles, TileIterator

``iterate_tiles(mode, inputdata_path, unpacked_dir_path, data_root)``
must yield ``(IterationInfo, InputPaths, OutputContext)`` triples in tile
order, uniformly across all 5 modes, driven by the same
``domain.mode.selected_input_checker``-family checker classes used by
``rdetoolkit.impl.input_controller`` (verified directly against those
checkers below — see the module-level fixture helpers).

This name (``iterate_tiles``) is this test suite's choice for the "one
concrete generator function" the task file leaves to implementer discretion;
Codex must implement a function with exactly this name and signature.
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from tests.fixtures.excelinvoice import (
    EXCELINVOICE_ENTRYDATA_SHEET1_MULTI,
    EXCELINVOICE_ENTRYDATA_SHEET2,
    EXCELINVOICE_ENTRYDATA_SHEET3,
)

# Target imports — fail until implementation exists (expected in Red phase):
# from rdetoolkit.runner.iterator import iterate_tiles, TileIterator
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import InputPaths, OutputContext, IterationInfo


def _mk_dirs(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Build a fresh (inputdata, unpacked, data_root) triple under tmp_path.

    ``data_root`` is the fourth ``iterate_tiles`` argument: since Session
    I-REVIEW-A it anchors both the per-tile outputs and the invoice/tasksupport
    inputs, so the iterator can no longer straddle two roots (ruling #1).
    """
    inputdata = tmp_path / "inputdata"
    inputdata.mkdir()
    unpacked = tmp_path / "unpacked"
    unpacked.mkdir()
    data_root = tmp_path / "data"
    return inputdata, unpacked, data_root


def _write_excel_invoice(path: Path, *, drop_rows: int = 0) -> None:
    """Build a minimal ``*_excel_invoice.xlsx`` (no zip) with N data tiles.

    Replicates the pattern proven in
    ``tests/v2/golden/test_dir_tree_parity.py::_write_three_tile_excel_invoice``
    (session_d1.md's fixture-asset guidance). The unmodified
    ``EXCELINVOICE_ENTRYDATA_SHEET1_MULTI`` produces 2 data tiles (verified
    directly against ``ExcelInvoiceChecker.parse`` during test authoring);
    ``drop_rows=1`` removes the trailing data row to produce 1 tile.
    """
    sheet1_rows = [list(row) for row in EXCELINVOICE_ENTRYDATA_SHEET1_MULTI]
    if drop_rows:
        sheet1_rows = sheet1_rows[:-drop_rows]
    df1 = pd.DataFrame(
        sheet1_rows,
        columns=["invoiceList_format_id", "Sample_RDE_DataSet", *([""] * 17)],
    )
    df2 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET2, columns=["term_id", "key_name"])
    df3 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET3, columns=["sample_class_id", "term_id", "key_name"])
    with pd.ExcelWriter(path) as writer:
        df1.to_excel(writer, sheet_name="invoice_form", index=False)
        df2.to_excel(writer, sheet_name="generalTerm", index=False)
        df3.to_excel(writer, sheet_name="specificTerm", index=False)


def _write_rdeformat_zip(path: Path, groups: dict[str, list[str]]) -> None:
    """Build a zip whose entries live under the given folder names."""
    with zipfile.ZipFile(path, "w") as zf:
        for folder, filenames in groups.items():
            for filename in filenames:
                zf.writestr(f"{folder}/{filename}", "dummy-content")


def _patched_smarttable_rows(rows: list[tuple[Path, tuple[Path, ...]]]):
    """Return the ``patch(...)`` context for ``SmartTableFile`` returning ``rows``.

    Mirrors ``tests/test_smarttable_checker.py::test_parse_with_excel_file``
    (v1, read-only reference; mock boundary reused per session_d1.md's
    "Fixture assets for D1.5 (smarttable)" guidance, approach (b)).
    """
    ctx = patch("rdetoolkit.impl.input_controller.SmartTableFile")

    def _configure(mock_cls: Mock) -> Mock:
        mock_instance = Mock()
        mock_cls.return_value = mock_instance
        mock_instance.generate_row_csvs_with_file_mapping.return_value = rows
        return mock_instance

    return ctx, _configure


class TestTileIteratorExported:
    """The generic generator's type/callable is importable (implementer's choice)."""

    def test_tile_iterator_name_is_exported(self) -> None:
        """A ``TileIterator`` name (Protocol or type alias) must be importable."""
        import rdetoolkit.runner.iterator as iterator_module  # noqa: PLC0415

        assert hasattr(iterator_module, "TileIterator"), (
            "runner/iterator.py must export a TileIterator Protocol or type alias "
            "describing the (mode, inputdata_path, unpacked_dir_path, data_root) "
            "-> Iterator[tuple[IterationInfo, InputPaths, OutputContext]] shape."
        )

    def test_iterate_tiles_is_a_generator_function(self, tmp_path: Path) -> None:
        """iterate_tiles(...) returns an iterator/generator, not a list."""
        from rdetoolkit.runner.iterator import iterate_tiles  # noqa: PLC0415

        inputdata, unpacked, base_output = _mk_dirs(tmp_path)
        result = iterate_tiles(ModeKind.invoice, inputdata, unpacked, base_output)
        assert iter(result) is iter(result), "iterate_tiles(...) must return an iterator"


class TestInvoiceModeIteration:
    """Invoice mode: InvoiceChecker puts every input file into a single tile."""

    def test_multiple_loose_files_yield_one_tile_with_all_rawfiles(self, tmp_path: Path) -> None:
        """TC-ITER-001: N loose files -> exactly 1 tile; rawfiles holds all N paths."""
        from rdetoolkit.runner.iterator import iterate_tiles  # noqa: PLC0415

        inputdata, unpacked, base_output = _mk_dirs(tmp_path)
        (inputdata / "a.txt").write_text("a")
        (inputdata / "b.txt").write_text("b")
        (inputdata / "c.txt").write_text("c")

        tiles = list(iterate_tiles(ModeKind.invoice, inputdata, unpacked, base_output))

        assert len(tiles) == 1
        info, paths, out = tiles[0]
        assert isinstance(info, IterationInfo)
        assert isinstance(paths, InputPaths)
        assert isinstance(out, OutputContext)
        assert info.index == 0
        assert info.total == 1
        assert info.mode == "invoice"
        assert len(paths.rawfiles) == 3
        assert {p.name for p in paths.rawfiles} == {"a.txt", "b.txt", "c.txt"}

    def test_empty_inputdata_yields_one_tile_with_empty_rawfiles__boundary(self, tmp_path: Path) -> None:
        """TC-ITER-002 (0-file boundary): InvoiceChecker still yields 1 tile, rawfiles=()."""
        from rdetoolkit.runner.iterator import iterate_tiles  # noqa: PLC0415

        inputdata, unpacked, base_output = _mk_dirs(tmp_path)

        tiles = list(iterate_tiles(ModeKind.invoice, inputdata, unpacked, base_output))

        assert len(tiles) == 1
        _, paths, _ = tiles[0]
        assert paths.rawfiles == ()
        assert paths.raw is None, "raw must stay None (no single-file convenience) when rawfiles is empty"

    def test_single_file_populates_raw_convenience_field(self, tmp_path: Path) -> None:
        """TC-ITER-003: with exactly 1 rawfile, InputPaths.raw is that single path."""
        from rdetoolkit.runner.iterator import iterate_tiles  # noqa: PLC0415

        inputdata, unpacked, base_output = _mk_dirs(tmp_path)
        (inputdata / "only.txt").write_text("only")

        tiles = list(iterate_tiles(ModeKind.invoice, inputdata, unpacked, base_output))

        assert len(tiles) == 1
        _, paths, _ = tiles[0]
        assert paths.rawfiles == (inputdata / "only.txt",)
        assert paths.raw == inputdata / "only.txt"


class TestMultiDataTileModeIteration:
    """MultiDataTile mode: one tile per loose file (MultiFileChecker)."""

    def test_three_loose_files_yield_three_tiles_in_sorted_order(self, tmp_path: Path) -> None:
        """TC-ITER-004: N loose files -> N tiles, each a singleton rawfiles tuple."""
        from rdetoolkit.runner.iterator import iterate_tiles  # noqa: PLC0415

        inputdata, unpacked, base_output = _mk_dirs(tmp_path)
        (inputdata / "c.txt").write_text("c")
        (inputdata / "a.txt").write_text("a")
        (inputdata / "b.txt").write_text("b")

        tiles = list(iterate_tiles(ModeKind.multidatatile, inputdata, unpacked, base_output))

        assert len(tiles) == 3
        names = [tile[1].rawfiles[0].name for tile in tiles]
        assert names == sorted(names), "tile order must follow the checker's own sort (by str(path))"
        for idx, (info, paths, _out) in enumerate(tiles):
            assert info.index == idx
            assert info.total == 3
            assert info.mode == "multidatatile"
            assert len(paths.rawfiles) == 1
            assert paths.raw == paths.rawfiles[0]

    def test_single_file_yields_one_tile(self, tmp_path: Path) -> None:
        """TC-ITER-005 (1-tile boundary): a single loose file -> exactly 1 tile."""
        from rdetoolkit.runner.iterator import iterate_tiles  # noqa: PLC0415

        inputdata, unpacked, base_output = _mk_dirs(tmp_path)
        (inputdata / "solo.txt").write_text("solo")

        tiles = list(iterate_tiles(ModeKind.multidatatile, inputdata, unpacked, base_output))

        assert len(tiles) == 1
        info, paths, _out = tiles[0]
        assert info.index == 0
        assert info.total == 1
        assert paths.rawfiles == (inputdata / "solo.txt",)

    def test_empty_inputdata_yields_one_tile_with_empty_rawfiles__boundary(self, tmp_path: Path) -> None:
        """TC-ITER-006 (0-file boundary): MultiFileChecker still yields 1 tile, rawfiles=()."""
        from rdetoolkit.runner.iterator import iterate_tiles  # noqa: PLC0415

        inputdata, unpacked, base_output = _mk_dirs(tmp_path)

        tiles = list(iterate_tiles(ModeKind.multidatatile, inputdata, unpacked, base_output))

        assert len(tiles) == 1
        info, paths, _out = tiles[0]
        assert info.total == 1
        assert paths.rawfiles == ()

    def test_directory_layout_matches_resolve_tile_paths_convention(self, tmp_path: Path) -> None:
        """TC-ITER-007: idx 0 -> base/*, idx>=1 -> base/divided/{idx:04d}/*."""
        from rdetoolkit.runner.iterator import iterate_tiles  # noqa: PLC0415

        inputdata, unpacked, base_output = _mk_dirs(tmp_path)
        (inputdata / "a.txt").write_text("a")
        (inputdata / "b.txt").write_text("b")

        tiles = list(iterate_tiles(ModeKind.multidatatile, inputdata, unpacked, base_output))

        assert len(tiles) == 2
        _, _, out0 = tiles[0]
        _, _, out1 = tiles[1]
        assert out0.struct == base_output / "structured"
        assert out1.struct == base_output / "divided" / "0001" / "structured"
        assert out0.logs == base_output / "logs"
        assert out1.logs == base_output / "divided" / "0001" / "logs"


class TestRdeformatModeIteration:
    """RDEFormat mode: tiles grouped by numbered folder inside the input zip."""

    def test_two_numbered_folders_yield_two_tiles(self, tmp_path: Path) -> None:
        """TC-ITER-008: zip with 0000/ and 0001/ folders -> 2 tiles in index order."""
        from rdetoolkit.runner.iterator import iterate_tiles  # noqa: PLC0415

        inputdata, unpacked, base_output = _mk_dirs(tmp_path)
        _write_rdeformat_zip(inputdata / "sample.zip", {"0000": ["f0.txt"], "0001": ["f1.txt"]})

        tiles = list(iterate_tiles(ModeKind.rdeformat, inputdata, unpacked, base_output))

        assert len(tiles) == 2
        info0, paths0, _out0 = tiles[0]
        info1, paths1, _out1 = tiles[1]
        assert info0.index == 0
        assert info1.index == 1
        assert info0.total == 2
        assert info1.total == 2
        assert paths0.rawfiles[0].name == "f0.txt"
        assert paths1.rawfiles[0].name == "f1.txt"

    def test_no_numbered_folder_yields_one_tile__boundary(self, tmp_path: Path) -> None:
        """TC-ITER-009 (1-tile boundary): unnumbered zip contents collapse to tile 0."""
        from rdetoolkit.runner.iterator import iterate_tiles  # noqa: PLC0415

        inputdata, unpacked, base_output = _mk_dirs(tmp_path)
        _write_rdeformat_zip(inputdata / "sample.zip", {"flat": ["only.txt"]})

        tiles = list(iterate_tiles(ModeKind.rdeformat, inputdata, unpacked, base_output))

        assert len(tiles) == 1
        info, paths, _out = tiles[0]
        assert info.index == 0
        assert info.mode == "rdeformat"
        assert paths.rawfiles[0].name == "only.txt"


class TestExcelInvoiceModeIteration:
    """ExcelInvoice mode: one tile per Excel-invoice data row (no zip)."""

    def test_two_row_invoice_yields_two_tiles(self, tmp_path: Path) -> None:
        """TC-ITER-010: unmodified fixture (2 data rows) -> 2 tiles."""
        from rdetoolkit.runner.iterator import iterate_tiles  # noqa: PLC0415

        inputdata, unpacked, base_output = _mk_dirs(tmp_path)
        _write_excel_invoice(inputdata / "sample_excel_invoice.xlsx")

        tiles = list(iterate_tiles(ModeKind.excelinvoice, inputdata, unpacked, base_output))

        assert len(tiles) == 2
        for idx, (info, _paths, _out) in enumerate(tiles):
            assert info.index == idx
            assert info.total == 2
            assert info.mode == "excelinvoice"

    def test_single_row_invoice_yields_one_tile__boundary(self, tmp_path: Path) -> None:
        """TC-ITER-011 (1-tile boundary): dropping the trailing row -> 1 tile."""
        from rdetoolkit.runner.iterator import iterate_tiles  # noqa: PLC0415

        inputdata, unpacked, base_output = _mk_dirs(tmp_path)
        _write_excel_invoice(inputdata / "sample_excel_invoice.xlsx", drop_rows=1)

        tiles = list(iterate_tiles(ModeKind.excelinvoice, inputdata, unpacked, base_output))

        assert len(tiles) == 1
        info, _paths, _out = tiles[0]
        assert info.index == 0
        assert info.total == 1


class TestSmartTableModeIteration:
    """SmartTable mode: one tile per SmartTable row (SmartTableFile mocked, per D1.5)."""

    def test_two_row_smarttable_yields_two_tiles(self, tmp_path: Path) -> None:
        """TC-ITER-012: 2 mocked row mappings -> 2 tiles (save_table_file default False)."""
        from rdetoolkit.runner.iterator import iterate_tiles  # noqa: PLC0415

        inputdata, unpacked, base_output = _mk_dirs(tmp_path)
        (inputdata / "smarttable_test.csv").touch()
        ctx, configure = _patched_smarttable_rows([
            (Path("row_0.csv"), (Path("file1.txt"),)),
            (Path("row_1.csv"), (Path("file2.txt"),)),
        ])
        with ctx as mock_cls:
            configure(mock_cls)
            tiles = list(iterate_tiles(ModeKind.smarttable, inputdata, unpacked, base_output))

        assert len(tiles) == 2
        for idx, (info, _paths, _out) in enumerate(tiles):
            assert info.index == idx
            assert info.total == 2
            assert info.mode == "smarttable"

    def test_single_row_smarttable_yields_one_tile__boundary(self, tmp_path: Path) -> None:
        """TC-ITER-013 (1-tile boundary): 1 mocked row mapping -> 1 tile."""
        from rdetoolkit.runner.iterator import iterate_tiles  # noqa: PLC0415

        inputdata, unpacked, base_output = _mk_dirs(tmp_path)
        (inputdata / "smarttable_test.csv").touch()
        ctx, configure = _patched_smarttable_rows([(Path("row_0.csv"), ())])
        with ctx as mock_cls:
            configure(mock_cls)
            tiles = list(iterate_tiles(ModeKind.smarttable, inputdata, unpacked, base_output))

        assert len(tiles) == 1
        info, paths, _out = tiles[0]
        assert info.index == 0
        assert paths.rawfiles[0].name == "row_0.csv"


class TestInputPathsConventionalDirs:
    """InputPaths.invoice/tasksupport belong to the run's single data root."""

    def test_invoice_and_tasksupport_dirs_belong_to_the_data_root(self, tmp_path: Path) -> None:
        """TC-ITER-014 (UPDATED, Session I-REVIEW-A ruling #1): invoice and
        tasksupport resolve under the ``data_root`` the Runner decided, not
        under ``inputdata_path.parent``.

        The old ``inputdata_path.parent`` rule was a fifth, implicit data-root
        resolver: with an alias-flat root it answered ``root`` while the tile
        outputs were hard-coded to ``root/data``, so one run read its invoice
        from one tree and wrote its artifacts into another."""
        from rdetoolkit.runner.iterator import iterate_tiles  # noqa: PLC0415

        inputdata, unpacked, data_root = _mk_dirs(tmp_path)
        (inputdata / "a.txt").write_text("a")

        info, paths, _out = next(iterate_tiles(ModeKind.invoice, inputdata, unpacked, data_root))

        assert paths.inputdata == inputdata
        assert paths.invoice == data_root / "invoice"
        assert paths.tasksupport == data_root / "tasksupport"
        assert paths.invoice != inputdata.parent / "invoice"


class TestDirectoryCreationSideEffect:
    """Step 4a: iterate_tiles (not resolve_tile_paths) owns mkdir (Design §6.4)."""

    def test_all_ten_output_dirs_are_created_for_root_and_divided_tiles(self, tmp_path: Path) -> None:
        """TC-ITER-015: consuming the generator creates all 10 dirs per tile on disk."""
        from rdetoolkit.runner.iterator import iterate_tiles  # noqa: PLC0415

        inputdata, unpacked, base_output = _mk_dirs(tmp_path)
        (inputdata / "a.txt").write_text("a")
        (inputdata / "b.txt").write_text("b")

        list(iterate_tiles(ModeKind.multidatatile, inputdata, unpacked, base_output))

        expected_dirnames = (
            "structured", "meta", "main_image", "other_image", "thumbnail",
            "attachment", "nonshared_raw", "raw", "invoice", "logs",
        )
        for dirname in expected_dirnames:
            assert (base_output / dirname).is_dir(), f"missing root tile dir: {dirname}"
            assert (base_output / "divided" / "0001" / dirname).is_dir(), (
                f"missing divided/0001 tile dir: {dirname}"
            )

    def test_resolve_tile_paths_itself_does_not_create_directories(self, tmp_path: Path) -> None:
        """Regression guard: iterate_tiles must own mkdir, not rely on resolve_tile_paths."""
        from rdetoolkit.runner.paths import resolve_tile_paths  # noqa: PLC0415

        base_output = tmp_path / "data"
        tile_paths = resolve_tile_paths(base_output, 0)
        assert not tile_paths.struct.exists(), (
            "resolve_tile_paths must remain a pure path resolver (Design §6.4)"
        )


class TestOutputContextFromIterator:
    """Each yielded OutputContext is built via OutputContext.from_resource_paths()."""

    def test_output_context_is_constructed_via_factory(self, tmp_path: Path) -> None:
        """TC-ITER-016: the yielded OutputContext is a real OutputContext instance."""
        from rdetoolkit.runner.iterator import iterate_tiles  # noqa: PLC0415

        inputdata, unpacked, base_output = _mk_dirs(tmp_path)
        (inputdata / "a.txt").write_text("a")

        _info, _paths, out = next(iterate_tiles(ModeKind.invoice, inputdata, unpacked, base_output))

        assert isinstance(out, OutputContext)
        assert out.struct == base_output / "structured"
