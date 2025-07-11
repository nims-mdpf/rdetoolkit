from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from rdetoolkit.models.config import Config as Config
from typing import TypedDict

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
    def __init__(self, inputdata, invoice, tasksupport, config=...) -> None: ...

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
    temp: Path | None = ...
    invoice_patch: Path | None = ...
    attachment: Path | None = ...
    def __init__(self, raw, nonshared_raw, rawfiles, struct, main_image, other_image, meta, thumbnail, logs, invoice, invoice_schema_json, invoice_org, temp=..., invoice_patch=..., attachment=...) -> None: ...

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
    def __init__(self, value, unit) -> None: ...
