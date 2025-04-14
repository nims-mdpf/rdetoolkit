import datetime
import json
import os
import tempfile

import pytest
from rdetoolkit.rde2util import Meta, _split_value_unit, CharDecEncoding, read_from_json_file, write_to_json_file, castval, ValueCaster
from rdetoolkit.exceptions import StructuredError


def test_split_value_unit():
    # テストケース1: 値と単位が両方存在する場合
    result = _split_value_unit("10.5 kg")
    assert result.value == "10.5"
    assert result.unit == "kg"

    # テストケース2: 値のみ存在する場合
    result = _split_value_unit("25")
    assert result.value == "25"
    assert result.unit == ""

    # テストケース3: 単位のみ存在する場合
    result = _split_value_unit("m/s")
    assert result.value == ""
    assert result.unit == "m/s"

    # テストケース4: 値と単位が空の場合
    result = _split_value_unit("")
    assert result.value == ""
    assert result.unit == ""

    # テストケース5: 値と単位が空白文字のみの場合
    result = _split_value_unit("   ")
    assert result.value == ""
    assert result.unit == ""


@pytest.fixture
def meta_const_instance():
    meta_dict = {
        "common.data_origin": {
            "name": {"ja": "データの起源", "en": "Data Origin"},
            "schema": {"type": "string"},
        },
        "common.technical_category": {
            "name": {"ja": "技術カテゴリー", "en": "Technical Category"},
            "schema": {"type": "string"},
        },
        "date": {
            "name": {"ja": "日時", "en": "date"},
            "schema": {"type": "string"},
        },
        "datetime": {
            "name": {
                "ja": "分析年月日",
                "en": "Measured date",
            },
            "schema": {
                "type": "string",
                "format": "date",
            },
        },
        "reference": {
            "name": {"ja": "参考文献", "en": "Reference"},
            "schema": {"type": "string"},
        },
    }

    with open("tests/metadata-def.json", mode="w", encoding="utf-8") as f:
        json.dump(meta_dict, f, ensure_ascii=False)
    metadef_filepath = "tests/metadata-def.json"  # Replace with the actual file path
    yield Meta(metadef_filepath=metadef_filepath)
    if os.path.exists("tests/metadata-def.json"):
        os.remove("tests/metadata-def.json")
    if os.path.exists("tests/metadata.json"):
        os.remove("tests/metadata.json")


def test_read_metadef_file(meta_const_instance):
    metadef_filepath = "tests/metadata-def.json"  # Replace with the actual file path
    result = meta_const_instance._read_metadef_file(metadef_filepath)
    assert isinstance(result, dict)


def test_assignVals_unknown_key(meta_const_instance):
    entry_dict_meta = {"key1": "value1", "key2": "value2"}
    result = meta_const_instance.assign_vals(entry_dict_meta)
    print(result)
    assert result["unknown"] == {"key1", "key2"}
    assert result["assigned"] == set()


def test_assignVals_exsit_key(meta_const_instance):
    entry_dict_meta = {"date": "2022-01-01", "datetime": datetime.datetime(2012, 12, 16, 0, 0), "reference": "sample.com"}
    result = meta_const_instance.assign_vals(entry_dict_meta)
    assert meta_const_instance.metaConst["datetime"]["value"] == "2012-12-16"
    assert result["unknown"] == set()
    assert result["assigned"] == {"reference", "date", "datetime"}


def test_empty_writefile(meta_const_instance):
    """metadata.json is empty"""
    metafilepath = "tests/metadata.json"  # Replace with the actual file path
    result = meta_const_instance.writefile(metafilepath)
    assert os.path.exists("tests/metadata.json")
    assert result["assigned"] == set()


def test_has_contents_writefile(meta_const_instance):
    """Write the metadata to metadata.json"""
    metafilepath = "tests/metadata.json"
    entry_dict_meta = {"date": "2022-01-01", "reference": "sample.com"}
    meta_const_instance.assign_vals(entry_dict_meta)
    meta_const_instance.writefile(metafilepath)
    assert os.path.exists("tests/metadata.json")

    with open(metafilepath, encoding="utf-8") as f:
        content = json.load(f)
        assert content["constant"]["date"]["value"] == "2022-01-01"
        assert content["constant"]["reference"]["value"] == "sample.com"


@pytest.fixture
def meta_variable_instance():
    meta_dict = {
        "common.data_origin": {
            "name": {"ja": "データの起源", "en": "Data Origin"},
            "schema": {"type": "string"},
        },
        "common.technical_category": {
            "name": {"ja": "技術カテゴリー", "en": "Technical Category"},
            "schema": {"type": "string"},
        },
        "date": {
            "name": {"ja": "日時", "en": "date"},
            "schema": {"type": "string"},
            "variable": 1,
        },
        "reference": {
            "name": {"ja": "参考文献", "en": "Reference"},
            "schema": {"type": "string"},
            "variable": 1,
        },
        "custom.user": {
            "name": {"ja": "ユーザー", "en": "User"},
            "schema": {"type": "string"},
            "variable": 1,
        },
    }

    with open("tests/metadata-def.json", mode="w", encoding="utf-8") as f:
        json.dump(meta_dict, f, ensure_ascii=False)
    metadef_filepath = "tests/metadata-def.json"  # Replace with the actual file path
    yield Meta(metadef_filepath=metadef_filepath)
    if os.path.exists("tests/metadata-def.json"):
        os.remove("tests/metadata-def.json")
    if os.path.exists("tests/metadata.json"):
        os.remove("tests/metadata.json")


