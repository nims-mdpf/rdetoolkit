from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

MAX_NAME_LENGTH: int
MAX_OUTPUT_LENGTH: int

@dataclass(frozen=True, slots=True)
class MagicOptions:
    policy: Literal["auto", "enabled", "disabled"] = ...
    missing: Literal["error", "omit"] = ...
    def __post_init__(self) -> None: ...

@dataclass(frozen=True, slots=True)
class ResolutionContext:
    _original_json: str
    _current_json: str
    _metadata_json: str | None
    rawfiles: tuple[Path, ...] = ...
    iteration_index: int = ...
    mode: str = ...
    schema_version: str = field(init=False, default="1")
    @classmethod
    def from_sources(
        cls,
        *,
        original_invoice: Mapping[str, Any],
        current_invoice: Mapping[str, Any],
        metadata: Mapping[str, Any] | None = ...,
        rawfiles: tuple[Path, ...] = ...,
        iteration_index: int = ...,
        mode: str = ...,
    ) -> ResolutionContext: ...
    @property
    def original_invoice(self) -> dict[str, Any]: ...
    @property
    def current_invoice(self) -> dict[str, Any]: ...
    @property
    def metadata(self) -> dict[str, Any] | None: ...

@dataclass(frozen=True, slots=True)
class ResolutionDiagnostic:
    destination: str
    expression: str
    offset: int
    source_scope: str
    source_path: str
    iteration_index: int
    status: str
    reason: str
    code: int | None
    message: str
    remediation: str
    def to_dict(self) -> dict[str, Any]: ...

@dataclass(frozen=True, slots=True)
class ResolutionPreview:
    diagnostics: tuple[ResolutionDiagnostic, ...]
    schema_version: str = field(init=False, default="1")
    def to_dict(self) -> dict[str, Any]: ...

def resolve_invoice(
    context: ResolutionContext,
    *,
    options: MagicOptions = ...,
    schema: Mapping[str, Any] | None = ...,
) -> dict[str, Any]: ...

def preview_invoice(
    context: ResolutionContext,
    *,
    options: MagicOptions = ...,
    schema: Mapping[str, Any] | None = ...,
    deferred_scopes: frozenset[str] = ...,
) -> ResolutionPreview: ...
