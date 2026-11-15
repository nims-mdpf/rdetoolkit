from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

FAILURE_DIAGNOSTICS_SCHEMA_VERSION: str
FAILURE_DIAGNOSTICS_FORMAT: str

FailurePhase = Literal[
    "config_load",
    "mode_resolution",
    "pre_validate",
    "tile_prepare",
    "node_execution",
    "node_argument_validation",
    "artifact_publish",
    "post_validate",
    "finalize",
]

FAILURE_PHASES: tuple[FailurePhase, ...]
NODE_ARGUMENT_REJECTION: str
MAX_DIAGNOSTICS: int
MAX_FRAMES: int
MAX_CHAIN: int
MAX_MESSAGE_LENGTH: int

@dataclass(frozen=True, slots=True)
class SourceFrame:
    file: str
    line: int | None
    function: str
    def to_dict(self) -> dict[str, Any]: ...

@dataclass(frozen=True, slots=True)
class ExceptionSummary:
    relation: Literal["primary", "cause", "context"]
    type: str
    message: str
    frames: tuple[SourceFrame, ...]
    frames_truncated: bool = ...
    def to_dict(self) -> dict[str, Any]: ...

@dataclass(frozen=True, slots=True)
class FailureDiagnostic:
    phase: FailurePhase
    code: int | None
    name: str | None
    category: str
    message: str | None
    exception: ExceptionSummary | None = ...
    causes: tuple[ExceptionSummary, ...] = ...
    causes_truncated: bool = ...
    location: SourceFrame | None = ...
    iteration_index: int | None = ...
    node_id: str | None = ...
    call_id: str | None = ...
    parameter: str | None = ...
    expected_type: str | None = ...
    actual_type: str | None = ...
    artifact_path: str | None = ...
    def to_dict(self) -> dict[str, Any]: ...

def failure_diagnostic(
    exc: BaseException | None,
    *,
    phase: FailurePhase,
    error: Mapping[str, Any] | None = None,
    root: Path | None = None,
    iteration_index: int | None = None,
    node_id: str | None = None,
    call_id: str | None = None,
    artifact_path: str | None = None,
) -> FailureDiagnostic: ...
def node_argument_rejection(exc: BaseException | None) -> dict[str, Any] | None: ...
def diagnostics_filename(run_id: str) -> str: ...
def diagnostics_document(
    diagnostics: list[FailureDiagnostic],
    *,
    run_id: str,
    run_status: str,
    truncated: bool = False,
) -> dict[str, Any]: ...
