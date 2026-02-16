"""Excel invoice file handling.

This module provides the ExcelInvoiceFile class for reading, processing,
and generating Excel invoice files.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.fileops import readf_json, writef_json
from rdetoolkit.invoicefile._helpers import (
    EX_GENERALTERM,
    EX_SPECIFICTERM,
    _ensure_pandas,
)
from rdetoolkit.invoicefile._invoice import _assign_invoice_val
from rdetoolkit.invoicefile._sheet_processing import (
    _SHEET_PROCESSORS,
    _identify_sheet_type,
)
from rdetoolkit.invoicefile._template import ExcelInvoiceTemplateGenerator

if TYPE_CHECKING:
    import pandas as pd


class ExcelInvoiceFile:
    """Class representing an invoice file in Excel format. Provides utilities for reading and overwriting the invoice file.

    Attributes:
        invoice_path (Path): Path to the excel invoice file (.xlsx).
        dfexcelinvoice (pd.DataFrame): Dataframe of the invoice.
        df_general (pd.DataFrame | None): Dataframe of general data (None if the sheet is absent).
        df_specific (pd.DataFrame | None): Dataframe of specific data (None if the sheet is absent).
        self.template_generator (ExcelInvoiceTemplateGenerator): Template generator for the Excelinvoice.
    """

    template_generator: ExcelInvoiceTemplateGenerator | None = None

    def __init__(self, invoice_path: Path):
        self.invoice_path = invoice_path
        self.dfexcelinvoice, self.df_general, self.df_specific = self.read()

    @classmethod
    def _get_template_generator(cls) -> ExcelInvoiceTemplateGenerator:
        if cls.template_generator is None:
            from rdetoolkit.models.invoice import FixedHeaders

            cls.template_generator = ExcelInvoiceTemplateGenerator(FixedHeaders())
        return cls.template_generator

    def read(self, *, target_path: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
        """Reads the content of the Excel invoice file and returns it as three dataframes.

        Args:
            target_path (Optional[Path], optional): Path to the excelinvoice file(.xlsx) to be read. If not provided, uses the path from `self.invoice_path`. Defaults to None.

        Returns:
            tuple[pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
                Three dataframes (dfexcelinvoice, df_general, df_specific). The general and specific sheets are ``None``
                when the source workbook does not define the corresponding sheet.

        Raises:
            StructuredError: If the invoice file is missing, if multiple invoice-list sheets exist, or if no
            invoice-list sheet is present.
        """
        if target_path is None:
            target_path = self.invoice_path

        if not os.path.exists(target_path):
            emsg = f"ERROR: excelinvoice not found {target_path}"
            raise StructuredError(emsg)

        pd = _ensure_pandas()
        dct_sheets = pd.read_excel(target_path, sheet_name=None, dtype=str, header=None, index_col=None)

        dfexcelinvoice, df_general, df_specific = None, None, None
        for sh_name, df in dct_sheets.items():
            if df.empty:
                continue

            sheet_type = _identify_sheet_type(sh_name, df)

            if sheet_type == "invoice":
                if dfexcelinvoice is not None:
                    emsg = "ERROR: multiple sheet in invoiceList files"
                    raise StructuredError(emsg)
                ExcelInvoiceFile.check_intermittent_empty_rows(df)
                dfexcelinvoice = _SHEET_PROCESSORS[sheet_type](df)
            elif sheet_type == "general_term":
                df_general = _SHEET_PROCESSORS[sheet_type](df)
            elif sheet_type == "specific_term":
                df_specific = _SHEET_PROCESSORS[sheet_type](df)
            # If sheet_type == "unknown", do nothing (skip)

        if dfexcelinvoice is None:
            emsg = "ERROR: no sheet in invoiceList files"
            raise StructuredError(emsg)

        return dfexcelinvoice, df_general, df_specific

    @classmethod
    def generate_template(cls, invoice_schema_path: str | Path, save_path: str | Path, file_mode: Literal["file", "folder"] = "file") -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Generates a template DataFrame based on the provided invoice schema and saves it to the specified path.

        Args:
            invoice_schema_path (str | Path): The path to the invoice schema file.
            save_path (str | Path): The path where the generated template will be saved.
            file_mode (Literal["file", "folder"], optional): The mode indicating whether the input is a file or a folder. Defaults to "file".

        Returns:
            tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
                - A DataFrame representing the generated template.
                - A DataFrame containing references for general terms.
                - A DataFrame containing references for specific terms.
        """
        from rdetoolkit.models.invoice import TemplateConfig

        config = TemplateConfig(
            schema_path=invoice_schema_path,
            general_term_path=EX_GENERALTERM,
            specific_term_path=EX_SPECIFICTERM,
            inputfile_mode=file_mode,
        )

        generator = cls._get_template_generator()
        template_df, df_general, df_specific, _df_version = generator.generate(config)
        _dataframes = {
            "invoice_form": template_df,
            "generalTerm": df_general,
            "specificTerm": df_specific,
            "_version": _df_version,
        }
        generator.save(_dataframes, str(save_path))
        return template_df, df_general, df_specific

    def save(self, save_path: str | Path, *, invoice: pd.DataFrame | None = None, sheet_name: str = "invoice_form", index: list[str] | None = None, header: list[str] | None = None) -> None:
        """Save the invoice DataFrame to an Excel file.

        Args:
            save_path (str | Path): The path where the Excel file will be saved.
            invoice (pd.DataFrame | None, optional): The DataFrame containing the invoice data. Defaults to None.
            sheet_name (str, optional): The name of the sheet in the Excel file. Defaults to "invoice_form".
            index (list[str] | None, optional): The list of index labels to use. If None, index will not be written. Defaults to None.
            header (list[str] | None, optional): The list of column headers to use. If None, header will not be written. Defaults to None.

        Returns:
            None
        """
        pd = _ensure_pandas()
        _invoice_df = invoice if invoice is not None else self.dfexcelinvoice
        try:
            if index:
                _invoice_df.index = pd.Index(index)
                _index_enabled = True
            else:
                _index_enabled = False
            if header:

                _invoice_df.columns = header
                _header_enabled = True
            else:
                _header_enabled = False
            _invoice_df.to_excel(save_path, index=_index_enabled, header=_header_enabled, sheet_name=sheet_name)
        except Exception as e:
            emsg = "Failed to save the invoice file."
            raise StructuredError(emsg) from e

    def overwrite(self, invoice_org: Path, dist_path: Path, invoice_schema_path: Path, idx: int) -> None:
        """Overwrites the content of the original invoice file based on the data from the Excel invoice and saves it as a new file.

        Args:
            invoice_org (Path): Path to the original invoice file.
            dist_path (Path): Path to where the overwritten invoice file will be saved.
            invoice_schema_path (Path): Path to the invoice schema.
            idx (int): Index of the target row in the invoice dataframe.
        """
        invoice_schema_obj = readf_json(invoice_schema_path)
        invoice_obj = readf_json(invoice_org)

        # Initialize to prevent original values from being retained when Excel invoice cells are empty.
        # Tags and related samples are not supported in this version of the Excel invoice.
        for key, value in invoice_obj.items():
            if key == "sample":
                self._initialize_sample(value)
            else:
                self._initialize_non_sample(key, value)

        for k, valstr in self.dfexcelinvoice.iloc[idx, :].dropna().items():
            self._assign_value_to_invoice(k, valstr, invoice_obj, invoice_schema_obj)

        self._ensure_sample_id_order(invoice_obj)

        writef_json(dist_path, invoice_obj, enc="utf_8")

    @staticmethod
    def check_intermittent_empty_rows(df: pd.DataFrame) -> None:
        """Function to detect if there are empty rows between data rows in the ExcelInvoice (in DataFrame format).

        If an empty row exists, an exception is raised.

        Args:
            df (pd.DataFrame): Information of Sheet 1 of ExcelInvoice.

        Raises:
            StructuredError: An exception is raised if an empty row exists.
        """
        for i, row in df.iterrows():
            if not ExcelInvoiceFile.__is_empty_row(row):
                continue
            if any(not ExcelInvoiceFile.__is_empty_row(r) for r in df.iloc[i + 1]):
                emsg = "Error! Blank lines exist between lines"
                raise StructuredError(emsg)

    @staticmethod
    def __is_empty_row(row: pd.Series) -> bool:
        pd = _ensure_pandas()
        return all(cell == "" or pd.isnull(cell) for cell in row)

    def _assign_value_to_invoice(self, key: str, value: str, invoice_obj: dict, schema_obj: dict) -> None:
        assign_funcs: dict[str, Callable[[str, str, dict[Any, Any], dict[Any, Any]], None]] = {
            "basic/": self._assign_basic,
            "sample/": self._assign_sample,
            "sample.general/": self._assign_sample_general,
            "sample.specific/": self._assign_sample_specific,
            "custom/": self._assign_custom,
        }

        for prefix, func in assign_funcs.items():
            if key.startswith(prefix):
                func(key, value, invoice_obj, schema_obj)
                break

    def _assign_basic(self, key: str, value: str, invoice_obj: dict, schema_obj: dict) -> None:
        cval = key.replace("basic/", "")
        _assign_invoice_val(invoice_obj, "basic", cval, value, schema_obj)

    def _assign_sample(self, key: str, value: str, invoice_obj: dict, schema_obj: dict) -> None:
        cval = key.replace("sample/", "")
        if cval == "names":
            _assign_invoice_val(invoice_obj, "sample", cval, [value], schema_obj)
        else:
            _assign_invoice_val(invoice_obj, "sample", cval, value, schema_obj)

    def _assign_sample_general(self, key: str, value: str, invoice_obj: dict, schema_obj: dict) -> None:
        cval = key.replace("sample.general/", "sample.general.")
        df_general = self.df_general
        if df_general is None:
            emsg = "ERROR: generalTerm sheet is required to assign general attributes."
            raise StructuredError(emsg)
        term_id = df_general[df_general["key_name"] == cval]["term_id"].values[0]
        for dictobj in invoice_obj["sample"]["generalAttributes"]:
            if dictobj.get("termId") == term_id:
                dictobj["value"] = value
                break

    def _assign_sample_specific(self, key: str, value: str, invoice_obj: dict, schema_obj: dict) -> None:
        cval = key.replace("sample.specific/", "sample.specific.")
        df_specific = self.df_specific
        if df_specific is None:
            emsg = "ERROR: specificTerm sheet is required to assign specific attributes."
            raise StructuredError(emsg)
        term_id = df_specific[df_specific["key_name"] == cval]["term_id"].values[0]
        for dictobj in invoice_obj["sample"]["specificAttributes"]:
            if dictobj.get("termId") == term_id:
                dictobj["value"] = value
                break

    def _assign_custom(self, key: str, value: str, invoice_obj: dict, schema_obj: dict) -> None:
        cval = key.replace("custom/", "")
        _assign_invoice_val(invoice_obj, "custom", cval, value, schema_obj)

    def _ensure_sample_id_order(self, invoice_obj: dict) -> None:
        sample_info_value = invoice_obj.get("sample")
        if sample_info_value is None:
            return
        if "sampleId" not in sample_info_value:
            return

        sampleid_value = invoice_obj["sample"].pop("sampleId")
        invoice_obj["sample"] = {"sampleId": sampleid_value, **invoice_obj["sample"]}

    def _initialize_sample(self, sample_obj: Any) -> None:
        for item, val in sample_obj.items():
            if item in ["sampleId", "composition", "referenceUrl", "description", "ownerId"]:
                sample_obj[item] = None
            elif item in ["generalAttributes", "specificAttributes"]:
                for attribute in val:
                    attribute["value"] = None

    def _initialize_non_sample(self, key: str, value: Any) -> None:
        if key not in ["datasetId", "sample"]:
            for item in value:
                if item not in ["dateSubmitted", "instrumentId"]:
                    value[item] = None
