"""main::generate_folder_paths_iterator()の生成物か正しいか確認する

テストスイート
1 通常のフォルダ構成を作成する
2 ExcelInvoice
3 RDE format

Note:
    テスト実行後、dataフォルダというフォルダは削除されるのでご注意ください。
"""

import os
from pathlib import Path
from unittest.mock import Mock, patch

from rdetoolkit.impl.input_controller import SmartTableChecker
from rdetoolkit.models.rde2types import RdeOutputResourcePath
from rdetoolkit.workflows import generate_folder_paths_iterator


def test_standard_output_dir_structured(invoice_json_with_sample_info, inputfile_single):
    """1 通常のフォルダ構成を作成する
    RDEに登録するための標準的なフォルダ構成
    送り状モード・1ファイル入力の場合などが対象
    """
    expect_dir_names = (
        "raw",
        "meta",
        "main_image",
        "other_image",
        "structured",
        "thumbnail",
    )

    input_files = [(Path("data/inputdata/test_single.txt"),)]
    input_invoice_schema_json = Path("data", "tasksupport", "invoice.schema.json")
    result_generator_obj = generate_folder_paths_iterator(input_files, invoice_json_with_sample_info, input_invoice_schema_json)

    assert isinstance(list(result_generator_obj)[0], RdeOutputResourcePath)
    for name in expect_dir_names:
        assert os.path.exists(Path("data", name))


def test_excel_invoice_output_dir_structured(inputfile_zip_with_folder, inputfile_multi_excelinvoice):
    """2 ExcelInvoice
    ExcelInvoiceを使った時のRDEフォルダ構成
    Excelinvoiceモードの場合などが対象
    divdiedフォルダが作成される。
    """
    expect_dir_names = (
        "raw",
        "invoice",
        "structured",
        "main_image",
        "other_image",
        "thumbnail",
    )

    input_files = [
        (
            Path("data/temp/invoice_org.json"),
            Path("data/temp/structured/test.csv"),
            Path("data/temp/inputdata/test_file0.txt"),
            Path("data/temp/raw/test_file0.txt"),
        ),
        (
            Path("data/temp/divided/0001/structured/test_file1.csv"),
            Path("data/temp/divided/0001/inputdata/test_file1.txt"),
            Path("data/temp/divided/0001/raw/test_file1.txt"),
        ),
        (
            Path("data/temp/divided/0002/structured/test_file2.csv"),
            Path("data/temp/divided/0002/inputdata/test_file2.txt"),
            Path("data/temp/divided/0002/raw/test_file2.txt"),
        ),
    ]
    invoice_org_json = Path("data", "temp", "invoice_org.json")
    input_invoice_schema_json = Path("data", "tasksupport", "invoice.schema.json")

    result_generator_obj = generate_folder_paths_iterator(input_files, invoice_org_json, input_invoice_schema_json)

    for output in result_generator_obj:
        assert isinstance(output, RdeOutputResourcePath)
    for name in expect_dir_names:
        assert os.path.exists(Path("data", name))


def test_rdeformat_output_dir_structured(inputfile_rdeformat_divived):
    """3 RDE format
    RDEformatで必要となるフォルダ構成
    """
    expect_dir_names = (
        "raw",
        "meta",
        "main_image",
        "other_image",
        "structured",
        "thumbnail",
    )

    input_files = [
        (Path("data/temp/test_child1.txt"),),
        (Path("data/temp/test_child2.txt"),),
    ]
    invoice_org_json = Path("data", "temp", "invoice_org.json")
    input_invoice_schema_json = Path("data", "tasksupport", "invoice.schema.json")
    result_generator_obj = generate_folder_paths_iterator(input_files, invoice_org_json, input_invoice_schema_json)

    for output in result_generator_obj:
        assert isinstance(output, RdeOutputResourcePath)

    for name in expect_dir_names:
        assert os.path.exists(Path("data", name))


def test_generate_folder_paths_iterator_sets_smarttable_rawfile(tmp_path):
    """Verify that the row CSV is set to smarttable_rawfile in SmartTable mode."""
    raw_csv = tmp_path / "fsmarttable_sample_0000.csv"
    related_file = tmp_path / "extracted" / "file.txt"
    input_files = [(raw_csv, (related_file,))]
    invoice_org_json = tmp_path / "invoice_org.json"
    invoice_schema_json = tmp_path / "invoice.schema.json"

    results = list(
        generate_folder_paths_iterator(
            input_files,
            invoice_org_json,
            invoice_schema_json,
            smarttable_mode=True,
        ),
    )

    assert results
    assert results[0].smarttable_rawfile == raw_csv
    assert results[0].rawfiles == (related_file,)


def test_generate_folder_paths_iterator_rejects_legacy_shape_in_smarttable_mode(tmp_path):
    """A legacy flat RawFiles tuple with smarttable_mode=True raises a clear TypeError."""
    import pytest

    legacy_flat_tuple = [(tmp_path / "fsmarttable_sample_0000.csv", tmp_path / "file.txt", tmp_path / "other.txt")]

    with pytest.raises(TypeError, match="smarttable_mode=True requires"):
        list(
            generate_folder_paths_iterator(
                legacy_flat_tuple,
                tmp_path / "invoice_org.json",
                tmp_path / "invoice.schema.json",
                smarttable_mode=True,
            ),
        )


