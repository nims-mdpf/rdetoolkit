from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from rdetoolkit.models.config import Config as Config
from typing import NewType, Protocol, TypedDict, overload

# Legacy type aliases - kept for backward compatibility
ZipFilesPathList = Sequence[Path]
UnZipFilesPathList = Sequence[Path]
ExcelInvoicePathList = Sequence[Path]
OtherFilesPathList = Sequence[Path]
PathTuple = tuple[Path, ...]
InputFilesGroup = tuple[ZipFilesPathList, ExcelInvoicePathList, OtherFilesPathList]
RawFiles = Sequence[PathTuple]
MetaType = dict[str, str | int | float | list | bool]
RepeatedMetaType = dict[str, list[str | int | float | list | bool]]
MetaItem = dict[str, str | int | float | list | bool]
RdeFsPath = str | Path

# NewType definitions for improved type safety
ZipFilePath = NewType('ZipFilePath', Path)
UnzippedFilePath = NewType('UnzippedFilePath', Path)
ExcelInvoicePath = NewType('ExcelInvoicePath', Path)
SmartTablePath = NewType('SmartTablePath', Path)
OtherFilePath = NewType('OtherFilePath', Path)
InputDataDir = NewType('InputDataDir', Path)
OutputDir = NewType('OutputDir', Path)
TemporaryDir = NewType('TemporaryDir', Path)
TaskSupportDir = NewType('TaskSupportDir', Path)
InvoiceDir = NewType('InvoiceDir', Path)

# Helper function stubs for NewType creation
def create_zip_file_path(path: Path | str) -> ZipFilePath: ...
def create_excel_invoice_path(path: Path | str) -> ExcelInvoicePath: ...
def create_smarttable_path(path: Path | str) -> SmartTablePath: ...
def create_input_data_dir(path: Path | str) -> InputDataDir: ...
def create_output_dir(path: Path | str) -> OutputDir: ...

# Validated path types with runtime validation
@dataclass(frozen=True, slots=True)
class ValidatedPath:
    path: Path
    def __post_init__(self) -> None: ...
    def __str__(self) -> str: ...
    def __fspath__(self) -> str: ...
    @classmethod
    def from_string(cls, path_str: str) -> ValidatedPath: ...
    @classmethod
    def from_parts(cls, *parts: str) -> ValidatedPath: ...

@dataclass(frozen=True, slots=True)
class ZipFile(ValidatedPath):
    def __post_init__(self) -> None: ...

@dataclass(frozen=True, slots=True)
class ExcelFile(ValidatedPath):
    def __post_init__(self) -> None: ...

@dataclass(frozen=True, slots=True)
class CsvFile(ValidatedPath):
    def __post_init__(self) -> None: ...

@dataclass(frozen=True, slots=True)
class JsonFile(ValidatedPath):
    def __post_init__(self) -> None: ...

@dataclass(frozen=True, slots=True)
class ValidatedDirectory(ValidatedPath):
    must_exist: bool
    def __post_init__(self) -> None: ...

# Collection types for file groups
@dataclass(frozen=True)
class FileGroup:
    raw_files: tuple[Path, ...]
    zip_files: tuple[ZipFile, ...]
    excel_invoices: tuple[ExcelFile, ...]
    other_files: tuple[Path, ...]
    def __post_init__(self) -> None: ...
    @property
    def all_files(self) -> tuple[Path, ...]: ...
    @property
    def file_count(self) -> int: ...
    @property
    def has_zip_files(self) -> bool: ...
    @property
    def has_excel_invoices(self) -> bool: ...
    @classmethod
    def from_paths(cls, paths: Sequence[Path], *, auto_classify: bool = True) -> FileGroup: ...
    @classmethod
    def empty(cls) -> FileGroup: ...

@dataclass(frozen=True)
class ProcessedFileGroup:
    unzipped_files: tuple[Path, ...]
    excel_invoice: ExcelFile | None
    smarttable_csv: CsvFile | None
    raw_data_files: tuple[Path, ...]
    metadata_files: tuple[Path, ...]
    @property
    def has_excel_invoice(self) -> bool: ...
    @property
    def has_smarttable(self) -> bool: ...
    @property
    def total_file_count(self) -> int: ...

