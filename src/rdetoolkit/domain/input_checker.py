"""Input-file checker selection shared by the unified Runner and ``check_files``.

Extracted from ``domain/mode.py`` in Phase K2 (session K2(a)) so the Runner no
longer imports the legacy mode orchestration (and, through it, the v1
processing pipeline) just to pick a checker. The detection order is the v1
contract: SmartTable, Excel invoice, RDEFormat, MultiDataTile, invoice.
"""

from __future__ import annotations

from pathlib import Path

from rdetoolkit.impl.input_controller import (
    ExcelInvoiceChecker,
    InvoiceChecker,
    MultiFileChecker,
    RDEFormatChecker,
    SmartTableChecker,
)
from rdetoolkit.interfaces.filechecker import IInputFileChecker
from rdetoolkit.models.config import Config
from rdetoolkit.models.rde2types import RdeInputDirPaths


def selected_input_checker(src_paths: RdeInputDirPaths, unpacked_dir_path: Path, mode: str | None, config: Config | None = None) -> IInputFileChecker:
    """Determine the appropriate input file checker based on the provided format flags and source paths.

    The function scans the source paths to identify the type of input files present. Based on the file type
    and format flags provided, it instantiates and returns the appropriate checker.

    Args:
        src_paths (RdeInputDirPaths): Paths for the source input files.
        unpacked_dir_path (Path): Directory path for unpacked files.
        mode (str | None): Format flags indicating which checker mode is enabled. Expected values include "rdeformat", "multidatatile", or None.
        config (Config | None): Configuration instance for structuring processing execution. Defaults to None.

    Returns:
        IInputFileChecker: An instance of the appropriate input file checker based on the provided criteria.

    Note:
        The concrete checker constructors may raise exceptions if their
        initialization requirements are not met; those exceptions are not
        intercepted here.
    """
    input_files = list(src_paths.inputdata.glob("*"))
    smarttable_files = [f for f in input_files if f.name.startswith("smarttable_") and f.suffix.lower() in [".xlsx", ".csv", ".tsv"]]
    excel_invoice_files = [f for f in input_files if f.suffix.lower() in [".xls", ".xlsx"] and f.stem.endswith("_excel_invoice")]
    mode = mode.lower() if mode is not None else ""
    if smarttable_files:
        save_table_file = False
        if config and config.smarttable:
            save_table_file = config.smarttable.save_table_file
        return SmartTableChecker(unpacked_dir_path, save_table_file=save_table_file)
    if excel_invoice_files:
        return ExcelInvoiceChecker(unpacked_dir_path)
    if mode == "rdeformat":
        return RDEFormatChecker(unpacked_dir_path)
    if mode == "multidatatile":
        return MultiFileChecker(unpacked_dir_path)
    return InvoiceChecker(unpacked_dir_path)
