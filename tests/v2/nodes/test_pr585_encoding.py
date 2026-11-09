"""PR585 CI regression: honor CP932 detection before a legacy fallback."""

import json
from pathlib import Path

import pytest

from rdetoolkit.nodes import read_csv_with_header, read_json, read_text
from rdetoolkit.rde2util import CharDecEncoding


@pytest.mark.parametrize("kind", ["text", "json", "csv"])
def test_cp932_primary_beats_non_japanese_fallback__r585_enc_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    """R585-ENC-1: CI's fallback misclassification cannot replace primary CP932."""
    # Given: Japanese CP932 input and the legacy detector's CI-observed fallback
    content = "こんにちは世界\n"
    if kind == "json":
        content = json.dumps({"text": content}, ensure_ascii=False)
    elif kind == "csv":
        content = "text\n" + content
    path = tmp_path / f"input.{kind}"
    path.write_bytes(content.encode("cp932"))
    monkeypatch.setattr(CharDecEncoding, "detect_text_file_encoding", lambda _path: "maccyrillic")
    # When: decoding through the public node API
    if kind == "json":
        actual = read_json(path)["text"]
    elif kind == "csv":
        actual = read_csv_with_header(path).iloc[0, 0] + "\n"
    else:
        actual = read_text(path)
    # Then: the supported Japanese codec is retained
    assert actual == "こんにちは世界\n"


@pytest.mark.parametrize("text, encoding", [("plain\n", "ascii"), ("日本語\n", "utf-8"), ("Привет мир\n", "cp1251"), ("日本語です。これは測定データの説明です。\n", "euc_jp")])
def test_other_encodings_keep_existing_selection__r585_enc_2(tmp_path: Path, text: str, encoding: str) -> None:
    """R585-ENC-2: the CP932 correction does not force Japanese decoding on all files."""
    # Given: an existing supported non-CP932 encoding
    path = tmp_path / "source.txt"
    path.write_bytes(text.encode(encoding))
    # When: reading through the public node
    result = read_text(path)
    # Then: the original content is preserved
    assert result == text
