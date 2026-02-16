"""Excel sheet processing utilities for invoice files.

This module provides functions for identifying and processing different
types of sheets in Excel invoice files (invoice, general term, specific term).
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from rdetoolkit.exceptions import StructuredError

if TYPE_CHECKING:
    import pandas as pd


# Type alias for sheet types
SheetType = Literal["invoice", "general_term", "specific_term", "unknown"]


def read_excelinvoice(
    excelinvoice_filepath: Path | str,
) -> tuple[pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    """Deprecated wrapper around :class:`ExcelInvoiceFile`.

    This helper will be removed in version 1.5.0. Please instantiate ``ExcelInvoiceFile``
    directly and use the ``dfexcelinvoice``, ``df_general``, and ``df_specific`` attributes.
    """
    # Local import to avoid circular dependency
    from rdetoolkit.invoicefile._excelinvoice import ExcelInvoiceFile

    warnings.warn(
        "read_excelinvoice() is deprecated and will be removed in version 1.5.0. "
        "Instantiate ExcelInvoiceFile(invoice_path) and use the .dfexcelinvoice, "
        ".df_general, and .df_specific attributes instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    excel_invoice = ExcelInvoiceFile(Path(excelinvoice_filepath))
    return excel_invoice.dfexcelinvoice, excel_invoice.df_general, excel_invoice.df_specific


def _process_invoice_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """Process the main invoice sheet by extracting headers and data rows.

    Args:
        df: Raw DataFrame from Excel invoice sheet.

    Returns:
        Processed DataFrame with combined headers and data rows.
    """
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    hd1 = list(df.iloc[1, :].fillna(""))
    hd2 = list(df.iloc[2, :].fillna(""))
    df.columns = [f"{s1}/{s2}" if s1 else s2 for s1, s2 in zip(hd1, hd2, strict=False)]
    return df.iloc[4:, :].reset_index(drop=True).copy()


def _process_general_term_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """Process the general term sheet by extracting term definitions.

    Args:
        df: Raw DataFrame from general term sheet.

    Returns:
        Processed DataFrame with term_id and key_name columns.
    """
    _df_general = df[1:].copy()
    _df_general.columns = ["term_id", "key_name"]
    return _df_general


def _process_specific_term_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """Process the specific term sheet by extracting specific term definitions.

    Args:
        df: Raw DataFrame from specific term sheet.

    Returns:
        Processed DataFrame with sample_class_id, term_id, and key_name columns.
    """
    _df_specific = df[1:].copy()
    _df_specific.columns = ["sample_class_id", "term_id", "key_name"]
    return _df_specific


def _identify_sheet_type(sh_name: str, df: pd.DataFrame) -> SheetType:
    """Identify the type of an Excel sheet.

    Args:
        sh_name: Excel sheet name.
        df: DataFrame loaded from the sheet.

    Returns:
        Sheet type:
        - "invoice": InvoiceList sheet (cell A1 is "invoiceList_format_id")
        - "general_term": generalTerm sheet
        - "specific_term": specificTerm sheet
        - "unknown": Other sheets (skipped in processing)
    """
    if not df.empty and len(df) > 0 and len(df.columns) > 0:
        target_comment_value = df.iat[0, 0]
        if target_comment_value == "invoiceList_format_id":
            return "invoice"

    if sh_name == "generalTerm":
        return "general_term"
    if sh_name == "specificTerm":
        return "specific_term"

    return "unknown"


# Sheet type to processor function mapping
_SHEET_PROCESSORS: dict[SheetType, Callable[[pd.DataFrame], pd.DataFrame]] = {
    "invoice": _process_invoice_sheet,
    "general_term": _process_general_term_sheet,
    "specific_term": _process_specific_term_sheet,
}


def check_exist_rawfiles(dfexcelinvoice: pd.DataFrame, excel_rawfiles: list[Path]) -> list[Path]:
    """Checks for the existence of raw file paths listed in a DataFrame against a list of file Paths.

    This function compares a set of file names extracted from the `data_file_names/name` column of the provided DataFrame (dfexcelinvoice) with the names of files in the excel_rawfiles list.
    If there are file names in the DataFrame that are not present in the excel_rawfiles list, it raises a StructuredError with a message indicating the missing file.
    If all file names in the DataFrame are present in the excel_rawfiles list, it returns a list of Path objects from excel_rawfiles, sorted in the order they appear in the DataFrame.

    Args:
        dfexcelinvoice (pd.DataFrame): A DataFrame containing file names in the 'data_file_names/name' column.
        excel_rawfiles (list[Path]): A list of Path objects representing file paths.

    Raises:
        tructuredError: If any file name in dfexcelinvoice is not found in excel_rawfiles.

    Returns:
        list[Path]: A list of Path objects corresponding to the file names in dfexcelinvoice, ordered as they appear in the DataFrame.
    """
    file_set_group = {f.name for f in excel_rawfiles}
    file_set_invoice = set(dfexcelinvoice["data_file_names/name"])
    if file_set_invoice - file_set_group:
        emsg = f"ERROR: raw file not found: {(file_set_invoice-file_set_group).pop()}"
        raise StructuredError(emsg)
    # Sort excel_rawfiles in the order they appear in the invoice
    _tmp = {f.name: f for f in excel_rawfiles}
    try:
        return [_tmp[f] for f in dfexcelinvoice["data_file_names/name"]]
    except KeyError as e:
        emsg = f"Invalid or missing key in data_file_names/name: {e}"
        raise StructuredError(emsg) from e


def check_exist_rawfiles_for_folder(dfexcelinvoice: pd.DataFrame, rawfiles_tpl: tuple) -> list:
    """Function to check the existence of rawfiles_tpl specified for a folder.

    It checks whether rawfiles_tpl, specified as an index, exists in all indexes of ExcelInvoice.
    Assumes that the names of the terminal folders are unique and checks for the existence of rawfiles_tpl.

    Args:
        dfexcelinvoice (DataFrame): The dataframe of ExcelInvoice.
        rawfiles_tpl (tuple): Tuple of raw files.

    Returns:
        list: A list of rawfiles_tpl sorted in the order they appear in the invoice.

    Raises:
        StructuredError: If rawfiles_tpl does not exist in all indexes of ExcelInvoice, or if there are unused raw data.
    """
    # Check for the existence of rawfiles_tpl specified as an index
    # Conversely, check that all rawfiles_tpl are present in the ExcelInvoice index
    dcttpl = {str(tpl[0].parent.name): tpl for tpl in rawfiles_tpl}  # Assuming terminal folder names are unique
    dir_setglob = set(dcttpl.keys())
    dir_set_invoice = set(dfexcelinvoice["data_folder"])
    if dir_setglob == dir_set_invoice:
        # Reorder rawfiles_tpl according to the order of appearance in the invoice
        return [dcttpl[d] for d in dfexcelinvoice["data_folder"]]
    if dir_setglob - dir_set_invoice:
        emsg = f"ERROR: unused raw data: {(dir_setglob-dir_set_invoice).pop()}"
        raise StructuredError(emsg)
    if dir_set_invoice - dir_setglob:
        emsg = f"ERROR: raw data not found: {(dir_set_invoice-dir_setglob).pop()}"
        raise StructuredError(emsg)

    emsg = "ERROR: unknown error"
    raise StructuredError(emsg)  # This line should never be reached
