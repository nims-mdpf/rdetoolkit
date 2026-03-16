from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar, overload

F = TypeVar('F', bound=Callable[..., Any])

@dataclass(frozen=True, slots=True)
class NodeSpec:
    id: str
    name: str
    fn: Callable[..., Any]
    input_schema: dict[str, type]
    output_schema: dict[str, type]
    tags: tuple[str, ...]
    version: str
    idempotent: bool
    source_location: str

@overload
def node(func: F, /) -> F: ...
@overload
def node(*, tags: list[str] | None = None, version: str = '0.0.0', idempotent: bool = False) -> Callable[[F], F]: ...
