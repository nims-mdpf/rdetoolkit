from __future__ import annotations

import os
import shutil
from pathlib import Path

from rdetoolkit.impl.input_controller import (
    ExcelInvoiceChecker,
    InvoiceChecker,
    MultiFileChecker,
    RDEFormatChecker,
    SmartTableChecker,
)
from rdetoolkit.interfaces.filechecker import IInputFileChecker
from rdetoolkit.models.rde2types import DatasetCallback, RdeInputDirPaths, RdeOutputResourcePath
from rdetoolkit.models.result import WorkflowExecutionStatus
from rdetoolkit.models.config import Config
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.processing.factories import PipelineFactory
from rdetoolkit.rdelogger import get_logger


logger = get_logger(__name__, file_path="data/logs/rdesys.log")


def rdeformat_mode_process(
    index: str,
    srcpaths: RdeInputDirPaths,
    resource_paths: RdeOutputResourcePath,
    datasets_process_function: DatasetCallback | None = None,
) -> WorkflowExecutionStatus:
    """Run the ``rdeformat`` pipeline and optional dataset callback.

    Args:
        index: Workflow execution identifier.
        srcpaths: Directories containing input data.
        resource_paths: Destination directories for structured outputs.
        datasets_process_function: Optional hook executed before validation.

    Raises:
        Exception: Propagates failures raised by the dataset callback or
            pipeline validation steps. Errors from the description update stage
            are swallowed by the pipeline implementation.

    Returns:
        WorkflowExecutionStatus: Execution metadata including status, target,
        and optional error information.
    """
    context = ProcessingContext(
        index=index,
        srcpaths=srcpaths,
        resource_paths=resource_paths,
        datasets_function=datasets_process_function,
        mode_name="rdeformat",
    )

    pipeline = PipelineFactory.create_rdeformat_pipeline()
    return pipeline.execute(context)


def multifile_mode_process(
    index: str,
    srcpaths: RdeInputDirPaths,
    resource_paths: RdeOutputResourcePath,
    datasets_process_function: DatasetCallback | None = None,
) -> WorkflowExecutionStatus:
    """Run the ``MultiDataTile`` pipeline and optional dataset callback.

    Args:
        index: Workflow execution identifier.
        srcpaths: Directories containing input data.
        resource_paths: Destination directories for structured outputs.
        datasets_process_function: Optional hook executed before validation.

    Raises:
        Exception: Propagates failures raised by the dataset callback or
            pipeline validation steps. Errors from the description update stage
            are swallowed by the pipeline implementation.

    Returns:
        WorkflowExecutionStatus: Execution metadata including status, target,
        and optional error information.
    """
    context = ProcessingContext(
        index=index,
        srcpaths=srcpaths,
        resource_paths=resource_paths,
        datasets_function=datasets_process_function,
        mode_name="MultiDataTile",
    )

    pipeline = PipelineFactory.create_multifile_pipeline()
    return pipeline.execute(context)


def excel_invoice_mode_process(
    srcpaths: RdeInputDirPaths,
    resource_paths: RdeOutputResourcePath,
    excel_invoice_file: Path,
    idx: int,
    datasets_process_function: DatasetCallback | None = None,
) -> WorkflowExecutionStatus:
    """Run the ``ExcelInvoice`` pipeline and optional dataset callback.

    Args:
        srcpaths: Directories containing input data.
        resource_paths: Destination directories for structured outputs.
        excel_invoice_file: Source Excel invoice file.
        idx: Index of the workbook row to process.
        datasets_process_function: Optional hook executed before validation.

    Raises:
        Exception: Propagates failures raised by the dataset callback or
            pipeline validation steps. Errors from the description update stage
            are swallowed by the pipeline implementation.

    Returns:
        WorkflowExecutionStatus: Execution metadata including status, target,
        and optional error information.
    """
    context = ProcessingContext(
        index=str(idx),
        srcpaths=srcpaths,
        resource_paths=resource_paths,
        datasets_function=datasets_process_function,
        mode_name="Excelinvoice",
        excel_file=excel_invoice_file,
        excel_index=idx,
    )

    pipeline = PipelineFactory.create_excel_pipeline()
    return pipeline.execute(context)


