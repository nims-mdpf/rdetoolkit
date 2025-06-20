"""Test Suite
1 Invoice
    1-1 File (e.g., sample.txt)
    1-2 Folder (e.g., sample1.txt, sample2.txt)
    1-3 None
2 ExcelInvoice
    2-1 File (e.g., sample.zip (compressed single file) + *_excel_invoice.xlsx)
    2-2 Folder (e.g., sample.zip (compressed folder) + *_excel_invoice.xlsx)
    2-3 None (e.g., *_excel_invoice.xlsx)
3 RDEFormat (e.g., *.zip, tasksupport/rdeformat.txt)
4 Multi-Mode (e.g., sample1.txt, sample2.txt, sample3.txt)

Note:
    After running the tests, the folder named 'data' will be deleted, so please be cautious.
"""

from pathlib import Path

from rdetoolkit.models.config import Config
from rdetoolkit.models.rde2types import RdeInputDirPaths
from rdetoolkit.rde2util import StorageDir
from rdetoolkit.workflows import check_files


def test_check_files_single(inputfile_single, ivnoice_json_none_sample_info, tasksupport):
    """テスト1-1: 入力形式: 送り状 / 入力ファイルタイプ: ファイル / ファイル数: 1ファイル
    inputfile_single: data/inputdata/test_single.txt
    invoice_json_with_sample_info: data/invoice/invoice.json
    """
    expect_rawfiles = [(Path("data", "inputdata", "test_single.txt"),)]

    format_flags = Config(extended_mode=None, save_raw=True, save_thumbnail_image=False, magic_variable=False)
    srcpaths = RdeInputDirPaths(
        inputdata=StorageDir.get_specific_outputdir(False, "inputdata"),
        invoice=StorageDir.get_specific_outputdir(False, "invoice"),
        tasksupport=StorageDir.get_specific_outputdir(False, "tasksupport"),
        config=format_flags,
    )
    raw_files_group, excel_invoice_files, smarttable_files = check_files(srcpaths, mode=format_flags.extended_mode)

    assert raw_files_group == expect_rawfiles
    assert excel_invoice_files is None
    assert smarttable_files is None


def test_check_files_multi(tasksupport, invoice_json_with_sample_info, inputfile_multi):
    """テスト1-2: 入力形式: 送り状 / 入力ファイルタイプ: フォルダ / ファイル数: 複数ファイル
    inputfile_multi: data/inputdata/test_child1.txt, data/inputdata/test_child2.txt
    invoice_json_with_sample_info: data/invoice/invoice.json
    """
    expect_rawfiles = [(Path("data/inputdata/test_child1.txt"), Path("data/inputdata/test_child2.txt"))]

    format_flags = Config(extended_mode=None, save_raw=True, save_thumbnail_image=False, magic_variable=False)
    srcpaths = RdeInputDirPaths(
        inputdata=StorageDir.get_specific_outputdir(False, "inputdata"),
        invoice=StorageDir.get_specific_outputdir(False, "invoice"),
        tasksupport=StorageDir.get_specific_outputdir(False, "tasksupport"),
        config=format_flags,
    )
    raw_files_group, excel_invoice_files, smarttable_files = check_files(srcpaths, mode=format_flags.extended_mode)

    # The order of appearance of the contents of the tuples is
    # not relevant to the content of the test
    assert set(raw_files_group[0]) == set(expect_rawfiles[0])
    assert excel_invoice_files is None
    assert smarttable_files is None


def test_check_files_invoice_non_file(tasksupport, invoice_json_with_sample_info):
    """テスト1-3: 入力形式: 送り状 / 入力ファイルタイプ: なし
    invoice_json_with_sample_info: data/invoice/invoice.json
    """
    expect_rawfiles = [()]

    format_flags = Config(extended_mode=None, save_raw=True, save_thumbnail_image=False, magic_variable=False)
    srcpaths = RdeInputDirPaths(
        inputdata=StorageDir.get_specific_outputdir(False, "inputdata"),
        invoice=StorageDir.get_specific_outputdir(False, "invoice"),
        tasksupport=StorageDir.get_specific_outputdir(False, "tasksupport"),
        config=format_flags,
    )
    raw_files_group, excel_invoice_files, smarttable_files = check_files(srcpaths, mode=format_flags.extended_mode)

    assert raw_files_group == expect_rawfiles
    assert excel_invoice_files is None
    assert smarttable_files is None


# テストスイート(No. 2-xx)
# エクセルインボイスからのデータ登録についてテスト
def test_check_files_excelinvoice_zip_with_file(
    tasksupport,
    invoice_json_with_sample_info,
    inputfile_single_excelinvoice,
    inputfile_zip_with_file,
):
    """テスト2-1: 入力形式: エクセルインボイス / 入力ファイルタイプ: ファイル / ファイル数: 1ファイル
    inputfile_zip_with_file: "test_child1.txt"圧縮
    """
    expect_rawfiles = [(Path("data/temp/test_child1.txt"),)]
    expect_excelinvoice = Path("data/inputdata/test_excel_invoice.xlsx")

    format_flags = Config(extended_mode=None, save_raw=True, save_thumbnail_image=False, magic_variable=False)
    srcpaths = RdeInputDirPaths(
        inputdata=StorageDir.get_specific_outputdir(False, "inputdata"),
        invoice=StorageDir.get_specific_outputdir(False, "invoice"),
        tasksupport=StorageDir.get_specific_outputdir(False, "tasksupport"),
        config=format_flags,
    )
    raw_files_group, excel_invoice_files, smarttable_files = check_files(srcpaths, mode=format_flags.extended_mode)

    assert raw_files_group == expect_rawfiles
    assert excel_invoice_files == expect_excelinvoice
    assert smarttable_files is None


