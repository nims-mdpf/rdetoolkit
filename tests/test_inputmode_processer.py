import json
import os
import shutil
from pathlib import Path

import pytest
from rdetoolkit.models.rde2types import RdeDatasetPaths, RdeInputDirPaths, RdeOutputResourcePath
from rdetoolkit.modeproc import (
    copy_input_to_rawfile,
    copy_input_to_rawfile_for_rdeformat,
    excel_invoice_mode_process,
    invoice_mode_process,
    multifile_mode_process,
    rdeformat_mode_process,
)
from rdetoolkit.models.config import Config, SystemSettings, MultiDataTileSettings


@pytest.fixture
def dummy_files_tuple():
    dirname = Path("tests", "input")
    dirname.mkdir(exist_ok=True)
    path1 = dirname.joinpath("dummy1.txt")
    path1.touch()
    path2 = dirname.joinpath("dummy2.txt")
    path2.touch()

    yield tuple([path1, path2])

    if os.path.exists(dirname):
        shutil.rmtree(dirname)


@pytest.fixture
def dummy_files_rdeformat():
    dirnames = ["raw", "main_image", "other_image", "meta", "structured", "logs", "nonshared_raw"]
    rawfiles = []
    for name in dirnames:
        raw = Path("tests", name)
        raw.mkdir(exist_ok=True)
        rawpath = raw.joinpath("dummy.txt")
        rawpath.touch()
        rawfiles.append(rawpath)

    yield tuple(rawfiles)

    for name in dirnames:
        if os.path.exists(Path("tests", name)):
            shutil.rmtree(Path("tests", name))


@pytest.fixture
def invoice_json_with_desc():
    Path("data", "invoice").mkdir(parents=True, exist_ok=True)
    test_invoice_file = Path("data", "invoice").joinpath("invoice.json")
    shutil.copy(os.path.join(os.path.dirname(__file__), "samplefile", "invoice.json"), test_invoice_file)
    yield test_invoice_file

    if test_invoice_file.exists():
        test_invoice_file.unlink()


@pytest.fixture
def invoice_shcema_json_full():
    test_shcema_invoice_file = Path("data", "tasksupport").joinpath("invoice.schema.json")
    shutil.copy(os.path.join(os.path.dirname(__file__), "samplefile", "invoice.schema.json"), test_shcema_invoice_file)
    yield test_shcema_invoice_file

    if test_shcema_invoice_file.exists():
        test_shcema_invoice_file.unlink()


def test_copy_input_to_rawfile(dummy_files_tuple):
    temp_raw_file_dirname = Path("tests", "raws")
    temp_raw_file_dirname.mkdir(parents=True, exist_ok=True)
    copy_input_to_rawfile(temp_raw_file_dirname, dummy_files_tuple)

    assert len(list(temp_raw_file_dirname.glob("*"))) == 2

    if os.path.exists(Path("tests", "raws")):
        shutil.rmtree(Path("tests", "raws"))


def test_copy_input_to_rawfile_rdeformat(dummy_files_rdeformat):
    """Test the `copy_input_to_rawfile_for_rdeformat` function.

    This test verifies that the `copy_input_to_rawfile_for_rdeformat` function correctly copies input files
    to the appropriate directories in the RDE format.

    Steps:
    1. Create the necessary directory structure under "tests/result".
    2. Initialize an `RdeOutputResourcePath` object with paths to the created directories.
    3. Call the `copy_input_to_rawfile_for_rdeformat` function with the initialized paths.
    4. Assert that each directory contains exactly one file.
    5. Clean up by removing the "tests/result" directory.

    Args:
        dummy_files_rdeformat (list[Path]): List of dummy file paths to be used as input.

    """
    temp_raw_file_dirname = Path("tests", "result")
    temp_raw_file_dirname.mkdir(parents=True, exist_ok=True)
    dirnames = ["raw", "main_image", "other_image", "meta", "structured", "logs", "nonshared_raw"]
    for name in dirnames:
        raw = Path("tests", "result", name)
        raw.mkdir(exist_ok=True)

    paths = RdeOutputResourcePath(
        rawfiles=dummy_files_rdeformat,
        raw=Path("tests", "result", "raw"),
        main_image=Path("tests", "result", "main_image"),
        other_image=Path("tests", "result", "other_image"),
        meta=Path("tests", "result", "meta"),
        struct=Path("tests", "result", "structured"),
        logs=Path("tests", "result", "logs"),
        thumbnail=Path(),
        invoice=Path(),
        invoice_org=Path(),
        invoice_schema_json=Path(),
        nonshared_raw=Path("tests", "result", "nonshared_raw"),
    )

    copy_input_to_rawfile_for_rdeformat(paths)

    assert len(list(Path("tests", "result", "raw").glob("*"))) == 1
    assert len(list(Path("tests", "result", "main_image").glob("*"))) == 1
    assert len(list(Path("tests", "result", "other_image").glob("*"))) == 1
    assert len(list(Path("tests", "result", "meta").glob("*"))) == 1
    assert len(list(Path("tests", "result", "structured").glob("*"))) == 1
    assert len(list(Path("tests", "result", "logs").glob("*"))) == 1

    if os.path.exists(Path("tests", "result")):
        shutil.rmtree(Path("tests", "result"))


def test_invoice_mode_process_calls_functions(
    mocker,
    inputfile_single,
    ivnoice_json_none_sample_info,
    tasksupport,
    metadata_def_json_with_feature,
    metadata_json,
    ivnoice_schema_json_none_sample,
):
    """Invoice mode processテスト
    テスト対象: 以下の処理が実行されるかテスト
    - invoice上書き
    - データセット処理
    - 特徴量書き込み(既存のdescription: desc1を含む)
    - 各種バリデーションチェック
    - nonshared_rawフォルダへのコピー(defualt)
    - rawへのコピーが実行されないことを確認(defualt)
    """
    Path("data", "raw").mkdir(parents=True, exist_ok=True)
    Path("data", "nonshared_raw").mkdir(parents=True, exist_ok=True)
    Path("data", "main_image").mkdir(parents=True, exist_ok=True)
    Path("data", "other_image").mkdir(parents=True, exist_ok=True)
    Path("data", "meta").mkdir(parents=True, exist_ok=True)
    Path("data", "structured").mkdir(parents=True, exist_ok=True)
    Path("data", "logs").mkdir(parents=True, exist_ok=True)
    expected_description = "desc1\n特徴量1:test-value1\n特徴量2(V):test-value2\n特徴量3(V):test-value3"
    mock_datasets_process_function = mocker.Mock()

    config = Config(system=SystemSettings(extended_mode=None, save_raw=False, save_nonshared_raw=True, magic_variable=False, save_thumbnail_image=True), multidata_tile=MultiDataTileSettings(ignore_errors=False))
    srcpaths = RdeInputDirPaths(
        inputdata=Path("data", "inputdata"),
        invoice=Path("data", "invoice"),
        tasksupport=Path("data", "tasksupport"),
        config=config,
    )
    resource_paths = RdeOutputResourcePath(
        rawfiles=(
            [
                Path(inputfile_single),
            ]
        ),
        raw=Path("data", "raw"),
        main_image=Path("data", "main_image"),
        other_image=Path("data", "other_image"),
        meta=Path("data", "meta"),
        struct=Path("data", "structured"),
        logs=Path("data", "logs"),
        thumbnail=Path(),
        invoice=Path("data", "invoice"),
        invoice_org=Path(ivnoice_json_none_sample_info),
        invoice_schema_json=Path(ivnoice_schema_json_none_sample),
        nonshared_raw=Path("data", "nonshared_raw"),
    )

    # テスト対象の処理を実行
    invoice_mode_process("1", srcpaths, resource_paths, mock_datasets_process_function)

    # 関数が呼び出されたかどうかをチェック
    _assert_dataset_callback_called_once(mock_datasets_process_function, srcpaths, resource_paths)
    # invoiceのバックアップが実行されたかチェック
    assert os.path.exists(os.path.join("data", "invoice", "invoice.json"))
    # descriptionのチェック
    with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
        content = json.load(f)
    assert content["basic"]["description"] == expected_description
    # rawへのコピーが実行されないことを確認
    assert len(list(Path("data", "raw").glob("*"))) == 0
    # nonshared_rawへのコピーが実行されたかどうかをチェック
    assert len(list(Path("data", "nonshared_raw").glob("*"))) == 1


