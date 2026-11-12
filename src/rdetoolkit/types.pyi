from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Final, Literal, final, type_check_only

from pydantic import BaseModel, ConfigDict, Field

@dataclass(frozen=True, slots=True)
class InputPaths:
    inputdata: Path
    invoice: Path
    tasksupport: Path
    raw: Path | None = ...
    rawfiles: tuple[Path, ...] = ...
    smarttable_rawfile: Path | None = ...
    invoice_org: Path | None = ...

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

@type_check_only
@final
class _FactoryToken:
    """Stub-only nominal type of the private ``_FACTORY_TOKEN`` sentinel.

    At runtime the sentinel is a bare ``object()``; giving it a type that user
    code cannot construct is what makes direct ``OutputContext(...)`` calls a
    type error while rdetoolkit's own factories stay type-checked.
    """

_FACTORY_TOKEN: Final[_FactoryToken]

class OutputContext:
    """Immutable, factory-only output path context (Design §4.2).

    Construct it with ``OutputContext.from_resource_paths()``. The runtime class
    is a frozen dataclass whose ``__post_init__`` raises ``TypeError`` unless the
    private factory token is passed, so the stub models that contract directly:

    * ``__init__`` requires ``_token: _FactoryToken``, a stub-only type no public
      API hands out, so ``OutputContext(struct=..., ...)`` fails type checking
      exactly where it would fail at runtime.
    * It is deliberately *not* declared as a dataclass: ``dataclasses.replace()``
      re-enters ``__init__`` without the token and raises at runtime, so it must
      not type-check either.
    * The ten directories are read-only properties because the runtime instance
      is frozen.
    """

    def __init__(
        self,
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
        _token: _FactoryToken,
    ) -> None: ...
    @property
    def struct(self) -> Path: ...
    @property
    def meta(self) -> Path: ...
    @property
    def main_image(self) -> Path: ...
    @property
    def other_image(self) -> Path: ...
    @property
    def thumbnail(self) -> Path: ...
    @property
    def raw(self) -> Path: ...
    @property
    def logs(self) -> Path: ...
    @property
    def attachment(self) -> Path: ...
    @property
    def nonshared_raw(self) -> Path: ...
    @property
    def invoice(self) -> Path: ...
    @classmethod
    def from_resource_paths(cls, resource_paths: Any) -> OutputContext: ...
    def path_for(self, kind: OutputKind, filename: str) -> Path: ...
    def write_bytes(self, kind: OutputKind, filename: str, content: bytes) -> Path: ...

@dataclass(slots=True)
class Metadata:
    custom: dict[str, Any] = field(default_factory=dict)
    basic: dict[str, Any] | None = None
    units: dict[str, str] = field(default_factory=dict)
    variable: list[dict[str, dict[str, Any]]] = field(default_factory=list)
    def set(self, key: str, value: Any, *, unit: str | None = None) -> None: ...
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
    model_config: ClassVar[ConfigDict]
    extended_mode: str = ...
    save_raw: bool = ...
    save_nonshared_raw: bool = ...
    save_thumbnail_image: bool = ...
    magic_variable: bool = ...
    save_invoice_to_structured: bool = ...
    feature_description: bool = ...

class V2ExecutionSettings(BaseModel):
    model_config: ClassVar[ConfigDict]
    type_check: str = ...
    on_iteration_error: Literal["continue", "fail_fast"] = ...

class V2RecordingSettings(BaseModel):
    model_config: ClassVar[ConfigDict]
    repr_head: Literal["on", "off"] = ...
    repr_head_len: int = ...

class V2SmartTableSettings(BaseModel):
    model_config: ClassVar[ConfigDict]
    save_table_file: bool = ...

class V2MultiDataTileSettings(BaseModel):
    model_config: ClassVar[ConfigDict]
    order: Literal["name", "filesystem"] = ...


class RdeConfig(BaseModel):
    model_config: ClassVar[ConfigDict]
    system: V2SystemSettings = Field(default_factory=V2SystemSettings)
    execution: V2ExecutionSettings = Field(default_factory=V2ExecutionSettings)
    provenance: V2RecordingSettings = Field(default_factory=V2RecordingSettings)
    custom: dict[str, Any] = Field(default_factory=dict)
    smarttable: V2SmartTableSettings = Field(default_factory=V2SmartTableSettings)
    multidata_tile: V2MultiDataTileSettings = Field(default_factory=V2MultiDataTileSettings)

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
