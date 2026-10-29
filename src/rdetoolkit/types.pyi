from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

@dataclass(frozen=True, slots=True)
class InputPaths:
    inputdata: Path
    invoice: Path
    tasksupport: Path
    raw: Path | None = ...
    rawfiles: tuple[Path, ...] = ...
    smarttable_rawfile: Path | None = ...

OutputKind = Literal[
    "struct",
    "meta",
    "main_image",
    "other_image",
    "thumbnail",
    "attachment",
    "nonshared_raw",
    "raw",
    "invoice",
    "logs",
]

@dataclass(frozen=True, slots=True)
class OutputContext:
    struct: Path
    meta: Path
    main_image: Path
    other_image: Path
    thumbnail: Path
    raw: Path
    logs: Path
    attachment: Path
    nonshared_raw: Path
    invoice: Path
    @classmethod
    def from_resource_paths(cls, resource_paths: Any) -> OutputContext: ...
    def path_for(self, kind: OutputKind, filename: str) -> Path: ...
    def write_bytes(self, kind: OutputKind, filename: str, content: bytes) -> Path: ...

@dataclass(slots=True)
class Metadata:
    custom: dict[str, Any] = field(default_factory=dict)
    basic: dict[str, Any] | None = None
    def set(self, key: str, value: Any) -> None: ...
    def get(self, key: str, default: Any = None) -> Any: ...

@dataclass(frozen=True, slots=True)
class InvoiceData:
    raw: dict[str, Any] = field(default_factory=dict)
    mode: str = ...
    schema: dict[str, Any] | None = None
    def get_field(self, key: str, default: Any = None) -> Any: ...
    def get_custom_fields(self) -> dict[str, Any]: ...

@dataclass(frozen=True, slots=True)
class IterationInfo:
    index: int
    total: int
    mode: str

class V2SystemSettings(BaseModel):
    model_config: ConfigDict
    extended_mode: str = ...
    save_raw: bool = ...
    save_nonshared_raw: bool = ...
    save_thumbnail_image: bool = ...
    magic_variable: bool = ...
    save_invoice_to_structured: bool = ...
    feature_description: bool = ...

class V2ExecutionSettings(BaseModel):
    model_config: ConfigDict
    type_check: str = ...
    on_iteration_error: Literal["continue", "fail_fast"]

class V2RecordingSettings(BaseModel):
    model_config: ConfigDict
    repr_head: Literal["on", "off"]
    repr_head_len: int

class V2SmartTableSettings(BaseModel):
    model_config: ConfigDict
    save_table_file: bool = ...


class RdeConfig(BaseModel):
    model_config: ConfigDict
    system: V2SystemSettings = Field(default_factory=V2SystemSettings)
    execution: V2ExecutionSettings = Field(default_factory=V2ExecutionSettings)
    provenance: V2RecordingSettings = Field(default_factory=V2RecordingSettings)
    custom: dict[str, Any] = Field(default_factory=dict)
    smarttable: V2SmartTableSettings = Field(default_factory=V2SmartTableSettings)

def _require_simple_filename(filename: str) -> None: ...
def _build_output_context(
    *,
    struct: Path,
    meta: Path,
    main_image: Path,
    other_image: Path,
    thumbnail: Path,
    raw: Path,
    logs: Path,
    attachment: Path,
    nonshared_raw: Path,
    invoice: Path,
) -> OutputContext: ...

from rdetoolkit.core.context import RunContext as RunContext
from rdetoolkit.core.calllog import NodeCallRecord as NodeCallRecord
from rdetoolkit.core.calllog import TypeSummary as TypeSummary
from rdetoolkit.report.events import Event as Event
from rdetoolkit.report.events import EventSink as EventSink
from rdetoolkit.report.run_report import RunReport as RunReport