def test_invoice_mode_save_raw(
    mocker,
    inputfile_single,
    ivnoice_json_none_sample_info,
    tasksupport,
    metadata_def_json_with_feature,
    metadata_json,
    ivnoice_schema_json_none_sample,
):
    """Invoice mode processテスト
    テスト対象: 以下の処理が実行されるかテスト
    - invoice上書き
    - データセット処理
    - nonshared_rawフォルダへのコピーへのコピーが実行されない
    - rawへのコピーが実行される
    """
    Path("data", "raw").mkdir(parents=True, exist_ok=True)
    Path("data", "nonshared_raw").mkdir(parents=True, exist_ok=True)
    Path("data", "main_image").mkdir(parents=True, exist_ok=True)
    Path("data", "other_image").mkdir(parents=True, exist_ok=True)
    Path("data", "meta").mkdir(parents=True, exist_ok=True)
    Path("data", "structured").mkdir(parents=True, exist_ok=True)
    Path("data", "logs").mkdir(parents=True, exist_ok=True)
    mock_datasets_process_function = mocker.Mock()

    config = Config(system=SystemSettings(extended_mode=None, save_raw=True, save_nonshared_raw=False, magic_variable=False, save_thumbnail_image=True), multidata_tile=MultiDataTileSettings(ignore_errors=False))
    srcpaths = RdeInputDirPaths(
        inputdata=Path("data", "inputdata"),
        invoice=Path("data", "invoice"),
        tasksupport=Path("data", "tasksupport"),
        config=config,
    )
    resource_paths = RdeOutputResourcePath(
        rawfiles=(
            [
                Path(inputfile_single),
            ]
        ),
        raw=Path("data", "raw"),
        main_image=Path("data", "main_image"),
        other_image=Path("data", "other_image"),
        meta=Path("data", "meta"),
        struct=Path("data", "structured"),
        logs=Path("data", "logs"),
        thumbnail=Path(),
        invoice=Path("data", "invoice"),
        invoice_org=Path(ivnoice_json_none_sample_info),
        invoice_schema_json=Path(ivnoice_schema_json_none_sample),
        nonshared_raw=Path("data", "nonshared_raw"),
    )

    # テスト対象の処理を実行
    invoice_mode_process("1", srcpaths, resource_paths, mock_datasets_process_function)

    # 関数が呼び出されたかどうかをチェック
    _assert_dataset_callback_called_once(mock_datasets_process_function, srcpaths, resource_paths)
    # rawへのコピーが実行されないことを確認
    assert len(list(Path("data", "raw").glob("*"))) == 1
    # nonshared_rawへのコピーが実行されたかどうかをチェック
    assert len(list(Path("data", "nonshared_raw").glob("*"))) == 0


def test_invoice_mode_process_calls_functions_none_metadata_json(
    mocker,
    inputfile_single,
    ivnoice_json_none_sample_info,
    tasksupport,
    metadata_def_json_with_feature,
    ivnoice_schema_json_none_sample,
):
    """Invoice mode processテスト
    テスト対象: 以下の処理が実行されるかテスト
    - invoice上書き
    - データセット処理
    - 特徴量書き込み処理(特徴量なし)
    - 各種バリデーションチェック(metadata.jsonが存在しないケース)
        - metadata.jsonが存在しない場合、特徴量の書き込み処理は実行されない
    """
    Path("data", "raw").mkdir(parents=True, exist_ok=True)
    Path("data", "nonshared_raw").mkdir(parents=True, exist_ok=True)
    Path("data", "main_image").mkdir(parents=True, exist_ok=True)
    Path("data", "other_image").mkdir(parents=True, exist_ok=True)
    Path("data", "meta").mkdir(parents=True, exist_ok=True)
    Path("data", "structured").mkdir(parents=True, exist_ok=True)
    Path("data", "logs").mkdir(parents=True, exist_ok=True)
    expected_description = "desc1"
    mock_datasets_process_function = mocker.Mock()

    config = Config(system=SystemSettings(extended_mode=None, save_raw=False, save_nonshared_raw=True, magic_variable=False, save_thumbnail_image=True), multidata_tile=MultiDataTileSettings(ignore_errors=False))
    srcpaths = RdeInputDirPaths(
        inputdata=Path("data", "inputdata"),
        invoice=Path("data", "invoice"),
        tasksupport=Path("data", "tasksupport"),
        config=config,
    )

    resource_paths = RdeOutputResourcePath(
        rawfiles=(
            [
                Path(inputfile_single),
            ]
        ),
        raw=Path("data", "raw"),
        main_image=Path("data", "main_image"),
        other_image=Path("data", "other_image"),
        meta=Path("data", "meta"),
        struct=Path("data", "structured"),
        logs=Path("data", "logs"),
        thumbnail=Path(),
        invoice=Path("data", "invoice"),
        invoice_org=Path(ivnoice_json_none_sample_info),
        invoice_schema_json=Path(ivnoice_schema_json_none_sample),
        nonshared_raw=Path("data", "nonshared_raw"),
    )

    # テスト対象の処理を実行
    invoice_mode_process("1", srcpaths, resource_paths, mock_datasets_process_function)

    # 関数が呼び出されたかどうかをチェック
    _assert_dataset_callback_called_once(mock_datasets_process_function, srcpaths, resource_paths)
    # invoiceのバックアップが実行されたかチェック
    assert os.path.exists(os.path.join("data", "invoice", "invoice.json"))
    # descriptionのチェック
    with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
        content = json.load(f)
    assert content["basic"]["description"] == expected_description


