from pathlib import Path
from rdetoolkit.fileops import readf_json, writef_json
import json
from unittest.mock import mock_open, patch
from rdetoolkit.exceptions import StructuredError
import pytest


@pytest.fixture
def test_json():
    test_path = "dummy_path.json"
    mock_json = {"key": "value"}
    with open(test_path, mode="w", encoding="utf-8") as f:
        json.dump(mock_json, f)
    yield test_path

    if Path(test_path).exists():
        Path(test_path).unlink()


def test_readf_json_success():
    test_path = "test.json"
    mock_encoding = "utf_8"
    mock_json_content = '{"key": "value"}'
    expected_result = {"key": "value"}

    with patch('rdetoolkit.fileops.detect_encoding', return_value=mock_encoding) as mock_detect:
        with patch('builtins.open', mock_open(read_data=mock_json_content)) as mock_file:
            result = readf_json(test_path)

            mock_detect.assert_called_once_with(test_path)
            mock_file.assert_called_once_with(test_path, encoding='utf_8')
            assert result == expected_result


def test_readf_json_with_path_object():
    test_path = Path('test.json')
    mock_encoding = 'UTF-8'
    mock_json_content = '{"number": 123}'
    expected_result = {"number": 123}

    with patch('rdetoolkit.fileops.detect_encoding', return_value=mock_encoding) as mock_detect:
        with patch('builtins.open', mock_open(read_data=mock_json_content)) as mock_file:
            result = readf_json(test_path)

            mock_detect.assert_called_once_with(str(test_path))
            mock_file.assert_called_once_with(str(test_path), encoding="utf_8")
            assert result == expected_result


def test_readf_json_with_different_encoding():
    test_path = 'test_shift_jis.json'
    mock_encoding = 'Shift-JIS'
    mock_json_content = '{"japanese": "テスト"}'
    expected_result = {"japanese": "テスト"}

    with patch('rdetoolkit.fileops.detect_encoding', return_value=mock_encoding) as mock_detect:
        with patch('builtins.open', mock_open(read_data=mock_json_content)) as mock_file:
            result = readf_json(test_path)

            mock_detect.assert_called_once_with(test_path)
            mock_file.assert_called_once_with(test_path, encoding='shift_jis')
            assert result == expected_result


def test_readf_json_with_default_encoding():
    test_path = 'default_encoding.json'
    mock_encoding = None
    mock_json_content = '{"default": true}'
    expected_result = {"default": True}

    with patch('rdetoolkit.fileops.detect_encoding', return_value=mock_encoding) as mock_detect:
        with patch('builtins.open', mock_open(read_data=mock_json_content)) as mock_file:
            result = readf_json(test_path)

            mock_detect.assert_called_once_with(test_path)
            mock_file.assert_called_once_with(test_path, encoding='utf_8')
            assert result == expected_result


def test_readf_json_raise_structured_error_on_exception():
    test_path = 'invalid.json'
    mock_encoding = 'utf-8'

    with patch('rdetoolkit.fileops.detect_encoding', return_value=mock_encoding) as mock_detect:
        with patch('builtins.open', mock_open()) as mock_file:
            mock_file.side_effect = OSError('File not found')

            with pytest.raises(StructuredError) as exc_info:
                readf_json(test_path)

            assert "An error occurred while processing the file: File not found" in str(exc_info.value)
            mock_detect.assert_called_once_with(test_path)
            mock_file.assert_called_once_with(test_path, encoding='utf_8')


def test_writef_json_basic(tmp_path):
    """基本的な書き込みテスト:

    単純な辞書オブジェクトを JSON ファイルに書き込み、ファイルの内容と関数の戻り値を検証。
    """
    test_data = {'key': 'value', 'number': 123, 'bool': True}
    file_path = tmp_path / 'test_basic.json'

    returned_data = writef_json(file_path, test_data)

    assert file_path.exists()

    with open(file_path, encoding='utf-8') as f:
        file_content = json.load(f)
    assert file_content == test_data

    assert returned_data == test_data


def test_writf_json_with_path_object(tmp_path):
    """Pathオブジェクトを使用した書き込みテスト

    `pathlib.Path` オブジェクトを使用してファイルを書き込み、正しく動作することを確認.
    """
    test_data = {"path": "object", "data": [1, 2, 3]}
    file_path = tmp_path / "test_path_object.json"

    returned_data = writef_json(Path(file_path), test_data)

    assert file_path.exists()

    with open(file_path, encoding="utf_8") as f:
        file_content = json.load(f)
    assert file_content == test_data

    assert returned_data == test_data


def test_writef_json_with_different_encoding(tmp_path):
    """異なるエンコーディングでの書き込みテスト:
    異なる文字エンコーディング（例: 'utf_16'）を使用してファイルを書き込み、正しくエンコーディングが適用されていることを確認します。
    """
    test_data = {"japanese": "テスト", "emoji": "😊"}
    file_path = tmp_path / "test_utf16.json"
    encoding = "utf_16"

    returned_data = writef_json(file_path, test_data, enc=encoding)

    assert file_path.exists()

    with open(file_path, encoding=encoding) as f:
        file_content = json.load(f)
    assert file_content == test_data

    assert returned_data == test_data


def test_writef_json_empty_dict(tmp_path):
    """空の辞書を使用した書き込みテスト:

    空の辞書オブジェクトを JSON ファイルに書き込み、正しく空の JSON オブジェクトが作成されることを確認。
    """
    test_data = {}
    file_path = tmp_path / "test_empty.json"

    returned_data = writef_json(file_path, test_data)

    assert file_path.exists()

    with open(file_path, encoding="utf_8") as f:
        file_content = json.load(f)
    assert file_content == test_data

    assert returned_data == test_data


def test_writef_json_invalid_path(tmp_path):
    """無効なパスでの書き込みテスト

    存在しないディレクトリへの書き込みを試み、適切な例外が発生することを確認。
    """
    test_data = {"invalid": "path"}
    invalid_dir = tmp_path / "non_existent_dir"
    file_path = invalid_dir / "test_invalid.json"

    with pytest.raises(FileNotFoundError):
        writef_json(file_path, test_data)

    # ファイルが作成されていないことを確認
    assert not file_path.exists()
