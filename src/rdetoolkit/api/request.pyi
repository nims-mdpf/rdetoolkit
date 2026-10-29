from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True, slots=True)
class FlowTarget:
    function: Callable[..., object]

@dataclass(frozen=True, slots=True)
class LegacyCallbackTarget:
    function: Callable[..., object] | None

ExecutionTarget = FlowTarget | LegacyCallbackTarget

@dataclass(frozen=True, slots=True)
class RunRequest:
    root: Path
    target: ExecutionTarget
    config_source: object | None = ...
    validate_only: bool = ...

def build_run_request(
    *,
    flow: Callable[..., object] | None,
    custom_dataset_function: Callable[..., object] | None,
    config: object | None,
    root: Path | None = ...,
    validate_only: bool = ...,
) -> RunRequest: ...