def test_invoice_mode_process_calls_functions_with_magic_variable(
    mocker,
    inputfile_single,
    ivnoice_json_magic_filename_variable,
    tasksupport,
    metadata_def_json_with_feature,
    metadata_json,
    ivnoice_schema_json,
):
    """Invoice mode processテスト
    テスト対象: 以下の処理が実行されるかテスト
    - invoice上書き
    - データセット処理
    - ${filename}書き換え処理
        - invoice.jsonに記載された${filename}が書き換えられるかテスト
    - 各種バリデーションチェック
    """
    Path("data", "raw").mkdir(parents=True, exist_ok=True)
    Path("data", "nonshared_raw").mkdir(parents=True, exist_ok=True)
    Path("data", "nonshared_raw").mkdir(parents=True, exist_ok=True)
    Path("data", "main_image").mkdir(parents=True, exist_ok=True)
    Path("data", "other_image").mkdir(parents=True, exist_ok=True)
    Path("data", "meta").mkdir(parents=True, exist_ok=True)
    Path("data", "structured").mkdir(parents=True, exist_ok=True)
    Path("data", "logs").mkdir(parents=True, exist_ok=True)
    mock_datasets_process_function = mocker.Mock()

    config = Config(system=SystemSettings(extended_mode=None, save_raw=False, save_nonshared_raw=True, magic_variable=True, save_thumbnail_image=True), multidata_tile=MultiDataTileSettings(ignore_errors=False))
    srcpaths = RdeInputDirPaths(
        inputdata=Path("data", "inputdata"),
        invoice=Path("data", "invoice"),
        tasksupport=Path("data", "tasksupport"),
        config=config,
    )

    resource_paths = RdeOutputResourcePath(
        rawfiles=(
            [
                Path(inputfile_single),
            ]
        ),
        raw=Path("data", "raw"),
        main_image=Path("data", "main_image"),
        other_image=Path("data", "other_image"),
        meta=Path("data", "meta"),
        struct=Path("data", "structured"),
        logs=Path("data", "logs"),
        thumbnail=Path(),
        invoice=Path("data", "invoice"),
        invoice_org=Path(ivnoice_json_magic_filename_variable),
        invoice_schema_json=Path(ivnoice_schema_json),
        nonshared_raw=Path("data", "nonshared_raw"),
    )

    # テスト対象の処理を実行
    invoice_mode_process("1", srcpaths, resource_paths, mock_datasets_process_function)

    # 関数が呼び出されたかどうかをチェック
    _assert_dataset_callback_called_once(mock_datasets_process_function, srcpaths, resource_paths)
    # invoiceのバックアップが実行されたかチェック
    assert os.path.exists(os.path.join("data", "invoice", "invoice.json"))
    # descriptionのチェック
    with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
        content = json.load(f)
    assert content["basic"]["dataName"] == "test_single.txt"


def test_excel_invoice_mode_process_calls_functions(
    mocker,
    inputfile_single_dummy_header_excelinvoice,
    inputfile_zip_with_file,
    invoice_json_with_sample_info,
    tasksupport,
    metadata_def_json_with_feature,
    metadata_json,
    ivnoice_schema_json_none_specificAttributes,
):
    """Excelinvoice mode processテスト
    テスト対象: 以下の処理が実行されるかテスト
    - invoice上書き
    - データセット処理
    - 特徴量書き込み
        - 既存のdescription: desc1を含む
    - 各種バリデーションチェック
    - nonshared_rawフォルダへのコピー(defualt)
    - rawへのコピーが実行されないことを確認(defualt)
    """
    # 事前準備: フィクスチャ
    Path("data", "raw").mkdir(parents=True, exist_ok=True)
    Path("data", "nonshared_raw").mkdir(parents=True, exist_ok=True)
    Path("data", "main_image").mkdir(parents=True, exist_ok=True)
    Path("data", "other_image").mkdir(parents=True, exist_ok=True)
    Path("data", "meta").mkdir(parents=True, exist_ok=True)
    Path("data", "structured").mkdir(parents=True, exist_ok=True)
    Path("data", "logs").mkdir(parents=True, exist_ok=True)
    Path("data", "temp").mkdir(parents=True, exist_ok=True)
    shutil.copy(
        Path("data", "invoice").joinpath("invoice.json"),
        Path("data", "temp", "invoice_org.json"),
    )
    shutil.unpack_archive(Path("data", "inputdata", "test_input_multi.zip"), Path("data", "temp"))
    expected_description = "desc1\n特徴量1:test-value1\n特徴量2(V):test-value2\n特徴量3(V):test-value3"

    config = Config(system=SystemSettings(extended_mode=None, save_raw=False, save_nonshared_raw=True, magic_variable=True, save_thumbnail_image=True), multidata_tile=MultiDataTileSettings(ignore_errors=False))
    srcpaths = RdeInputDirPaths(
        inputdata=Path("data", "inputdata"),
        invoice=Path("data", "invoice"),
        tasksupport=Path("data", "tasksupport"),
        config=config,
    )

    resource_paths = RdeOutputResourcePath(
        rawfiles=(
            [
                Path("data", "temp", "test_child1.txt"),
            ]
        ),
        raw=Path("data", "raw"),
        main_image=Path("data", "main_image"),
        other_image=Path("data", "other_image"),
        meta=Path("data", "meta"),
        struct=Path("data", "structured"),
        logs=Path("data", "logs"),
        thumbnail=Path(),
        invoice=Path("data", "invoice"),
        invoice_org=Path("data", "temp", "invoice_org.json"),
        invoice_schema_json=Path(ivnoice_schema_json_none_specificAttributes),
        nonshared_raw=Path("data", "nonshared_raw"),
    )

    # 関数のモック
    mock_datasets_process_function = mocker.Mock()

    # テスト対象の関数を実行
    excel_invoice_mode_process(srcpaths, resource_paths, inputfile_single_dummy_header_excelinvoice, 0, mock_datasets_process_function)

    # 関数が呼び出されたかどうかをチェック
    _assert_dataset_callback_called_once(mock_datasets_process_function, srcpaths, resource_paths)
    # invoiceのバックアップが実行されたかチェック
    # descriptionがバックアップ後に実行されるため内容が一致しない。
    with open(os.path.join("data", "temp", "invoice_org.json"), encoding="utf-8") as f:
        contents_backup = json.load(f)
    with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
        contents_origin = json.load(f)
    assert contents_backup != contents_origin
    # descriptionのチェック
    with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
        content = json.load(f)
    assert content["basic"]["description"] == expected_description
    # rawへのコピーが実行されないことを確認
    assert len(list(Path("data", "raw").glob("*"))) == 0
    # nonshared_rawへのコピーが実行されたかどうかをチェック
    assert len(list(Path("data", "nonshared_raw").glob("*"))) >= 1