def test_check_files_excelinvoice_zip_with_folder(
    tasksupport,
    inputfile_multi_excelinvoice,
    inputfile_zip_with_folder,
    ivnoice_json_none_sample_info,
):
    """テスト2-2: 入力形式: エクセルインボイス / 入力ファイルタイプ: フォルダ (フォルダ圧縮.zip) / ファイル数: 複数ファイル
    inputfile_zip_with_file: test_input_multi/test_child1.txt, test_input_multi/test_child2.txt圧縮
    """
    expect_rawfiles = [
        (Path("data/temp/test_child1.txt"),),
        (Path("data/temp/test_child2.txt"),),
    ]
    expect_excelinvoice = Path("data/inputdata/test_excel_invoice.xlsx")

    format_flags = Config(extended_mode=None, save_raw=True, save_thumbnail_image=False, magic_variable=False)
    srcpaths = RdeInputDirPaths(
        inputdata=StorageDir.get_specific_outputdir(False, "inputdata"),
        invoice=StorageDir.get_specific_outputdir(False, "invoice"),
        tasksupport=StorageDir.get_specific_outputdir(False, "tasksupport"),
        config=format_flags,
    )
    raw_files_group, excel_invoice_files, smarttable_files = check_files(srcpaths, mode=format_flags.extended_mode)

    assert raw_files_group == expect_rawfiles
    assert excel_invoice_files == expect_excelinvoice
    assert smarttable_files is None


def test_check_files_excelinvoice_non_file(tasksupport, invoice_json_with_sample_info, non_inputfile_excelinvoice):
    """テスト2-3: 入力形式: エクセルインボイス / 入力ファイルタイプ: なし"""
    expect_rawfiles = []
    expect_excelinvoice = Path("data/inputdata/test_excel_invoice.xlsx")

    format_flags = Config(extended_mode=None, save_raw=True, save_thumbnail_image=False, magic_variable=False)
    srcpaths = RdeInputDirPaths(
        inputdata=StorageDir.get_specific_outputdir(False, "inputdata"),
        invoice=StorageDir.get_specific_outputdir(False, "invoice"),
        tasksupport=StorageDir.get_specific_outputdir(False, "tasksupport"),
        config=format_flags,
    )
    raw_files_group, excel_invoice_files, smarttable_files = check_files(srcpaths, mode=format_flags.extended_mode)

    assert raw_files_group == expect_rawfiles
    assert excel_invoice_files == expect_excelinvoice
    assert smarttable_files is None


def test_check_files_rdeformat_single(inputfile_rdeformat_divived, tasksupport, invoice_json_with_sample_info):
    """テスト3: 入力形式: RDEformat / 入力ファイルタイプ: *.zip, tasksupport/rdeformat.txt)"""
    expect_rawfiles = [
        (
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
    expect_excelinvoice = None

    format_flags = Config(extended_mode="rdeformat", save_raw=True, save_thumbnail_image=False, magic_variable=False)
    srcpaths = RdeInputDirPaths(
        inputdata=StorageDir.get_specific_outputdir(False, "inputdata"),
        invoice=StorageDir.get_specific_outputdir(False, "invoice"),
        tasksupport=StorageDir.get_specific_outputdir(False, "tasksupport"),
        config=format_flags,
    )
    raw_files_group, excel_invoice_files, smarttable_files = check_files(srcpaths, mode=format_flags.extended_mode)

    assert set(raw_files_group[0]) == set(expect_rawfiles[0])
    assert set(raw_files_group[1]) == set(expect_rawfiles[1])
    assert set(raw_files_group[2]) == set(expect_rawfiles[2])
    assert excel_invoice_files == expect_excelinvoice
    assert smarttable_files is None


def test_check_files_invoice_multiformat(tasksupport, invoice_json_with_sample_info, inputfile_multi, inputfile_multimode):
    """テスト4: 入力形式: 送り状 / 入力ファイルタイプ: マルチモード / ファイル数: 複数ファイル
    inputfile_multi: data/inputdata/test_child1.txt, data/inputdata/test_child2.txt
    invoice_json_with_sample_info: data/invoice/invoice.json
    """
    expect_rawfiles = [
        (Path("data/inputdata/test_child1.txt"),),
        (Path("data/inputdata/test_child2.txt"),),
    ]
    expect_excelinvoice = None

    format_flags = Config(extended_mode="MultiDataTile", save_raw=True, save_thumbnail_image=False, magic_variable=False)
    srcpaths = RdeInputDirPaths(
        inputdata=StorageDir.get_specific_outputdir(False, "inputdata"),
        invoice=StorageDir.get_specific_outputdir(False, "invoice"),
        tasksupport=StorageDir.get_specific_outputdir(False, "tasksupport"),
        config=format_flags,
    )
    raw_files_group, excel_invoice_files, smarttable_files = check_files(srcpaths, mode=format_flags.extended_mode)
    assert set(raw_files_group) == set(expect_rawfiles)
    assert excel_invoice_files == expect_excelinvoice
    assert smarttable_files is None
