"""test_inputfile_checker.py
(test_checkfiles_input_pattern.pyの互換テスト)

main::checkFiles()の入力パターンとその出力をテストする

テストスイート
1 送り状
    1-1 ファイル(ex: sample.txt)
    1-2 フォルダ(ex: sample1.txt, sample2.txt)
    1-3 なし
2 ExcelInvoice
    2-1 ファイル(ex: sample.zip(1ファイルのみ圧縮)+ *_excel_invoice.xlsx)
    2-2 フォルダ(ex: sample.zip(フォルダ圧縮)+ *_excel_invoice.xlsx)
    2-3 なし(ex: *_excel_invoice.xlsx)
3 Format (ex: *.zip, tasksupport/rdeformat.txt)
    3-1 dividedなし
    3-2 dividedあり
4 マルチモード(ex: sample1.txt, sample2.txt, sample3.txt)
"""

from pathlib import Path

from rdetoolkit.impl.input_controller import (
    ExcelInvoiceChecker,
    InvoiceChecker,
    MultiFileChecker,
    RDEFormatChecker,
)
from rdetoolkit.models.rde2types import RdeInputDirPaths
from rdetoolkit.modeproc import selected_input_checker
from rdetoolkit.models.config import Config


class TestInvoiceChecker:
    """1 テストスイート: 送り状登録を想定したファイルチェックテスト
    1-1 テストケース: 1ファイル登録のテスト
    1-2 テストケース: 複数ファイル登録のテスト
    1-3 テストケース: ファイルなしの登録テスト
    """

    def test_parse_single(self, inputfile_single):
        unpacked_dir_basename = Path("data/temp")
        src_dir_input = Path("data/inputdata")

        checker = InvoiceChecker(unpacked_dir_basename)
        rawfiles, _ = checker.parse(src_dir_input)

        assert len(rawfiles) == 1
        assert isinstance(rawfiles[0], tuple)
        assert all(isinstance(file, Path) for file in rawfiles[0])

    def test_parse_multi(self, inputfile_multi):
        unpacked_dir_basename = Path("data/temp")
        src_dir_input = Path("data/inputdata")

        checker = InvoiceChecker(unpacked_dir_basename)
        rawfiles, excelinvoice = checker.parse(src_dir_input)

        assert len(rawfiles[0]) == 2
        assert excelinvoice is None
        assert isinstance(rawfiles[0], tuple)
        assert all(isinstance(file, Path) for file in rawfiles[0])

    def test_parse_non_data_only_invoice(self, invoice_json_with_sample_info):
        unpacked_dir_basename = Path("data/temp")
        src_dir_input = Path("data/inputdata")

        checker = InvoiceChecker(unpacked_dir_basename)
        rawfiles, excelinvoice = checker.parse(src_dir_input)

        assert len(rawfiles[0]) == 0
        assert rawfiles == [()]
        assert excelinvoice is None
        assert isinstance(rawfiles[0], tuple)