def test_excel_invoice_save_raw(
    mocker,
    inputfile_single_dummy_header_excelinvoice,
    inputfile_zip_with_file,
    invoice_json_with_sample_info,
    tasksupport,
    metadata_def_json_with_feature,
    metadata_json,
    ivnoice_schema_json_none_specificAttributes,
):
    """Excelinvoice mode processテスト
    テスト対象: 以下の処理が実行されるかテスト
    - invoice上書き
    - データセット処理
    - 特徴量書き込み
        - 既存のdescription: desc1を含む
    - 各種バリデーションチェック
    - nonshared_rawフォルダへのコピーされない
    - rawへのコピーが実行
    """
    # 事前準備: フィクスチャ
    Path("data", "raw").mkdir(parents=True, exist_ok=True)
    Path("data", "nonshared_raw").mkdir(parents=True, exist_ok=True)
    Path("data", "main_image").mkdir(parents=True, exist_ok=True)
    Path("data", "other_image").mkdir(parents=True, exist_ok=True)
    Path("data", "meta").mkdir(parents=True, exist_ok=True)
    Path("data", "structured").mkdir(parents=True, exist_ok=True)
    Path("data", "logs").mkdir(parents=True, exist_ok=True)
    Path("data", "temp").mkdir(parents=True, exist_ok=True)
    shutil.copy(
        Path("data", "invoice").joinpath("invoice.json"),
        Path("data", "temp", "invoice_org.json"),
    )
    shutil.unpack_archive(Path("data", "inputdata", "test_input_multi.zip"), Path("data", "temp"))
    expected_description = "desc1\n特徴量1:test-value1\n特徴量2(V):test-value2\n特徴量3(V):test-value3"

    config = Config(system=SystemSettings(extended_mode=None, save_raw=True, save_nonshared_raw=False, magic_variable=True, save_thumbnail_image=True), multidata_tile=MultiDataTileSettings(ignore_errors=False))
    srcpaths = RdeInputDirPaths(
        inputdata=Path("data", "inputdata"),
        invoice=Path("data", "invoice"),
        tasksupport=Path("data", "tasksupport"),
        config=config,
    )

    resource_paths = RdeOutputResourcePath(
        rawfiles=(
            [
                Path("data", "temp", "test_child1.txt"),
            ]
        ),
        raw=Path("data", "raw"),
        main_image=Path("data", "main_image"),
        other_image=Path("data", "other_image"),
        meta=Path("data", "meta"),
        struct=Path("data", "structured"),
        logs=Path("data", "logs"),
        thumbnail=Path(),
        invoice=Path("data", "invoice"),
        invoice_org=Path("data", "temp", "invoice_org.json"),
        invoice_schema_json=Path(ivnoice_schema_json_none_specificAttributes),
        nonshared_raw=Path("data", "nonshared_raw"),
    )

    # 関数のモック
    mock_datasets_process_function = mocker.Mock()

    # テスト対象の関数を実行
    excel_invoice_mode_process(srcpaths, resource_paths, inputfile_single_dummy_header_excelinvoice, 0, mock_datasets_process_function)

    # 関数が呼び出されたかどうかをチェック
    _assert_dataset_callback_called_once(mock_datasets_process_function, srcpaths, resource_paths)
    # invoiceのバックアップが実行されたかチェック
    # descriptionがバックアップ後に実行されるため内容が一致しない。
    with open(os.path.join("data", "temp", "invoice_org.json"), encoding="utf-8") as f:
        contents_backup = json.load(f)
    with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
        contents_origin = json.load(f)
    assert contents_backup != contents_origin
    # descriptionのチェック
    with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
        content = json.load(f)
    assert content["basic"]["description"] == expected_description
    # rawへのコピーが実行されることを確認
    assert len(list(Path("data", "raw").glob("*"))) >= 1
    # nonshared_rawへのコピーが実行されないことを確認
    assert len(list(Path("data", "nonshared_raw").glob("*"))) == 0


def test_excel_invoice_mode_process_calls_functions_none_metadatajson(
    mocker,
    inputfile_single_dummy_header_excelinvoice,
    inputfile_zip_with_file,
    invoice_json_with_sample_info,
    tasksupport,
    metadata_def_json_with_feature,
    ivnoice_schema_json_none_specificAttributes,
):
    """Excelinvoice mode processテスト
    テスト対象: 以下の処理が実行されるかテスト
    - invoice上書き
    - データセット処理
    - 特徴量書き込み
        - 既存のdescription: desc1を含む
    - 各種バリデーションチェック
        - metadata.jsonが存在しない
    """
    # 事前準備: フィクスチャ
    Path("data", "raw").mkdir(parents=True, exist_ok=True)
    Path("data", "nonshared_raw").mkdir(parents=True, exist_ok=True)
    Path("data", "main_image").mkdir(parents=True, exist_ok=True)
    Path("data", "other_image").mkdir(parents=True, exist_ok=True)
    Path("data", "meta").mkdir(parents=True, exist_ok=True)
    Path("data", "structured").mkdir(parents=True, exist_ok=True)
    Path("data", "logs").mkdir(parents=True, exist_ok=True)
    Path("data", "temp").mkdir(parents=True, exist_ok=True)
    shutil.copy(
        Path("data", "invoice").joinpath("invoice.json"),
        Path("data", "temp", "invoice_org.json"),
    )
    shutil.unpack_archive(Path("data", "inputdata", "test_input_multi.zip"), Path("data", "temp"))
    expected_description = "desc1"

    config = Config(system=SystemSettings(extended_mode=None, save_raw=True, save_nonshared_raw=False, magic_variable=True, save_thumbnail_image=True), multidata_tile=MultiDataTileSettings(ignore_errors=False))
    srcpaths = RdeInputDirPaths(
        inputdata=Path("data", "inputdata"),
        invoice=Path("data", "invoice"),
        tasksupport=Path("data", "tasksupport"),
        config=config,
    )

    resource_paths = RdeOutputResourcePath(
        rawfiles=(
            [
                Path("data", "temp", "test_child1.txt"),
            ]
        ),
        raw=Path("data", "raw"),
        main_image=Path("data", "main_image"),
        other_image=Path("data", "other_image"),
        meta=Path("data", "meta"),
        struct=Path("data", "structured"),
        logs=Path("data", "logs"),
        thumbnail=Path(),
        invoice=Path("data", "invoice"),
        invoice_org=Path("data", "temp", "invoice_org.json"),
        invoice_schema_json=Path(ivnoice_schema_json_none_specificAttributes),
        nonshared_raw=Path("data", "nonshared_raw"),
    )

    # 関数のモック
    mock_datasets_process_function = mocker.Mock()

    # テスト対象の関数を実行
    excel_invoice_mode_process(srcpaths, resource_paths, inputfile_single_dummy_header_excelinvoice, 0, mock_datasets_process_function)

    # 関数が呼び出されたかどうかをチェック
    _assert_dataset_callback_called_once(mock_datasets_process_function, srcpaths, resource_paths)
    # invoiceのバックアップが実行されたかチェック
    # descriptionがバックアップ後に実行されるため内容が一致しない。
    with open(os.path.join("data", "temp", "invoice_org.json"), encoding="utf-8") as f:
        contents_backup = json.load(f)
    with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
        contents_origin = json.load(f)
    assert contents_backup != contents_origin
    # descriptionのチェック
    with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
        content = json.load(f)
    assert content["basic"]["description"] == expected_description


