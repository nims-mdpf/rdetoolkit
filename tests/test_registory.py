import pytest

import polars as pl

from src.rdetoolkit.exceptions import DataRetrievalError
from src.rdetoolkit.models.invoice import GeneralTermRegistry, SpecificTermRegistry


@pytest.fixture
def sample_csv(tmp_path):
    # サンプルデータを含む一時的なCSVファイルを作成
    data = """sample_class_id,term_id,key_name,ja,en
1,101,KeyA,日本語A,EnglishA
2,102,KeyB,日本語B,EnglishB
3,103,KeyC,日本語C,EnglishC
4,104,KeyD,日本語D,EnglishD
"""
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text(data)
    yield str(csv_file)

    if csv_file.exists():
        csv_file.unlink()


class TestSpecificTermRegistry:

    def test_initialization(self, sample_csv):
        registry = SpecificTermRegistry(sample_csv)
        assert not registry.df.is_empty()
        assert registry.df.shape == (4, 5)

    def test_search_success(self, sample_csv):
        registry = SpecificTermRegistry(sample_csv)
        results = registry.search(
            columns=["key_name"],
            values=["KeyA"],
            out_cols=["sample_class_id", "en"],
        )
        assert len(results) == 1
        assert results[0]["sample_class_id"] == "1"
        assert results[0]["en"] == "EnglishA"

    def test_search_multiple_conditions(self, sample_csv):
        registry = SpecificTermRegistry(sample_csv)
        results = registry.search(
            columns=["key_name", "en"],
            values=["KeyB", "EnglishB"],
            out_cols=["sample_class_id", "term_id"],
        )
        assert len(results) == 1
        assert results[0]["sample_class_id"] == "2"
        assert results[0]["term_id"] == "102"

    def test_search_mismatched_columns_values(self, sample_csv):
        registry = SpecificTermRegistry(sample_csv)
        with pytest.raises(ValueError) as exc_info:
            registry.search(
                columns=["key_name", "en"],
                values=["KeyA"],
                out_cols=["sample_class_id"],
            )
        assert "The lengths of 'columns' and 'values' must be the same." in str(exc_info.value)

    def test_search_invalid_column(self, sample_csv):
        registry = SpecificTermRegistry(sample_csv)
        with pytest.raises((Exception, DataRetrievalError)) as excinfo:
            registry.search(
                columns=["non_existent_column"],
                values=["Value"],
                out_cols=["sample_class_id", "term_id", "key_name", "ja"],
            )

        # エラーメッセージの部分一致で検証
        error_message = str(excinfo.value)
        assert any([
            "unable to find column" in error_message,
            "non_existent_column" in error_message,
            "An error occurred while searching for terms" in error_message,
        ])

    def test_by_term_and_class_id_success(self, sample_csv):
        registry = SpecificTermRegistry(sample_csv)
        results = registry.by_term_and_class_id(term_id="101", sample_class_id="1")
        assert len(results) == 1
        assert results[0]["key_name"] == "KeyA"

    def test_by_key_name_success(self, sample_csv):
        registry = SpecificTermRegistry(sample_csv)
        results = registry.by_key_name(key_name=["KeyD"])
        assert len(results) == 1
        assert results[0]["ja"] == "日本語D"

    def test_by_ja_success(self, sample_csv):
        registry = SpecificTermRegistry(sample_csv)
        results = registry.by_ja(ja_text=["日本語A"])
        assert len(results) == 1
        assert results[0]["en"] == "EnglishA"

    def test_by_en_success(self, sample_csv):
        registry = SpecificTermRegistry(sample_csv)
        results = registry.by_en(en_text=["EnglishB"])
        assert len(results) == 1
        assert results[0]["key_name"] == "KeyB"

    def test_by_term_and_class_id_no_result(self, sample_csv):
        registry = SpecificTermRegistry(sample_csv)
        results = registry.by_term_and_class_id(term_id="999", sample_class_id="999")
        assert len(results) == 0

    def test_by_key_name_multiple_results(self, tmp_path):
        # CSVに複数の同じkey_nameを含める
        data = """sample_class_id,term_id,key_name,ja,en
1,101,KeyA,日本語A,EnglishA
2,102,KeyA,日本語B,EnglishB
3,103,KeyC,日本語C,EnglishC
"""
        csv_file = tmp_path / "test_data_multiple.csv"
        csv_file.write_text(data)
        registry = SpecificTermRegistry(str(csv_file))
        results = registry.by_key_name(key_name=["KeyA"])
        assert len(results) == 2
        assert results[0]["sample_class_id"] == "1"
        assert results[1]["sample_class_id"] == "2"