def test_generate_folder_paths_iterator_rejects_smarttable_shape_without_mode(tmp_path):
    """A SmartTableRawFiles pair with smarttable_mode=False raises a clear TypeError."""
    import pytest

    smarttable_pair = [(tmp_path / "fsmarttable_sample_0000.csv", (tmp_path / "file.txt",))]

    with pytest.raises(TypeError, match="smarttable_mode=False requires"):
        list(
            generate_folder_paths_iterator(
                smarttable_pair,
                tmp_path / "invoice_org.json",
                tmp_path / "invoice.schema.json",
                smarttable_mode=False,
            ),
        )


def test_generate_folder_paths_iterator_smarttable_original_file_entry(tmp_path):
    """Verify the original-file tile ((None, (smarttable_file,))) is handled when save_table_file=True."""
    smarttable_file = tmp_path / "smarttable_test.xlsx"
    input_files = [(None, (smarttable_file,))]
    invoice_org_json = tmp_path / "invoice_org.json"
    invoice_schema_json = tmp_path / "invoice.schema.json"

    results = list(
        generate_folder_paths_iterator(
            input_files,
            invoice_org_json,
            invoice_schema_json,
            smarttable_mode=True,
        ),
    )

    assert results
    assert results[0].smarttable_rawfile is None
    assert results[0].rawfiles == (smarttable_file,)


def test_parse_to_generate_folder_paths_iterator_keeps_smarttable_order_save_table_file_true(tmp_path):
    """Integration test: SmartTableChecker.parse()(save_table_file=True) output feeds generate_folder_paths_iterator correctly.

    Registration order (per SmartTableChecker.parse docstring): idx=0 -> data/ root
    (registered last), idx=1 -> divided/0001 (registered first), idx=2 -> divided/0002.
    With save_table_file=True and 2 data rows, raw_files = [row1, original_file, row0].
    """
    smarttable_file = tmp_path / "smarttable_test.xlsx"
    smarttable_file.touch()

    with patch("rdetoolkit.impl.input_controller.SmartTableFile") as mock_st:
        mock_instance = Mock()
        mock_st.return_value = mock_instance
        mock_instance.generate_row_csvs_with_file_mapping.return_value = [
            (Path("data/temp/fsmarttable_test_0000.csv"), (Path("file0.txt"),)),
            (Path("data/temp/fsmarttable_test_0001.csv"), (Path("file1.txt"),)),
        ]

        checker = SmartTableChecker(Path("data/temp"), save_table_file=True)
        rawfiles, _ = checker.parse(tmp_path)

    invoice_org_json = tmp_path / "invoice_org.json"
    invoice_schema_json = tmp_path / "invoice.schema.json"

    results = list(
        generate_folder_paths_iterator(
            rawfiles,
            invoice_org_json,
            invoice_schema_json,
            smarttable_mode=True,
        ),
    )

    assert len(results) == 3
    # idx=0 -> data/ root: last data row (row1), registered last.
    assert results[0].rawfiles == (Path("file1.txt"),)
    assert results[0].smarttable_rawfile == Path("data/temp/fsmarttable_test_0001.csv")
    # idx=1 -> divided/0001: original SmartTable file, registered first.
    assert results[1].rawfiles == (smarttable_file,)
    assert results[1].smarttable_rawfile is None
    # idx=2 -> divided/0002: first data row (row0).
    assert results[2].rawfiles == (Path("file0.txt"),)
    assert results[2].smarttable_rawfile == Path("data/temp/fsmarttable_test_0000.csv")


def test_parse_to_generate_folder_paths_iterator_keeps_smarttable_order_save_table_file_false(tmp_path):
    """Integration test: SmartTableChecker.parse()(save_table_file=False) output feeds generate_folder_paths_iterator correctly.

    With save_table_file=False and 2 data rows, raw_files = [row1, row0]
    (last row registered last at data/ root, first row at divided/0001).
    """
    smarttable_file = tmp_path / "smarttable_test.xlsx"
    smarttable_file.touch()

    with patch("rdetoolkit.impl.input_controller.SmartTableFile") as mock_st:
        mock_instance = Mock()
        mock_st.return_value = mock_instance
        mock_instance.generate_row_csvs_with_file_mapping.return_value = [
            (Path("data/temp/fsmarttable_test_0000.csv"), (Path("file0.txt"),)),
            (Path("data/temp/fsmarttable_test_0001.csv"), (Path("file1.txt"),)),
        ]

        checker = SmartTableChecker(Path("data/temp"), save_table_file=False)
        rawfiles, _ = checker.parse(tmp_path)

    invoice_org_json = tmp_path / "invoice_org.json"
    invoice_schema_json = tmp_path / "invoice.schema.json"

    results = list(
        generate_folder_paths_iterator(
            rawfiles,
            invoice_org_json,
            invoice_schema_json,
            smarttable_mode=True,
        ),
    )

    assert len(results) == 2
    # idx=0 -> data/ root: last data row (row1), registered last.
    assert results[0].rawfiles == (Path("file1.txt"),)
    assert results[0].smarttable_rawfile == Path("data/temp/fsmarttable_test_0001.csv")
    # idx=1 -> divided/0001: first data row (row0), registered first.
    assert results[1].rawfiles == (Path("file0.txt"),)
    assert results[1].smarttable_rawfile == Path("data/temp/fsmarttable_test_0000.csv")