def test_assignVals_variable_exsit_key(meta_variable_instance):
    entry_dict_meta = {
        "date": ["2022-01-01", "2022-01-02", "2022-01-03"],
        "reference": ["sample.com", "experiments.app", "myDocuments.go.jp"],
        "custom.user": ["A", "B", "C"],
    }
    result = meta_variable_instance.assign_vals(entry_dict_meta)
    assert result["unknown"] == set()
    assert result["assigned"] == {"reference", "date", "custom.user"}


def test_has_variable_writefile(meta_variable_instance):
    """Write the metadata to metadata.json"""
    metafilepath = "tests/metadata.json"
    entry_dict_meta = {
        "date": ["2022-01-01", "2022-01-02", "2022-01-03"],
        "reference": ["sample.com", "experiments.app", "myDocuments.go.jp"],
        "custom.user": ["A", "B", "C"],
    }
    meta_variable_instance.assign_vals(entry_dict_meta)
    meta_variable_instance.writefile(metafilepath)
    assert os.path.exists("tests/metadata.json")

    with open(metafilepath, encoding="utf-8") as f:
        content = json.load(f)
        assert content["variable"][0]["date"]["value"] == "2022-01-01"
        assert content["variable"][0]["reference"]["value"] == "sample.com"
        assert content["variable"][0]["custom.user"]["value"] == "A"
        assert content["variable"][1]["date"]["value"] == "2022-01-02"
        assert content["variable"][1]["reference"]["value"] == "experiments.app"
        assert content["variable"][1]["custom.user"]["value"] == "B"
        assert content["variable"][2]["date"]["value"] == "2022-01-03"
        assert content["variable"][2]["reference"]["value"] == "myDocuments.go.jp"
        assert content["variable"][2]["custom.user"]["value"] == "C"


# detect_text_file_encodingに関するテスト
@pytest.fixture
def utf_8_file():
    # テスト用の"utf_8"エンコーディングのファイルを作成する
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf_8", delete=False) as f:
        f.write("テストファイル（UTF-8）")
        file_path = f.name
    yield file_path
    os.remove(file_path)


@pytest.fixture
def shift_jis_file():
    # テスト用の"shift_jis"エンコーディングのファイルを作成する
    with tempfile.NamedTemporaryFile(mode="w", encoding="shift_jis", delete=False) as f:
        f.write("テストファイル（Shift-JIS）")
        file_path = f.name
    yield file_path
    os.remove(file_path)


@pytest.fixture
def utf_8_sig_file():
    # テスト用の"utf_8_sig"エンコーディングのファイルを作成する
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf_8_sig", delete=False) as f:
        f.write("テストファイル（UTF-8 with BOM）")
        file_path = f.name
    yield file_path
    os.remove(file_path)


def test_detect_text_file_encoding(utf_8_file):
    assert CharDecEncoding.detect_text_file_encoding(utf_8_file) == "utf_8"


def test_detect_text_file_encoding_shift_jis(shift_jis_file):
    assert CharDecEncoding.detect_text_file_encoding(shift_jis_file) == "cp932"


def test_detect_text_file_encoding_utf_8_sig(utf_8_sig_file):
    assert CharDecEncoding.detect_text_file_encoding(utf_8_sig_file) == "utf_8_sig"


# read_invoice_json_fileのテスト
def test_read_from_json_file_valid_json_file(ivnoice_json_none_sample_info):
    """version1.2.0で削除予定"""
    expect_json = {
        "datasetId": "1s1199df4-0d1v-41b0-1dea-23bf4dh09g12",
        "basic": {
            "dateSubmitted": "2023-03-14",
            "dataOwnerId": "0c233ef274f28e611de4074638b4dc43e737ab993132343532343430",
            "dataName": "test1",
            "experimentId": "test_230606_1",
            "description": "desc1",
        },
        "custom": {"key1": "test1", "key2": "test2"},
    }
    # JSONファイルを読み込む関数を呼び出し
    result = read_from_json_file(ivnoice_json_none_sample_info)

    assert result == expect_json


def test_read_from_json_file_deprecation_warning(ivnoice_json_none_sample_info):
    with pytest.warns(DeprecationWarning, match=r"read_from_json_file is deprecated\. Use 'from rdetoolkit\.fileops import readf_json' instead\."):
        _ = read_from_json_file(ivnoice_json_none_sample_info)


