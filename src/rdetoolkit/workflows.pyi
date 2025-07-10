from collections.abc import Generator
from pathlib import Path
from rdetoolkit.config import load_config as load_config
from rdetoolkit.core import DirectoryOps as DirectoryOps
from rdetoolkit.errors import handle_and_exit_on_structured_error as handle_and_exit_on_structured_error, handle_generic_error as handle_generic_error, skip_exception_context as skip_exception_context
from rdetoolkit.exceptions import StructuredError as StructuredError
from rdetoolkit.invoicefile import backup_invoice_json_files as backup_invoice_json_files
from rdetoolkit.models.config import Config as Config
from rdetoolkit.models.rde2types import RawFiles as RawFiles, RdeInputDirPaths as RdeInputDirPaths, RdeOutputResourcePath as RdeOutputResourcePath
from rdetoolkit.models.result import WorkflowExecutionStatus as WorkflowExecutionStatus, WorkflowResultManager as WorkflowResultManager
from rdetoolkit.modeproc import excel_invoice_mode_process as excel_invoice_mode_process, invoice_mode_process as invoice_mode_process, multifile_mode_process as multifile_mode_process, rdeformat_mode_process as rdeformat_mode_process, selected_input_checker as selected_input_checker, smarttable_invoice_mode_process as smarttable_invoice_mode_process
from rdetoolkit.rde2util import StorageDir as StorageDir
from rdetoolkit.rdelogger import get_logger as get_logger

def check_files(srcpaths: RdeInputDirPaths, *, mode: str | None, config: Config | None = None) -> tuple[RawFiles, Path | None, Path | None]: ...
def generate_folder_paths_iterator(raw_files_group: RawFiles, invoice_org_filepath: Path, invoice_schema_filepath: Path) -> Generator[RdeOutputResourcePath, None, None]: ...
def run(*, custom_dataset_function: _CallbackType | None = None, config: Config | None = None) -> str: ...
