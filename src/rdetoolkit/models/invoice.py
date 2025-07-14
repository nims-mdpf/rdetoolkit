from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import polars as pl
from openpyxl.utils import get_column_letter
from pydantic import BaseModel, Field

from rdetoolkit.exceptions import DataRetrievalError, InvalidSearchParametersError
from rdetoolkit.models.invoice_schema import GeneralAttribute, SpecificAttribute


class HeaderRow1(BaseModel):
    """Data class to hold the first header row data of ExcelInvoice."""
    A1: str = "invoiceList_format_id"


class HeaderRow2(BaseModel):
    """Data class to hold the second header row data of ExcelInvoice."""
    A2: str = "data_file_names"
    D2_G2: list[str] = Field(default_factory=lambda: ["basic"] * 4)
    H2_M2: list[str] = Field(default_factory=lambda: ["sample"] * 6)


class HeaderRow3(BaseModel):
    """Data class to hold the third header row data of ExcelInvoice."""
    A3: str = "name"
    B3: str = "dataset_title"
    C3: str = "dataOwner"
    D3: str = "dataOwnerId"
    E3: str = "dataName"
    F3: str = "experimentId"
    G3: str = "description"
    H3: str = "names"
    I3: str = "sampleId"
    J3: str = "ownerId"
    K3: str = "composition"
    L3: str = "referenceUrl"
    M3: str = "description"


class HeaderRow4(BaseModel):
    """Data class to hold the fourth header row data of ExcelInvoice."""
    A4: str = "ファイル名\n(拡張子も含め入力)\n(入力例:○○.txt)"
    B4: str = "データセット名\n(必須)"
    C4: str = "データ所有者\n(NIMS User ID)"
    D4: str = "NIMS user UUID\n(必須)"
    E4: str = "データ名\n(必須)"
    F4: str = "実験ID"
    G4: str = "説明"
    H4: str = "試料名\n(ローカルID)"
    I4: str = "試料UUID\n(必須)"
    J4: str = "試料管理者UUID"
    K4: str = "化学式・組成式・分子式など"
    L4: str = "参考URL"
    M4: str = "試料の説明"


class FixedHeaders(BaseModel):
    """Data class to hold the fixed header rows data of ExcelInvoice."""
    row1: HeaderRow1 = HeaderRow1()
    row2: HeaderRow2 = HeaderRow2()
    row3: HeaderRow3 = HeaderRow3()
    row4: HeaderRow4 = HeaderRow4()

    def to_template_dataframe(self) -> pl.DataFrame:
        """Converts the invoice data to a Polars DataFrame formatted for a template.

        This method organizes the invoice data into a DataFrame with specific padding
        and column structure suitable for template processing.

        Returns:
            pl.DataFrame: A Polars DataFrame containing the formatted invoice data.
        """
        padding_value = None
        row1 = [self.row1.A1] + [padding_value] * 12
        row2 = [self.row2.A2] + [padding_value] * 2 + self.row2.D2_G2 + self.row2.H2_M2 + [padding_value]
        row3 = list(self.row3.model_dump().values())
        row4 = list(self.row4.model_dump().values())

        data = [row1, row2, row3, row4]
        columns = [get_column_letter(i) for i in range(1, 14)]

        return pl.DataFrame(data, columns, orient="row")


@dataclass
class TemplateConfig:
    """Data class to hold configuration settings for generating ExcelInvoice template files."""
    schema_path: str | Path
    general_term_path: str | Path
    specific_term_path: str | Path
    inputfile_mode: Literal["file", "folder"] = "file"


class BaseTermRegistry:
    """Base class for term registries."""
    base_schema = {
        "term_id": pl.Utf8,
        "key_name": pl.Utf8,
        "ja": pl.Utf8,
        "en": pl.Utf8,
    }


class GeneralTermRegistry(BaseTermRegistry):
    """Class for managing general terms."""

    def __init__(self, csv_path: str):
        self.df = pl.read_csv(csv_path, schema_overrides=self.base_schema)

    def search(self, column: str, value: str, out_cols: list[str]) -> list[dict[str, Any]]:
        """Search for rows in the DataFrame where the specified column matches the given value and return selected columns.

        Args:
            column (str): The name of the column to search.
            value (str): The value to search for in the specified column.
            out_cols (list[str]): A list of column names to include in the output.

        Returns:
            list[dict[str, Any]]: A list of dictionaries representing the rows that match the search criteria, with only the specified columns included.
        """
        filtered_df = self.df.filter(pl.col(column) == value)
        return filtered_df.select(out_cols).to_dicts()

    def by_term_id(self, term_id: str) -> list[dict[str, Any]]:
        """Retrieve a list of dictionaries containing invoice details filtered by term ID.

        Args:
            term_id (str): The term ID to filter invoices by.

        Returns:
            list[dict[str, Any]]: A list of dictionaries, each containing the keys
            "term_id", "key_name", and "term_description" with their corresponding values.
        """
        return self.search("term_id", term_id, ["term_id", "key_name", "ja", "en"])

    def by_ja(self, ja_text: str) -> list[dict[str, Any]]:
        """Search for records with Japanese text.

        Args:
            ja_text (str): The Japanese text to search for.

        Returns:
            list[dict[str, Any]]: A list of dictionaries containing the search results with keys "term_id", "key_name", and "term_description".
        """
        return self.search("ja", ja_text, ["term_id", "key_name", "en"])

    def by_en(self, en_text: str) -> list[dict[str, Any]]:
        """Search for terms in English text.

        Args:
            en_text (str): The English text to search for.

        Returns:
            list[dict[str, Any]]: A list of dictionaries containing the search results with keys "term_id", "key_name", and "term_description".
        """
        return self.search("en", en_text, ["term_id", "key_name", "ja"])