def test_excel_invoice_mode_process_calls_functions_replace_magic_variable(
    mocker,
    inputfile_single_dummy_header_excelinvoice_with_magic_variable,
    inputfile_zip_with_file,
    ivnoice_json_none_sample_info,
    tasksupport,
    metadata_def_json_with_feature,
    metadata_json,
    ivnoice_schema_json_none_sample,
):
    """Excelinvoice mode processテスト
    テスト対象: 以下の処理が実行されるかテスト
    - invoice上書き
    - データセット処理
    - ${filename}の書き換え処理
        - ファイルモードのとき、${filename}の書き換えが実行されるか
    - 各種バリデーションチェック
    """
    # 事前準備: フィクスチャ
    Path("data", "raw").mkdir(parents=True, exist_ok=True)
    Path("data", "main_image").mkdir(parents=True, exist_ok=True)
    Path("data", "other_image").mkdir(parents=True, exist_ok=True)
    Path("data", "meta").mkdir(parents=True, exist_ok=True)
    Path("data", "structured").mkdir(parents=True, exist_ok=True)
    Path("data", "logs").mkdir(parents=True, exist_ok=True)
    Path("data", "temp").mkdir(parents=True, exist_ok=True)
    Path("data", "nonshared_raw").mkdir(parents=True, exist_ok=True)
    shutil.copy(
        Path("data", "invoice").joinpath("invoice.json"),
        Path("data", "temp", "invoice_org.json"),
    )
    shutil.unpack_archive(Path("data", "inputdata", "test_input_multi.zip"), Path("data", "temp"))

    config = Config(system=SystemSettings(extended_mode=None, save_raw=False, save_nonshared_raw=True, magic_variable=True, save_thumbnail_image=True), multidata_tile=MultiDataTileSettings(ignore_errors=False))
    srcpaths = RdeInputDirPaths(
        inputdata=Path("data", "inputdata"),
        invoice=Path("data", "invoice"),
        tasksupport=Path("data", "tasksupport"),
        config=config,
    )

    resource_paths = RdeOutputResourcePath(
        rawfiles=(
            [
                Path("data", "temp", "test_child1.txt"),
            ]
        ),
        raw=Path("data", "raw"),
        main_image=Path("data", "main_image"),
        other_image=Path("data", "other_image"),
        meta=Path("data", "meta"),
        struct=Path("data", "structured"),
        logs=Path("data", "logs"),
        thumbnail=Path(),
        invoice=Path("data", "invoice"),
        invoice_org=Path("data", "temp", "invoice_org.json"),
        invoice_schema_json=Path(ivnoice_schema_json_none_sample),
        nonshared_raw=Path("data", "nonshared_raw"),
    )
    # 関数のモック
    mock_datasets_process_function = mocker.Mock()

    # テスト対象の関数を実行
    excel_invoice_mode_process(
        srcpaths, resource_paths, inputfile_single_dummy_header_excelinvoice_with_magic_variable, 0, mock_datasets_process_function,
    )

    # 関数が呼び出されたかどうかをチェック
    _assert_dataset_callback_called_once(mock_datasets_process_function, srcpaths, resource_paths)
    # invoiceのバックアップが実行されたかチェック
    # descriptionがバックアップ後に実行されるため内容が一致しない。
    with open(os.path.join("data", "temp", "invoice_org.json"), encoding="utf-8") as f:
        contents_backup = json.load(f)
    with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
        contents_origin = json.load(f)
    assert contents_backup != contents_origin
    # descriptionのチェック
    with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
        content = json.load(f)
    assert content["basic"]["dataName"] == "test_child1.txt"


def test_multifile_mode_process_calls_functions(
    mocker,
    inputfile_multi,
    ivnoice_json_magic_filename_variable,
    tasksupport,
    metadata_def_json_with_feature,
    metadata_json,
    ivnoice_schema_json,
):
    """Multifile mode processテスト
    テスト対象: 以下の処理が実行されるかテスト
    - invoice上書き
    - データセット処理
    - 特徴量書き込み処理
        - 既存のdescription: desc1を含む
    - 各種バリデーションチェック
    - nonshared_rawフォルダへのコピー(defualt)
    - rawへのコピーが実行されないことを確認(defualt)
    """
    Path("data", "raw").mkdir(parents=True, exist_ok=True)
    Path("data", "nonshared_raw").mkdir(parents=True, exist_ok=True)
    Path("data", "main_image").mkdir(parents=True, exist_ok=True)
    Path("data", "other_image").mkdir(parents=True, exist_ok=True)
    Path("data", "meta").mkdir(parents=True, exist_ok=True)
    Path("data", "structured").mkdir(parents=True, exist_ok=True)
    Path("data", "logs").mkdir(parents=True, exist_ok=True)
    Path("data", "temp").mkdir(parents=True, exist_ok=True)
    shutil.copy(
        Path("data", "invoice").joinpath("invoice.json"),
        Path("data", "temp", "invoice_org.json"),
    )
    expected_description = "desc1\n特徴量1:test-value1\n特徴量2(V):test-value2\n特徴量3(V):test-value3"
    mock_datasets_process_function = mocker.Mock()

    config = Config(system=SystemSettings(extended_mode="MultiDataTile", save_raw=False, save_nonshared_raw=True, magic_variable=True, save_thumbnail_image=True), multidata_tile=MultiDataTileSettings(ignore_errors=False))
    srcpaths = RdeInputDirPaths(
        inputdata=Path("data", "inputdata"),
        invoice=Path("data", "invoice"),
        tasksupport=Path("data", "tasksupport"),
        config=config,
    )
    resource_paths = RdeOutputResourcePath(
        rawfiles=(inputfile_multi),
        raw=Path("data", "raw"),
        main_image=Path("data", "main_image"),
        other_image=Path("data", "other_image"),
        meta=Path("data", "meta"),
        struct=Path("data", "structured"),
        logs=Path("data", "logs"),
        thumbnail=Path(),
        invoice=Path("data", "invoice"),
        invoice_org=Path("data", "temp", "invoice_org.json"),
        invoice_schema_json=Path(ivnoice_schema_json),
        nonshared_raw=Path("data", "nonshared_raw"),
    )

    # テスト対象の処理を実行
    multifile_mode_process("1", srcpaths, resource_paths, mock_datasets_process_function)

    # 関数が呼び出されたかどうかをチェック
    _assert_dataset_callback_called_once(mock_datasets_process_function, srcpaths, resource_paths)

    # invoiceのバックアップが実行されたかチェック
    # descriptionがバックアップ後に実行されるため内容が一致しない。
    with open(os.path.join("data", "temp", "invoice_org.json"), encoding="utf-8") as f:
        contents_backup = json.load(f)
    with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
        contents_origin = json.load(f)
    assert contents_backup != contents_origin

    # rawfileのバックアップが実行されたかチェック
    for file in resource_paths.rawfiles:
        assert os.path.exists(file)

    # descriptionのチェック
    with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
        content = json.load(f)
    assert content["basic"]["description"] == expected_description
    # rawへのコピーが実行されないことを確認
    assert len(list(Path("data", "raw").glob("*"))) == 0
    # nonshared_rawへのコピーが実行されたか確認
    assert len(list(Path("data", "nonshared_raw").glob("*"))) >= 1


