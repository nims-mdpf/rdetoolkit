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