@pytest.fixture
def sample_invoice():
    return {
        "invoice_id": "12345",
        "items": [
            {"product": "apple", "quantity": 3, "price": 0.5},
            {"product": "orange", "quantity": 1, "price": 0.8},
        ],
    }


def test_write_to_json_file(tmp_path, sample_invoice):
    # tmp_path is a pytest fixture that provides a temporary directory unique to the test invocation
    file_path = tmp_path / "invoice.json"
    write_to_json_file(file_path, sample_invoice)

    # Check if the file exists
    assert file_path.exists()

    # Read the file and check its content
    with open(file_path, encoding="utf_8") as f:
        data = json.load(f)

    assert data == sample_invoice


def test_write_to_json_file_deprecation_warning(tmp_path, sample_invoice):
    file_path = tmp_path / "invoice.json"
    with pytest.warns(DeprecationWarning, match=r"write_to_json_file is deprecated\. Use 'from rdetoolkit\.fileops import writef_json' instead\."):
        write_to_json_file(file_path, sample_invoice)


@pytest.mark.parametrize(
    "valstr, fmt, outfmt, expected",
    [
        ("100", "integer", None, 100),
        ("100", "number", None, 100),
        ("100.1", "number", None, 100.1),
        ("True", "boolean", None, True),
        ("sample", "string", None, "sample"),
        ("2023/1/1 12:00:00", "string", "date-time", "2023-01-01T12:00:00"),
        ("2023/1/1", "string", "date", "2023-01-01"),
        ("12:00:00", "string", "time", "12:00:00"),
    ],
)
def test_castval(valstr, fmt, outfmt, expected):
    result = castval(valstr, fmt, outfmt)
    assert expected == result


def test_castval_invalid():
    with pytest.raises(StructuredError) as e:
        castval("100", "num", None)
    assert str(e.value) == "ERROR: unknown value type in metaDef"


def test_castval_invalid_last_statement():
    with pytest.raises(StructuredError) as e:
        castval("sample", "number", None)
    assert str(e.value) == "ERROR: failed to cast metaDef value"


def test_trycast():
    assert ValueCaster.trycast("123", int) == 123
    assert ValueCaster.trycast("123.456", float) == 123.456
    assert ValueCaster.trycast("True", bool) is True
    assert ValueCaster.trycast("abc", int) is None  # キャストが失敗するケース


def test_convert_to_date_format():
    assert ValueCaster.convert_to_date_format("2021-01-01", "date") == "2021-01-01"
    assert ValueCaster.convert_to_date_format("2021-01-01T12:00:00", "date-time") == "2021-01-01T12:00:00"
    assert ValueCaster.convert_to_date_format("12:00:00", "time") == "12:00:00"

    with pytest.raises(StructuredError, match="ERROR: unknown format in metaDef"):
        ValueCaster.convert_to_date_format("2021-01-01", "unknown-format")


@pytest.mark.parametrize(
    "vsrc, outtype, outfmt, orgtype, outunit, expected",
    [
        # Case 1: orgtype=None case (castval is called directly)
        ("100", "integer", None, None, None, {"value": 100}),
        ("true", "boolean", None, None, None, {"value": True}),
        ("test", "string", None, None, None, {"value": "test"}),
        ("2023-01-01", "string", "date", None, None, {"value": "2023-01-01"}),

        # Case 2: orgtype=integer with unit
        ("100kg", "integer", None, "integer", None, {"value": 100}),
        ("50.5m", "number", None, "integer", None, {"value": 50.5}), # integerなので小数点以下が切り捨て

        # Case 3: orgtype=number with unit
        ("100.5kg", "number", None, "number", None, {"value": 100.5}),

        # Case 4: orgtype=string (other types)
        ("test", "string", None, "string", None, {"value": "test"}),

        # Case 5: with outunit (unit information included)
        ("100", "integer", None, None, "kg", {"value": 100, "unit": "kg"}),
        ("test", "string", None, "string", "m", {"value": "test", "unit": "m"}),

        # Case 6: input value with whitespace (should be trimmed)
        ("  100  ", "integer", None, None, None, {"value": 100}),

        # Case 7: combination of unit and format
        ("2023-01-01", "string", "date", None, "UTC", {"value": "2023-01-01", "unit": "UTC"}),
    ],
)
def test_metadata_validation(meta_const_instance, vsrc, outtype, outfmt, orgtype, outunit, expected):
    """Meta.metadata_validation"""
    result = meta_const_instance.metadata_validation(vsrc, outtype, outfmt, orgtype, outunit)
    assert result == expected


def test_metadata_validation_error(meta_const_instance):
    """Error testing with invalid input or type"""
    # Cases where castval throws an error with an invalid type
    with pytest.raises(StructuredError, match="ERROR: unknown value type in metaDef"):
        meta_const_instance.metadata_validation("test", "invalid_type", None, None, None)

    # Cases in which castval throws an error with invalid value
    with pytest.raises(StructuredError, match="ERROR: failed to cast metaDef value"):
        meta_const_instance.metadata_validation("abc", "integer", None, None, None)
