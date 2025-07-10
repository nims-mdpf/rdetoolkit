from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable

from rdetoolkit.impl.input_controller import (
    ExcelInvoiceChecker,
    InvoiceChecker,
    MultiFileChecker,
    RDEFormatChecker,
    SmartTableChecker,
)
from rdetoolkit.interfaces.filechecker import IInputFileChecker
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
from rdetoolkit.models.result import WorkflowExecutionStatus
from rdetoolkit.models.config import Config
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.processing.factories import PipelineFactory
from rdetoolkit.rdelogger import get_logger

_CallbackType = Callable[[RdeInputDirPaths, RdeOutputResourcePath], None]


logger = get_logger(__name__, file_path="data/logs/rdesys.log")


def rdeformat_mode_process(
    index: str,
    srcpaths: RdeInputDirPaths,
    resource_paths: RdeOutputResourcePath,
    datasets_process_function: _CallbackType | None = None,
) -> WorkflowExecutionStatus:
    """Process the source data and apply specific transformations using the provided callback function.

    This function performs several steps:

    1. Overwrites the invoice file.
    2. Copies input files to the rawfile directory.
    3. Runs a custom dataset process function if provided.
    4. Copies images to the thumbnail directory.
    5. Updates descriptions with features, ignoring any errors during this step.
    6. Validates the metadata-def.json file.
    7. Validates the invoice file against the invoice schema.

    Args:
        index: The workflow execution ID (run_id) is a unique identifier used to distinguish a specific execution of a workflow.
        srcpaths (RdeInputDirPaths): Input paths for the source data.
        resource_paths (RdeOutputResourcePath): Paths to the resources where data will be written or read from.
        datasets_process_function (_CallbackType, optional): A callback function that processes datasets. Defaults to None.
        config (Config, optional): Configuration instance for structured processing execution. Defaults to None.

    Raises:
        Any exceptions raised by `datasets_process_function` or during the validation steps will propagate upwards. Exceptions during the `update_description_with_features` step are caught and silently ignored.

    Returns:
        WorkflowExecutionStatus: An object containing the execution status of the workflow, including:
            - run_id (str): The unique identifier for the workflow execution, zero-padded to four digits.
            - title (str): A descriptive title for the workflow execution.
            - status (str): The status of the workflow execution, either "success" or "failed".
            - mode (str): The mode in which the workflow was executed, e.g., "rdeformat".
            - error_code (int | None): The error code if an error occurred, otherwise None.
            - error_message (str | None): The error message if an error occurred, otherwise None.
            - target (str): The target directory or file path related to the workflow execution.
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
    datasets_process_function: _CallbackType | None = None,
) -> WorkflowExecutionStatus:
    """Processes multiple source files and applies transformations using the provided callback function.

    This function performs several steps:

    1. Overwrites the invoice file.
    2. Copies input files to the rawfile directory.
    3. Runs a custom dataset process function if provided.
    4. Replaces the placeholder '${filename}' in the invoice with the actual filename if necessary.
    5. Copies images to the thumbnail directory.
    6. Attempts to update descriptions with features, ignoring any errors during this step.
    7. Validates the metadata-def.json file.
    8. Validates the invoice file against the invoice schema.

    Args:
        index: The workflow execution ID (run_id) is a unique identifier used to distinguish a specific execution of a workflow.
        srcpaths (RdeInputDirPaths): Input paths for the source data.
        resource_paths (RdeOutputResourcePath): Paths to the resources where data will be written or read from.
        datasets_process_function (_CallbackType, optional): A callback function that processes datasets. Defaults to None.
        config (Config, optional): Configuration instance for structured processing execution. Defaults to None.

    Raises:
        Any exceptions raised by `datasets_process_function` or during the validation steps will propagate upwards. Exceptions during the `update_description_with_features` step are caught and silently ignored.

    Returns:
        WorkflowExecutionStatus: An object containing the execution status of the workflow, including:
            - run_id (str): The unique identifier for the workflow execution, zero-padded to four digits.
            - title (str): A descriptive title for the workflow execution.
            - status (str): The status of the workflow execution, either "success" or "failed".
            - mode (str): The mode in which the workflow was executed, e.g., "rdeformat".
            - error_code (int | None): The error code if an error occurred, otherwise None.
            - error_message (str | None): The error message if an error occurred, otherwise None.
            - target (str): The target directory or file path related to the workflow execution.
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
    datasets_process_function: _CallbackType | None = None,
) -> WorkflowExecutionStatus:
    """Processes invoice data from an Excel file and applies dataset transformations using the provided callback function.

    This function performs several steps:

    1. Overwrites the Excel invoice file.
    2. Copies input files to the rawfile directory.
    3. Runs a custom dataset process function if provided.
    4. Replaces the placeholder '${filename}' in the invoice with the actual filename if necessary.
    5. Copies images to the thumbnail directory.
    6. Attempts to update descriptions with features, ignoring any errors during this step.
    7. Validates the metadata-def.json file.
    8. Validates the invoice file against the invoice schema.

    Args:
        srcpaths (RdeInputDirPaths): Input paths for the source data.
        resource_paths (RdeOutputResourcePath): Paths to the resources where data will be written or read from.
        excel_invoice_file (Path): Path to the source Excel invoice file.
        idx (int): Index or identifier for the data being processed.
        datasets_process_function (_CallbackType, optional): A callback function that processes datasets. Defaults to None.
        config (Config, optional): Configuration instance for structured processing execution. Defaults to None.

    Raises:
        StructuredError: When encountering issues related to Excel invoice overwriting or during the validation steps.
        Any exceptions raised by `datasets_process_function` will propagate upwards. Exceptions during the `update_description_with_features` step are caught and silently ignored.

    Returns:
        WorkflowExecutionStatus: An object containing the execution status of the workflow, including:
            - run_id (str): The unique identifier for the workflow execution, zero-padded to four digits.
            - title (str): A descriptive title for the workflow execution.
            - status (str): The status of the workflow execution, either "success" or "failed".
            - mode (str): The mode in which the workflow was executed, e.g., "rdeformat".
            - error_code (int | None): The error code if an error occurred, otherwise None.
            - error_message (str | None): The error message if an error occurred, otherwise None.
            - target (str): The target directory or file path related to the workflow execution.
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
    datasets_process_function: _CallbackType | None = None,
) -> WorkflowExecutionStatus:
    """Processes invoice-related data, applies dataset transformations using the provided callback function, and updates descriptions.

    This function performs several steps:

    1. Copies input files to the rawfile directory.
    2. Runs a custom dataset process function if provided.
    3. Copies images to the thumbnail directory.
    4. Replaces the placeholder '${filename}' in the invoice with the actual filename if necessary.
    5. Attempts to update descriptions with features, ignoring any errors during this step.
    6. Validates the metadata-def.json file.
    7. Validates the invoice file against the invoice schema.

    Args:
        index: The workflow execution ID (run_id) is a unique identifier used to distinguish a specific execution of a workflow.
        srcpaths (RdeInputDirPaths): Input paths for the source data.
        resource_paths (RdeOutputResourcePath): Paths to the resources where data will be written or read from.
        datasets_process_function (_CallbackType, optional): A callback function that processes datasets. Defaults to None.
        config (Config, optional): Configuration instance for structured processing execution. Defaults to None.

    Raises:
        Any exceptions raised by `datasets_process_function` will propagate upwards. Exceptions during the `update_description_with_features` step are caught and silently ignored.

    Returns:
        WorkflowExecutionStatus: An object containing the execution status of the workflow, including:
            - run_id (str): The unique identifier for the workflow execution, zero-padded to four digits.
            - title (str): A descriptive title for the workflow execution.
            - status (str): The status of the workflow execution, either "success" or "failed".
            - mode (str): The mode in which the workflow was executed, e.g., "rdeformat".
            - error_code (int | None): The error code if an error occurred, otherwise None.
            - error_message (str | None): The error message if an error occurred, otherwise None.
            - target (str): The target directory or file path related to the workflow execution.
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
    datasets_process_function: _CallbackType | None = None,
) -> WorkflowExecutionStatus:
    """Processes SmartTable files and generates invoice data for structured processing.

    This function performs several steps:

    1. Initializes invoice from SmartTable file data.
    2. Copies input files to the rawfile directory.
    3. Runs a custom dataset process function if provided.
    4. Copies images to the thumbnail directory.
    5. Replaces the placeholder '${filename}' in the invoice with the actual filename if necessary.
    6. Attempts to update descriptions with features, ignoring any errors during this step.
    7. Validates the metadata-def.json file.
    8. Validates the invoice file against the invoice schema.

    Args:
        index: The workflow execution ID (run_id) is a unique identifier used to distinguish a specific execution of a workflow.
        srcpaths (RdeInputDirPaths): Input paths for the source data.
        resource_paths (RdeOutputResourcePath): Paths to the resources where data will be written or read from.
        smarttable_file (Path): Path to the SmartTable file (.xlsx, .csv, .tsv).
        datasets_process_function (_CallbackType, optional): A callback function that processes datasets. Defaults to None.

    Raises:
        StructuredError: When encountering issues related to SmartTable processing or during the validation steps.
        Any exceptions raised by `datasets_process_function` will propagate upwards. Exceptions during the `update_description_with_features` step are caught and silently ignored.

    Returns:
        WorkflowExecutionStatus: An object containing the execution status of the workflow, including:
            - run_id (str): The unique identifier for the workflow execution, zero-padded to four digits.
            - title (str): A descriptive title for the workflow execution.
            - status (str): The status of the workflow execution, either "success" or "failed".
            - mode (str): The mode in which the workflow was executed, e.g., "SmartTableInvoice".
            - error_code (int | None): The error code if an error occurred, otherwise None.
            - error_message (str | None): The error message if an error occurred, otherwise None.
            - target (str): The target directory or file path related to the workflow execution.
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
        config (Config | None): Configuration instance for structured processing execution. Defaults to None.

    Returns:
        IInputFileChecker: An instance of the appropriate input file checker based on the provided criteria.

    Raises:
        None, but callers should be aware that downstream exceptions can be raised by individual checker initializations.
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