def test_multifile_save_raw(
    mocker,
    inputfile_multi,
    ivnoice_json_magic_filename_variable,
    tasksupport,
    metadata_def_json_with_feature,
    metadata_json,
    ivnoice_schema_json,
):
    """Multifile mode processテスト
    テスト対象: 以下の処理が実行されるかテスト
    - invoice上書き
    - データセット処理
    - 特徴量書き込み処理
        - 既存のdescription: desc1を含む
    - 各種バリデーションチェック
    - nonshared_rawフォルダへのコピーへ実行されない
    - rawへのコピーが実行されたことを確認
    """
    Path("data", "raw").mkdir(parents=True, exist_ok=True)
    Path("data", "nonshared_raw").mkdir(parents=True, exist_ok=True)
    Path("data", "main_image").mkdir(parents=True, exist_ok=True)
    Path("data", "other_image").mkdir(parents=True, exist_ok=True)
    Path("data", "meta").mkdir(parents=True, exist_ok=True)
    Path("data", "structured").mkdir(parents=True, exist_ok=True)
    Path("data", "logs").mkdir(parents=True, exist_ok=True)
    Path("data", "temp").mkdir(parents=True, exist_ok=True)
    shutil.copy(
        Path("data", "invoice").joinpath("invoice.json"),
        Path("data", "temp", "invoice_org.json"),
    )
    expected_description = "desc1\n特徴量1:test-value1\n特徴量2(V):test-value2\n特徴量3(V):test-value3"
    mock_datasets_process_function = mocker.Mock()

    config = Config(system=SystemSettings(extended_mode="MultiDataTile", save_raw=True, save_nonshared_raw=False, magic_variable=True, save_thumbnail_image=True), multidata_tile=MultiDataTileSettings(ignore_errors=False))
    srcpaths = RdeInputDirPaths(
        inputdata=Path("data", "inputdata"),
        invoice=Path("data", "invoice"),
        tasksupport=Path("data", "tasksupport"),
        config=config,
    )
    resource_paths = RdeOutputResourcePath(
        rawfiles=(inputfile_multi),
        raw=Path("data", "raw"),
        main_image=Path("data", "main_image"),
        other_image=Path("data", "other_image"),
        meta=Path("data", "meta"),
        struct=Path("data", "structured"),
        logs=Path("data", "logs"),
        thumbnail=Path(),
        invoice=Path("data", "invoice"),
        invoice_org=Path("data", "temp", "invoice_org.json"),
        invoice_schema_json=Path(ivnoice_schema_json),
        nonshared_raw=Path("data", "nonshared_raw"),
    )

    # テスト対象の処理を実行
    multifile_mode_process("1", srcpaths, resource_paths, mock_datasets_process_function)

    # 関数が呼び出されたかどうかをチェック
    _assert_dataset_callback_called_once(mock_datasets_process_function, srcpaths, resource_paths)

    # invoiceのバックアップが実行されたかチェック
    # descriptionがバックアップ後に実行されるため内容が一致しない。
    with open(os.path.join("data", "temp", "invoice_org.json"), encoding="utf-8") as f:
        contents_backup = json.load(f)
    with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
        contents_origin = json.load(f)
    assert contents_backup != contents_origin

    # rawfileのバックアップが実行されたかチェック
    for file in resource_paths.rawfiles:
        assert os.path.exists(file)

    # descriptionのチェック
    with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
        content = json.load(f)
    assert content["basic"]["description"] == expected_description
    # rawへのコピーが実行されないことを確認
    assert len(list(Path("data", "raw").glob("*"))) >= 1
    # nonshared_rawへのコピーが実行されたか確認
    assert len(list(Path("data", "nonshared_raw").glob("*"))) == 0


def test_multifile_mode_process_calls_functions_none_metadata_json(
    mocker,
    inputfile_multi,
    ivnoice_json_magic_filename_variable,
    tasksupport,
    metadata_def_json_with_feature,
    ivnoice_schema_json,
):
    """Multifile mode processテスト
    テスト対象: 以下の処理が実行されるかテスト
    - invoice上書き
    - データセット処理
    - 特徴量書き込み処理
    - 各種バリデーションチェック(metadata.jsonが存在しない)
    metadata.jsonが存在しない場合、特徴量の書き込み処理は実行されない
    """
    Path("data", "raw").mkdir(parents=True, exist_ok=True)
    Path("data", "nonshared_raw").mkdir(parents=True, exist_ok=True)
    Path("data", "main_image").mkdir(parents=True, exist_ok=True)
    Path("data", "other_image").mkdir(parents=True, exist_ok=True)
    Path("data", "meta").mkdir(parents=True, exist_ok=True)
    Path("data", "structured").mkdir(parents=True, exist_ok=True)
    Path("data", "logs").mkdir(parents=True, exist_ok=True)
    Path("data", "temp").mkdir(parents=True, exist_ok=True)
    shutil.copy(
        Path("data", "invoice").joinpath("invoice.json"),
        Path("data", "temp", "invoice_org.json"),
    )
    expected_description = "desc1"
    mock_datasets_process_function = mocker.Mock()

    config = Config(system=SystemSettings(extended_mode="MultiDataTile", save_raw=False, save_nonshared_raw=True, magic_variable=True, save_thumbnail_image=True), multidata_tile=MultiDataTileSettings(ignore_errors=False))
    srcpaths = RdeInputDirPaths(
        inputdata=Path("data", "inputdata"),
        invoice=Path("data", "invoice"),
        tasksupport=Path("data", "tasksupport"),
        config=config,
    )

    resource_paths = RdeOutputResourcePath(
        rawfiles=(inputfile_multi),
        raw=Path("data", "raw"),
        main_image=Path("data", "main_image"),
        other_image=Path("data", "other_image"),
        meta=Path("data", "meta"),
        struct=Path("data", "structured"),
        logs=Path("data", "logs"),
        thumbnail=Path(),
        invoice=Path("data", "invoice"),
        invoice_org=Path("data", "temp", "invoice_org.json"),
        invoice_schema_json=Path(ivnoice_schema_json),
        nonshared_raw=Path("data", "nonshared_raw"),
    )

    # テスト対象の処理を実行
    multifile_mode_process("1", srcpaths, resource_paths, mock_datasets_process_function)

    # 関数が呼び出されたかどうかをチェック
    _assert_dataset_callback_called_once(mock_datasets_process_function, srcpaths, resource_paths)

    # invoiceのバックアップが実行されたかチェック
    # descriptionがバックアップ後に実行されるため内容が一致しない。
    with open(os.path.join("data", "temp", "invoice_org.json"), encoding="utf-8") as f:
        contents_backup = json.load(f)
    with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
        contents_origin = json.load(f)
    assert contents_backup != contents_origin

    # rawfileのバックアップが実行されたかチェック
    for file in resource_paths.rawfiles:
        assert os.path.exists(file)

    # descriptionのチェック
    with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
        content = json.load(f)
    assert content["basic"]["description"] == expected_description


# def test_multifile_mode_process_calls_functions_raise_exception_skip(
#     mocker,
#     inputfile_multi,
#     ivnoice_json_magic_filename_variable,
#     tasksupport_skip_multi_setting,
#     metadata_def_json_with_feature,
#     ivnoice_schema_json,
#     caplog,  # warningを検出
# ):
#     """multifile mode processテスト
#     テスト対象: 以下の処理が実行されるかテスト
#     - invoice上書き
#     - データセット処理(例外が発生しても処理が継続されるかテスト)
#     - 特徴量書き込み処理
#     - 各種バリデーションチェック(metadata.jsonが存在しない)
#     metadata.jsonが存在しない場合、特徴量の書き込み処理は実行されない
#     """
#     Path("data", "raw").mkdir(parents=True, exist_ok=True)
#     Path("data", "main_image").mkdir(parents=True, exist_ok=True)
#     Path("data", "other_image").mkdir(parents=True, exist_ok=True)
#     Path("data", "meta").mkdir(parents=True, exist_ok=True)
#     Path("data", "structured").mkdir(parents=True, exist_ok=True)
#     Path("data", "logs").mkdir(parents=True, exist_ok=True)
#     Path("data", "temp").mkdir(parents=True, exist_ok=True)
#     shutil.copy(
#         Path("data", "invoice").joinpath("invoice.json"),
#         Path("data", "temp", "invoice_org.json"),
#     )
#     expected_description = "desc1"

#     config = Config(system=SystemSettings(extended_mode="MultiDataTile", save_raw=True, magic_variable=True, save_thumbnail_image=True), multidata_tile=MultiDataTileSettings(ignore_errors=True))
#     srcpaths = RdeInputDirPaths(
#         inputdata=Path("data", "inputdata"),
#         invoice=Path("data", "invoice"),
#         tasksupport=Path("data", "tasksupport"),
#         config=config,
#     )

#     resource_paths = RdeOutputResourcePath(
#         rawfiles=(inputfile_multi),
#         raw=Path("data", "raw"),
#         main_image=Path("data", "main_image"),
#         other_image=Path("data", "other_image"),
#         meta=Path("data", "meta"),
#         struct=Path("data", "structured"),
#         logs=Path("data", "logs"),
#         thumbnail=Path(),
#         invoice=Path("data", "invoice"),
#         invoice_org=Path("data", "temp", "invoice_org.json"),
#         invoice_schema_json=Path(ivnoice_schema_json),
#     )

