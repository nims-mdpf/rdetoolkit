from collections.abc import Callable, Generator, Mapping
from pathlib import Path
from typing import Any, overload
from rdetoolkit.config import load_config as load_config
from rdetoolkit.core import DirectoryOps as DirectoryOps
from rdetoolkit.exceptions import StructuredError as StructuredError
from rdetoolkit.invoicefile import backup_invoice_json_files as backup_invoice_json_files
from rdetoolkit.models.config import Config as Config
from rdetoolkit.models.rde2types import DatasetCallback as DatasetCallback, RawFiles as RawFiles, RdeDatasetPaths as RdeDatasetPaths, RdeInputDirPaths as RdeInputDirPaths, RdeOutputResourcePath as RdeOutputResourcePath, SmartTableRawFiles as SmartTableRawFiles
from rdetoolkit.rde2util import StorageDir as StorageDir
from rdetoolkit.rdelogger import get_logger as get_logger
from rdetoolkit.result import Result as Result
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.types import RdeConfig
from rdetoolkit.templates import ProcessingTemplate

def check_files_result(srcpaths: RdeInputDirPaths, *, mode: str | None, config: Config | None = None) -> Result[tuple[RawFiles | SmartTableRawFiles, Path | None, Path | None], StructuredError]: ...
def check_files(srcpaths: RdeInputDirPaths, *, mode: str | None, config: Config | None = None) -> tuple[RawFiles | SmartTableRawFiles, Path | None, Path | None]: ...
def generate_folder_paths_iterator(raw_files_group: RawFiles | SmartTableRawFiles, invoice_org_filepath: Path, invoice_schema_filepath: Path, *, smarttable_mode: bool = ...) -> Generator[RdeOutputResourcePath, None, None]: ...
def _callback_entry_log_path(root: Path, data_root: Path) -> Path: ...
def _run_callback_entry(custom_dataset_function: DatasetCallback | None, config: Any = None) -> str: ...
@overload
def run(
    *,
    flow: Callable[..., Any] | type[ProcessingTemplate],
    custom_dataset_function: None = None,
    config: RdeConfig | Mapping[str, Any] | None = None,
) -> RunReport: ...
@overload
def run(
    *,
    flow: None = None,
    custom_dataset_function: DatasetCallback | None = None,
    config: Config | None = None,
) -> str: ...