class SpecificTermRegistry(BaseTermRegistry):
    """Class for managing specific terms."""

    def __init__(self, csv_path: str):
        schema = {
            "sample_class_id": pl.Utf8,
            **self.base_schema,
        }
        self.df = pl.read_csv(csv_path, schema_overrides=schema)

    def search(self, columns: list[str], values: list[str], out_cols: list[str]) -> list[dict[str, Any]]:
        """Search for rows in the DataFrame where the specified column matches the given value and return the selected columns.

        Args:
            columns (list[str]): The name of the column to search.
            values (list[str]): The value to search for in the specified column.
            out_cols (list[str]): A list of column names to include in the output.

        Returns:
            list[dict[str, Any]]: A list of dictionaries representing the rows that match the search criteria, with only the specified columns included.
        """
        if len(columns) != len(values):
            emsg = "The lengths of 'columns' and 'values' must be the same."
            raise ValueError(emsg)

        try:
            filter_expr = pl.lit(True)
            for col, val in zip(columns, values):
                expr = pl.col(col) == val
                filter_expr = expr if filter_expr is None else filter_expr & expr
            filtered_df = self.df.filter(filter_expr)

            if filtered_df.is_empty():
                return []
            return filtered_df.select(out_cols).to_dicts()
        except DataRetrievalError:
            raise
        except InvalidSearchParametersError:
            raise
        except Exception as e:
            terms = ",".join(f"{col}={val}" for col, val in zip(columns, values))
            emsg = f"An error occurred while searching for terms: {terms}. Error: {e}"
            raise DataRetrievalError(emsg) from e

    def by_term_and_class_id(self, term_id: str, sample_class_id: str) -> list[dict[str, Any]]:
        """Retrieve a list of dictionaries containing specific fields for entries matching the given term and sample class IDs.

        Args:
            term_id (str): The term ID to search for.
            sample_class_id (str): The sample class ID to search for.

        Returns:
            list[dict[str, Any]]: A list of dictionaries, each containing the fields "sample_class_id", "term_id", "key_name", "ja", and "en" for entries that match the term and sample class IDs.
        """
        return self.search(["sample_class_id", "term_id"], [sample_class_id, term_id], ["sample_class_id", "term_id", "key_name", "ja", "en"])

    def by_key_name(self, key_name: list[str]) -> list[dict[str, Any]]:
        """Retrieve a list of dictionaries containing specific fields for entries matching the given key name.

        Args:
            key_name (list[str]): The key name to search for.

        Returns:
            list[dict[str, Any]]: A list of dictionaries, each containing the fields "sample_class_id", "term_id", "key_name", "ja", and "en" for entries that match the key name.
        """
        return self.search(["key_name"], key_name, ["sample_class_id", "term_id", "key_name", "ja", "en"])

    def by_ja(self, ja_text: list[str]) -> list[dict[str, Any]]:
        """Search for records by Japanese text.

        Args:
            ja_text (list[str]): The Japanese text to search for.

        Returns:
            list[dict[str, Any]]: A list of dictionaries containing the search results.
        """
        return self.search(["ja"], ja_text, ["sample_class_id", "term_id", "key_name", "en"])

    def by_en(self, en_text: list[str]) -> list[dict[str, Any]]:
        """Search for records in the database using the provided English text.

        Args:
            en_text (list[str]): The English text to search for.

        Returns:
            list[dict[str, Any]]: A list of dictionaries containing the search results.
        """
        return self.search(["en"], en_text, ["sample_class_id", "term_id", "key_name", "ja"])


@dataclass
class GeneralAttributeConfig:
    type: str
    registry: GeneralTermRegistry
    prefix: str
    attributes: GeneralAttribute | None
    requires_class_id: Literal[False]


@dataclass
class SpecificAttributeConfig:
    type: str
    registry: SpecificTermRegistry
    prefix: str
    attributes: SpecificAttribute | None
    requires_class_id: Literal[True]