#     def custom_dataset_process(srcpaths, resource_paths):
#         raise Exception("test exception")

#     # テスト対象の処理を実行
#     with caplog.at_level(logging.WARNING):
#         multifile_mode_process(srcpaths, resource_paths, custom_dataset_process)

#     # エラースキップフラグがTrueの場合、Warningを検知できるかテスト
#     warnings = [record for record in caplog.records if record.levelname == "WARNING"]
#     assert len(warnings) > 0

#     # invoiceのバックアップが実行されたかチェック
#     # descriptionがバックアップ後に実行されるため内容が一致しない。
#     with open(os.path.join("data", "temp", "invoice_org.json"), encoding="utf-8") as f:
#         contents_backup = json.load(f)
#     with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
#         contents_origin = json.load(f)
#     assert contents_backup != contents_origin

#     # rawfileのバックアップが実行されたかチェック
#     for file in resource_paths.rawfiles:
#         assert os.path.exists(file)

#     # descriptionのチェック
#     with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
#         content = json.load(f)
#     assert content["basic"]["description"] == expected_description


def test_multifile_mode_process_calls_functions_replace_magic_filename(
    mocker,
    inputfile_multi,
    ivnoice_json_magic_filename_variable,
    tasksupport,
    metadata_def_json_with_feature,
    metadata_json,
    ivnoice_schema_json,
):
    """multifile_mode_processモード時、
    - invoice上書き
    - データセット処理
    - 特徴量書き込み
    - 既存のdescription: desc1を含む
    - nonshared_rawフォルダへのコピーへ実行される
    - rawへのコピーが実行されない
    """
    inputfile_multi.sort()
    input1_path_lists = [
        Path("data", "raw"),
        Path("data", "nonshared_raw"),
        Path("data", "main_image"),
        Path("data", "other_image"),
        Path("data", "meta"),
        Path("data", "structured"),
        Path("data", "logs"),
        Path("data", "temp"),
    ]
    for path in input1_path_lists:
        path.mkdir(parents=True, exist_ok=True)

    # common process
    shutil.copy(
        Path("data", "invoice").joinpath("invoice.json"),
        Path("data", "temp", "invoice_org.json"),
    )

    config = Config(system=SystemSettings(extended_mode="MultiDataTile", save_raw=False, save_nonshared_raw=True, magic_variable=True, save_thumbnail_image=True), multidata_tile=MultiDataTileSettings(ignore_errors=False))
    srcpaths = RdeInputDirPaths(
        inputdata=Path("data", "inputdata"),
        invoice=Path("data", "invoice"),
        tasksupport=Path("data", "tasksupport"),
        config=config,
    )
    resource_paths1 = RdeOutputResourcePath(
        rawfiles=(inputfile_multi[0],),
        raw=Path("data", "raw"),
        main_image=Path("data", "main_image"),
        other_image=Path("data", "other_image"),
        meta=Path("data", "meta"),
        struct=Path("data", "structured"),
        logs=Path("data", "logs"),
        thumbnail=Path(),
        invoice=Path("data", "invoice"),
        invoice_org=Path("data", "temp", "invoice_org.json"),
        invoice_schema_json=Path(ivnoice_schema_json),
        nonshared_raw=Path("data", "nonshared_raw"),
    )

    input2_path_lists = [
        Path("data", "divided", f"{1:04d}", "invoice"),
        Path("data", "divided", f"{1:04d}", "raw"),
        Path("data", "divided", f"{1:04d}", "nonshared_raw"),
        Path("data", "divided", f"{1:04d}", "main_image"),
        Path("data", "divided", f"{1:04d}", "other_image"),
        Path("data", "divided", f"{1:04d}", "meta"),
        Path("data", "divided", f"{1:04d}", "structured"),
        Path("data", "divided", f"{1:04d}", "logs"),
    ]
    for path in input2_path_lists:
        path.mkdir(parents=True, exist_ok=True)
    shutil.copy(metadata_json, Path("data", "divided", f"{1:04d}", "meta"))

    resource_paths2 = RdeOutputResourcePath(
        rawfiles=(inputfile_multi[1],),
        raw=Path("data", "divided", f"{1:04d}", "raw"),
        main_image=Path("data", "divided", f"{1:04d}", "main_image"),
        other_image=Path("data", "divided", f"{1:04d}", "other_image"),
        meta=Path("data", "divided", f"{1:04d}", "meta"),
        struct=Path("data", "divided", f"{1:04d}", "structured"),
        logs=Path("data", "divided", f"{1:04d}", "logs"),
        thumbnail=Path(),
        invoice=Path("data", "divided", f"{1:04d}", "invoice"),
        invoice_org=Path("data", "temp", "invoice_org.json"),
        invoice_schema_json=Path(ivnoice_schema_json),
        nonshared_raw=Path("data", "divided", f"{1:04d}", "nonshared_raw"),
    )

    expected_filename1 = "test_child1.txt"
    expected_filename2 = "test_child2.txt"

    mock_datasets_process_function = mocker.Mock()

    # テスト対象の処理を実行
    for idx in range(2):
        if idx == 0:
            resource_paths = resource_paths1
            expected_filename = expected_filename1
            invoice = Path("data", "invoice", "invoice.json")
        else:
            resource_paths = resource_paths2
            expected_filename = expected_filename2
            invoice = Path("data", "divided", f"{1:04d}", "invoice", "invoice.json")

        multifile_mode_process("1", srcpaths, resource_paths, mock_datasets_process_function)

        # 関数が呼び出されたかどうかをチェック
        _assert_dataset_callback_called_with(mock_datasets_process_function, srcpaths, resource_paths, idx)

        # invoiceのバックアップが実行されたかチェック
        # descriptionがバックアップ後に実行されるため内容が一致しない。
        with open(os.path.join("data", "temp", "invoice_org.json"), encoding="utf-8") as f:
            contents_backup = json.load(f)
        with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
            contents_origin = json.load(f)
        assert contents_backup != contents_origin

        # rawfileのバックアップが実行されたかチェック
        for file in resource_paths.rawfiles:
            assert os.path.exists(file)

        with open(invoice, encoding="utf-8") as f:
            content = json.load(f)
        # ${filename}の書き換えの実行
        assert content["basic"]["dataName"] == expected_filename

        # rawへのコピーが実行されないことを確認
        assert len(list(resource_paths.raw.glob("*"))) == 0
        # nonshared_rawへのコピーが実行されたか確認
        assert len(list(resource_paths.nonshared_raw.glob("*"))) >= 1