@pytest.fixture
def sample_general_term_csv(tmp_path):
    # サンプルデータを含む一時的なCSVファイルを作成
    data = """term_id,key_name,ja,en
101,KeyA,日本語A,EnglishA
102,KeyB,日本語B,EnglishB
103,KeyC,日本語C,EnglishC
104,KeyD,日本語D,EnglishD
"""
    csv_file = tmp_path / "test_general_data.csv"
    csv_file.write_text(data)
    yield str(csv_file)

    if csv_file.exists():
        csv_file.unlink()


class TestGeneralTermRegistry:

    def test_initialization(self, sample_general_term_csv):
        registry = GeneralTermRegistry(sample_general_term_csv)
        assert not registry.df.is_empty()
        assert registry.df.shape == (4, 4)

    def test_search_success(self, sample_general_term_csv):
        registry = GeneralTermRegistry(sample_general_term_csv)
        results = registry.search(
            column="key_name",
            value="KeyA",
            out_cols=["term_id", "en"],
        )
        assert len(results) == 1
        assert results[0]["term_id"] == "101"
        assert results[0]["en"] == "EnglishA"

    def test_search_no_results(self, sample_general_term_csv):
        registry = GeneralTermRegistry(sample_general_term_csv)
        results = registry.search(
            column="key_name",
            value="NonExistentKey",
            out_cols=["term_id"],
        )
        assert len(results) == 0

    def test_search_invalid_column(self, sample_general_term_csv):
        registry = GeneralTermRegistry(sample_general_term_csv)
        with pytest.raises(pl.exceptions.ColumnNotFoundError):
            registry.search(
                column="non_existent_column",
                value="Value",
                out_cols=["term_id"],
            )

    def test_search_invalid_out_cols(self, sample_general_term_csv):
        registry = GeneralTermRegistry(sample_general_term_csv)
        with pytest.raises(pl.exceptions.ColumnNotFoundError):
            registry.search(
                column="key_name",
                value="KeyA",
                out_cols=["term_id", "non_existent_column"],
            )

    def test_by_term_id_success(self, sample_general_term_csv):
        registry = GeneralTermRegistry(sample_general_term_csv)
        results = registry.by_term_id(term_id="103")
        assert len(results) == 1
        assert results[0]["key_name"] == "KeyC"
        assert results[0]["ja"] == "日本語C"
        assert results[0]["en"] == "EnglishC"

    def test_by_term_id_no_result(self, sample_general_term_csv):
        registry = GeneralTermRegistry(sample_general_term_csv)
        results = registry.by_term_id(term_id="999")
        assert len(results) == 0

    def test_by_ja_success(self, sample_general_term_csv):
        registry = GeneralTermRegistry(sample_general_term_csv)
        results = registry.by_ja(ja_text="日本語A")
        assert len(results) == 1
        assert results[0]["term_id"] == "101"
        assert results[0]["key_name"] == "KeyA"
        assert results[0]["en"] == "EnglishA"

    def test_by_ja_no_result(self, sample_general_term_csv):
        registry = GeneralTermRegistry(sample_general_term_csv)
        results = registry.by_ja(ja_text="存在しない日本語")
        assert len(results) == 0

    def test_by_en_success(self, sample_general_term_csv):
        registry = GeneralTermRegistry(sample_general_term_csv)
        results = registry.by_en(en_text="EnglishB")
        assert len(results) == 1
        assert results[0]["term_id"] == "102"
        assert results[0]["key_name"] == "KeyB"
        assert results[0]["ja"] == "日本語B"

    def test_by_en_no_result(self, sample_general_term_csv):
        registry = GeneralTermRegistry(sample_general_term_csv)
        results = registry.by_en(en_text="NonExistentEnglish")
        assert len(results) == 0

    def test_multiple_results_search(self, tmp_path):
        # CSVに複数の同じterm_idを含める
        data = """term_id,key_name,ja,en
101,KeyA,日本語A,EnglishA
101,KeyB,日本語B,EnglishB
103,KeyC,日本語C,EnglishC
"""
        csv_file = tmp_path / "test_data_multiple.csv"
        csv_file.write_text(data)
        registry = GeneralTermRegistry(str(csv_file))
        results = registry.search(
            column="term_id",
            value="101",
            out_cols=["term_id", "key_name"],
        )
        assert len(results) == 2
        assert results[0]["key_name"] == "KeyA"
        assert results[1]["key_name"] == "KeyB"

    def test_search_with_empty_out_cols(self, sample_general_term_csv):
        registry = GeneralTermRegistry(sample_general_term_csv)
        results = registry.search(
            column="key_name",
            value="KeyA",
            out_cols=[],
        )
        assert len(results) == 0
