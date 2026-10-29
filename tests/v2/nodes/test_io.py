"""Tests for rdetoolkit v2 builtin read nodes (Session F1.1, TC-F1-IO-*).

Written before implementation (TDD Red phase). Target: make all tests pass
in codex-worker Green phase. Authority: local/develop/v2/tasks/session_f1.md
(Current-State Survey, Conflict #1/#2, Known Traps 4/6).

Pinned API shapes (this file's binding contract -- Codex's implementation
choice only within these signatures, per Conflict #2's argument-order rule:
data/content first, no ``out``/privilege needed for pure reads):

    read_text(path: Path) -> str
    read_csv_with_header(path: Path) -> pd.DataFrame
    read_excel(path: Path) -> pd.DataFrame
    unzip_inputs(src_zip: Path, dst_dir: Path) -> None

All four are plain ``@node``-decorated functions with no special-casing
(Design §5.1); registration happens at import time of
``rdetoolkit.nodes.io``.

Fixture provenance (see ``tests/v2/nodes/fixtures/``, all independently
smoke-verified against the real libraries before being pinned as test
oracles -- see this file's sibling test manifest for the verification
transcript):
    - ``sample_utf8.txt``: plain UTF-8 text.
    - ``sample_cp932.txt``: Shift-JIS (cp932) encoded Japanese text, the v1
      ``CharDecEncoding.detect_text_file_encoding`` porting-source case.
    - ``sample_header.csv`` / ``empty.csv``: flat-header CSV and a
      zero-byte file (BV).
    - ``sample.xlsx``: generated via ``pandas.DataFrame.to_excel``.
    - ``sample_sjis.zip``: one entry whose filename is cp932-encoded with
      the UTF-8 flag bit UNSET, reproducing the exact mojibake condition
      ``rde2util.unzip_japanese_zip``/``_decode_filename`` exists to fix.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.v2.nodes.conftest import FIXTURES_DIR


class TestReadText:
    """TC-F1-IO-READ-TEXT-*."""

    def test_read_text_utf8_returns_str_matching_content(self) -> None:
        """EP: a UTF-8 fixture file is read back as an identical str."""
        from rdetoolkit.nodes.io import read_text

        result = read_text(FIXTURES_DIR / "sample_utf8.txt")

        assert isinstance(result, str)
        assert result == "hello utf-8 world\nline two\n"

    def test_read_text_cp932_is_correctly_decoded(self) -> None:
        """EP: a Shift-JIS (cp932) fixture is decoded to the correct Japanese text (v1 CharDecEncoding parity)."""
        from rdetoolkit.nodes.io import read_text

        result = read_text(FIXTURES_DIR / "sample_cp932.txt")

        assert result == "こんにちは世界\n"

    def test_read_text_nonexistent_path_raises(self) -> None:
        """BV: a nonexistent path raises."""
        from rdetoolkit.nodes.io import read_text

        with pytest.raises(OSError, match="definitely_missing"):
            read_text(FIXTURES_DIR / "definitely_missing_file.txt")

    def test_read_text_registered_as_builtin_node(self) -> None:
        """Registration: read_text appears in the registry after import."""
        import rdetoolkit.nodes  # noqa: F401
        from rdetoolkit.core import registry

        ids = {spec.id for spec in registry.list_nodes()}
        assert any(node_id.endswith("read_text") for node_id in ids), ids


class TestReadCsvWithHeader:
    """TC-F1-IO-READ-CSV-*."""

    def test_read_csv_with_header_separates_header_from_data(self) -> None:
        """EP: header row becomes columns; data rows are the returned rows."""
        from rdetoolkit.nodes.io import read_csv_with_header

        result = read_csv_with_header(FIXTURES_DIR / "sample_header.csv")

        assert list(result.columns) == ["col_a", "col_b", "col_c"]
        assert result.shape == (2, 3)
        assert list(result.iloc[0]) == [1, 2, 3]
        assert list(result.iloc[1]) == [4, 5, 6]

    def test_read_csv_with_header_empty_file_raises(self) -> None:
        """BV: an empty file raises."""
        from rdetoolkit.nodes.io import read_csv_with_header

        with pytest.raises(Exception):  # noqa: B017,PT011 -- pandas.errors.EmptyDataError, a v2-node impl detail
            read_csv_with_header(FIXTURES_DIR / "empty.csv")

    def test_read_csv_with_header_nonexistent_path_raises(self) -> None:
        """BV: a nonexistent path raises."""
        from rdetoolkit.nodes.io import read_csv_with_header

        with pytest.raises(OSError):
            read_csv_with_header(FIXTURES_DIR / "definitely_missing.csv")

    def test_read_csv_with_header_registered_as_builtin_node(self) -> None:
        """Registration: read_csv_with_header appears in the registry after import."""
        import rdetoolkit.nodes  # noqa: F401
        from rdetoolkit.core import registry

        ids = {spec.id for spec in registry.list_nodes()}
        assert any(node_id.endswith("read_csv_with_header") for node_id in ids), ids


class TestReadExcel:
    """TC-F1-IO-READ-EXCEL-*."""

    def test_read_excel_returns_dataframe_with_expected_shape(self) -> None:
        """EP: a small xlsx fixture is read with the correct columns/shape."""
        from rdetoolkit.nodes.io import read_excel

        result = read_excel(FIXTURES_DIR / "sample.xlsx")

        assert list(result.columns) == ["col_a", "col_b", "col_c"]
        assert result.shape == (2, 3)

    def test_read_excel_nonexistent_path_raises(self) -> None:
        """BV: a nonexistent file raises."""
        from rdetoolkit.nodes.io import read_excel

        with pytest.raises(OSError):
            read_excel(FIXTURES_DIR / "definitely_missing.xlsx")

    def test_read_excel_corrupt_file_raises(self, tmp_path: Path) -> None:
        """BV: a corrupt (non-xlsx-bytes) file raises."""
        from rdetoolkit.nodes.io import read_excel

        corrupt = tmp_path / "corrupt.xlsx"
        corrupt.write_bytes(b"not an xlsx file at all")

        with pytest.raises(Exception):  # noqa: B017,PT011 -- openpyxl/pandas raise their own error types
            read_excel(corrupt)

    def test_read_excel_registered_as_builtin_node(self) -> None:
        """Registration: read_excel appears in the registry after import."""
        import rdetoolkit.nodes  # noqa: F401
        from rdetoolkit.core import registry

        ids = {spec.id for spec in registry.list_nodes()}
        assert any(node_id.endswith("read_excel") for node_id in ids), ids


class TestUnzipInputs:
    """TC-F1-IO-UNZIP-*."""

    def test_unzip_inputs_extracts_to_target_directory(self, tmp_path: Path) -> None:
        """EP: a small zip fixture is extracted into the destination directory."""
        from rdetoolkit.nodes.io import unzip_inputs

        dest = tmp_path / "extracted"
        unzip_inputs(FIXTURES_DIR / "sample_sjis.zip", dest)

        extracted_files = list(dest.rglob("*"))
        assert extracted_files, "unzip_inputs must extract at least one file"

    def test_unzip_inputs_fixes_shift_jis_mojibake_filename(self, tmp_path: Path) -> None:
        """EP: a Shift-JIS in-zip filename (UTF-8 flag unset) is correctly
        decoded to its original Japanese name, mirroring
        ``rde2util.unzip_japanese_zip``'s mojibake fix -- not left as
        cp437-mojibake and not left undecoded."""
        from rdetoolkit.nodes.io import unzip_inputs

        dest = tmp_path / "extracted_sjis"
        unzip_inputs(FIXTURES_DIR / "sample_sjis.zip", dest)

        extracted_files = list(dest.rglob("*.txt"))
        names = {p.name for p in extracted_files}
        assert "日本語ファイル.txt" in names, names
        matching = next(p for p in extracted_files if p.name == "日本語ファイル.txt")
        assert matching.read_bytes() == b"hello japan sjis zip fixture\n"

    def test_unzip_inputs_corrupt_zip_raises(self, tmp_path: Path) -> None:
        """BV: a non-zip input raises."""
        from rdetoolkit.nodes.io import unzip_inputs

        bogus = tmp_path / "not_a_zip.zip"
        bogus.write_bytes(b"this is definitely not a zip archive")

        with pytest.raises(Exception):  # noqa: B017,PT011 -- zipfile.BadZipFile
            unzip_inputs(bogus, tmp_path / "out")

    def test_unzip_inputs_registered_as_builtin_node(self) -> None:
        """Registration: unzip_inputs appears in the registry after import."""
        import rdetoolkit.nodes  # noqa: F401
        from rdetoolkit.core import registry

        ids = {spec.id for spec in registry.list_nodes()}
        assert any(node_id.endswith("unzip_inputs") for node_id in ids), ids


class TestReadNodesDiscoverability:
    """Registration presence for all 4 read nodes in one place (belt-and-braces)."""

    def test_all_four_read_node_ids_present_after_import(self) -> None:
        """All 4 read-node ids appear in registry.list_nodes() after import rdetoolkit.nodes."""
        import rdetoolkit.nodes  # noqa: F401
        from rdetoolkit.core import registry

        ids = {spec.id for spec in registry.list_nodes()}
        expected_suffixes = ("read_text", "read_csv_with_header", "read_excel", "unzip_inputs")
        for suffix in expected_suffixes:
            assert any(node_id.endswith(suffix) for node_id in ids), (suffix, ids)