class TestExcelInvoiceChecker:
    """2 テストスイート: エクセルインボイス登録を想定したファイルチェックテスト
    2-1 テストケース: ファイルモード+エクセルインボイスの登録テスト
    2-2 テストケース: フォルダモード+エクセルインボイスの登録テスト
    """

    def test_parse_single(self, inputfile_zip_with_file, inputfile_single_excelinvoice):
        unpacked_dir_basename = Path("data/temp")
        src_dir_input = Path("data/inputdata")

        checker = ExcelInvoiceChecker(unpacked_dir_basename)
        rawfiles, excelinvoice = checker.parse(src_dir_input)

        assert len(rawfiles) == 1
        assert isinstance(rawfiles[0], tuple)
        assert excelinvoice is not None
        assert all(isinstance(file, Path) for file in rawfiles[0])

    def test_parse_multi(self, inputfile_zip_with_folder, inputfile_multi_excelinvoice):
        unpacked_dir_basename = Path("data/temp")
        src_dir_input = Path("data/inputdata")

        checker = ExcelInvoiceChecker(unpacked_dir_basename)
        rawfiles, excelinvoice = checker.parse(src_dir_input)

        assert rawfiles == [
            (Path("data/temp/test_child1.txt"),),
            (Path("data/temp/test_child2.txt"),),
        ]
        assert excelinvoice is not None
        assert isinstance(rawfiles[0], tuple)
        assert all(isinstance(file, Path) for file in rawfiles[0])

    def test_parse_multi_folder(self, inputfile_zip_with_folder_multi, inputfile_multi_folder_excelinvoice):
        """sortを考慮したテスト"""
        unpacked_dir_basename = Path("data/temp")
        src_dir_input = Path("data/inputdata")

        checker = ExcelInvoiceChecker(unpacked_dir_basename)
        rawfiles, excelinvoice = checker.parse(src_dir_input)

        assert rawfiles == [
            (Path("data/temp/data2/test_child2.txt"),),
            (Path("data/temp/data1/test_child1.txt"),),
        ]
        assert excelinvoice is not None
        assert isinstance(rawfiles[0], tuple)
        assert all(isinstance(file, Path) for file in rawfiles[0])

    def test_parse_only_sample_without_zip(self, non_inputfile_excelinvoice):
        unpacked_dir_basename = Path("data/temp")
        src_dir_input = Path("data/inputdata")

        checker = ExcelInvoiceChecker(unpacked_dir_basename)
        rawfiles, excelinvoice = checker.parse(src_dir_input)

        assert len(rawfiles) == 0
        assert excelinvoice is not None

    def test_parse_only_singlefile_with_zip_multiline(self, inputfile_zip_with_file, excelinvoice_single_input_multiline):
        """zipに1ファイルのみ+Excelinvoiceに書かれた全ての行に同じデータを登録する"""
        unpacked_dir_basename = Path("data/temp")
        src_dir_input = Path("data/inputdata")

        checker = ExcelInvoiceChecker(unpacked_dir_basename)
        rawfiles, excelinvoice = checker.parse(src_dir_input)

        assert rawfiles == [
            (Path("data/temp/test_child1.txt"),),
            (Path("data/temp/test_child1.txt"),),
            (Path("data/temp/test_child1.txt"),),
        ]
        assert excelinvoice is not None


class TestRDEFormatChecker:
    """3 テストスイート: RDEフォーマット登録を想定したファイルチェックテスト
    3-1 テストケース: RDEフォーマットの登録テスト(dividedなし)
    3-2 テストケース: RDEフォーマットの登録テスト(dividedあり)
    """

    def test_parse_rdeformat(self, inputfile_rdeformat):
        expect_rawfiles = [
            Path("data/temp/raw/test_child1.txt"),
            Path("data/temp/inputdata/test_child1.txt"),
            Path("data/temp/structured/test.csv"),
        ]
        unpacked_dir_basename = Path("data/temp")
        src_dir_input = Path("data/inputdata")

        checker = RDEFormatChecker(unpacked_dir_basename)
        rawfiles, excelinvoice = checker.parse(src_dir_input)

        assert len(rawfiles) == 1
        assert isinstance(rawfiles[0], tuple)
        assert excelinvoice is None
        assert set(rawfiles[0]) == set(expect_rawfiles)
        assert all(isinstance(file, Path) for file in rawfiles[0])

    def test_parse_rdeformat_divided(self, inputfile_rdeformat_divived):
        expect_rawfiles_0 = [
            Path("data/temp/inputdata/test_file0.txt"),
            Path("data/temp/raw/test_file0.txt"),
            Path("data/temp/structured/test.csv"),
        ]
        expect_rawfiles_1 = [
            Path("data/temp/divided/0001/inputdata/test_file1.txt"),
            Path("data/temp/divided/0001/raw/test_file1.txt"),
            Path("data/temp/divided/0001/structured/test_file1.csv"),
        ]
        expect_rawfiles_2 = [
            Path("data/temp/divided/0002/inputdata/test_file2.txt"),
            Path("data/temp/divided/0002/raw/test_file2.txt"),
            Path("data/temp/divided/0002/structured/test_file2.csv"),
        ]
        unpacked_dir_basename = Path("data/temp")
        src_dir_input = Path("data/inputdata")

        checker = RDEFormatChecker(unpacked_dir_basename)
        rawfiles, excelinvoice = checker.parse(src_dir_input)

        assert len(rawfiles) == 3
        assert isinstance(rawfiles[0], tuple)
        assert excelinvoice is None
        assert set(rawfiles[0]) == set(expect_rawfiles_0)
        assert set(rawfiles[1]) == set(expect_rawfiles_1)
        assert set(rawfiles[2]) == set(expect_rawfiles_2)
        assert all(isinstance(file, Path) for file in rawfiles[0])