@dataclass
class RdeFormatFlags:
    def __init__(self) -> None: ...
    def __post_init__(self) -> None: ...
    @property
    def is_rdeformat_enabled(self) -> bool: ...
    @is_rdeformat_enabled.setter
    def is_rdeformat_enabled(self, value: bool) -> None: ...
    @property
    def is_multifile_enabled(self) -> bool: ...
    @is_multifile_enabled.setter
    def is_multifile_enabled(self, value: bool) -> None: ...

def create_default_config() -> Config: ...
@dataclass
class RdeInputDirPaths:
    inputdata: Path
    invoice: Path
    tasksupport: Path
    config: Config = ...
    @property
    def default_csv(self) -> Path: ...
    def __init__(self, inputdata: Path, invoice: Path, tasksupport: Path, config: Config = ...) -> None: ...

@dataclass
class RdeOutputResourcePath:
    raw: Path
    nonshared_raw: Path
    rawfiles: tuple[Path, ...]
    struct: Path
    main_image: Path
    other_image: Path
    meta: Path
    thumbnail: Path
    logs: Path
    invoice: Path
    invoice_schema_json: Path
    invoice_org: Path
    smarttable_rowfile: Path | None = ...
    temp: Path | None = ...
    invoice_patch: Path | None = ...
    attachment: Path | None = ...
    def __init__(self, raw: Path, nonshared_raw: Path, rawfiles: tuple[Path, ...], struct: Path, main_image: Path, other_image: Path, meta: Path, thumbnail: Path, logs: Path, invoice: Path, invoice_schema_json: Path, invoice_org: Path, smarttable_rowfile: Path | None = ..., temp: Path | None = ..., invoice_patch: Path | None = ..., attachment: Path | None = ...) -> None: ...

@dataclass
class RdeDatasetPaths:
    input_paths: RdeInputDirPaths
    output_paths: RdeOutputResourcePath
    @property
    def inputdata(self) -> Path: ...
    @property
    def tasksupport(self) -> Path: ...
    @property
    def config(self) -> Config: ...
    @property
    def default_csv(self) -> Path: ...
    @property
    def raw(self) -> Path: ...
    @property
    def nonshared_raw(self) -> Path: ...
    @property
    def smarttable_rowfile(self) -> Path | None: ...
    @property
    def rawfiles(self) -> tuple[Path, ...]: ...
    @property
    def struct(self) -> Path: ...
    @property
    def main_image(self) -> Path: ...
    @property
    def other_image(self) -> Path: ...
    @property
    def meta(self) -> Path: ...
    @property
    def thumbnail(self) -> Path: ...
    @property
    def logs(self) -> Path: ...
    @property
    def invoice(self) -> Path: ...
    @property
    def invoice_schema_json(self) -> Path: ...
    @property
    def invoice_org(self) -> Path: ...
    @property
    def temp(self) -> Path | None: ...
    @property
    def invoice_patch(self) -> Path | None: ...
    @property
    def attachment(self) -> Path | None: ...
    @property
    def metadata_def_json(self) -> Path: ...
    def as_legacy_args(self) -> tuple[RdeInputDirPaths, RdeOutputResourcePath]: ...
    def __init__(self, input_paths, output_paths) -> None: ...

class DatasetCallback(Protocol):
    @overload
    def __call__(self, paths: RdeDatasetPaths, /) -> None: ...
    @overload
    def __call__(self, srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath, /) -> None: ...

class Name(TypedDict):
    ja: str
    en: str

class Schema(TypedDict, total=False):
    type: str
    format: str

class MetadataDefJson(TypedDict):
    name: Name
    schema: Schema
    unit: str
    description: str
    uri: str
    originalName: str
    originalType: str
    mode: str
    order: str
    valiable: int
    action: str

@dataclass
class ValueUnitPair:
    value: str
    unit: str
    def __init__(self, value: str, unit: str) -> None: ...
