from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, TypeVar, overload

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.types import RdeConfig

F = TypeVar("F", bound=Callable[..., Any])
PrepareFn = Callable[[Path, RdeConfig], None]

def current_flow_id() -> str | None: ...
def push_flow(flow_id: str) -> AbstractContextManager[None]: ...
def derive_flow_id(fn: Callable[..., Any]) -> str: ...
@overload
def flow(func: F, /) -> F: ...
@overload
def flow(
    *,
    id: str | None = None,
    error_code: int | None = None,
    error_message: str | None = None,
    prepare: PrepareFn | None = None,
) -> Callable[[F], F]: ...
def flow_prepare(fn: Callable[..., Any]) -> PrepareFn | None: ...
def flow_error(fn: Callable[..., Any], error: Exception) -> StructuredError | None: ...
def flow_for_runner(fn: Callable[..., Any]) -> Callable[..., Any]: ...