class TestMultiFileChecker:
    """4 テストスイート: Multifileモード登録を想定したファイルチェックテスト
    テストケース1: Multifileモードの登録テスト
    """

    def test_parse(self, inputfile_multi, inputfile_multimode):
        unpacked_dir_basename = Path("data/temp")
        src_dir_input = Path("data/inputdata")

        checker = MultiFileChecker(unpacked_dir_basename)
        rawfiles, excelinvoice = checker.parse(src_dir_input)

        assert len(rawfiles) == 2
        assert isinstance(rawfiles[0], tuple)
        assert excelinvoice is None
        assert all(isinstance(file, Path) for file in rawfiles[0])


def test_selected_input_checker_rde_format():
    fmtflags = Config(extended_mode="rdeformat", save_raw=True, save_thumbnail_image=False)
    src_paths = RdeInputDirPaths(
        inputdata=Path("data/inputdata"),
        invoice=Path("data/invoice"),
        tasksupport=Path("data/tasksupport"),
        config=fmtflags,
    )
    unpacked_dir_path = Path("data/temp")
    assert isinstance(selected_input_checker(src_paths, unpacked_dir_path, fmtflags.extended_mode), RDEFormatChecker)


def test_selected_input_checker_multi_file():
    fmtflags = Config(extended_mode="MultiDataTile", save_raw=True, save_thumbnail_image=False)
    src_paths = RdeInputDirPaths(
        inputdata=Path("data/inputdata"),
        invoice=Path("data/invoice"),
        tasksupport=Path("data/tasksupport"),
        config=fmtflags,
    )
    unpacked_dir_path = Path("data/temp")
    assert isinstance(selected_input_checker(src_paths, unpacked_dir_path, fmtflags.extended_mode), MultiFileChecker)


def test_selected_input_checker_excelinvoice(inputfile_zip_with_file, inputfile_single_excelinvoice):
    fmtflags = Config(extended_mode=None, save_raw=True, save_thumbnail_image=False)
    src_paths = RdeInputDirPaths(
        inputdata=Path("data/inputdata"),
        invoice=Path("data/invoice"),
        tasksupport=Path("data/tasksupport"),
        config=fmtflags,
    )
    unpacked_dir_path = Path("data/temp")
    assert isinstance(
        selected_input_checker(src_paths, unpacked_dir_path, fmtflags.extended_mode),
        ExcelInvoiceChecker,
    )


def test_selected_input_checker_invoice(inputfile_single):
    fmtflags = Config(extended_mode=None, save_raw=True, save_thumbnail_image=False)
    src_paths = RdeInputDirPaths(
        inputdata=Path("data/inputdata"),
        invoice=Path("data/invoice"),
        tasksupport=Path("data/tasksupport"),
        config=fmtflags,
    )
    unpacked_dir_path = Path("data/temp")
    assert isinstance(selected_input_checker(src_paths, unpacked_dir_path, fmtflags.extended_mode), InvoiceChecker)