def test_rdeformat_mode_process_alls_functions(
    mocker,
    inputfile_rdeformat,
    invoice_json_with_desc,
    tasksupport,
    metadata_def_json_with_feature,
    metadata_json,
    invoice_shcema_json_full,
):
    """Rdeformat mode processテスト
    テスト対象: 以下の処理が実行されるかテスト
    - invoice上書き
    - データセット処理
    - 特徴量書き込み処理
        - 既存のdescription: desc1を含む
    - 各種バリデーションチェック
    """
    Path("data", "raw").mkdir(parents=True, exist_ok=True)
    Path("data", "nonshared_raw").mkdir(parents=True, exist_ok=True)
    Path("data", "main_image").mkdir(parents=True, exist_ok=True)
    Path("data", "other_image").mkdir(parents=True, exist_ok=True)
    Path("data", "meta").mkdir(parents=True, exist_ok=True)
    Path("data", "structured").mkdir(parents=True, exist_ok=True)
    Path("data", "logs").mkdir(parents=True, exist_ok=True)
    Path("data", "temp").mkdir(parents=True, exist_ok=True)
    Path("data", "thumbnail").mkdir(parents=True, exist_ok=True)
    zip_path = Path("data", "inputdata") / Path(inputfile_rdeformat).name
    shutil.unpack_archive(zip_path, Path("data", "temp"))

    shutil.copy(
        Path("data", "invoice").joinpath("invoice.json"),
        Path("data", "temp", "invoice_org.json"),
    )
    Path("data/main_image/dummy_file.png").touch()
    expected_description = "特徴量1:test-value1\n特徴量2(V):test-value2\n特徴量3(V):test-value3"
    mock_datasets_process_function = mocker.Mock()

    raw_files = tuple(f for f in Path("data", "temp").rglob("*") if f.is_file())

    config = Config(system=SystemSettings(extended_mode="rdeformat", save_raw=True, save_nonshared_raw=False, magic_variable=False, save_thumbnail_image=True), multidata_tile=MultiDataTileSettings(ignore_errors=False))
    srcpaths = RdeInputDirPaths(
        inputdata=Path("data", "inputdata"),
        invoice=Path("data", "invoice"),
        tasksupport=Path("data", "tasksupport"),
        config=config,
    )
    resource_paths = RdeOutputResourcePath(
        rawfiles=raw_files,
        raw=Path("data", "raw"),
        main_image=Path("data", "main_image"),
        other_image=Path("data", "other_image"),
        meta=Path("data", "meta"),
        struct=Path("data", "structured"),
        logs=Path("data", "logs"),
        thumbnail=Path("data", "thumbnail"),
        invoice=Path("data", "invoice"),
        invoice_org=Path("data", "temp", "invoice_org.json"),
        invoice_schema_json=invoice_shcema_json_full,
        nonshared_raw=Path("data", "nonshared_raw"),
    )
    # テスト対象の処理を実行
    rdeformat_mode_process("1", srcpaths, resource_paths, mock_datasets_process_function)

    # 関数が呼び出されたかどうかをチェック
    _assert_dataset_callback_called_once(mock_datasets_process_function, srcpaths, resource_paths)

    # descriptionのチェック
    with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
        content = json.load(f)
    assert content["basic"]["description"] == expected_description

    # rawフォルダにコピーされたかチェック
    assert len(list(Path("data", "raw").glob("*"))) == 1

    # thumbnailフォルダにコピーされたかチェック
    assert len(list(Path("data", "thumbnail").glob("*"))) == 1


def test_rdeformat_mode_process_alls_functions_none_metadata_json(
    mocker,
    inputfile_rdeformat,
    invoice_json_with_desc,
    tasksupport,
    metadata_def_json_with_feature,
    invoice_shcema_json_full,
):
    """Rdeformat mode processテスト
    テスト対象: 以下の処理が実行されるかテスト
    - invoice上書き
    - データセット処理
    - 特徴量書き込み処理
    - 各種バリデーションチェック(metadata.jsonが存在しない)
    metadata.jsonが存在しない場合、特徴量の書き込み処理は実行されない
    """
    Path("data", "raw").mkdir(parents=True, exist_ok=True)
    Path("data", "nonshared_raw").mkdir(parents=True, exist_ok=True)
    Path("data", "main_image").mkdir(parents=True, exist_ok=True)
    Path("data", "other_image").mkdir(parents=True, exist_ok=True)
    Path("data", "meta").mkdir(parents=True, exist_ok=True)
    Path("data", "structured").mkdir(parents=True, exist_ok=True)
    Path("data", "logs").mkdir(parents=True, exist_ok=True)
    Path("data", "temp").mkdir(parents=True, exist_ok=True)
    Path("data", "thumbnail").mkdir(parents=True, exist_ok=True)
    zip_path = Path("data", "inputdata") / Path(inputfile_rdeformat).name
    shutil.unpack_archive(zip_path, Path("data", "temp"))

    shutil.copy(
        Path("data", "invoice").joinpath("invoice.json"),
        Path("data", "temp", "invoice_org.json"),
    )
    Path("data/main_image/dummy_file.png").touch()
    expected_description = None
    mock_datasets_process_function = mocker.Mock()

    raw_files = tuple(f for f in Path("data", "temp").rglob("*") if f.is_file())
    config = Config(system=SystemSettings(extended_mode="rdeformat", save_raw=True, save_nonshared_raw=False, magic_variable=False, save_thumbnail_image=True), multidata_tile=MultiDataTileSettings(ignore_errors=False))
    srcpaths = RdeInputDirPaths(
        inputdata=Path("data", "inputdata"),
        invoice=Path("data", "invoice"),
        tasksupport=Path("data", "tasksupport"),
        config=config,
    )
    resource_paths = RdeOutputResourcePath(
        rawfiles=raw_files,
        raw=Path("data", "raw"),
        main_image=Path("data", "main_image"),
        other_image=Path("data", "other_image"),
        meta=Path("data", "meta"),
        struct=Path("data", "structured"),
        logs=Path("data", "logs"),
        thumbnail=Path("data", "thumbnail"),
        invoice=Path("data", "invoice"),
        invoice_org=Path("data", "temp", "invoice_org.json"),
        invoice_schema_json=invoice_shcema_json_full,
        nonshared_raw=Path("data", "nonshared_raw"),
    )
    # テスト対象の処理を実行
    rdeformat_mode_process("1", srcpaths, resource_paths, mock_datasets_process_function)

    # 関数が呼び出されたかどうかをチェック
    _assert_dataset_callback_called_once(mock_datasets_process_function, srcpaths, resource_paths)

    # descriptionのチェック
    with open(os.path.join("data", "invoice", "invoice.json"), encoding="utf-8") as f:
        content = json.load(f)
    assert content["basic"]["description"] == expected_description

    # rawフォルダにコピーされたかチェック
    assert len(list(Path("data", "raw").glob("*"))) == 1

    # thumbnailフォルダにコピーされたかチェック
    assert len(list(Path("data", "thumbnail").glob("*"))) == 1


def _verify_dataset_callback_args(call_args, srcpaths, resource_paths):
    args, kwargs = call_args
    assert kwargs == {}
    if len(args) == 1:
        dataset_paths = args[0]
        assert isinstance(dataset_paths, RdeDatasetPaths)
        assert dataset_paths.input_paths is srcpaths
        assert dataset_paths.output_paths is resource_paths
    else:
        assert args == (srcpaths, resource_paths)


def _assert_dataset_callback_called_once(mock, srcpaths, resource_paths):
    call_args_list = list(mock.call_args_list)
    assert len(call_args_list) == 1
    _verify_dataset_callback_args(call_args_list[0], srcpaths, resource_paths)


def _assert_dataset_callback_called_with(mock, srcpaths, resource_paths, index: int = -1):
    call_args_list = list(mock.call_args_list)
    assert call_args_list, "Callback was not invoked"
    if index < 0:
        call_args = call_args_list[index]
    else:
        assert len(call_args_list) > index
        call_args = call_args_list[index]
    _verify_dataset_callback_args(call_args, srcpaths, resource_paths)