def invoice_mode_process(
    index: str,
    srcpaths: RdeInputDirPaths,
    resource_paths: RdeOutputResourcePath,
    datasets_process_function: DatasetCallback | None = None,
) -> WorkflowExecutionStatus:
    """Run the standard invoice pipeline and optional dataset callback.

    Args:
        index: Workflow execution identifier.
        srcpaths: Directories containing input data.
        resource_paths: Destination directories for structured outputs.
        datasets_process_function: Optional hook executed before validation.

    Raises:
        Exception: Propagates failures raised by the dataset callback or
            pipeline validation steps. Errors from the description update stage
            are swallowed by the pipeline implementation.

    Returns:
        WorkflowExecutionStatus: Execution metadata including status, target,
        and optional error information.
    """
    context = ProcessingContext(
        index=index,
        srcpaths=srcpaths,
        resource_paths=resource_paths,
        datasets_function=datasets_process_function,
        mode_name="invoice",
    )

    pipeline = PipelineFactory.create_invoice_pipeline()
    return pipeline.execute(context)


def smarttable_invoice_mode_process(
    index: str,
    srcpaths: RdeInputDirPaths,
    resource_paths: RdeOutputResourcePath,
    smarttable_file: Path,
    datasets_process_function: DatasetCallback | None = None,
) -> WorkflowExecutionStatus:
    """Run the ``SmartTableInvoice`` pipeline and optional dataset callback.

    Args:
        index: Workflow execution identifier.
        srcpaths: Directories containing input data.
        resource_paths: Destination directories for structured outputs.
        smarttable_file: SmartTable spreadsheet supplying invoice data.
        datasets_process_function: Optional hook executed before validation.

    Raises:
        Exception: Propagates failures raised by the dataset callback or
            pipeline validation steps. Errors from the description update stage
            are swallowed by the pipeline implementation.

    Returns:
        WorkflowExecutionStatus: Execution metadata including status, target,
        and optional error information.
    """
    context = ProcessingContext(
        index=index,
        srcpaths=srcpaths,
        resource_paths=resource_paths,
        datasets_function=datasets_process_function,
        mode_name="SmartTableInvoice",
        smarttable_file=smarttable_file,
    )

    pipeline = PipelineFactory.create_smarttable_invoice_pipeline()
    return pipeline.execute(context)


def copy_input_to_rawfile_for_rdeformat(resource_paths: RdeOutputResourcePath) -> None:
    """Copy the input raw files to their respective directories based on the file's part names.

    This function scans through the parts of each file's path in `resource_paths.rawfiles`. If the file path
    contains a directory name listed in the `directories` dict, the file will be copied to the corresponding
    directory.

    Args:
        resource_paths (RdeOutputResourcePath): Paths to the resources where data will be written or read from.

    Returns:
        None
    """
    directories = {
        "raw": resource_paths.raw,
        "main_image": resource_paths.main_image,
        "other_image": resource_paths.other_image,
        "meta": resource_paths.meta,
        "structured": resource_paths.struct,
        "logs": resource_paths.logs,
        "nonshared_raw": resource_paths.nonshared_raw,
    }
    for f in resource_paths.rawfiles:
        for dir_name, directory in directories.items():
            if dir_name in f.parts:
                shutil.copy(f, os.path.join(str(directory), f.name))
                break


def copy_input_to_rawfile(raw_dir_path: Path, raw_files: tuple[Path, ...]) -> None:
    """Copy the input raw files to the specified directory.

    This function takes a list of raw file paths and copies each file to the given `raw_dir_path`.

    Args:
        raw_dir_path (Path): The directory path where the raw files will be copied to.
        raw_files (tuple[Path, ...]): A tuple of file paths that need to be copied.

    Returns:
        None
    """
    # Ensure the directory exists before copying files
    raw_dir_path.mkdir(parents=True, exist_ok=True)

    for f in raw_files:
        shutil.copy(f, os.path.join(raw_dir_path, f.name))


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
